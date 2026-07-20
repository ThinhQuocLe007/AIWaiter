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
    unit_price: Optional[float] = None     # per-item price from MenuManager (VND)
    special_requests: Optional[str] = None  # e.g., "Nhiều hành", "Không cay"
    is_valid: bool = False
    error_msg: Optional[str] = None


class Cart(BaseModel):
    items: List[OrderItem] = []
    total_price: float = 0.0

    def __str__(self) -> str:
        if not self.items:
            return "(trống)"
        total = f"{int(self.total_price):,}".replace(",", ".")
        item_lines = []
        for item in self.items:
            price_str = f"{int(item.unit_price):,}".replace(",", ".") if item.unit_price else "?"
            line = f"{item.name} ×{item.quantity} ({price_str}₫/phần)"
            if item.special_requests:
                line += f" (Ghi chú: {item.special_requests})"
            item_lines.append(f"  - {line}")
        return "\n".join(item_lines) + f"\nTổng: {total}₫"


class CartAddItem(BaseModel):
    """Single item delta for add_cart — lighter than OrderItem (no is_valid, no error_msg)."""
    name: str
    quantity: int = 1
    special_requests: Optional[str] = None


class CartAddResponse(BaseModel):
    status: Literal["success", "error"]
    items: List[OrderItem]
    total_price: float
    message: str


class CartRemoveResponse(BaseModel):
    status: Literal["success", "error"]
    removed: str
    # How many portions to take off. None = drop the whole line ("bỏ bia đi"), a number = take
    # that many off and keep the rest ("xóa một phần lẩu thái"). Without this the tool could only
    # say WHICH dish, so a partial removal wiped every portion of it.
    quantity: Optional[int] = None
    total_price: float
    message: str


class CartClearResponse(BaseModel):
    status: Literal["success", "error"]
    message: str


class ConfirmOrderResponse(BaseModel):
    status: Literal["success", "error"]
    order_id: Optional[int] = None
    message: str
