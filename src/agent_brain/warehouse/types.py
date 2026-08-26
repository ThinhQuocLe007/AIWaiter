"""Cross-role shared types and the action/position contract.

The agent (brain) and the edge device (Jetson) agree on these schemas. The brain never emits
coordinates — only a location *token* (e.g. "A", "PACK") that the ROS bridge maps to geometry
using ``warehouse_agv_demo/config/semantic_tasks.yaml``.

Addressing mirrors the Gazebo sa bàn exactly: section A/B/C → ``storage_A/B/C``, slot A01..C03 →
the ``slots`` key under that station, colour blue/red/green → the box actually sitting in it.
Those three fields are everything ``storage_pick_mission.py --storage <X> --color <c>`` needs.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field


class Intent(str, Enum):
    ANSWER = "answer"          # any warehouse-information question (locate/stock/attribute/section/…)
    NAVIGATE = "navigate"      # move to an item or a named place → emit a location token
    CONTROL = "control"        # stop / resume / cancel the run in progress → emit a control verb
    MOTION = "motion"          # directional primitive: forward / back / left / right (no destination)
    PLAN = "plan"              # complex/compound/low-confidence → LLM decomposes into atomic steps
    CHAT = "chat"              # general conversation, no warehouse context


class TaskVerb(str, Enum):
    """What to do on arrival. Destination and job are separate questions: "đi tới khu C lấy hàng"
    and "qua khu C thôi, đừng lấy gì" name the same rack and run different missions."""

    FETCH = "fetch"            # lấy rồi mang về trạm đóng gói — mặc định của một lệnh kho
    FETCH_HOLD = "fetch_hold"  # lấy xong giữ trên khay, không chạy chặng về
    GOTO = "goto"              # chỉ chạy tới, không gắp gì (bài demo né người)
    DELIVER = "deliver"        # hàng đã trên khay: chạy nốt chặng về và hạ xuống


class LiftDirection(str, Enum):
    UP = "up"
    DOWN = "down"


class ControlVerb(str, Enum):
    """What a CONTROL turn asks the robot to do to the run that is already moving."""

    STOP = "stop"      # hold position, keep the goal — "đi tiếp" resumes the same mission
    RESUME = "resume"  # release the hold placed by STOP
    CANCEL = "cancel"  # abandon the mission entirely and stand down


class PositionToken(BaseModel):
    """A geometry-agnostic location label emitted by the brain.

    `token` is the single string the bridge resolves: a section ("A"/"B"/"C") for a rack, or a
    named place ("PACK"/"DOCK"). `slot` and `color` narrow it to one physical box; they are None
    for named places, which have no shelf cell.
    """

    token: str = Field(..., description='Location label the bridge understands, e.g. "A" or "PACK".')
    section: Optional[str] = None
    slot: Optional[str] = Field(default=None, description='Shelf cell, e.g. "A01".')
    color: Optional[str] = Field(default=None, description="blue | red | green — the box in that cell.")


class NavigateAction(BaseModel):
    type: Literal["navigate"] = "navigate"
    position: PositionToken
    task: TaskVerb = TaskVerb.FETCH


class ControlAction(BaseModel):
    type: Literal["control"] = "control"
    verb: ControlVerb


class LiftAction(BaseModel):
    """The five-stage scissor lift. Separate from navigate because it names no destination."""

    type: Literal["lift"] = "lift"
    direction: LiftDirection


class MotionDirection(str, Enum):
    """A directional primitive — drives the AGV a fixed pulse, names no destination."""

    FORWARD = "forward"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"


class MotionAction(BaseModel):
    """Velocity pulse in one of four directions (demo-grade, no distance/heading)."""

    type: Literal["motion"] = "motion"
    direction: MotionDirection


# Discriminated on `type` rather than one class with nullable fields: a stop must never be
# mistaken for a navigate whose position failed to resolve. `robot_link.capabilities` switches on
# `type` (and then on `task`) to pick the exact warehouse_agv_demo command.
Action = Annotated[
    Union[NavigateAction, ControlAction, LiftAction, MotionAction], Field(discriminator="type")
]


class ChatRequest(BaseModel):
    text: str
    session_id: str = Field(..., description="Thread id for multi-turn memory (one worker shift).")


class ChatResponse(BaseModel):
    reply: str
    intent: Intent
    action: Optional[Action] = None
