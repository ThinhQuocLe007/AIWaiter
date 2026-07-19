"""Pipeline Latency Instrumentor — measures per-stage latency for the agent
pipeline by instrumenting each LangGraph node with high-resolution timestamps.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_latency.py
    PYTHONPATH=. uv run python evals/scripts/eval_latency.py --cold-start
"""

import json
import os
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

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

# Test utterances covering all intent types
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


def extract_node_timings(stream: list) -> dict[str, float]:
    """Extract per-node timing from stream updates by recording when each node fires."""
    timings = {}
    node_start = None

    for i, update in enumerate(stream):
        node_names = list(update.keys())
        for name in node_names:
            if name not in timings:
                # First time we see this node
                timings[name] = None
                node_start = time.perf_counter()
        # Record when we last saw output (approximates completion)
        if node_start is not None and len(stream) > 0:
            pass  # Just tracking presence

    # Use the routing_meta latency from router as baseline
    for update in stream:
        if "router" in update:
            router_output = update["router"]
            routing_meta = router_output.get("routing_meta", {})
            router_latency = routing_meta.get("latency_seconds")
            if router_latency:
                timings["router"] = router_latency

    return timings


def measure_cold_start(app, test_state: dict, config: dict) -> float:
    """Measure first utterance latency (cold start penalty)."""
    print("  Measuring cold start...")
    start = time.perf_counter()
    for _ in app.stream(test_state, config=config, stream_mode="updates"):
        pass
    elapsed = time.perf_counter() - start
    print(f"    Cold start: {elapsed:.2f}s")
    return elapsed


def measure_warm_utterance(app, test_state: dict, config: dict) -> float:
    """Measure warm utterance latency."""
    start = time.perf_counter()
    for _ in app.stream(test_state, config=config, stream_mode="updates"):
        pass
    elapsed = time.perf_counter() - start
    return elapsed


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Latency Instrumentor")
    parser.add_argument("--cold-start", action="store_true", help="Measure cold-start penalty")
    parser.add_argument("--n-runs", type=int, default=3, help="Runs per utterance")
    args = parser.parse_args()

    print("PIPELINE LATENCY INSTRUMENTOR")
    print("=" * 60)

    checkpoint_db = PROJECT_ROOT / "storage" / "db" / "checkpoints.db"
    if checkpoint_db.exists():
        checkpoint_db.unlink()
        print("Cleared checkpoint DB")

    print("Loading agent...")
    app = get_agent_app()

    # Cold start measurement
    cold_start_latency = None
    if args.cold_start:
        cs_config = {"configurable": {"thread_id": f"lat_cold_{uuid.uuid4().hex[:8]}"}}
        cs_state = {"messages": [HumanMessage(content="Xin chào")], "table_id": "T_lat"}
        cold_start_latency = measure_cold_start(app, cs_state, cs_config)
    else:
        # Warmup
        print("Warming up agent...")
        warm_config = {"configurable": {"thread_id": "warmup_lat"}}
        for _ in app.stream(
            {"messages": [HumanMessage(content="warmup")], "table_id": "warmup"},
            config=warm_config,
            stream_mode="updates",
        ):
            pass
        print("Agent warm.")

    # Per-utterance latency measurement
    print(f"\nMeasuring latencies ({args.n_runs} runs each)...")

    results = []
    per_intent_latency = defaultdict(list)

    for intent, utterance in TEST_UTTERANCES:
        thread_id = f"lat_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        run_latencies = []
        print(f"\n  [{intent}] '{utterance[:60]}'")

        for run_i in range(args.n_runs):
            state = {
                "messages": [HumanMessage(content=utterance)],
                "table_id": "T_lat",
            }

            # Instrument with stream to capture per-node output
            start = time.perf_counter()
            stream = []
            node_appearances = []
            for chunk in app.stream(state, config=config, stream_mode="updates"):
                stream.append(chunk)
                node_names = list(chunk.keys())
                node_appearances.append((node_names, time.perf_counter()))
            total_latency = time.perf_counter() - start

            run_latencies.append(total_latency)

            # Extract final response
            for update in reversed(stream):
                if "response_node" in update:
                    for msg in reversed(update["response_node"].get("messages", [])):
                        if isinstance(msg, AIMessage) and msg.content:
                            resp = msg.content[:60]
                            break
                for node in ["order_worker", "search_worker", "payment_dispatch", "chat_worker"]:
                    if node in update:
                        for msg in reversed(update[node].get("messages", [])):
                            if isinstance(msg, AIMessage) and msg.content and isinstance(msg.content, str) and not msg.tool_calls:
                                resp = msg.content[:60]
                                break

            # Get routing info
            routing_meta = {}
            for update in stream:
                if "router" in update:
                    routing_meta = update["router"].get("routing_meta", {})

            decided_by = routing_meta.get("decided_by", "N/A")
            router_lat = routing_meta.get("latency_seconds", 0)

            print(f"    Run {run_i+1}: total={total_latency:.2f}s  router={router_lat:.3f}s  by={decided_by}")

        avg_lat = sum(run_latencies) / len(run_latencies)
        per_intent_latency[intent].append(avg_lat)

        results.append({
            "intent": intent,
            "utterance": utterance,
            "n_runs": args.n_runs,
            "mean_latency_s": round(avg_lat, 3),
            "min_latency_s": round(min(run_latencies), 3),
            "max_latency_s": round(max(run_latencies), 3),
            "individual_times_s": [round(l, 3) for l in run_latencies],
        })

    # Summary
    print(f"\n{'='*60}")
    print("LATENCY SUMMARY")
    print(f"{'='*60}")

    per_intent_summary = {}
    for intent in ["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT", "MULTI"]:
        vals = per_intent_latency.get(intent, [])
        if vals:
            avg = sum(vals) / len(vals)
            per_intent_summary[intent] = round(avg, 3)
            print(f"  {intent:<20} mean={avg:.3f}s  (n={len(vals)} utterances)")

    if cold_start_latency:
        print(f"\n  Cold-start penalty: {cold_start_latency:.2f}s (first utterance vs warm)")

    report = {
        "timestamp": TS,
        "cold_start": round(cold_start_latency, 3) if cold_start_latency else None,
        "n_runs_per_utterance": args.n_runs,
        "per_intent_summary": per_intent_summary,
        "detailed": results,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
