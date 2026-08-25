"""Navigation worker — turns a resolved target into a position *token* (geometry-agnostic).

The brain emits only the token; the Jetson `position_parser` maps it to coordinates. This node is
the seam that absorbs future navigation richness (multi-stop, nearest-with-stock, named places).
"""

from __future__ import annotations

from src.agent_brain.warehouse.types import Action, PositionToken
from src.agent_brain.warehouse.actions import navigate_action
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.services.warehouse_data import Item


# Named, non-inventory places the worker can ask to go to (loaded from data/warehouse.json).
# Tokens are sections (e.g. "A") — the other team maps a section to coordinates.
from src.agent_brain.warehouse.services import warehouse_info
from src.agent_brain.warehouse.services.warehouse_info import build_named_places

NAMED_PLACES: dict[str, Action] = build_named_places()


def navigation_worker_node(state: AgentState) -> dict:
    # Named place? Match on either the English key or the Vietnamese label.
    text = state["user_text"].lower()
    info = warehouse_info.load_warehouse_info().get("named_places", {})
    for key, val in info.items():
        label = (val.get("label") or "").strip().lower()
        if key in text or (label and label in text):
            return {
                "action": NAMED_PLACES[key].model_dump(),
                "navigated_place": val.get("label") or key,
            }

    # Inventory target (resolved by retrieval_worker)
    item_dict = state.get("item")
    if item_dict:
        item = Item(
            **{k: (item_dict.get(k) or "") for k in ("item", "sku", "section", "aisle", "bin")},
            quantity=float(item_dict.get("quantity") or 0),
            unit=item_dict.get("unit", ""),
            desc=item_dict.get("desc", ""),
        )
        return {"action": navigate_action(item).model_dump()}

    # Follow-up pronoun ("dẫn tôi đến đó") → use the last mentioned section.
    sec = state.get("current_section")
    if sec:
        token = PositionToken(token=sec, section=sec)
        return {"action": Action(type="navigate", position=token).model_dump(), "navigated_place": f"Khu {sec}"}

    return {"action": None, "navigated_place": None}
