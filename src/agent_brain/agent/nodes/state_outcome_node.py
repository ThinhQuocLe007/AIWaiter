"""state_outcome_node — builds a typed ResponseContext from each turn's state.

Runs once per turn at the end of every path (tool, retry, chat). Pure function:
no LLM call, no side effects. Returns a dict for LangGraph state update including
per-turn resets so fields don't leak to the next turn.
"""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agent_brain.agent.state import AgentState
from src.agent_brain.schemas import (
    AmbiguousItem,
    ChatResponseContext,
    OffMenuItem,
    OrderResponseContext,
    PaymentResponseContext,
    ResponseContext,
    RetryResponseContext,
    SearchResponseContext,
)
from src.agent_brain.agent.nodes.chat_worker_node import _to_curated_memory
# One money formatter for the whole response path. There used to be a second `_vnd` defined
# right here that was identical EXCEPT it left the ₫ off — so `total_vnd` reached the templates
# bare while the per-item prices beside it carried the symbol, and the cart echo read
# "… 255.000₫/phần … Tổng tạm tính 255.000". The templates' comments already claimed the ₫ was
# applied here, which is what kept it unnoticed.
from src.agent_brain.agent.nodes.response_template import _vnd
from src.agent_brain.schemas.order import Cart
from src.agent_brain.utils import last_user_text


def _last_tool_call_args(state: AgentState) -> dict[str, Any]:
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


def _build_clear_cart(artifact, state, _total_vnd, _stage, ui, _tool_args) -> OrderResponseContext:
    status, error_msg = _status_and_error(artifact)
    return OrderResponseContext(
        tool="clear_cart", status=status, cart=[], total_vnd="0",
        stage="IDLE", ui_action=ui,
        error_message=error_msg if status == "error" else None,
    )


def _build_confirm_order(artifact, state, total_vnd, _stage, ui, tool_args) -> OrderResponseContext:
    status, error_msg = _status_and_error(artifact)
    cart = state.get("active_cart")
    stage = "CONFIRMED" if status == "success" else state.get("order_stage", "IDLE")
    return OrderResponseContext(
        tool="confirm_order", status=status, cart=cart.items if cart else [],
        total_vnd=total_vnd, order_id=getattr(artifact, "order_id", None) if status == "success" else None,
        stage=stage, ui_action=None,
        error_message=error_msg if status == "error" else None,
    )


def _build_search(artifact, state, _total_vnd, _stage, ui, tool_args) -> SearchResponseContext:
    status, error_msg = _status_and_error(artifact)
    return SearchResponseContext(
        tool="search", status=status, query=tool_args.get("query", ""),
        results=getattr(artifact, "results", []) or [],
        shown_dishes=state.get("shown_dishes") or [],
        ui_action=ui,
        error_message=error_msg if status == "error" else None,
    )


def _build_request_payment(artifact, state, _total_vnd, _stage, ui, tool_args) -> PaymentResponseContext:
    status, error_msg = _status_and_error(artifact)
    amount = getattr(artifact, "amount", None) if artifact else None
    return PaymentResponseContext(
        tool="request_payment", status=status,
        amount_vnd=_vnd(amount) if amount else None,
        qr_url=getattr(artifact, "qr_url", None) if artifact else None,
        table_id=state.get("table_id", "T1"), ui_action=ui,
        error_message=error_msg if status == "error" else None,
    )


def _build_verify_payment(artifact, state, _total_vnd, _stage, ui, _tool_args) -> PaymentResponseContext:
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


def _pick_tool_messages(state: AgentState) -> list:
    """Return every ToolMessage from the current turn in chronological order.

    Single-intent turns get one message; multi-intent turns (e.g. ORDER + SEARCH)
    get several, and the response node verbalises all of them so the guest hears
    every action that happened.
    """
    messages = state["messages"]
    tool_msgs: list = []
    for m in messages:
        if isinstance(m, ToolMessage):
            tool_msgs.append(m)

    if not tool_msgs:
        return []

    seen_since_last_user = []
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, ToolMessage):
            seen_since_last_user.append(m)

    return list(reversed(seen_since_last_user))


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
def _finalize(ctx: ResponseContext) -> dict[str, Any]:
    """Attach the new context + reset per-turn state to prevent context leakage."""
    updates = {
        "response_context": ctx,
        "unavailable_items": None,
        "ambiguous_items": None,
        "feedback": None,
        "last_tool": None,
        "delegate_reason": None,
        "intent_queries": None,
    }
    if getattr(ctx, "kind", None) == "PAYMENT":
        updates["search_context"] = None
    return updates


def state_outcome_node(state: AgentState) -> dict[str, Any]:
    existing = state.get("response_context")
    if existing is not None:
        return _finalize(existing)

    if _is_retry_state(state):
        return _finalize(_build_retry_context(state))

    tool_msgs = _pick_tool_messages(state)
    if tool_msgs:
        contexts = []
        for tm in tool_msgs:
            ctx = _build_from_tool_message(tm, state)
            if ctx is not None:
                contexts.append(ctx)
        if len(contexts) == 1:
            return _finalize(contexts[0])
        if contexts:
            return {
                **{k: None for k in ("unavailable_items", "ambiguous_items", "feedback",
                                      "last_tool", "delegate_reason", "intent_queries")},
                "response_context": contexts,
            }
        return _finalize(_build_retry_context(state))

    return _finalize(ChatResponseContext(
        intent="CHAT", user_message=last_user_text(state),
        active_cart=state.get("active_cart") or Cart(),
        order_stage=state.get("order_stage", "IDLE"),
        chat_history=list(state.get("messages") or []),
        curated_memory=_to_curated_memory(state.get("search_context")),
        delegate_reason=state.get("delegate_reason"),
    ))
