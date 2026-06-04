from langchain_core.tools import tool
from ai_waiter_core.schemas.payment import PaymentResponse
from ai_waiter_core.services.payment_mgr import PaymentManager
from ai_waiter_core.utils import trace_latency

payment_provider = PaymentManager()


@tool
@trace_latency("Payment Request Tool", run_type="tool")
def request_payment(table_id: str, amount: float) -> PaymentResponse:
    """
    Generates a payment QR code link for the customer.
    
    table_id: The ID of the table (e.g., 'T1', 'T5')
    amount: The total amount to be paid in VND
    """
    try:
        if amount <= 0:
            return PaymentResponse(
                status="error",
                message="Số tiền thanh toán phải lớn hơn 0."
            )

        qr_url = payment_provider.generate_qr_payload(table_id, amount)

        return PaymentResponse(
            status="success",
            qr_url=qr_url,
            amount=int(amount),
            message=f"Vui lòng quét mã QR để thanh toán {int(amount):,} VND."
        )
    except Exception as e:
        return PaymentResponse(
            status="error",
            message=f"Lỗi tạo mã thanh toán: {str(e)}"
        )
