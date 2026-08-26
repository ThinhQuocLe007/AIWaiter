"""Navigation API — the brain tells the orchestrator where to send the AGV.

POST /navigation takes a brain-emitted section/place token (e.g. ``"A"``,
``"dock"``, ``"Cầu cảng"``), resolves it to a warehouse pose via the
``position_parser``, and enqueues a navigation task for the fleet. This is the
server-side half of the agent → robot position contract.
"""

from fastapi import APIRouter, HTTPException

from ..schemas import NavigationRequest, TaskOut
from ..services import dispatcher, position_parser

router = APIRouter(tags=["navigation"])


@router.post("/navigation", response_model=TaskOut, status_code=201)
async def navigate(req: NavigationRequest) -> TaskOut:
    pose = position_parser.parse_position(req.token)
    if pose is None:
        raise HTTPException(404, f"Không tìm thấy vị trí '{req.token}' trên bản đồ kho")
    return await dispatcher.create_task("navigate", target_token=req.token, pose=pose)
