"""response_node — typed rewriter.

Reads ``state["response_context"]``, produces a Vietnamese AIMessage reply.
Dispatches by context type to templates (imported from ``response_template``)
or LLM paraphrasing (for search results, off-menu suggestions, free-form chat).

Streaming: when ``set_output_queue()`` is called before graph invocation, LLM-based
rewriters stream sentences through ``_stream.emit()``; template-based rewriters push
their full text as a single sentence.
"""

import logging
import re
from queue import Queue
from typing import Any

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from src.agent_brain.agent.nodes.response_template import (
    _FALLBACK_REPLY,
    _format_ambiguity,
    _format_cart_echo,
    _format_clear_reply,
    _format_confirm_reply,
    _format_greeting,
    _format_off_menu,
    _format_order_error,
    _format_remove_reply,
    _format_thanks,
    _is_greeting,
    _is_thanks,
    _normalize,
    _vnd,
)
from src.agent_brain.agent.state import AgentState
from src.agent_brain.config import settings
from src.agent_brain.schemas import (
    ChatResponseContext,
    OrderResponseContext,
    PaymentResponseContext,
    ResponseContext,
    RetryResponseContext,
    SearchResponseContext,
)
from src.agent_brain.utils import trace_latency
from src.agent_brain.utils.prompt_utils import load_prompt

logger = logging.getLogger(__name__)

# ── Stream context (bridge between sync graph → async SSE generator) ─────────
_SENTENCE_BOUNDARY = re.compile(r"[.!?]\s")


class _StreamContext:
    """Per-request stream state. Module-level singleton; safe for v1 single-concurrent-request."""

    def __init__(self):
        self.queue: Queue | None = None
        self._streamed = False

    def set_queue(self, q: Queue | None) -> None:
        self.queue = q
        self._streamed = False

    def emit(self, text: str) -> None:
        if self.queue is not None:
            self.queue.put(("sentence", text))
            self._streamed = True

    @property
    def active(self) -> bool:
        return self.queue is not None

    @property
    def was_streamed(self) -> bool:
        return self._streamed


_stream = _StreamContext()


def set_output_queue(q: Queue | None) -> None:
    _stream.set_queue(q)

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


# ── Shared LLM call helpers ──────────────────────────────────────────────────
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


def _llm_stream(system_prompt: str, context_text: str, fallback: str) -> str:
    """Stream LLM output, emitting complete sentences (punctuation + whitespace)."""
    full_text: list[str] = []
    buffer = ""
    try:
        for chunk in _response_llm.stream([
            SystemMessage(content=system_prompt),
            SystemMessage(content=f"CONTEXT:\n{context_text}"),
        ]):
            token = (
                chunk.content if hasattr(chunk, "content")
                else str(chunk) if isinstance(chunk, str)
                else ""
            )
            if not token:
                continue
            full_text.append(token)
            buffer += token
            while True:
                match = _SENTENCE_BOUNDARY.search(buffer)
                if not match:
                    break
                end = match.end()
                sentence = buffer[:end].strip()
                if sentence:
                    _stream.emit(sentence)
                buffer = buffer[end:]
        remaining = buffer.strip()
        if remaining:
            _stream.emit(remaining)
        return "".join(full_text)
    except (httpx.HTTPError, ConnectionError) as e:
        logger.error("LLM stream failed: %s", e)
        if fallback:
            _stream.emit(fallback)
        return fallback


# ── Context formatters (text passed to the LLM as CONTEXT) ──────────────────
def _format_search_for_llm(ctx: SearchResponseContext) -> str:
    # No prices in the CONTEXT on purpose: the reply is read aloud by TTS, and the tablet
    # renders each mentioned dish as a card (image + price + add button) under the bubble.
    # Keeping prices out of the LLM's sight guarantees they can't leak into speech.
    lines = [f"- {r.document.metadata.get('name', 'Unknown')}" for r in ctx.results]
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

    if ctx.table_context:
        blocks.append(f"Đang phục vụ: {ctx.table_context}")

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
        # No per-dish prices here (same reason as _format_search_for_llm): suggestions are
        # spoken by TTS while the tablet shows price cards. Cart lines above DO keep prices —
        # "tổng bao nhiêu?" must still be answerable out loud.
        mem_lines = []
        for d in ctx.curated_memory:
            tags_part = ", ".join(d.tags) if d.tags else ""
            taste_part = d.taste_profile or ""
            parts = [p for p in [d.name, tags_part, taste_part] if p]
            mem_lines.append(f"  - {' | '.join(parts)}")
        blocks.append("Món đã thảo luận (từ các lần tìm kiếm trước):\n" + "\n".join(mem_lines))

    history_text = _format_history_for_llm(ctx.chat_history)
    blocks.append(f"Lịch sử hội thoại:\n{history_text}" if history_text else "(chưa có lịch sử)")
    blocks.append(f"Khách vừa nói: \"{ctx.user_message}\"")

    return "\n".join(blocks)


