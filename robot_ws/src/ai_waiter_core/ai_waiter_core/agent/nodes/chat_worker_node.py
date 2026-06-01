import logging
from typing import Dict, Any

from langchain_ollama import ChatOllama
from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.config import settings
from ai_waiter_core.utils import trace_latency
from ai_waiter_core.utils.prompt_utils import build_system_prompt, build_dynamic_suffix

logger = logging.getLogger(__name__)

# Initialize ChatOllama for casual conversation (no tools bound)
_chat_model = ChatOllama(
    model=settings.WORKER_MODEL,
    temperature=0.1,
    metadata={"ls_model_name": settings.WORKER_MODEL, "ls_provider": "ollama"}
)

@trace_latency("Chat Worker Node", run_type="chain")
def chat_worker_node(state: AgentState) -> Dict[str, Any]:
    """
    Decoupled LangGraph node that manages small talk, greetings, wifi, and general restaurant inquiries.
    """
    table_id = state.get("table_id", "T1")
    
    # 1. Compile KV-Cache optimized static prompt elements
    static_system_message = build_system_prompt("waiter_agent.md", ["hospitality.md"])
    
    # 2. Compile dynamic suffix elements (table metadata)
    dynamic_suffix_message = build_dynamic_suffix(table_id=table_id)
    
    # 3. Assemble complete message array preserving prefix caching
    input_messages = (
        [static_system_message] 
        + [dynamic_suffix_message] 
        + state["messages"]
    )
    
    response = _chat_model.invoke(input_messages)
    
    return {
        "messages": [response],
        "feedback": None
    }
