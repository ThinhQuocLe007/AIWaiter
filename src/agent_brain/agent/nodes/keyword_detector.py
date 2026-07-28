"""keyword_detector — lightweight regex-based multi-intent pre-filter.

Runs after semantic router argmax. Two-condition rewriter trigger:
  (A) >= 2 distinct intent keyword groups hit → multi-intent → invoke rewriter
  (B) max_sim < MIN_SIM_THRESHOLD (0.35) → short ambiguous text → invoke rewriter

Zero LLM. The rewriter (1 LLM) is the authoritative handler for both cases.
"""

from __future__ import annotations

import re

from src.agent_brain.agent.nodes.semantic_router_node import MIN_SIM_THRESHOLD

# Keyword groups (non-exhaustive, tuneable).
# Short ambiguous words ("ừ", "ok", "rồi", "được") are EXCLUDED from all groups —
# they hit condition B and the rewriter resolves them via chat history.
INTENT_KEYWORDS: dict[str, str] = {
    "ORDER": (
        r"cho|gọi|lấy|thêm|bỏ|cancel|hủy|xóa|đổi|thay|"
        r"đặt món|gọi món|lấy món|sửa đơn|ghi chú"
    ),
    "ORDER_CONFIRM": (
        r"chốt đơn|đặt luôn|xác nhận đặt|confirm\s*(order|đơn)"
    ),
    "SEARCH": (
        r"bao nhiêu|giá|cay không|ngon không|có.*không|nguyên liệu|"
        r"mấy giờ|ở đâu|gợi ý|wifi|toilet|vệ sinh|ship|menu|"
        r"thực đơn|best seller|so sánh|xem món|khuyến mãi"
    ),
    "PAYMENT": (
        r"tính tiền|thanh toán|bill|hóa đơn|qr|chuyển khoản|"
        r"tiền mặt|check bill|trả tiền|xuất hóa đơn|tách bill|chia đôi"
    ),
    "CHAT": (
        r"\bchào\b|\bcảm ơn\b|\btạm biệt\b|\bhello\b|\bhi\b|\bbye\b|"
        r"\bbạn là\b|\btên gì\b|\bngon quá\b|\bđẹp quá\b|\btuyệt vời\b"
    ),
}

# Compile patterns once
_compiled: dict[str, re.Pattern] = {
    intent: re.compile(pattern, re.IGNORECASE)
    for intent, pattern in INTENT_KEYWORDS.items()
}


def detect_intent_groups(utterance: str) -> set[str]:
    """Return the set of intent groups whose keywords appear in the utterance."""
    lower = utterance.lower()
    return {intent for intent, pat in _compiled.items() if pat.search(lower)}


def should_invoke_rewriter(
    utterance: str,
    max_sim: float,
) -> tuple[bool, str]:
    """Two-condition rewriter trigger.

    Returns (should_invoke, reason).
      - (True, "multi_intent")  — condition A: >= 2 keyword groups
      - (True, "low_confidence") — condition B: max_sim < MIN_SIM_THRESHOLD
      - (False, "single_intent") — single-intent, good signal
    """
    groups = detect_intent_groups(utterance)

    if len(groups) >= 2:
        return True, "multi_intent"

    if max_sim < MIN_SIM_THRESHOLD:
        return True, "low_confidence"

    return False, "single_intent"
