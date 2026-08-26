"""Which *job* a movement order carries: fetch, fetch-and-hold, drive-only, or finish a delivery.

Destination and job are separate questions. "Đi tới khu C lấy hàng" and "qua khu C thôi, đừng lấy
gì" name the same rack and mean different missions — the second is the obstacle-avoidance demo,
which drives the full route and touches nothing. `capabilities.TASKS` turns each job into the
right `pick_box.sh` flag; this module is the half that reads it out of Vietnamese.

`fetch` is the default, because that is what a warehouse order means when nobody says otherwise.
Everything here is therefore a rule for *departing* from the default, and most of those rules are
negations ("đừng lấy", "khỏi giao") — which is why order matters below.

Stdlib only, like its neighbours: the laptop's fallback parser imports it under ROS's interpreter.
"""

from __future__ import annotations

import re
import unicodedata

FETCH = "fetch"            # đi lấy rồi mang về trạm đóng gói (mặc định)
FETCH_HOLD = "fetch_hold"  # lấy xong giữ trên khay
GOTO = "goto"              # chỉ chạy tới, không gắp
DELIVER = "deliver"        # hàng đã trên khay, chạy nốt chặng về

# Somebody saying "lấy"/"gắp" is ordering a pick, which settles the question before any
# return-trip wording is considered. Without this, "đi lấy thùng bia rồi mang về" would read as
# DELIVER — and DELIVER means `--resume-delivery`, which assumes a box is *already* on the tray
# and would skip the entire outbound leg and the pick.
_PICK_CUE = re.compile(r"\b(lay|gap|boc|nhat)\b")

# Checked in order. Negations come first: "đừng mang về" contains "mang về", so a DELIVER rule
# placed above FETCH_HOLD would swallow it.
# Vietnamese has four interchangeable ways to say "don't" here, and a rule that lists only two of
# them fails on the third the one time a VIP uses it. Spell the negation once and reuse it.
_NO = r"(dung|khong|khoi|khong can|mien)"

_RULES: list[tuple[str, re.Pattern]] = [
    (GOTO, re.compile(rf"\b({_NO} (lay|gap|boc|dong vao|dong toi)|"
                      r"chi di|di thoi|di khong thoi|chay thu|di mot vong|"
                      r"chi chay|chi ghe|ghe qua thoi)\b")),
    (FETCH_HOLD, re.compile(rf"\b({_NO} (giao|mang ve|dem ve|cho ve|tra ve|dua ve)|"
                            r"giu (tren (xe|khay|ban|do)|lai|nguyen tren)|"
                            r"de tren (xe|khay))\b")),
    (DELIVER, re.compile(r"\b(mang ve|dem ve|giao ve|cho ve|mang hang ve|giao hang|"
                         r"tra hang ve|dua ve)\b")),
]


def _fold(text: str) -> str:
    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    folded = folded.replace("đ", "d")
    return " ".join(re.sub(r"[^\w\s]", " ", folded).split())


def task_of(text: str) -> str:
    """The job named in `text`, defaulting to FETCH."""
    folded = _fold(text or "")
    if not folded:
        return FETCH
    for task, pattern in _RULES:
        if pattern.search(folded):
            # A pick order outranks a return-trip phrase; see _PICK_CUE above.
            if task == DELIVER and _PICK_CUE.search(folded):
                return FETCH
            return task
    return FETCH


def is_pure_delivery(text: str) -> bool:
    """True when `text` asks to finish a delivery already in progress, naming no new target."""
    return task_of(text) == DELIVER
