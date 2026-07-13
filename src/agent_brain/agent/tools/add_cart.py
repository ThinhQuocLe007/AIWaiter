from typing import List
from langchain_core.tools import tool
from src.agent_brain.schemas.order import CartAddItem, CartAddResponse, OrderItem
from src.agent_brain.utils import MenuManager, trace_latency

menu_manager = MenuManager()


@tool(response_format="content_and_artifact")
@trace_latency("Add Cart Tool", run_type="tool")
def add_cart(items: List[CartAddItem]) -> CartAddResponse:
    """
    Add items to the cart. Only pass the NEW items being added — the system
    merges them with whatever is already in the cart. Use this for:
    - First-time ordering  ("Cho 2 Ốc Hương")
    - Adding more items   ("Thêm Lẩu Thái nữa")
    - Changing quantity   ("Lẩu cho 2 phần" — pass the item again)
    - Replacing an item   (pass replacement name)

    Pass item names **exactly as the customer says them** — the system resolves
    to official menu names and handles ambiguous/off-menu items automatically.
    """
    total_price = 0.0
    order_items = []
    for item in items:
        price = menu_manager.get_price(item.name)
        if price:
            total_price += price * item.quantity
        order_items.append(OrderItem(
            name=item.name,
            quantity=item.quantity,
            unit_price=price if price else None,
            special_requests=item.special_requests,
            is_valid=True,
        ))

    result = CartAddResponse(
        status="success",
        items=order_items,
        total_price=total_price,
        message=f"Đã thêm {len(items)} món, tạm tính {total_price:,}₫.",
    )
    return (result.message, result)
