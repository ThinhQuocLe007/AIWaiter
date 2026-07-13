import logging
from typing import Dict, Any, Callable

from src.agent_brain.agent.state import AgentState
from src.agent_brain.agent.actions import ui_action_for_tool
from src.agent_brain.schemas.order import Cart
from src.agent_brain.utils import MenuManager

logger = logging.getLogger(__name__)

menu_manager = MenuManager()


def _recalc_cart(cart: Cart) -> Cart:
    """Recalculate total_price and per-item unit_price from MenuManager."""
    cart.total_price = 0.0
    for item in cart.items:
        price = menu_manager.get_price(item.name)
        if price:
            item.unit_price = price
            cart.total_price += price * item.quantity
        elif item.unit_price:
            cart.total_price += item.unit_price * item.quantity
    return cart


def _handle_add_cart_result(state: AgentState, tool_result) -> Dict[str, Any]:
    """Merge new items into existing cart (ADD semantics)."""
    existing = state.get("active_cart")
    if existing is None or not existing.items:
        cart = Cart(items=list(tool_result.items), total_price=tool_result.total_price)
    else:
        cart = Cart(items=list(existing.items), total_price=existing.total_price)
        for new_item in tool_result.items:
            match = next((i for i in cart.items if i.name == new_item.name), None)
            if match:
                match.quantity += new_item.quantity
                if new_item.special_requests:
                    match.special_requests = new_item.special_requests
            else:
                cart.items.append(new_item)
        cart = _recalc_cart(cart)

    return {
        "active_cart": cart,
        "order_stage": "AWAITING_CONFIRMATION" if cart.items else "IDLE",
    }


def _handle_remove_cart_result(state: AgentState, tool_result) -> Dict[str, Any]:
    """Remove item by name from existing cart."""
    existing = state.get("active_cart")
    if existing is None:
        return {"active_cart": Cart(), "order_stage": "IDLE"}

    removed_name = tool_result.removed
    cart = Cart(
        items=[i for i in existing.items if i.name != removed_name],
        total_price=existing.total_price,
    )
    cart = _recalc_cart(cart)
    return {
        "active_cart": cart,
        "order_stage": "AWAITING_CONFIRMATION" if cart.items else "IDLE",
    }


def _handle_clear_cart_result(state: AgentState, tool_result) -> Dict[str, Any]:
    return {"active_cart": Cart(), "order_stage": "IDLE"}


def _handle_confirm_order_result(state: AgentState, tool_result) -> Dict[str, Any]:
    return {"order_stage": "CONFIRMED"}


def _handle_search_result(state: AgentState, tool_result) -> Dict[str, Any]:
    return {"search_context": tool_result.results}


TOOL_STATE_HANDLERS: Dict[str, Callable] = {
    "add_cart": _handle_add_cart_result,
    "remove_cart": _handle_remove_cart_result,
    "clear_cart": _handle_clear_cart_result,
    "confirm_order": _handle_confirm_order_result,
    "search": _handle_search_result,
}


def update_state_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts tool results and updates AgentState, manages intent queue.

    Processes ALL ToolMessages from the current turn (not just the last
    one) — when the worker emits multiple tool calls in one message, the
    ToolNode produces multiple ToolMessages. Each must be handled so the
    cart reflects the full set of operations.
    """
    result = {}
    current_state = dict(state)

    # Collect all ToolMessages from the current turn in chronological order.
    messages = state["messages"]
    tool_messages = []
    for m in reversed(messages):
        if hasattr(m, "type") and m.type == "tool":
            tool_messages.insert(0, m)
        else:
            break

    for msg in tool_messages:
        tool_name = getattr(msg, "name", "")
        tool_result = getattr(msg, "artifact", None)

        if tool_result is None:
            logger.warning("update_state_node: no artifact for tool %s", tool_name)
            continue

        status = getattr(tool_result, "status", None)
        if status != "success":
            continue

        handler = TOOL_STATE_HANDLERS.get(tool_name)
        if handler:
            handler_update = handler(current_state, tool_result)
            result.update(handler_update)
            current_state.update(handler_update)
        else:
            logger.debug("No state handler for tool: %s", tool_name)

        ui_action = ui_action_for_tool(tool_name)
        if ui_action:
            result["ui_action"] = ui_action

    intents = state.get("current_intents") or []
    if intents:
        result["current_intents"] = intents[1:]

    return result
