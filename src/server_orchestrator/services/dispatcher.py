"""Dispatcher — turns navigation requests into AGV tasks and assigns them to robots.

This is the "shift manager": it never moves anything itself. When a navigation
request arrives (the warehouse brain wants the AGV at section A, or it should
return to dock), the API routers call ``create_task(...)``. The dispatcher
persists a PENDING task, then ``try_assign()`` picks the best free robot (idle +
enough battery + nearest to the target pose) and pushes the task — with the
resolved goal pose — to *that* robot over WS. The robot reports back
(``task_accepted`` / ``arrived`` / ``task_done``), which advances the task and
the robot's state.

Two task layers (mục 6 of SYSTEM_ARCHITECTURE.md): the *system task* lives here
("navigate to A"); the robot itself turns it into physical motion (Nav2). So this
module knows target poses only to pick the nearest robot — it never speaks Nav2.
"""

import asyncio
import logging
import math
import time

from ..config import settings
from ..data.db import get_conn
from ..realtime.connection_manager import manager
from ..schemas import RobotOut, TaskOut
from ..services import position_parser
from . import fleet, floorplan

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

# Warehouse geometry, in the SAVED SLAM MAP FRAME — loaded from the shared layout file that the
# robot bridge navigates by (services/floorplan.py). The robot's heartbeat pose is in the same
# frame, so these line up with it and with warehouse_lidar.*. `TARGET_POS` is the pose we score
# "nearest robot" against for a task; the robot navigates itself, this module never speaks Nav2.
DOCK_POS = floorplan.dock_pos()  # dock in the map frame; an idle robot's default position

_IDLE_ACTIVITY = "Đang ở dock"
_RETURN_ACTIVITY = "Đang về dock"


# --- Read helpers -----------------------------------------------------------------------------
def _task_out(row) -> TaskOut:
    return TaskOut(**dict(row))


def _fetch_task(conn, task_id: int) -> TaskOut | None:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _task_out(row) if row else None


def _robot_out(row) -> RobotOut:
    return RobotOut(**fleet.overlay(dict(row)))


# --- Pose resolution ---------------------------------------------------------------------------
def _pose_for(kind: str, target_token: str | None) -> dict | None:
    """Resolve a task's goal pose (x, y, yaw) in the map frame, or None if it can't be mapped."""
    if kind == "return":
        return floorplan.dock_pose()
    if kind == "charge":
        place = floorplan.named_place_poses().get("charging")
        return place  # already has x, y, yaw
    # navigate: map the brain's token via the position_parser.
    if target_token:
        return position_parser.parse_position(target_token)
    return None


def _pose_tuple(pose: dict | None) -> tuple[float, float]:
    if pose:
        return (float(pose["x"]), float(pose["y"]))
    return DOCK_POS


# --- Broadcasting helpers (keep the panel in sync) --------------------------------------------
async def _broadcast_task(conn, task_id: int, event: str) -> None:
    task = _fetch_task(conn, task_id)
    if task:
        await manager.broadcast("panel", {"type": event, "task": task.model_dump()})


async def _broadcast_robot(conn, robot_id: str) -> None:
    row = conn.execute("SELECT * FROM robots WHERE id = ?", (robot_id,)).fetchone()
    if row:
        robot = RobotOut(**fleet.overlay(dict(row)))
        await manager.broadcast(
            "panel", {"type": "robot.updated", "robot": robot.model_dump()}
        )


# --- Robot selection --------------------------------------------------------------------------
def _distance(robot_row, target: tuple[float, float]) -> float:
    """Euclidean distance from a robot to a target pose (dock if target unknown)."""
    rx = robot_row["x"] if robot_row["x"] is not None else DOCK_POS[0]
    ry = robot_row["y"] if robot_row["y"] is not None else DOCK_POS[1]
    return math.hypot(rx - target[0], ry - target[1])


def _pick_robot(conn, target: tuple[float, float]) -> str | None:
    """Best free robot for a task: online + idle + enough battery, then nearest to the target.

    Only robots with a live WS connection are eligible (a seeded-but-offline robot can't act).
    """
    online = manager.connected_robot_ids()
    candidates = []
    for r in conn.execute(
        "SELECT * FROM robots WHERE status IN ('idle', 'returning', 'holding')"
    ).fetchall():
        if r["id"] not in online:
            continue
        m = fleet.overlay(dict(r))
        if m["battery"] is None or m["battery"] >= MIN_BATTERY:
            candidates.append(m)
    if not candidates:
        return None
    best = min(candidates, key=lambda m: _distance(m, target))
    return best["id"]


