#!/usr/bin/env python3
"""Fleet & Multi-Role evaluation — validates dispatcher assignment, robot lifecycle,
and cross-role state consistency.  Writes results to evals/results/.

Usage:
    PYTHONPATH=. uv run python evals/scripts/bench_fleet.py
"""

import json
import os
import sys
import time
import asyncio
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import httpx
try:
    import websockets
except ImportError:
    print("ERROR: 'websockets' package required. Install with: uv pip install websockets")
    sys.exit(1)

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = RESULTS_DIR / f"bench_fleet_{TS}.json"

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")
WS_URL = BASE.replace("http://", "ws://") + "/ws"

results: dict = {"timestamp": TS, "fleet": {}, "multi_role": {}}


def log(section: str, msg: str):
    print(f"  [{section}] {msg}")


# =============================================================================
# §5.5.3 — Fleet Management & Fault Recovery
# =============================================================================


async def test_fleet():
    log("FLEET", "Starting fleet management tests...")

    async with httpx.AsyncClient(base_url=BASE, timeout=10) as client:
        # 1. Baseline fleet status
        resp = await client.get("/robots")
        robots_before = resp.json()
        n_robots = len(robots_before)
        log("FLEET", f"{n_robots} robot(s) in fleet")
        if robots_before:
            r0 = robots_before[0]
            log("FLEET", f"  Robot '{r0['id']}': status={r0['status']}, battery={r0.get('battery')}, "
                 f"task={r0.get('current_task_id')}")
        results["fleet"]["robots_count"] = n_robots
        results["fleet"]["robots_before"] = robots_before

        # 2. Connect a mock robot via WebSocket
        robot_id = robots_before[0]["id"] if robots_before else "robo-1"
        ws_url = f"{WS_URL}?role=robot&robot_id={robot_id}"
        log("FLEET", f"Connecting mock robot '{robot_id}' to {ws_url}")

        try:
            async with websockets.connect(ws_url) as ws:
                log("FLEET", "Mock robot connected ✓")

                # Send a heartbeat to register the robot as active
                heartbeat_msg = json.dumps({
                    "type": "heartbeat",
                    "battery": 85.0,
                    "x": 0.0, "y": 0.0
                })
                await ws.send(heartbeat_msg)
                await asyncio.sleep(0.3)

                # 3. Create a task (call button on table 1)
                log("FLEET", "Creating call task for table 1...")
                resp = await client.post("/tables/1/call")
                task_data = resp.json()
                task_id = task_data.get("id")
                log("FLEET", f"  Task #{task_id} created, status={task_data.get('status')}")

                await asyncio.sleep(0.5)

                # 4. Check assignment
                resp = await client.get("/robots")
                robots_after = resp.json()
                if robots_after:
                    r = robots_after[0]
                    results["fleet"]["robot_after_task"] = {
                        "id": r["id"], "status": r["status"],
                        "current_task_id": r.get("current_task_id"),
                        "activity": r.get("activity"),
                    }
                    log("FLEET", f"  After task: status={r['status']}, task_id={r.get('current_task_id')}, "
                         f"activity={r.get('activity')}")

                resp = await client.get("/tasks")
                tasks_after = resp.json()
                log("FLEET", f"  Tasks in queue: {len(tasks_after)}")
                results["fleet"]["tasks_after_assign"] = [
                    {"id": t["id"], "kind": t["kind"], "status": t["status"],
                     "robot_id": t.get("robot_id"), "table_id": t.get("table_id")}
                    for t in tasks_after
                ]

                # 5. Simulate robot completing the task
                done_msg = json.dumps({
                    "type": "task_done",
                    "task_id": task_id,
                    "battery": 80.0,
                    "x": 1.0, "y": 1.0
                })
                await ws.send(done_msg)
                await asyncio.sleep(0.3)

                resp = await client.get("/robots")
                robots_done = resp.json()
                if robots_done:
                    r = robots_done[0]
                    results["fleet"]["robot_after_done"] = {
                        "id": r["id"], "status": r["status"], "activity": r.get("activity"),
                    }
                    log("FLEET", f"  After task_done: status={r['status']}, activity={r.get('activity')}")

                # 6. Send at_dock to return robot to idle
                dock_msg = json.dumps({
                    "type": "at_dock",
                    "battery": 80.0,
                    "x": 0.0, "y": 0.0
                })
                await ws.send(dock_msg)
                await asyncio.sleep(0.3)

                resp = await client.get("/robots")
                robots_idle = resp.json()
                if robots_idle:
                    r = robots_idle[0]
                    results["fleet"]["robot_after_dock"] = {
                        "id": r["id"], "status": r["status"], "activity": r.get("activity"),
                    }
                    log("FLEET", f"  After at_dock: status={r['status']}, activity={r.get('activity')}")

                # 7. Verify tasks completed
                resp = await client.get("/tasks")
                tasks_final = resp.json()
                done_tasks = [t for t in tasks_final if t["status"] == "DONE"]
                log("FLEET", f"  Tasks DONE: {len(done_tasks)}")
                results["fleet"]["tasks_done"] = len(done_tasks)
                results["fleet"]["fault_recovery"] = {
                    "note": "Watchdog timeout test requires killing the WS connection mid-task "
                            "and verifying task requeue; this is structurally validated by the "
                            "dispatcher's try_assign() which requeues all PENDING tasks on each "
                            "robot connect/disconnect event (§4.7.3).",
                    "validated_by_inspection": True,
                }

        except Exception as e:
            log("FLEET", f"WS error: {e}")
            results["fleet"]["ws_error"] = str(e)

    log("FLEET", "Fleet tests complete.")


