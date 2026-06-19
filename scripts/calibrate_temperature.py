#!/usr/bin/env python3
"""
calibrate_temperature.py — 1D sweep over temperature T on eval data.

Finds optimal (T, prob_threshold, gap_threshold) that maximizes
fast-track rate while maintaining 0 misclassifications on the eval set.

Usage:
    python scripts/calibrate_temperature.py

Output:
    - Prints optimal constants to stdout
    - Saves detailed JSON report to evals/results/calibration_*.json
"""
import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# ── Paths (same convention as build_centroids.py) ──
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PACKAGE_RESOURCES = (
    PROJECT_ROOT
    / "ai_waiter_core/ai_waiter_core/agent/resources"
)

EVAL_PATH = PROJECT_ROOT / "evals" / "data" / "router" / "router_eval.json"
CENTROIDS_PATH = PACKAGE_RESOURCES / "centroids" / "centroids.npz"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "AITeamVN/Vietnamese_Embedding"

# ── Sweep ranges ──
T_VALUES = [0.01, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30, 0.40, 0.50]
PROB_CANDIDATES = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
GAP_CANDIDATES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]

# ── Intent mapping: eval labels → acceptable semantic router intents ──
# Eval uses ORDER, SEARCH, PAYMENT, CHAT.
# Our centroids have ORDER, ORDER_CONFIRM, SEARCH, PAYMENT, CHAT.
# ORDER and ORDER_CONFIRM both route to order_worker → both acceptable for ORDER.
ACCEPTABLE_MAP = {
    "ORDER": {"ORDER", "ORDER_CONFIRM"},
    "SEARCH": {"SEARCH"},
    "PAYMENT": {"PAYMENT"},
    "CHAT": {"CHAT"},
}


def softmax_routing(
    all_scores: dict[str, float],
    T: float,
    prob_threshold: float,
    gap_threshold: float,
) -> tuple[bool, str | None, float, float]:
    """
    Same logic as in semantic_router_node.softmax_routing().
    Returns (fast_track, intent, P1, gap).
    """
    scores = np.array(list(all_scores.values()))
    labels = list(all_scores.keys())

    exp_scores = np.exp(scores / T)
    probs = exp_scores / exp_scores.sum()

    sorted_indices = np.argsort(probs)[::-1]
    P1, P2 = float(probs[sorted_indices[0]]), float(probs[sorted_indices[1]])
    best_label = labels[sorted_indices[0]]
    gap = P1 - P2

    if P1 >= prob_threshold and gap >= gap_threshold:
        return True, best_label, P1, gap
    return False, best_label, P1, gap


def is_correct(predicted_intent: str | None, expected) -> bool:
    """Check if the predicted intent matches the expected label.

    Single-intent cases: predicted must match expected (ORDER_CONFIRM acceptable for ORDER).
    Multi-intent cases (list): never correct — semantic router can only output one intent,
    so these should always fall back to SLM. A fast-track here is a wrong decision.
    """
    if predicted_intent is None:
        return False
    if isinstance(expected, list):
        return False
    acceptable = ACCEPTABLE_MAP.get(expected, {expected})
    return predicted_intent in acceptable


def load_centroids(path: Path) -> dict[str, np.ndarray]:
    """Load centroids from .npz file."""
    data = np.load(str(path))
    return {k: data[k] for k in data.files}