# --- Public API: requests -> tasks ------------------------------------------------------------
async def create_task(
    kind: str,
    target_token: str | None = None,
    pose: dict | None = None,
) -> TaskOut:
    """Persist a PENDING task for a navigation request, then try to assign it immediately.

    If no robot is free (the fleet is busy with a prior navigate), the new navigate **preempts**
    the in-flight one: the oldest active navigate is cancelled and its robot is reassigned to this
    new goal. This is the "stop the old errand, run the new one" behaviour the operator expects
    when they change their mind mid-drive (e.g. "đi tới khu A" → "dừng lại" → "đi tới khu B").
    """
    if pose is None:
        pose = _pose_for(kind, target_token)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (kind, target_token, pose_x, pose_y, pose_yaw, status) "
            "VALUES (?, ?, ?, ?, ?, 'PENDING')",
            (
                kind,
                target_token,
                float(pose["x"]) if pose else None,
                float(pose["y"]) if pose else None,
                float(pose["yaw"]) if pose else None,
            ),
        )
        task_id = cur.lastrowid
        task = _fetch_task(conn, task_id)
    assert task is not None
    await manager.broadcast("panel", {"type": "task.created", "task": task.model_dump()})
    log.info("task %s created kind=%s target=%s", task_id, kind, target_token)
    await try_assign()
    # Re-fetch: the snapshot above was taken before assignment. If the task is *still* PENDING
    # (no free robot), preempt one in-flight navigate and reassign its robot. Checking the live
    # status here (not the stale PENDING snapshot) is what stops us from cancelling the task we
    # just created.
    with get_conn() as conn:
        task = _fetch_task(conn, task_id)
    if task.status == "PENDING":
        await _preempt_one_navigate()
        await try_assign()
        with get_conn() as conn:
            task = _fetch_task(conn, task_id)
    return task


async def _preempt_one_navigate() -> None:
    """Cancel the oldest in-flight navigate so its robot can take a new (preempting) goal."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE kind = 'navigate' "
            "AND status IN ('ASSIGNED', 'IN_PROGRESS') ORDER BY created_at, id LIMIT 1"
        ).fetchone()
    if row is not None:
        log.info("preempting in-flight navigate task %s for new goal", row["id"])
        await cancel_task(row["id"])


async def cancel_task(task_id: int) -> None:
    """Cancel a task (e.g. operator said "dừng lại" / changed destination).

    Marks the task CANCELLED and frees its robot (status -> holding, immediately reassignable) so a
    new goal can be dispatched. The robot itself is NOT sent a separate abort frame: the contract is
    "latest ``task.assign`` wins" — the next navigate simply reassigns and the robot drops its current
    goal for the new one. This keeps the server→robot protocol to a single command type, so no robot
    bridge (incl. the Gazebo machine) needs a new message handler. Idempotent for DONE/CANCELLED.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return
        if row["status"] in ("DONE", "CANCELLED"):
            return
        conn.execute(
            "UPDATE tasks SET status = 'CANCELLED', updated_at = datetime('now') WHERE id = ?",
            (task_id,),
        )
        robot_id = row["robot_id"]
        if robot_id:
            conn.execute(
                "UPDATE robots SET status = 'holding', current_task_id = NULL, activity = ? "
                "WHERE id = ?",
                ("Đã dừng", robot_id),
            )
            await _broadcast_robot(conn, robot_id)
        await _broadcast_task(conn, task_id, "task.updated")


