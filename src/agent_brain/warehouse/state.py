"""Agent state passed between LangGraph nodes.

Intent/action are stored as **plain** types (str / dict) so the checkpointer never has to serialize
our custom pydantic enums/models — they're reconstructed into `ChatResponse` at the API edge.
"""

from __future__ import annotations

from typing import Optional, TypedDict


class AgentState(TypedDict, total=False):
    user_text: str
    session_id: str
    intent: Optional[str]          # "answer" | "navigate" | "control" | "chat"
    confidence: float
    routed_to_planner: bool
    # working item resolved THIS turn (reset each turn)
    item: Optional[dict]
    # last successfully resolved item — survives across turns for follow-ups ("còn bao nhiêu?")
    current_item: Optional[dict]
    # last mentioned section (e.g. after "khu A có gì") — lets "dẫn tôi đến đó" resolve to it
    current_section: Optional[str]
    candidates: list[dict]
    # The LLM decomposer's output for a complex/compound turn: a list of atomic step dicts.
    plan: list[dict]
    # One action per executed step (the executor threads state so steps share context). The single
    # `action` field carries the last one for the legacy one-command contract.
    actions: list[dict]
    reply: str
    action: Optional[dict]          # serialized Action / PositionToken
    navigated_place: Optional[str]  # human label when navigating to a named place (dock, qc, …)
    error: Optional[str]
