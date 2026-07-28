"""Pipeline Latency Instrumentor — measures agent turn latency per intent class,
reporting p50 and p95 percentiles.  The LLM stages have heavily right-skewed
distributions, so percentiles replace means throughout.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_latency.py
    PYTHONPATH=. uv run python evals/scripts/eval_latency.py --cold-start
    PYTHONPATH=. uv run python evals/scripts/eval_latency.py --n-runs 5
"""

import json
import os
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage
from src.agent_brain.agent.agent import get_agent_app

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = RESULTS_DIR / f"latency_{TS}.json"

TEST_UTTERANCES = [
    ("ORDER", "Cho mình 2 phần Ốc Hương Xốt Trứng Muối"),
    ("ORDER", "Lấy 1 Lẩu Thái với 3 chai bia Tiger"),
    ("ORDER_CONFIRM", "Đúng rồi, xác nhận đặt luôn"),
    ("SEARCH", "Quán có món gì ngon nhất?"),
    ("SEARCH", "Có món nào cay cay không em?"),
    ("SEARCH", "Món nào dành cho người ăn chay?"),
    ("PAYMENT", "Tính tiền đi em"),
    ("PAYMENT", "Cho anh check out nhé"),
    ("CHAT", "Chào em"),
    ("CHAT", "Nhà hàng mở cửa đến mấy giờ?"),
    ("MULTI", "Cho 2 Ốc Hương Xốt Trứng Muối rồi tính tiền luôn"),
    ("MULTI", "Có món gì ngon nhất? Cho anh 1 phần"),
]


