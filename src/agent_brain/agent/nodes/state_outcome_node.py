"""state_outcome_node — builds a typed ResponseContext from the current turn's state.

Pure function: no LLM call, no side effects. Runs once per turn, at the
end of every path (tool, retry, chat), to assemble the typed context
that response_node reads.

For the CHAT path, ``chat_worker`` has already set
``response_context``; this node just runs the per-turn reset. For the
tool path, it inspects ``messages[-1]`` (a ``ToolMessage``) and builds
the appropriate context. For the retry path, it builds a
``RetryResponseContext`` from the validator's feedback. As a defensive
fallback, it builds a ``ChatResponseContext``.

Always returns a dict suitable for LangGraph's state update, including
per-turn resets so fields don't leak to the next turn.
"""

from typing import Dict, Any
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage

from src.agent_brain.agent.state import AgentState
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


# --- Small text helpers ----------------------------------------------------

def _vnd(amount) -> str:
    """Format Vietnamese dong: 255000.0 -> '255.000' (no symbol).

    The symbol is added by the templates that consume the formatted
    string. Keeping the helper symbol-free lets callers decide where
    the '₫' goes.
    """
    return f"{int(amount):,}".replace(",", ".")


def last_user_text(state: AgentState) -> str:
    """Return the most recent HumanMessage content, or '' if none.

    Public so ``chat_worker_node`` (and future nodes) can reuse it
    without a second copy.
    """
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def _last_tool_call_args(state: AgentState) -> Dict[str, Any]:
    """Get the args of the most recent tool call (from messages[-2]).

    The previous AI message holds the tool call; the current ToolMessage
    holds the result. The args (e.g. the search query, the table_id)
    live with the call, not the result.
    """
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
    """Return (status, error_message) from an artifact, defaulting to error.

    The tool's artifact (a Pydantic model with ``status`` and
    ``message`` fields) is the source of truth. If the artifact is None
    (e.g. the tool raised before returning), we treat it as an error
    with an empty message.
    """
    if artifact is None:
        return "error", ""
    return getattr(artifact, "status", "error"), getattr(artifact, "message", "") or ""


# --- Per-tool builders ------------------------------------------------------

def _build_order_context_sync_cart(artifact, state, total_vnd, stage, ui, tool_args) -> OrderResponseContext:
    status, error_message = _status_and_error(artifact)
    cart = state.get("active_cart")
    # off_menu and ambiguous are stored as raw dicts in state by the
    # validator; convert to the typed Pydantic lists here so the rewriter
    # sees clean Pydantic objects.
    off_menu = [
        OffMenuItem(name=u["name"], suggestion=u.get("suggestion"))
        for u in (state.get("unavailable_items") or [])
    ]
    ambiguous = [
        AmbiguousItem(name=a["name"], candidates=a.get("candidates", []))
        for a in (state.get("ambiguous_items") or [])
    ]
    return OrderResponseContext(
        tool="sync_cart",
        status=status,
        cart=cart.items if cart else [],
        total_vnd=total_vnd,
        off_menu=off_menu,
        ambiguous=ambiguous,
        stage=stage,
        ui_action=ui,
        error_message=error_message if status == "error" else None,
    )


def _build_order_context_confirm(artifact, state, total_vnd, ui, tool_args) -> OrderResponseContext:
    status, error_message = _status_and_error(artifact)
    cart = state.get("active_cart")
    return OrderResponseContext(
        tool="confirm_order",
        status=status,
        cart=cart.items if cart else [],
        total_vnd=total_vnd,
        order_id=getattr(artifact, "order_id", None) if status == "success" else None,
        # Stage transitions to CONFIRMED on success; preserved on error
        # (the customer may retry the confirmation on the same stage).
        stage="CONFIRMED" if status == "success" else state.get("order_stage", "IDLE"),
        ui_action=None,  # confirm_order has no tablet UI action
        error_message=error_message if status == "error" else None,
    )


def _build_search_context(artifact, state, ui, tool_args) -> SearchResponseContext:
    status, error_message = _status_and_error(artifact)
    return SearchResponseContext(
        tool="search",
        status=status,
        query=tool_args.get("query", ""),
        results=getattr(artifact, "results", []) or [],
        ui_action=ui,
        error_message=error_message if status == "error" else None,
    )


def _build_payment_context_request(artifact, state, ui, tool_args) -> PaymentResponseContext:
    status, error_message = _status_and_error(artifact)
    amount = getattr(artifact, "amount", None) if artifact else None
    return PaymentResponseContext(
        tool="request_payment",
        status=status,
        amount_vnd=_vnd(amount) if amount else None,
        qr_url=getattr(artifact, "qr_url", None) if artifact else None,
        table_id=state.get("table_id", "T1"),
        ui_action=ui,
        error_message=error_message if status == "error" else None,
    )


def _build_payment_context_verify(artifact, state, ui, tool_args) -> PaymentResponseContext:
    status, error_message = _status_and_error(artifact)
    return PaymentResponseContext(
        tool="verify_payment",
        status=status,
        table_id=state.get("table_id", "T1"),
        ui_action=ui,  # no UI action for verify; None in practice
        error_message=error_message if status == "error" else None,
    )


