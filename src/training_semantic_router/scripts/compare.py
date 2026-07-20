#!/usr/bin/env python3
"""A/B comparison: hybrid_router vs trained classifier on router_eval.json.

Usage:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/compare.py
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/compare.py --json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import HumanMessage

from src.training_semantic_router.classifier.predict import classify as cls_predict

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("compare")

EVAL_PATH = PROJECT_ROOT / "evals" / "data" / "router" / "router_eval.json"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAVED_DIR = Path(__file__).resolve().parent.parent / "classifier" / "saved"

ORDER_CONFIRM_MERGE = {"ORDER_CONFIRM": "ORDER"}


def _map_hybrid_label(intent: str) -> str:
    return ORDER_CONFIRM_MERGE.get(intent, intent)


def _build_mock_state(utterance: str, case: dict | None = None) -> dict:
    state: dict[str, Any] = {
        "messages": [HumanMessage(content=utterance)],
        "current_intents": [],
        "routing_meta": None,
        "intent_queries": None,
        "table_id": "",
        "table_context": None,
        "active_cart": None,
        "order_stage": "IDLE",
        "search_context": None,
        "is_valid": True,
        "feedback": None,
        "loop_count": 0,
        "unavailable_items": None,
        "ambiguous_items": None,
        "last_tool": None,
        "ui_action": None,
        "order_confirmed": False,
        "response_context": None,
        "delegate_reason": None,
        "shown_dishes": None,
    }
    if case and "order_stage" in (case.get("context") or {}):
        state["order_stage"] = case["context"]["order_stage"]
    elif case and case.get("order_stage"):
        state["order_stage"] = case["order_stage"]
    return state


def _run_hybrid(utterance: str, case: dict | None = None) -> dict[str, Any]:
    from src.agent_brain.agent.nodes.hybrid_router_node import hybrid_router_node

    state = _build_mock_state(utterance, case)

    if case and case.get("order_stage"):
        state["order_stage"] = case["order_stage"]

    result = hybrid_router_node(state)
    return result


def _run_classifier(utterance: str, case: dict | None = None) -> dict[str, Any]:
    ctx = None
    if case:
        nested_ctx = case.get("context")
        if nested_ctx:
            ctx = nested_ctx
        elif case.get("order_stage"):
            ctx = {"order_stage": case["order_stage"]}
    return cls_predict(
        utterance,
        state=ctx,
        model_path=SAVED_DIR / "model.pt",
        label_path=SAVED_DIR / "label_encoder.json",
        scaler_path=SAVED_DIR / "scaler.npz",
    )


def _is_multi_intent(expected) -> bool:
    return isinstance(expected, list)


def _normalize_expected(expected) -> list[str]:
    if isinstance(expected, list):
        return [_map_hybrid_label(e) for e in expected]
    return [_map_hybrid_label(expected)]


def main():
    parser = argparse.ArgumentParser(description="A/B comparison: hybrid router vs classifier")
    parser.add_argument("--eval-path", default=str(EVAL_PATH))
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    with open(args.eval_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    cases = eval_data["cases"]

    results = []
    hybrid_correct = 0
    cls_correct = 0
    hybrid_wrong = 0
    cls_wrong = 0
    cls_wins = 0
    hybrid_wins = 0
    both_correct = 0
    both_wrong = 0
    total = 0

    print(f"\n{'=' * 80}")
    print(f"  A/B Comparison: Hybrid Router vs Trained Classifier")
    print(f"  {len(cases)} cases from {args.eval_path}")
    print(f"{'=' * 80}")

    print(f"\n{'ID':<10} {'Utterance':<40} {'Expected':<22} {'Hybrid':<22} {'Classifier':<22} {'Result'}")
    print("-" * 120)

    for case in cases:
        uid = case["id"]
        utterance = case["input"]
        expected_raw = case.get("expected_route", case.get("intent"))
        expected_list = _normalize_expected(expected_raw)
        is_multi = _is_multi_intent(expected_raw)

        hybrid_result = _run_hybrid(utterance, case)
        hybrid_intents = hybrid_result.get("current_intents", ["CHAT"])
        hybrid_canon = [_map_hybrid_label(i) for i in hybrid_intents]
        hybrid_decided = hybrid_result.get("routing_meta", {}).get("decided_by", "?")

        cls_result = _run_classifier(utterance, case)
        cls_intent = cls_result["intent"]
        cls_conf = cls_result["confidence"]

        if is_multi:
            h_match = hybrid_canon == expected_list
            c_match = cls_intent in expected_list
        else:
            h_match = len(hybrid_canon) == 1 and hybrid_canon[0] == expected_list[0]
            c_match = cls_intent == expected_list[0]

        if h_match:
            hybrid_correct += 1
        else:
            hybrid_wrong += 1

        if c_match:
            cls_correct += 1
        else:
            cls_wrong += 1

        if h_match and c_match:
            both_correct += 1
        elif not h_match and not c_match:
            both_wrong += 1
        elif h_match and not c_match:
            hybrid_wins += 1
        elif not h_match and c_match:
            cls_wins += 1

        total += 1

        expected_str = "/".join(expected_list) if len(expected_list) > 1 else expected_list[0]
        hybrid_str = "/".join(hybrid_canon) if len(hybrid_canon) > 1 else hybrid_canon[0]
        cls_str = f"{cls_intent} ({cls_conf:.2f})"

        result_icon = ""
        if h_match and c_match:
            result_icon = "=="
        elif h_match and not c_match:
            result_icon = "H+"
        elif not h_match and c_match:
            result_icon = "C+"
        else:
            result_icon = "XX"

        print(f"{uid:<10} {utterance[:38]:<40} {expected_str:<22} {hybrid_str:<22} {cls_str:<22} {result_icon}")

        results.append({
            "id": uid,
            "utterance": utterance,
            "difficulty": case.get("difficulty", "?"),
            "expected": expected_raw,
            "expected_4class": expected_list,
            "is_multi": is_multi,
            "hybrid_intents": hybrid_intents,
            "hybrid_canon": hybrid_canon,
            "hybrid_decided_by": hybrid_decided,
            "hybrid_correct": h_match,
            "classifier_intent": cls_intent,
            "classifier_confidence": round(cls_conf, 4),
            "classifier_correct": c_match,
            "classifier_all_probs": cls_result.get("all_probs", {}),
            "win": "hybrid" if (h_match and not c_match) else ("classifier" if (c_match and not h_match) else ("both" if (h_match and c_match) else "neither")),
        })

    print("-" * 120)
    print(f"\n{'=' * 60}")
    print(f"  Summary")
    print(f"{'=' * 60}")
    print(f"  Total cases:                     {total}")
    print(f"  Multi-intent cases:              {sum(1 for c in cases if _is_multi_intent(c.get('expected_route', c.get('intent'))))}")
    print(f"")
    print(f"  Hybrid Router accuracy:          {hybrid_correct}/{total} ({hybrid_correct/total*100:.1f}%)")
    print(f"  Trained Classifier accuracy:     {cls_correct}/{total} ({cls_correct/total*100:.1f}%)")
    print(f"")
    print(f"  Both correct:                    {both_correct}")
    print(f"  Both wrong:                      {both_wrong}")
    print(f"  Hybrid wins / Classifier loses:  {hybrid_wins}")
    print(f"  Classifier wins / Hybrid loses:  {cls_wins}")
    print(f"{'=' * 60}")

    single_cases = [c for c in cases if not _is_multi_intent(c.get("expected_route", c.get("intent")))]
    single_results = [r for r in results if not r["is_multi"]]
    h_single = sum(1 for r in single_results if r["hybrid_correct"])
    c_single = sum(1 for r in single_results if r["classifier_correct"])

    print(f"\n  Single-intent only ({len(single_cases)} cases):")
    print(f"    Hybrid:   {h_single}/{len(single_cases)} ({h_single/len(single_cases)*100:.1f}%)")
    print(f"    Classifier: {c_single}/{len(single_cases)} ({c_single/len(single_cases)*100:.1f}%)")

    multi_cases = [c for c in cases if _is_multi_intent(c.get("expected_route", c.get("intent")))]
    multi_results = [r for r in results if r["is_multi"]]
    h_multi = sum(1 for r in multi_results if r["hybrid_correct"])
    c_multi = sum(1 for r in multi_results if r["classifier_correct"])
    if multi_cases:
        print(f"\n  Multi-intent only ({len(multi_cases)} cases):")
        print(f"    Hybrid:   {h_multi}/{len(multi_cases)} ({h_multi/len(multi_cases)*100:.1f}%)")
        print(f"    Classifier: {c_multi}/{len(multi_cases)} ({c_multi/len(multi_cases)*100:.1f}%) [single-label only]")

    print(f"\n  Classifier wins:")
    for r in results:
        if r["win"] == "classifier":
            print(f"    [{r['id']}] \"{r['utterance'][:55]}\" | expected={r['expected']} | hybrid={r['hybrid_canon']} | cls={r['classifier_intent']}")

    print(f"\n  Hybrid wins:")
    for r in results:
        if r["win"] == "hybrid":
            print(f"    [{r['id']}] \"{r['utterance'][:55]}\" | expected={r['expected']} | hybrid={r['hybrid_canon']} | cls={r['classifier_intent']}")

    output_path = DATA_DIR / "comparison_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": total,
            "hybrid_accuracy": round(hybrid_correct/total, 4),
            "classifier_accuracy": round(cls_correct/total, 4),
            "hybrid_correct": hybrid_correct,
            "classifier_correct": cls_correct,
            "both_correct": both_correct,
            "both_wrong": both_wrong,
            "hybrid_wins": hybrid_wins,
            "classifier_wins": cls_wins,
            "single_intent": {
                "count": len(single_cases),
                "hybrid_accuracy": round(h_single/len(single_cases), 4) if single_cases else 0,
                "classifier_accuracy": round(c_single/len(single_cases), 4) if single_cases else 0,
            },
            "details": results,
        }, f, ensure_ascii=False, indent=2)
    logger.warning("Report saved to %s", output_path)
    print(f"\n  Report saved to: {output_path}")


if __name__ == "__main__":
    main()
