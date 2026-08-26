"""Tasks API — inspect the dispatcher queue.

GET /tasks backs a panel view of the dispatcher queue (what's pending / who's on what).
"""

from fastapi import APIRouter

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
