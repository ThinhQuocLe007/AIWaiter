"""Dispatcher — turns business events into robot tasks and assigns them to robots.

This is the "shift manager": it never moves anything itself. When a business event happens
(a party is seated, the kitchen marks an order done, a guest presses the call button) the API
routers call `create_task(...)`. The dispatcher persists a PENDING task, then `try_assign()`
picks the best free robot (idle + enough battery + nearest to the target table) and pushes the
task to *that* robot over WS. The robot reports back (`task_accepted`/`arrived`/`task_done`),
which advances the task and the table's serving-lifecycle state.

Two task layers (mục 6 of SYSTEM_ARCHITECTURE.md): the *system task* lives here ("serve table
3"); the robot itself turns it into physical motion (waypoint + Nav2). So this module knows
table waypoints only to pick the nearest robot — it never speaks Nav2.
"""

import asyncio
import logging
import math
import time

from .config import settings
from .db import get_conn
from .schemas import RobotOut, TaskOut
from .ws import manager

log = logging.getLogger(__name__)

# Robot is considered too low to take a new task (should head to the dock to charge).
MIN_BATTERY = 20.0

# Last time (monotonic seconds) we heard a heartbeat from each connected robot. A robot that
# goes silent past settings.heartbeat_timeout_s is treated as hung even if its socket looks open.
_last_seen: dict[str, float] = {}

# Approach waypoints (ArUco markers q1–q6) per table, from robot_ws/docs/restaurant_positions.md.
# Used only to score "which idle robot is nearest"; the robot navigates to these itself.
TABLE_POS: dict[int, tuple[float, float]] = {
    1: (-3.293, -0.89),
    2: (-2.3, 0.89),
    3: (-1.3, -0.89),
    4: (1.3, -0.89),
    5: (2.3, 0.89),
    6: (3.3, -0.89),
}
DOCK_POS = (-1.95, -7.01)  # where an idle robot waits; its default position before a heartbeat

# What a robot is doing, for the panel's robot board (human-readable, not coordinates).
_ACTIVITY = {
    "go_to_table": "Đang tới bàn {table}",
    "deliver": "Đang giao món · Bàn {table}",
    "call": "Đang tới bàn {table} (gọi phục vụ)",
}
_IDLE_ACTIVITY = "Đang ở dock"


# --- Read helpers -----------------------------------------------------------------------------
def _task_out(row) -> TaskOut:
    return TaskOut(**dict(row))


def _fetch_task(conn, task_id: int) -> TaskOut | None:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _task_out(row) if row else None


def _robot_out(row) -> RobotOut:
    return RobotOut(**dict(row))


# --- Broadcasting helpers (keep the panel in sync) --------------------------------------------
async def _broadcast_task(conn, task_id: int, event: str) -> None:
    task = _fetch_task(conn, task_id)
    if task:
        await manager.broadcast("panel", {"type": event, "task": task.model_dump()})


async def _broadcast_robot(conn, robot_id: str) -> None:
    row = conn.execute("SELECT * FROM robots WHERE id = ?", (robot_id,)).fetchone()
    if row:
        await manager.broadcast(
            "panel", {"type": "robot.updated", "robot": _robot_out(row).model_dump()}
        )


async def _broadcast_table(conn, table_id: int) -> None:
    from .schemas import TableOut

    row = conn.execute('SELECT * FROM "tables" WHERE id = ?', (table_id,)).fetchone()
    if row:
        await manager.broadcast(
            "panel", {"type": "table.updated", "table": TableOut(**dict(row)).model_dump()}
        )


# --- Robot selection --------------------------------------------------------------------------
def _distance(robot_row, table_id: int | None) -> float:
    """Euclidean distance from a robot to a table's waypoint (dock if table unknown)."""
    tx, ty = TABLE_POS.get(table_id, DOCK_POS) if table_id else DOCK_POS
    rx = robot_row["x"] if robot_row["x"] is not None else DOCK_POS[0]
    ry = robot_row["y"] if robot_row["y"] is not None else DOCK_POS[1]
    return math.hypot(rx - tx, ry - ty)


def _pick_robot(conn, table_id: int | None) -> str | None:
    """Best free robot for a task: online + idle + enough battery, then nearest to the table.

    Only robots with a live WS connection are eligible (a seeded-but-offline robot can't act).
    """
    online = manager.connected_robot_ids()
    candidates = [
        r
        for r in conn.execute("SELECT * FROM robots WHERE status = 'idle'").fetchall()
        if r["id"] in online and (r["battery"] is None or r["battery"] >= MIN_BATTERY)
    ]
    if not candidates:
        return None
    best = min(candidates, key=lambda r: _distance(r, table_id))
    return best["id"]


