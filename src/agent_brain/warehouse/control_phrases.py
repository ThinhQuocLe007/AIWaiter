"""Phrase matching for run-control commands ("dừng lại", "đi tiếp", "hủy").

Deliberately dependency-free (stdlib only) because it is imported from **both** ends of the
pipeline and the two must never disagree:

  * the Jetson voice loop, which matches it on the raw STT text and fires the command over UDP
    *without waiting for the LLM* — a stop that takes four seconds to arrive is not a stop;
  * the agent's control node, which is the slow-path safety net for phrasings the fast path
    missed ("khoan đã, robot đứng lại giùm anh"), so those still stop the robot instead of
    landing in `chat` and getting a polite answer while the AGV keeps driving.

Matching runs in two tiers, and the split is not cosmetic. Stripping Vietnamese tones makes the
STT's tone slips harmless, but it also collapses **dừng** (stop), **dùng** (use) and **đúng**
(correct) onto one string. A bare `dung` rule would brake the AGV every time someone said "đúng
rồi". So the toneless tier only carries phrases that stay unambiguous without tones, and anything
resting on a single ambiguous syllable is matched on the toned text instead.

Verbs are plain strings, not the `ControlVerb` enum, so importing this never drags pydantic onto
the edge device.
"""

from __future__ import annotations

import re
import unicodedata

STOP = "stop"
RESUME = "resume"
CANCEL = "cancel"
# The scissor lift. Grouped with the run-control verbs because it shares their defining property:
# it names no location, needs no inventory lookup, and nothing the LLM could add would improve it.
# That makes it fast-path eligible — "hạ càng xuống" reaches the robot without a VPN round trip.
LIFT_UP = "lift_up"
LIFT_DOWN = "lift_down"

# Verbs that control the run in progress, as opposed to driving the manipulator. The agent maps
# these to ControlAction and the rest to LiftAction.
RUN_VERBS = (STOP, RESUME, CANCEL)

# Tier 1 — matched on text with tones stripped. Every phrase here survives the dừng/dùng/đúng
# collapse because a second token disambiguates it ("dung lai" cannot be "đúng lại").
# CANCEL is checked before STOP: "hủy chuyến, dừng lại" is an abandon, not a hold.
_FOLDED: list[tuple[str, re.Pattern]] = [
    (CANCEL, re.compile(r"\b(huy (chuyen|lenh|nhiem vu|don|bo)|bo (chuyen|lenh)|"
                        r"khoi (di|lay) nua|thoi khoi|khong lay nua|huy di)\b")),
    (STOP, re.compile(r"\b(dung lai|dung ngay lai|ngung lai|ngung ngay|dung yen|dung o do|"
                      r"dung xe lai|khoan da|khoan cai|stop|halt|phanh lai)\b")),
    (RESUME, re.compile(r"\b(di tiep|chay tiep|tiep tuc|di di|chay di|di duoc roi|thong roi|"
                        r"duong thong|het nguoi roi|resume|go on|continue)\b")),
    # Both lift rules need a second token. Toneless, "nâng" collapses onto "nặng"/"năng" and
    # "hạ" onto "hà"/"há"; "nang len" and "ha xuong" cannot be any of those.
    (LIFT_UP, re.compile(r"\b(nang (cang|len|khay|ben|bang|hang)|kich len|lift up|nang cao)\b")),
    (LIFT_DOWN, re.compile(r"\b(ha (cang|xuong|khay|ben|bang|hang)|lift down|ha thap|"
                           r"bo (hang )?xuong|tha (hang )?xuong)\b")),
]

# Tier 2 — matched on the lowercased text WITH tones, for commands that rest on one syllable.
# "dừng" only ever means stop; "dùng"/"đúng" simply never match these.
_TONED: list[tuple[str, re.Pattern]] = [
    (STOP, re.compile(r"\b(dừng|đứng lại|đỗ lại)\b")),
    (STOP, re.compile(r"^\s*khoan\b")),  # bare interjection: "Khoan!" — only at the start
]


# What the robot says back. Shared so the fast path and the agent's control node cannot drift
# into answering the same command with two different sentences — the operator would hear the
# difference and read it as the robot being confused.
REPLY: dict[str, str] = {
    STOP: "Đã dừng. Nói “đi tiếp” khi muốn chạy lại.",
    RESUME: "Đang chạy tiếp.",
    CANCEL: "Đã hủy chuyến. Robot sẽ đứng chờ lệnh mới.",
    LIFT_UP: "Đang nâng càng lên.",
    LIFT_DOWN: "Đang hạ càng xuống.",
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
    """The control verb `text` commands, or None if it is not a control command at all."""
    if not text or not text.strip():
        return None
    folded = _fold(text)
    for verb, pattern in _FOLDED:
        if pattern.search(folded):
            return verb
    toned = _strip_punct(text)
    for verb, pattern in _TONED:
        if pattern.search(toned):
            return verb
    return None
