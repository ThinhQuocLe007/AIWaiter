"""response_node — typed rewriter.

Reads ``state["response_context"]``, produces a Vietnamese AIMessage reply.
Dispatches by context type to templates (imported from ``response_template``)
or LLM paraphrasing (for search results, off-menu suggestions, free-form chat).
"""

import logging
import httpx
from typing import Dict, Any, List

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_ollama import ChatOllama

from src.agent_brain.agent.state import AgentState
from src.agent_brain.config import settings
from src.agent_brain.schemas import (
    ResponseContext,
    OrderResponseContext,
    SearchResponseContext,
    PaymentResponseContext,
    ChatResponseContext,
    RetryResponseContext,
)
from src.agent_brain.utils import trace_latency
from src.agent_brain.utils.prompt_utils import load_prompt
from src.agent_brain.agent.nodes.response_template import (
    _FALLBACK_REPLY,
    _vnd,
    _normalize,
    _is_greeting,
    _is_thanks,
    _format_cart_lines,
    _format_ambiguity,
    _format_off_menu,
    _format_order_error,
    _format_cart_echo,
    _format_confirm_reply,
    _format_remove_reply,
    _format_clear_reply,
    _format_greeting,
    _format_thanks,
)

logger = logging.getLogger(__name__)

# ── LLM client + static prompts (loaded once at module level) ───────────────
_response_llm = ChatOllama(
    model=settings.RESPONSE_MODEL,
    temperature=0.1,
    num_ctx=settings.LLM_NUM_CTX,
    keep_alive=settings.llm_keep_alive,
    metadata={"ls_model_name": settings.RESPONSE_MODEL, "ls_provider": "ollama"},
)

_WAITER_PROMPT = load_prompt("response_rewriter.md")
_CHAT_PROMPT = load_prompt("chat_rewriter.md")


# ── Shared LLM call helper ──────────────────────────────────────────────────
def _llm_invoke(system_prompt: str, context_text: str, fallback: str) -> str:
    try:
        response = _response_llm.invoke([
            SystemMessage(content=system_prompt),
            SystemMessage(content=f"CONTEXT:\n{context_text}"),
        ])
        return response.content
    except (httpx.HTTPError, ConnectionError) as e:
        logger.error("LLM call failed: %s", e)
        return fallback


# ── Context formatters (text passed to the LLM as CONTEXT) ──────────────────
def _format_search_for_llm(ctx: SearchResponseContext) -> str:
    lines = [
        f"- {r.document.metadata.get('name', 'Unknown')} — {_vnd(r.document.metadata.get('price', 0))}"
        for r in ctx.results
    ]
    return f"Khách tìm: \"{ctx.query}\"\nKết quả ({len(ctx.results)} món):\n" + "\n".join(lines)


def _format_off_menu_for_llm(ctx: OrderResponseContext) -> str:
    lines = []
    for o in ctx.off_menu:
        if o.suggestion:
            lines.append(f"  - {o.name} (không có trong thực đơn; món gần giống: {o.suggestion})")
        else:
            lines.append(f"  - {o.name} (không có trong thực đơn)")
    return "Món khách yêu cầu nhưng không có trong thực đơn:\n" + "\n".join(lines)


def _format_history_for_llm(messages) -> str:
    lines = []
    for m in messages:
        if isinstance(m, HumanMessage):
            lines.append(f"  Khách: {m.content}")
        elif isinstance(m, AIMessage) and m.content:
            lines.append(f"  Em: {m.content}")
    return "\n".join(lines)


def _format_chat_for_llm(ctx: ChatResponseContext) -> str:
    blocks = []

    cart = ctx.active_cart
    cart_text = "trống"
    if cart and cart.items:
        cart_lines = []
        for i in cart.items:
            price_part = f" ({_vnd(i.unit_price)}/phần)" if i.unit_price else ""
            cart_lines.append(f"{i.name} ×{i.quantity}{price_part}")
        cart_text = ", ".join(cart_lines) + f" (tổng {_vnd(cart.total_price)})"
    blocks.append(f"Giỏ hàng hiện tại: {cart_text}")
    blocks.append(f"Trạng thái đơn: {ctx.order_stage}")

    if ctx.curated_memory:
        mem_lines = []
        for d in ctx.curated_memory:
            price_part = f"{_vnd(d.price)}/phần" if d.price else "?₫/phần"
            tags_part = ", ".join(d.tags) if d.tags else ""
            taste_part = d.taste_profile or ""
            parts = [p for p in [d.name, price_part, tags_part, taste_part] if p]
            mem_lines.append(f"  - {' | '.join(parts)}")
        blocks.append("Món đã thảo luận (từ các lần tìm kiếm trước):\n" + "\n".join(mem_lines))

    history_text = _format_history_for_llm(ctx.chat_history)
    blocks.append(f"Lịch sử hội thoại:\n{history_text}" if history_text else "(chưa có lịch sử)")
    blocks.append(f"Khách vừa nói: \"{ctx.user_message}\"")

    return "\n".join(blocks)


