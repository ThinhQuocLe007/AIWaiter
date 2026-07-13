import json
import logging
from typing import Dict, Any

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
)

from src.agent_brain.schemas.routing import IntentPrediction
from src.agent_brain.config import settings
from src.agent_brain.agent.state import AgentState
from src.agent_brain.utils import trace_latency
from src.agent_brain.utils.prompt_utils import load_prompt, load_json_data

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Chain building (compiled once at module level)
# ------------------------------------------------------------

def _build_router_prompt() -> ChatPromptTemplate:
    system_prompt = load_prompt("router_agent.md")
    raw_examples = load_json_data("router.json")

    # Convert to the format FewShotChatMessagePromptTemplate expects.
    # Because we use structured output, the AI's response must be formatted as a JSON string!
    examples = []
    for ex in raw_examples:
        examples.append({
            "input": ex["query"],
            "output": json.dumps({"intents": ex["intents"], "reasoning": ex["reasoning"]}, ensure_ascii=False)
        })

    example_prompt = ChatPromptTemplate.from_messages([
        ("human", "{input}"),
        ("ai", "{output}"),
    ])

    few_shot_prompt = FewShotChatMessagePromptTemplate(
        example_prompt=example_prompt,
        examples=examples,
    )

    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        few_shot_prompt,
        ("system", "### RECENT CONVERSATION CONTEXT (last 5 exchanges):\n{chat_history}"),
        (
            "system",
            "### CURRENT ORDER STAGE: {order_stage}\n"
            "If stage is AWAITING_CONFIRMATION, the waiter has drafted an order and is "
            "waiting for the customer to confirm. In that stage a short affirmation "
            '("ừ", "uh", "ok", "ok em", "đúng rồi", "được", "ừ đặt nha") is the customer '
            "confirming the drafted order → classify as ORDER_CONFIRM, not CHAT.",
        ),
        ("human", "{query}"),
    ])

# ------------------------------------------------------------
# Context helper: get last N user‑assistant pairs
# ------------------------------------------------------------

def _format_last_n_turns(messages: list, n: int = 5) -> str:
    """Return a string of the last `n` user‑assistant exchanges."""
    pairs = []
    i = len(messages) - 1
    while i >= 0 and len(pairs) < n:
        if isinstance(messages[i], HumanMessage):
            user_content = messages[i].content
            asst_content = ""
            if i + 1 < len(messages) and isinstance(messages[i + 1], AIMessage):
                asst_content = messages[i + 1].content
            pairs.append((user_content, asst_content))
        i -= 1
    pairs.reverse()
    return "\n".join(f"User: {u}\nAI: {a}" for u, a in pairs)

# ------------------------------------------------------------
# Global Instance
# ------------------------------------------------------------

_llm = ChatOllama(
    model=settings.ROUTER_MODEL,
    temperature=0.0,
    num_ctx=settings.LLM_NUM_CTX,
    keep_alive=settings.llm_keep_alive,
    metadata={"ls_model_name": settings.ROUTER_MODEL, "ls_provider": "ollama"}
).with_structured_output(IntentPrediction)

_router_prompt = _build_router_prompt()
_router_chain = _router_prompt | _llm

# ------------------------------------------------------------
# The graph node
# ------------------------------------------------------------

@trace_latency("SLM Router Node", run_type="chain")
def slm_router_node(state: AgentState) -> Dict[str, Any]:
    """
    Classify the latest user message and return the predicted intents.
    """
    # Extract the last user query
    user_message = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    if not user_message:
        logger.warning("No user message found, defaulting to CHAT")
        return {"current_intents": ["CHAT"]}

    query = user_message.content
    chat_history = _format_last_n_turns(state["messages"], n=2)
    order_stage = state.get("order_stage") or "IDLE"

    try:
        result: IntentPrediction = _router_chain.invoke({
            "query": query,
            "chat_history": chat_history or "No previous history.",
            "order_stage": order_stage,
        })
        intents = result.intents or ["CHAT"]
        logger.info(f"SLM Router Output: {intents} | reason: {result.reasoning}")
    except Exception:
        logger.exception("SLM Router LLM call failed, defaulting to CHAT")
        intents = ["CHAT"]

    return {"current_intents": intents}
