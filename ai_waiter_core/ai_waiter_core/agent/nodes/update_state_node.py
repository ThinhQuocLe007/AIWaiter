import logging
from typing import Dict, Any, Callable

from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.schemas.order import Cart

logger = logging.getLogger(__name__)


def _handle_sync_cart_result(tool_result) -> Dict[str, Any]:
    """Handle successful sync_cart tool result."""
    # If every requested item was out-of-menu (stripped by the validator), the cart
    # is empty — stay IDLE instead of asking the customer to confirm an empty order.
    has_items = bool(tool_result.items)
    return {
        "active_cart": Cart(
            items=tool_result.items,
            total_price=tool_result.total_price
        ),
        "order_stage": "AWAITING_CONFIRMATION" if has_items else "IDLE",
    }


def _handle_confirm_order_result(tool_result) -> Dict[str, Any]:
    """Handle successful confirm_order tool result."""
    return {"order_stage": "CONFIRMED"}


def _handle_search_result(tool_result) -> Dict[str, Any]:
    """Handle successful search tool result."""
    return {"search_context": tool_result.results}


TOOL_STATE_HANDLERS: Dict[str, Callable] = {
    "sync_cart": _handle_sync_cart_result,
    "confirm_order": _handle_confirm_order_result,
    "search": _handle_search_result,
}


def update_state_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts tool results and updates AgentState, manages intent queue.
    
    Responsibilities:
    1. Parse tool artifacts and update relevant state fields
    2. Pop processed intent from the queue
    """
    last_msg = state["messages"][-1]
    result = {}

    if last_msg.type == "tool":
        tool_name = getattr(last_msg, "name", "")
        tool_result = getattr(last_msg, "artifact", None)
        
        if tool_result is None:
            logger.warning(f"update_state_node: no artifact found for tool {tool_name}")
        else:
            status = getattr(tool_result, "status", None)
            if status == "success":
                handler = TOOL_STATE_HANDLERS.get(tool_name)
                if handler:
                    result.update(handler(tool_result))
                else:
                    logger.debug(f"No state handler for tool: {tool_name}")

    intents = state.get("current_intents") or []
    if intents:
        result["current_intents"] = intents[1:]

    return result