# --- Public API: events → tasks ---------------------------------------------------------------
async def create_task(
    kind: str, table_id: int | None = None, order_id: int | None = None
) -> TaskOut:
    """Persist a PENDING task for a business event, then try to assign it immediately."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (kind, table_id, order_id, status) VALUES (?, ?, ?, 'PENDING')",
            (kind, table_id, order_id),
        )
        task_id = cur.lastrowid
        task = _fetch_task(conn, task_id)
    assert task is not None
    await manager.broadcast("panel", {"type": "task.created", "task": task.model_dump()})
    log.info("task %s created kind=%s table=%s order=%s", task_id, kind, table_id, order_id)
    await try_assign()
    return task


async def try_assign() -> None:
    """Assign every PENDING task to a free robot, oldest first. No-op if none are free."""
    with get_conn() as conn:
        pending = conn.execute(
            "SELECT * FROM tasks WHERE status = 'PENDING' ORDER BY created_at, id"
        ).fetchall()
        assignments: list[tuple[int, str, str, int | None]] = []
        for task in pending:
            robot_id = _pick_robot(conn, task["table_id"])
            if robot_id is None:
                break  # no free robot — leave this and the rest queued
            conn.execute(
                "UPDATE tasks SET robot_id = ?, status = 'ASSIGNED', "
                "updated_at = datetime('now') WHERE id = ?",
                (robot_id, task["id"]),
            )
            activity = _ACTIVITY.get(task["kind"], "Đang làm nhiệm vụ").format(
                table=task["table_id"]
            )
            conn.execute(
                "UPDATE robots SET status = 'busy', current_task_id = ?, activity = ? "
                "WHERE id = ?",
                (task["id"], activity, robot_id),
            )
            assignments.append((task["id"], robot_id, task["kind"], task["table_id"]))

    # Push outside the DB transaction so a slow/closed socket can't hold the write lock.
    for task_id, robot_id, kind, table_id in assignments:
        order_id = None
        with get_conn() as conn:
            row = conn.execute(
                "SELECT order_id FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            order_id = row["order_id"] if row else None
        delivered = await manager.send_to_robot(
            robot_id,
            {
                "type": "task.assign",
                "task_id": task_id,
                "kind": kind,
                "table_id": table_id,
                "order_id": order_id,
            },
        )
        with get_conn() as conn:
            await _broadcast_task(conn, task_id, "task.updated")
            await _broadcast_robot(conn, robot_id)
        if not delivered:
            log.warning("robot %s vanished before task %s delivered; requeueing", robot_id, task_id)
            await _requeue_task(task_id, robot_id)
    if assignments:
        log.info("assigned %d task(s)", len(assignments))


# --- Public API: robot → server callbacks -----------------------------------------------------
async def on_robot_connect(robot_id: str) -> None:
    """A robot's WS came up: mark it online+idle and try to hand it any queued work."""
    _last_seen[robot_id] = time.monotonic()  # count it alive from the moment it connects
    with get_conn() as conn:
        conn.execute(
            "UPDATE robots SET status = 'idle', current_task_id = NULL, activity = ? "
            "WHERE id = ?",
            (_IDLE_ACTIVITY, robot_id),
        )
        await _broadcast_robot(conn, robot_id)
    log.info("robot %s online", robot_id)
    await try_assign()


async def on_robot_disconnect(robot_id: str) -> None:
    """A robot dropped: requeue whatever it was doing so another robot can take over.

    Idempotent: once the robot is marked offline with current_task_id NULL, a second call (e.g.
    the watchdog kicked a hung socket and then the WS close also fires this) finds no task and
    is a no-op.
    """
    _last_seen.pop(robot_id, None)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT current_task_id FROM robots WHERE id = ?", (robot_id,)
        ).fetchone()
        task_id = row["current_task_id"] if row else None
        conn.execute(
            "UPDATE robots SET status = 'offline', current_task_id = NULL, activity = ? "
            "WHERE id = ?",
            ("Mất kết nối", robot_id),
        )
        await _broadcast_robot(conn, robot_id)
    log.info("robot %s offline (was on task %s)", robot_id, task_id)
    if task_id is not None:
        await _requeue_task(task_id, robot_id)


