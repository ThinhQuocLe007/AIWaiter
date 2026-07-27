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

# --- Deterministic PAYMENT override -------------------------------------------------
# "Cho tôi thanh toán" hits BOTH the ORDER group (bare "cho") and the PAYMENT group, so
# condition A fired and a perfectly clear payment request was handed to the rewriter LLM,
# which sometimes dropped or mangled the payment fragment. But an utterance that names a
# payment ACTION and carries no real ordering signal doesn't need a model to interpret it —
# it IS payment. This pair of patterns short-circuits those turns straight to PAYMENT.
#
# Deliberately excluded: price questions ("món này bao nhiêu tiền") — those are SEARCH and
# stay with the semantic router. Only explicit payment actions belong here.
PAYMENT_STRONG = re.compile(
    r"thanh\s*to[áa]n|t[íi]nh\s*ti[ềe]n|tr[ảa]\s*ti[ềe]n|thanh\s*ton|"
    r"\bbill\b|h[óo]a\s*đơn|ho[áa]\s*đơn|"
    r"chuy[ểe]n\s*kho[ảa]n|\bck\b|m[ãa]\s*qr|qu[ée]t\s*qr|"
    r"c[àa]\s*th[ẻe]|qu[ẹe]t\s*th[ẻe]|ti[ềe]n\s*m[ặa]t|thu\s*ng[âa]n|check\s*out",
    re.IGNORECASE,
)

# A real ordering signal — an add-item verb, or a quantity glued to a classifier. Keeps
# genuine mixed turns ("cho tôi 2 phần gà rồi tính tiền") on the rewriter path instead of
# collapsing them to payment-only and silently losing the order.
_CLASSIFIERS = r"ph[ầa]n|su[ấa]t|d[ĩi]a|đ[ĩi]a|t[ôo]|ch[ée]n|ly|c[ốo]c|c[áa]i|con|chai|lon|h[ũu]"
ORDER_STRONG = re.compile(
    r"\bth[êe]m\b|\bg[ọo]i\s*(th[êe]m|m[óo]n)|\bđ[ặa]t\s*m[óo]n\b|\border\b|"
    rf"\d+\s*({_CLASSIFIERS})\b|"
    rf"\b(m[ộo]t|hai|ba|b[ốo]n|n[ăa]m|s[áa]u|b[ảa]y|t[áa]m|ch[íi]n|m[ưu][ờo]i)\s*({_CLASSIFIERS})\b",
    re.IGNORECASE,
)


def is_definite_payment(utterance: str) -> bool:
    """True when the utterance is an unambiguous payment request.

    Used by the hybrid router to route PAYMENT deterministically — no rewriter, no LLM.
    Downstream is already LLM-free (``payment_dispatch_node`` always emits
    ``request_payment``), so a True here makes "cho tôi thanh toán" open the bill every
    single time.
    """
    if not utterance:
        return False
    return bool(PAYMENT_STRONG.search(utterance)) and not ORDER_STRONG.search(utterance)


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
