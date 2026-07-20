import logging
from collections.abc import Callable
from typing import Any

from src.agent_brain.agent.actions import ui_action_for_tool
from src.agent_brain.agent.state import AgentState
from src.agent_brain.schemas.order import Cart, OrderItem
from src.agent_brain.utils import MenuManager

logger = logging.getLogger(__name__)

menu_manager = MenuManager()


def recalc_cart(cart: Cart) -> Cart:
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


def _handle_add_cart_result(state: AgentState, tool_result) -> dict[str, Any]:
    """Merge new items into existing cart.

    - Item NOT in cart → append.
    - Item in cart + user said "thêm"/"nữa" → additive merge.
    - Item in cart + no additive markers → replace quantity (re-specification).
    """
    from src.agent_brain.utils.state_helpers import last_user_text

    _ADDITIVE = ("thêm", "nữa", "lấy thêm", "gọi thêm", "cho thêm")
    user_text = last_user_text(state).lower()
    additive = any(m in user_text for m in _ADDITIVE)

    existing = state.get("active_cart")
    if existing is None or not existing.items:
        cart = Cart(items=list(tool_result.items), total_price=tool_result.total_price)
    else:
        cart = Cart(items=list(existing.items), total_price=existing.total_price)
        for new_item in tool_result.items:
            match = next((i for i in cart.items if i.name == new_item.name), None)
            if match:
                if additive:
                    match.quantity += new_item.quantity
                else:
                    match.quantity = new_item.quantity
                if new_item.special_requests:
                    match.special_requests = new_item.special_requests
            else:
                cart.items.append(new_item)
        cart = recalc_cart(cart)

    return {
        "active_cart": cart,
        "order_stage": "AWAITING_CONFIRMATION" if cart.items else "IDLE",
    }


def _handle_remove_cart_result(state: AgentState, tool_result) -> dict[str, Any]:
    """Remove an item from the cart — either whole, or just some of its portions.

    ``quantity`` None means "bỏ hẳn món đó" (the original all-or-nothing behaviour). A number
    means the customer only wanted some portions off ("xóa một phần lẩu thái") — dropping the
    whole line there would take the other portions with it, which is exactly what used to happen
    when the tool had no way to say how many.
    """
    existing = state.get("active_cart")
    if existing is None:
        return {"active_cart": Cart(), "order_stage": "IDLE"}

    removed_name = tool_result.removed
    remove_qty = getattr(tool_result, "quantity", None)

    items: list[OrderItem] = []
    for item in existing.items:
        if item.name != removed_name:
            items.append(item)
            continue
        # The matching line: keep what's left over, or drop it entirely.
        if remove_qty is not None and remove_qty < item.quantity:
            items.append(item.model_copy(update={"quantity": item.quantity - remove_qty}))

    cart = recalc_cart(Cart(items=items, total_price=existing.total_price))
    return {
        "active_cart": cart,
        "order_stage": "AWAITING_CONFIRMATION" if cart.items else "IDLE",
    }


def _handle_clear_cart_result(state: AgentState, tool_result) -> dict[str, Any]:
    return {"active_cart": Cart(), "order_stage": "IDLE", "shown_dishes": None}


def _handle_confirm_order_result(state: AgentState, tool_result) -> dict[str, Any]:
    return {"order_stage": "CONFIRMED"}


def _handle_search_result(state: AgentState, tool_result) -> dict[str, Any]:
    existing = state.get("shown_dishes") or []
    new_names = [
        r.document.metadata.get("name")
        for r in tool_result.results
        if r.document.metadata.get("name")
    ]
    return {
        "search_context": tool_result.results,
        "shown_dishes": list(dict.fromkeys(existing + new_names)),
    }


# Tools whose success actually changes the cart contents. Drives the per-turn ``cart_touched``
# flag the tablet gates its cart mirroring on — see AgentState.cart_touched. confirm_order is
# deliberately absent: it moves the cart to the kitchen, and the tablet follows its own
# ``order_confirmed`` flag for that.
CART_MUTATING_TOOLS = ("add_cart", "remove_cart", "clear_cart")


TOOL_STATE_HANDLERS: dict[str, Callable] = {
    "add_cart": _handle_add_cart_result,
    "remove_cart": _handle_remove_cart_result,
    "clear_cart": _handle_clear_cart_result,
    "confirm_order": _handle_confirm_order_result,
    "search": _handle_search_result,
}


def update_state_node(state: AgentState) -> dict[str, Any]:
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
            if tool_name in CART_MUTATING_TOOLS:
                result["cart_touched"] = True
        else:
            logger.debug("No state handler for tool: %s", tool_name)

        ui_action = ui_action_for_tool(tool_name)
        if ui_action:
            result["ui_action"] = ui_action

    intents = state.get("current_intents") or []
    if intents:
        result["current_intents"] = intents[1:]

    return result
