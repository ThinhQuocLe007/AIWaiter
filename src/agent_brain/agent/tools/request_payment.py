import httpx
from langchain_core.tools import tool

from src.agent_brain.schemas.payment import PaymentRequest, PaymentResponse
from src.agent_brain.services.orchestrator_client import OrchestratorClient
from src.agent_brain.utils import trace_latency

client = OrchestratorClient()


@tool(response_format="content_and_artifact", args_schema=PaymentRequest)
@trace_latency("Payment Request Tool", run_type="tool")
def request_payment(table_id: str) -> PaymentResponse:
    """
    Generates a payment QR code for the active session at the given table.
    Calculates the gộp total across all orders in the session. The customer pays, then
    `verify_payment` confirms it.

    table_id: The table ID (e.g., 'T1')
    """
    try:
        pay = client.create_payment(table_id)
        total = pay.get("amount") or 0
        if total <= 0:
            result = PaymentResponse(
                status="error",
                table_id=table_id,
                message="Không có đơn hàng nào trong phiên này.",
            )
            return (result.message, result)

        result = PaymentResponse(
            status="success",
            table_id=table_id,
            session_id=pay["session_id"],
            qr_url=pay["qr_url"],
            amount=int(total),
            message=f"Tổng tiền: {int(total):,} VND. Vui lòng quét mã QR để thanh toán.",
        )
        return (result.message, result)
    except httpx.HTTPError as e:
        result = PaymentResponse(
            status="error",
            table_id=table_id,
            message=f"Lỗi tạo mã thanh toán: {str(e)}",
        )
        return (result.message, result)
