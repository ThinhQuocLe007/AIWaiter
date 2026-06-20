import logging
from typing import Dict, Any

from langchain_ollama import ChatOllama
from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.config import settings
from ai_waiter_core.utils import trace_latency
from ai_waiter_core.utils.prompt_utils import build_system_prompt, build_few_shot_examples, build_dynamic_suffix
from ..tools import request_payment, verify_payment

logger = logging.getLogger(__name__)

# Initialize ChatOllama with bound payment tools
_payment_model = ChatOllama(
    model=settings.WORKER_MODEL,
    temperature=0.1,
    num_ctx=settings.LLM_NUM_CTX,
    metadata={"ls_model_name": settings.WORKER_MODEL, "ls_provider": "ollama"}
).bind_tools([request_payment, verify_payment])

@trace_latency("Payment Worker Node", run_type="chain")
def payment_worker_node(state: AgentState) -> Dict[str, Any]:
    """
    Decoupled LangGraph node that manages checkout, bill queries, and payment processing.
    """
    table_id = state.get("table_id", "T1")

    # 1. Compile KV-Cache optimized static prompt elements
    static_system_message = build_system_prompt("payment_worker_agent.md")
    static_few_shot_messages = build_few_shot_examples("payment_worker.json")

    # 2. Compile dynamic suffix elements (table metadata)
    dynamic_suffix_message = build_dynamic_suffix(table_id=table_id)

    # 3. Assemble complete message array preserving prefix caching
    input_messages = (
        [static_system_message]
        + static_few_shot_messages
        + [dynamic_suffix_message]
        + state["messages"]
    )

    response = _payment_model.invoke(input_messages)

    return {
        "messages": [response],
        "feedback": None
    }
