from pathlib import Path
from typing import Dict, Any

from langchain_ollama import ChatOllama
from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.config import settings
from ai_waiter_core.utils import trace_latency
from ai_waiter_core.schemas.menu_registry import MENU_NAMES
from ai_waiter_core.schemas.reflection import CriticVerdict

# Resolved path from centralized config settings
SKILL_PATH = settings.resources_dir / "skills" / "menu_grounding.md"

# Initialize structured critic LLM self-containedly
_critic_model = ChatOllama(
    model=settings.WORKER_MODEL,
    temperature=0.1,
    metadata={"ls_model_name": settings.WORKER_MODEL, "ls_provider": "ollama"}
).with_structured_output(CriticVerdict)

@trace_latency("Critic Node", run_type="chain")
def critic_node(state: AgentState) -> Dict[str, Any]:
    """
    Qualitative inspector node. Evaluates remaining semantic/grounding aspects
    of drafted tool calls using a structured LLM reflection step.
    """
    last_message = state["messages"][-1]
    
    # 1. No tool calls? Conversational chat is always qualitatively valid
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"is_valid": True, "feedback": None}
    
    # 2. Load Grounding Skill Plugin and Inject Active Menu
    with open(SKILL_PATH, 'r', encoding='utf-8') as f:
        grounding_skill_template = f.read()
    
    menu_list_str = "\n".join([f"- {name}" for name in MENU_NAMES])
    grounding_skill = grounding_skill_template.format(menu_list=menu_list_str)
    
    # 3. Format qualitative audit prompt
    prompt = f"Review these tool calls and verify item names against the menu:\n{last_message.tool_calls}"
    
    # 4. Invoke Structured Critic LLM
    try:
        verdict: CriticVerdict = _critic_model.invoke([
            {"role": "system", "content": grounding_skill},
            {"role": "user", "content": prompt}
        ])
        
        return {
            "is_valid": verdict.is_valid,
            "feedback": verdict.feedback,
            "loop_count": state.get("loop_count", 0) + (1 if not verdict.is_valid else 0)
        }
    except Exception as e:
        # Robust fallback: if Critic LLM times out or fails, let it pass to tools
        # to prevent freezing the interface
        return {
            "is_valid": True,
            "feedback": None
        }
