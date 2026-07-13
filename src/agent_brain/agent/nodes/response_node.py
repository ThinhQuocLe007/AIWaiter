"""response_node — the rewriter (Phase 3 of the response-context refactor).

Architecture
------------
The graph ends every turn at this node. The node reads a single typed
``ResponseContext`` from ``state["response_context"]`` (set by
``state_outcome_node`` for tool paths, or by ``chat_worker_node`` for
the CHAT path) and returns a Vietnamese reply as an ``AIMessage``.

The node is a pure dispatcher:
    response_node(state)
      ├── reads state["response_context"]
      ├── _rewrite(ctx)        # isinstance dispatch
      │     ├── _rewrite_order(ctx)      # ORDER → 12 templated cases + 1 LLM
      │     ├── _rewrite_search(ctx)     # SEARCH → template or LLM
      │     ├── _rewrite_payment(ctx)    # PAYMENT → template
      │     ├── _rewrite_chat(ctx)       # CHAT → 2 templates + LLM
      │     └── _rewrite_retry(ctx)      # validator rejected → template
      └── returns AIMessage(content=reply), clears response_context

Most cases are pure-Python templates (no LLM call). The LLM is called
only for 3 cases that genuinely need paraphrasing: search results,
off-menu-with-suggestion apology, and free-form chat (status questions,
small talk, out-of-scope).

What is NOT in this file
------------------------
- ``_build_response_context`` (the legacy dynamic-context builder) is
  preserved at the bottom of the file as commented-out reference code.
  Phase 5 will delete it.
- The legacy ``_build_ambiguity_response`` is ported to
  ``_format_ambiguity`` (takes a typed context, not state).
- The legacy ``response_node`` body is preserved at the bottom of the
  file as commented-out reference code. Phase 5 will delete it.
"""

import logging
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

logger = logging.getLogger(__name__)


# --- LLM client (module-level, loaded once) ---------------------------------

_response_llm = ChatOllama(
    model=settings.RESPONSE_MODEL,
    temperature=0.1,
    num_ctx=settings.LLM_NUM_CTX,
    keep_alive=settings.llm_keep_alive,
    metadata={"ls_model_name": settings.RESPONSE_MODEL, "ls_provider": "ollama"},
)


# --- Prompt constants ------------------------------------------------------
# These are the slim prompts the LLM sees. The dynamic per-turn context
# (cart, history, search results, etc.) is passed as a separate
# SystemMessage so the static prompt stays reusable across all LLM calls.

WAITER_REWRITER_PROMPT = (
    "Bạn là phục vụ viên AI tại Ốc Quậy. Viết lại một đoạn ngắn bằng "
    "tiếng Việt lịch sự cho khách, dựa trên CONTEXT dưới đây.\n"
    "KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT.\n"
    "Dùng 'Dạ', 'ạ', xưng 'em', gọi khách là 'anh/chị'. 1-3 câu. Không kể lể."
)

CHAT_REWRITER_PROMPT = (
    "Bạn là phục vụ viên AI tại Ốc Quậy. Khách vừa nói gì đó. Nhìn CONTEXT bên dưới "
    "rồi trả lời lịch sự bằng tiếng Việt.\n"
    "KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT. "
    "Nếu CONTEXT không chứa câu trả lời cho câu hỏi cụ thể của khách (ví dụ: số lượng "
    "con/phần, trọng lượng, cách chế biến chi tiết, nguyên liệu) → phải nói "
    "'Dạ em chưa có thông tin đó ạ, anh/chị cho em hỏi bếp giúp nhé.'\n"
    "Nếu khách hỏi về một món cụ thể (có cay không? giá bao nhiêu? mô tả? vị ra sao?), "
    "kiểm tra 'Món đã thảo luận' trong CONTEXT trước. "
    "Nếu món có trong đó nhưng thông tin khách hỏi KHÔNG có trong đó → nói không có "
    "thông tin, tuyệt đối không bịa.\n"
    "Nếu khách dùng đại từ tham chiếu ('cái đó', 'món đó', 'món lúc nãy') → dùng "
    "lịch sử hội thoại để xác định món đang được nhắc tới, rồi tra trong "
    "'Món đã thảo luận' hoặc giỏ hàng.\n"
    "Nếu khách hỏi về giỏ hàng / đơn hàng → liệt kê món + giá từng món + tổng từ CONTEXT.\n"
    "Nếu khách tán gẫu / hỏi ngoài phạm vi → trả lời ngắn rồi hỏi lại cần hỗ trợ gì.\n"
    "Dùng 'Dạ', 'ạ', xưng 'em', gọi khách là 'anh/chị'. 1-3 câu."
)

