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

from . import fleet
from ..config import settings
from ..data.db import get_conn
from ..schemas import RobotOut, TaskOut
from ..realtime.connection_manager import manager

log = logging.getLogger(__name__)

# Robot is considered too low to take a new task (should head to the dock to charge).
MIN_BATTERY = 20.0

# Last time (monotonic seconds) we heard a heartbeat from each connected robot. A robot that
# goes silent past settings.heartbeat_timeout_s is treated as hung even if its socket looks open.
_last_seen: dict[str, float] = {}

# Last time (monotonic) we pushed a robot's live pose to the panel. Heartbeats can arrive several
# times a second while a robot is moving; we throttle the minimap broadcast so a big fleet can't
# flood the panel socket. Live pose/battery live in RAM (fleet.py), NOT the DB — see on_heartbeat.
_last_pose_bcast: dict[str, float] = {}
POSE_BCAST_EVERY = 0.2  # seconds — smooth enough for the minimap, light on the socket

# Last time (monotonic) we snapshotted a robot's live pose/battery to the DB. The DB row is only a
# cold-start fallback (panel reload before the first heartbeat), so we persist it occasionally
# instead of on every beat — that's the whole point of keeping telemetry in RAM.
_last_snapshot: dict[str, float] = {}
SNAPSHOT_EVERY = 15.0  # seconds

# Approach waypoints per table, in the SAVED SLAM MAP FRAME — copied verbatim from the sim's
# food_delivery.py (DESTINATIONS), which is what the real robot's Nav2/AMCL actually navigates to.
# The robot's heartbeat pose is published in this same map frame, so these line up with it (and
# with restaurant.pgm). Used to score "which idle robot is nearest"; the robot navigates itself.
TABLE_POS: dict[int, tuple[float, float]] = {
    1: (8.730, 1.301),
    2: (7.233, 0.314),
    3: (8.741, -0.694),
    4: (8.700, -3.152),
    5: (7.257, -4.309),
    6: (8.679, -5.178),
}
DOCK_POS = (0.0, 0.0)  # spawn/dock in the map frame; an idle robot's default position

# ArUco marker positions per table in the map frame — the marker hangs at the table itself
# (computed from food_delivery.get_marker_global_tf's world poses through the world→map
# transform). This is where the physical table actually is, so the panel minimap draws the
# table icons here; TABLE_POS above is only the robot's *approach* waypoint in front of it.
TABLE_MARKER_POS: dict[int, tuple[float, float]] = {
    1: (7.110, 1.343),
    2: (8.890, 0.350),
    3: (7.110, -0.650),
    4: (7.110, -3.250),
    5: (8.890, -4.250),
    6: (7.110, -5.250),
}

# Approach heading per table, as a unit vector in the map frame (NORTH=+X, SOUTH=-X,
# WEST=+Y, EAST=-Y), copied from food_delivery.py DESTINATIONS. The ArUco marker sits in
# front of the robot (this direction) so it can read the table number; the physical table
# is just beyond the marker, against the wall. The minimap uses this to draw the table icon
# out at the wall edge instead of at the robot's approach waypoint.
TABLE_HEADING: dict[int, tuple[float, float]] = {
    1: (-1.0, 0.0),   # SOUTH
    2: (1.0, 0.0),    # NORTH
    3: (-1.0, 0.0),   # SOUTH
    4: (-1.0, 0.0),   # SOUTH
    5: (1.0, 0.0),    # NORTH
    6: (-1.0, 0.0),   # SOUTH
}

