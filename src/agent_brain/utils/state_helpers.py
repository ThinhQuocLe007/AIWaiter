from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage

if TYPE_CHECKING:
    from src.agent_brain.agent.state import AgentState


def last_user_text(state: AgentState) -> str:
    """Return the most recent HumanMessage content, or '' if none."""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def get_worker_query(state: AgentState, intent: str) -> str:
    """Return the sub-query for this worker, or fall back to the full user text.

    For multi-intent turns the router populates ``intent_queries`` with
    per-intent sub-queries. Single-intent turns and the semantic router
    fast-track leave it as None → workers see the full original utterance.
    """
    queries = state.get("intent_queries") or {}
    sub = queries.get(intent)
    if sub:
        return sub
    return last_user_text(state)
