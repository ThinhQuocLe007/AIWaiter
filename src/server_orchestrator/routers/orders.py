"""Orders API — create/list/inspect/update customer orders.

POST /orders is the heart of Mốc B: the customer UI (and later the kiosk) posts a cart here;
we persist the order + its line items, compute the total server-side (never trust the client
total), mark the table as waiting-for-kitchen, and return the saved order.
"""

from fastapi import APIRouter, HTTPException

from ..data.db import get_conn
from ..schemas import OrderCreate, OrderOut, OrderStatusUpdate, TableOut
from ..services.sessions import ensure_active_session
from ..realtime.connection_manager import manager

router = APIRouter(tags=["orders"])


def _fetch_order(conn, order_id: int) -> OrderOut | None:
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        return None
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    return OrderOut(**dict(row), items=[dict(it) for it in items])


def _committed_quantities(conn, session_id: int) -> dict[str, int]:
    """How many portions of each dish the kitchen has already STARTED this session.

    Anything past CHO_BEP is committed — a pot on the stove cannot be un-ordered — so a
    replace-confirm must leave those rows alone AND subtract them from the incoming cart, or the
    dish would show up twice on the board (once cooking, once queued again).
    """
    rows = conn.execute(
        "SELECT i.name, SUM(i.qty) AS qty FROM order_items i JOIN orders o ON i.order_id = o.id "
        "WHERE o.session_id = ? AND o.status != 'CHO_BEP' GROUP BY i.name",
        (session_id,),
    ).fetchall()
    return {r["name"]: int(r["qty"]) for r in rows}


def _drop_pending_orders(conn, session_id: int) -> list[int]:
    """Delete this session's not-yet-started orders. Returns the ids that were removed.

    Only CHO_BEP rows: nothing here has been cooked, so throwing them away costs the kitchen
    nothing and keeps the board equal to the cart the guest just confirmed.
    """
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM orders WHERE session_id = ? AND status = 'CHO_BEP'", (session_id,)
        ).fetchall()
    ]
    for order_id in ids:
        conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    return ids


@router.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(payload: OrderCreate) -> OrderOut:
    with get_conn() as conn:
        table = conn.execute(
            'SELECT id FROM "tables" WHERE id = ?', (payload.table_id,)
        ).fetchone()
        if table is None:
            raise HTTPException(404, f"Table {payload.table_id} not found")

        # Attach the order to the table's open session (gộp bill). Opened at seating; lazily
        # created here if missing so an order never fails for lack of a session.
        session_id = ensure_active_session(conn, payload.table_id)

        lines = [(it.dish_id, it.name, it.qty, it.price, it.note) for it in payload.items]
        dropped_order_ids: list[int] = []
        if payload.replace_pending:
            # `items` is the guest's whole cart (see OrderCreate.replace_pending): retire the
            # queued batch and re-send only what the kitchen has not started, so a dish the guest
            # removed disappears from Chờ bếp instead of being cooked anyway.
            committed = _committed_quantities(conn, session_id)
            lines = [
                (it.dish_id, it.name, it.qty - committed.get(it.name, 0), it.price, it.note)
                for it in payload.items
                if it.qty - committed.get(it.name, 0) > 0
            ]
            dropped_order_ids = _drop_pending_orders(conn, session_id)

        if lines:
            # Server-side total so a tampered/stale client cart can't set the price.
            total = sum(qty * price for _, _, qty, price, _ in lines)
            cur = conn.execute(
                "INSERT INTO orders (session_id, table_id, status, total) "
                "VALUES (?, ?, 'CHO_BEP', ?)",
                (session_id, payload.table_id, total),
            )
            order_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO order_items (order_id, dish_id, name, qty, price, note) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(order_id, *line) for line in lines],
            )
        else:
            # Every dish in the cart is already on the stove, so this confirm only retired the
            # queued batch. Writing a zero-line order would draw a blank kitchen card; point the
            # table at the surviving order instead and return that.
            row = conn.execute(
                "SELECT id FROM orders WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if row is None:  # can't happen: empty `lines` implies a committed order exists
                raise HTTPException(409, "Giỏ hàng không còn món nào để gửi bếp.")
            order_id = row["id"]

        # The table stays DANG_PHUC_VU (dining); we just point it at its active order. Kitchen
        # progress lives on orders.status (CHO_BEP→DANG_LAM→XONG), not on the table.
        conn.execute(
            'UPDATE "tables" SET current_order_id = ? WHERE id = ?',
            (order_id, payload.table_id),
        )
        order = _fetch_order(conn, order_id)
        table_row = conn.execute(
            'SELECT * FROM "tables" WHERE id = ?', (payload.table_id,)
        ).fetchone()
    assert order is not None
    # Retire the replaced cards on the kitchen board before pushing the new one, so the panel
    # never shows the old and the new batch side by side.
    for dropped in dropped_order_ids:
        await manager.broadcast(
            "panel",
            {"type": "order.deleted", "order_id": dropped, "table_id": payload.table_id},
        )
    # Push the new order to the kitchen panel, and the table change to the overview.
    await manager.broadcast("panel", {"type": "order.created", "order": order.model_dump()})
    await manager.broadcast(
        "panel", {"type": "table.updated", "table": TableOut(**dict(table_row)).model_dump()}
    )
    # Robot stays at the table — the voice module's auto-release timer will send it
    # home after the guest stops interacting (15 s idle after the confirm reply).
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
    # Kitchen progress is panel-only: the robot takes orders, staff carry the dishes out, so
    # marking an order XONG dispatches nothing.
    await manager.broadcast("panel", {"type": "order.updated", "order": order.model_dump()})
    return order
