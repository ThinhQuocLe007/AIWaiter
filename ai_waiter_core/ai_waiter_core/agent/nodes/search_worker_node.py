import logging
from typing import Dict, Any, Optional

from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage

from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.config import settings
from ai_waiter_core.utils import trace_latency
from ai_waiter_core.utils.prompt_utils import build_system_prompt, build_few_shot_examples, build_dynamic_suffix
from ..tools import search

logger = logging.getLogger(__name__)


# Initialize ChatOllama with bound search tool
_search_model = ChatOllama(
    model=settings.WORKER_MODEL,
    temperature=0.1,
    metadata={"ls_model_name": settings.WORKER_MODEL, "ls_provider": "ollama"}
).bind_tools([search], tool_choice="any")
# NOTE: `tool_choice="any"` is currently ignored by ChatOllama (see its
# bind_tools docstring: "not supported by Ollama"). The binding is kept for
# forward-compatibility and to signal intent. Today's tool-call enforcement
# comes from the system prompt + Pydantic-constrained schema + few-shot
# examples. If the LLM ever replies in text despite that, the graph's
# defensive routing in `_route_if_tool_call` (agent/graph.py) sends the
# message to response_node so the customer still gets a verbalized reply.


def _build_search_dynamic_context(state: AgentState) -> Optional[str]:
    """
    Build the dynamic context block for the search worker.

    Surfaces validator feedback on retry so the LLM sees why its previous
    tool call was rejected (e.g., missing required arg, wrong type).
    Without this, the LLM has no signal to correct its mistake and the
    retry loop is blind.
    """
    if state.get("feedback"):
        return (
            "### SYSTEM FEEDBACK (MANDATORY FIX):\n"
            f"{state['feedback']}\n"
            "Fix the tool call arguments and retry immediately."
        )
    return None


@trace_latency("Search Worker Node", run_type="chain")
def search_worker_node(state: AgentState) -> Dict[str, Any]:
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
    input_messages = (
        [static_system_message]
        + static_few_shot_messages
        + [dynamic_suffix_message]
        + state["messages"]
    )

    try:
        response = _search_model.invoke(input_messages)
    except Exception as e:
        logger.error(f"Search Worker Failed: {e}")
        return {
            "messages": [
                AIMessage(
                    content="Xin lỗi, em xử lý thông tin bị lỗi. Anh/chị có thể nhắc lại được không ạ?"
                )
            ],
            "feedback": None,
            "loop_count": state.get("loop_count", 0) + 1,
        }

    return {
        "messages": [response],
        "feedback": None,
    }
