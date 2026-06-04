from typing import List
from langchain_core.tools import tool
from ai_waiter_core.schemas.order import OrderItem, ConfirmOrderResponse
from ai_waiter_core.services.order_db import OrderDB
from ai_waiter_core.utils import MenuManager, trace_latency

db_manager = OrderDB()
menu_manager = MenuManager()

@tool
@trace_latency("Order Confirmation Tool", run_type="tool")
def confirm_order(table_id: str, items: List[OrderItem]) -> ConfirmOrderResponse:
    """
    Finalizes and saves the order to the database. 
    ONLY call this after the user has explicitly agreed to the final summary.
    
    table_id: The table ID (e.g., 'T1')
    items: The final list of items in the customer's cart.
    """
    try:
        total_price = 0.0
        for item in items:
            price = menu_manager.get_price(item.name)
            if price:
                total_price += price * item.quantity

        cart_data = {
            "items": [item.model_dump() for item in items],
            "total_price": total_price
        }

        order_id = db_manager.add_order(table_id, cart_data)

        if order_id:
            return ConfirmOrderResponse(
                status="success",
                order_id=order_id,
                message=f"Đã xác nhận đơn hàng #{order_id} cho bàn {table_id}."
            )
        else:
            return ConfirmOrderResponse(
                status="error",
                message="Lỗi cơ sở dữ liệu khi lưu đơn hàng."
            )
    except Exception as e:
        return ConfirmOrderResponse(
            status="error",
            message=f"Lỗi xử lý đơn hàng: {str(e)}"
        )
