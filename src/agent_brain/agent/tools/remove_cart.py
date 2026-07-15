from langchain_core.tools import tool

from src.agent_brain.schemas.order import CartRemoveResponse
from src.agent_brain.utils import MenuManager, trace_latency

menu_manager = MenuManager()


@tool(response_format="content_and_artifact")
@trace_latency("Remove Cart Tool", run_type="tool")
def remove_cart(name: str) -> CartRemoveResponse:
    """
    Remove an item from the cart by its name. Use this when the customer
    says "bỏ bia đi", "không lấy mực nữa", "xóa món X", etc.
    """
    result = CartRemoveResponse(
        status="success",
        removed=name,
        total_price=0.0,
        message=f"Đã bỏ món '{name}' khỏi giỏ hàng.",
    )
    return (result.message, result)
