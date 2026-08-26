"""Laptop-side fallback: read a raw Vietnamese sentence when no structured action came with it.

The normal path never reaches this file. The Jetson asks the LLM on the home server, gets back a
`NavigateAction`/`ControlAction`, and ships that in the datagram — resolution done by a trained
router over the real inventory, phrased by the LLM, with none of it repeated here.

This exists for the case where `action` is null: the VPN is down, the home PC is asleep, or the
agent errored. Then the sentence is all the laptop has, and a demo that still drives the AGV to
Storage B beats one that stands still because a tunnel dropped. It is deliberately dumber than the
brain — substring matching over the same `data/inventory.csv`, no embeddings, no RAG — and it
declines rather than guesses.

Two things keep it from drifting away from the brain's own reading:

  * it imports `control_phrases` and `colors` directly, the same modules the agent and the Jetson
    fast path use, so "dừng lại" and "xanh dương" cannot mean three different things;
  * it reads the same CSV file, not a copy. (It parses that CSV with the stdlib rather than
    through `warehouse_data.py`, which reaches pydantic-settings through `paths.py` — this module
    has to import under ROS's system interpreter, where the project venv does not exist.)

A question is not a command. "bột mì ở đâu" resolves to nothing here: it names an item, but with
no fetch cue it is something for the brain to answer, not for the AGV to drive toward.
"""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

from src.agent_brain.warehouse import colors, control_phrases, task_phrases

INVENTORY = Path(__file__).resolve().parents[2] / "data" / "inventory.csv"

# A sentence must carry one of these to be read as an order to move. Without one we are looking at
# a question about the warehouse, which the brain answers and the robot ignores.
_MOVE_CUES = (
    "di", "toi", "den", "dan", "dat", "lay", "qua", "sang", "ve",
    "cho", "mang", "dua", "chay", "ra", "vao", "gap",
)

# Named places, keyed by the spoken label. Tokens match data/warehouse.json.
_PLACES = {
    "tram dong goi": "PACK",
    "khu dong goi": "PACK",
    "dong goi": "PACK",
    "tram sac": "DOCK",
    "cho sac": "DOCK",
}


def _fold(text: str) -> str:
    """Lowercase and strip Vietnamese tones — same normalisation the phrase matcher uses."""
    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    return " ".join(folded.replace("đ", "d").split())


def load_items(path: Path | None = None) -> list[dict]:
    """The nine boxes, straight from the CSV the brain uses. Empty list if it is unreadable."""
    src = path or INVENTORY
    try:
        with src.open(newline="", encoding="utf-8") as f:
            return [r for r in csv.DictReader(f) if (r.get("item") or "").strip()]
    except OSError:
        return []


def _has_words(haystack: str, needle: str) -> bool:
    """Is `needle` present in `haystack` as whole words? Both already folded.

    Plain `in` would find "gao" inside a longer syllable and match the wrong item.
    """
    return f" {needle} " in f" {haystack} "


def _navigate(token: str, section: str = "", slot: str = "", color: str = "",
              task: str = task_phrases.FETCH) -> dict:
    position = {"token": token}
    if section:
        position["section"] = section
    if slot:
        position["slot"] = slot
    if color:
        position["color"] = color
    return {"type": "navigate", "task": task, "position": position}


def needs_memory(sentence: str) -> bool:
    """True when `sentence` is a real order this parser structurally cannot fill in.

    Only "mang về đi" and friends qualify. `--resume-delivery` has to name the box already on the
    tray, and that fact lives in the agent's per-session memory of the previous turn. This module
    is stateless by design — one datagram in, one action out — so it declines instead of guessing
    a colour. The distinction matters in the log: "cannot" and "not a command" look the same to an
    operator and send them looking for completely different faults.
    """
    return (
        control_phrases.match(sentence) is None
        and task_phrases.task_of(sentence) == task_phrases.DELIVER
    )


def parse(sentence: str, items: list[dict] | None = None) -> dict | None:
    """Read `sentence` into the same action dict shape the agent emits, or None if it is neither
    a control command nor an order to move."""
    if not sentence or not sentence.strip():
        return None

    # 1. Immediate commands, first and unconditionally — a stop needs no fetch cue and no item,
    #    and a lift command names no destination at all.
    verb = control_phrases.match(sentence)
    if verb is not None:
        if verb in control_phrases.RUN_VERBS:
            return {"type": "control", "verb": verb}
        return {"type": "lift", "direction": verb.removeprefix("lift_")}

    task = task_phrases.task_of(sentence)
    folded = _fold(sentence)
    if not any(f" {cue} " in f" {folded} " for cue in _MOVE_CUES):
        return None

    # 2. Named place.
    for label, token in _PLACES.items():
        if label in folded:
            return _navigate(token, task=task)

    rows = items if items is not None else load_items()

    # 3. An item by name, searched with colour words removed first: "xanh dương" ends in the
    #    inventory's "Đường", so leaving colours in makes "lấy hộp xanh dương" fetch sugar.
    #    Longest name first so "trà xanh" wins over a bare "trà".
    without_color = _fold(colors.strip(sentence))
    for row in sorted(rows, key=lambda r: -len(r["item"])):
        if _has_words(without_color, _fold(row["item"])):
            return _navigate(row["section"], row["section"], row["slot"], row["color"], task)

    # 4. A colour named against a section ("qua khu C lấy hộp xanh dương").
    section = next((r["section"] for r in rows if _has_words(folded, f"khu {_fold(r['section'])}")), "")
    color = colors.parse(sentence)
    if section and color:
        hit = next((r for r in rows if r["section"] == section and r["color"] == color), None)
        if hit:
            return _navigate(section, section, hit["slot"], hit["color"], task)

    # 5. A bare section. storage_pick_mission.py accepts --storage without --color and chooses
    #    the box once it reaches the rack, so this is a complete goal, not a partial one.
    if section:
        return _navigate(section, section, task=task)

    return None
