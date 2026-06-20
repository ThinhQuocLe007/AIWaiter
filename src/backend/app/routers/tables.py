"""Tables API — table list + seating (Kiosk check-in).

GET /tables backs the kiosk's "which tables are free" view and the panel's per-table order
list. POST /seatings seats a party (marks a free table as occupied) so the customer UI knows
which table_id to attach to its orders.
"""

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..schemas import SeatingCreate, TableOut

router = APIRouter(tags=["tables"])


@router.get("/tables", response_model=list[TableOut])
def list_tables() -> list[TableOut]:
    with get_conn() as conn:
        rows = conn.execute('SELECT * FROM "tables" ORDER BY id').fetchall()
    return [TableOut(**dict(r)) for r in rows]


@router.post("/seatings", response_model=TableOut, status_code=201)
def create_seating(payload: SeatingCreate) -> TableOut:
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM "tables" WHERE id = ?', (payload.table_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"Table {payload.table_id} not found")
        if row["status"] != "TRONG":
            raise HTTPException(409, f"Table {payload.table_id} is not free ({row['status']})")
        conn.execute(
            'UPDATE "tables" SET status = ? WHERE id = ?',
            ("DANG_PHUC_VU", payload.table_id),
        )
        updated = conn.execute(
            'SELECT * FROM "tables" WHERE id = ?', (payload.table_id,)
        ).fetchone()
    return TableOut(**dict(updated))
