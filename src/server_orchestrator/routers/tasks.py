"""Tasks API — inspect the dispatcher queue.

GET /tasks backs a panel view of the dispatcher queue (what's pending / who's on what).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..data.db import get_conn
from ..schemas import TaskOut
from ..services import dispatcher

router = APIRouter(tags=["tasks"])


class CancelCurrentRequest(BaseModel):
    """Cancel the task a robot is currently on (operator said "dừng lại")."""

    robot_id: str


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(status: str | None = None) -> list[TaskOut]:
    clause, params = ("WHERE status = ?", [status]) if status else ("", [])
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM tasks {clause} ORDER BY created_at DESC, id DESC", params
        ).fetchall()
    return [TaskOut(**dict(r)) for r in rows]


@router.post("/tasks/cancel")
async def cancel_current(req: CancelCurrentRequest) -> dict:
    """Cancel the task the named robot is currently running."""
    await dispatcher.cancel_robot_task(req.robot_id)
    return {"status": "ok"}


@router.post("/tasks/{task_id}/cancel")
async def cancel_one(task_id: int) -> dict:
    """Cancel a specific task by id."""
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "task not found")
    await dispatcher.cancel_task(task_id)
    return {"status": "ok"}
