"""Navigation worker — turns a resolved target into a location *token* (geometry-agnostic).

The brain emits only the token; the ROS bridge maps it to coordinates from the sa bàn's
``semantic_tasks.yaml``. Three shapes of target, in falling order of precision:

  1. a named place ("trạm đóng gói") → token PACK / DOCK, no slot, no colour;
  2. an item the retrieval worker resolved → section + slot + colour, one exact box;
  3. a colour spoken against a section ("lấy hộp xanh dương ở khu A") → the box in that cell,
     resolved here because retrieval matches item *names* and "hộp xanh dương" is not one.

A bare section with no colour is still a valid goal: ``storage_pick_mission.py`` accepts
``--storage A`` without ``--color`` and picks the box after it reaches the rack.
"""

from __future__ import annotations

from src.agent_brain.warehouse.types import NavigateAction, PositionToken
from src.agent_brain.warehouse.colors import parse as parse_color
from src.agent_brain.warehouse.task_phrases import DELIVER, task_of
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.services.warehouse_data import Item
from src.agent_brain.warehouse.tools import live_tools

# Named, non-inventory places the worker can ask to go to (loaded from data/warehouse.json).
from src.agent_brain.warehouse.services import warehouse_info
from src.agent_brain.warehouse.services.warehouse_info import build_named_places

NAMED_PLACES: dict[str, NavigateAction] = build_named_places()

def _section_in(text: str) -> str | None:
    for sec in warehouse_info.section_names():
        if f"khu {sec.lower()}" in text or f"khu {sec}" in text:
            return sec
    return None


def _box_at(section: str, color: str) -> Item | None:
    """The single item sitting in `section`'s `color` cell, if the sa bàn has one."""
    for it in live_tools.get_data().all_items():
        if it.section == section and it.color == color:
            return it
    return None


def _action(section: str, slot: str | None, color: str | None, task: str) -> NavigateAction:
    return NavigateAction(
        position=PositionToken(token=section, section=section, slot=slot or None,
                               color=color or None),
        task=task,
    )


def navigation_worker_node(state: AgentState) -> dict:
    text = state["user_text"].lower()
    task = task_of(text)

    # "Mang về đi" — no destination named, because the destination is implied: finish the delivery
    # already in progress. The payload's identity comes from the item resolved on an earlier turn,
    # since `--resume-delivery` has to be told which box is on the tray.
    if task == DELIVER:
        carried = state.get("current_item")
        if carried and carried.get("section"):
            return {
                "action": _action(carried["section"], carried.get("slot"),
                                  carried.get("color"), task).model_dump(),
                "navigated_place": "Trạm đóng gói",
            }
        return {"action": None, "navigated_place": None,
                "reply": "Robot chưa cầm hàng nào để mang về."}

    # Named place? Match on either the English key or the Vietnamese label.
    info = warehouse_info.load_warehouse_info().get("named_places", {})
    for key, val in info.items():
        label = (val.get("label") or "").strip().lower()
        if key in text or (label and label in text):
            return {
                "action": NAMED_PLACES[key].model_dump(),
                "navigated_place": val.get("label") or key,
            }

    # Inventory target (resolved by retrieval_worker). Read the three address fields straight
    # off the dict: rebuilding a whole Item here only to hand three of its strings to _action
    # was work with no reader.
    item_dict = state.get("item")
    if item_dict and item_dict.get("section"):
        return {"action": _action(item_dict["section"], item_dict.get("slot"),
                                  item_dict.get("color"), task).model_dump()}

    # Colour spoken against a section, with no item name to resolve.
    sec = _section_in(text) or state.get("current_section")
    color = parse_color(text)
    if sec and color:
        box = _box_at(sec, color)
        if box is not None:
            return {"action": _action(sec, box.slot, box.color, task).model_dump(),
                    "item": None, "navigated_place": f"Khu {sec}"}

    # Follow-up pronoun ("dẫn tôi đến đó") → the last mentioned section, colour chosen at the rack.
    if sec:
        return {
            "action": _action(sec, None, None, task).model_dump(),
            "navigated_place": f"Khu {sec}",
        }

    return {"action": None, "navigated_place": None}
