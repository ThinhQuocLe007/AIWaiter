#!/usr/bin/env python3
"""Multi-intent verbalisation: three-layer loss attribution (thesis §5.4.3)

The agent is a pipeline of three independently failing stages. A turn where the customer
asked for two intents and received an answer for one may have broken at any of them:

    Layer 1 — Router:  did the router queue every intent the customer expressed?
    Layer 2 — Worker:  did every queued intent actually execute a tool call?
    Layer 3 — Response: did every executed intent reach the customer's reply?

These are measured as three separate metrics on the same turns. Before this revision the
script attributed all loss to the response layer, which loaded the final stage with
failures that occurred earlier. Inspection of the 53 loss turns showed three distinct
failure mechanisms: (1) the router queuing an intent the customer never expressed,
(2) a queued intent never producing a tool call, and (3) generic ORDER execution errors
whose replies the scorer deliberately excluded. Each belongs to a different architectural
layer, and reporting them separately turns a single blended number into a diagnostic.

Scoring uses two rules (see NEGATIVE_OUTCOME_EVIDENCE): the strict rule credits only the
happy-path evidence enumerated per case in the dataset, and the corrected rule also credits a
contentful refusal, since a customer told "that dish is not on the menu" has been told the fate
of their request. Both are reported so the effect of the rule is visible.

Because the agent is stochastic, this defaults to N=5 runs and reports mean [min-max], per
the protocol in §5.2.3.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_multi_intent.py
    PYTHONPATH=. uv run python evals/scripts/eval_multi_intent.py --runs 1 --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

from evals.lib.stats import Proportion, RunAggregate, markdown_table  # noqa: E402

DATASET = PROJECT_ROOT / "evals" / "data" / "e2e" / "multi_intent_eval.json"
RESULTS = PROJECT_ROOT / "evals" / "results"

MERGE = {"ORDER_CONFIRM": "ORDER_CONFIRM"}  # kept distinct here: confirming is its own utterance

TOOL_TO_INTENT = {
    "add_cart": "ORDER",
    "remove_cart": "ORDER",
    "clear_cart": "ORDER",
    "confirm_order": "ORDER_CONFIRM",
    "search": "SEARCH",
    "request_payment": "PAYMENT",
    "verify_payment": "PAYMENT",
}


# Per-intent phrasings for a *contentful negative outcome*: the system executed the intent,
# could not complete it, and told the customer specifically why. These are copied from the
# response templates in the agent itself, not written to fit observed failures:
#   "chưa có đơn hàng"        -> response_node.py, request_payment with no order in session
#   "không có trong thực đơn" -> response_template.py, off-menu rejection (3 call sites)
#
# The generic failure string "có lỗi khi xử lý đơn" (response_template.py) is deliberately
# EXCLUDED. It tells the customer that something went wrong without saying which request it
# concerns, so it is not evidence that a particular intent was verbalised.
#
# Applied uniformly to every case of the given intent. The per-case `evidence` lists in the
# dataset enumerate happy-path wording only, so without this a correct refusal scores as a
# verbalisation failure. Both the strict and the corrected figure are reported so the effect
# of this rule is visible rather than baked in.
NEGATIVE_OUTCOME_EVIDENCE = {
    "PAYMENT": ["chưa có đơn hàng"],
    "ORDER": ["không có trong thực đơn"],
    "ORDER_CONFIRM": ["chưa có đơn hàng", "không có trong thực đơn"],
    "SEARCH": ["không có trong thực đơn"],
}


def mentioned(
    intent: str,
    reply: str,
    evidence: dict[str, list[str]],
    allow_negative_outcome: bool = True,
) -> bool:
    """Whether the reply carries lexical evidence of a given intent having been performed.

    Lexical matching is a deliberate choice over an LLM judge: the question is only whether
    the customer was told about the action, the evidence terms are enumerated per case in the
    dataset, and an LLM judge would add a second stochastic component to a measurement whose
    whole purpose is to quantify a response-selection bug.

    An intent counts as verbalised when the customer learns the fate of that request, whether
    it succeeded or was correctly refused. Passing ``allow_negative_outcome=False`` reproduces
    the original happy-path-only rule.
    """
    terms = list(evidence.get(intent, []))
    if allow_negative_outcome:
        terms += NEGATIVE_OUTCOME_EVIDENCE.get(intent, [])
    low = reply.lower()
    return any(t.lower() in low for t in terms)


def run_case(app, case: dict, run_idx: int) -> dict[str, Any]:
    thread_id = f"eval_multi_intent_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    state = {
        "messages": [HumanMessage(content=case["utterance"])],
        "table_id": f"T_mi_{case['id']}",
    }
    routed: list[str] = []
    executed_tools: list[str] = []
    validator_rejected = False
    out: dict[str, Any] = {}
    for update in app.stream(state, config=config, stream_mode="updates"):
        for node, delta in update.items():
            if not isinstance(delta, dict):
                continue
            if delta.get("current_intents") and not routed:
                routed = list(delta["current_intents"])
            for m in delta.get("messages", []) or []:
                if isinstance(m, ToolMessage):
                    executed_tools.append(m.name)
            if delta.get("is_valid") is False:
                validator_rejected = True
            out |= delta

    final = app.get_state(config).values
    reply = ""
    for msg in reversed(final.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            reply = msg.content
            break

    expected = case["expected_intents"]
    executed = list(dict.fromkeys(
        TOOL_TO_INTENT.get(t) for t in executed_tools if t in TOOL_TO_INTENT))

    routing_precision = len(set(routed) & set(expected)) / len(routed) if routed else 0.0
    execution_rate = len(set(executed) & set(routed)) / len(routed) if routed else 0.0
    spoken_of_executed = [i for i in executed if mentioned(i, reply, case["evidence"])]
    verbalisation_rate = len(spoken_of_executed) / len(executed) if executed else 0.0
    spoken_of_routed = [i for i in routed if mentioned(i, reply, case["evidence"])]
    spoken_of_expected = [i for i in expected if mentioned(i, reply, case["evidence"])]
    strict_of_routed = [
        i for i in routed
        if mentioned(i, reply, case["evidence"], allow_negative_outcome=False)
    ]
    strict_of_executed = [
        i for i in executed
        if mentioned(i, reply, case["evidence"], allow_negative_outcome=False)
    ]

    return {
        "id": case["id"],
        "run": run_idx,
        "utterance": case["utterance"],
        "difficulty": case["difficulty"],
        "expected_intents": expected,
        "routed_intents": routed,
        "executed_intents": executed,
        "executed_tools": executed_tools,
        "router_found_all": sorted(set(routed)) == sorted(set(expected)),
        "n_routed": len(routed),
        "n_executed": len(executed),
        "n_expected": len(expected),
        "routing_precision": routing_precision,
        "execution_rate": execution_rate,
        "verbalisation_rate": verbalisation_rate,
        "n_mentioned_of_executed": len(spoken_of_executed),
        "n_mentioned_of_routed": len(spoken_of_routed),
        "fully_verbalised": bool(executed) and len(spoken_of_executed) == len(executed),
        "coverage_of_expected": len(spoken_of_expected) / len(expected) if expected else 0.0,
        "verbalisation_rate_strict": len(strict_of_executed) / len(executed) if executed else 0.0,
        "fully_verbalised_strict": bool(executed) and len(strict_of_executed) == len(executed),
        "mentioned": spoken_of_executed,
        "mentioned_strict": strict_of_executed,
        "mentioned_of_expected": spoken_of_expected,
        "routing_meta": out.get("routing_meta"),
        "validator_rejected": validator_rejected,
        "generic_error_reply": "có lỗi khi xử lý đơn" in reply,
        "retry_apology_reply": "em xin lỗi" in reply and "kiểm tra lại giúp em" in reply,
        "reply": reply,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=5, help="repetitions (§5.1.3 requires 5)")
    ap.add_argument("--limit", type=int, help="only the first N cases, for a quick check")
    ap.add_argument("--json", type=Path, help="output path (default: timestamped)")
    args = ap.parse_args()

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = data["cases"][: args.limit] if args.limit else data["cases"]

    from src.agent_brain.agent.agent import get_agent_app

    app = get_agent_app()

    print(f"\n{'=' * 78}")
    print("  Multi-intent verbalisation — three-layer loss attribution")
    print(f"  {len(cases)} cases x {args.runs} run(s)")
    print(f"{'=' * 78}\n")

    all_rows: list[dict[str, Any]] = []
    per_run_rate: list[float] = []
    per_run_full: list[float] = []
    per_run_cov: list[float] = []
    per_run_rate_strict: list[float] = []
    per_run_full_strict: list[float] = []
    per_run_routing_precision: list[float] = []
    per_run_execution_rate: list[float] = []

    for run_idx in range(args.runs):
        rows = []
        for case in cases:
            try:
                row = run_case(app, case, run_idx)
            except Exception as exc:
                print(f"  !! {case['id']} raised: {type(exc).__name__}: {exc}")
                continue
            rows.append(row)
            flag = "OK  " if row["fully_verbalised"] else "LOSS"
            if row["execution_rate"] < 1.0 and row["fully_verbalised"]:
                flag = "EPRT"  # execution partial but still fully verbalised
            if not row["router_found_all"]:
                flag = "RMISS"
            if row["executed_intents"] and not row["executed_intents"]:
                flag = "NEXEC"  # nothing executed
            print(f"  [{flag}] {row['id']} run{run_idx}  routed={row['routed_intents']}"
                  f"  executed={row['executed_intents']}"
                  f"  spoken={row['mentioned']}")
        all_rows.extend(rows)
        if rows:
            per_run_rate.append(sum(r["verbalisation_rate"] for r in rows) / len(rows))
            per_run_full.append(sum(r["fully_verbalised"] for r in rows) / len(rows))
            per_run_cov.append(sum(r["coverage_of_expected"] for r in rows) / len(rows))
            per_run_rate_strict.append(
                sum(r["verbalisation_rate_strict"] for r in rows) / len(rows))
            per_run_full_strict.append(
                sum(r["fully_verbalised_strict"] for r in rows) / len(rows))
            per_run_routing_precision.append(
                sum(r["routing_precision"] for r in rows) / len(rows))
            per_run_execution_rate.append(
                sum(r["execution_rate"] for r in rows) / len(rows))

    if not all_rows:
        print("\n  no cases completed")
        return 1

    rate_agg = RunAggregate("verbalisation_rate", per_run_rate)
    rate_strict_agg = RunAggregate("verbalisation_rate_strict", per_run_rate_strict)
    full_strict_agg = RunAggregate("fully_verbalised_rate_strict", per_run_full_strict)
    full_agg = RunAggregate("fully_verbalised_rate", per_run_full)
    cov_agg = RunAggregate("coverage_of_expected", per_run_cov)
    routing_precision_agg = RunAggregate("routing_precision", per_run_routing_precision)
    execution_rate_agg = RunAggregate("execution_rate", per_run_execution_rate)

    first_run = [r for r in all_rows if r["run"] == 0]
    full_count = sum(r["fully_verbalised"] for r in first_run)
    router_ok = sum(r["router_found_all"] for r in first_run)
    gen_err_count = sum(r["generic_error_reply"] for r in first_run)
    retry_apology_count = sum(r["retry_apology_reply"] for r in first_run)
    validator_rej_count = sum(r["validator_rejected"] for r in first_run)

    print(f"\n{'=' * 78}")
    print("  THREE-LAYER LOSS ATTRIBUTION")
    print(f"{'=' * 78}\n")
    print(f"  ── Layer 1: Router (intents the router queues vs. what the customer asked)")
    print(f"     Routing precision : {routing_precision_agg}")
    print(f"     Router found all   : {Proportion(router_ok, len(first_run))}")
    print()
    print(f"  ── Layer 2: Execution (routed intents that actually produce tool calls)")
    print(f"     Execution rate     : {execution_rate_agg}")
    print(f"     ORDER execution failures (generic error response) : {Proportion(gen_err_count, len(first_run))}")
    print(f"     Retry/apology template responses                  : {Proportion(retry_apology_count, len(first_run))}")
    print(f"     Validator rejected a turn                        : {Proportion(validator_rej_count, len(first_run))}")
    print()
    print(f"  ── Layer 3: Verbalisation (executed intents spoken in the reply)")
    print(f"     Verbalisation rate (corrected)  : {rate_agg}")
    print(f"     Fully verbalised turns          : {full_agg}")
    print(f"     Fully verbalised (run 0)        : {Proportion(full_count, len(first_run))}")
    print()
    print(f"  Coverage of what was asked : {cov_agg}")
    print(f"\n  Same, happy-path evidence only (strict, the original rule):")
    print(f"    Verbalisation rate : {rate_strict_agg}")
    print(f"    Fully verbalised   : {full_strict_agg}")
    print("  The gap between the two is turns where the system correctly refused an intent\n"
          "  and said so, which the happy-path evidence lists cannot match.")
    print("\n  Coverage is scored over what the customer asked for, so it absorbs all\n"
          "  three failure modes — router miss, execution miss, and verbalisation miss.")

    by_n: dict[int, list[float]] = defaultdict(list)
    for r in all_rows:
        by_n[r["n_executed"]].append(r["verbalisation_rate"])
    print("\n  By number of intents actually executed in the turn:\n")
    print(markdown_table(
        ["Intents executed", "Turns", "Mean verbalisation rate"],
        [[n, len(v), f"{sum(v) / len(v):.1%}"] for n, v in sorted(by_n.items())]))

    lost = [r for r in first_run if not r["fully_verbalised"]]
    if lost:
        print(f"\n  Turns where an executed intent was never spoken ({len(lost)}):\n")
        for r in lost[:12]:
            missing = [i for i in r["expected_intents"] if i not in r["mentioned_of_expected"]]
            print(f"    [{r['id']}] \"{r['utterance'][:52]}\"")
            print(f"       routed={r['routed_intents']} executed={r['executed_intents']}"
                  f"  spoken={r['mentioned']} lost={missing}")

    gen_errs = [r for r in first_run if r["generic_error_reply"]]
    if gen_errs:
        print(f"\n  Turns with generic ORDER execution error ({len(gen_errs)}):\n")
        for r in gen_errs:
            print(f"    [{r['id']}] \"{r['utterance'][:52]}\""
                  f"  routed={r['routed_intents']} exec={r['executed_intents']}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.json or RESULTS / f"multi_intent_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated": stamp,
        "n_cases": len(cases),
        "runs": args.runs,
        "routing_precision": routing_precision_agg.as_dict(),
        "execution_rate": execution_rate_agg.as_dict(),
        "verbalisation_rate": rate_agg.as_dict(),
        "fully_verbalised_rate": full_agg.as_dict(),
        "coverage_of_expected": cov_agg.as_dict(),
        "verbalisation_rate_strict": rate_strict_agg.as_dict(),
        "fully_verbalised_rate_strict": full_strict_agg.as_dict(),
        "negative_outcome_evidence": NEGATIVE_OUTCOME_EVIDENCE,
        "tool_to_intent": TOOL_TO_INTENT,
        "generic_error_reply_count": gen_err_count,
        "retry_apology_count": retry_apology_count,
        "validator_rejected_count": validator_rej_count,
        "by_intent_count": {str(k): round(sum(v) / len(v), 4) for k, v in sorted(by_n.items())},
        "rows": all_rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