_FALLBACK_REPLY = "Xin lỗi, em chưa rõ, anh/chị nói lại giúp em nhé ạ."


# --- Small text helpers -----------------------------------------------------

def _vnd(amount) -> str:
    """Format Vietnamese dong: 255000.0 -> '255.000₫' (WITH symbol).

    Only used for LLM context text (e.g. ``_format_chat_for_llm``).
    Templates use the ``total_vnd`` / ``amount_vnd`` fields from the
    typed ResponseContext, which are formatted WITHOUT the symbol by
    ``state_outcome_node._vnd``; the template adds the ₫ itself.
    """
    return f"{int(amount):,}".replace(",", ".") + "₫"


def _normalize(msg: str) -> str:
    return (msg or "").lower().strip()


def _is_greeting(msg: str) -> bool:
    """Match the common greeting forms. False positives are tolerable."""
    m = _normalize(msg)
    return (
        m in {"chào", "chào bạn", "chào em", "xin chào", "hello", "hi"}
        or m.startswith(("chào ", "xin chào ", "hello", "hi "))
        or m in {"chào", "hello", "hi"}
    )


def _is_thanks(msg: str) -> bool:
    """Match the common thanks forms. False positives are tolerable."""
    m = _normalize(msg)
    return any(t in m for t in ("cảm ơn", "cám ơn", "thank", "tks", "thanks"))


def _format_cart_lines(items) -> str:
    """Render a list of OrderItem as '- Name ×qty (price/phần)' lines."""
    lines = []
    for item in items:
        price_str = f"{_vnd(item.unit_price)}/phần" if item.unit_price else "?₫/phần"
        line = f"  - {item.name} ×{item.quantity} ({price_str})"
        if item.special_requests:
            line += f" (Ghi chú: {item.special_requests})"
        lines.append(line)
    return "\n".join(lines)


# --- LLM call helpers (the 3 cases that need paraphrasing) ----------------

def _format_search_for_llm(ctx: SearchResponseContext) -> str:
    """Project the search results to a compact text for the LLM prompt."""
    lines = [
        f"- {r.document.metadata.get('name', 'Unknown')} — "
        f"{_vnd(r.document.metadata.get('price', 0))}"
        for r in ctx.results
    ]
    return (
        f"Khách tìm: \"{ctx.query}\"\n"
        f"Kết quả ({len(ctx.results)} món):\n"
        + "\n".join(lines)
    )


def _llm_paraphrase_search(ctx: SearchResponseContext) -> str:
    """Ask the LLM to paraphrase the search results in natural Vietnamese.

    LLM picks 1-2 best matches and phrases them politely. Falls back to
    a pure template if the LLM call fails.
    """
    context_text = _format_search_for_llm(ctx)
    try:
        response = _response_llm.invoke([
            SystemMessage(content=WAITER_REWRITER_PROMPT),
            SystemMessage(content=f"CONTEXT:\n{context_text}"),
        ])
        return response.content
    except Exception as e:
        logger.error(f"LLM call failed in _llm_paraphrase_search: {e}")
        return _FALLBACK_REPLY