# ── Per-context-type rewriters ──────────────────────────────────────────────
def _rewrite_order(ctx: OrderResponseContext) -> str:
    if ctx.ambiguous:
        return _format_ambiguity(ctx)
    if ctx.off_menu:
        if any(o.suggestion for o in ctx.off_menu):
            return _llm_invoke(_WAITER_PROMPT, _format_off_menu_for_llm(ctx), _format_off_menu(ctx))
        return _format_off_menu(ctx)
    if ctx.status == "error":
        return _format_order_error(ctx)
    if ctx.tool == "confirm_order" and ctx.status == "success":
        return _format_confirm_reply(ctx.order_id)
    if ctx.tool == "remove_cart" and ctx.status == "success":
        return _format_remove_reply(ctx)
    if ctx.tool == "clear_cart" and ctx.status == "success":
        return _format_clear_reply()
    return _format_cart_echo(ctx)


def _rewrite_search(ctx: SearchResponseContext) -> str:
    if ctx.status == "error":
        return "Dạ, em chưa tìm thấy món phù hợp ạ. Anh/chị thử từ khóa khác nhé ạ."
    if not ctx.results:
        query_text = f"'{ctx.query}'" if ctx.query else "món này"
        return f"Dạ, {query_text} không có trong thực đơn của quán mình ạ. Anh/chị muốn em gợi ý món khác không ạ?"
    return _llm_invoke(_WAITER_PROMPT, _format_search_for_llm(ctx), _FALLBACK_REPLY)


def _rewrite_payment(ctx: PaymentResponseContext) -> str:
    if ctx.tool == "request_payment":
        if ctx.status == "error" or not ctx.amount_vnd:
            return "Dạ, hiện chưa có đơn hàng nào trong phiên này ạ."
        return f"Dạ, tổng hóa đơn của anh/chị là {ctx.amount_vnd}₫ ạ. Anh/chị vui lòng quét mã QR để thanh toán nhé."
    if ctx.status == "success":
        return "Dạ, em đã xác nhận thanh toán thành công. Cảm ơn anh/chị đã dùng bữa tại Ốc Quậy ạ!"
    return f"Dạ, chưa xác nhận được thanh toán. {ctx.error_message or 'Anh/chị thử lại giúp em nhé ạ.'}"


def _rewrite_chat(ctx: ChatResponseContext) -> str:
    msg = _normalize(ctx.user_message)
    if _is_greeting(msg):
        return _format_greeting()
    if _is_thanks(msg):
        return _format_thanks()
    return _llm_invoke(_CHAT_PROMPT, _format_chat_for_llm(ctx), _FALLBACK_REPLY)


def _rewrite_retry(ctx: RetryResponseContext) -> str:
    return f"Dạ, em xin lỗi anh/chị, {ctx.feedback} Anh/chị kiểm tra lại giúp em nhé ạ."


# ── Top-level dispatcher ────────────────────────────────────────────────────
def _rewrite(ctx: ResponseContext) -> str:
    if isinstance(ctx, OrderResponseContext):
        return _rewrite_order(ctx)
    if isinstance(ctx, SearchResponseContext):
        return _rewrite_search(ctx)
    if isinstance(ctx, PaymentResponseContext):
        return _rewrite_payment(ctx)
    if isinstance(ctx, ChatResponseContext):
        return _rewrite_chat(ctx)
    if isinstance(ctx, RetryResponseContext):
        return _rewrite_retry(ctx)
    return _FALLBACK_REPLY


# ── Public node entry point ─────────────────────────────────────────────────
@trace_latency("Response Node", run_type="chain")
def response_node(state: AgentState) -> Dict[str, Any]:
    ctx = state.get("response_context")
    if ctx is None:
        return {"messages": [AIMessage(content=_FALLBACK_REPLY)], "response_context": None}
    reply = _rewrite(ctx)
    return {"messages": [AIMessage(content=reply)], "response_context": None}
