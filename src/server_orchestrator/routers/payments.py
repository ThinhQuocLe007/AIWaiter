"""Payments — mock confirmation, gộp theo phiên (session).

A party's whole visit pays ONCE: the bill is the sum of every order in the table's ACTIVE
session. No real money moves — the tablet shows a (mock) VietQR image and the guest taps "Đã
thanh toán xong".

Two steps, matching the session lifecycle:
  1. POST /payments {table_id}        → open a PENDING payment for the active session (amount =
                                         gộp total) and return the QR. Idempotent + refreshes the
                                         amount if more was ordered.
  2. POST /payments/{id}/verify       → mark PAID, CLOSE the session (the boundary), flip the
                                         table to DA_THANH_TOAN. Idempotent.
A real PSP (VietQR/MoMo/ZaloPay) would replace step 2 with a webhook; not needed for the demo.
"""

import uuid

from fastapi import APIRouter, HTTPException

from ..services import dispatcher
from ..data.db import get_conn
from ..schemas import PaymentCreate, PaymentOut, PaymentVerify, TableOut
from ..services.sessions import close_session, get_active_session, session_total
from ..realtime.connection_manager import manager

router = APIRouter(tags=["payments"])


def _vietqr_url(amount: float) -> str:
    return (
        "https://img.vietqr.io/image/ICB-123456789-qr_only.png"
        f"?amount={int(amount)}&addInfo=AI_Waiter_Payment"
    )


def _fetch_payment(conn, payment_id: int):
    return conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()


def _settle_payment(conn, pay):
    """Mark a payment PAID, close its session (the lifecycle boundary), free its table. Idempotent.

    Returns the updated table row to broadcast, or None (already settled / table gone).
    """
    if pay["status"] == "PAID":
        return None
    conn.execute(
        "UPDATE payments SET status = 'PAID', paid_at = datetime('now') WHERE id = ?",
        (pay["id"],),
    )
    # Closing the session is the boundary: the next guest at this table gets a fresh session
    # (and a fresh agent thread — Phase 4).
    close_session(conn, pay["session_id"])
    sess = conn.execute(
        "SELECT table_id FROM sessions WHERE id = ?", (pay["session_id"],)
    ).fetchone()
    if sess is None:
        return None
    conn.execute(
        'UPDATE "tables" SET status = ? WHERE id = ?', ("DA_THANH_TOAN", sess["table_id"])
    )
    return conn.execute(
        'SELECT * FROM "tables" WHERE id = ?', (sess["table_id"],)
    ).fetchone()


@router.post("/payments", response_model=PaymentOut, status_code=201)
def create_payment(payload: PaymentCreate) -> PaymentOut:
    """Open (or refresh) the gộp payment for a table's active session and return its QR."""
    with get_conn() as conn:
        sess = get_active_session(conn, payload.table_id)
        if sess is None:
            raise HTTPException(404, f"No active session for table {payload.table_id}")
        session_id = sess["id"]
        total = session_total(conn, session_id)

        existing = conn.execute(
            "SELECT * FROM payments WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if existing is not None and existing["status"] == "PAID":
            return PaymentOut(**dict(existing))  # already settled — return it unchanged

        qr_url = _vietqr_url(total)
        if existing is not None:  # a PENDING row — refresh amount/qr in case more was ordered
            conn.execute(
                "UPDATE payments SET amount = ?, qr_url = ?, method = ? WHERE id = ?",
                (total, qr_url, payload.method, existing["id"]),
            )
            pay = _fetch_payment(conn, existing["id"])
        else:
            txn_ref = f"AIW{session_id}-{uuid.uuid4().hex[:8]}"
            cur = conn.execute(
                "INSERT INTO payments (session_id, method, amount, status, txn_ref, qr_url) "
                "VALUES (?, ?, ?, 'PENDING', ?, ?)",
                (session_id, payload.method, total, txn_ref, qr_url),
            )
            pay = _fetch_payment(conn, cur.lastrowid)
    return PaymentOut(**dict(pay))


async def _broadcast_table(trow) -> None:
    if trow is not None:
        await manager.broadcast(
            "panel", {"type": "table.updated", "table": TableOut(**dict(trow)).model_dump()}
        )


@router.post("/payments/verify", response_model=PaymentOut)
async def verify_payment_by_table(payload: PaymentVerify) -> PaymentOut:
    """Confirm a table's payment (the agent's verify_payment knows only table_id). Settles the
    table's most recent payment regardless of session state, so a re-confirm is idempotent."""
    with get_conn() as conn:
        pay = conn.execute(
            "SELECT p.* FROM payments p JOIN sessions s ON p.session_id = s.id "
            "WHERE s.table_id = ? ORDER BY p.id DESC LIMIT 1",
            (payload.table_id,),
        ).fetchone()
        if pay is None:
            raise HTTPException(404, f"No payment for table {payload.table_id}")
        trow = _settle_payment(conn, pay)
        pay = _fetch_payment(conn, pay["id"])
    await _broadcast_table(trow)
    # Bill settled → the visit is over: clear the table's leftover tasks from the queue and send any
    # robot still parked there back to the dock.
    await dispatcher.cancel_table_tasks(payload.table_id)
    return PaymentOut(**dict(pay))


@router.post("/payments/{payment_id}/verify", response_model=PaymentOut)
async def verify_payment(payment_id: int) -> PaymentOut:
    """Confirm the (mock) payment by id: PAID + close the session + free the table. Idempotent."""
    with get_conn() as conn:
        pay = _fetch_payment(conn, payment_id)
        if pay is None:
            raise HTTPException(404, f"Payment {payment_id} not found")
        trow = _settle_payment(conn, pay)
        pay = _fetch_payment(conn, payment_id)
    await _broadcast_table(trow)
    if trow is not None:  # freshly settled — clear the table's tasks + send its robot home
        await dispatcher.cancel_table_tasks(trow["id"])
    return PaymentOut(**dict(pay))
