from typing import List
from langchain_core.tools import tool
from ai_waiter_core.schemas.order import OrderItem, ConfirmOrderResponse
from ai_waiter_core.services.restaurant_db import RestaurantDB
from ai_waiter_core.utils import MenuManager, trace_latency

db = RestaurantDB()
menu_manager = MenuManager()


@tool(response_format="content_and_artifact")
@trace_latency("Order Confirmation Tool", run_type="tool")
def confirm_order(table_id: str, items: List[OrderItem]) -> ConfirmOrderResponse:
    """
    Finalizes and saves the order to the database under the active session.
    ONLY call this after the user has explicitly agreed to the final summary.

    table_id: The table ID (e.g., 'T1')
    items: The final list of items in the customer's cart.
    """
    try:
        session = db.get_active_session(table_id)
        if not session:
            session_id = db.create_session(table_id)
            if not session_id:
                result = ConfirmOrderResponse(
                    status="error",
                    message="Lỗi tạo phiên phục vụ."
                )
                return (result.message, result)
        else:
            session_id = session["id"]

        order_id = db.create_order(session_id)
        if not order_id:
            result = ConfirmOrderResponse(
                status="error",
                message="Lỗi tạo đơn hàng."
            )
            return (result.message, result)

        item_dicts = []
        for item in items:
            unit_price = menu_manager.get_price(item.name)
            item_dicts.append({
                "name": item.name,
                "quantity": item.quantity,
                "unit_price": unit_price,
                "special_requests": item.special_requests
            })

        db.add_items_to_order(order_id, item_dicts)

        result = ConfirmOrderResponse(
            status="success",
            order_id=order_id,
            message=f"Đã xác nhận đơn hàng #{order_id} cho bàn {table_id}."
        )
        return (result.message, result)
    except Exception as e:
        result = ConfirmOrderResponse(
            status="error",
            message=f"Lỗi xử lý đơn hàng: {str(e)}"
        )
        return (result.message, result)
