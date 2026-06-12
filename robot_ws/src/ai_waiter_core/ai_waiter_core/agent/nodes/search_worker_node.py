from pathlib import Path
from typing import Dict, Any
import json

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.config import settings
from ai_waiter_core.utils import trace_latency
from ai_waiter_core.utils.prompt_utils import build_system_prompt, build_few_shot_examples, build_dynamic_suffix
from ..tools import search

RESOURCES_DIR = settings.resources_dir

# Initialize ChatOllama with bound search tools
_search_model = ChatOllama(
    model=settings.WORKER_MODEL,
    temperature=0.1,
    metadata={"ls_model_name": settings.WORKER_MODEL, "ls_provider": "ollama"}
).bind_tools([search])

@trace_latency("Search Worker Node", run_type="chain")
def search_worker_node(state: AgentState) -> Dict[str, Any]:
    """
    Decoupled LangGraph node that manages database searches, restaurant info, and RAG queries.
    """
    table_id = state.get("table_id", "T1")
    
    # 1. Compile KV-Cache optimized static prompt elements
    static_system_message = build_system_prompt("search_agent.md")
    static_few_shot_messages = build_few_shot_examples("search_worker.json")
    
    # 2. Compile dynamic suffix elements (table metadata, RAG context if applicable)
    dynamic_suffix_message = build_dynamic_suffix(table_id=table_id)
    
    # 3. Assemble complete message array preserving prefix caching order
    input_messages = (
        [static_system_message] 
        + static_few_shot_messages 
        + [dynamic_suffix_message] 
        + state["messages"]
    )
    response = _search_model.invoke(input_messages)
    
    return {
        "messages": [response],
        "feedback": None
    }