def _format_off_menu_for_llm(ctx: OrderResponseContext) -> str:
    """Project the off-menu items + suggestions to text for the LLM prompt."""
    lines = []
    for o in ctx.off_menu:
        if o.suggestion:
            lines.append(f"  - {o.name} (không có trong thực đơn; món gần giống: {o.suggestion})")
        else:
            lines.append(f"  - {o.name} (không có trong thực đơn)")
    return "Món khách yêu cầu nhưng không có trong thực đơn:\n" + "\n".join(lines)


def _llm_paraphrase_order(ctx: OrderResponseContext) -> str:
    """Ask the LLM to phrase the off-menu apology (with suggestion).

    The LLM adds naturalness — Vietnamese politeness, sentence flow.
    Falls back to a pure template on LLM error.
    """
    context_text = _format_off_menu_for_llm(ctx)
    try:
        response = _response_llm.invoke([
            SystemMessage(content=WAITER_REWRITER_PROMPT),
            SystemMessage(content=f"CONTEXT:\n{context_text}"),
        ])
        return response.content
    except Exception as e:
        logger.error(f"LLM call failed in _llm_paraphrase_order: {e}")
        return _format_off_menu(ctx)  # template fallback


def _format_history_for_llm(messages) -> str:
    """Format the conversation history as a short text block for the LLM.

    Skips ToolMessage (not useful for chat reply generation) and
    empty-content AIMessages (tool-call-only messages).
    """
    lines = []
    for m in messages:
        if isinstance(m, HumanMessage):
            lines.append(f"  Khách: {m.content}")
        elif isinstance(m, AIMessage) and m.content:
            lines.append(f"  Em: {m.content}")
        # ToolMessage skipped (chat LLM doesn't need tool results)
    return "\n".join(lines)


def _format_chat_for_llm(ctx: ChatResponseContext) -> str:
    """Project the chat context (cart + memory + history + stage + last msg) to text."""
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
            parts = [d.name, price_part, tags_part, taste_part]
            parts = [p for p in parts if p]
            mem_lines.append(f"  - {' | '.join(parts)}")
        blocks.append("Món đã thảo luận (từ các lần tìm kiếm trước):\n" + "\n".join(mem_lines))

    history_text = _format_history_for_llm(ctx.chat_history)
    history_block = f"Lịch sử hội thoại:\n{history_text}" if history_text else "(chưa có lịch sử)"
    blocks.append(history_block)
    blocks.append(f"Khách vừa nói: \"{ctx.user_message}\"")

    return "\n".join(blocks)


def _llm_paraphrase_chat(ctx: ChatResponseContext) -> str:
    """Ask the LLM to handle free-form chat (status questions, small talk, out of scope).

    The LLM has the cart, order_stage, and conversation history in
    context — so it can answer "cái đó có cay không?" by resolving
    "cái đó" via the history. Falls back to a pure template on LLM error.
    """
    context_text = _format_chat_for_llm(ctx)
    try:
        response = _response_llm.invoke([
            SystemMessage(content=CHAT_REWRITER_PROMPT),
            SystemMessage(content=f"CONTEXT:\n{context_text}"),
        ])
        return response.content
    except Exception as e:
        logger.error(f"LLM call failed in _llm_paraphrase_chat: {e}")
        return _FALLBACK_REPLY


# --- Templates (no LLM call) -----------------------------------------------

def _format_ambiguity(ctx: OrderResponseContext) -> str:
    """Reply when the customer named a generic dish that matches several variants.

    Includes: cart summary (if any), off-menu note (if any), then the
    clarification question for the ambiguous item. Pure template.
    """
    parts = []

    # 1. Cart summary (if any items survived)
    if ctx.cart:
        lines = _format_cart_lines(ctx.cart)
        parts.append(
            "Dạ, giỏ hàng của anh/chị hiện có:\n"
            + lines
            + f"\nTổng tạm tính {ctx.total_vnd}₫."
        )

    # 2. Off-menu note (if any items were stripped)
    if ctx.off_menu:
        names = ", ".join(o.name for o in ctx.off_menu if o.name)
        parts.append(f"Món {names} hiện không có trong thực đơn ạ.")

    # 3. The ambiguity question (the main point)
    for a in ctx.ambiguous:
        cands = "\n".join(f"  - {c}" for c in a.candidates)
        parts.append(
            f"Dạ, món **{a.name}** bên em có nhiều loại ạ, "
            f"anh/chị muốn chọn loại nào ạ?\n{cands}"
        )

    return "\n\n".join(parts)


