from langchain_core.tools import tool
from ai_waiter_core.schemas.payment import VerifyPaymentResponse
from ai_waiter_core.services.restaurant_db import RestaurantDB
from ai_waiter_core.utils import trace_latency

db = RestaurantDB()


@tool(response_format="content_and_artifact")
@trace_latency("Verify Payment Tool", run_type="tool")
def verify_payment(table_id: str) -> VerifyPaymentResponse:
    """
    Confirms payment for the active session at the given table.
    Marks payment as COMPLETED and closes the session.

    table_id: The table ID (e.g., 'T1')
    """
    try:
        session = db.get_active_session(table_id)
        if not session:
            result = VerifyPaymentResponse(
                status="error",
                table_id=table_id,
                message="Không tìm thấy phiên phục vụ nào cho bàn này."
            )
            return (result.message, result)

        session_id = session["id"]
        payment = db.get_payment(session_id)
        if not payment:
            result = VerifyPaymentResponse(
                status="error",
                table_id=table_id,
                message="Chưa có yêu cầu thanh toán cho phiên này."
            )
            return (result.message, result)

        if payment["status"] == "COMPLETED":
            result = VerifyPaymentResponse(
                status="success",
                table_id=table_id,
                message="Thanh toán thành công! Cảm ơn quý khách."
            )
            return (result.message, result)

        success = db.update_payment_status(session_id, "COMPLETED")
        if not success:
            result = VerifyPaymentResponse(
                status="error",
                table_id=table_id,
                message="Không thể xác nhận thanh toán."
            )
            return (result.message, result)

        result = VerifyPaymentResponse(
            status="success",
            table_id=table_id,
            message="Thanh toán thành công! Cảm ơn quý khách."
        )
        return (result.message, result)
    except Exception as e:
        result = VerifyPaymentResponse(
            status="error",
            table_id=table_id,
            message=f"Lỗi xác nhận thanh toán: {str(e)}"
        )
        return (result.message, result)
