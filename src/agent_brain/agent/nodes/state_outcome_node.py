"""state_outcome_node — builds a typed ResponseContext from each turn's state.

Runs once per turn at the end of every path (tool, retry, chat). Pure function:
no LLM call, no side effects. Returns a dict for LangGraph state update including
per-turn resets so fields don't leak to the next turn.
"""

from typing import Dict, Any
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage

from src.agent_brain.agent.state import AgentState
from src.agent_brain.utils import last_user_text
from src.agent_brain.schemas import (
    ResponseContext,
    OrderResponseContext,
    SearchResponseContext,
    PaymentResponseContext,
    ChatResponseContext,
    RetryResponseContext,
    OffMenuItem,
    AmbiguousItem,
)
from src.agent_brain.schemas.order import Cart


def _vnd(amount) -> str:
    return f"{int(amount):,}".replace(",", ".")


def _last_tool_call_args(state: AgentState) -> Dict[str, Any]:
    if len(state["messages"]) < 2:
        return {}
    prev = state["messages"][-2]
    if not isinstance(prev, AIMessage) or not prev.tool_calls:
        return {}
    tc = prev.tool_calls[0]
    if isinstance(tc, dict):
        return tc.get("args", {}) or {}
    return getattr(tc, "args", {}) or {}


def _status_and_error(artifact) -> tuple:
    if artifact is None:
        return "error", ""
    return getattr(artifact, "status", "error"), getattr(artifact, "message", "") or ""


# ── Per-tool context builders ───────────────────────────────────────────────
def _build_add_cart(artifact, state, total_vnd, stage, ui, tool_args) -> OrderResponseContext:
    status, error_msg = _status_and_error(artifact)
    cart = state.get("active_cart")
    off_menu = [
        OffMenuItem(name=u["name"], suggestion=u.get("suggestion"))
        for u in (state.get("unavailable_items") or [])
    ]
    ambiguous = [
        AmbiguousItem(name=a["name"], candidates=a.get("candidates", []))
        for a in (state.get("ambiguous_items") or [])
    ]
    return OrderResponseContext(
        tool="add_cart", status=status, cart=cart.items if cart else [],
        total_vnd=total_vnd, off_menu=off_menu, ambiguous=ambiguous,
        stage=stage, ui_action=ui,
        error_message=error_msg if status == "error" else None,
    )


def _build_remove_cart(artifact, state, total_vnd, stage, ui, tool_args) -> OrderResponseContext:
    status, error_msg = _status_and_error(artifact)
    cart = state.get("active_cart")
    return OrderResponseContext(
        tool="remove_cart", status=status, cart=cart.items if cart else [],
        total_vnd=total_vnd, stage=stage, ui_action=ui,
        error_message=error_msg if status == "error" else None,
    )


def _build_clear_cart(artifact, state, ui) -> OrderResponseContext:
    status, error_msg = _status_and_error(artifact)
    return OrderResponseContext(
        tool="clear_cart", status=status, cart=[], total_vnd="0",
        stage="IDLE", ui_action=ui,
        error_message=error_msg if status == "error" else None,
    )


def _build_confirm_order(artifact, state, total_vnd, ui, tool_args) -> OrderResponseContext:
    status, error_msg = _status_and_error(artifact)
    cart = state.get("active_cart")
    stage = "CONFIRMED" if status == "success" else state.get("order_stage", "IDLE")
    return OrderResponseContext(
        tool="confirm_order", status=status, cart=cart.items if cart else [],
        total_vnd=total_vnd, order_id=getattr(artifact, "order_id", None) if status == "success" else None,
        stage=stage, ui_action=None,
        error_message=error_msg if status == "error" else None,
    )


def _build_search(artifact, state, ui, tool_args) -> SearchResponseContext:
    status, error_msg = _status_and_error(artifact)
    return SearchResponseContext(
        tool="search", status=status, query=tool_args.get("query", ""),
        results=getattr(artifact, "results", []) or [], ui_action=ui,
        error_message=error_msg if status == "error" else None,
    )


