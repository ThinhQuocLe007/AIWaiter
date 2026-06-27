"""In-memory live robot telemetry (pose + battery).

High-frequency, latest-value-only, ephemeral — kept in RAM, NOT the orchestrator DB. A robot
streams heartbeats several times a second while driving; persisting each one would hammer the
single SQLite file and contend with order/payment writes (a write takes a file-level lock).
Losing a tick is harmless: the next heartbeat (~ms later) overwrites it.

The `robots` table keeps identity (id, name) + assignment (status, current_task_id, activity,
dispatcher-owned) + a periodic snapshot of battery/x/y for cold start / panel reload. These live
values override that snapshot whenever we have them (see `overlay`).
"""

import threading
import time

_lock = threading.Lock()
_live: dict[str, dict] = {}  # robot_id -> {"battery", "x", "y", "updated"}


def update(robot_id: str, *, battery=None, x=None, y=None) -> None:
    """Record the latest telemetry for a robot (latest-value-wins, only non-None fields)."""
    with _lock:
        cur = _live.setdefault(robot_id, {"battery": None, "x": None, "y": None, "updated": 0.0})
        if battery is not None:
            cur["battery"] = battery
        if x is not None:
            cur["x"] = x
        if y is not None:
            cur["y"] = y
        cur["updated"] = time.monotonic()


def get(robot_id: str) -> dict | None:
    with _lock:
        v = _live.get(robot_id)
        return dict(v) if v else None


def clear() -> None:
    """Drop all live telemetry. Used by /admin/reset so a fresh demo starts with no stale pose
    (the DB snapshot is zeroed there too, but this RAM overlay would otherwise keep showing the
    last-seen pose until the next heartbeat)."""
    with _lock:
        _live.clear()


def overlay(row: dict) -> dict:
    """Return a `robots` row dict with live battery/x/y layered on top when we have them.

    Used by GET /robots, the panel broadcast and the dispatcher's robot picker so they all read
    the current pose/battery instead of the (possibly stale) DB snapshot.
    """
    live = _live.get(row.get("id"))
    if not live:
        return row
    merged = dict(row)
    for k in ("battery", "x", "y"):
        if live.get(k) is not None:
            merged[k] = live[k]
    return merged
