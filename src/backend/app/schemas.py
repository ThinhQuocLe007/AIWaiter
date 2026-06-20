"""Pydantic request/response models for the Orchestrator API.

Kept in one module (small for now) so the frontends and — later — the robot Brain share a
single contract. These mirror the SQLite schema in db.py (mục 8 of SYSTEM_ARCHITECTURE.md).
"""

from pydantic import BaseModel, Field


# --- Orders -------------------------------------------------------------------------------
class OrderItemIn(BaseModel):
    """One line of a new order as sent by a client (cart item)."""

    name: str
    qty: int = Field(gt=0)
    price: float = Field(ge=0)
    dish_id: int | None = None
    note: str | None = None


class OrderCreate(BaseModel):
    table_id: int
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemOut(OrderItemIn):
    id: int
    status: str


class OrderOut(BaseModel):
    id: int
    table_id: int
    status: str
    total: float
    created_at: str
    items: list[OrderItemOut] = []


class OrderStatusUpdate(BaseModel):
    status: str


# --- Tables / seatings --------------------------------------------------------------------
class TableOut(BaseModel):
    id: int
    name: str
    capacity: int
    status: str
    current_order_id: int | None = None


class SeatingCreate(BaseModel):
    """Seat a party at a table (Kiosk check-in)."""

    table_id: int
    party_size: int = Field(gt=0)
