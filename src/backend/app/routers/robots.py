"""Robots API — fleet status for the panel's robot board.

Rows hold identity (id, name) + assignment (status, current_task_id, activity) + a periodic
snapshot of pose/battery. Live pose/battery come from heartbeats and are kept in RAM (app/fleet.py)
so they don't hammer the DB; we layer them over the snapshot here. The panel polls GET /robots and
also gets realtime `robot.updated` pushes over the WS hub (app/ws.py, role=panel).
"""

from fastapi import APIRouter

from .. import fleet
from ..db import get_conn
from ..schemas import RobotOut

router = APIRouter(tags=["robots"])


@router.get("/robots", response_model=list[RobotOut])
def list_robots() -> list[RobotOut]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM robots ORDER BY id").fetchall()
    return [RobotOut(**fleet.overlay(dict(r))) for r in rows]
