from langchain_core.tools import tool

from src.agent_brain.schemas.order import CartClearResponse
from src.agent_brain.utils import trace_latency


@tool(response_format="content_and_artifact")
@trace_latency("Clear Cart Tool", run_type="tool")
def clear_cart() -> CartClearResponse:
    """
    Empty the ENTIRE cart. Only for an explicit, unambiguous cancellation:
    "hủy đơn", "không đặt nữa", "cho đặt lại từ đầu", "xóa hết đơn đi".

    Do NOT use for a bare hesitation particle. "thôi", "à mà thôi", "khoan đã",
    "từ từ", "để tính sau" mean the guest is pausing, not cancelling — call
    delegate for those. Clearing a cart the guest still wants is not recoverable.
    """
    result = CartClearResponse(
        status="success",
        message="Đã hủy toàn bộ đơn hàng.",
    )
    return (result.message, result)
