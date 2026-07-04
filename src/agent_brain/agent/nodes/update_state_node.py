import logging
from typing import Dict, Any, Callable

from src.agent_brain.agent.state import AgentState
from src.agent_brain.agent.actions import ui_action_for_tool
from src.agent_brain.schemas.order import Cart

logger = logging.getLogger(__name__)


def _handle_sync_cart_result(tool_result, state: AgentState) -> Dict[str, Any]:
    """Handle successful sync_cart tool result."""
    has_items = bool(tool_result.items)

    if not has_items:
        prev_cart = state.get("active_cart")
        stripped = bool(state.get("unavailable_items") or state.get("ambiguous_items"))
        if prev_cart and prev_cart.items and stripped:
            # The list came back empty ONLY because the validator stripped every requested
            # item (off-menu / ambiguous) — the LLM had sent just the new invalid item
            # instead of the full cart. Wiping here would destroy the guest's confirmed
            # draft (the "chào ủi wipes 445k" bug). Keep the cart and the stage untouched;
            # the response node still tells the guest the item isn't on the menu.
            return {}
        # Genuinely empty (guest cancelled: sync_cart([])) — stay IDLE instead of asking
        # the customer to confirm an empty order.
        return {
            "active_cart": Cart(items=[], total_price=0.0),
            "order_stage": "IDLE",
        }

    return {
        "active_cart": Cart(
            items=tool_result.items,
            total_price=tool_result.total_price
        ),
        "order_stage": "AWAITING_CONFIRMATION",
    }


def _handle_confirm_order_result(tool_result, state: AgentState) -> Dict[str, Any]:
    """Handle successful confirm_order tool result."""
    # order_confirmed is the per-turn "the order was JUST sent to the kitchen" signal the
    # tablet needs (order_stage stays CONFIRMED on later turns, so it can't carry that).
    return {"order_stage": "CONFIRMED", "order_confirmed": True}


def _handle_search_result(tool_result, state: AgentState) -> Dict[str, Any]:
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
                    result.update(handler(tool_result, state))
                else:
                    logger.debug(f"No state handler for tool: {tool_name}")
                # A successful tool is the agent's cue to also act on the tablet (open the
                # menu / the bill). Decided here where the tool name is known; delivered later
                # by the bridge. Last write wins for multi-intent turns (most recent action).
                ui_action = ui_action_for_tool(tool_name)
                if ui_action:
                    result["ui_action"] = ui_action

    intents = state.get("current_intents") or []
    if intents:
        result["current_intents"] = intents[1:]

    return result
