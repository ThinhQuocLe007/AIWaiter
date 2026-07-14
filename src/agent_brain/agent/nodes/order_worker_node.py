import logging
from typing import Dict, Any

import httpx
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, SystemMessage

from src.agent_brain.agent.state import AgentState
from src.agent_brain.config import settings
from src.agent_brain.utils import trace_latency
from src.agent_brain.utils.prompt_utils import build_system_prompt, build_few_shot_examples, build_dynamic_suffix, last_n_turns

from ..tools import add_cart, remove_cart, clear_cart, confirm_order

logger = logging.getLogger(__name__)

_llm = ChatOllama(
    model=settings.WORKER_MODEL,
    temperature=0.1,
    num_ctx=settings.LLM_NUM_CTX,
    keep_alive=settings.llm_keep_alive,
    metadata={"ls_model_name": settings.WORKER_MODEL, "ls_provider": "ollama"},
).bind_tools([add_cart, remove_cart, clear_cart, confirm_order], tool_choice="any")


def _build_dynamic_context_block(state: AgentState, order_stage: str) -> str:
    """Assembles the current order stage, cart summary, and validation feedback.

    The full menu list is intentionally NOT included — the validator resolves
    names independently, so the LLM only needs to see cart state and feedback.
    This keeps the context ~200 tokens (down from ~3000 with the menu).
    """
    blocks = [f"Trạng thái đơn hàng (Current Stage): {order_stage}"]

    cart = state.get("active_cart")
    if cart and cart.items:
        blocks.append("### CURRENT ACTIVE CART:")
        blocks.append(str(cart))
    else:
        blocks.append("### CURRENT ACTIVE CART:")
        blocks.append("(trống)")

    if state.get("feedback"):
        blocks.extend([
            "",
            "### SYSTEM FEEDBACK (MANDATORY FIX):",
            state["feedback"],
            "Fix the tool call arguments and retry immediately.",
        ])

    return "\n".join(blocks)


@trace_latency("Order Worker Node", run_type="chain")
def order_worker_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node: maps customer utterance to exactly ONE cart CRUD tool call."""
    table_id = state.get("table_id", "T1")
    order_stage = state.get("order_stage", "IDLE")
    context_block = _build_dynamic_context_block(state, order_stage)

    static_system_message = build_system_prompt("order_worker_agent.md")
    static_few_shot_messages = build_few_shot_examples("order_worker.json")
    dynamic_suffix_message = build_dynamic_suffix(table_id=table_id, dynamic_context=context_block)

    input_messages = (
        [static_system_message]
        + static_few_shot_messages
        + [dynamic_suffix_message]
        + last_n_turns(state["messages"], n=3)
    )

    try:
        ai_msg = _llm.invoke(input_messages)
    except (httpx.HTTPError, ConnectionError) as e:
        logger.error("Order Worker Failed: %s", e)
        ai_msg = AIMessage(content="Xin lỗi, em xử lý thông tin bị lỗi. Anh/chị có thể nhắc lại được không ạ?")

    if not ai_msg.tool_calls:
        logger.warning("ORDER worker produced no tool_calls on first attempt — retrying with forced instruction")
        retry_prompt = SystemMessage(
            content=(
                "⚠ CRITICAL: Bạn PHẢI gọi một tool call (add_cart, remove_cart, "
                "clear_cart, hoặc confirm_order). KHÔNG được trả lời bằng text. "
                "Chỉ trả về tool call. Nhìn câu cuối cùng của khách và gọi tool "
                "phù hợp NGAY BÂY GIỜ."
            )
        )
        try:
            ai_msg = _llm.invoke([retry_prompt] + list(input_messages))
        except (httpx.HTTPError, ConnectionError) as e:
            logger.error("Order Worker retry failed: %s", e)
            ai_msg = AIMessage(content="Xin lỗi, em xử lý thông tin bị lỗi. Anh/chị có thể nhắc lại được không ạ?")

    return {"messages": [ai_msg], "feedback": None}
