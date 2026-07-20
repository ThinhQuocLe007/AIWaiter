"""rewriter_node — utterance decomposition into single-intent fragments.

A focused LLM call that splits multi-intent utterances into self-contained
Vietnamese sentences. Each fragment is then classified independently by the
semantic router (per-fragment argmax).

Replaces both the old slm_router_node and planner_node.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
)
from langchain_ollama import ChatOllama

from src.agent_brain.agent.state import AgentState
from src.agent_brain.config import settings
from src.agent_brain.schemas.routing import RewriterOutput
from src.agent_brain.utils import trace_latency
from src.agent_brain.utils.prompt_utils import load_json_data, load_prompt

logger = logging.getLogger(__name__)


def _build_rewriter_prompt() -> ChatPromptTemplate:
    system_prompt = load_prompt("rewriter_agent.md")
    raw_examples = load_json_data("rewriter.json")

    examples = []
    for ex in raw_examples:
        examples.append({
            "input": ex["query"],
            "output": json.dumps(
                {"fragments": ex["fragments"]},
                ensure_ascii=False,
            ),
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
        ("human", "{query}"),
    ])


def _format_last_n_turns(messages: list, n: int = 5) -> str:
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


_llm = ChatOllama(
    model=settings.ROUTER_MODEL,
    temperature=0.0,
    num_ctx=settings.LLM_NUM_CTX,
    keep_alive=settings.llm_keep_alive,
    metadata={"ls_model_name": settings.ROUTER_MODEL, "ls_provider": "ollama"},
).with_structured_output(RewriterOutput)

_rewriter_prompt = _build_rewriter_prompt()
_rewriter_chain = _rewriter_prompt | _llm


@trace_latency("Rewriter Node", run_type="chain")
def rewriter_node(state: AgentState) -> dict[str, Any]:
    """Decompose utterance into single-intent fragments.

    Called by hybrid_router_node when the keyword detector triggers
    (condition A: >= 2 groups, or condition B: max_sim < 0.35).
    """
    user_message = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    if not user_message:
        logger.warning("Rewriter: no user message found")
        return {"fragments": []}

    query = user_message.content
    chat_history = _format_last_n_turns(state["messages"], n=2)

    try:
        result: RewriterOutput = _rewriter_chain.invoke({
            "query": query,
            "chat_history": chat_history or "No previous history.",
        })
        fragments = result.fragments or [query]
        logger.info(
            "Rewriter: decomposed into %d fragments: %s",
            len(fragments), fragments,
        )
    except (httpx.HTTPError, ConnectionError) as e:
        logger.exception("Rewriter LLM call failed: %s", e)
        fragments = [query]

    return {"fragments": fragments}