def _build_order_context_remove(artifact, state, total_vnd, stage, ui, tool_args) -> OrderResponseContext:
    status, error_message = _status_and_error(artifact)
    cart = state.get("active_cart")
    removed = getattr(artifact, "removed", "") if artifact else ""
    return OrderResponseContext(
        tool="remove_cart",
        status=status,
        cart=cart.items if cart else [],
        total_vnd=total_vnd,
        stage=stage,
        ui_action=ui,
        error_message=error_message if status == "error" else None,
    )


def _build_order_context_clear(artifact, state, ui) -> OrderResponseContext:
    status, error_message = _status_and_error(artifact)
    return OrderResponseContext(
        tool="clear_cart",
        status=status,
        cart=[],
        total_vnd="0",
        stage="IDLE",
        ui_action=ui,
        error_message=error_message if status == "error" else None,
    )


# --- Dispatcher ------------------------------------------------------------

def _build_from_tool_message(last: ToolMessage, state: AgentState) -> ResponseContext:
    """Map a tool result to a typed context based on the tool name."""
    ui = state.get("ui_action")
    tool_name = last.name
    artifact = getattr(last, "artifact", None)
    cart = state.get("active_cart")
    total_vnd = _vnd(cart.total_price) if cart else "0"
    stage = state.get("order_stage", "IDLE")
    tool_args = _last_tool_call_args(state)

    if tool_name == "add_cart":
        return _build_order_context_sync_cart(artifact, state, total_vnd, stage, ui, tool_args)
    if tool_name == "remove_cart":
        return _build_order_context_remove(artifact, state, total_vnd, stage, ui, tool_args)
    if tool_name == "clear_cart":
        return _build_order_context_clear(artifact, state, ui)
    if tool_name == "sync_cart":
        return _build_order_context_sync_cart(artifact, state, total_vnd, stage, ui, tool_args)
    if tool_name == "confirm_order":
        return _build_order_context_confirm(artifact, state, total_vnd, ui, tool_args)
    if tool_name == "search":
        return _build_search_context(artifact, state, ui, tool_args)
    if tool_name == "request_payment":
        return _build_payment_context_request(artifact, state, ui, tool_args)
    if tool_name == "verify_payment":
        return _build_payment_context_verify(artifact, state, ui, tool_args)

    # Defensive fallback for unknown tools — degrade to a chat context.
    return ChatResponseContext(
        intent="CHAT",
        user_message=last_user_text(state),
        active_cart=cart or Cart(),
        order_stage=stage,
        chat_history=list(state.get("messages") or []),
    )


def _is_retry_state(state: AgentState) -> bool:
    """True if the validator rejected the worker's last tool call and the
    customer is being asked to retry (or the circuit breaker has tripped).

    The validator always appends ToolMessages (even for error feedback),
    so we check ``is_valid`` + ``feedback`` rather than message type."""
    return (
        state.get("is_valid") is False
        and bool(state.get("feedback"))
    )


def _build_retry_context(state: AgentState) -> RetryResponseContext:
    """Build a RetryResponseContext from the validator's feedback."""
    return RetryResponseContext(
        tool=state.get("last_tool") or "unknown",
        feedback=state.get("feedback", "") or "",
        intent="ORDER",  # most retries are order-domain; can be enriched
    )


# --- Public surface --------------------------------------------------------

def _finalize(ctx: ResponseContext) -> Dict[str, Any]:
    """Return the dict to update the state with: the new context + per-turn resets.

    Per-turn resets are critical — without them, ``unavailable_items``,
    ``ambiguous_items``, ``last_tool``, and ``feedback`` from the previous
    turn would leak into the next turn and contaminate the new context.

    Clears ``search_context`` only on PAYMENT turns — the conversation
    ended. On ORDER turns, curated memory from prior SEARCH turns is NOT
    cleared so it's available if the ORDER worker falls through to CHAT
    (see _route_if_tool_call in graph.py).
    """
    updates = {
        "response_context": ctx,
        "unavailable_items": None,
        "ambiguous_items": None,
        "feedback": None,
        "last_tool": None,
    }
    kind = getattr(ctx, "kind", None)
    if kind == "PAYMENT":
        updates["search_context"] = None
    return updates


def state_outcome_node(state: AgentState) -> Dict[str, Any]:
    """Build a typed ResponseContext from the current turn's state.

    Pure function: no LLM call, no side effects. For the CHAT path
    ``chat_worker`` has already set ``response_context``; this node
    just runs the per-turn reset. For the tool path, it inspects
    ``messages[-1]`` (a ``ToolMessage``) and builds the appropriate
    context. For the retry path, it builds a ``RetryResponseContext``
    from the validator's feedback. As a defensive fallback, it builds
    a ``ChatResponseContext``.

    Always returns a dict suitable for LangGraph's state update,
    including per-turn resets so fields don't leak to the next turn.
    """
    # CHAT path: chat_worker has already set the context; just finalize.
    existing = state.get("response_context")
    if existing is not None:
        return _finalize(existing)
    last = state["messages"][-1]

    if _is_retry_state(state):
        return _finalize(_build_retry_context(state))

    if isinstance(last, ToolMessage):
        return _finalize(_build_from_tool_message(last, state))

    # Defensive: should be unreachable for tool paths. Degrade to a
    # chat context so the rewriter always has something to read.
    return _finalize(ChatResponseContext(
        intent="CHAT",
        user_message=last_user_text(state),
        active_cart=state.get("active_cart") or Cart(),
        order_stage=state.get("order_stage", "IDLE"),
        chat_history=list(state.get("messages") or []),
    ))
