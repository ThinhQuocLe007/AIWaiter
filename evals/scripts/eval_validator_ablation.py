"""Validator Ablation — runs E2E scenarios with validator ON vs OFF
to prove the validator prevents LLM hallucinations from reaching the cart.

Off-menu detection resolves dish names against menu.json directly rather than
reading the validator's is_valid flag, so the OFF arm (where the validator is
bypassed and nothing sets the flag) cannot silently hide hallucinations.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_validator_ablation.py
    PYTHONPATH=. uv run python evals/scripts/eval_validator_ablation.py --bypass-validator
    PYTHONPATH=. uv run python evals/scripts/eval_validator_ablation.py --runs 5
"""

import json
import os
import sys
import time
import unicodedata
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.agent_brain.agent.agent import get_agent_app
from evals.lib.stats import RunAggregate


def install_bypass() -> None:
    """Replace the validator node with a pass-through, before the graph is built."""
    from typing import Any as _Any
    from src.agent_brain.agent import graph as _graph

    def _pass_through(state: dict) -> dict[str, _Any]:
        return {"is_valid": True, "feedback": None}

    _graph.deterministic_validator_node = _pass_through


E2E_DIR = os.path.join(PROJECT_ROOT, "evals", "data", "e2e")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "evals", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")

DATASETS = [
    "e2e_conversations_part1.json",
    "e2e_conversations_part2.json",
    "e2e_out_of_menu_test.json",
]


def _load_menu_names() -> set[str]:
    """Load the set of valid dish names from menu.json."""
    menu_path = os.path.join(PROJECT_ROOT, "assets", "data", "menu.json")
    with open(menu_path, "r", encoding="utf-8") as f:
        menu = json.load(f)
    return {item["name"] for item in menu}


MENU_NAMES = _load_menu_names()


