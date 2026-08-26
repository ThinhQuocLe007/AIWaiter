"""Static warehouse facility info (sections + named places). No coordinates — the ROS bridge maps a
token to geometry. Source: ``data/warehouse.json``.

Sections A/B/C are the sa bàn's ``storage_A/B/C``. Named places carry their own token ("PACK",
"DOCK") because ``packing_station`` and the charging dock sit in no rack section at all — giving
them a fake section would make the validator accept a goal the bridge cannot resolve.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.agent_brain.warehouse.paths import ROOT
from src.agent_brain.warehouse.types import NavigateAction, PositionToken


WAREHOUSE_JSON = ROOT / "data" / "warehouse.json"


def load_warehouse_info() -> dict:
    if not WAREHOUSE_JSON.exists():
        return {"sections": {}, "named_places": {}}
    return json.loads(WAREHOUSE_JSON.read_text(encoding="utf-8"))


def section_names() -> set[str]:
    return set(load_warehouse_info().get("sections", {}).keys())


def build_named_places() -> dict[str, NavigateAction]:
    """Named, non-inventory places the worker can ask to go to (trạm đóng gói, trạm sạc).

    Keyed by both the English key and the Vietnamese label (lowercased) so a spoken
    "trạm sạc" matches the same action as "dock".
    """
    info = load_warehouse_info()
    out: dict[str, NavigateAction] = {}
    for key, val in info.get("named_places", {}).items():
        token = (val.get("token") or key).strip().upper()
        action = NavigateAction(position=PositionToken(token=token))
        out[key] = action
        label = (val.get("label") or "").strip().lower()
        if label:
            out[label] = action
    return out
