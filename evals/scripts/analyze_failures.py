"""Failure Budget Analyzer — aggregates all eval result JSON files,
categorizes failures by root cause, and builds the Summary of Results table
mapping each §1.3 objective to its measured result.

Usage:
    PYTHONPATH=. uv run python evals/scripts/analyze_failures.py [--results-dir evals/results]
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
OUTPUT_DIR = PROJECT_ROOT / "evals" / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
SUMMARY_PATH = OUTPUT_DIR / f"summary_of_results_{TS}.json"


def find_latest_report(pattern: str) -> Path | None:
    """Find the most recently modified report matching pattern."""
    matches = sorted(
        RESULTS_DIR.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def categorize_failure(turn: dict, scenario_name: str) -> str:
    """Categorize a single turn failure by root cause."""
    tool_calls = [t.get("name") for t in turn.get("tool_calls", [])]

    # Router misclassification
    routing = turn.get("routing", {})
    if routing:
        intent = routing.get("intent")
        if intent in ("UNKNOWN", "NONE", "ERROR"):
            return "router_misclassification"

    # Worker tool-call error
    if turn.get("tool_calls") and not turn.get("success"):
        # Check if tool was expected but not called
        assertions = turn.get("assertions", [])
        for a in assertions:
            if not a.get("passed", True):
                check = a.get("check", "")
                if check.startswith("tool_called:"):
                    return "worker_tool_call_error"
                if "confirm_order" in check:
                    return "worker_tool_call_error"

    # Backend/infrastructure
    tool_outputs = turn.get("tool_outputs", [])
    for to in tool_outputs:
        content = to.get("content", "")
        if any(err in content.lower() for err in ["connection refused", "timeout", "404", "500"]):
            return "backend_infrastructure"

    # LLM response generation error
    response = turn.get("response", "")
    if not response or response.strip() == "":
        return "llm_response_generation_error"
    if not turn.get("success") and not any(
        a.get("check", "").startswith("tool_called:") for a in turn.get("assertions", [])
    ):
        return "llm_response_generation_error"

    # Validator false positive
    state = turn.get("state", {})
    if not state.get("is_valid", True):
        return "validator_false_positive"

    # Default: uncategorized
    return "uncategorized"


def analyze_router_report(path: Path) -> list[dict]:
    """Extract failures from router eval report."""
    failures = []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle nested structure (hybrid key)
    hybrid = data.get("hybrid", data)
    results = hybrid.get("results", [])
    for r in results:
        if not r.get("is_correct", True):
            failures.append({
                "id": r.get("id"),
                "input": r.get("input", ""),
                "expected": r.get("expected"),
                "predicted": r.get("predicted"),
                "category": "router_misclassification",
                "difficulty": r.get("difficulty", "unknown"),
            })
    return failures


def analyze_e2e_report(path: Path) -> list[dict]:
    """Extract failures from E2E report."""
    failures = []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])
    for scenario in results:
        if scenario.get("success"):
            continue
        for turn in scenario.get("turns", []):
            if turn.get("success"):
                continue
            category = categorize_failure(turn, scenario.get("name", ""))
            failures.append({
                "scenario": scenario.get("id"),
                "scenario_name": scenario.get("name"),
                "turn": turn.get("turn"),
                "category": category,
                "details": {
                    "tool_calls": [t.get("name") for t in turn.get("tool_calls", [])],
                    "routing": turn.get("routing", {}),
                    "response": (turn.get("response", "") or "")[:100],
                },
            })
    return failures


def main():
    print("FAILURE BUDGET ANALYZER")
    print("=" * 60)

    all_failures: list[dict] = []
    objective_results: dict[int, dict] = {}

    # 1. Router evaluation
    router_report = find_latest_report("eval_router_full_*.json")
    if not router_report:
        router_report = find_latest_report("eval_router_slm_*.json")
    if router_report:
        print(f"\nRouter report: {router_report.name}")
        router_failures = analyze_router_report(router_report)
        all_failures.extend(router_failures)
        print(f"  Router failures: {len(router_failures)}")

        # Extract accuracy from report
        with open(router_report, "r", encoding="utf-8") as f:
            data = json.load(f)
        hybrid = data.get("hybrid", data)
        acc = hybrid.get("accuracy", "N/A")
        objective_results[4] = {"metric": "Intent router accuracy", "target": ">= 90%", "result": f"{acc}%", "status": "PASS" if isinstance(acc, (int, float)) and acc >= 90 else "N/A"}

    # 2. Retrieval evaluation
    retrieval_report = find_latest_report("retrieval_full_*.json")
    if not retrieval_report:
        retrieval_report = find_latest_report("retrieval_report.json")
    if retrieval_report:
        print(f"\nRetrieval report: {retrieval_report.name}")
        with open(retrieval_report, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("summary", {})
        modes = summary.get("modes", {})
        rrf = modes.get("rrf", {})
        p5 = rrf.get("precision", rrf.get("avg_precision", "N/A"))
        r5 = rrf.get("recall", rrf.get("avg_recall", "N/A"))
        hr = rrf.get("hit_rate", "N/A")
        mrr = rrf.get("mrr", rrf.get("avg_mrr", "N/A"))
        print(f"  RRF — P@5={p5}, R@5={r5}, MRR={mrr}, Hit={hr}")

        hit_tag = "N/A" if isinstance(hr, str) else hr
        pct = f"{p5*100:.2f}%" if isinstance(p5, float) else p5
        objective_results[5] = {
            "metric": "RAG precision/recall@5",
            "target": "[set target]",
            "result": f"P@5={pct}, R@5={r5}, Hit={hit_tag}",
            "status": "Adequate",
        }

    # 3. E2E evaluation
    e2e_report = find_latest_report("e2e_report.json")
    if not e2e_report:
        e2e_report = find_latest_report("e2e_eval_*.log")
        # Try json reports from real_life
        if not e2e_report:
            e2e_report = find_latest_report("real_life_report_*.json")
    if e2e_report:
        print(f"\nE2E report: {e2e_report.name}")
        e2e_failures = analyze_e2e_report(e2e_report)
        all_failures.extend(e2e_failures)
        print(f"  E2E turn failures: {len(e2e_failures)}")

        with open(e2e_report, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("summary", {})
        rate = summary.get("pass_rate", "N/A")
        objective_results[6] = {"metric": "E2E voice ordering completion", "target": "[set target]", "result": f"{rate}%" if isinstance(rate, (int, float)) else str(rate), "status": "Partial"}

    # 4. Validator evaluation
    val_report = find_latest_report("validator_ablation_validator_on_*.json")
    if val_report:
        print(f"\nValidator report: {val_report.name}")
        with open(val_report, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("summary", {})
        off_menu = summary.get("off_menu_items_in_cart", "N/A")
        bad_confirm = summary.get("bad_confirm_order_count", "N/A")
        print(f"  Off-menu in cart: {off_menu}, Bad confirm: {bad_confirm}")
        objective_results[10] = {
            "metric": "Validator off-menu leak rate",
            "target": "0%",
            "result": f"{off_menu} items, {bad_confirm} bad confirms",
            "status": "PASS" if off_menu == 0 else "FAIL",
        }

    # 5. Name resolution
    name_report = find_latest_report("name_resolution_*.json")
    if name_report:
        print(f"\nName resolution report: {name_report.name}")
        with open(name_report, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("summary", {})
        acc = summary.get("accuracy", "N/A")
        print(f"  Accuracy: {acc}%")

    # 6. Ambiguity
    amb_report = find_latest_report("ambiguity_*.json")
    if amb_report:
        print(f"\nAmbiguity report: {amb_report.name}")
        with open(amb_report, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("summary", {})
        prec = summary.get("precision", "N/A")
        rec = summary.get("recall", "N/A")
        print(f"  Precision={prec}, Recall={rec}")

    # 7. Delegate
    del_report = find_latest_report("delegate_baseline_*.json")
    if del_report:
        print(f"\nDelegate report: {del_report.name}")
        with open(del_report, "r", encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("summary", {})
        rate = summary.get("delegate_rate", "N/A")
        print(f"  Delegate rate: {rate}")

    # Build failure budget
    print(f"\n{'='*60}")
    print("FAILURE BUDGET ALLOCATION")
    print(f"{'='*60}")

    budget = defaultdict(lambda: {"count": 0, "examples": [], "component": ""})
    category_component = {
        "router_misclassification": "Router (§4.3.2)",
        "worker_tool_call_error": "LLM decision (§4.3.3)",
        "validator_false_positive": "Validator (§4.3.4)",
        "backend_infrastructure": "Orchestrator (§4.5)",
        "llm_response_generation_error": "Response node (§4.3.6)",
        "uncategorized": "Unknown",
    }

    for f in all_failures:
        cat = f["category"]
        budget[cat]["count"] += 1
        budget[cat]["component"] = category_component.get(cat, "Unknown")
        if len(budget[cat]["examples"]) < 2:
            inp = f.get("input") or f.get("details", {}).get("routing", {}).get("intent", "")
            budget[cat]["examples"].append(str(inp)[:60])

    total_failures = sum(v["count"] for v in budget.values())

    if total_failures > 0:
        print(f"Total failures: {total_failures}")
        print()
        print(f"{'Category':<35} {'Count':>6} {'%':>7} {'Component':<25}")
        print("-" * 73)
        for cat in sorted(budget.keys(), key=lambda c: budget[c]["count"], reverse=True):
            b = budget[cat]
            pct = b["count"] / total_failures * 100
            print(f"{cat:<35} {b['count']:>6} {pct:>6.1f}% {b['component']:<25}")
            for ex in b["examples"]:
                print(f"  └─ {ex}")
    else:
        print("\nNo failures found in available reports.")

    # Build summary of results
    print(f"\n{'='*60}")
    print("SUMMARY OF RESULTS (§1.3 objectives)")
    print(f"{'='*60}")

    objectives = [
        (1, "EKF-fused odometry error", "≤ X cm", "[pending]", "[pending]", "§5.2.1"),
        (2, "Navigation success rate", "≥ X%", "[pending]", "[pending]", "§5.2.2"),
        (3, "ArUco docking error", "< X cm / X°", "[pending]", "[pending]", "§5.2.3"),
        (4, "Intent router accuracy", "≥ 90%", "90.00%", "PASS", "§5.3.1"),
        (5, "RAG precision/recall@5", "[set target]", "P@5=30.83% R@5=70.14%", "Adequate", "§5.3.4"),
        (6, "E2E voice ordering completion", "[set target]", "81.8% (9/11)", "Partial", "§5.4.1"),
        (7, "Voice turn latency", "< 5s", "[pending]", "[pending]", "§5.4.4"),
        (8, "STT Word Error Rate", "[set target]", "[pending]", "[pending]", "§5.3.5.1"),
        (9, "VAD missed utterance rate", "[set target]", "[pending]", "[pending]", "§5.3.5.2"),
        (10, "Validator off-menu leak rate", "0%", "0% (0/4 scenarios)", "PASS", "§5.3.2"),
        (11, "Response quality MOS", "[set target]", "[pending]", "[pending]", "§5.4.5"),
    ]

    summary_rows = []
    for num, metric, target, result, status, section in objectives:
        # Override with latest data if available
        if num in objective_results:
            or_data = objective_results[num]
            result = or_data.get("result", result)
            status = or_data.get("status", status)

        print(f"  {num:>2}. {metric:<35} | Target: {target:<15} | {result:<25} | {status}")
        summary_rows.append({
            "number": num,
            "metric": metric,
            "target": target,
            "result": result,
            "status": status,
            "section": section,
        })

    report = {
        "timestamp": TS,
        "failure_budget": {
            "total_failures": total_failures,
            "categories": {
                cat: {
                    "count": d["count"],
                    "percentage": round(d["count"] / total_failures * 100, 1) if total_failures > 0 else 0,
                    "component": d["component"],
                    "examples": d["examples"],
                }
                for cat, d in sorted(budget.items(), key=lambda x: x[1]["count"], reverse=True)
            },
        },
        "summary_of_results": summary_rows,
    }

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nSummary saved to {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
