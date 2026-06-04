from typing import List
from langchain_core.tools import tool
from ai_waiter_core.schemas.order import OrderItem, SyncCartResponse
from ai_waiter_core.utils import MenuManager, trace_latency

menu_manager = MenuManager()

@tool
@trace_latency("Sync Cart Tool", run_type="tool")
def sync_cart(items: List[OrderItem]) -> SyncCartResponse:
    """
    Synchronizes the active cart with the provided items.
    Use this to draft or update the cart. ALWAYS pass the ENTIRE updated list of items.
    """
    total_price = 0.0
    for item in items:
        price = menu_manager.get_price(item.name)
        if price:
            total_price += price * item.quantity

    return SyncCartResponse(
        status="success",
        items=items,
        total_price=total_price,
        message=f"Đã cập nhật {len(items)} món, tạm tính {total_price:,}₫."
    )
