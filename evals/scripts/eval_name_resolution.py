"""Validator Name Resolution Evaluator — tests each stage of the 5-stage
menu name resolution pipeline independently.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_name_resolution.py
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.agent_brain.utils.menu_utils import resolve_menu_name, find_nearest_menu_name

EVAL_DATA_PATH = PROJECT_ROOT / "evals" / "data" / "validator" / "name_resolution_eval.json"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = RESULTS_DIR / f"name_resolution_{TS}.json"


def main():
    if not EVAL_DATA_PATH.exists():
        print(f"ERROR: Dataset not found at {EVAL_DATA_PATH}")
        sys.exit(1)

    with open(EVAL_DATA_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    cases = dataset.get("cases", [])
    print(f"Loaded {len(cases)} test cases from {EVAL_DATA_PATH.name}")
    print()

    results = []
    per_level = defaultdict(lambda: {"correct": 0, "total": 0})
    total_correct = 0

    for case in cases:
        case_id = case["id"]
        name = case["input"]
        expected_kind = case["expected_kind"]
        expected_resolution = case.get("expected_resolution")
        expected_nearest = case.get("expected_nearest")
        level = case.get("level", "unknown")

        resolution = resolve_menu_name(name)
        nearest = find_nearest_menu_name(name)

        actual_kind = resolution["kind"]
        actual_resolution = resolution["resolved"]
        kind_ok = actual_kind == expected_kind
        resolution_ok = (
            actual_resolution == expected_resolution
            if expected_resolution
            else actual_resolution is None
        )

        if expected_kind == "none":
            nearest_ok = (
                nearest == expected_nearest
                if expected_nearest is not None
                else nearest is None
            )
        else:
            nearest_ok = True

        case_ok = kind_ok and resolution_ok and nearest_ok
        if case_ok:
            total_correct += 1

        per_level[level]["total"] += 1
        if case_ok:
            per_level[level]["correct"] += 1

        status = "PASS" if case_ok else "FAIL"
        flags = []
        if not kind_ok:
            flags.append(f"kind: expected={expected_kind} got={actual_kind}")
        if not resolution_ok:
            flags.append(f"resolution: expected={expected_resolution} got={actual_resolution}")
        if not nearest_ok:
            flags.append(f"nearest: expected={expected_nearest} got={nearest}")

        print(f"[{status}] {case_id} '{name}' | {', '.join(flags) if flags else 'OK'}")
        if not case_ok:
            print(f"       candidates={resolution['candidates']}")

        results.append({
            "id": case_id,
            "input": name,
            "expected_kind": expected_kind,
            "actual_kind": actual_kind,
            "expected_resolution": expected_resolution,
            "actual_resolution": actual_resolution,
            "expected_nearest": expected_nearest,
            "actual_nearest": nearest,
            "kind_ok": kind_ok,
            "resolution_ok": resolution_ok,
            "nearest_ok": nearest_ok,
            "passed": case_ok,
            "level": level,
        })

    accuracy = total_correct / len(cases) * 100 if cases else 0

    print(f"\n{'='*60}")
    print("NAME RESOLUTION EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total cases:        {len(cases)}")
    print(f"Correct:            {total_correct}")
    print(f"Failed:             {len(cases) - total_correct}")
    print(f"Overall accuracy:   {accuracy:.2f}%")
    print()
    print(f"{'Level':<30} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print("-" * 56)
    for level_name in ["exact_match", "diacritic_insensitive", "prefix_match", "substring_match", "token_jaccard", "token_jaccard_reject", "misspelled"]:
        if level_name in per_level:
            d = per_level[level_name]
            pct = d["correct"] / d["total"] * 100 if d["total"] else 0
            print(f"{level_name:<30} {d['correct']:>8} {d['total']:>8} {pct:>9.1f}%")

    report = {
        "timestamp": TS,
        "summary": {
            "accuracy": round(accuracy, 2),
            "total": len(cases),
            "correct": total_correct,
            "per_level": {
                k: {
                    "accuracy": round(v["correct"] / v["total"] * 100, 2) if v["total"] else 0,
                    "correct": v["correct"],
                    "total": v["total"],
                }
                for k, v in sorted(per_level.items())
            },
        },
        "results": results,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
