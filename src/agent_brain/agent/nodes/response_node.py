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
import unicodedata
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
    _format_off_menu_with_suggestions,
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
# CJK terminators included so a Chinese digression breaks into its own chunk instead of
# being glued to the Vietnamese answer that follows it — see _sanitize_sentence below.
_SENTENCE_BOUNDARY = re.compile(r"[.!?]\s|[。！？：]")

# ── Output sanitising ───────────────────────────────────────────────────────
# Everything the guest HEARS passes through here. Two independent problems:
#
#   markdown — not the LLM's fault. Templates in response_template.py write literal
#     ``**{name}**``, which TTS reads out as "sao sao". Deterministic, so it is stripped
#     rather than prompted away.
#
#   CJK — qwen2.5 is a Chinese model and occasionally narrates its self-correction in
#     Chinese before giving the Vietnamese answer, despite response_rewriter.md forbidding
#     it outright. Measured at roughly 1 turn in 4. A prompt cannot guarantee this, and on
#     the streaming path a sentence is spoken the moment it is emitted — there is no
#     retracting it — so the guard has to run BEFORE the queue, not after.
#
# A contaminated sentence is dropped whole. Deleting just the Han characters would leave a
# stump full of ，。 that is worse to listen to than silence; the neighbouring clean
# sentences still carry the answer.
_CJK_RE = re.compile(r"[一-鿿㐀-䶿　-〿＀-￯]")
_MARKDOWN_RE = re.compile(r"\*\*|__|[*_`#]")


