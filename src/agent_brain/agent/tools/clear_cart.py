from langchain_core.tools import tool
from src.agent_brain.schemas.order import CartClearResponse
from src.agent_brain.utils import trace_latency


@tool(response_format="content_and_artifact")
@trace_latency("Clear Cart Tool", run_type="tool")
def clear_cart() -> CartClearResponse:
    """
    Empty the entire cart. Use when the customer says "hủy đơn",
    "không đặt nữa", "thôi bỏ hết đi", "cho đặt lại từ đầu".
    """
    result = CartClearResponse(
        status="success",
        message="Đã hủy toàn bộ đơn hàng.",
    )
    return (result.message, result)
