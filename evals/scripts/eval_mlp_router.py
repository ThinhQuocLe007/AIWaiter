#!/usr/bin/env python3
"""Evaluate MLP intent classifier against the new eval datasets.

Three benchmarks:
  1. single_intent_eval.json  — accuracy, per-class F1, confusion matrix
  2. multi_intent_detection.json — detection rate (conf < 0.7 on true multi-intent)
  3. context_dependent_eval.json — with/without context accuracy

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_mlp_router.py
    PYTHONPATH=. uv run python evals/scripts/eval_mlp_router.py --datasets single multi context
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.training_semantic_router.classifier.predict import classify  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_mlp")

DATA_DIR = PROJECT_ROOT / "evals" / "data" / "router"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
SAVED_DIR = PROJECT_ROOT / "src" / "training_semantic_router" / "classifier" / "saved"

DATASETS = {
    "single": DATA_DIR / "single_intent_eval.json",
    "multi": DATA_DIR / "multi_intent_detection.json",
    "context": DATA_DIR / "context_dependent_eval.json",
}

LABELS = ["ORDER", "SEARCH", "PAYMENT", "CHAT"]
THRESHOLD = 0.7

_BOUNDARY_RE = re.compile(r"\b(rồi thì|với lại|rồi|và|thì|xong)\b|à mà|,\s*mà\b")


def _has_boundary_markers(utterance: str) -> bool:
    low = utterance.lower()
    for m in _BOUNDARY_RE.finditer(low):
        before = low[:m.start()].split()
        after = low[m.end():].split()
        if len(before) >= 2 and len(after) >= 2:
            return True
    return False


def _per_class_metrics(y_true: list[str], y_pred: list[str]) -> dict:
    from collections import Counter

    cm = Counter()
    for t, p in zip(y_true, y_pred):
        cm[(t, p)] += 1

    metrics = {}
    for label in LABELS:
        tp = cm.get((label, label), 0)
        fp = sum(cm.get((other, label), 0) for other in LABELS if other != label)
        fn = sum(cm.get((label, other), 0) for other in LABELS if other != label)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        metrics[label] = {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "support": tp + fn}
    return metrics


def _confusion_matrix(y_true: list[str], y_pred: list[str]) -> list[list[int]]:
    from collections import Counter

    cm = Counter()
    for t, p in zip(y_true, y_pred):
        cm[(t, p)] += 1
    return [[cm.get((t, p), 0) for p in LABELS] for t in LABELS]


def eval_single_intent(data_path: Path) -> dict:
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]
    y_true, y_pred, y_conf, details = [], [], [], []

    for case in cases:
        utterance = case["utterance"]
        expected = case["intent"]

        start = time.perf_counter()
        result = classify(utterance, state=None,
                          model_path=SAVED_DIR / "model.pt",
                          label_path=SAVED_DIR / "label_encoder.json",
                          scaler_path=SAVED_DIR / "scaler.npz")
        latency_ms = (time.perf_counter() - start) * 1000

        predicted = result["intent"]
        confidence = result["confidence"]
        correct = predicted == expected

        y_true.append(expected)
        y_pred.append(predicted)
        y_conf.append(confidence)
        details.append({
            "utterance": utterance, "expected": expected,
            "predicted": predicted, "confidence": round(confidence, 4),
            "correct": correct, "latency_ms": round(latency_ms, 2),
            "all_probs": {k: round(v, 4) for k, v in result.get("all_probs", {}).items()},
        })

    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
    per_class = _per_class_metrics(y_true, y_pred)
    cm = _confusion_matrix(y_true, y_pred)
    latencies = [d["latency_ms"] for d in details]

    print("\n" + "=" * 65)
    print(f"  SINGLE-INTENT ACCURACY — {len(cases)} cases")
    print(f"  Accuracy: {accuracy*100:.1f}% ({sum(1 for t,p in zip(y_true, y_pred) if t==p)}/{len(cases)})")
    print(f"  Mean confidence (correct): {np.mean([c for c, pair in zip(y_conf, zip(y_true, y_pred)) if pair[0]==pair[1]]):.4f}")
    print(f"  Mean confidence (all):     {np.mean(y_conf):.4f}")
    print(f"  Latency p50/p95: {np.percentile(latencies, 50):.1f} / {np.percentile(latencies, 95):.1f} ms")
    print("=" * 65)

    print(f"\n{'Intent':<10} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>8}")
    print("-" * 52)
    for label in LABELS:
        m = per_class[label]
        print(f"{label:<10} {m['precision']:>10.4f} {m['recall']:>10.4f} {m['f1']:>10.4f} {m['support']:>8}")

    print(f"\n{'':>10}", end="")
    for l in LABELS:
        print(f"{l:>10}", end="")
    print()
    for i, label in enumerate(LABELS):
        print(f"{label:<10}", end="")
        for v in cm[i]:
            print(f"{v:>10}", end="")
        print()

    errors = [d for d in details if not d["correct"]]
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for d in errors:
            print(f"  '{d['utterance'][:60]}' → {d['predicted']} (exp: {d['expected']}, conf={d['confidence']:.3f})")

    return {
        "benchmark": "single_intent",
        "accuracy": round(accuracy, 4),
        "per_class": per_class,
        "confusion_matrix": {LABELS[i]: {LABELS[j]: cm[i][j] for j in range(len(LABELS))} for i in range(len(LABELS))},
        "mean_confidence": round(float(np.mean(y_conf)), 4),
        "latency_p50_ms": round(float(np.percentile(latencies, 50)), 2),
        "latency_p95_ms": round(float(np.percentile(latencies, 95)), 2),
        "correct": sum(1 for t, p in zip(y_true, y_pred) if t == p),
        "total": len(y_true),
        "details": details,
    }


def eval_multi_intent_detection(data_path: Path) -> dict:
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]
    true_multi = [c for c in cases if len(c["intents"]) > 1]
    pseudo_multi = [c for c in cases if len(c["intents"]) == 1]

    details = []

    # Evaluate true multi-intent: MLP should produce conf < THRESHOLD OR contain boundary markers
    detected_by_conf = 0
    detected_by_boundary = 0
    detected_total = 0
    for case in true_multi:
        result = classify(case["utterance"], state=None,
                          model_path=SAVED_DIR / "model.pt",
                          label_path=SAVED_DIR / "label_encoder.json",
                          scaler_path=SAVED_DIR / "scaler.npz")
        has_boundary = _has_boundary_markers(case["utterance"])
        low_conf = result["confidence"] < THRESHOLD
        detected = has_boundary or low_conf

        if low_conf:
            detected_by_conf += 1
        if has_boundary:
            detected_by_boundary += 1
        if detected:
            detected_total += 1

        details.append({
            "utterance": case["utterance"],
            "intents": case["intents"],
            "type": "true_multi",
            "predicted": result["intent"],
            "confidence": round(result["confidence"], 4),
            "has_boundary_markers": has_boundary,
            "low_confidence": low_conf,
            "detected": detected,
            "all_probs": {k: round(v, 4) for k, v in result.get("all_probs", {}).items()},
        })

    detection_rate = detected_total / len(true_multi) if true_multi else 1.0

    # Evaluate pseudo multi-intent: should NOT be detected (no boundary, conf >= threshold)
    false_alarms = 0
    correct_single = 0
    for case in pseudo_multi:
        result = classify(case["utterance"], state=None,
                          model_path=SAVED_DIR / "model.pt",
                          label_path=SAVED_DIR / "label_encoder.json",
                          scaler_path=SAVED_DIR / "scaler.npz")
        has_boundary = _has_boundary_markers(case["utterance"])
        low_conf = result["confidence"] < THRESHOLD
        detected = has_boundary or low_conf
        if detected:
            false_alarms += 1
        if result["intent"] == case["intents"][0]:
            correct_single += 1
        details.append({
            "utterance": case["utterance"],
            "intents": case["intents"],
            "type": "pseudo_multi",
            "predicted": result["intent"],
            "confidence": round(result["confidence"], 4),
            "has_boundary_markers": has_boundary,
            "low_confidence": low_conf,
            "detected": detected,
            "correct_intent": result["intent"] == case["intents"][0],
            "all_probs": {k: round(v, 4) for k, v in result.get("all_probs", {}).items()},
        })

    print("\n" + "=" * 65)
    print(f"  MULTI-INTENT DETECTION — {len(cases)} cases")
    print(f"  Detection = has_boundary_markers OR conf < {THRESHOLD}")
    print(f"  Boundary markers: rồi | và | thì | xong | rồi thì | với lại | à mà | ,mà")
    print("=" * 65)
    print(f"\n  True multi-intent ({len(true_multi)} cases):")
    print(f"    Detected:   {detected_total}/{len(true_multi)} = {detection_rate*100:.1f}%")
    print(f"    By boundary: {detected_by_boundary}")
    print(f"    By low conf: {detected_by_conf}")
    print(f"  Pseudo multi-intent ({len(pseudo_multi)} cases):")
    print(f"    False alarms: {false_alarms}/{len(pseudo_multi)}")
    print(f"    Correct intent: {correct_single}/{len(pseudo_multi)}")

    # Show missed detections (true multi-intent but not detected)
    missed = [d for d in details if d["type"] == "true_multi" and not d["detected"]]
    if missed:
        print(f"\n  Missed detections ({len(missed)} cases — needs boundary marker in utterance):")
        for d in missed:
            print(f"    '{d['utterance'][:70]}' → {d['predicted']} (conf={d['confidence']:.3f})")

    false_pos = [d for d in details if d["type"] == "pseudo_multi" and d["detected"]]
    if false_pos:
        print(f"\n  False alarms ({len(false_pos)} — single-intent but flagged as multi):")
        for d in false_pos:
            print(f"    '{d['utterance'][:60]}' → {d['predicted']} (conf={d['confidence']:.3f})")

    return {
        "benchmark": "multi_intent_detection",
        "threshold": THRESHOLD,
        "boundary_markers": "rồi|và|thì|xong|rồi thì|với lại|à mà|,mà",
        "true_multi_count": len(true_multi),
        "detected_total": detected_total,
        "detected_by_boundary": detected_by_boundary,
        "detected_by_low_conf": detected_by_conf,
        "detection_rate": round(detection_rate, 4),
        "pseudo_multi_count": len(pseudo_multi),
        "false_alarms": false_alarms,
        "correct_single": correct_single,
        "details": details,
    }


def eval_context_dependent(data_path: Path) -> dict:
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]
    correct_with_context = 0
    correct_without_context = 0
    details = []

    for case in cases:
        utterance = case["utterance"]
        expected = case["intent"]
        ctx = case.get("context", {})

        # With context
        result_ctx = classify(utterance, state=ctx if ctx else None,
                              model_path=SAVED_DIR / "model.pt",
                              label_path=SAVED_DIR / "label_encoder.json",
                              scaler_path=SAVED_DIR / "scaler.npz")
        correct_ctx = result_ctx["intent"] == expected
        if correct_ctx:
            correct_with_context += 1

        # Without context (IDLE defaults)
        result_noctx = classify(utterance, state=None,
                                model_path=SAVED_DIR / "model.pt",
                                label_path=SAVED_DIR / "label_encoder.json",
                                scaler_path=SAVED_DIR / "scaler.npz")
        correct_noctx = result_noctx["intent"] == expected
        if correct_noctx:
            correct_without_context += 1

        details.append({
            "id": case.get("id", "?"),
            "utterance": utterance,
            "expected": expected,
            "order_stage": case.get("order_stage", ctx.get("order_stage", "?")),
            "predicted_with_context": result_ctx["intent"],
            "conf_with_context": round(result_ctx["confidence"], 4),
            "correct_with_context": correct_ctx,
            "predicted_without_context": result_noctx["intent"],
            "conf_without_context": round(result_noctx["confidence"], 4),
            "correct_without_context": correct_noctx,
        })

    acc_ctx = correct_with_context / len(cases) if cases else 0
    acc_noctx = correct_without_context / len(cases) if cases else 0

    # Count cases that NEED context (where without-context is wrong but with-context is right)
    context_helped = sum(1 for d in details if not d["correct_without_context"] and d["correct_with_context"])
    context_hurt = sum(1 for d in details if d["correct_without_context"] and not d["correct_with_context"])

    print("\n" + "=" * 65)
    print(f"  CONTEXT-DEPENDENT EVALUATION — {len(cases)} cases")
    print("=" * 65)
    print(f"\n  With context:    {correct_with_context}/{len(cases)} = {acc_ctx*100:.1f}%")
    print(f"  Without context: {correct_without_context}/{len(cases)} = {acc_noctx*100:.1f}%")
    print(f"  Context helped:  {context_helped} cases")
    print(f"  Context hurt:    {context_hurt} cases")

    helped = [d for d in details if not d["correct_without_context"] and d["correct_with_context"]]
    if helped:
        print(f"\n  Cases where context fixed the prediction:")
        for d in helped:
            print(f"    [{d['order_stage']}] '{d['utterance']}' → {d['predicted_with_context']} (conf={d['conf_with_context']:.3f})")

    hurt = [d for d in details if d["correct_without_context"] and not d["correct_with_context"]]
    if hurt:
        print(f"\n  Cases where context broke the prediction:")
        for d in hurt:
            print(f"    [{d['order_stage']}] '{d['utterance']}' → {d['predicted_with_context']} (exp: {d['expected']})")

    both_wrong = [d for d in details if not d["correct_without_context"] and not d["correct_with_context"]]
    if both_wrong:
        print(f"\n  Cases wrong in both modes:")
        for d in both_wrong:
            print(f"    [{d['order_stage']}] '{d['utterance']}' → ctx={d['predicted_with_context']}, noctx={d['predicted_without_context']} (exp: {d['expected']})")

    return {
        "benchmark": "context_dependent",
        "total": len(cases),
        "accuracy_with_context": round(acc_ctx, 4),
        "accuracy_without_context": round(acc_noctx, 4),
        "context_helped": context_helped,
        "context_hurt": context_hurt,
        "correct_with_context": correct_with_context,
        "correct_without_context": correct_without_context,
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate MLP intent classifier")
    parser.add_argument("--datasets", nargs="+", default=["single", "multi", "context"],
                        choices=["single", "multi", "context", "all"],
                        help="Which datasets to evaluate (default: all three)")
    parser.add_argument("--threshold", type=float, default=0.7,
                        help="Confidence threshold for multi-intent detection")
    args = parser.parse_args()

    global THRESHOLD
    THRESHOLD = args.threshold

    if "all" in args.datasets:
        args.datasets = ["single", "multi", "context"]

    results = {}
    for ds in args.datasets:
        path = DATASETS[ds]
        if not path.exists():
            print(f"Dataset not found: {path} — run build_eval_datasets.py first")
            continue

        logger.info("Evaluating %s ...", ds)
        if ds == "single":
            results["single_intent"] = eval_single_intent(path)
        elif ds == "multi":
            results["multi_intent_detection"] = eval_multi_intent_detection(path)
        elif ds == "context":
            results["context_dependent"] = eval_context_dependent(path)

    # Save report
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = RESULTS_DIR / f"mlp_router_eval_{ts}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
