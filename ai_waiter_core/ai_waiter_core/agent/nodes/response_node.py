import logging
from typing import Dict, Any

from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage

from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.config import settings
from ai_waiter_core.utils import trace_latency
from ai_waiter_core.utils.prompt_utils import build_system_prompt, build_dynamic_suffix

logger = logging.getLogger(__name__)

_response_llm = ChatOllama(
    model=settings.RESPONSE_MODEL,
    temperature=0.1,
    num_ctx=settings.LLM_NUM_CTX,
    metadata={"ls_model_name": settings.RESPONSE_MODEL, "ls_provider": "ollama"}
)

_static_system_prompt = build_system_prompt("waiter_agent.md")


def _build_response_context(state: AgentState) -> str:
    blocks = []

    blocks.append(f"Trạng thái đơn hàng (order_stage): {state.get('order_stage', 'IDLE')}")

    active_cart = state.get("active_cart")
    if active_cart and active_cart.items:
        cart_lines = []
        for item in active_cart.items:
            line = f"  - {item.name} ×{item.quantity}"
            if item.special_requests:
                line += f" (Ghi chú: {item.special_requests})"
            cart_lines.append(line)
        cart_lines.append(f"  Tổng tạm tính: {active_cart.total_price:,}₫")
        blocks.append(f"Giỏ hàng hiện tại (active_cart):\n" + "\n".join(cart_lines))

    unavailable = state.get("unavailable_items")
    if unavailable:
        lines = []
        for u in unavailable:
            name = u.get("name")
            sugg = u.get("suggestion")
            if sugg:
                lines.append(f"  - {name} (KHÔNG có trong thực đơn — món gần giống: {sugg})")
            else:
                lines.append(f"  - {name} (KHÔNG có trong thực đơn)")
        blocks.append(
            "Món khách vừa yêu cầu nhưng KHÔNG có trong thực đơn — em PHẢI báo rõ cho "
            "khách những món này, tuyệt đối không bỏ qua và không tự thay bằng món khác:\n"
            + "\n".join(lines)
        )

    # NOTE: ambiguous_items (generic dish -> many variants) is handled deterministically
    # in response_node itself (the small model is unreliable at asking), not here.

    search_context = state.get("search_context")
    if search_context:
        blocks.append("Kết quả tìm kiếm (search_context):")
        for r in search_context:
            doc = r.document
            name = doc.metadata.get("name", "Unknown")
            price = doc.metadata.get("price", "")
            desc = doc.page_content
            price_str = f"{price:,}₫" if price else ""
            blocks.append(f"  - {name}{' — ' + price_str if price_str else ''}\n    {desc}")

    return "\n\n".join(blocks)


def _format_ambiguity_question(ambiguous: list) -> str:
    """Deterministic clarification message for generic dish names with many variants."""
    lines = []
    for a in ambiguous:
        name = a.get("name")
        cands = a.get("candidates", []) or []
        shown = "\n".join(f"  - {c}" for c in cands)
        lines.append(
            f"Dạ, món **{name}** bên em có nhiều loại ạ, anh/chị muốn chọn loại nào ạ?\n{shown}"
        )
    return "\n\n".join(lines)


def _vnd(amount: float) -> str:
    """Format a price the Vietnamese way: 255000.0 -> '255.000₫'."""
    return f"{int(amount):,}".replace(",", ".") + "₫"


def _build_ambiguity_response(state: AgentState) -> str:
    """
    Fully deterministic reply for any turn that has ambiguous items. The small
    response model tends to hallucinate stripped items back into the cart summary
    ("Ốc Hương ×2" while it was actually removed), so we compose the whole message
    ourselves: real cart items only, off-menu note, then the clarification question.
    """
    parts = []

    active_cart = state.get("active_cart")
    if active_cart and active_cart.items:
        lines = []
        for item in active_cart.items:
            line = f"  - {item.name} ×{item.quantity}"
            if item.special_requests:
                line += f" (Ghi chú: {item.special_requests})"
            lines.append(line)
        parts.append(
            "Dạ, giỏ hàng của anh/chị hiện có:\n"
            + "\n".join(lines)
            + f"\nTạm tính {_vnd(active_cart.total_price)}."
        )

    unavailable = state.get("unavailable_items")
    if unavailable:
        names = ", ".join(u.get("name") for u in unavailable if u.get("name"))
        parts.append(f"Món {names} hiện không có trong thực đơn ạ.")

    parts.append(_format_ambiguity_question(state.get("ambiguous_items") or []))
    return "\n\n".join(parts)


@trace_latency("Response Node", run_type="chain")
def response_node(state: AgentState) -> Dict[str, Any]:
    """
    Generates natural language responses.

    Handles two scenarios:
    1. CHAT intent: Small talk, greetings, general inquiries
    2. Post-tool execution: Verbalizing tool results into natural responses
    """
    table_id = state.get("table_id", "T1")
    messages = state["messages"]

    # Whenever a generic dish maps to several variants, build the ENTIRE reply
    # deterministically (cart + off-menu note + clarification). The small response
    # model is unreliable here: it ignores the "ask which variant" instruction and
    # hallucinates the stripped item back into the cart summary.
    ambiguous = state.get("ambiguous_items")
    if ambiguous:
        return {
            "messages": [AIMessage(content=_build_ambiguity_response(state))],
            "feedback": None,
            "unavailable_items": None,
            "ambiguous_items": None,
        }

    dynamic_context = _build_response_context(state)
    dynamic_suffix = build_dynamic_suffix(table_id=table_id, dynamic_context=dynamic_context)

    input_messages = [_static_system_prompt, dynamic_suffix] + list(messages)

    try:
        response = _response_llm.invoke(input_messages)
        # Clear once surfaced so they don't leak into the next turn.
        return {"messages": [response], "feedback": None, "unavailable_items": None, "ambiguous_items": None}
    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        fallback = "Xin lỗi, em xử lý thông tin bị lỗi. Anh/chị có thể nhắc lại được không ạ?"
        return {"messages": [AIMessage(content=fallback)], "feedback": None, "unavailable_items": None, "ambiguous_items": None}
