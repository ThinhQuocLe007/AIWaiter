import json
import logging
import unicodedata
from typing import List, Optional, TypedDict
from src.agent_brain.config import settings

logger = logging.getLogger(__name__)

def get_menu_names() -> List[str]:
    """Dynamically loads menu item names from the JSON asset."""
    menu_path = settings.assets_dir / "data" / "menu.json"
    
    if not menu_path.exists():
        logger.error(f"Menu JSON file not found at {menu_path} for dynamic extraction.")
        return []
        
    try:
        with open(menu_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [item['name'] for item in data]
    except Exception as e:
        logger.error(f"Error loading menu names for schemas: {e}")
        return []

# Dynamic import-time array containing official menu items
MENU_NAMES = get_menu_names()


def _normalize(text: str) -> str:
    """Lowercase, strip Vietnamese diacritics and collapse whitespace for matching."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.lower().split())


# Precomputed normalized index: normalized_name -> official menu name.
_NORMALIZED_MENU = {_normalize(name): name for name in MENU_NAMES}


class MenuResolution(TypedDict):
    # "exact"     -> requested name is an official menu item (possibly differing only by case/diacritics)
    # "single"    -> requested name is a prefix/substring of exactly one menu item
    # "ambiguous" -> requested name matches several menu items; ask the customer which one
    # "none"      -> not on the menu at all
    kind: str
    resolved: Optional[str]   # the single official name for "exact"/"single", else None
    candidates: List[str]     # all matching official names (for "ambiguous")


def resolve_menu_name(name: str) -> MenuResolution:
    """
    Resolve a customer-spoken dish name against the menu, tolerant of case,
    diacritics and generic/partial names.

    Acceptance is no longer exact-only: a generic name that is a prefix of menu
    items (e.g. "Ốc Hương" -> 11 sauces) becomes "ambiguous" so the agent can ask
    which variant, instead of being silently dropped as "not on the menu".
    """
    if not name or not isinstance(name, str):
        return {"kind": "none", "resolved": None, "candidates": []}

    norm = _normalize(name)

    # 1. Exact (case/diacritics-insensitive) match.
    if norm in _NORMALIZED_MENU:
        return {"kind": "exact", "resolved": _NORMALIZED_MENU[norm], "candidates": [_NORMALIZED_MENU[norm]]}

    # 2. Prefix matches first (most intuitive: "Ốc Hương" -> "Ốc Hương Xốt ..."),
    #    fall back to substring matches if no prefix hit.
    prefix = [official for n, official in _NORMALIZED_MENU.items() if n.startswith(norm)]
    candidates = prefix or [official for n, official in _NORMALIZED_MENU.items() if norm in n]

    if len(candidates) == 1:
        return {"kind": "single", "resolved": candidates[0], "candidates": candidates}
    if len(candidates) >= 2:
        return {"kind": "ambiguous", "resolved": None, "candidates": candidates}
    return {"kind": "none", "resolved": None, "candidates": []}
