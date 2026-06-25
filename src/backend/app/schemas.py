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
    party_size: int | None = None
    seated_at: str | None = None


class SeatingCreate(BaseModel):
    """Seat a party at a table (Kiosk check-in)."""

    table_id: int
    party_size: int = Field(gt=0)


class TableStatusUpdate(BaseModel):
    """Change a table's serving-lifecycle status (panel: mark paid / end table)."""

    status: str


# --- Sessions -----------------------------------------------------------------------------
class SessionOut(BaseModel):
    """One serving session (a party's visit). `total` is the gộp bill across its orders."""

    id: int
    table_id: int
    status: str
    party_size: int | None = None
    started_at: str
    ended_at: str | None = None
    total: float = 0


# --- Payments (mock, gộp theo phiên) ------------------------------------------------------
class PaymentCreate(BaseModel):
    """Open a (mock) payment for a table's active session. No real money moves — the tablet shows
    a VietQR image and the guest taps "I've paid" (→ POST /payments/{id}/verify)."""

    table_id: int
    method: str = "VIETQR"


class PaymentVerify(BaseModel):
    """Confirm a payment by table (the agent's verify_payment only knows the table)."""

    table_id: int


class PaymentOut(BaseModel):
    id: int
    session_id: int
    method: str | None = None
    amount: float
    status: str
    txn_ref: str | None = None
    qr_url: str | None = None
    paid_at: str | None = None


# --- Tasks (dispatcher) -------------------------------------------------------------------
class TaskOut(BaseModel):
    """A system task the dispatcher hands to a robot (go_to_table / deliver / call)."""

    id: int
    kind: str
    table_id: int | None = None
    order_id: int | None = None
    robot_id: str | None = None
    status: str
    created_at: str
    updated_at: str


# --- Robots -------------------------------------------------------------------------------
class RobotOut(BaseModel):
    id: str
    name: str | None = None
    status: str
    battery: float | None = None
    # Human-readable "what it's doing" (e.g. "Đang giao món · Bàn 4", "Đang ở dock") — the panel
    # shows this on the robot board. Set by the dispatcher for real robots later.
    activity: str | None = None
    # Live pose in the world frame (from heartbeats), used to plot the robot on the panel minimap.
    x: float | None = None
    y: float | None = None
    current_task_id: int | None = None
