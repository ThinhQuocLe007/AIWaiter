"""Admin / demo utilities.

POST /admin/reset wipes all live state (orders, seatings, payments, tasks), frees every table
and restores the mock robot fleet — so a demo can be run again from scratch without restarting
the backend or deleting the SQLite file. It then pushes a `reset` event so any open panel
reloads immediately. Not meant for production.
"""

from fastapi import APIRouter

from ..db import get_conn
from ..menu import SEED_ROBOTS
from ..ws import manager

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
        # Restore the mock fleet to its seeded state.
        for rid, _name, status, battery, activity in SEED_ROBOTS:
            conn.execute(
                "UPDATE robots SET status = ?, battery = ?, activity = ?, "
                "current_task_id = NULL WHERE id = ?",
                (status, battery, activity, rid),
            )
        (table_count,) = conn.execute('SELECT COUNT(*) FROM "tables"').fetchone()
    # Tell any live panel to reload its boards (orders gone, tables freed, fleet reset).
    await manager.broadcast("panel", {"type": "reset"})
    return {"status": "ok", "tables_freed": table_count}
