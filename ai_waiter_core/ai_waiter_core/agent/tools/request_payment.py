from langchain_core.tools import tool
from ai_waiter_core.schemas.payment import PaymentRequest, PaymentResponse
from ai_waiter_core.services.payment_mgr import PaymentManager
from ai_waiter_core.services.restaurant_db import RestaurantDB
from ai_waiter_core.utils import trace_latency

payment_provider = PaymentManager()
db = RestaurantDB()


@tool(response_format="content_and_artifact", args_schema=PaymentRequest)
@trace_latency("Payment Request Tool", run_type="tool")
def request_payment(table_id: str) -> PaymentResponse:
    """
    Generates a payment QR code for the active session at the given table.
    Calculates the total from all unpaid orders. Auto-verifies after a few seconds (mock).

    table_id: The table ID (e.g., 'T1')
    """
    try:
        session = db.get_active_session(table_id)
        if not session:
            result = PaymentResponse(
                status="error",
                table_id=table_id,
                message="Không tìm thấy phiên phục vụ nào cho bàn này."
            )
            return (result.message, result)

        session_id = session["id"]
        orders = db.get_orders_by_session(session_id)
        if not orders:
            result = PaymentResponse(
                status="error",
                table_id=table_id,
                message="Không có đơn hàng nào trong phiên này."
            )
            return (result.message, result)

        total = sum(o["total_price"] for o in orders)

        qr_url = payment_provider.generate_qr_payload(session_id, total)
        payment_id = db.add_payment(session_id, total, qr_url)
        if not payment_id:
            result = PaymentResponse(
                status="error",
                table_id=table_id,
                message="Lỗi lưu thông tin thanh toán."
            )
            return (result.message, result)

        payment_provider.schedule_mock_verify(session_id)

        result = PaymentResponse(
            status="success",
            table_id=table_id,
            session_id=session_id,
            qr_url=qr_url,
            amount=int(total),
            message=f"Tổng tiền: {int(total):,} VND. Vui lòng quét mã QR để thanh toán."
        )
        return (result.message, result)
    except Exception as e:
        result = PaymentResponse(
            status="error",
            table_id=table_id,
            message=f"Lỗi tạo mã thanh toán: {str(e)}"
        )
        return (result.message, result)
