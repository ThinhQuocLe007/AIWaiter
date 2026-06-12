from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PaymentRequest(BaseModel):
    table_id: str = Field(..., description="The table ID to request payment for (e.g., 'T1')")


class PaymentResponse(BaseModel):
    status: Literal["success", "error"]
    table_id: str
    session_id: Optional[int] = None
    qr_url: Optional[str] = None
    amount: Optional[int] = None
    message: str


class VerifyPaymentResponse(BaseModel):
    status: Literal["success", "error"]
    table_id: str
    message: str