def _format_off_menu(ctx: OrderResponseContext) -> str:
    """Reply for off-menu items WITHOUT a suggestion. Pure template apology."""
    names = ", ".join(o.name for o in ctx.off_menu if o.name)
    return (
        f"Dạ, món {names} hiện không có trong thực đơn ạ. "
        f"Anh/chị muốn chọn món khác không ạ?"
    )


def _format_order_error(ctx: OrderResponseContext) -> str:
    """Reply when a tool returned an error status."""
    msg = ctx.error_message or "Anh/chị thử lại giúp em nhé ạ."
    return f"Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. {msg}"


def _format_cart_echo(ctx: OrderResponseContext) -> str:
    """Reply for sync_cart success. Lists the cart, total, and asks for confirmation."""
    if not ctx.cart:
        # Cart was emptied (all items stripped). No cart to show.
        return "Dạ, giỏ hàng hiện đang trống ạ. Anh/chị muốn gọi món gì không ạ?"

    cart = _format_cart_lines(ctx.cart)
    suffix = (
        "\nAnh/chị xác nhận đặt hàng chưa ạ?"
        if ctx.stage == "AWAITING_CONFIRMATION"
        else ""
    )
    return (
        f"Dạ, giỏ hàng của anh/chị hiện có:\n{cart}\n"
        f"Tổng tạm tính {ctx.total_vnd}₫"
        f"{'.' + suffix if suffix else '.'}"
    )


# --- Per-context-type rewriters (the dispatcher targets) -------------------

def _rewrite_order(ctx: OrderResponseContext) -> str:
    """Order rewriter: dispatches on (tool, outcome, ctx fields)."""
    # 1. Ambiguous items: must ask the customer which variant
    if ctx.ambiguous:
        return _format_ambiguity(ctx)

    # 2. Off-menu items: apologize and (if available) offer the suggestion
    if ctx.off_menu:
        if any(o.suggestion for o in ctx.off_menu):
            return _llm_paraphrase_order(ctx)  # LLM phrases the apology + offer
        return _format_off_menu(ctx)  # pure template, no suggestion

    # 3. Tool error
    if ctx.status == "error":
        return _format_order_error(ctx)

    # 4. confirm_order success
    if ctx.tool == "confirm_order" and ctx.status == "success":
        return (
            f"Dạ, em đã xác nhận đơn hàng #{ctx.order_id} ạ. "
            f"Món đang được chuẩn bị, anh/chị chờ một chút nhé."
        )

    # 5. remove_cart success
    if ctx.tool == "remove_cart" and ctx.status == "success":
        return (
            f"Dạ, em đã bỏ món khỏi giỏ hàng ạ.\n"
            f"{_format_cart_echo(ctx)}"
        )

    # 6. clear_cart success
    if ctx.tool == "clear_cart" and ctx.status == "success":
        return "Dạ, em đã hủy toàn bộ đơn hàng ạ. Anh/chị muốn gọi món khác không ạ?"

    # 7. add_cart / sync_cart success (default for the order rewriter)
    return _format_cart_echo(ctx)


def _rewrite_search(ctx: SearchResponseContext) -> str:
    """Search rewriter: empty / error → template; with results → LLM paraphrase."""
    if ctx.status == "error":
        return "Dạ, em chưa tìm thấy món phù hợp ạ. Anh/chị thử từ khóa khác nhé ạ."
    if not ctx.results:
        query_text = f"'{ctx.query}'" if ctx.query else "món này"
        return (
            f"Dạ, {query_text} không có trong thực đơn của quán mình ạ. "
            f"Anh/chị muốn em gợi ý món khác không ạ?"
        )
    # LLM picks 1-2 best matches and paraphrases
    return _llm_paraphrase_search(ctx)


