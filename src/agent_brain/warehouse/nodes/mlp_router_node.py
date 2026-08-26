"""Intent router — trained MLP over Vietnamese embeddings.

A cheap keyword override handles high-precision hits; otherwise a trained `MLPRouter`
(sklearn MLP) classifies the utterance by its embedding and returns a **calibrated**
softmax probability. Below `PLANNER_THRESHOLD` we don't trust the router and escalate to
the LLM planner. Weights are produced by `src/brain.router.train` (`make train-router`)
and live in `storage/router/` (gitignored).

The classifier internals can be swapped freely — the graph only depends on `route()`.
"""

from __future__ import annotations

from typing import Optional

from src.agent_brain.warehouse import control_phrases, motion_phrases
from src.agent_brain.warehouse.types import Intent
from src.agent_brain.warehouse.router.model import MLPRouter, RouterNotTrained
from src.agent_brain.warehouse.services import warehouse_info

_KW: dict[Intent, list[str]] = {
    Intent.NAVIGATE: ["đi", "tới", "đến", "dẫn", "chỉ đường", "đưa tôi", "navigate", "dắt", "ra", "vào"],
    Intent.CHAT: ["xin chào", "chào", "cảm ơn", "tạm biệt", "bạn là ai", "bạn tên", "giúp gì", "khỏe không"],
    Intent.ANSWER: [
        "ở đâu", "đâu", "vị trí", "chỗ nào", "khu nào", "ô nào", "ngăn nào", "kệ nào", "màu gì",
        "còn", "bao nhiêu", "tồn kho", "số lượng", "hết chưa", "còn không", "còn lại",
        "nhà cung cấp", "cung cấp", "danh mục", "thuộc", "loại", "lưu ý", "bảo quản",
        "nhập thêm", "đặt thêm", "tối thiểu", "mã", "barcode", "vạch", "khu",
    ],
}

_MOVE_KW = ["đi", "tới", "đến", "dẫn", "chỉ đường", "đưa tôi", "dắt", "navigate", "ra", "vào"]

# Compound detection — fired when one utterance clearly asks for several things at once. The safe
# signal is an explicit connector ("rồi", "sau đó", "và"…): a single command like "đi lấy thùng bia"
# or "lấy bia mang về" is ONE navigate task (fetch + bring-back) and must NOT be split. Counting
# action-verb groups is deliberately avoided because navigate+fetch co-occur in one normal command.
# This runs AFTER the single-intent short-circuits (control/motion/section) so plain "đi thẳng" /
# "đi tới khu A" are never mis-flagged as compound.
_COMPOUND_CONNECTORS = ["rồi", "sau đó", "và", "luôn", "xong", "đồng thời", "thế rồi", "rồi sau"]


def _looks_compound(text: str) -> bool:
    t = text.lower()
    return any(conn in t for conn in _COMPOUND_CONNECTORS)

# Below this softmax probability we don't trust the router → send to the planner.
PLANNER_THRESHOLD = 0.5

_mlp: Optional[MLPRouter] = None


def get_router() -> MLPRouter:
    global _mlp
    if _mlp is None:
        _mlp = MLPRouter.load()
    return _mlp


def _keyword_scores(text: str) -> dict[Intent, int]:
    t = text.lower()
    return {intent: sum(kw in t for kw in kws) for intent, kws in _KW.items()}


def classify(text: str) -> tuple[Intent, float]:
    # Fast, high-precision keyword override (fixed high confidence).
    kw = _keyword_scores(text)
    kw_best, kw_score = max(kw.items(), key=lambda kv: kv[1])
    if kw_score >= 2:
        return kw_best, 0.95
    # Trained MLP with a calibrated confidence.
    return get_router().classify(text)


def _mentions_section(t: str) -> str | None:
    """Return the matched section letter if the text mentions 'khu X', else None."""
    for sec in warehouse_info.section_names():
        if f"khu {sec.lower()}" in t or f"khu {sec}" in t:
            return sec
    return None


def route(text: str) -> tuple[Intent, float, bool]:
    """Return (intent, confidence, escalate_to_planner)."""
    t = text.lower()
    # Control first, and by phrase rather than by the MLP. The classifier is trained on three
    # labels and re-training it is a separate step (`make train-router`); more importantly, a
    # stop must not depend on an embedding model being loaded and confident. `control_phrases`
    # is the same matcher the Jetson fast path uses, so both ends agree on what a stop is.
    if control_phrases.match(text) is not None:
        return Intent.CONTROL, 0.99, False
    # Compound check runs BEFORE the section/motion/navigate short-circuits. A multi-step command
    # like "khu B có gì rồi dẫn tôi tới khu B" mentions a section AND a move verb, so the rules
    # below would otherwise collapse it to NAVIGATE and silently drop the question half. Escalating
    # first lets the LLM decomposer split it into (answer + navigate). Plain single commands
    # ("đi thẳng", "đi tới khu A") carry no connector, so they are unaffected. Control stays first
    # because a "dừng lại rồi đi tiếp" must still stop instantly rather than wait for the planner.
    if _looks_compound(text):
        return Intent.PLAN, 0.5, True
    # A named place (dock, charging, qc, …) with a movement cue is always navigation.
    if any(name in t for name in warehouse_info.build_named_places()) and any(
        kw in t for kw in _MOVE_KW
    ):
        return Intent.NAVIGATE, 0.95, False
    # A section mention is navigation when it carries a movement cue ("đến/tới/dẫn khu B"),
    # but an information question when it doesn't ("khu B có gì", "khu B để mặt hàng nào").
    sec = _mentions_section(t)
    if sec is not None:
        if any(kw in t for kw in _MOVE_KW):
            return Intent.NAVIGATE, 0.95, False
        return Intent.ANSWER, 0.95, False
    # No destination named yet → a bare directional word is a motion primitive, not a (failed)
    # navigate. Checked only here so "đi tới khu A" above wins the NAVIGATE intent.
    mdir = motion_phrases.match(text)
    if mdir is not None:
        return Intent.MOTION, 0.99, False
    intent, conf = classify(text)
    escalate = conf < PLANNER_THRESHOLD
    # A complex/compound request (or one the MLP isn't confident about) goes to the LLM decomposer
    # instead of being forced into a single bucket. The decomposer breaks it into atomic steps the
    # deterministic workers already know how to run.
    if escalate:
        return Intent.PLAN, conf, True
    return intent, conf, False
