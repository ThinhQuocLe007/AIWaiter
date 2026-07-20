#!/usr/bin/env python3
"""Evaluate trained classifier against test_holdout.json.

Usage:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/evaluate.py
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/evaluate.py --context-aware
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.training_semantic_router.classifier.predict import classify

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluate")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAVED_DIR = Path(__file__).resolve().parent.parent / "classifier" / "saved"


def _per_class_metrics(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str],
) -> dict:
    from collections import Counter

    cm = Counter()
    for t, p in zip(y_true, y_pred):
        cm[(t, p)] += 1

    metrics = {}
    for label in labels:
        tp = cm.get((label, label), 0)
        fp = sum(cm.get((other, label), 0) for other in labels if other != label)
        fn = sum(cm.get((label, other), 0) for other in labels if other != label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": tp + fn,
        }

    return metrics


def _confusion_matrix(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str],
) -> list[list[int]]:
    from collections import Counter

    cm = Counter()
    for t, p in zip(y_true, y_pred):
        cm[(t, p)] += 1

    matrix = []
    for t in labels:
        row = [cm.get((t, p), 0) for p in labels]
        matrix.append(row)
    return matrix


def main():
    parser = argparse.ArgumentParser(description="Evaluate intent classifier")
    parser.add_argument("--test-data", default=str(DATA_DIR / "test_holdout.json"))
    parser.add_argument("--model-path", default=str(SAVED_DIR / "model.pt"))
    parser.add_argument("--label-path", default=str(SAVED_DIR / "label_encoder.json"))
    parser.add_argument("--scaler-path", default=str(SAVED_DIR / "scaler.npz"))
    parser.add_argument("--context-aware", action="store_true", help="Supply context features from test data")
    parser.add_argument("--no-context", action="store_true", help="Run without context features (IDLE defaults)")
    args = parser.parse_args()

    test_path = Path(args.test_data)
    if not test_path.exists():
        logger.error("Test data not found: %s", test_path)
        sys.exit(1)

    model_path = Path(args.model_path)
    if not model_path.exists():
        logger.error("Model not found: %s", model_path)
        sys.exit(1)

    with open(test_path, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    cases = test_data["cases"]
    labels = ["ORDER", "SEARCH", "PAYMENT", "CHAT"]

    y_true = []
    y_pred = []
    y_conf = []
    details = []

    logger.info("Evaluating %d test cases ...", len(cases))
    for case in cases:
        utterance = case["utterance"]
        expected = case["intent"]

        if args.no_context or not args.context_aware:
            state = None
        else:
            ctx = case.get("context")
            state = ctx if ctx else None

        try:
            result = classify(
                utterance,
                state=state,
                model_path=model_path,
                label_path=Path(args.label_path),
                scaler_path=Path(args.scaler_path),
            )
        except Exception as e:
            logger.error("Failed on case %s: %s", case.get("id", "?"), e)
            result = {"intent": "CHAT", "confidence": 0.0}
            result["all_probs"] = {l: 0.0 for l in labels}

        predicted = result["intent"]
        confidence = result["confidence"]
        correct = predicted == expected

        y_true.append(expected)
        y_pred.append(predicted)
        y_conf.append(confidence)

        details.append({
            "id": case.get("id", "?"),
            "utterance": utterance,
            "expected": expected,
            "predicted": predicted,
            "confidence": round(confidence, 4),
            "correct": correct,
            "all_probs": {k: round(v, 4) for k, v in result.get("all_probs", {}).items()},
        })

    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)

    print("\n" + "=" * 60)
    print(f"  Overall Accuracy: {accuracy * 100:.2f}% ({sum(1 for t,p in zip(y_true, y_pred) if t==p)}/{len(y_true)})")
    print(f"  Mean Confidence (correct): {np.mean([c for c, pair in zip(y_conf, zip(y_true, y_pred)) if pair[0]==pair[1]]):.4f}")
    print(f"  Mean Confidence (all):       {np.mean(y_conf):.4f}")
    print("=" * 60)

    per_class = _per_class_metrics(y_true, y_pred, labels)
    print(f"\n{'Intent':<12} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-" * 55)
    for label in labels:
        m = per_class[label]
        print(f"{label:<12} {m['precision']:>10.4f} {m['recall']:>10.4f} {m['f1']:>10.4f} {m['support']:>10}")

    cm = _confusion_matrix(y_true, y_pred, labels)
    print(f"\nConfusion Matrix (rows=true, cols=predicted):")
    header = " " * 12 + "".join(f"{l:>10}" for l in labels)
    print(header)
    for i, label in enumerate(labels):
        row = f"{label:<12}" + "".join(f"{v:>10}" for v in cm[i])
        print(row)

    print("\nMisclassified cases:")
    for d in details:
        if not d["correct"]:
            print(f"  [{d['id']}] \"{d['utterance'][:60]}\" expected={d['expected']} → predicted={d['predicted']} (conf={d['confidence']:.2f})")

    output_path = Path(__file__).resolve().parent.parent / "data" / "eval_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "accuracy": round(accuracy, 4),
            "per_class": per_class,
            "confusion_matrix": {labels[i]: {labels[j]: cm[i][j] for j in range(len(labels))} for i in range(len(labels))},
            "mean_confidence": round(float(np.mean(y_conf)), 4),
            "mode": "context-aware" if (args.context_aware and not args.no_context) else "no-context",
            "total_cases": len(y_true),
            "correct": sum(1 for t, p in zip(y_true, y_pred) if t == p),
            "details": details,
        }, f, ensure_ascii=False, indent=2)
    logger.info("Report saved to %s", output_path)


if __name__ == "__main__":
    main()
