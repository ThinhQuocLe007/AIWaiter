"""Robots API — fleet status for the panel's robot board.

For now the fleet is seeded mock data (seed_robots in menu.py); the panel polls GET /robots and
shows busy/idle + battery. When the robot Brain comes online (Mốc A/D) it will update these rows
and push `robot.updated` over the shared WS hub (app/ws.py, role=panel).
"""

from fastapi import APIRouter

from ..db import get_conn
from ..schemas import RobotOut

router = APIRouter(tags=["robots"])


@router.get("/robots", response_model=list[RobotOut])
def list_robots() -> list[RobotOut]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM robots ORDER BY id").fetchall()
    return [RobotOut(**dict(r)) for r in rows]
