"""Enhanced Router Evaluator — comprehensive evaluation with confusion matrix,
per-difficulty breakdown, and three ablations (tier comparison, few-shot sweep,
dynamic context ON/OFF).

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_router_full.py
    PYTHONPATH=. uv run python evals/scripts/eval_router_full.py --only ablation-tier
"""

import json
import sys
import time
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from src.agent_brain.agent.nodes.hybrid_router_node import hybrid_router_node
from src.agent_brain.agent.nodes.semantic_router_node import semantic_router_node
from src.agent_brain.agent.nodes.slm_router_node import slm_router_node

EVAL_DATA_PATH = PROJECT_ROOT / "evals" / "data" / "router" / "router_eval.json"
CONTEXT_DATA_PATH = PROJECT_ROOT / "evals" / "data" / "router" / "router_context_eval.json"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = RESULTS_DIR / f"eval_router_full_{TIMESTAMP}.log"
JSON_PATH = RESULTS_DIR / f"eval_router_full_{TIMESTAMP}.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)

INTENTS = ["ORDER", "SEARCH", "PAYMENT", "CHAT", "COMPLEX"]
INTENT_ORDER = ["ORDER", "SEARCH", "PAYMENT", "CHAT", "COMPLEX"]


def load_cases(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("cases", [])


def standardize_expected(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return raw
    if raw == "ORDER_CONFIRM":
        return ["ORDER"]
    return [raw]


def is_correct(predicted: list[str], expected: list[str]) -> bool:
    if predicted == ["ORDER_CONFIRM"] and expected == ["ORDER"]:
        return True
    return predicted == expected


def normalize_multi_intent(intents: list[str]) -> str:
    if len(intents) >= 2:
        return "COMPLEX"
    return intents[0] if intents else "UNKNOWN"


def warmup():
    logging.info("Warming up models...")
    warmup_state = {
        "messages": [HumanMessage(content="Xin chào")],
        "table_id": "T1",
        "loop_count": 0,
        "is_valid": True,
        "order_stage": "IDLE",
    }
    try:
        hybrid_router_node(warmup_state)
        logging.info("Warm-up complete.")
    except Exception as e:
        logging.warning(f"Warm-up failed: {e}")


def run_hybrid_eval(cases: list[dict]) -> dict:
    logging.info(f"\n{'='*60}")
    logging.info("HYBRID ROUTER EVALUATION (%d cases)", len(cases))
    logging.info(f"{'='*60}")

    results = []
    correct = 0
    semantic_count = 0
    slm_count = 0
    per_intent = defaultdict(lambda: {"correct": 0, "total": 0})
    per_difficulty = defaultdict(lambda: {"correct": 0, "total": 0})
    confusion = defaultdict(lambda: defaultdict(int))

    for case in tqdm(cases, desc="Hybrid"):
        case_id = case["id"]
        expected = standardize_expected(case["expected_route"])
        difficulty = case.get("difficulty", "unknown")

        state = {
            "messages": [HumanMessage(content=case["input"])],
            "table_id": "T1",
            "loop_count": 0,
            "is_valid": True,
            "order_stage": case.get("order_stage", "IDLE"),
        }

        try:
            start = time.time()
            output = hybrid_router_node(state)
            latency = time.time() - start

            predicted = output.get("current_intents", ["UNKNOWN"])
            routing_meta = output.get("routing_meta", {})
            decided_by = routing_meta.get("decided_by", "N/A")

            if decided_by == "SEMANTIC":
                semantic_count += 1
            else:
                slm_count += 1

            ok = is_correct(predicted, expected)
            if ok:
                correct += 1

            normalized = normalize_multi_intent(expected)
            per_intent[normalized]["total"] += 1
            if ok:
                per_intent[normalized]["correct"] += 1

            per_difficulty[difficulty]["total"] += 1
            if ok:
                per_difficulty[difficulty]["correct"] += 1

            pred_norm = normalize_multi_intent(predicted)
            confusion[normalized][pred_norm] += 1

            logging.info(
                "  %s: '%s' | exp=%s got=%s | by=%s | %s | %.2fs",
                "PASS" if ok else "FAIL",
                case["input"][:60],
                expected,
                predicted,
                decided_by,
                difficulty,
                latency,
            )

            results.append({
                "id": case_id,
                "input": case["input"],
                "expected": expected,
                "predicted": predicted,
                "is_correct": ok,
                "latency": latency,
                "difficulty": difficulty,
                "decided_by": decided_by,
            })

        except Exception as e:
            logging.error("  Error case %s: %s", case_id, e)

    accuracy = correct / len(cases) * 100 if cases else 0
    fast_track_rate = semantic_count / len(cases) * 100 if cases else 0

    report = {
        "mode": "hybrid",
        "accuracy": round(accuracy, 2),
        "total": len(cases),
        "correct": correct,
        "semantic_count": semantic_count,
        "slm_count": slm_count,
        "fast_track_rate": round(fast_track_rate, 2),
        "per_intent": {
            k: {
                "accuracy": round(v["correct"] / v["total"] * 100, 2) if v["total"] else 0,
                "correct": v["correct"],
                "total": v["total"],
            }
            for k, v in sorted(per_intent.items())
        },
        "per_difficulty": {
            k: {
                "accuracy": round(v["correct"] / v["total"] * 100, 2) if v["total"] else 0,
                "correct": v["correct"],
                "total": v["total"],
            }
            for k, v in sorted(per_difficulty.items())
        },
        "confusion_matrix": {k: dict(v) for k, v in sorted(confusion.items())},
        "results": results,
    }

    logging.info("\n--- Hybrid Summary ---")
    logging.info("Accuracy: %.2f%% (%d/%d)", accuracy, correct, len(cases))
    logging.info("Semantic fast-track: %d (%.1f%%)", semantic_count, fast_track_rate)
    logging.info("SLM fallback: %d (%.1f%%)", slm_count, 100 - fast_track_rate)

    for intent in sorted(per_intent.keys()):
        d = per_intent[intent]
        pct = d["correct"] / d["total"] * 100 if d["total"] else 0
        logging.info("  %s: %.1f%% (%d/%d)", intent, pct, d["correct"], d["total"])

    logging.info("\nPer-difficulty:")
    for diff in sorted(per_difficulty.keys()):
        d = per_difficulty[diff]
        pct = d["correct"] / d["total"] * 100 if d["total"] else 0
        logging.info("  %s: %.1f%% (%d/%d)", diff, pct, d["correct"], d["total"])

    logging.info("\nConfusion matrix:")
    header = "        " + "  ".join(f"{i:>8}" for i in INTENT_ORDER)
    logging.info(header)
    for actual in INTENT_ORDER:
        row = [f"{confusion[actual].get(p, 0):>8}" for p in INTENT_ORDER]
        logging.info(f"  {actual:>6} " + "  ".join(row))

    return report


def run_ablation_tier(cases: list[dict]) -> dict:
    """Ablation 1: semantic-only vs SLM-only vs hybrid."""
    logging.info(f"\n{'='*60}")
    logging.info("ABLATION 1: Tier Comparison (%d cases)", len(cases))
    logging.info(f"{'='*60}")

    modes = {}

    # Semantic-only
    logging.info("\n--- Semantic-only ---")
    sem_correct = 0
    for case in tqdm(cases, desc="Semantic-only"):
        expected = standardize_expected(case["expected_route"])
        state = {
            "messages": [HumanMessage(content=case["input"])],
            "table_id": "T1",
            "loop_count": 0,
            "is_valid": True,
            "order_stage": case.get("order_stage", "IDLE"),
        }
        try:
            output = semantic_router_node(state)
            meta = output.get("metadata", {})
            intent = meta.get("intent")
            predicted = [intent] if intent else ["CHAT"]
            if is_correct(predicted, expected):
                sem_correct += 1
        except Exception as e:
            logging.error("  Error: %s", e)

    sem_acc = sem_correct / len(cases) * 100 if cases else 0
    modes["semantic_only"] = {"accuracy": round(sem_acc, 2), "correct": sem_correct, "total": len(cases)}

    # SLM-only
    logging.info("\n--- SLM-only ---")
    slm_correct = 0
    for case in tqdm(cases, desc="SLM-only"):
        expected = standardize_expected(case["expected_route"])
        state = {
            "messages": [HumanMessage(content=case["input"])],
            "table_id": "T1",
            "loop_count": 0,
            "is_valid": True,
            "order_stage": case.get("order_stage", "IDLE"),
        }
        try:
            output = slm_router_node(state)
            predicted = output.get("current_intents", ["CHAT"])
            if is_correct(predicted, expected):
                slm_correct += 1
        except Exception as e:
            logging.error("  Error: %s", e)

    slm_acc = slm_correct / len(cases) * 100 if cases else 0
    modes["slm_only"] = {"accuracy": round(slm_acc, 2), "correct": slm_correct, "total": len(cases)}

    # Hybrid (already computed above, re-run)
    logging.info("\n--- Hybrid ---")
    hyb = run_hybrid_eval(cases)
    modes["hybrid"] = {
        "accuracy": hyb["accuracy"],
        "correct": hyb["correct"],
        "total": hyb["total"],
        "fast_track_rate": hyb["fast_track_rate"],
    }

    logging.info("\n--- Tier Comparison Summary ---")
    logging.info("  Semantic-only:  %.2f%%", modes["semantic_only"]["accuracy"])
    logging.info("  SLM-only:       %.2f%%", modes["slm_only"]["accuracy"])
    logging.info("  Hybrid:         %.2f%% (%.1f%% fast-tracked)", modes["hybrid"]["accuracy"], modes["hybrid"]["fast_track_rate"])

    return {"ablation_tier": modes}


def run_ablation_context(cases: list[dict]) -> dict:
    """Ablation 3: dynamic context ON vs OFF."""
    logging.info(f"\n{'='*60}")
    logging.info("ABLATION 3: Dynamic Context ON vs OFF (%d cases)", len(cases))
    logging.info(f"{'='*60}")

    on_correct = 0
    off_correct = 0

    for case in tqdm(cases, desc="Context ablation"):
        expected = standardize_expected(case["expected_route"])
        order_stage = case.get("order_stage", "IDLE")

        # Context ON (default hybrid router)
        state_on = {
            "messages": [HumanMessage(content=case["input"])],
            "table_id": "T1",
            "loop_count": 0,
            "is_valid": True,
            "order_stage": order_stage,
        }
        try:
            output = hybrid_router_node(state_on)
            predicted = output.get("current_intents", ["UNKNOWN"])
            if is_correct(predicted, expected):
                on_correct += 1
            logging.info(
                "  CTX-ON  '%s' stage=%s exp=%s got=%s %s",
                case["input"][:50], order_stage, expected, predicted,
                "PASS" if is_correct(predicted, expected) else "FAIL",
            )
        except Exception as e:
            logging.error("  CTX-ON error: %s", e)

        # Context OFF (always IDLE)
        state_off = {
            "messages": [HumanMessage(content=case["input"])],
            "table_id": "T1",
            "loop_count": 0,
            "is_valid": True,
            "order_stage": "IDLE",
        }
        try:
            output = hybrid_router_node(state_off)
            predicted = output.get("current_intents", ["UNKNOWN"])
            if is_correct(predicted, expected):
                off_correct += 1
            logging.info(
                "  CTX-OFF '%s' stage=IDLE(fake) exp=%s got=%s %s",
                case["input"][:50], expected, predicted,
                "PASS" if is_correct(predicted, expected) else "FAIL",
            )
        except Exception as e:
            logging.error("  CTX-OFF error: %s", e)

    on_acc = on_correct / len(cases) * 100 if cases else 0
    off_acc = off_correct / len(cases) * 100 if cases else 0

    logging.info("\n--- Context Ablation Summary ---")
    logging.info("  Dynamic context ON:  %.2f%% (%d/%d)", on_acc, on_correct, len(cases))
    logging.info("  Dynamic context OFF: %.2f%% (%d/%d)", off_acc, off_correct, len(cases))

    return {
        "ablation_context": {
            "context_on": {"accuracy": round(on_acc, 2), "correct": on_correct, "total": len(cases)},
            "context_off": {"accuracy": round(off_acc, 2), "correct": off_correct, "total": len(cases)},
        }
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enhanced Router Evaluation")
    parser.add_argument("--only", choices=["hybrid", "ablation-tier", "ablation-context"], default=None)
    args = parser.parse_args()

    warmup()

    report = {"timestamp": TIMESTAMP}

    if args.only is None or args.only == "hybrid":
        cases = load_cases(EVAL_DATA_PATH)
        report["hybrid"] = run_hybrid_eval(cases)

    if args.only is None or args.only == "ablation-tier":
        cases = load_cases(EVAL_DATA_PATH)
        report.update(run_ablation_tier(cases))

    if args.only is None or args.only == "ablation-context":
        if not CONTEXT_DATA_PATH.exists():
            logging.error("Context dataset not found at %s", CONTEXT_DATA_PATH)
        else:
            cases = load_cases(CONTEXT_DATA_PATH)
            report.update(run_ablation_context(cases))

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logging.info("\nReport saved to %s", JSON_PATH)
    logging.info("Detailed logs saved to %s", LOG_PATH)


if __name__ == "__main__":
    main()
