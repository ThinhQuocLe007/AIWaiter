"""Seed data for the warehouse orchestrator.

The canonical warehouse layout (sections + named places + SLAM map) lives in
``assets/data/warehouse_layout.json`` and is read by ``services/floorplan.py``.
This module only seeds the mock AGV fleet so the panel's robot board is demoable
before real robots wire up.
"""

# Mock fleet so the panel's robot board is demoable before Mốc A/D wires up real AGVs.
# `activity` is a human-readable "what is it doing" (the dispatcher sets this for real
# robots later). Replace with live heartbeats from the AGV bridge (same `robots` table).
SEED_ROBOTS = [
    # id, name, status, battery, activity — a robot starts UNACTIVATED: its bridge (make
    # simbridge / mockrobot) hasn't connected, so there is no battery/pose to show. It flips to
    # idle + "Đang ở dock" the moment its WS connects (dispatcher.on_robot_connect) and the panel
    # fills pin/vị trí from the first heartbeats.
    ("robo-1", "AGV 1", "offline", None, "Chưa kích hoạt"),
]


def seed_robots() -> int:
    """Populate the robots table with a small mock fleet if empty. Returns row count."""
    from ..data.db import get_conn

    with get_conn() as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM robots").fetchone()
        if count == 0:
            conn.executemany(
                "INSERT INTO robots (id, name, status, battery, activity) "
                "VALUES (?, ?, ?, ?, ?)",
                SEED_ROBOTS,
            )
        else:
            # Backfill activity on fleets seeded before the column existed (don't clobber
            # live status/battery — only fill when missing).
            for rid, _name, _status, _batt, activity in SEED_ROBOTS:
                conn.execute(
                    "UPDATE robots SET activity = ? WHERE id = ? AND activity IS NULL",
                    (activity, rid),
                )
        (total,) = conn.execute("SELECT COUNT(*) FROM robots").fetchone()
    return total