def _strip_markdown(text: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", _MARKDOWN_RE.sub("", text)).strip()


def _sanitize_sentence(text: str) -> str | None:
    """Clean one spoken sentence. ``None`` means drop it entirely."""
    if _CJK_RE.search(text):
        logger.warning("[response] CJK leak — dropping sentence: %.80s", text)
        return None
    return _strip_markdown(text) or None


def _sanitize_reply(text: str) -> str:
    """Full-text variant: drop contaminated sentences, keep the clean ones."""
    # Split on CJK terminators too (。！？：). A Chinese run typically ends in one of those
    # and is immediately followed by the real Vietnamese answer; splitting only on [.!?]
    # would glue the two together and drop the answer along with the contamination.
    # Latin terminators still REQUIRE trailing whitespace — without that, "510.000₫" splits
    # mid-price and TTS reads the amount wrong. CJK ones need no such guard.
    sentences = re.split(r"(?<=[.!?])\s+|(?<=[。！？：])\s*", text)
    kept = [s for s in sentences if s.strip() and not _CJK_RE.search(s)]
    if len(kept) != len([s for s in sentences if s.strip()]):
        logger.warning("[response] CJK leak — dropped %d of %d sentences",
                       len(sentences) - len(kept), len(sentences))
    return _strip_markdown(" ".join(kept)) or _FALLBACK_REPLY


class _StreamContext:
    """Stream state shared by the request thread and the thread running the graph.

    Deliberately a module-level singleton, NOT ``threading.local``: ``server.py`` calls
    ``set_output_queue()`` on the request thread but runs the graph on a separate
    ``ThreadPoolExecutor`` worker, so a per-thread context would leave the worker with an
    empty queue and ``emit()`` would silently no-op — /chat/stream then degrades to
    progress+done with no ``sentence`` events at all. Keep this global unless the executor
    in ``chat_stream`` goes away too.

    The cost of being global: one queue for the whole process, so two tables streaming at
    the same time would have their sentences interleaved into whichever queue was set last.
    Fine for v1 (one voice device), but this is what to fix first when a second one lands —
    pass the queue through the graph call instead of parking it in module state.
    """

    def __init__(self):
        self.queue: Queue | None = None
        self._streamed = False

    def set_queue(self, q: Queue | None) -> None:
        self.queue = q
        self._streamed = False

    def emit(self, text: str) -> None:
        if self.queue is None:
            return
        clean = _sanitize_sentence(text)
        if clean is None:
            return  # dropped: leave _streamed alone so a clean fallback can still be sent
        self.queue.put(("sentence", clean))
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
    stream = _stream
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
                    stream.emit(sentence)
                buffer = buffer[end:]
        remaining = buffer.strip()
        if remaining:
            stream.emit(remaining)
        return "".join(full_text)
    except (httpx.HTTPError, ConnectionError) as e:
        logger.error("LLM stream failed: %s", e)
        if fallback:
            stream.emit(fallback)
        return fallback


# ── Grounding guard for recommendations ─────────────────────────────────────
# qwen2.5 invents plausible-sounding dish names ("Ốc Luộc", "Ốc Hương nướng mỡ hành")
# even though the retrieved list sits right there in CONTEXT and the prompt forbids it.
# That is worse than a clumsy sentence: the guest orders something the kitchen does not
# have, and the tablet renders no card because the name matches nothing in the menu.
#
# Detecting a fabricated name directly is not tractable — an invented name matches nothing,
# and Vietnamese prose is full of bare food words ("món ốc rất ngon") that would false-positive.
# So the check is positive instead: a recommendation must name at least one dish that was
# actually retrieved. A reply that names none is ungrounded and gets replaced wholesale by a
# deterministic listing of the real results.
#
# Known limit: a fake name sitting NEXT TO a real one still passes. Catching that needs the
# retrain in src/training_semantic_router plus a stricter decoder, not a regex.


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower().strip()


def _is_word_char(ch: str) -> bool:
    return bool(ch) and (ch.isalnum())


def _mentioned_dishes(text: str, names: list[str]) -> list[str]:
    """Which of ``names`` the text actually says. Mirrors the tablet's matchDishes:
    normalized, whole-word, longest name claims an overlapping span first."""
    hay = _norm(text)
    claimed: list[tuple[int, int]] = []
    found: list[str] = []
    for name in sorted(names, key=len, reverse=True):
        needle = _norm(name)
        if len(needle) < 3:
            continue
        start = hay.find(needle)
        while start != -1:
            end = start + len(needle)
            before = hay[start - 1] if start > 0 else ""
            after = hay[end] if end < len(hay) else ""
            if not _is_word_char(before) and not _is_word_char(after):
                if not any(start < ce and end > cs for cs, ce in claimed):
                    claimed.append((start, end))
                    found.append(name)
                    break
            start = hay.find(needle, end)
    return found


def _retrieved_dishes(ctx: SearchResponseContext) -> list[tuple[str, float]]:
    out = []
    for r in ctx.results:
        meta = r.document.metadata
        name = (meta.get("name") or "").strip()
        if meta.get("type") == "menu" and (meta.get("price", 0) or 0) > 0 and name:
            out.append((name, meta.get("price", 0)))
    return out


def _deterministic_listing(dishes: list[tuple[str, float]]) -> str:
    # Price only when we actually have one — curated_memory carries names without prices, and
    # "Lẩu Thái (0₫)" would be worse than saying nothing about the price.
    listing = ", ".join(f"{n} ({_vnd(p)})" if p else n for n, p in dishes[:3])
    return f"Dạ, anh/chị tham khảo {listing} ạ. Anh/chị muốn em thêm món nào vào đơn không ạ?"


def _ground_reply(reply: str, dishes: list[tuple[str, float]], where: str) -> str:
    """Replace `reply` with a real listing if it names none of the dishes it was given.

    No dishes to check against means nothing to verify — a general question ("mấy giờ mở
    cửa") legitimately names none, and there is no way to tell that apart from an invented
    name without the retrain. Those turns pass through untouched.
    """
    if not dishes:
        return reply
    if _mentioned_dishes(reply, [n for n, _ in dishes]):
        return reply
    logger.warning(
        "[response] ungrounded %s — named none of %s; replacing. Was: %.90s",
        where, [n for n, _ in dishes], reply,
    )
    return _deterministic_listing(dishes)


def _emit_sentences(text: str) -> None:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if sentence.strip():
            _stream.emit(sentence.strip())


# ── Context formatters (text passed to the LLM as CONTEXT) ──────────────────
def _format_search_for_llm(ctx: SearchResponseContext) -> str:
    lines = [
        f"- {r.document.metadata.get('name', 'Unknown')}"
        f" — {_vnd(r.document.metadata.get('price', 0))}"
        for r in ctx.results
        if r.document.metadata.get("type") == "menu"
        and r.document.metadata.get("price", 0) > 0
        and r.document.metadata.get("name", "").strip()
    ]
    blocks = [f"Khách tìm: \"{ctx.query}\"\nKết quả ({len(ctx.results)} món):\n" + "\n".join(lines)]
    if ctx.shown_dishes:
        blocks.append(
            f"Món đã giới thiệu ở các lượt trước: {', '.join(ctx.shown_dishes)}. "
            "Nếu món nằm trong danh sách này, hãy ưu tiên giới thiệu món KHÁC thay vì lặp lại."
        )
    return "\n\n".join(blocks)


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
    stream = _stream
    if ctx.ambiguous:
        reply = _format_ambiguity(ctx)
        stream.emit(reply)
        return reply
    if ctx.off_menu:
        reply = (
            _format_off_menu_with_suggestions(ctx)
            if any(o.suggestion for o in ctx.off_menu)
            else _format_off_menu(ctx)
        )
        stream.emit(reply)
        return reply
    if ctx.status == "error":
        reply = _format_order_error(ctx)
        stream.emit(reply)
        return reply
    if ctx.tool == "confirm_order" and ctx.status == "success":
        reply = _format_confirm_reply(ctx.order_id)
        stream.emit(reply)
        return reply
    if ctx.tool == "remove_cart" and ctx.status == "success":
        reply = _format_remove_reply(ctx)
        stream.emit(reply)
        return reply
    if ctx.tool == "clear_cart" and ctx.status == "success":
        reply = _format_clear_reply()
        stream.emit(reply)
        return reply
    reply = _format_cart_echo(ctx)
    stream.emit(reply)
    return reply


def _rewrite_search(ctx: SearchResponseContext) -> str:
    stream = _stream
    if ctx.status == "error":
        reply = "Dạ, em chưa tìm thấy món phù hợp ạ. Anh/chị thử từ khóa khác nhé ạ."
        stream.emit(reply)
        return reply
    if not ctx.results:
        query_text = f"'{ctx.query}'" if ctx.query else "món này"
        reply = (
            f"Dạ, {query_text} không có trong thực đơn của quán mình ạ."
            f" Anh/chị muốn em gợi ý món khác không ạ?"
        )
        stream.emit(reply)
        return reply
    # Generated whole, NOT streamed: grounding can only be judged on the complete reply, and a
    # sentence emitted is a sentence already spoken. Costs time-to-first-word on this intent —
    # the alternative is telling the guest about a dish the kitchen does not have.
    raw = _llm_invoke(_WAITER_PROMPT, _format_search_for_llm(ctx), _FALLBACK_REPLY)
    reply = _ground_reply(raw, _retrieved_dishes(ctx), "recommendation")
    _emit_sentences(reply)
    return reply


def _rewrite_payment(ctx: PaymentResponseContext) -> str:
    stream = _stream
    if ctx.tool == "request_payment":
        if ctx.status == "error" or not ctx.amount_vnd:
            reply = "Dạ, hiện chưa có đơn hàng nào trong phiên này ạ."
            stream.emit(reply)
            return reply
        reply = (
            f"Dạ, tổng hóa đơn của anh/chị là {ctx.amount_vnd}₫ ạ."
            f" Anh/chị vui lòng quét mã QR để thanh toán nhé."
        )
        stream.emit(reply)
        return reply
    if ctx.status == "success":
        reply = (
            "Dạ, em đã xác nhận thanh toán thành công."
            " Cảm ơn anh/chị đã dùng bữa tại Ốc Quậy ạ!"
        )
        stream.emit(reply)
        return reply
    reply = (
        f"Dạ, chưa xác nhận được thanh toán."
        f" {ctx.error_message or 'Anh/chị thử lại giúp em nhé ạ.'}"
    )
    stream.emit(reply)
    return reply


def _rewrite_chat(ctx: ChatResponseContext) -> str:
    stream = _stream
    reason = ctx.delegate_reason
    if reason and "xem lại" in reason:
        cart = ctx.active_cart
        if cart and cart.items:
            reply = _format_cart_echo(OrderResponseContext(
                tool="add_cart", status="success", cart=cart.items,
                total_vnd=_vnd(cart.total_price), stage=ctx.order_stage,
            ))
            stream.emit(reply)
            return reply
        reply = "Dạ, hiện tại giỏ hàng của anh/chị đang trống ạ."
        stream.emit(reply)
        return reply
    if reason and "không rõ" in reason:
        reply = "Dạ em chưa rõ ý anh/chị lắm, anh/chị có thể nói lại được không ạ?"
        stream.emit(reply)
        return reply
    msg = _normalize(ctx.user_message)
    if _is_greeting(msg):
        reply = _format_greeting()
        stream.emit(reply)
        return reply
    if _is_thanks(msg):
        reply = _format_thanks()
        stream.emit(reply)
        return reply
    # When curated_memory holds dishes, this turn is a recommendation too and gets the same
    # grounding check as _rewrite_search — generated whole so it can be judged before it is
    # spoken. With no dishes to check against, keep streaming: nothing to verify, and general
    # chat is where time-to-first-word matters most.
    curated = [(d.name, 0.0) for d in (ctx.curated_memory or []) if getattr(d, "name", "")]
    if curated:
        raw = _llm_invoke(_CHAT_PROMPT, _format_chat_for_llm(ctx), _FALLBACK_REPLY)
        reply = _ground_reply(raw, curated, "chat recommendation")
        _emit_sentences(reply)
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
    stream = _stream
    ctx = state.get("response_context")
    if ctx is None:
        if not stream.was_streamed:
            stream.emit(_FALLBACK_REPLY)
        return {"messages": [AIMessage(content=_FALLBACK_REPLY)], "response_context": None}
    # Sanitise here too, not only in emit(): this text is what /chat returns and what the
    # tablet renders, and on the streaming path it never passes through emit() at all.
    reply = _sanitize_reply(_rewrite(ctx))
    if not stream.was_streamed:
        stream.emit(reply)
    return {"messages": [AIMessage(content=reply)], "response_context": None}