def _rewrite_payment(ctx: PaymentResponseContext) -> str:
    """Payment rewriter: pure templates (no LLM call)."""
    if ctx.tool == "request_payment":
        if ctx.status == "error" or not ctx.amount_vnd:
            return "Dạ, hiện chưa có đơn hàng nào trong phiên này ạ."
        return (
            f"Dạ, tổng hóa đơn của anh/chị là {ctx.amount_vnd}₫ ạ. "
            f"Anh/chị vui lòng quét mã QR để thanh toán nhé."
        )
    # verify_payment
    if ctx.status == "success":
        return (
            "Dạ, em đã xác nhận thanh toán thành công. "
            "Cảm ơn anh/chị đã dùng bữa tại Ốc Quậy ạ!"
        )
    return (
        f"Dạ, chưa xác nhận được thanh toán. "
        f"{ctx.error_message or 'Anh/chị thử lại giúp em nhé ạ.'}"
    )


def _rewrite_chat(ctx: ChatResponseContext) -> str:
    """Chat rewriter: 2 templates (greeting, thanks) + LLM for everything else.

    The LLM call (via ``_llm_paraphrase_chat``) handles status questions
    ("nảy giờ mình gọi món gì rồi nhỉ?"), small talk, and out-of-scope
    questions — it has the cart + history in context, so it can resolve
    follow-up references naturally.
    """
    msg = _normalize(ctx.user_message)

    if _is_greeting(msg):
        return "Dạ, em chào anh/chị ạ. Em có thể giúp gì cho anh/chị ạ?"

    if _is_thanks(msg):
        return "Dạ, không có gì ạ. Anh/chị cần em hỗ trợ gì thêm không ạ?"

    # Everything else: LLM with the cart + history + user_message
    return _llm_paraphrase_chat(ctx)


def _rewrite_retry(ctx: RetryResponseContext) -> str:
    """Retry rewriter: translate validator feedback into a polite explanation."""
    return (
        f"Dạ, em xin lỗi anh/chị, {ctx.feedback} "
        f"Anh/chị kiểm tra lại giúp em nhé ạ."
    )


# --- Top-level dispatcher ---------------------------------------------------

def _rewrite(ctx: ResponseContext) -> str:
    """Dispatch a typed ResponseContext to the per-type rewriter."""
    if isinstance(ctx, OrderResponseContext):    return _rewrite_order(ctx)
    if isinstance(ctx, SearchResponseContext):   return _rewrite_search(ctx)
    if isinstance(ctx, PaymentResponseContext):  return _rewrite_payment(ctx)
    if isinstance(ctx, ChatResponseContext):     return _rewrite_chat(ctx)
    if isinstance(ctx, RetryResponseContext):    return _rewrite_retry(ctx)
    return _FALLBACK_REPLY


# --- Public node -----------------------------------------------------------

@trace_latency("Response Node", run_type="chain")
def response_node(state: AgentState) -> Dict[str, Any]:
    """The rewriter entry point. Reads state["response_context"] and produces a reply.

    Pure dispatcher: reads one field, returns one field. Never mines
    other state fields. The graph already routes every turn to this node
    via state_outcome → response_node (or chat_worker →
    state_outcome → response_node for CHAT turns).
    """
    ctx = state.get("response_context")
    if ctx is None:
        # Defensive: should be unreachable now that state_outcome
        # runs at the end of every turn.
        return {
            "messages": [AIMessage(content=_FALLBACK_REPLY)],
            "response_context": None,
        }

    reply = _rewrite(ctx)
    return {
        "messages": [AIMessage(content=reply)],
        "response_context": None,  # never leak to next turn
    }