# What a robot is doing *while travelling* to the table, for the panel's robot board.
_ACTIVITY = {
    "go_to_table": "Đang tới bàn {table}",
    "deliver": "Đang giao món · Bàn {table}",
    "call": "Đang tới bàn {table} (gọi phục vụ)",
}
# What a robot is doing *after it has arrived* and is standing at the table (serving the guest).
# go_to_table / call mean the robot waits there (taking the order / helping) until the guest orders
# or pays; deliver just hands the food over and leaves on its own.
_SERVING_ACTIVITY = {
    "go_to_table": "Đang phục vụ · Bàn {table}",
    "call": "Đang hỗ trợ · Bàn {table}",
    "deliver": "Đang giao món · Bàn {table}",
}
_IDLE_ACTIVITY = "Đang ở dock"
# After task_done the robot is still physically DRIVING home — it only becomes "Đang ở dock"
# when it reports `at_dock` (see on_at_dock). Both sim bridge and mock robot send that frame.
_RETURNING_ACTIVITY = "Đang về dock"
# Seeded robot whose bridge (make simbridge / mockrobot) has never connected this run.
_UNACTIVATED_ACTIVITY = "Chưa kích hoạt"


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
    # Identity/assignment come from the DB row (read in the caller's transaction so an
    # uncommitted status change is reflected); live pose/battery are layered from RAM.
    row = conn.execute("SELECT * FROM robots WHERE id = ?", (robot_id,)).fetchone()
    if row:
        robot = RobotOut(**fleet.overlay(dict(row)))
        await manager.broadcast(
            "panel", {"type": "robot.updated", "robot": robot.model_dump()}
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
    candidates = []
    # 'returning' counts as free: the robot is just driving home and both robot clients queue a
    # task assigned mid-drive, so it starts as soon as the wheels are free.
    for r in conn.execute(
        "SELECT * FROM robots WHERE status IN ('idle', 'returning')"
    ).fetchall():
        if r["id"] not in online:
            continue
        # Live pose/battery (RAM) over the DB snapshot, so "nearest + charged enough" uses the
        # robot's current position, not where it was last persisted.
        m = fleet.overlay(dict(r))
        if m["battery"] is None or m["battery"] >= MIN_BATTERY:
            candidates.append(m)
    if not candidates:
        return None
    best = min(candidates, key=lambda m: _distance(m, table_id))
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
    manager.unbind_robot(robot_id)  # no longer at any table — stop routing voice to it
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
    """Record battery + position from a periodic robot heartbeat, and mark it freshly alive.

    The hot path is RAM-only (fleet.update) so a robot streaming pose several times a second never
    writes the SQLite ledger. The DB gets an occasional snapshot (cold-start fallback) and the
    panel minimap broadcast is throttled.
    """
    now = time.monotonic()
    _last_seen[robot_id] = now
    battery, x, y = msg.get("battery"), msg.get("x"), msg.get("y")
    fleet.update(robot_id, battery=battery, x=x, y=y)

    # Snapshot to the DB occasionally (NOT every beat) so a panel reload before the next heartbeat
    # still has a recent-ish pose/battery.
    if now - _last_snapshot.get(robot_id, 0.0) >= SNAPSHOT_EVERY:
        _last_snapshot[robot_id] = now
        with get_conn() as conn:
            conn.execute(
                "UPDATE robots SET battery = COALESCE(?, battery), x = COALESCE(?, x), "
                "y = COALESCE(?, y) WHERE id = ?",
                (battery, x, y, robot_id),
            )

    # Push the new pose to the panel minimap, throttled per robot (a read, not a write).
    if now - _last_pose_bcast.get(robot_id, 0.0) >= POSE_BCAST_EVERY:
        _last_pose_bcast[robot_id] = now
        with get_conn() as conn:
            await _broadcast_robot(conn, robot_id)


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
    """Robot reached the table — flip its panel board to "serving" and bind the table's voice.

    The table's own status is NOT touched here: it's already DANG_PHUC_VU from seating
    (the lifecycle collapsed to TRONG / DANG_PHUC_VU / DA_THANH_TOAN — see TableStatus), so the
    finer "ordering / eating" states are gone. Only the robot board + voice binding change.
    """
    if task_id is None:
        return
    with get_conn() as conn:
        task = _fetch_task(conn, task_id)
        if task is None or task.table_id is None:
            return
        # Flip the panel's robot board from "đang tới" to "đang phục vụ" — it's standing there now.
        serving = _SERVING_ACTIVITY.get(task.kind, "Đang phục vụ · Bàn {table}").format(
            table=task.table_id
        )
        conn.execute("UPDATE robots SET activity = ? WHERE id = ?", (serving, robot_id))
        await _broadcast_robot(conn, robot_id)
    # The robot is now standing at the table, so route this table's "talk to AI" button to this
    # robot's mic. Held until the robot leaves (on_done), is dispatched elsewhere (re-bind), or
    # drops (on disconnect). For go_to_table/call the robot now WAITS here until the guest orders
    # or pays — the orders/payments routers then call release_robot_at_table to send it home.
    manager.bind_table_robot(task.table_id, robot_id)
    # Wake the table's customer_ui: the robot is standing there now, so the tablet should switch
    # to the right screen on its own (menu for a first visit, order-more/pay chooser for a call).
    await manager.broadcast(
        "customer",
        {"type": "robot.arrived", "table_id": task.table_id, "kind": task.kind},
    )
    log.info("task %s arrived (table %s) — voice bound to %s", task_id, task.table_id, robot_id)


async def on_done(robot_id: str, task_id: int | None) -> None:
    """Task finished: close it, mark the robot driving home, then pull the next queued task."""
    manager.unbind_robot(robot_id)  # robot is driving home — it no longer serves any table's mic
    with get_conn() as conn:
        if task_id is not None:
            conn.execute(
                "UPDATE tasks SET status = 'DONE', updated_at = datetime('now') WHERE id = ?",
                (task_id,),
            )
            await _broadcast_task(conn, task_id, "task.updated")
        conn.execute(
            "UPDATE robots SET status = 'returning', current_task_id = NULL, activity = ? "
            "WHERE id = ?",
            (_RETURNING_ACTIVITY, robot_id),
        )
        await _broadcast_robot(conn, robot_id)
    log.info("task %s done by %s — heading back to dock", task_id, robot_id)
    await try_assign()


async def on_at_dock(robot_id: str) -> None:
    """Robot reports it physically reached the dock: flip 'Đang về dock' → 'Đang ở dock'.

    Guarded on status = 'returning' so a late frame never clobbers a robot that was already
    dispatched to a new task mid-drive (busy) or dropped offline.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE robots SET status = 'idle', activity = ? "
            "WHERE id = ? AND status = 'returning'",
            (_IDLE_ACTIVITY, robot_id),
        )
        if cur.rowcount:
            await _broadcast_robot(conn, robot_id)
            log.info("robot %s docked", robot_id)


def reset_fleet_offline() -> None:
    """Backend startup: no robot WS can be connected yet, so every seeded robot is unactivated
    until its bridge (make simbridge / mockrobot) connects. Also clears the stale battery/pose
    snapshot from a previous run — the panel must not show pin/vị trí without live data behind it.
    """
    with get_conn() as conn:
        conn.execute(
            "UPDATE robots SET status = 'offline', current_task_id = NULL, activity = ?, "
            "battery = NULL, x = NULL, y = NULL",
            (_UNACTIVATED_ACTIVITY,),
        )


async def release_robot_at_table(table_id: int) -> None:
    """Tell the robot standing at `table_id` that its visit is over (the guest just ordered or paid)
    so it can head back to the dock. We only *signal* the robot; it drives home and reports
    ``task_done`` through the normal path (on_done → free + unbind + try_assign).

    No-op if no robot is serving the table (e.g. it already left, or none ever arrived). Idempotent:
    a second order/payment event after the robot has gone simply finds no binding.
    """
    robot_id = manager.table_robot(table_id)
    if robot_id is None:
        return
    with get_conn() as conn:
        row = conn.execute(
            "SELECT current_task_id FROM robots WHERE id = ?", (robot_id,)
        ).fetchone()
    task_id = row["current_task_id"] if row else None
    await manager.send_to_robot(
        robot_id, {"type": "task.release", "task_id": task_id, "table_id": table_id}
    )
    log.info("released robot %s from table %s (task %s) — heading home", robot_id, table_id, task_id)


async def cancel_table_tasks(table_id: int) -> None:
    """Close out a table's outstanding work when its visit ends (paid, or staff ends the table).

    Every PENDING/ASSIGNED/IN_PROGRESS task for the table is marked DONE so it leaves the panel's
    queue instead of lingering forever (e.g. a `call`/`deliver` that no robot ever picked up because
    the only robot went offline). Any **online** robot still assigned one is told to drive home
    (`task.release`) and freed via the normal `on_done` path; offline robots were already cleared by
    `on_robot_disconnect`. Idempotent: a second call finds no non-DONE task and does nothing.
    """
    online = manager.connected_robot_ids()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, robot_id FROM tasks WHERE table_id = ? AND status != 'DONE'",
            (table_id,),
        ).fetchall()
        if not rows:
            return
        robots_to_send_home = {r["robot_id"] for r in rows if r["robot_id"] in online}
        for r in rows:
            conn.execute(
                "UPDATE tasks SET status = 'DONE', updated_at = datetime('now') WHERE id = ?",
                (r["id"],),
            )
            await _broadcast_task(conn, r["id"], "task.updated")
    # Nudge any robot still parked at the table to head back; on_done will free it + unbind its mic
    # when it reports in. Also drop the voice binding now so the table stops routing to it.
    for robot_id in robots_to_send_home:
        manager.unbind_robot(robot_id)
        await manager.send_to_robot(
            robot_id, {"type": "task.release", "table_id": table_id}
        )
    log.info(
        "table %s ended — cancelled %d task(s); sent home: %s",
        table_id,
        len(rows),
        robots_to_send_home or "—",
    )
    await try_assign()  # any freed robot can now pick up another table's queued work


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