async def on_heartbeat(robot_id: str, msg: dict) -> None:
    """Update battery + position from a periodic robot heartbeat, and mark it freshly alive."""
    _last_seen[robot_id] = time.monotonic()
    battery, x, y = msg.get("battery"), msg.get("x"), msg.get("y")
    with get_conn() as conn:
        conn.execute(
            "UPDATE robots SET battery = COALESCE(?, battery), x = COALESCE(?, x), "
            "y = COALESCE(?, y) WHERE id = ?",
            (battery, x, y, robot_id),
        )


async def on_accepted(robot_id: str, task_id: int | None) -> None:
    if task_id is None:
        return
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'IN_PROGRESS', updated_at = datetime('now') "
            "WHERE id = ? AND robot_id = ?",
            (task_id, robot_id),
        )
        await _broadcast_task(conn, task_id, "task.updated")
    log.info("task %s accepted by %s", task_id, robot_id)


async def on_arrived(robot_id: str, task_id: int | None) -> None:
    """Robot reached the table — advance the table's serving lifecycle by task kind."""
    if task_id is None:
        return
    with get_conn() as conn:
        task = _fetch_task(conn, task_id)
        if task is None or task.table_id is None:
            return
        new_status = {
            "go_to_table": "DANG_GOI_MON",  # robot waits, /menu open for ordering
            "deliver": "DANG_AN",  # food delivered, guests eating
        }.get(task.kind)  # "call" leaves table status as-is (guest then picks add/pay)
        if new_status:
            conn.execute(
                'UPDATE "tables" SET status = ? WHERE id = ?', (new_status, task.table_id)
            )
            await _broadcast_table(conn, task.table_id)
    log.info("task %s arrived (table %s)", task_id, task.table_id)


async def on_done(robot_id: str, task_id: int | None) -> None:
    """Task finished: close it, free the robot, then pull the next queued task."""
    with get_conn() as conn:
        if task_id is not None:
            conn.execute(
                "UPDATE tasks SET status = 'DONE', updated_at = datetime('now') WHERE id = ?",
                (task_id,),
            )
            await _broadcast_task(conn, task_id, "task.updated")
        conn.execute(
            "UPDATE robots SET status = 'idle', current_task_id = NULL, activity = ? "
            "WHERE id = ?",
            (_IDLE_ACTIVITY, robot_id),
        )
        await _broadcast_robot(conn, robot_id)
    log.info("task %s done by %s", task_id, robot_id)
    await try_assign()


async def _requeue_task(task_id: int, robot_id: str) -> None:
    """Put a task back on the queue (robot died/vanished) and try to reassign it."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'PENDING', robot_id = NULL, "
            "updated_at = datetime('now') WHERE id = ? AND status != 'DONE'",
            (task_id,),
        )
        await _broadcast_task(conn, task_id, "task.updated")
    await try_assign()


# --- Liveness watchdog ------------------------------------------------------------------------
async def watchdog_tick() -> None:
    """One pass: any robot silent past the timeout is treated as hung and torn down.

    This catches the case a plain disconnect cannot: the robot is wedged/frozen but its TCP
    socket still looks open, so no WebSocketDisconnect ever fires. We reuse on_robot_disconnect
    (requeue + mark offline) and then force-close the zombie socket so it leaves the pool.
    """
    now = time.monotonic()
    stale = [
        rid
        for rid, seen in list(_last_seen.items())
        if now - seen > settings.heartbeat_timeout_s
    ]
    for robot_id in stale:
        gap = now - _last_seen.get(robot_id, now)
        log.warning(
            "robot %s hung: no heartbeat for %.1fs (> %.0fs) — requeueing its task",
            robot_id,
            gap,
            settings.heartbeat_timeout_s,
        )
        await on_robot_disconnect(robot_id)  # requeue + mark offline (pops _last_seen)
        await manager.kick_robot(robot_id)  # drop the zombie socket


async def watchdog_loop() -> None:
    """Background task (started in the app lifespan) scanning robot liveness periodically."""
    log.info(
        "robot watchdog started (timeout=%.0fs, every=%.0fs)",
        settings.heartbeat_timeout_s,
        settings.watchdog_interval_s,
    )
    while True:
        await asyncio.sleep(settings.watchdog_interval_s)
        try:
            await watchdog_tick()
        except Exception:  # never let one bad pass kill the watchdog
            log.exception("watchdog tick failed")
