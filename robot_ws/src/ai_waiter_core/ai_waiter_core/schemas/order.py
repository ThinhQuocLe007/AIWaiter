from typing import Literal, List, Optional
from pydantic import BaseModel

# The 3-Step Verification Enum
OrderStage = Literal[
    "IDLE",                  # No active order
    "DRAFTING",              # User adding items, Validator checking them
    "AWAITING_CONFIRMATION", # Waiter asked "Do you confirm?"
    "CONFIRMED"              # Sent to database
]

class OrderItem(BaseModel):
    name: str
    quantity: int
    special_requests: Optional[str] = None  # e.g., "Nhiều hành", "Không cay"
    is_valid: bool = False
    error_msg: Optional[str] = None


class Cart(BaseModel):
    items: List[OrderItem] = []
    total_price: float = 0.0


class SyncCartResponse(BaseModel):
    status: Literal["success", "error"]
    items: List[OrderItem]
    total_price: float
    message: str


class ConfirmOrderResponse(BaseModel):
    status: Literal["success", "error"]
    order_id: Optional[int] = None
    message: str
