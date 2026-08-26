"""Pydantic request/response models for the Orchestrator API (warehouse).

Kept in one module (small for now) so the frontends and — later — the robot
bridge share a single contract. These mirror the SQLite schema in db.py.

Status fields are typed against the cross-role enums in ``src._shared.types`` so
the orchestrator, the brain, and the AGV all speak the same vocabulary.
"""

from pydantic import BaseModel

from src._shared.types import RobotStatus, TaskKind, TaskStatus  # noqa: F401


# --- Navigation request (brain -> orchestrator) ---------------------------------
class NavigationRequest(BaseModel):
    """A brain request to send the AGV to a section/place. `token` is the geometry-agnostic
    label the brain emits (``"A"``, ``"dock"``, ``"Cầu cảng"`` …). `section` is the raw
    PositionToken.section when available (optional, used for display)."""

    token: str
    section: str | None = None


# --- Tasks (dispatcher) -------------------------------------------------------------------
class Pose(BaseModel):
    """A resolved navigation goal in the warehouse map frame (metres, radians)."""

    x: float
    y: float
    yaw: float


class TaskOut(BaseModel):
    """A system task the dispatcher hands to an AGV (navigate / return / charge)."""

    id: int
    kind: TaskKind
    target_token: str | None = None
    pose: Pose | None = None
    robot_id: str | None = None
    status: TaskStatus
    created_at: str
    updated_at: str


# --- Robots -------------------------------------------------------------------------------
class RobotOut(BaseModel):
    id: str
    name: str | None = None
    status: RobotStatus
    battery: float | None = None
    # Human-readable "what it's doing" (e.g. "Đang tới Khu A", "Đang ở dock") — the panel
    # shows this on the robot board. Set by the dispatcher.
    activity: str | None = None
    # Live pose in the world frame (from heartbeats), used to plot the robot on the panel minimap.
    x: float | None = None
    y: float | None = None
    current_task_id: int | None = None
