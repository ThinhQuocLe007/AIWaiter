"""Box colours — the third coordinate of the sa bàn's addressing scheme.

Each shelf cell (A01..C03) holds one box, and the three cells of a storage are blue / red / green.
``storage_pick_mission.py`` takes the colour in English (``--color blue``), workers speak it in
Vietnamese, and replies must read back in Vietnamese, so the mapping lives here rather than being
re-spelled in every node.
"""

from __future__ import annotations

import re

# English colour (as stored in inventory.csv and consumed by the mission) → spoken Vietnamese.
COLOR_VI: dict[str, str] = {
    "blue": "xanh dương",
    "red": "đỏ",
    "green": "xanh lá",
}

# Spoken forms → the English colour. Bare "xanh" is deliberately absent: in Vietnamese it covers
# both blue and green, and every storage holds one of each, so guessing would send the robot to
# the wrong cell half the time. An unqualified "xanh" resolves to None and the item name decides.
_SPOKEN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"xanh\s*(dương|da\s*trời|biển|nước\s*biển)"), "blue"),
    (re.compile(r"xanh\s*(lá|lục|lá\s*cây)"), "green"),
    (re.compile(r"\bblue\b"), "blue"),
    (re.compile(r"\bgreen\b"), "green"),
    (re.compile(r"\bred\b"), "red"),
    (re.compile(r"\b(đỏ|do)\b"), "red"),
]


def vi(color: str | None) -> str:
    """Vietnamese name for an English colour; the input itself if we don't know it."""
    if not color:
        return ""
    return COLOR_VI.get(color.strip().lower(), color)


def strip(text: str) -> str:
    """`text` with every colour phrase removed.

    Needed because a colour phrase can contain an item name: "xanh dương" ends in "dương", which
    is the inventory's "Đường" once tones are stripped. A parser that looks for item names before
    removing colours reads "lấy hộp xanh dương" as an order to fetch sugar.
    """
    out = text.lower()
    for pattern, _color in _SPOKEN:
        out = pattern.sub(" ", out)
    return " ".join(out.split())


def parse(text: str) -> str | None:
    """The colour a worker named in `text`, or None if they named none (or an ambiguous "xanh")."""
    t = text.lower()
    for pattern, color in _SPOKEN:
        if pattern.search(t):
            return color
    return None