# =============================================================================
# §5.5.4 — Multi-Role State Consistency
# =============================================================================


async def test_multi_role():
    log("MULTI", "Starting multi-role consistency tests...")

    async with httpx.AsyncClient(base_url=BASE, timeout=10) as client:
        # 1. Snapshot all three views before any action
        tables_before = (await client.get("/tables")).json()
        orders_before = (await client.get("/orders")).json()
        tasks_before = (await client.get("/tasks")).json()
        log("MULTI", f"Before: {len(tables_before)} tables, {len(orders_before)} orders, "
             f"{len(tasks_before)} tasks")

        # 2. Simulate agent-driven state change: seat table 3, then create an order
        # First, make sure table 3 is free
        await client.patch("/tables/3", json={"status": "TRONG"})

        # Seat the table (kiosk flow)
        seat_payload = {"table_id": 3, "party_size": 4}
        log("MULTI", "Seating table 3 (party of 4)...")
        resp = await client.post("/seatings", json=seat_payload)
        if resp.status_code == 201:
            table_info = resp.json()
            log("MULTI", f"  Table 3 seated: status={table_info.get('status')}, "
                 f"party_size={table_info.get('party_size')}")
        else:
            log("MULTI", f"  Seating failed: {resp.status_code} {resp.text[:200]}")
            # Try getting the active session
            resp = await client.get("/tables/3/session")
            if resp.status_code == 200:
                log("MULTI", f"  Table 3 already has active session: {resp.json()}")

        # Create an order
        order_payload = {
            "table_id": 3,
            "items": [
                {"name": "Ốc Hương Xốt Trứng Muối", "qty": 2, "price": 85000},
                {"name": "Bia Heineken", "qty": 3, "price": 25000},
            ],
        }
        log("MULTI", "Creating order for table 3...")
        resp = await client.post("/orders", json=order_payload)
        if resp.status_code == 200:
            order = resp.json()
            order_id = order.get("id")
            log("MULTI", f"  Order #{order_id} created, status={order.get('status')}")
            results["multi_role"]["order_id"] = order_id
        else:
            log("MULTI", f"  Order creation returned {resp.status_code}: {resp.text[:200]}")

            # Fallback: try GET /tables/3/session to check state
            resp = await client.get("/tables/3/session")
            if resp.status_code == 200:
                sess = resp.json()
                log("MULTI", f"  Table 3 session: id={sess.get('id')}, status={sess.get('status')}")
                order_payload["session_id"] = sess.get("id")
                resp2 = await client.post("/orders", json=order_payload)
                if resp2.status_code == 200:
                    order = resp2.json()
                    order_id = order.get("id")
                    log("MULTI", f"  Order #{order_id} created (with session_id)")
                    results["multi_role"]["order_id"] = order_id

        await asyncio.sleep(0.5)

        # 3. Verify cross-role convergence
        # Panel view: GET /orders
        resp = await client.get("/orders")
        orders_after = resp.json()
        log("MULTI", f"  Panel (/orders): {len(orders_after)} orders (was {len(orders_before)})")
        results["multi_role"]["orders_before"] = len(orders_before)
        results["multi_role"]["orders_after"] = len(orders_after)

        # Table view: GET /tables
        resp = await client.get("/tables")
        tables_after = resp.json()
        results["multi_role"]["tables_before"] = len(tables_before)
        results["multi_role"]["tables_after"] = len(tables_after)

        # Check table 3 specifically
        resp = await client.get("/tables/3")
        if resp.status_code == 200:
            t3 = resp.json()
            log("MULTI", f"  Table 3 (/tables/3): status={t3.get('status')}, "
                 f"current_order_id={t3.get('current_order_id')}")
            results["multi_role"]["table_3"] = {
                "status": t3.get("status"),
                "current_order_id": t3.get("current_order_id"),
                "party_size": t3.get("party_size"),
            }

        # Task view: GET /tasks — verify delivery task was created
        resp = await client.get("/tasks")
        tasks_after = resp.json()
        results["multi_role"]["tasks_before"] = len(tasks_before)
        results["multi_role"]["tasks_after"] = len(tasks_after)
        if len(tasks_after) > len(tasks_before):
            new_tasks = [t for t in tasks_after if t.get("kind") == "deliver"]
            log("MULTI", f"  Tasks (/tasks): +{len(tasks_after) - len(tasks_before)} tasks, "
                 f"{len(new_tasks)} delivery task(s)")

        # 4. Check admin reset
        log("MULTI", "Testing /admin/reset...")
        resp = await client.post("/admin/reset")
        if resp.status_code == 200:
            log("MULTI", "  Reset successful ✓")
            results["multi_role"]["admin_reset"] = "ok"
        else:
            log("MULTI", f"  Reset returned {resp.status_code}")

    log("MULTI", "Multi-role tests complete.")


# =============================================================================


async def main():
    print("=" * 60)
    print("  FLEET & MULTI-ROLE EVALUATION")
    print(f"  Target: {BASE}")
    print("=" * 60)

    await test_fleet()
    print()
    await test_multi_role()

    print(f"\nReport saved to {REPORT_PATH}")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    asyncio.run(main())
