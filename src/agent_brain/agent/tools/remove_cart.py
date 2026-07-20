from langchain_core.tools import tool

from src.agent_brain.schemas.order import CartRemoveResponse
from src.agent_brain.utils import MenuManager, trace_latency

menu_manager = MenuManager()


@tool(response_format="content_and_artifact")
@trace_latency("Remove Cart Tool", run_type="tool")
def remove_cart(name: str, quantity: int | None = None) -> CartRemoveResponse:
    """
    Remove an item from the cart by its name.

    quantity = số phần cần bỏ. Bỏ TRỐNG khi khách muốn bỏ hẳn món đó:
      - "bỏ bia đi", "không lấy mực nữa", "xóa món X"   -> quantity=None (bỏ cả món)
      - "xóa một phần lẩu thái", "bớt 1 phần ốc hương"  -> quantity=1  (chỉ bớt 1 phần)
      - "bỏ bớt 2 phần lẩu thái"                         -> quantity=2

    Khách đang có 2 phần mà chỉ muốn bỏ 1 thì PHẢI truyền quantity=1, nếu không
    cả 2 phần sẽ bị xóa.
    """
    if quantity is None:
        message = f"Đã bỏ món '{name}' khỏi giỏ hàng."
    else:
        message = f"Đã bỏ {quantity} phần '{name}' khỏi giỏ hàng."
    result = CartRemoveResponse(
        status="success",
        removed=name,
        quantity=quantity,
        total_price=0.0,
        message=message,
    )
    return (result.message, result)
