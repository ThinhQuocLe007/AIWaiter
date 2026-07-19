import logging
from typing import Any

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from src.agent_brain.agent.state import AgentState
from src.agent_brain.config import settings
from src.agent_brain.utils import trace_latency
from src.agent_brain.utils.prompt_utils import (
    build_dynamic_suffix,
    build_few_shot_examples,
    build_system_prompt,
    last_n_turns,
)
from src.agent_brain.utils.state_helpers import get_worker_query

from ..tools import delegate, search

logger = logging.getLogger(__name__)


# Initialize ChatOllama with bound search tool
_search_model = ChatOllama(
    model=settings.WORKER_MODEL,
    temperature=0.1,
    num_ctx=settings.LLM_NUM_CTX,
    keep_alive=settings.llm_keep_alive,
    metadata={"ls_model_name": settings.WORKER_MODEL, "ls_provider": "ollama"}
).bind_tools([delegate, search], tool_choice="any")


def _build_search_dynamic_context(state: AgentState) -> str:
    """Build context block: already-known topics + feedback on retry.

    Merges names from search_context (prior RAG results) and active_cart
    (ordered items) into a single ĐÃ BIẾT list. The LLM uses this to decide:
    - Name in list → delegate (already covered)
    - Name not in list → search (new topic)
    """
    blocks: list[str] = []
    known: set[str] = set()

    search_context = state.get("search_context")
    if search_context:
        for r in search_context:
            name = r.document.metadata.get("name", "").strip()
            if name:
                known.add(name)

    if known:
        blocks.append("### ĐÃ BIẾT (already discussed/ordered — use to optimize query):")
        blocks.extend(f"  - {name}" for name in sorted(known))
    else:
        blocks.append("### ĐÃ BIẾT: (chưa có gì — phải search)")

    if state.get("feedback"):
        blocks.append("")
        blocks.append("### SYSTEM FEEDBACK (MANDATORY FIX):")
        blocks.append(state["feedback"])
        blocks.append("Fix the tool call arguments and retry immediately.")

    return "\n".join(blocks)


def _extract_delegate_reason(ai_msg) -> str | None:
    if ai_msg.tool_calls:
        for tc in ai_msg.tool_calls:
            if tc.get("name") == "delegate":
                return tc.get("args", {}).get("reason", "")
    return None


@trace_latency("Search Worker Node", run_type="chain")
def search_worker_node(state: AgentState) -> dict[str, Any]:
    """
    Decoupled LangGraph node that manages database searches, restaurant info,
    and RAG queries.
    """
    table_id = state.get("table_id", "T1")

    # 1. Compile KV-Cache optimized static prompt elements
    static_system_message = build_system_prompt("search_agent.md")
    static_few_shot_messages = build_few_shot_examples("search_worker.json")

    # 2. Compile dynamic suffix (table_id + validator feedback if retrying)
    dynamic_context = _build_search_dynamic_context(state)
    dynamic_suffix_message = build_dynamic_suffix(
        table_id=table_id, dynamic_context=dynamic_context
    )

    # 3. Assemble complete message array preserving prefix caching order
    worker_query = get_worker_query(state, "SEARCH")
    history = last_n_turns(state["messages"], n=2)
    for i in range(len(history) - 1, -1, -1):
        if isinstance(history[i], HumanMessage):
            history[i] = HumanMessage(content=worker_query)
            break

    input_messages = (
        [static_system_message]
        + static_few_shot_messages
        + [dynamic_suffix_message]
        + history
    )

    try:
        response = _search_model.invoke(input_messages)
    except (httpx.HTTPError, ConnectionError) as e:
        logger.error("Search Worker Failed: %s", e)
        return {
            "messages": [
                AIMessage(
                    content="Xin lỗi, em xử lý thông tin bị lỗi. Anh/chị có thể nhắc lại được không ạ?"
                )
            ],
            "feedback": None,
            "loop_count": state.get("loop_count", 0) + 1,
        }

    if not response.tool_calls:
        logger.warning(
            "SEARCH worker produced no tool_calls on first attempt — retrying with forced instruction"
        )
        retry_prompt = SystemMessage(
            content=(
                "⚠ CRITICAL: Bạn PHẢI gọi một tool call (search hoặc delegate). "
                "KHÔNG được trả lời bằng text. Nếu không chắc chắn, hãy gọi "
                "search() với tên món ăn hoặc từ khóa chính. "
                "Chỉ trả về tool call NGAY BÂY GIỜ."
            )
        )
        try:
            response = _search_model.invoke([retry_prompt] + list(input_messages))
        except (httpx.HTTPError, ConnectionError) as e:
            logger.error("Search Worker retry failed: %s", e)
            return {
                "messages": [
                    AIMessage(
                        content="Xin lỗi, em xử lý thông tin bị lỗi. Anh/chị có thể nhắc lại được không ạ?"
                    )
                ],
                "feedback": None,
                "loop_count": state.get("loop_count", 0) + 1,
            }

    delegate_reason = _extract_delegate_reason(response)
    if delegate_reason:
        logger.info("Search worker delegating: %s", delegate_reason)
        return {"messages": [response], "delegate_reason": delegate_reason}

    return {
        "messages": [response],
        "feedback": None,
    }