def _normalize(name: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace — same as the validator."""
    text = unicodedata.normalize("NFD", name.lower().strip())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d").replace(" ", "")
    return text


def _resolve_against_menu(item_name: str) -> bool:
    """Return True if item_name resolves to a known menu dish (any resolution level)."""
    norm = _normalize(item_name)
    norm_menu = {_normalize(n): n for n in MENU_NAMES}

    if norm in norm_menu:
        return True

    prefixes = [k for k in norm_menu if k.startswith(norm)]
    if len(prefixes) == 1:
        return True
    if prefixes:
        return False  # ambiguous, not auto-resolved

    for k in norm_menu:
        if norm in k:
            return True

    return False


def log(msg: str, log_path: str):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def extract_tool_calls(stream: list) -> list[dict]:
    calls = []
    for update in stream:
        for node in ["order_worker", "search_worker", "payment_dispatch"]:
            if node in update:
                for msg in update[node].get("messages", []):
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        calls.extend(msg.tool_calls)
    return calls


def extract_tool_outputs(stream: list) -> list[dict]:
    outputs = []
    for update in stream:
        if "tools" in update:
            for msg in update["tools"].get("messages", []):
                if isinstance(msg, ToolMessage):
                    outputs.append({"name": msg.name, "content": str(msg.content)})
    return outputs


def extract_ai_response(stream: list) -> str:
    for update in reversed(stream):
        if "response_node" in update:
            for msg in reversed(update["response_node"].get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content:
                    return msg.content
    return ""


def extract_validator_actions(stream: list) -> dict:
    for update in stream:
        if "validator" in update:
            return update["validator"]
    return {}


def check_off_menu_items(tool_calls: list[dict]) -> tuple[list[str], list[str]]:
    """Resolve every item name in cart tool calls against menu.json.

    Returns (off_menu_names, ambiguous_names).  Does not look at is_valid flags —
    the OFF arm has no validator to set them.
    """
    off_menu: list[str] = []
    ambiguous: list[str] = []

    for tc in tool_calls:
        tool_name = tc.get("name", "")
        if tool_name not in ("add_cart", "confirm_order"):
            continue
        items = tc.get("args", {}).get("items", [])
        for item in items:
            name = item.get("name", "")
            if not name:
                continue
            if _resolve_against_menu(name):
                continue
            off_menu.append(name)

    return off_menu, ambiguous


def run_scenario_with_validator(app, scenario: dict, bypass_validator: bool, log_path: str) -> dict:
    sid = scenario["id"]
    thread_id = f"val_ablation_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    mode = "OFF" if bypass_validator else "ON"
    log(f"\n  Scenario {sid}: {scenario['name']} (Validator {mode})", log_path)

    turns_results = []
    scenario_ok = True
    off_menu_in_cart_count = 0
    bad_confirm_count = 0
    total_tool_calls = 0

    for turn_data in scenario["turns"]:
        t = turn_data["turn"]
        user_input = turn_data["content"]
        asserts = turn_data.get("assert", {})

        log(f"    Turn {t}: {user_input[:80]}", log_path)

        state = {
            "messages": [HumanMessage(content=user_input)],
            "table_id": scenario["table_id"],
        }

        start = time.time()
        stream = []
        for chunk in app.stream(state, config=config, stream_mode="updates"):
            stream.append(chunk)
        latency = time.time() - start

        tool_calls = extract_tool_calls(stream)
        tool_outputs = extract_tool_outputs(stream)
        response = extract_ai_response(stream)
        validator_actions = extract_validator_actions(stream)
        final_state = app.get_state(config)
        sv = final_state.values if final_state else {}

        total_tool_calls += len(tool_calls)

        # Resolve item names against menu.json (not the validator's is_valid flag)
        off_menu_names, ambiguous_names = check_off_menu_items(tool_calls)
        off_menu_in_cart_count += len(off_menu_names)

        # Check confirm_order calls
        confirm_calls = [tc for tc in tool_calls if tc.get("name") == "confirm_order"]
        for tc in confirm_calls:
            items = tc.get("args", {}).get("items", [])
            off = [i.get("name", "?") for i in items if not _resolve_against_menu(i.get("name", ""))]
            if off:
                bad_confirm_count += 1
                log(f"      [ALERT] confirm_order with {len(off)} off-menu items: {off}", log_path)

            # Also check: confirm_order with empty cart
            if not items:
                bad_confirm_count += 1
                log(f"      [ALERT] confirm_order with empty cart", log_path)

        if off_menu_names:
            log(f"      [ALERT] OFF-MENU items in cart tools: {off_menu_names}", log_path)

        # Check assertions
        ok = True
        tc_names = [tc.get("name") for tc in tool_calls]
        expected_tool = asserts.get("tool_called")
        if expected_tool:
            if expected_tool not in tc_names:
                ok = False
                log(f"      [FAIL] Expected tool '{expected_tool}' not in {tc_names}", log_path)

        not_expected = asserts.get("tool_must_NOT_call")
        if not_expected and not_expected in tc_names:
            ok = False
            log(f"      [FAIL] Forbidden tool '{not_expected}' was called", log_path)

        if not ok:
            scenario_ok = False

        turns_results.append({
            "turn": t,
            "success": ok,
            "tool_calls": tc_names,
            "off_menu_items": off_menu_names,
            "latency": round(latency, 2),
            "response_preview": response[:100] if response else "",
        })

    return {
        "id": sid,
        "name": scenario["name"],
        "success": scenario_ok,
        "off_menu_items_in_cart": off_menu_in_cart_count,
        "bad_confirm_count": bad_confirm_count,
        "total_tool_calls": total_tool_calls,
        "turns": turns_results,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validator Ablation Evaluation")
    parser.add_argument("--bypass-validator", action="store_true", help="Run with validator bypassed")
    parser.add_argument("--runs", type=int, default=5, help="Repetitions (§5.2.3 requires 5)")
    args = parser.parse_args()

    suffix = "validator_off" if args.bypass_validator else "validator_on"

    # Per-run metrics for aggregation
    per_run_pass_rate: list[float] = []
    per_run_off_menu: list[int] = []
    per_run_bad_confirm: list[int] = []
    per_run_connection_errors: list[int] = []
    all_run_results: list[dict] = []

    for run_idx in range(args.runs):
        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_log_path = os.path.join(RESULTS_DIR, f"validator_ablation_{suffix}_{run_ts}_run{run_idx}.log")

        log(f"VALIDATOR ABLATION — Validator {'OFF' if args.bypass_validator else 'ON'} — Run {run_idx+1}/{args.runs}", run_log_path)
        log("=" * 60, run_log_path)

        checkpoint_db = os.path.join(PROJECT_ROOT, "storage", "db", "checkpoints.db")
        if os.path.exists(checkpoint_db):
            os.remove(checkpoint_db)

        if args.bypass_validator:
            install_bypass()
            log("Validator node replaced with pass-through (OFF arm)", run_log_path)

        log("Loading agent...", run_log_path)
        app = get_agent_app()

        warmup_cfg = {"configurable": {"thread_id": f"warmup_val_{run_idx}"}}
        for _ in app.stream(
            {"messages": [HumanMessage(content="warmup")], "table_id": "warmup"},
            config=warmup_cfg,
            stream_mode="updates",
        ):
            pass
        log("Agent ready.", run_log_path)

        all_scenarios = []
        for ds in DATASETS:
            path = os.path.join(E2E_DIR, ds)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                scenarios = data.get("scenarios", [])
                all_scenarios.extend(scenarios)
                log(f"Loaded {len(scenarios)} scenarios from {ds}", run_log_path)
            else:
                log(f"Warning: {path} not found", run_log_path)

        log(f"\nRunning {len(all_scenarios)} scenarios...", run_log_path)

        results = []
        total_off_menu = 0
        total_bad_confirm = 0
        connection_errors = 0
        passed = 0

        for sc in all_scenarios:
            r = run_scenario_with_validator(app, sc, args.bypass_validator, run_log_path)
            results.append(r)
            total_off_menu += r["off_menu_items_in_cart"]
            total_bad_confirm += r["bad_confirm_count"]
            # Detect connection errors from agent replies
            for t in r.get("turns", []):
                resp = t.get("response_preview", "")
                if "connection" in resp.lower() or "timeout" in resp.lower():
                    connection_errors += 1
            if r["success"]:
                passed += 1

        total = len(results)
        rate = passed / total if total > 0 else 0

        per_run_pass_rate.append(rate)
        per_run_off_menu.append(total_off_menu)
        per_run_bad_confirm.append(total_bad_confirm)
        per_run_connection_errors.append(connection_errors)
        all_run_results.append({"run": run_idx, "passed": passed, "total": total,
                                 "off_menu": total_off_menu, "bad_confirm": total_bad_confirm,
                                 "connection_errors": connection_errors})

        log(f"\n{'='*60}", run_log_path)
        log(f"VALIDATOR ABLATION SUMMARY — Run {run_idx+1}", run_log_path)
        log(f"{'='*60}", run_log_path)
        log(f"Validator:          {'OFF' if args.bypass_validator else 'ON'}", run_log_path)
        log(f"Pass Rate:          {rate:.2%} ({passed}/{total})", run_log_path)
        log(f"Off-menu items in cart tools: {total_off_menu}", run_log_path)
        log(f"Bad confirm_order:  {total_bad_confirm}", run_log_path)
        log(f"Connection errors:  {connection_errors}", run_log_path)

    # Final aggregate report
    final_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(RESULTS_DIR, f"validator_ablation_{suffix}_{final_ts}.json")

    pass_agg = RunAggregate("pass_rate", per_run_pass_rate)
    off_menu_agg = RunAggregate("off_menu_items", [float(v) for v in per_run_off_menu])
    bad_confirm_agg = RunAggregate("bad_confirm_order", [float(v) for v in per_run_bad_confirm])

    conn_total = sum(per_run_connection_errors)
    if conn_total > 0:
        print(f"\n  !! {conn_total} connection errors across {args.runs} runs — see per-run logs")
        print(f"  !! Report may be untrustworthy (Ollama disconnect, §5.1.3 protocol)")

    print(f"\n{'='*60}")
    print(f"VALIDATOR ABLATION — {'OFF' if args.bypass_validator else 'ON'} — {args.runs} runs")
    print(f"{'='*60}")
    print(f"  Pass rate: {pass_agg}")
    print(f"  Off-menu items: {off_menu_agg}")
    print(f"  Bad confirm_order: {bad_confirm_agg}")

    report = {
        "timestamp": final_ts,
        "validator": "OFF" if args.bypass_validator else "ON",
        "runs": args.runs,
        "summary": {
            "pass_rate": pass_agg.as_dict(),
            "off_menu_items_in_cart_tools": off_menu_agg.as_dict(),
            "bad_confirm_order_count": bad_confirm_agg.as_dict(),
        },
        "per_run": all_run_results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
