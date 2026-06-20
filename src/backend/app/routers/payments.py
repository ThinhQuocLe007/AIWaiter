"""Payments — mock confirmation (Mốc C, nhánh feat/payment-tool).

No real money moves: the tablet shows a (mock) VietQR image and the guest taps "Đã thanh
toán xong". This endpoint records that confirmation (a PAID row in `payments`) and flips the
table to DA_THANH_TOAN so the panel can clear it (→ TRONG via its "Kết thúc bàn" button).
A real PSP (VietQR/MoMo/ZaloPay) would add a /qr + webhook flow later; not needed for the demo.
"""

import uuid

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..schemas import PaymentCreate, PaymentOut, TableOut
from ..ws import manager

router = APIRouter(tags=["payments"])


@router.post("/payments/{order_id}", response_model=PaymentOut, status_code=201)
async def pay_order(order_id: int, payload: PaymentCreate) -> PaymentOut:
    table_update: TableOut | None = None
    with get_conn() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if order is None:
            raise HTTPException(404, f"Order {order_id} not found")
        # Idempotent: a double-tap reuses the existing PAID row instead of recording twice.
        pay = conn.execute(
            "SELECT * FROM payments WHERE order_id = ? AND status = 'PAID' "
            "ORDER BY id DESC LIMIT 1",
            (order_id,),
        ).fetchone()
        if pay is None:
            txn_ref = f"AIW{order_id}-{uuid.uuid4().hex[:8]}"
            cur = conn.execute(
                "INSERT INTO payments (order_id, method, amount, status, txn_ref, paid_at) "
                "VALUES (?, ?, ?, 'PAID', ?, datetime('now'))",
                (order_id, payload.method, order["total"], txn_ref),
            )
            pay = conn.execute(
                "SELECT * FROM payments WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        # Mark the table paid; the panel shows "đã thanh toán" and offers "Kết thúc bàn" → TRONG.
        conn.execute(
            'UPDATE "tables" SET status = ? WHERE id = ?',
            ("DA_THANH_TOAN", order["table_id"]),
        )
        trow = conn.execute(
            'SELECT * FROM "tables" WHERE id = ?', (order["table_id"],)
        ).fetchone()
        if trow:
            table_update = TableOut(**dict(trow))
    if table_update is not None:
        await manager.broadcast(
            "panel", {"type": "table.updated", "table": table_update.model_dump()}
        )
    return PaymentOut(**dict(pay))