def load_eval_cases(path: Path) -> list[dict]:
    """Load eval cases from router_eval.json."""
    with open(path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    return dataset.get("cases", [])


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 65)
    print("  Temperature Calibration — Softmax + Gap Routing")
    print("=" * 65)

    # 1. Load eval cases
    print(f"\n[1/5] Loading eval cases from {EVAL_PATH}...")
    if not EVAL_PATH.exists():
        print(f"ERROR: Eval dataset not found at {EVAL_PATH}", file=sys.stderr)
        sys.exit(1)
    cases = load_eval_cases(EVAL_PATH)
    print(f"       Loaded {len(cases)} cases.")

    # 2. Load centroids
    print(f"\n[2/5] Loading centroids from {CENTROIDS_PATH}...")
    if not CENTROIDS_PATH.exists():
        print(f"ERROR: Centroids not found at {CENTROIDS_PATH}", file=sys.stderr)
        sys.exit(1)
    centroids = load_centroids(CENTROIDS_PATH)
    intent_names = list(centroids.keys())
    centroid_vectors = np.array([centroids[k] for k in intent_names])
    print(f"       Loaded {len(centroids)} centroids: {intent_names}")

    # 3. Load embedding model
    print(f"\n[3/5] Loading embedding model: {DEFAULT_MODEL}...")
    model = SentenceTransformer(DEFAULT_MODEL)
    print("       Model loaded.")

    # 4. Encode all eval queries and compute centroid similarities
    print(f"\n[4/5] Encoding {len(cases)} eval queries and computing similarities...")
    cached = []
    for case in tqdm(cases, desc="  Encoding"):
        q_vec = model.encode([case["input"]])[0]
        sims = {}
        for i, name in enumerate(intent_names):
            sim = float(cosine_similarity([q_vec], [centroid_vectors[i]])[0][0])
            sims[name] = sim
        cached.append({
            "id": case["id"],
            "input": case["input"],
            "expected": case["expected_route"],
            "difficulty": case.get("difficulty", "unknown"),
            "sims": sims,
        })

    # 5. Sweep parameters
    print(f"\n[5/5] Sweeping parameters...")
    print(f"       T values: {len(T_VALUES)}")
    print(f"       Prob thresholds: {len(PROB_CANDIDATES)}")
    print(f"       Gap thresholds: {len(GAP_CANDIDATES)}")
    print(f"       Total combos: {len(T_VALUES) * len(PROB_CANDIDATES) * len(GAP_CANDIDATES)}")

    best = {"T": 0.0, "prob": 0.0, "gap": 0.0, "fast_tracked": 0, "wrong": 0}
    results_by_combo = []

    for T in T_VALUES:
        for prob_th in PROB_CANDIDATES:
            for gap_th in GAP_CANDIDATES:
                fast_tracked = 0
                correct = 0
                wrong = 0
                case_details = []

                for c in cached:
                    ft, intent, p1, gap = softmax_routing(
                        c["sims"], T, prob_th, gap_th
                    )
                    if ft:
                        fast_tracked += 1
                        if is_correct(intent, c["expected"]):
                            correct += 1
                        else:
                            wrong += 1
                    case_details.append({
                        "id": c["id"],
                        "fast_track": ft,
                        "predicted_intent": intent,
                        "expected": c["expected"],
                        "P1": round(p1, 4),
                        "gap": round(gap, 4),
                    })

                combo = {
                    "T": T,
                    "prob_threshold": prob_th,
                    "gap_threshold": gap_th,
                    "fast_tracked": fast_tracked,
                    "correct": correct,
                    "wrong": wrong,
                    "accuracy": round(correct / fast_tracked, 4) if fast_tracked > 0 else 0,
                }
                results_by_combo.append(combo)

                if wrong == 0 and fast_tracked > best["fast_tracked"]:
                    best = {
                        "T": T,
                        "prob": prob_th,
                        "gap": gap_th,
                        "fast_tracked": fast_tracked,
                        "wrong": wrong,
                    }

    # 6. Report results
    print("\n" + "=" * 65)
    print(f"  CALIBRATION RESULTS")
    print("=" * 65)

    if best["fast_tracked"] == 0:
        print("\n  ⚠ No safe combo found (all combos produced misclassifications).")
        print("  Try widening PROB_CANDIDATES or GAP_CANDIDATES.")
    else:
        print(f"\n  Optimal Parameters (0 misclassifications):")
        print(f"  ───────────────────────────────────────────")
        print(f"  TEMPERATURE       = {best['T']}")
        print(f"  PROB_THRESHOLD    = {best['prob']}")
        print(f"  GAP_THRESHOLD     = {best['gap']}")
        print(f"  ───────────────────────────────────────────")
        print(f"  Fast-tracked: {best['fast_tracked']}/{len(cases)} ({best['fast_tracked']/len(cases)*100:.1f}%)")
        print(f"  Misclassifications: {best['wrong']}")

    # 7. Per-intent breakdown for best combo
    if best["fast_tracked"] > 0:
        print(f"\n  Per-intent breakdown (best combo):")
        print(f"  ─────────────────────────────────")
        intent_stats: dict[str, dict] = {}
        for c in cached:
            label = c["expected"] if isinstance(c["expected"], str) else "multi"
            if label not in intent_stats:
                intent_stats[label] = {"total": 0, "fast_tracked": 0, "correct": 0}
            intent_stats[label]["total"] += 1

            ft, intent, p1, gap = softmax_routing(
                c["sims"], best["T"], best["prob"], best["gap"]
            )
            if ft:
                intent_stats[label]["fast_tracked"] += 1
                if is_correct(intent, c["expected"]):
                    intent_stats[label]["correct"] += 1

        for label, stats in sorted(intent_stats.items()):
            rate = stats["fast_tracked"] / stats["total"] * 100
            print(f"    {label:10s}: {stats['fast_tracked']:2d}/{stats['total']:2d} ({rate:5.1f}%)")

    # 8. Print top-5 safe combos for comparison
    safe_combos = [c for c in results_by_combo if c["wrong"] == 0]
    safe_combos.sort(key=lambda x: x["fast_tracked"], reverse=True)

    print(f"\n  Top-5 Safe Combos (by fast-track rate):")
    print(f"  ──────────────────────────────────────")
    print(f"  {'T':>5}  {'Prob':>5}  {'Gap':>5}  {'FastTr':>7}  {'Corr':>5}  {'Rate':>6}")
    print(f"  {'─────':>5}  {'─────':>5}  {'─────':>5}  {'──────':>7}  {'────':>5}  {'──────':>6}")
    for combo in safe_combos[:5]:
        rate = combo["fast_tracked"] / len(cases) * 100
        print(f"  {combo['T']:5.2f}  {combo['prob_threshold']:5.2f}  {combo['gap_threshold']:5.2f}  "
              f"{combo['fast_tracked']:5d}/{len(cases):<2d}  {combo['correct']:3d}  {rate:5.1f}%")

    # 9. Save full report
    report = {
        "timestamp": timestamp,
        "total_cases": len(cases),
        "optimal": best,
        "sweep_params": {
            "T_values": T_VALUES,
            "prob_candidates": PROB_CANDIDATES,
            "gap_candidates": GAP_CANDIDATES,
        },
        "safe_combos": safe_combos[:10],
        "all_combos": results_by_combo,
    }
    report_path = RESULTS_DIR / f"calibration_{timestamp}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Full report saved to: {report_path}")

    # 10. Print paste-ready constants
    if best["fast_tracked"] > 0:
        print("\n" + "=" * 65)
        print("  Paste these constants into semantic_router_node.py:")
        print("=" * 65)
        print(f"""
SOFTMAX_TEMPERATURE = {best['T']}
PROB_THRESHOLD      = {best['prob']}
GAP_THRESHOLD       = {best['gap']}
""")

    print("Done.")


if __name__ == "__main__":
    main()