def _percentile(values, pct):
    """Return the pct-th percentile of a sorted list."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct / 100.0
    f = int(k)
    c = k - f
    if f + 1 < len(s):
        return s[f] + c * (s[f + 1] - s[f])
    return s[f]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Latency Instrumentor")
    parser.add_argument("--cold-start", action="store_true", help="Measure cold-start penalty")
    parser.add_argument("--n-runs", type=int, default=5, help="Runs per utterance")
    args = parser.parse_args()

    print("PIPELINE LATENCY INSTRUMENTOR")
    print("=" * 60)

    # The checkpointer opens this DB in WAL mode, so the -wal and -shm sidecars belong to it.
    # Unlinking the .db alone leaves them behind to be paired with the next, empty database,
    # and every later process that opens it -- including any agent service already holding the
    # old file -- fails with "sqlite3.OperationalError: disk I/O error".
    checkpoint_db = PROJECT_ROOT / "storage" / "db" / "checkpoints.db"
    cleared = False
    for path in (checkpoint_db, *(checkpoint_db.with_name(checkpoint_db.name + suffix)
                                  for suffix in ("-wal", "-shm"))):
        if path.exists():
            path.unlink()
            cleared = True
    if cleared:
        print("Cleared checkpoint DB (including -wal / -shm)")

    print("Loading agent...")
    app = get_agent_app()

    cold_start_latency = None
    if args.cold_start:
        cs_config = {"configurable": {"thread_id": f"lat_cold_{uuid.uuid4().hex[:8]}"}}
        cs_state = {"messages": [HumanMessage(content="Xin chào")], "table_id": "T_lat_3"}
        print("  Measuring cold start...")
        start = time.perf_counter()
        for _ in app.stream(cs_state, config=cs_config, stream_mode="updates"):
            pass
        cold_start_latency = time.perf_counter() - start
        print(f"    Cold start: {cold_start_latency:.2f}s")
    else:
        print("Warming up agent...")
        warm_config = {"configurable": {"thread_id": "warmup_lat"}}
        for _ in app.stream(
            {"messages": [HumanMessage(content="warmup")], "table_id": "T_lat_3"},
            config=warm_config,
            stream_mode="updates",
        ):
            pass
        print("Agent warm.")

    print(f"\nMeasuring latencies ({args.n_runs} runs each)...")

    all_runs = []  # flat list for global p50/p95

    results = []
    per_intent_latencies = defaultdict(list)  # list of tuples (intent, all_run_vals)
    per_node_latencies = defaultdict(list)    # per-node latency samples across all runs

    for intent, utterance in TEST_UTTERANCES:
        thread_id = f"lat_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        run_latencies = []
        print(f"\n  [{intent}] '{utterance[:60]}'")

        for run_i in range(args.n_runs):
            state = {
                "messages": [HumanMessage(content=utterance)],
                "table_id": "T_lat_3",
            }

            start = time.perf_counter()
            last = start
            node_times: dict[str, float] = {}
            for update in app.stream(state, config=config, stream_mode="updates"):
                now = time.perf_counter()
                for node in update:
                    node_times[node] = node_times.get(node, 0.0) + (now - last)
                last = now
            total_latency = time.perf_counter() - start

            run_latencies.append(total_latency)
            all_runs.append((intent, total_latency))
            per_intent_latencies[intent].append(total_latency)
            for node, t in node_times.items():
                per_node_latencies[node].append(t)

            print(f"    Run {run_i + 1}: {total_latency:.2f}s")

        avg = sum(run_latencies) / len(run_latencies)
        sorted_runs = sorted(run_latencies)
        p50 = median(sorted_runs)
        p95 = _percentile(sorted_runs, 95)

        results.append({
            "intent": intent,
            "utterance": utterance,
            "n_runs": args.n_runs,
            "p50_s": round(p50, 3),
            "p95_s": round(p95, 3),
            "mean_s": round(avg, 3),
            "min_s": round(min(run_latencies), 3),
            "max_s": round(max(run_latencies), 3),
        })

    # Summary
    print(f"\n{'='*60}")
    print("LATENCY SUMMARY (p50 / p95)")
    print(f"{'='*60}")

    per_intent_summary = {}
    for intent in ["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT", "MULTI"]:
        vals = per_intent_latencies.get(intent, [])
        if vals:
            s = sorted(vals)
            p50_v = median(s)
            p95_v = _percentile(s, 95)
            per_intent_summary[intent] = {"p50": round(p50_v, 3), "p95": round(p95_v, 3),
                                           "n": len(vals)}
            print(f"  {intent:<20} p50={p50_v:.3f}s  p95={p95_v:.3f}s  n={len(vals)}")

    # Global
    all_sorted = sorted([v for _, v in all_runs])
    global_p50 = median(all_sorted) if all_sorted else 0.0
    global_p95 = _percentile(all_sorted, 95)
    print(f"\n  GLOBAL: p50={global_p50:.3f}s  p95={global_p95:.3f}s  n={len(all_sorted)}")

    if cold_start_latency:
        print(f"\n  Cold-start penalty: {cold_start_latency:.2f}s")

    # Per-node latency breakdown
    if per_node_latencies:
        print(f"\n{'='*60}")
        print("PER-NODE LATENCY BREAKDOWN (p50 / p95)")
        print(f"{'='*60}")
        node_summary = {}
        for node in sorted(per_node_latencies):
            vals = per_node_latencies[node]
            s = sorted(vals)
            p50_v = _percentile(s, 50)
            p95_v = _percentile(s, 95)
            pct = sum(vals) / sum(sum(per_node_latencies[n]) for n in per_node_latencies) * 100
            node_summary[node] = {
                "p50_s": round(p50_v, 3), "p95_s": round(p95_v, 3),
                "n": len(vals), "pct_of_total": round(pct, 1),
            }
            print(f"  {node:<30} p50={p50_v:.3f}s  p95={p95_v:.3f}s  "
                  f"{pct:.1f}%  n={len(vals)}")

    report = {
        "timestamp": TS,
        "cold_start_s": round(cold_start_latency, 3) if cold_start_latency else None,
        "n_runs_per_utterance": args.n_runs,
        "global": {"p50_s": round(global_p50, 3), "p95_s": round(global_p95, 3),
                    "n": len(all_sorted)},
        "per_intent_summary": per_intent_summary,
        "per_node_summary": node_summary if per_node_latencies else {},
        "detailed": results,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
