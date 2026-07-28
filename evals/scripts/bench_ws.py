"""WebSocket Event Latency Meter — measures how fast WebSocket events
propagate from the orchestrator server to clients by generating traffic
from a concurrent HTTP thread while the WS listeners collect events.

Requires: Orchestrator backend running on :8000
Usage:
    PYTHONPATH=. uv run python evals/scripts/bench_ws.py
    PYTHONPATH=. uv run python evals/scripts/bench_ws.py --samples 20
"""

import json
import os
import sys
import time
import asyncio
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median, quantiles

try:
    import websockets
    import httpx
except ImportError:
    print("ERROR: 'websockets' and 'httpx' packages required.")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = RESULTS_DIR / f"bench_ws_{TS}.json"

WS_URL = os.environ.get("WS_URL", "ws://localhost:8000/ws")
REST_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")

N_TRAFFIC_EVENTS = 20
TIMEOUT_S = 60


async def ws_listener(role: str, table_id: str | None, events_out: list):
    """Connect as a WS role and collect events with timestamps."""
    params = [f"role={role}"]
    if table_id:
        params.append(f"table_id={table_id}")
    url = f"{WS_URL}?{'&'.join(params)}"

    try:
        async with websockets.connect(url) as ws:
            t0 = time.monotonic()
            while (time.monotonic() - t0) < TIMEOUT_S:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    received_at = time.monotonic()
                    data = json.loads(raw)
                    events_out.append({
                        "role": role,
                        "type": data.get("type", "unknown"),
                        "received_at": received_at,
                        "payload": data,
                    })
                except asyncio.TimeoutError:
                    continue
    except Exception as e:
        print(f"  [WS {role}] connection closed: {e}")


async def traffic_generator(sent_events: list):
    """Generate REST calls that trigger WS events, recording send times."""
    async with httpx.AsyncClient(base_url=REST_URL, timeout=httpx.Timeout(10.0)) as cli:
        for i in range(N_TRAFFIC_EVENTS):
            table_id = (i % 4) + 1
            order_id = f"wsbench-{uuid.uuid4().hex[:6]}"
            sent_at = time.monotonic()
            try:
                resp = await cli.post("/orders", json={
                    "table_id": table_id,
                    "items": [{"name": "Lẩu Thái", "quantity": 1, "notes": order_id}],
                })
                resp.raise_for_status()
                sent_events.append({
                    "order_id": order_id,
                    "table_id": table_id,
                    "sent_at": sent_at,
                    "status": resp.status_code,
                })
                # Seat a table to generate table events
                seat_id = (i + 10) % 4 + 10
                try:
                    await cli.post("/seatings", json={"table_id": seat_id, "party_size": 2})
                except Exception:
                    pass
            except Exception as e:
                print(f"  [REST] order {order_id} failed: {e}")
            await asyncio.sleep(0.5)  # pace traffic


async def main_async(samples: int):
    global N_TRAFFIC_EVENTS
    N_TRAFFIC_EVENTS = samples

    print("WEBSOCKET EVENT LATENCY METER (with traffic generation)")
    print(f"Target: {WS_URL}")
    print(f"REST:   {REST_URL}")
    print(f"Traffic events to generate: {N_TRAFFIC_EVENTS}")
    print("=" * 60)

    # Check backend
    try:
        async with httpx.AsyncClient(base_url=REST_URL, timeout=httpx.Timeout(5.0)) as cli:
            resp = await cli.get("/menu")
            if resp.status_code < 400:
                print(f"Backend is up (GET /menu → {resp.status_code})")
            else:
                print(f"WARNING: Backend returned {resp.status_code}")
    except Exception:
        print(f"ERROR: Cannot connect to {REST_URL}")
        return

    ws_events: list = []
    sent_events: list = []

    print("\nStarting WS listeners + traffic generator in parallel...")
    t0 = time.monotonic()

    await asyncio.gather(
        ws_listener("panel", None, ws_events),
        ws_listener("customer", "T1", ws_events),
        traffic_generator(sent_events),
    )

    elapsed = time.monotonic() - t0
    print(f"\nDone in {elapsed:.1f}s.")
    print(f"  WS events collected: {len(ws_events)}")
    print(f"  REST calls sent:     {len(sent_events)}")

    # Match WS events to sent traffic by approximate timing
    latencies: list[float] = []
    for se in sent_events:
        nearby = [e for e in ws_events
                  if e["received_at"] >= se["sent_at"]
                  and e["received_at"] - se["sent_at"] < 5.0]
        if nearby:
            latency = nearby[0]["received_at"] - se["sent_at"]
            latencies.append(latency * 1000)

    if not latencies:
        print("\n  Could not match any WS events to traffic.")
        print("  Events may be arriving after traffic or not at all.")
        report = {
            "timestamp": TS, "target": WS_URL, "rest_target": REST_URL,
            "ws_events": len(ws_events), "rest_calls": len(sent_events),
            "latency_ms": None,
            "note": "No matched events — ensure orchestrator emits WS events on POST /orders.",
        }
    else:
        s = sorted(latencies)
        p50 = median(s)
        p95 = quantiles(s, n=20)[18] if len(s) >= 20 else s[-1] if s else 0

        print(f"\n{'='*60}")
        print("WEBSOCKET PROPAGATION LATENCY")
        print(f"{'='*60}")
        print(f"  Matched events: {len(latencies)}/{len(sent_events)}")
        print(f"  p50: {p50:.1f} ms")
        print(f"  p95: {p95:.1f} ms")
        print(f"  mean: {mean(s):.1f} ms")
        print(f"  min:  {min(s):.1f} ms")
        print(f"  max:  {max(s):.1f} ms")

        report = {
            "timestamp": TS, "target": WS_URL, "rest_target": REST_URL,
            "traffic_samples": N_TRAFFIC_EVENTS,
            "ws_events_total": len(ws_events),
            "matched_latency_samples": len(latencies),
            "p50_ms": round(p50, 1),
            "p95_ms": round(p95, 1),
            "mean_ms": round(mean(s), 1) if s else 0,
            "min_ms": round(min(s), 1) if s else 0,
            "max_ms": round(max(s), 1) if s else 0,
        }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to {REPORT_PATH}")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="WebSocket Event Latency Meter")
    ap.add_argument("--samples", type=int, default=20, help="Traffic events to generate")
    args = ap.parse_args()
    asyncio.run(main_async(args.samples))


if __name__ == "__main__":
    main()
