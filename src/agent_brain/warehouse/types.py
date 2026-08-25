"""Cross-role shared types and the action/position contract.

The agent (brain) and the edge device (Jetson) agree on these schemas. The brain never emits
coordinates — only a section *token* (e.g. "A") that the other team maps to geometry.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Intent(str, Enum):
    ANSWER = "answer"          # any warehouse-information question (locate/stock/attribute/section/…)
    NAVIGATE = "navigate"      # move to an item or a named place → emit a section token
    CHAT = "chat"              # general conversation, no warehouse context


class PositionToken(BaseModel):
    """A geometry-agnostic location label emitted by the brain.

    `section`/`aisle`/`bin` mirror the inventory record; `token` is the single string the edge
    parser expects (the section, e.g. "A"). The brain does NOT compute coordinates.
    """

    token: str = Field(..., description='Section label the edge parser understands, e.g. "A".')
    section: Optional[str] = None
    aisle: Optional[str] = None
    bin: Optional[str] = None


class Action(BaseModel):
    """Optional structured action attached to a reply."""

    type: Literal["navigate"] = "navigate"
    position: PositionToken


class ChatRequest(BaseModel):
    text: str
    session_id: str = Field(..., description="Thread id for multi-turn memory (one worker shift).")


class ChatResponse(BaseModel):
    reply: str
    intent: Intent
    action: Optional[Action] = None
