"""Validator Ablation — runs E2E scenarios with validator ON vs OFF
to prove the validator prevents LLM hallucinations from reaching the cart.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_validator_ablation.py
    PYTHONPATH=. uv run python evals/scripts/eval_validator_ablation.py --bypass-validator
"""

import json
import os
import sys
import time
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

E2E_DIR = os.path.join(PROJECT_ROOT, "evals", "data", "e2e")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "evals", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")

DATASETS = [
    "e2e_conversations_part1.json",
    "e2e_conversations_part2.json",
    "e2e_out_of_menu_test.json",
]


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

        if bypass_validator:
            state["bypass_validator"] = True  # Signal for patched graph

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

        unavail = validator_actions.get("unavailable_items") or []
        ambig = validator_actions.get("ambiguous_items") or []

        # Check for off-menu items reaching confirm_order
        confirm_calls = [tc for tc in tool_calls if tc.get("name") == "confirm_order"]
        if confirm_calls:
            for tc in confirm_calls:
                items = tc.get("args", {}).get("items", [])
                invalid = [i for i in items if not i.get("is_valid", True)]
                if invalid:
                    bad_confirm_count += 1
                    off_menu_in_cart_count += len(invalid)
                    log(f"      [ALERT] confirm_order with {len(invalid)} invalid items: {[i['name'] for i in invalid]}", log_path)

        # Check add_cart for invalid items
        add_calls = [tc for tc in tool_calls if tc.get("name") == "add_cart"]
        for tc in add_calls:
            items = tc.get("args", {}).get("items", [])
            invalid = [i for i in items if not i.get("is_valid", True)]
            if invalid:
                off_menu_in_cart_count += len(invalid)
                log(f"      [ALERT] add_cart with {len(invalid)} invalid items: {[i.get('name') for i in invalid]}", log_path)

        if unavail:
            log(f"      Validator OFF-MENU: {[u['name'] for u in unavail]}", log_path)
        if ambig:
            log(f"      Validator AMBIGUOUS: {[a['name'] for a in ambig]}", log_path)

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
            "off_menu_in_this_turn": len(unavail),
            "ambiguous_in_this_turn": len(ambig),
            "latency": round(latency, 2),
            "response_preview": response[:100] if response else "",
        })

    return {
        "id": sid,
        "name": scenario["name"],
        "success": scenario_ok,
        "off_menu_in_cart_total": off_menu_in_cart_count,
        "bad_confirm_count": bad_confirm_count,
        "total_tool_calls": total_tool_calls,
        "turns": turns_results,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validator Ablation Evaluation")
    parser.add_argument("--bypass-validator", action="store_true", help="Run with validator bypassed")
    args = parser.parse_args()

    suffix = "validator_off" if args.bypass_validator else "validator_on"
    log_path = os.path.join(RESULTS_DIR, f"validator_ablation_{suffix}_{TS}.log")
    report_path = os.path.join(RESULTS_DIR, f"validator_ablation_{suffix}_{TS}.json")

    log(f"VALIDATOR ABLATION — Validator {'OFF' if args.bypass_validator else 'ON'}", log_path)
    log("=" * 60, log_path)

    # Clean checkpoints
    checkpoint_db = os.path.join(PROJECT_ROOT, "storage", "db", "checkpoints.db")
    if os.path.exists(checkpoint_db):
        os.remove(checkpoint_db)

    log("Loading agent...", log_path)
    app = get_agent_app()

    warmup_cfg = {"configurable": {"thread_id": "warmup_val"}}
    for _ in app.stream(
        {"messages": [HumanMessage(content="warmup")], "table_id": "warmup"},
        config=warmup_cfg,
        stream_mode="updates",
    ):
        pass
    log("Agent ready.", log_path)

    all_scenarios = []
    for ds in DATASETS:
        path = os.path.join(E2E_DIR, ds)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            scenarios = data.get("scenarios", [])
            all_scenarios.extend(scenarios)
            log(f"Loaded {len(scenarios)} scenarios from {ds}", log_path)
        else:
            log(f"Warning: {path} not found", log_path)

    log(f"\nRunning {len(all_scenarios)} scenarios...", log_path)

    results = []
    total_off_menu = 0
    total_bad_confirm = 0
    passed = 0

    for sc in all_scenarios:
        r = run_scenario_with_validator(app, sc, args.bypass_validator, log_path)
        results.append(r)
        total_off_menu += r["off_menu_in_cart_total"]
        total_bad_confirm += r["bad_confirm_count"]
        if r["success"]:
            passed += 1

    total = len(results)
    rate = passed / total if total > 0 else 0

    log(f"\n{'='*60}", log_path)
    log("VALIDATOR ABLATION SUMMARY", log_path)
    log(f"{'='*60}", log_path)
    log(f"Validator:          {'OFF' if args.bypass_validator else 'ON'}", log_path)
    log(f"Total Scenarios:    {total}", log_path)
    log(f"Passed:             {passed}", log_path)
    log(f"Failed:             {total - passed}", log_path)
    log(f"Pass Rate:          {rate:.2%}", log_path)
    log(f"Off-menu in cart:   {total_off_menu}", log_path)
    log(f"Bad confirm_order:  {total_bad_confirm}", log_path)
    log("", log_path)
    for r in results:
        status = "PASS" if r["success"] else "FAIL"
        log(f"  [{status}] {r['id']}: {r['name']} | off_menu={r['off_menu_in_cart_total']} bad_confirm={r['bad_confirm_count']}", log_path)

    report = {
        "timestamp": TS,
        "validator": "OFF" if args.bypass_validator else "ON",
        "summary": {
            "pass_rate": round(rate, 4),
            "total_scenarios": total,
            "passed": passed,
            "off_menu_items_in_cart": total_off_menu,
            "bad_confirm_order_count": total_bad_confirm,
        },
        "results": results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log(f"\nReport saved to {report_path}", log_path)


if __name__ == "__main__":
    main()
