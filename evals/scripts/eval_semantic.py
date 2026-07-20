"""semantic-only evaluation — measures centroid classifier accuracy on single-intent text.

No SLM, no hybrid, no planner. Pure semantic_router_node against a dataset
of 100 self-contained single-intent utterances across 5 classes.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_semantic.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_DATA_PATH = PROJECT_ROOT / "evals" / "data" / "router" / "semantic_eval.json"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = RESULTS_DIR / f"eval_semantic_{timestamp}.log"
JSON_PATH = RESULTS_DIR / f"eval_semantic_{timestamp}.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# List of 5 valid intent labels
ALL_INTENTS = ["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT"]


def _ensure_list(value: str | list) -> list[str]:
    return value if isinstance(value, list) else [value]


def main() -> None:
    if not EVAL_DATA_PATH.exists():
        logging.error("Eval dataset not found at %s", EVAL_DATA_PATH)
        return

    with open(EVAL_DATA_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    cases = dataset.get("cases", [])
    if not cases:
        logging.error("No cases found.")
        return

    logging.info("=" * 60)
    logging.info("SEMANTIC ROUTER EVALUATION — %d single-intent cases", len(cases))
    logging.info("Dataset: %s (v%s)", dataset["dataset"], dataset["version"])
    logging.info("=" * 60)

    # ── Warm-up ────────────────────────────────────────────────────────────
    logging.info("\nWarming up semantic router + embedding model ...")
    from src.agent_brain.agent.nodes.semantic_router_node import semantic_router_node
    warmup_state = {
        "messages": [HumanMessage(content="Xin chào")],
        "table_id": "T1",
        "loop_count": 0,
        "is_valid": True,
        "order_stage": "IDLE",
    }
    try:
        semantic_router_node(warmup_state)
        logging.info("Warm-up complete.\n")
    except Exception as e:
        logging.warning("Warm-up issue (non-fatal): %s\n", e)

    # ── Evaluate ───────────────────────────────────────────────────────────
    results = []
    correct = 0
    per_class = {k: {"correct": 0, "total": 0, "latencies": []} for k in ALL_INTENTS}
    confusion = defaultdict(lambda: defaultdict(int))
    per_difficulty = defaultdict(lambda: {"correct": 0, "total": 0})
    fast_track_count = 0
    all_confidences: list[float] = []
    all_gaps: list[float] = []

    for case in tqdm(cases, desc="Semantic-only"):
        case_id = case["id"]
        utterance = case["input"]
        expected = _ensure_list(case["expected_route"])[0]
        difficulty = case.get("difficulty", "unknown")

        state = {
            "messages": [HumanMessage(content=utterance)],
            "table_id": "T1",
            "loop_count": 0,
            "is_valid": True,
            "order_stage": "IDLE",  # semantic router ignores this
        }

        try:
            t0 = time.time()
            output = semantic_router_node(state)
            latency = time.time() - t0

            meta = output.get("metadata", {})
            predicted = meta.get("intent") or "NONE"
            confidence = meta.get("confidence", 0.0)
            all_sims = meta.get("all_similarities", {})

            sims_sorted = sorted(all_sims.values(), reverse=True)
            gap = sims_sorted[0] - sims_sorted[1] if len(sims_sorted) >= 2 else 0.0
        except Exception as e:
            logging.error("  Error %s: %s", case_id, e)
            predicted = "ERROR"
            confidence = 0.0
            latency = 0.0
            gap = 0.0
            all_sims = {}

        is_correct = (predicted == expected)
        if is_correct:
            correct += 1
            per_class[expected]["correct"] += 1

        if predicted != "NONE" and predicted != "ERROR":
            fast_track_count += 1
            all_confidences.append(confidence)
            all_gaps.append(gap)

        per_class[expected]["total"] += 1
        if latency > 0:
            per_class[expected]["latencies"].append(latency)

        confusion[expected][predicted] += 1
        per_difficulty[difficulty]["total"] += 1
        if is_correct:
            per_difficulty[difficulty]["correct"] += 1

        results.append({
            "id": case_id,
            "input": utterance,
            "expected": expected,
            "predicted": predicted,
            "is_correct": is_correct,
            "confidence": round(confidence, 4),
            "gap": round(gap, 4),
            "all_similarities": {k: round(v, 4) for k, v in all_sims.items()},
            "latency": round(latency, 4),
            "difficulty": difficulty,
            "note": case.get("note", ""),
        })

        if not is_correct:
            logging.warning(
                "  [FAIL] %s | \"%s\" → expected=%s got=%s conf=%.4f gap=%.4f",
                case_id, utterance[:60], expected, predicted, confidence, gap,
            )

    # ── Report ─────────────────────────────────────────────────────────────
    accuracy = correct / len(cases) * 100
    fast_track_rate = fast_track_count / len(cases) * 100

    logging.info("\n" + "=" * 60)
    logging.info("RESULTS SUMMARY")
    logging.info("=" * 60)
    logging.info("Overall accuracy:  %.2f%% (%d/%d)", accuracy, correct, len(cases))
    logging.info("Fast-track rate:   %.2f%% (%d/%d resolved with an intent)", fast_track_rate, fast_track_count, len(cases))
    if all_confidences:
        logging.info("Mean confidence:   %.4f", sum(all_confidences) / len(all_confidences))
    if all_gaps:
        logging.info("Mean gap:          %.4f", sum(all_gaps) / len(all_gaps))
    logging.info("Avg latency:       %.4f s", sum(r["latency"] for r in results) / len(cases))

    logging.info("\n--- Per-Class Accuracy ---")
    for intent in ALL_INTENTS:
        d = per_class[intent]
        pct = d["correct"] / d["total"] * 100 if d["total"] else 0
        avg_lat = sum(d["latencies"]) / len(d["latencies"]) if d["latencies"] else 0
        logging.info("  %-16s  %.1f%%  (%d/%d)  avg %.4f s", intent, pct, d["correct"], d["total"], avg_lat)

    logging.info("\n--- Per-Difficulty Accuracy ---")
    for diff in ["easy", "medium", "hard"]:
        d = per_difficulty[diff]
        if d["total"]:
            pct = d["correct"] / d["total"] * 100
            logging.info("  %-8s  %.1f%%  (%d/%d)", diff, pct, d["correct"], d["total"])

    logging.info("\n--- Confusion Matrix (rows=expected, cols=predicted) ---")
    header = "              " + "  ".join(f"{i:>10}" for i in ALL_INTENTS + ["NONE"])
    logging.info(header)
    for actual in ALL_INTENTS:
        row = f"  {actual:>12}"
        for pred in ALL_INTENTS + ["NONE"]:
            row += f"  {confusion[actual][pred]:>10}"
        logging.info(row)

    logging.info("\n--- Failed Cases ---")
    failures = [r for r in results if not r["is_correct"]]
    if failures:
        for f in failures:
            logging.info(
                "  %s | \"%s\" → expected=%s got=%s | conf=%.4f gap=%.4f | %s",
                f["id"], f["input"], f["expected"], f["predicted"],
                f["confidence"], f["gap"], f["note"],
            )
    else:
        logging.info("  (none — all cases correct)")

    # ── Save JSON report ───────────────────────────────────────────────────
    report = {
        "dataset": dataset["dataset"],
        "version": dataset["version"],
        "timestamp": timestamp,
        "embedding_model": _get_active_model(),
        "total": len(cases),
        "correct": correct,
        "accuracy": round(accuracy, 2),
        "fast_track_rate": round(fast_track_rate, 2),
        "avg_confidence": round(sum(all_confidences) / len(all_confidences), 4) if all_confidences else 0,
        "avg_gap": round(sum(all_gaps) / len(all_gaps), 4) if all_gaps else 0,
        "per_class": {
            intent: {
                "accuracy": round(d["correct"] / d["total"] * 100, 1) if d["total"] else 0,
                "correct": d["correct"],
                "total": d["total"],
                "avg_latency": round(sum(d["latencies"]) / len(d["latencies"]), 4) if d["latencies"] else 0,
            }
            for intent, d in per_class.items()
        },
        "per_difficulty": {
            diff: {
                "accuracy": round(d["correct"] / d["total"] * 100, 1) if d["total"] else 0,
                "correct": d["correct"],
                "total": d["total"],
            }
            for diff, d in per_difficulty.items()
        },
        "confusion_matrix": {
            actual: {pred: confusion[actual][pred] for pred in ALL_INTENTS + ["NONE"]}
            for actual in ALL_INTENTS
        },
        "failures": failures,
        "results": results,
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logging.info("\nReport saved to %s", JSON_PATH)
    logging.info("Log saved to %s", LOG_PATH)

    # ── Gate check ─────────────────────────────────────────────────────────
    pass_gate = True
    if accuracy < 92:
        logging.warning("\n⚠ GATE FAILED: overall accuracy %.1f%% < 92%% threshold", accuracy)
        pass_gate = False
    for intent in ALL_INTENTS:
        d = per_class[intent]
        if d["total"] and d["correct"] / d["total"] < 0.85:
            logging.warning("⚠ GATE FAILED: %s accuracy %.1f%% < 85%% threshold", intent, d["correct"] / d["total"] * 100)
            pass_gate = False
    if fast_track_rate < 40:
        logging.warning("⚠ GATE FAILED: fast-track rate %.1f%% < 40%% threshold", fast_track_rate)
        pass_gate = False

    if pass_gate:
        logging.info("\n✓ ALL GATES PASSED — semantic router is ready for split-then-classify refactor")
    else:
        logging.info("\n✗ GATES NOT MET — review failures, add centroid utterances, or recalibrate thresholds before proceeding")


def _get_active_model() -> str:
    try:
        from src.agent_brain.config import settings
        return str(settings.EMBEDDING_MODEL)
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