def _build_request_payment(artifact, state, ui, tool_args) -> PaymentResponseContext:
    status, error_msg = _status_and_error(artifact)
    amount = getattr(artifact, "amount", None) if artifact else None
    return PaymentResponseContext(
        tool="request_payment", status=status,
        amount_vnd=_vnd(amount) if amount else None,
        qr_url=getattr(artifact, "qr_url", None) if artifact else None,
        table_id=state.get("table_id", "T1"), ui_action=ui,
        error_message=error_msg if status == "error" else None,
    )


def _build_verify_payment(artifact, state, ui, tool_args) -> PaymentResponseContext:
    status, error_msg = _status_and_error(artifact)
    return PaymentResponseContext(
        tool="verify_payment", status=status, table_id=state.get("table_id", "T1"),
        ui_action=ui, error_message=error_msg if status == "error" else None,
    )


# Tool-name → builder lookup
_BUILDERS = {
    "add_cart":          _build_add_cart,
    "remove_cart":       _build_remove_cart,
    "clear_cart":        _build_clear_cart,
    "confirm_order":     _build_confirm_order,
    "search":            _build_search,
    "request_payment":   _build_request_payment,
    "verify_payment":    _build_verify_payment,
}


# ── Dispatcher ──────────────────────────────────────────────────────────────
def _build_from_tool_message(last: ToolMessage, state: AgentState) -> ResponseContext:
    builder = _BUILDERS.get(last.name)
    if builder is not None:
        ui = state.get("ui_action")
        artifact = getattr(last, "artifact", None)
        cart = state.get("active_cart")
        total_vnd = _vnd(cart.total_price) if cart else "0"
        stage = state.get("order_stage", "IDLE")
        tool_args = _last_tool_call_args(state)
        return builder(artifact, state, total_vnd, stage, ui, tool_args)

    # Unknown tool — degrade to chat context so the rewriter always has a reply.
    return ChatResponseContext(
        intent="CHAT", user_message=last_user_text(state),
        active_cart=state.get("active_cart") or Cart(),
        order_stage=state.get("order_stage", "IDLE"),
        chat_history=list(state.get("messages") or []),
    )


def _is_retry_state(state: AgentState) -> bool:
    return state.get("is_valid") is False and bool(state.get("feedback"))


def _build_retry_context(state: AgentState) -> RetryResponseContext:
    return RetryResponseContext(
        tool=state.get("last_tool") or "unknown",
        feedback=state.get("feedback", "") or "",
        intent="ORDER",
    )


# ── Finalize + public entry point ───────────────────────────────────────────
def _finalize(ctx: ResponseContext) -> Dict[str, Any]:
    """Attach the new context + reset per-turn state to prevent context leakage."""
    updates = {
        "response_context": ctx,
        "unavailable_items": None,
        "ambiguous_items": None,
        "feedback": None,
        "last_tool": None,
    }
    if getattr(ctx, "kind", None) == "PAYMENT":
        updates["search_context"] = None
    return updates


def state_outcome_node(state: AgentState) -> Dict[str, Any]:
    # CHAT path: chat_worker already set the context — just finalize.
    existing = state.get("response_context")
    if existing is not None:
        return _finalize(existing)

    last = state["messages"][-1]

    if _is_retry_state(state):
        return _finalize(_build_retry_context(state))

    if isinstance(last, ToolMessage):
        return _finalize(_build_from_tool_message(last, state))

    # Defensive fallback — should be unreachable.
    return _finalize(ChatResponseContext(
        intent="CHAT", user_message=last_user_text(state),
        active_cart=state.get("active_cart") or Cart(),
        order_stage=state.get("order_stage", "IDLE"),
        chat_history=list(state.get("messages") or []),
    ))
