"""WebSocket Event Latency Meter — measures how fast WebSocket events
propagate from the orchestrator server to clients.

Requires: Orchestrator backend running on :8000
Usage:
    PYTHONPATH=. uv run python evals/scripts/bench_ws.py
"""

import json
import os
import sys
import time
import asyncio
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median, quantiles

try:
    import websockets
except ImportError:
    print("ERROR: 'websockets' package required. Install with: uv pip install websockets")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = RESULTS_DIR / f"bench_ws_{TS}.json"

WS_URL = os.environ.get("WS_URL", "ws://localhost:8000/ws")

N_SAMPLES = 50
TIMEOUT_S = 30


async def collect_events(role: str, table_id: str | None = None, robot_id: str | None = None) -> list[dict]:
    """Connect as a WebSocket role and collect event latencies."""
    params = [f"role={role}"]
    if table_id:
        params.append(f"table_id={table_id}")
    if robot_id:
        params.append(f"robot_id={robot_id}")

    url = f"{WS_URL}?{'&'.join(params)}"
    events = []

    try:
        async with websockets.connect(url) as ws:
            start_time = time.monotonic()
            while len(events) < N_SAMPLES and (time.monotonic() - start_time) < TIMEOUT_S:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    received_at = time.monotonic()
                    data = json.loads(raw)
                    event_type = data.get("type", "unknown")
                    sent_at = data.get("timestamp")

                    events.append({
                        "type": event_type,
                        "received_at": received_at,
                        "sent_at_raw": sent_at,
                    })
                except asyncio.TimeoutError:
                    break
    except (websockets.exceptions.ConnectionClosed, OSError, asyncio.TimeoutError) as e:
        print(f"    WS connection closed: {e}")

    return events


async def main_async():
    print("WEBSOCKET EVENT LATENCY METER")
    print(f"Target: {WS_URL}")
    print(f"Target events per role: {N_SAMPLES}")
    print("=" * 60)

    roles = [
        ("panel", None, None),
        ("customer", "T1", None),
    ]

    all_latencies: dict[str, list] = defaultdict(list)

    for role, table_id, robot_id in roles:
        print(f"\n  Connecting as role={role}...")
        events = await collect_events(role, table_id, robot_id)
        print(f"    Collected {len(events)} events")

        for ev in events:
            all_latencies[ev["type"]].append({
                "role": role,
                "received_at": ev["received_at"],
            })

    # If we collected nothing useful, report it
    total_events = sum(len(v) for v in all_latencies.values())
    if total_events == 0:
        print("\n  WARNING: No events collected. The backend may not be emitting events.")
        print("  Try triggering orders/table updates from another terminal while this runs.")

    # Per-event-type statistics
    print(f"\n{'='*60}")
    print("WEBSOCKET EVENT LATENCY SUMMARY")
    print(f"{'='*60}")
    print(f"  Note: Timestamps not available in event payloads. Showing event count per type.")
    print(f"  To measure actual latency, add 'sent_at' field to WebSocket event payloads\n")

    report_events = {}
    for etype, items in sorted(all_latencies.items()):
        count = len(items)
        roles_involved = set(i["role"] for i in items)
        print(f"  {etype:<30} count={count:>4}  roles={roles_involved}")
        report_events[etype] = {
            "count": count,
            "roles": list(roles_involved),
        }

    if total_events > 0:
        print(f"\n  Total events collected: {total_events}")
        print(f"  Event types seen: {len(all_latencies)}")

    report = {
        "timestamp": TS,
        "target": WS_URL,
        "total_events_collected": total_events,
        "event_types_seen": len(all_latencies),
        "events": report_events,
        "note": "For server-side timestamping, inject 'sent_at' into each WS event payload (time.time() on emit).",
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to {REPORT_PATH}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
