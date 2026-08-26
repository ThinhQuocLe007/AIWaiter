"""Phrase matching for motion primitives ("đi thẳng", "lùi", "quẹo trái", "quẹo phải").

Deliberately dependency-free (stdlib only) because it is imported from **both** ends of the
pipeline and the two must never disagree:

  * the Jetson voice loop, which matches it on the raw STT text and fires the pulse over UDP
    *without waiting for the LLM* — a direction spoken to a parked robot should move it now;
  * the agent's motion worker, which is the slow-path safety net for phrasings the fast path
    missed, so those still move the robot instead of landing in `chat`.

Matching runs in two tiers. The toneless tier only carries multi-token phrases, because collapsing
Vietnamese tones would otherwise merge "tiến" (forward) onto "tiền"/"tiếng". The toned tier holds
the short single-syllable commands ("trái!", "phải!") that stay unambiguous with tones intact.

Crucially, the motion vocabulary **deliberately avoids destination verbs** ("tới", "đến", "đi tới
khu …"): those belong to `navigate`, and `route()` checks the section/place cues *before* motion so
"đi tới khu A" resolves to NAVIGATE, not a forward pulse.
"""

from __future__ import annotations

import re
import unicodedata

FORWARD = "forward"
BACK = "back"
LEFT = "left"
RIGHT = "right"

# Tier 1 — matched on text with tones stripped. Every phrase here needs a second token so it
# survives the tone collapse and can't be confused with a navigate verb.
_FOLDED: list[tuple[str, re.Pattern]] = [
    (FORWARD, re.compile(r"\b(di thang|thang|tien len|tien toi|di toi phia truoc|tien phia truoc|"
                         r"move forward|go straight|forward)\b")),
    (BACK, re.compile(r"\b(di lui|lui lai|lui xuong|di luoi|reverse|back up|backward|di sau)\b")),
    (LEFT, re.compile(r"\b(queo trai|re trai|quay trai|sang trai|turn left|left)\b")),
    (RIGHT, re.compile(r"\b(queo phai|re phai|quay phai|sang phai|turn right|right)\b")),
]

# Tier 2 — matched on the lowercased text WITH tones, for short one-word commands. These syllables
# are unambiguous in Vietnamese, so keeping their tones makes them safe as bare words.
_TONED: list[tuple[str, re.Pattern]] = [
    (FORWARD, re.compile(r"\b(thẳng)\b")),
    (BACK, re.compile(r"\b(lùi)\b")),
    (LEFT, re.compile(r"\b(trái)\b")),
    (RIGHT, re.compile(r"\b(phải)\b")),
]


# What the robot says back. Shared so the fast path and the agent's motion node cannot drift into
# answering the same command with two different sentences.
REPLY: dict[str, str] = {
    FORWARD: "Đang đi thẳng.",
    BACK: "Đang lùi lại.",
    LEFT: "Đang quẹo trái.",
    RIGHT: "Đang quẹo phải.",
}


def _fold(text: str) -> str:
    """Lowercase, strip Vietnamese tones, collapse punctuation and whitespace."""
    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    folded = folded.replace("đ", "d")
    folded = re.sub(r"[^\w\s]", " ", folded)
    return " ".join(folded.split())


def _strip_punct(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE).split())


def match(text: str) -> str | None:
    """The motion direction `text` commands, or None if it is not a motion command at all."""
    if not text or not text.strip():
        return None
    folded = _fold(text)
    for direction, pattern in _FOLDED:
        if pattern.search(folded):
            return direction
    toned = _strip_punct(text)
    for direction, pattern in _TONED:
        if pattern.search(toned):
            return direction
    return None
