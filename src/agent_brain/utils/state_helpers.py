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
