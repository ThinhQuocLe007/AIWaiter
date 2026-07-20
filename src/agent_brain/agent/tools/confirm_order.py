
import httpx
from langchain_core.tools import tool

from src.agent_brain.schemas.order import ConfirmOrderResponse, OrderItem
from src.agent_brain.services.orchestrator_client import OrchestratorClient
from src.agent_brain.utils import MenuManager, trace_latency

client = OrchestratorClient()
menu_manager = MenuManager()


@tool(response_format="content_and_artifact")
@trace_latency("Order Confirmation Tool", run_type="tool")
def confirm_order(table_id: str, items: list[OrderItem]) -> ConfirmOrderResponse:
    """
    Finalizes and saves the order to the database under the active session.
    ONLY call this after the user has explicitly agreed to the final summary.

    table_id: The table ID (e.g., 'T1')
    items: The final list of items in the customer's cart.
    """
    try:
        item_payloads = []
        for item in items:
            price = menu_manager.get_price(item.name)
            if price == 0.0:
                missing = ConfirmOrderResponse(
                    status="error",
                    order_id=None,
                    message=(
                        f"Không tìm thấy món '{item.name}' trong thực đơn."
                        f" Vui lòng kiểm tra lại tên món."
                    ),
                )
                return (missing.message, missing)
            item_payloads.append({
                "name": item.name,
                "qty": item.quantity,
                "price": price,
                "note": item.special_requests,
            })
        order = client.create_order(table_id, item_payloads)
        result = ConfirmOrderResponse(
            status="success",
            order_id=order["id"],
            message=f"Đã xác nhận đơn hàng #{order['id']} cho bàn {table_id}.",
        )
        return (result.message, result)
    except httpx.HTTPError as e:
        result = ConfirmOrderResponse(
            status="error",
            message=f"Lỗi xử lý đơn hàng: {str(e)}",
        )
        return (result.message, result)
