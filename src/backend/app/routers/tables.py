"""Tables API — table list + seating (Kiosk check-in) + serving lifecycle.

GET /tables backs the kiosk's "which tables are free" view and the panel's per-table overview.
POST /seatings seats a party (marks a free table as occupied, records party size + start time)
so the customer UI knows which table_id to attach to its orders. PATCH /tables/{id} drives the
panel's "mark paid / end table" actions. Status changes broadcast to the panel for realtime.
"""

from fastapi import APIRouter, HTTPException

from .. import dispatcher
from ..db import get_conn
from ..schemas import SeatingCreate, TableOut, TableStatusUpdate
from ..ws import manager

router = APIRouter(tags=["tables"])


def _fetch_table(conn, table_id: int) -> TableOut | None:
    row = conn.execute('SELECT * FROM "tables" WHERE id = ?', (table_id,)).fetchone()
    return TableOut(**dict(row)) if row else None


@router.get("/tables", response_model=list[TableOut])
def list_tables() -> list[TableOut]:
    with get_conn() as conn:
        rows = conn.execute('SELECT * FROM "tables" ORDER BY id').fetchall()
    return [TableOut(**dict(r)) for r in rows]


@router.get("/tables/{table_id}", response_model=TableOut)
def get_table(table_id: int) -> TableOut:
    with get_conn() as conn:
        table = _fetch_table(conn, table_id)
    if table is None:
        raise HTTPException(404, f"Table {table_id} not found")
    return table


@router.post("/seatings", response_model=TableOut, status_code=201)
async def create_seating(payload: SeatingCreate) -> TableOut:
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM "tables" WHERE id = ?', (payload.table_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"Table {payload.table_id} not found")
        if row["status"] != "TRONG":
            raise HTTPException(409, f"Table {payload.table_id} is not free ({row['status']})")
        conn.execute(
            'UPDATE "tables" SET status = ?, party_size = ?, seated_at = datetime(\'now\') '
            "WHERE id = ?",
            ("DANG_PHUC_VU", payload.party_size, payload.table_id),
        )
        updated = _fetch_table(conn, payload.table_id)
    assert updated is not None
    await manager.broadcast("panel", {"type": "table.updated", "table": updated.model_dump()})
    # A seated party needs a robot to come take the order → enqueue a go_to_table task.
    await dispatcher.create_task("go_to_table", table_id=payload.table_id)
    return updated


@router.patch("/tables/{table_id}", response_model=TableOut)
async def update_table_status(table_id: int, payload: TableStatusUpdate) -> TableOut:
    with get_conn() as conn:
        existing = conn.execute(
            'SELECT id FROM "tables" WHERE id = ?', (table_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(404, f"Table {table_id} not found")
        if payload.status == "TRONG":
            # Ending a table clears its party so the overview reads it as truly free.
            conn.execute(
                'UPDATE "tables" SET status = ?, current_order_id = NULL, '
                "party_size = NULL, seated_at = NULL WHERE id = ?",
                ("TRONG", table_id),
            )
        else:
            conn.execute(
                'UPDATE "tables" SET status = ? WHERE id = ?', (payload.status, table_id)
            )
        updated = _fetch_table(conn, table_id)
    assert updated is not None
    await manager.broadcast("panel", {"type": "table.updated", "table": updated.model_dump()})
    return updated
