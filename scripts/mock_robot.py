"""Mock robot — a stand-in for a real Jetson robot, to test the dispatcher end-to-end.

It speaks the same WS contract a real `ws_client.py` (Mốc A) will: connects as
`/ws?role=robot&robot_id=<id>`, sends periodic heartbeats, and when it receives a `task.assign`
it walks the task lifecycle (accept → drive → arrive → serve → finish) instead of using Nav2.

Serving is event-driven, not on a timer: for a `go_to_table` / `call` task the robot ARRIVES and
then WAITS at the table (so you can talk to it via the voice device) until the server sends a
`task.release` frame — which the dispatcher emits when the guest places an order (`POST /orders`)
or pays (`/payments/verify`). Only then does it report `task_done` and drive back to the dock. A
`deliver` task still auto-completes after dropping the food.

Run (backend must be up on :8000):
    uv run python scripts/mock_robot.py --id robo-1

Typical demo: seat a table (kiosk) → this robot drives over and parks ("đang phục vụ") → talk to it
on customer_ui → place an order or pay → it reports done and returns to the dock.

The dispatcher is written to handle a fleet of N robots, but the demo seeds a single robot
(robo-1). Pass a different --id only if you have added more robots to the seed.

Kill it mid-task (Ctrl-C) to see the dispatcher requeue its task to another robot.
"""

import argparse
import asyncio
import contextlib
import json
import math

import websockets

HEARTBEAT_EVERY = 3.0  # seconds, while idle
DRIVE_SPEED = 0.7  # m/s fake travel speed (a table is ~5m away → a few seconds)
MOVE_STEP = 0.2  # seconds between pose updates while driving → smooth dot on the panel minimap
ACTION_SECONDS = 3.0  # fake time doing the action at the table

# Approach waypoints per table and the dock — in the saved SLAM map frame, mirroring the server's
# dispatcher (src/server_orchestrator/services/dispatcher.py), which copies them from the sim's food_delivery.py.
TABLE_POS = {
    1: (8.730, 1.301),
    2: (7.233, 0.314),
    3: (8.741, -0.694),
    4: (8.700, -3.152),
    5: (7.257, -4.309),
    6: (8.679, -5.178),
}
DOCK_POS = (0.0, 0.0)


async def heartbeat_loop(ws, state: dict, hang_after: float | None) -> None:
    started = asyncio.get_event_loop().time()
    while True:
        # Simulate a hung robot: stop pinging but keep the socket open (no clean disconnect),
        # so the server's heartbeat-timeout watchdog is the only thing that can notice.
        if state.get("hung"):  # frozen by --hang-on-task
            return
        if hang_after is not None and asyncio.get_event_loop().time() - started >= hang_after:
            print(f"[{state['id']}] going silent (simulating a hung robot) — socket stays open")
            state["hung"] = True  # also freeze any in-flight task (no more arrived/done)
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
    """Walk one assigned task: accept → drive to table → arrive → serve → done → drive back to dock.

    The "serve" step depends on the task kind, mirroring the real flow:
      * ``go_to_table`` / ``call`` — the robot WAITS at the table (taking the order / helping) until
        the server says the guest is finished. That signal is a ``task.release`` frame, sent by the
        dispatcher when the guest places an order or pays. Only then does it report done and leave.
      * ``deliver`` — it just hands the food over (a few seconds) and heads back on its own.
    """
    task_id = task["task_id"]
    table_id = task["table_id"]
    kind = task.get("kind", "go_to_table")
    target = TABLE_POS.get(table_id, DOCK_POS)
    print(f"[{state['id']}] task {task_id} ({kind}, table {table_id}) → accept")
    await ws.send(json.dumps({"type": "task_accepted", "task_id": task_id}))

    if not await drive_to(ws, state, target):  # froze while driving — never report arrival
        print(f"[{state['id']}] task {task_id} frozen mid-drive, not reporting")
        return
    print(f"[{state['id']}] task {task_id} → arrived (bàn {table_id})")
    await ws.send(json.dumps({"type": "arrived", "task_id": task_id}))

    if kind in ("go_to_table", "call"):
        # Stand at the table and serve the guest. Heartbeats keep streaming our (unchanged) pose, so
        # the panel shows the robot parked at the table the whole time. Block until the server sends
        # task.release (guest ordered / paid).
        print(f"[{state['id']}] task {task_id} → đang phục vụ bàn {table_id}, chờ khách đặt món / thanh toán...")
        await state["release"].wait()
        print(f"[{state['id']}] task {task_id} → khách xong, rời bàn {table_id}")
    else:
        await asyncio.sleep(ACTION_SECONDS)  # deliver: drop the food and go
    if state.get("hung"):
        return
    print(f"[{state['id']}] task {task_id} → done")
    await ws.send(json.dumps({"type": "task_done", "task_id": task_id}))

    # Head back to the dock so the next task starts from a realistic spot (and the dot returns home).
    if await drive_to(ws, state, DOCK_POS):
        # Parked — server flips "Đang về dock" → "Đang ở dock" (ignored if we got a new task).
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
                        # Accept, then freeze mid-task: keep the socket open but stop reporting
                        # and stop heartbeats. Only the server's watchdog can notice. Deterministic
                        # (no timing to tune): the task stays IN_PROGRESS until it's requeued.
                        await ws.send(
                            json.dumps({"type": "task_accepted", "task_id": msg["task_id"]})
                        )
                        print(f"[{args.id}] accepted task {msg['task_id']} then FROZE (hung)")
                        state["hung"] = True
                        continue
                    if task_runner and not task_runner.done():
                        print(f"[{args.id}] busy, ignoring extra task {msg.get('task_id')}")
                        continue
                    # Fresh "guest is done" gate for this task; run_task waits on it, the release
                    # frame below sets it.
                    state["release"] = asyncio.Event()
                    task_runner = asyncio.create_task(run_task(ws, msg, state))
                elif msg.get("type") == "task.release":
                    # Server says the guest ordered / paid → let the waiting task finish and leave.
                    ev = state.get("release")
                    if ev is not None:
                        ev.set()
                    print(f"[{args.id}] <- task.release (bàn {msg.get('table_id')})")
                else:
                    print(f"[{args.id}] <- {msg}")
        finally:
            hb.cancel()
            if task_runner:
                task_runner.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Mock robot WS client for dispatcher testing")
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
