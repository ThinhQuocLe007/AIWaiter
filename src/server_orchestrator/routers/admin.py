"""Admin / demo utilities.

POST /admin/reset wipes all live state (orders, seatings, payments, tasks), frees every table
and restores the mock robot fleet — so a demo can be run again from scratch without restarting
the backend or deleting the SQLite file. It then pushes a `reset` event so any open panel
reloads immediately. Not meant for production.
"""

from fastapi import APIRouter

from ..services import fleet
from ..data.db import get_conn
from ..services.menu_loader import SEED_ROBOTS
from ..realtime.connection_manager import manager

router = APIRouter(tags=["admin"])


@router.post("/admin/reset")
async def reset_state() -> dict:
    with get_conn() as conn:
        conn.execute("DELETE FROM order_items")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM tasks")
        # Restart the AUTOINCREMENT counters so a fresh demo gets ids from 1 again.
        conn.execute(
            "DELETE FROM sqlite_sequence "
            "WHERE name IN ('orders', 'order_items', 'payments', 'tasks')"
        )
        # Free every table.
        conn.execute(
            'UPDATE "tables" SET status = ?, current_order_id = NULL, '
            "party_size = NULL, seated_at = NULL",
            ("TRONG",),
        )
        # Drop any robot that is not part of the seeded fleet (e.g. a removed mock robot).
        seed_ids = [rid for rid, *_ in SEED_ROBOTS]
        placeholders = ",".join("?" for _ in seed_ids)
        conn.execute(
            f"DELETE FROM robots WHERE id NOT IN ({placeholders})",
            seed_ids,
        )
        # Restore the mock fleet to its seeded state.
        for rid, _name, status, battery, activity in SEED_ROBOTS:
            conn.execute(
                "UPDATE robots SET status = ?, battery = ?, activity = ?, "
                "x = NULL, y = NULL, current_task_id = NULL WHERE id = ?",
                (status, battery, activity, rid),
            )
        (table_count,) = conn.execute('SELECT COUNT(*) FROM "tables"').fetchone()
    # Also drop the in-RAM live telemetry, otherwise GET /robots would keep overlaying the last
    # heartbeat pose on top of the now-zeroed DB snapshot (robot dot stuck at its old spot).
    fleet.clear()
    # Tell any live panel to reload its boards (orders gone, tables freed, fleet reset), and any
    # customer tablet to drop its persisted cart + conversation (the sessions no longer exist).
    await manager.broadcast("panel", {"type": "reset"})
    await manager.broadcast("customer", {"type": "reset"})
    return {"status": "ok", "tables_freed": table_count}
