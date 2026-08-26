"""Admin / demo utilities.

POST /admin/reset wipes all live state (tasks), frees every robot and restores
the mock robot fleet — so a demo can be run again from scratch without
restarting the backend or deleting the SQLite file. It then pushes a ``reset``
event so any open panel reloads immediately. Not meant for production.
"""

from fastapi import APIRouter

from ..data.db import get_conn
from ..realtime.connection_manager import manager
from ..services import fleet
from ..services.menu_loader import SEED_ROBOTS

router = APIRouter(tags=["admin"])


@router.post("/admin/reset")
async def reset_state() -> dict:
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('tasks')")
        # Drop any robot that is not part of the seeded fleet.
        seed_ids = [rid for rid, *_ in SEED_ROBOTS]
        placeholders = ",".join("?" for _ in seed_ids)
        conn.execute(f"DELETE FROM robots WHERE id NOT IN ({placeholders})", seed_ids)
        # Restore the mock fleet to its seeded state ("Chưa kích hoạt", no battery/pose).
        for rid, _name, status, battery, activity in SEED_ROBOTS:
            conn.execute(
                "UPDATE robots SET status = ?, battery = ?, activity = ?, "
                "x = NULL, y = NULL, current_task_id = NULL WHERE id = ?",
                (status, battery, activity, rid),
            )
        # A robot whose WS survived the reset is still very much activated — put it straight
        # back to idle (its next heartbeat refills battery/pose), else it would show
        # "Chưa kích hoạt" and never be assigned work until it reconnected.
        for rid in manager.connected_robot_ids():
            conn.execute(
                "UPDATE robots SET status = 'idle', activity = ? WHERE id = ?",
                ("Đang ở dock", rid),
            )
        (robot_count,) = conn.execute("SELECT COUNT(*) FROM robots").fetchone()
    # Also drop the in-RAM live telemetry, otherwise GET /robots would keep overlaying the last
    # heartbeat pose on top of the now-zeroed DB snapshot (robot dot stuck at its old spot).
    fleet.clear()
    # Tell any live panel to reload its boards (tasks gone, fleet reset).
    await manager.broadcast("panel", {"type": "reset"})
    return {"status": "ok", "robots_reset": robot_count}
