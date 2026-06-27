"""Tasks API — inspect the dispatcher queue + the table call button.

GET /tasks backs a panel view of the dispatcher queue (what's pending / who's on what).
POST /tables/{id}/call is the guest "call a waiter" button (later real ESP32 hardware, for now
curl): it enqueues a `call` task so a robot drives over to ask add-more vs. pay.
"""

from fastapi import APIRouter, HTTPException

from ..services import dispatcher
from ..data.db import get_conn
from ..schemas import TaskOut

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(status: str | None = None) -> list[TaskOut]:
    clause, params = ("WHERE status = ?", [status]) if status else ("", [])
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM tasks {clause} ORDER BY created_at DESC, id DESC", params
        ).fetchall()
    return [TaskOut(**dict(r)) for r in rows]


@router.post("/tables/{table_id}/call", response_model=TaskOut, status_code=201)
async def call_robot(table_id: int) -> TaskOut:
    with get_conn() as conn:
        row = conn.execute(
            'SELECT id FROM "tables" WHERE id = ?', (table_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, f"Table {table_id} not found")
    return await dispatcher.create_task("call", table_id=table_id)
