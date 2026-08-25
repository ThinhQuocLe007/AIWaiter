"""Retrieval worker — resolves the spoken item to a live record (fixed RAG + live fetch).

Sets `item` (this turn) and `current_item` (survives across turns). Also captures `current_section`
when the query mentions a section, so a later "dẫn tôi đến đó" can resolve to it. A section question
does NOT overwrite `current_item` (avoids leaving a stale/fuzzy item behind).
"""

from __future__ import annotations

from src.agent_brain.warehouse.actions import item_to_dict
from src.agent_brain.warehouse.services import warehouse_info
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.tools import live_tools


def _detect_section(text: str) -> str | None:
    t = text.lower()
    for sec in warehouse_info.section_names():
        if f"khu {sec.lower()}" in t or f"khu {sec}" in t:
            return sec
    return None


def retrieval_worker_node(state: AgentState) -> dict:
    text = state["user_text"]
    items = live_tools.resolve_item(text, k=3)
    sec = _detect_section(text)
    out: dict = {}
    if sec:
        # Talking about a section, not a (possibly fuzzy) item — do NOT leave a stale item behind.
        out["current_section"] = sec
        out["current_item"] = None
    if items and not sec:
        best = items[0]
        candidates = [
            {"sku": it.sku, "item": it.item, "section": it.section, "aisle": it.aisle, "bin": it.bin}
            for it in items
        ]
        data = item_to_dict(best)
        out.update({"item": data, "current_item": data, "candidates": candidates})
    elif not items and not sec and state.get("current_item"):
        # No new resolution: keep the previous item for follow-ups ("còn bao nhiêu?").
        out["item"] = state["current_item"]
        out["candidates"] = []
    return out
