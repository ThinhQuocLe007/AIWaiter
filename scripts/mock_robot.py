"""Mock AGV — a stand-in for a real warehouse robot, to test the dispatcher end-to-end.

It speaks the same WS contract a real ``ws_client`` (Mốc A) will: connects as
``/ws?role=robot&robot_id=<id>``, sends periodic heartbeats, and when it receives
a ``task.assign`` it walks the task lifecycle (accept → drive → arrive → done →
drive back to dock) instead of using Nav2.

The ``task.assign`` payload now carries the resolved goal ``pose`` (x, y, yaw)
plus a ``target_token`` (the brain's section label). The mock drives to that
pose and back, streaming heartbeats so the panel minimap animates.

Run (backend must be up on :8000):
    uv run python scripts/mock_robot.py --id robo-1

Kill it mid-task (Ctrl-C) to see the dispatcher requeue its task to another robot.
"""

import argparse
import asyncio
import contextlib
import json
import math
import os
from pathlib import Path

import websockets

HEARTBEAT_EVERY = 3.0  # seconds, while idle
DRIVE_SPEED = 0.7  # m/s fake travel speed
MOVE_STEP = 0.2  # seconds between pose updates while driving → smooth dot on the panel minimap

# Dock + section waypoints, in the warehouse map frame — read from the SAME layout file the
# backend and the real AGV bridge use (services/floorplan.py), so the fake robot always drives to
# the same spots the panel draws. Override with ORCH_FLOORPLAN_PATH=... .
_REPO_ROOT = Path(__file__).resolve().parents[1]
_FLOORPLAN = Path(
    os.environ.get("ORCH_FLOORPLAN_PATH", "assets/data/warehouse_layout.json")
)
if not _FLOORPLAN.is_absolute():
    _FLOORPLAN = _REPO_ROOT / _FLOORPLAN

_PLAN = json.loads(_FLOORPLAN.read_text(encoding="utf-8"))
DOCK_POS = (
    float(_PLAN["dock"]["approach"]["x"]),
    float(_PLAN["dock"]["approach"]["y"]),
)


async def heartbeat_loop(ws, state: dict, hang_after: float | None) -> None:
    started = asyncio.get_event_loop().time()
    while True:
        if state.get("hung"):
            return
        if hang_after is not None and asyncio.get_event_loop().time() - started >= hang_after:
            print(f"[{state['id']}] going silent (simulating a hung robot) — socket stays open")
            state["hung"] = True
            return
        await ws.send(
            json.dumps(
                {"type": "heartbeat", "battery": state["battery"], "x": state["x"], "y": state["y"]}
            )
        )
        state["battery"] = max(0.0, state["battery"] - 0.5)  # slow drain, for realism
        await asyncio.sleep(HEARTBEAT_EVERY)


async def drive_to(ws, state: dict, target: tuple[float, float]) -> bool:
    """Glide from the current pose to `target`, streaming frequent heartbeats so the panel
    minimap animates the dot. Returns False if the robot froze (--hang) mid-drive."""
    sx, sy = state["x"], state["y"]
    tx, ty = target
    dist = math.hypot(tx - sx, ty - sy)
    duration = max(MOVE_STEP, dist / DRIVE_SPEED)
    steps = max(1, round(duration / MOVE_STEP))
    for i in range(1, steps + 1):
        if state.get("hung"):
            return False
        f = i / steps  # linear interpolation 0→1
        state["x"], state["y"] = sx + (tx - sx) * f, sy + (ty - sy) * f
        state["battery"] = max(0.0, state["battery"] - 0.2)
        await ws.send(
            json.dumps(
                {"type": "heartbeat", "battery": state["battery"], "x": state["x"], "y": state["y"]}
            )
        )
        await asyncio.sleep(MOVE_STEP)
    return True


async def run_task(ws, task: dict, state: dict) -> None:
    """Walk one assigned navigation task: accept → drive to pose → arrive → done → drive back."""
    task_id = task["task_id"]
    target_token = task.get("target_token") or "đích"
    pose = task.get("pose") or {"x": DOCK_POS[0], "y": DOCK_POS[1]}
    target = (float(pose["x"]), float(pose["y"]))
    print(f"[{state['id']}] task {task_id} (navigate → {target_token}) → accept")
    await ws.send(json.dumps({"type": "task_accepted", "task_id": task_id}))

    if not await drive_to(ws, state, target):
        print(f"[{state['id']}] task {task_id} frozen mid-drive, not reporting")
        return
    print(f"[{state['id']}] task {task_id} → arrived ({target_token})")
    await ws.send(json.dumps({"type": "arrived", "task_id": task_id}))

    # Warehouse tasks complete on arrival (no "guest done" gate). A short dwell, then report done.
    await asyncio.sleep(1.0)
    if state.get("hung"):
        return
    print(f"[{state['id']}] task {task_id} → done")
    await ws.send(json.dumps({"type": "task_done", "task_id": task_id}))

    if await drive_to(ws, state, DOCK_POS):
        await ws.send(json.dumps({"type": "at_dock"}))
        print(f"[{state['id']}] về tới dock")


async def main(args) -> None:
    state = {"id": args.id, "battery": args.battery, "x": args.x, "y": args.y, "hung": False}
    url = f"ws://{args.host}:{args.port}/ws?role=robot&robot_id={args.id}"
    async with websockets.connect(url) as ws:
        print(f"[{args.id}] connected to {url}")
        hb = asyncio.create_task(heartbeat_loop(ws, state, args.hang_after))
        task_runner: asyncio.Task | None = None
        try:
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("type") == "task.assign":
                    if args.hang_on_task:
                        await ws.send(
                            json.dumps({"type": "task_accepted", "task_id": msg["task_id"]})
                        )
                        print(f"[{args.id}] accepted task {msg['task_id']} then FROZE (hung)")
                        state["hung"] = True
                        continue
                    # "Latest task.assign wins": a new goal preempts whatever we were doing. This
                    # mirrors the real bridge (a fresh goal replaces the old one) so the server only
                    # ever needs to send task.assign — no separate cancel frame, no Gazebo-side change.
                    if task_runner and not task_runner.done():
                        print(f"[{args.id}] preempting in-flight task, switching to {msg.get('task_id')}")
                        task_runner.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task_runner
                    task_runner = asyncio.create_task(run_task(ws, msg, state))
                else:
                    print(f"[{args.id}] <- {msg}")
        finally:
            hb.cancel()
            if task_runner:
                task_runner.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Mock AGV WS client for dispatcher testing")
    p.add_argument("--id", default="robo-1", help="robot id (must exist in robots table)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--battery", type=float, default=90.0)
    p.add_argument("--x", type=float, default=0.0, help="start x (default: dock)")
    p.add_argument("--y", type=float, default=0.0, help="start y (default: dock)")
    p.add_argument(
        "--hang-after",
        type=float,
        default=None,
        help="stop sending heartbeats after N seconds but keep the socket open "
        "(simulate a hung robot, to test the server's heartbeat-timeout watchdog)",
    )
    p.add_argument(
        "--hang-on-task",
        action="store_true",
        help="accept the first task then freeze (socket open, no heartbeats, never finishes) "
        "— deterministic way to test re-dispatch via the watchdog",
    )
    args = p.parse_args()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main(args))
    print(f"[{args.id}] stopped")
