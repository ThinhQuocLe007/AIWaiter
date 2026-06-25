"""Mock robot — a stand-in for a real Jetson robot, to test the dispatcher end-to-end.

It speaks the same WS contract a real `ws_client.py` (Mốc A) will: connects as
`/ws?role=robot&robot_id=<id>`, sends periodic heartbeats, and when it receives a `task.assign`
it walks the task lifecycle (accept → drive → arrive → finish) on a timer instead of using Nav2.

Run (backend must be up on :8000):
    uv run python scripts/mock_robot.py --id robo-1
    uv run python scripts/mock_robot.py --id robo-2 --x 2.0 --y 0.5   # second robot, elsewhere

Kill it mid-task (Ctrl-C) to see the dispatcher requeue its task to another robot.
"""

import argparse
import asyncio
import contextlib
import json

import websockets

HEARTBEAT_EVERY = 3.0  # seconds
DRIVE_SECONDS = 4.0  # fake travel time to a table
ACTION_SECONDS = 3.0  # fake time doing the action at the table


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


async def run_task(ws, task: dict, state: dict) -> None:
    """Walk one assigned task: accept → drive → arrive → act → done."""
    task_id = task["task_id"]
    print(f"[{state['id']}] task {task_id} ({task['kind']}, table {task['table_id']}) → accept")
    await ws.send(json.dumps({"type": "task_accepted", "task_id": task_id}))

    await asyncio.sleep(DRIVE_SECONDS)
    if state.get("hung"):  # froze while driving — never report arrival
        print(f"[{state['id']}] task {task_id} frozen mid-drive, not reporting")
        return
    print(f"[{state['id']}] task {task_id} → arrived")
    await ws.send(json.dumps({"type": "arrived", "task_id": task_id}))

    await asyncio.sleep(ACTION_SECONDS)
    if state.get("hung"):
        return
    print(f"[{state['id']}] task {task_id} → done")
    await ws.send(json.dumps({"type": "task_done", "task_id": task_id}))


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
    p = argparse.ArgumentParser(description="Mock robot WS client for dispatcher testing")
    p.add_argument("--id", default="robo-1", help="robot id (must exist in robots table)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--battery", type=float, default=90.0)
    p.add_argument("--x", type=float, default=-1.95, help="start x (default: dock)")
    p.add_argument("--y", type=float, default=-7.01, help="start y (default: dock)")
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
