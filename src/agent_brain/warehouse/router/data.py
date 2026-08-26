"""Training data for the intent router.

The dataset is **hand-written** in `intents.json` (natural Vietnamese warehouse
utterances, one row per example: `{"intent", "text"}`). Edit that file to add more
examples or paste in real transcripts — no code change needed. `build_dataset()`
loads and shuffles it for `train.py`.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

DATA_FILE = Path(__file__).parent / "intents.json"

VALID_INTENTS = {"answer", "navigate", "control", "chat"}


def load_handwritten() -> list[dict]:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    bad = [r for r in rows if r.get("intent") not in VALID_INTENTS]
    if bad:
        raise ValueError(f"intents.json has invalid intent(s): {bad[:3]}")
    return rows


def build_dataset(seed: int = 42) -> list[dict]:
    rows = load_handwritten()
    rnd = random.Random(seed)
    rnd.shuffle(rows)
    return rows


if __name__ == "__main__":
    rows = build_dataset()
    from collections import Counter

    print(f"{len(rows)} examples ->", dict(Counter(r["intent"] for r in rows)))
