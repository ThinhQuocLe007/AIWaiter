from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class SessionResponse(BaseModel):
    id: int
    table_id: str
    status: SessionStatus
    started_at: str
    ended_at: Optional[str] = None
    total_amount: float = 0.0
    has_pending_payment: bool = False
