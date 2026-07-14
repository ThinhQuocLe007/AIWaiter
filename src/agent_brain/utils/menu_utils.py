import functools
import json
import logging
import unicodedata
from typing import Dict, List, Optional, TypedDict, Iterator, Union
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
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Error loading menu names for schemas: {e}")
        return []


class _LazyMenuNames:
    """Lazy-loading proxy for the menu names list.

    Avoids eager ``get_menu_names()`` at import time — defers file I/O to
    the first actual access.  The proxy implements the full list interface
    so that ``MENU_NAMES`` behaves identically to a plain ``list[str]`` in
    all existing call sites (iteration, containment, bool, indexing,
    ``tuple()``, ``len()``, ``str()``).
    """

    def __init__(self):
        self._cache: Optional[List[str]] = None

    def _load(self) -> List[str]:
        if self._cache is None:
            self._cache = get_menu_names()
        return self._cache

    def __iter__(self) -> Iterator[str]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())

    def __bool__(self) -> bool:
        return bool(self._load())

    def __contains__(self, item: str) -> bool:
        return item in self._load()

    def __getitem__(self, index: Union[int, slice]) -> Union[str, List[str]]:
        return self._load()[index]

    def __repr__(self) -> str:
        return repr(self._load())

    def __str__(self) -> str:
        return str(self._load())


MENU_NAMES = _LazyMenuNames()


def _normalize(text: str) -> str:
    """Lowercase, strip Vietnamese diacritics and collapse whitespace for matching."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.lower().split())


@functools.lru_cache(maxsize=1)
def _get_normalized_menu() -> Dict[str, str]:
    return {_normalize(name): name for name in MENU_NAMES}


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
    norm_menu = _get_normalized_menu()

    # 1. Exact (case/diacritics-insensitive) match.
    if norm in norm_menu:
        return {"kind": "exact", "resolved": norm_menu[norm], "candidates": [norm_menu[norm]]}

    # 2. Prefix matches first (most intuitive: "Ốc Hương" -> "Ốc Hương Xốt ..."),
    #    fall back to substring matches if no prefix hit.
    prefix = [official for n, official in norm_menu.items() if n.startswith(norm)]
    candidates = prefix or [official for n, official in norm_menu.items() if norm in n]

    if len(candidates) == 1:
        return {"kind": "single", "resolved": candidates[0], "candidates": candidates}
    if len(candidates) >= 2:
        return {"kind": "ambiguous", "resolved": None, "candidates": candidates}
    return {"kind": "none", "resolved": None, "candidates": []}


# Threshold for ``find_nearest_menu_name``. Below this Jaccard similarity the
# function returns ``None`` (i.e. we don't suggest anything — the customer
# asked for something genuinely unlike the menu). 0.3 is calibrated to:
#   - "Bia Corona"      -> "Bia Sài Gòn"      (1/4 = 0.25) → NOT suggested
#   - "Pizza"           -> (no shared token)   (0.0)    → NOT suggested
# We lean conservative on the floor: better to give the rewriter an
# empty ``suggestion`` and let it apologize, than to suggest a barely-
# related item that the customer finds confusing. A higher threshold
# (e.g. 0.5) is also defensible; the trade-off is "more suggestions vs
# more accurate suggestions". The proposal uses 0.3.
MIN_JACCARD = 0.3


def find_nearest_menu_name(name: str) -> Optional[str]:
    """Token-Jaccard nearest match. Returns the menu name with the highest
    token overlap (if >= :data:`MIN_JACCARD`), else ``None``.

    Used by the validator to populate ``OffMenuItem.suggestion`` when an
    off-menu item has a near neighbor — so the rewriter can offer an
    alternative ("Bia Corona không có ạ, anh/chị có muốn thử Bia Sài
    Gòn không?") instead of just saying "không có trong thực đơn".

    Examples (with the current menu, on the date this was written):
        find_nearest_menu_name("Bia Corona")     → "Bia 333"
            (Jaccard: {bia} ∩ {bia, 333} / {bia, corona, 333} = 1/3 ≈ 0.33, >= 0.3)
        find_nearest_menu_name("Lẩu Hải Sản")   → "Gỏi Hải Sản"
            (Jaccard: {hai, san} shared = 2/4 = 0.50)
        find_nearest_menu_name("Pizza")           → None
            (no Vietnamese token match, Jaccard 0)
        find_nearest_menu_name("Phở Bò Tái")    → "Phở Bò Tái"
            (exact match after normalization)
        find_nearest_menu_name("Bia")             → "Bia 333" (or similar)
            (Bia Tiger has Jaccard 1/2 = 0.50; Bia Sài Gòn 1/3 ≈ 0.33; the
             one with the highest Jaccard wins)

    The function is O(N) over ``MENU_NAMES`` (≈210 items today) per
    call. The validator calls it at most once per off-menu item per
    turn, so the cost is negligible.
    """
    if not name or not isinstance(name, str):
        return None

    target = set(_normalize(name).split())
    if not target:
        return None

    best, best_score = None, 0.0
    for official in MENU_NAMES:
        official_tokens = set(_normalize(official).split())
        if not official_tokens:
            continue
        # Jaccard similarity: |A ∩ B| / |A ∪ B|. Tokens are
        # case- and diacritics-insensitive (via ``_normalize``).
        score = len(target & official_tokens) / len(target | official_tokens)
        if score > best_score:
            best, best_score = official, score

    return best if best_score >= MIN_JACCARD else None