# ── Per-context-type rewriters ──────────────────────────────────────────────
def _rewrite_order(ctx: OrderResponseContext) -> str:
    if ctx.ambiguous:
        reply = _format_ambiguity(ctx)
        _stream.emit(reply)
        return reply
    if ctx.off_menu:
        if any(o.suggestion for o in ctx.off_menu):
            return _llm_stream(_WAITER_PROMPT, _format_off_menu_for_llm(ctx), _format_off_menu(ctx))
        reply = _format_off_menu(ctx)
        _stream.emit(reply)
        return reply
    if ctx.status == "error":
        reply = _format_order_error(ctx)
        _stream.emit(reply)
        return reply
    if ctx.tool == "confirm_order" and ctx.status == "success":
        reply = _format_confirm_reply(ctx.order_id)
        _stream.emit(reply)
        return reply
    if ctx.tool == "remove_cart" and ctx.status == "success":
        reply = _format_remove_reply(ctx)
        _stream.emit(reply)
        return reply
    if ctx.tool == "clear_cart" and ctx.status == "success":
        reply = _format_clear_reply()
        _stream.emit(reply)
        return reply
    reply = _format_cart_echo(ctx)
    _stream.emit(reply)
    return reply


def _rewrite_search(ctx: SearchResponseContext) -> str:
    if ctx.status == "error":
        reply = "Dạ, em chưa tìm thấy món phù hợp ạ. Anh/chị thử từ khóa khác nhé ạ."
        _stream.emit(reply)
        return reply
    if not ctx.results:
        query_text = f"'{ctx.query}'" if ctx.query else "món này"
        reply = f"Dạ, {query_text} không có trong thực đơn của quán mình ạ. Anh/chị muốn em gợi ý món khác không ạ?"
        _stream.emit(reply)
        return reply
    return _llm_stream(_WAITER_PROMPT, _format_search_for_llm(ctx), _FALLBACK_REPLY)


def _rewrite_payment(ctx: PaymentResponseContext) -> str:
    if ctx.tool == "request_payment":
        if ctx.status == "error" or not ctx.amount_vnd:
            reply = "Dạ, hiện chưa có đơn hàng nào trong phiên này ạ."
            _stream.emit(reply)
            return reply
        reply = f"Dạ, tổng hóa đơn của anh/chị là {ctx.amount_vnd}₫ ạ. Anh/chị vui lòng quét mã QR để thanh toán nhé."
        _stream.emit(reply)
        return reply
    if ctx.status == "success":
        reply = "Dạ, em đã xác nhận thanh toán thành công. Cảm ơn anh/chị đã dùng bữa tại Ốc Quậy ạ!"
        _stream.emit(reply)
        return reply
    reply = f"Dạ, chưa xác nhận được thanh toán. {ctx.error_message or 'Anh/chị thử lại giúp em nhé ạ.'}"
    _stream.emit(reply)
    return reply


def _rewrite_chat(ctx: ChatResponseContext) -> str:
    reason = ctx.delegate_reason
    if reason and "xem lại" in reason:
        cart = ctx.active_cart
        if cart and cart.items:
            reply = _format_cart_echo(OrderResponseContext(
                tool="add_cart", status="success", cart=cart.items,
                total_vnd=_vnd(cart.total_price), stage=ctx.order_stage,
            ))
            _stream.emit(reply)
            return reply
        reply = "Dạ, hiện tại giỏ hàng của anh/chị đang trống ạ."
        _stream.emit(reply)
        return reply
    if reason and "không rõ" in reason:
        reply = "Dạ em chưa rõ ý anh/chị lắm, anh/chị có thể nói lại được không ạ?"
        _stream.emit(reply)
        return reply
    msg = _normalize(ctx.user_message)
    if _is_greeting(msg):
        reply = _format_greeting()
        _stream.emit(reply)
        return reply
    if _is_thanks(msg):
        reply = _format_thanks()
        _stream.emit(reply)
        return reply
    return _llm_stream(_CHAT_PROMPT, _format_chat_for_llm(ctx), _FALLBACK_REPLY)


def _rewrite_retry(ctx: RetryResponseContext) -> str:
    reply = f"Dạ, em xin lỗi anh/chị, {ctx.feedback} Anh/chị kiểm tra lại giúp em nhé ạ."
    _stream.emit(reply)
    return reply


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
def response_node(state: AgentState) -> dict[str, Any]:
    ctx = state.get("response_context")
    if ctx is None:
        if not _stream.was_streamed:
            _stream.emit(_FALLBACK_REPLY)
        return {"messages": [AIMessage(content=_FALLBACK_REPLY)], "response_context": None}
    reply = _rewrite(ctx)
    if not _stream.was_streamed:
        _stream.emit(reply)
    return {"messages": [AIMessage(content=reply)], "response_context": None}
