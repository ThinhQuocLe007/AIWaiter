"""Ambiguity Detection Evaluator — tests the validator's ability to flag
generic dish names that match multiple menu items as ambiguous (without
auto-resolving them).

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_ambiguity.py
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.agent_brain.utils.menu_utils import resolve_menu_name

EVAL_DATA_PATH = PROJECT_ROOT / "evals" / "data" / "validator" / "ambiguity_eval.json"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = RESULTS_DIR / f"ambiguity_{TS}.json"


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
    true_pos = 0   # correctly flagged as ambiguous
    false_pos = 0  # unambiguous but flagged as ambiguous
    true_neg = 0   # unambiguous, correctly NOT flagged
    false_neg = 0  # ambiguous but NOT flagged

    for case in cases:
        case_id = case["id"]
        name = case["input"]
        should_be_ambiguous = case["should_be_ambiguous"]
        expected_min = case.get("expected_min_candidates", 2)

        resolution = resolve_menu_name(name)
        kind = resolution["kind"]
        candidates = resolution["candidates"]
        is_ambiguous = kind == "ambiguous"

        if should_be_ambiguous and is_ambiguous:
            true_pos += 1
            status = "PASS"
        elif should_be_ambiguous and not is_ambiguous:
            false_neg += 1
            status = "FAIL (missed)"
        elif not should_be_ambiguous and is_ambiguous:
            false_pos += 1
            status = "FAIL (false positive)"
        else:
            true_neg += 1
            status = "PASS"

        note = ""
        if is_ambiguous:
            note = f"{len(candidates)} candidates: {candidates[:4]}{'...' if len(candidates) > 4 else ''}"
            if expected_min and len(candidates) < expected_min:
                note += f" [expected >= {expected_min}]"
        elif kind == "single" and should_be_ambiguous:
            note = f"resolved to '{resolution['resolved']}' (should be ambiguous)"
        elif kind == "none" and should_be_ambiguous:
            note = "no match found (should be ambiguous)"

        print(f"[{status}] {case_id}: '{name}' | kind={kind} | {note}")

        results.append({
            "id": case_id,
            "input": name,
            "should_be_ambiguous": should_be_ambiguous,
            "actual_kind": kind,
            "candidates": candidates,
            "candidate_count": len(candidates),
            "passed": (should_be_ambiguous == is_ambiguous),
        })

    total = len(cases)
    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) > 0 else 0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) > 0 else 0
    accuracy = (true_pos + true_neg) / total if total else 0

    print(f"\n{'='*60}")
    print("AMBIGUITY DETECTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total cases:              {total}")
    print(f"True positive  (flagged): {true_pos}")
    print(f"False positive (wrongly): {false_pos}")
    print(f"True negative  (correct): {true_neg}")
    print(f"False negative (missed):  {false_neg}")
    print()
    print(f"Precision: {precision:.4f} ({true_pos}/{true_pos + false_pos})")
    print(f"Recall:    {recall:.4f} ({true_pos}/{true_pos + false_neg})")
    print(f"Accuracy:  {accuracy:.4f} ({true_pos + true_neg}/{total})")

    report = {
        "timestamp": TS,
        "summary": {
            "total": total,
            "true_positive": true_pos,
            "false_positive": false_pos,
            "true_negative": true_neg,
            "false_negative": false_neg,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "accuracy": round(accuracy, 4),
        },
        "results": results,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
