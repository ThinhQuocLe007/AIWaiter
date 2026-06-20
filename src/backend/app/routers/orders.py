"""Orders API — create/list/inspect/update customer orders.

POST /orders is the heart of Mốc B: the customer UI (and later the kiosk) posts a cart here;
we persist the order + its line items, compute the total server-side (never trust the client
total), mark the table as waiting-for-kitchen, and return the saved order.
"""

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..schemas import OrderCreate, OrderOut, OrderStatusUpdate
from ..ws import manager

router = APIRouter(tags=["orders"])


def _fetch_order(conn, order_id: int) -> OrderOut | None:
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        return None
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    return OrderOut(**dict(row), items=[dict(it) for it in items])


@router.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(payload: OrderCreate) -> OrderOut:
    # Server-side total so a tampered/ stale client cart can't set the price.
    total = sum(it.price * it.qty for it in payload.items)
    with get_conn() as conn:
        table = conn.execute(
            'SELECT id FROM "tables" WHERE id = ?', (payload.table_id,)
        ).fetchone()
        if table is None:
            raise HTTPException(404, f"Table {payload.table_id} not found")

        cur = conn.execute(
            "INSERT INTO orders (table_id, status, total) VALUES (?, 'CHO_BEP', ?)",
            (payload.table_id, total),
        )
        order_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO order_items (order_id, dish_id, name, qty, price, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (order_id, it.dish_id, it.name, it.qty, it.price, it.note)
                for it in payload.items
            ],
        )
        # Table now waits for the kitchen and points at its active order.
        conn.execute(
            'UPDATE "tables" SET status = ?, current_order_id = ? WHERE id = ?',
            ("CHO_BEP", order_id, payload.table_id),
        )
        order = _fetch_order(conn, order_id)
    assert order is not None
    # Push the new order to the kitchen panel in realtime.
    await manager.broadcast("panel", {"type": "order.created", "order": order.model_dump()})
    return order


@router.get("/orders", response_model=list[OrderOut])
def list_orders(table_id: int | None = None, status: str | None = None) -> list[OrderOut]:
    clauses, params = [], []
    if table_id is not None:
        clauses.append("table_id = ?")
        params.append(table_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_conn() as conn:
        ids = conn.execute(
            f"SELECT id FROM orders{where} ORDER BY created_at DESC, id DESC", params
        ).fetchall()
        return [o for (oid,) in ids if (o := _fetch_order(conn, oid))]


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int) -> OrderOut:
    with get_conn() as conn:
        order = _fetch_order(conn, order_id)
    if order is None:
        raise HTTPException(404, f"Order {order_id} not found")
    return order


@router.patch("/orders/{order_id}", response_model=OrderOut)
async def update_order_status(order_id: int, payload: OrderStatusUpdate) -> OrderOut:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(404, f"Order {order_id} not found")
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?", (payload.status, order_id)
        )
        order = _fetch_order(conn, order_id)
    assert order is not None
    # Keep every panel in sync when a status changes (e.g. another panel ticked "done").
    await manager.broadcast("panel", {"type": "order.updated", "order": order.model_dump()})
    return order