async def cancel_robot_task(robot_id: str) -> None:
    """Cancel whatever task the named robot is currently on (used by "dừng lại")."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT current_task_id FROM robots WHERE id = ?", (robot_id,)
        ).fetchone()
    task_id = row["current_task_id"] if row else None
    if task_id is not None:
        await cancel_task(task_id)


async def try_assign() -> None:
    """Assign every PENDING task to a free robot, oldest first. No-op if none are free."""
    with get_conn() as conn:
        pending = conn.execute(
            "SELECT * FROM tasks WHERE status = 'PENDING' ORDER BY created_at, id"
        ).fetchall()
        assignments: list[tuple[int, str, str, dict | None]] = []
        for task in pending:
            target = _pose_tuple(
                {"x": task["pose_x"], "y": task["pose_y"]} if task["pose_x"] is not None else None
            )
            robot_id = _pick_robot(conn, target)
            if robot_id is None:
                break  # no free robot — leave this and the rest queued
            conn.execute(
                "UPDATE tasks SET robot_id = ?, status = 'ASSIGNED', "
                "updated_at = datetime('now') WHERE id = ?",
                (robot_id, task["id"]),
            )
            activity = (
                f"Đang tới {task['target_token']}" if task["target_token"]
                else _RETURN_ACTIVITY
            )
            conn.execute(
                "UPDATE robots SET status = 'busy', current_task_id = ?, activity = ? "
                "WHERE id = ?",
                (task["id"], activity, robot_id),
            )
            pose = (
                {"x": task["pose_x"], "y": task["pose_y"], "yaw": task["pose_yaw"]}
                if task["pose_x"] is not None
                else None
            )
            assignments.append((task["id"], robot_id, task["kind"], pose))

    # Push outside the DB transaction so a slow/closed socket can't hold the write lock.
    for task_id, robot_id, kind, pose in assignments:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT target_token FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            target_token = row["target_token"] if row else None
        payload = {
            "type": "task.assign",
            "task_id": task_id,
            "kind": kind,
            "target_token": target_token,
            "pose": pose,
        }
        delivered = await manager.send_to_robot(robot_id, payload)
        with get_conn() as conn:
            await _broadcast_task(conn, task_id, "task.updated")
            await _broadcast_robot(conn, robot_id)
        if not delivered:
            log.warning("robot %s vanished before task %s delivered; requeueing", robot_id, task_id)
            await _requeue_task(task_id, robot_id)
    if assignments:
        log.info("assigned %d task(s)", len(assignments))


# --- Public API: robot -> server callbacks -----------------------------------------------------
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
    """A robot dropped: requeue whatever it was doing so another robot can take over."""
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
    """Record battery + position from a periodic robot heartbeat, and mark it freshly alive."""
    now = time.monotonic()
    _last_seen[robot_id] = now
    battery, x, y = msg.get("battery"), msg.get("x"), msg.get("y")
    fleet.update(robot_id, battery=battery, x=x, y=y)

    if now - _last_snapshot.get(robot_id, 0.0) >= SNAPSHOT_EVERY:
        _last_snapshot[robot_id] = now
        with get_conn() as conn:
            conn.execute(
                "UPDATE robots SET battery = COALESCE(?, battery), x = COALESCE(?, x), "
                "y = COALESCE(?, y) WHERE id = ?",
                (battery, x, y, robot_id),
            )

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
            "WHERE id = ? AND robot_id = ? AND status = 'ASSIGNED'",
            (task_id, robot_id),
        )
        await _broadcast_task(conn, task_id, "task.updated")
    log.info("task %s accepted by %s", task_id, robot_id)


async def on_arrived(robot_id: str, task_id: int | None) -> None:
    """Robot reached the target — flip its panel board to "at target" and notify the panel."""
    if task_id is None:
        return
    with get_conn() as conn:
        task = _fetch_task(conn, task_id)
        if task is None or task.status == "CANCELLED":
            return
        target = task.target_token or "đích"
        conn.execute(
            "UPDATE robots SET activity = ? WHERE id = ?",
            (f"Đã tới {target}", robot_id),
        )
        await _broadcast_robot(conn, robot_id)
    # Wake any listening panel/operator that the AGV has arrived at the requested location.
    await manager.broadcast(
        "panel", {"type": "robot.arrived", "robot_id": robot_id, "task_id": task_id}
    )
    log.info("task %s arrived (robot %s)", task_id, robot_id)


async def on_done(robot_id: str, task_id: int | None) -> None:
    """Task finished: close it, mark the robot driving home, then pull the next queued task."""
    with get_conn() as conn:
        if task_id is not None:
            conn.execute(
                "UPDATE tasks SET status = 'DONE', updated_at = datetime('now') "
                "WHERE id = ? AND status != 'CANCELLED'",
                (task_id,),
            )
            await _broadcast_task(conn, task_id, "task.updated")
        conn.execute(
            "UPDATE robots SET status = 'returning', current_task_id = NULL, activity = ? "
            "WHERE id = ?",
            (_RETURN_ACTIVITY, robot_id),
        )
        await _broadcast_robot(conn, robot_id)
    log.info("task %s done by %s — heading back to dock", task_id, robot_id)
    await try_assign()


async def on_at_dock(robot_id: str) -> None:
    """Robot reports it physically reached the dock: flip 'Đang về dock' -> 'Đang ở dock'."""
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
    until its bridge connects. Also clears the stale battery/pose snapshot from a previous run.
    """
    with get_conn() as conn:
        conn.execute(
            "UPDATE robots SET status = 'offline', current_task_id = NULL, activity = ?, "
            "battery = NULL, x = NULL, y = NULL",
            ("Chưa kích hoạt",),
        )


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
    """One pass: any robot silent past the timeout is treated as hung and torn down."""
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
        await on_robot_disconnect(robot_id)  # requeue + mark offline
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
