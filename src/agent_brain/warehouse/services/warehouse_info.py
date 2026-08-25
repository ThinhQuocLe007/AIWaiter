"""Static warehouse facility info (sections + named places). No coordinates — another team maps a
section to geometry. Source: ``data/warehouse.json``."""

from __future__ import annotations

import json
from pathlib import Path

from src.agent_brain.warehouse.paths import ROOT
from src.agent_brain.warehouse.types import Action, PositionToken


WAREHOUSE_JSON = ROOT / "data" / "warehouse.json"


def load_warehouse_info() -> dict:
    if not WAREHOUSE_JSON.exists():
        return {"sections": {}, "named_places": {}}
    return json.loads(WAREHOUSE_JSON.read_text(encoding="utf-8"))


def section_names() -> set[str]:
    return set(load_warehouse_info().get("sections", {}).keys())


def build_named_places() -> dict[str, Action]:
    """Named, non-inventory places the worker can ask to go to (dock, charging, qc, …).

    Keyed by both the English key and the Vietnamese label (lowercased) so a spoken
    "cầu cảng" matches the same action as "dock".
    """
    info = load_warehouse_info()
    out: dict[str, Action] = {}
    for key, val in info.get("named_places", {}).items():
        section = val.get("section", "")
        action = Action(
            type="navigate",
            position=PositionToken(token=section, section=section or None),
        )
        out[key] = action
        label = (val.get("label") or "").strip().lower()
        if label:
            out[label] = action
    return out
