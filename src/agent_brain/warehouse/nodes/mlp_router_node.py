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

from src.agent_brain.warehouse.types import Intent
from src.agent_brain.warehouse.router.model import MLPRouter, RouterNotTrained
from src.agent_brain.warehouse.services import warehouse_info

_KW: dict[Intent, list[str]] = {
    Intent.NAVIGATE: ["đi", "tới", "đến", "dẫn", "chỉ đường", "đưa tôi", "navigate", "dắt", "ra", "vào"],
    Intent.CHAT: ["xin chào", "chào", "cảm ơn", "tạm biệt", "bạn là ai", "bạn tên", "giúp gì", "khỏe không"],
    Intent.ANSWER: [
        "ở đâu", "đâu", "vị trí", "chỗ nào", "khu nào", "lối nào", "ngăn nào", "bin nào",
        "còn", "bao nhiêu", "tồn kho", "số lượng", "hết chưa", "còn không", "còn lại",
        "nhà cung cấp", "cung cấp", "danh mục", "thuộc", "loại", "lưu ý", "bảo quản",
        "nhập thêm", "đặt thêm", "tối thiểu", "mã", "barcode", "vạch", "khu",
    ],
}

_MOVE_KW = ["đi", "tới", "đến", "dẫn", "chỉ đường", "đưa tôi", "dắt", "navigate", "ra", "vào"]

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


def route(text: str) -> tuple[Intent, float, bool]:
    """Return (intent, confidence, escalate_to_planner)."""
    t = text.lower()
    # A named place (dock, charging, qc, …) with a movement cue is always navigation.
    if any(name in t for name in warehouse_info.build_named_places()) and any(
        kw in t for kw in _MOVE_KW
    ):
        return Intent.NAVIGATE, 0.95, False
    # A section mention ("khu A", "khu B có gì") is always an information question.
    if any(f"khu {sec.lower()}" in t or f"khu {sec}" in t for sec in warehouse_info.section_names()):
        return Intent.ANSWER, 0.95, False
    intent, conf = classify(text)
    escalate = conf < PLANNER_THRESHOLD
    return intent, conf, escalate
