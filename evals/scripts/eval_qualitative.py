#!/usr/bin/env python3
"""Qualitative E2E runner — runs 7 curated scenarios, prints full traces for thesis §5.4.5.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_qualitative.py
    PYTHONPATH=. uv run python evals/scripts/eval_qualitative.py --runs 5
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.agent_brain.agent.agent import get_agent_app
from src.agent_brain.config import settings
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from evals.lib.stats import RunAggregate

DATA_PATH = PROJECT_ROOT / "evals" / "data" / "e2e" / "e2e_qualitative.json"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = RESULTS_DIR / f"e2e_qualitative_{TS}.json"

SEP = "─" * 72

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _extract_state(state: dict) -> dict:
    cart = state.get("active_cart")
    cart_str = None
    if cart is not None and hasattr(cart, "items"):
        # OrderItem exposes `unit_price` (may be None until the validator resolves it);
        # Cart carries the authoritative `total_price`.
        lines = [
            f"  - {i.name} ×{i.quantity} "
            f"({int(i.unit_price):,}₫/phần)" if i.unit_price else f"  - {i.name} ×{i.quantity}"
            for i in (cart.items or [])
        ]
        total = getattr(cart, "total_price", 0.0) or 0.0
        cart_str = "\n".join(lines) + f"\nTổng: {int(total):,}₫" if lines else "(trống)"
    elif cart is not None:
        cart_str = str(cart)
    return {
        "order_stage": state.get("order_stage"),
        "active_cart": cart_str,
        "current_intents": state.get("current_intents", []),
        "is_valid": state.get("is_valid"),
        "loop_count": state.get("loop_count"),
    }


def _tool_calls(stream: list) -> list[dict]:
    out = []
    for update in stream:
        for node in ("order_worker", "search_worker", "payment_dispatch"):
            for msg in update.get(node, {}).get("messages", []):
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for tc in msg.tool_calls:
                        out.append({"name": tc["name"], "args": tc.get("args", {})})
    return out


def _tool_outputs(stream: list) -> list[dict]:
    out = []
    for update in stream:
        for msg in update.get("tools", {}).get("messages", []):
            if isinstance(msg, ToolMessage):
                out.append({"name": msg.name, "content": str(msg.content)[:200]})
    return out


def _final_response(stream: list) -> str:
    for update in reversed(stream):
        for msg in update.get("response_node", {}).get("messages", []):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content
    return ""


def _check_asserts(asserts: dict, tool_calls: list, response: str,
                   confirm_items: Optional[list]) -> dict:
    results = []
    if "tool_called" in asserts:
        names = [tc["name"] for tc in tool_calls]
        results.append(("tool_called:" + asserts["tool_called"],
                        asserts["tool_called"] in names,
                        str(names)))
    if "tool_must_NOT_call" in asserts:
        blocked = asserts["tool_must_NOT_call"] if isinstance(asserts["tool_must_NOT_call"], list) else [asserts["tool_must_NOT_call"]]
        names = [tc["name"] for tc in tool_calls]
        violations = [b for b in blocked if b in names]
        results.append(("tool_must_NOT_call:" + ",".join(blocked),
                        len(violations) == 0,
                        f"violations: {violations}" if violations else "ok"))
    if "response_should_contain_one_of" in asserts:
        needles = asserts["response_should_contain_one_of"]
        results.append(("response_contains_one_of",
                        any(n.lower() in response.lower() for n in needles),
                        f"expected one of: {needles}"))
    if "confirmed_items_must_contain" in asserts and confirm_items:
        needles = asserts["confirmed_items_must_contain"]
        found = all(any(n.lower() in i.lower() for i in confirm_items) for n in needles)
        results.append(("confirmed_items_must_contain",
                        found,
                        f"expected: {needles}, actual: {confirm_items}"))
    if "confirmed_items_must_NOT_contain" in asserts and confirm_items:
        needles = asserts["confirmed_items_must_NOT_contain"]
        violations = [n for n in needles if any(n.lower() in i.lower() for i in confirm_items)]
        results.append(("confirmed_items_must_NOT_contain",
                        len(violations) == 0,
                        f"violations: {violations}" if violations else "ok"))
    return results


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _reset_state() -> None:
    """Clear conversation checkpoints and the orchestrator ledger before a run.

    Without this the scenarios resume the previous run's thread (carts survive) and the
    orchestrator's orders accumulate across runs, so every cart total and bill in the
    traces is inflated by whatever ran before. Mirrors the reset in eval_e2e.py.
    """
    checkpoint_db = PROJECT_ROOT / "storage" / "db" / "checkpoints.db"
    if checkpoint_db.exists():
        checkpoint_db.unlink()
        print(f"  Cleared checkpoint DB: {checkpoint_db}")

    orchestrator_db = PROJECT_ROOT / "storage" / "db" / "orchestrator.db"
    if orchestrator_db.exists():
        import sqlite3
        try:
            conn = sqlite3.connect(str(orchestrator_db))
            cur = conn.cursor()
            existing = {r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ("payments", "order_items", "orders", "sessions"):
                if table in existing:
                    cur.execute(f"DELETE FROM {table}")
            conn.commit()
            conn.close()
            print(f"  Reset orchestrator ledger: {orchestrator_db}")
        except sqlite3.Error as e:
            print(f"  Orchestrator DB reset failed (non-fatal): {e}")


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=5, help="Repetitions (§5.2.3 requires 5)")
    ap.add_argument("--verbose", type=int, default=0, help="Print detailed trace (0=summary only, 1=full)")
    args = ap.parse_args()

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    per_run_pass_rate: list[float] = []
    all_scenario_results: list[dict] = []

    for run_idx in range(args.runs):
        _reset_state()
        app = get_agent_app()
        graph = app
        run_id = uuid.uuid4().hex[:8]

        scenarios_out = []
        run_passed = 0
        run_total = 0

        for sc in data["scenarios"]:
            sid = sc["id"]
            table_id = sc["table_id"]
            if args.verbose:
                print(f"\n{SEP}")
                print(f"  {sid} — {sc['name']} (run {run_idx+1}/{args.runs})")
                print(f"  {sc['description']}")
                print(f"{SEP}")

            thread = {"configurable": {"thread_id": f"qual_{sid}_{run_id}__r{run_idx}"}}
            scenario_result = {"id": sid, "name": sc["name"], "category": sc["category"],
                               "turns": [], "overall_pass": True}

            for turn in sc["turns"]:
                tn = turn["turn"]
                content = turn["content"]
                asserts = turn.get("assert", {})
                note = turn.get("note", "")

                if args.verbose:
                    print(f"\n  [Turn {tn}] Khách: \"{content}\"")
                    if note:
                        print(f"           ({note})")

                t0 = time.time()
                stream = []
                state_snapshot = {}
                try:
                    for chunk in graph.stream(
                        {"messages": [HumanMessage(content=content)], "table_id": table_id},
                        thread,
                        stream_mode="updates",
                    ):
                        stream.append(chunk)
                    elapsed = time.time() - t0
                    state_snapshot = graph.get_state(thread).values

                    tcs = _tool_calls(stream)
                    tos = _tool_outputs(stream)
                    resp = _final_response(stream)
                    state = _extract_state(state_snapshot)

                    confirm_items = None
                    for tc in tcs:
                        if tc["name"] == "confirm_order":
                            confirm_items = [i.get("name", "") for i in tc.get("args", {}).get("items", [])]

                    if args.verbose:
                        print(f"  ── Tool calls ({elapsed:.1f}s):")
                        if tcs:
                            for tc in tcs:
                                print(f"       {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)[:200]})")
                        else:
                            print("       (none)")
                        print(f"  ── Response: {resp[:300]}")

                    checks = _check_asserts(asserts, tcs, resp, confirm_items)
                    turn_pass = all(p for _, p, _ in checks)
                    if not turn_pass:
                        scenario_result["overall_pass"] = False

                    if args.verbose:
                        print(f"  ── Assertions:")
                        for name, passed, detail in checks:
                            print(f"       {'✓' if passed else '✗'} {name}  |  {detail}")

                    turn_result = {
                        "turn": tn, "utterance": content, "latency_s": round(elapsed, 2),
                        "tool_calls": tcs, "tool_outputs": tos,
                        "response": resp, "state": state,
                        "assertions": [{"check": n, "passed": p, "detail": d} for n, p, d in checks],
                        "success": turn_pass,
                    }
                except Exception as e:
                    elapsed = time.time() - t0
                    if args.verbose:
                        print(f"  ── ERROR ({elapsed:.1f}s): {e}")
                    turn_result = {"turn": tn, "utterance": content, "latency_s": round(elapsed, 2),
                                   "error": str(e), "success": False}
                    scenario_result["overall_pass"] = False

                scenario_result["turns"].append(turn_result)

            run_total += 1
            if scenario_result["overall_pass"]:
                run_passed += 1

            if args.verbose:
                status = "PASS" if scenario_result["overall_pass"] else "FAIL"
                print(f"\n  >>> {sid} {status} <<<")

            scenarios_out.append(scenario_result)

        rate = run_passed / run_total if run_total else 0
        per_run_pass_rate.append(rate)
        all_scenario_results.append(scenarios_out)
        print(f"  Run {run_idx+1}/{args.runs}: {run_passed}/{run_total} = {rate:.1%}")

    pass_agg = RunAggregate("pass_rate", per_run_pass_rate)

    # Which scenarios failed, and in which runs. The full transcripts are kept for the last run
    # only because they are large, but the aggregate rate alone cannot say whether six failures
    # were one flaky scenario six times or six different ones once, and §5.4.5 makes a claim about
    # exactly that. This matrix is what supports or refutes it.
    per_scenario: dict[str, dict] = {}
    for run_idx, scenarios_out in enumerate(all_scenario_results):
        for sc in scenarios_out:
            row = per_scenario.setdefault(
                sc["id"], {"name": sc.get("name", ""), "passed_in_run": [], "failed_runs": []})
            row["passed_in_run"].append(bool(sc["overall_pass"]))
            if not sc["overall_pass"]:
                row["failed_runs"].append(run_idx + 1)
    for sid, row in per_scenario.items():
        row["pass_count"] = sum(row["passed_in_run"])
        row["runs"] = len(row["passed_in_run"])

    varying = sorted(s for s, r in per_scenario.items() if 0 < r["pass_count"] < r["runs"])
    always_failed = sorted(s for s, r in per_scenario.items() if r["pass_count"] == 0)
    total_passed = sum(r["pass_count"] for r in per_scenario.values())
    total_runs = sum(r["runs"] for r in per_scenario.values())

    print(f"\n{SEP}")
    print(f"  QUALITATIVE E2E — {args.runs} runs")
    print(f"  Scenarios passed: {pass_agg}")
    print(f"  Scenario runs passed: {total_passed}/{total_runs}")
    print(f"{SEP}\n")
    print("  Per-scenario outcome across runs:")
    for sid, row in sorted(per_scenario.items()):
        marks = "".join("." if ok else "X" for ok in row["passed_in_run"])
        print(f"    {sid}  {row['pass_count']}/{row['runs']}  [{marks}]  {row['name']}")
    print(f"\n  Varying across runs: {', '.join(varying) or 'none'}")
    if always_failed:
        print(f"  Failed in every run: {', '.join(always_failed)}")

    report = {
        "summary": {"timestamp": datetime.now().isoformat(), "runs": args.runs,
                     "pass_rate": pass_agg.as_dict(),
                     "scenario_runs_passed": total_passed, "scenario_runs_total": total_runs,
                     "varying_scenarios": varying, "always_failing_scenarios": always_failed},
        "per_run_passed": [round(r, 4) for r in per_run_pass_rate],
        "per_scenario": per_scenario,
        "results": all_scenario_results[-1] if all_scenario_results else [],  # last run's details
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
