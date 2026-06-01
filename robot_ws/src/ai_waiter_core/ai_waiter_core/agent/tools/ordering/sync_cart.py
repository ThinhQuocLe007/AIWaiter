from typing import List
from langchain_core.tools import tool
from ai_waiter_core.schemas.order import OrderItem, Cart
from ai_waiter_core.utils import MenuManager, trace_latency


# Initialize the Menu Manager for price lookup
menu_manager = MenuManager()

@tool
@trace_latency("Sync Cart Tool", run_type="tool")
def sync_cart(items: List[OrderItem]) -> str:
    """
    Synchronizes the active cart with the provided items.
    Use this to draft or update the cart. ALWAYS pass the ENTIRE updated list of items.
    """
    total_price = 0.0
    for item in items:
        price = menu_manager.get_price(item.name)
        if price:
            total_price += price * item.quantity
            
    cart = Cart(items=items, total_price=total_price)
    
    # Return the parsed cart as a JSON string flag.
    # The LangGraph will intercept this flag and update state["active_cart"] cleanly.
    return f"SYNC_CART_SUCCESS: {cart.model_dump_json()}"
