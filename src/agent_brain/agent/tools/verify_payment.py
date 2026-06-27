import httpx
from langchain_core.tools import tool
from src.agent_brain.schemas.payment import VerifyPaymentResponse
from src.agent_brain.services.orchestrator_client import OrchestratorClient
from src.agent_brain.utils import trace_latency

client = OrchestratorClient()


@tool(response_format="content_and_artifact")
@trace_latency("Verify Payment Tool", run_type="tool")
def verify_payment(table_id: str) -> VerifyPaymentResponse:
    """
    Confirms payment for the active session at the given table.
    Marks payment as PAID and closes the session.

    table_id: The table ID (e.g., 'T1')
    """
    try:
        pay = client.verify_payment(table_id)
        if pay["status"] == "PAID":
            result = VerifyPaymentResponse(
                status="success",
                table_id=table_id,
                message="Thanh toán thành công! Cảm ơn quý khách.",
            )
        else:
            result = VerifyPaymentResponse(
                status="error",
                table_id=table_id,
                message="Không thể xác nhận thanh toán.",
            )
        return (result.message, result)
    except httpx.HTTPStatusError as e:
        # 404 = no payment was ever requested for this table.
        msg = (
            "Chưa có yêu cầu thanh toán cho phiên này."
            if e.response.status_code == 404
            else f"Lỗi xác nhận thanh toán: {e}"
        )
        result = VerifyPaymentResponse(status="error", table_id=table_id, message=msg)
        return (result.message, result)
    except Exception as e:
        result = VerifyPaymentResponse(
            status="error",
            table_id=table_id,
            message=f"Lỗi xác nhận thanh toán: {str(e)}",
        )
        return (result.message, result)
