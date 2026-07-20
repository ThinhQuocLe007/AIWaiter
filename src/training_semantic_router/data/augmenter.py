from __future__ import annotations

import copy
import json
import logging
import random
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent

ORDER_STAGES = ["IDLE", "BUILDING", "AWAITING_CONFIRMATION", "CONFIRMED", "MODIFYING"]

CONTEXT_RULES: dict[str, list[dict[str, Any]]] = {
    "ORDER": [
        {"order_stage": "IDLE", "has_cart": False, "cart_size": 0, "has_search_context": False},
        {"order_stage": "IDLE", "has_cart": True, "cart_size": 3, "has_search_context": False},
        {"order_stage": "BUILDING", "has_cart": True, "cart_size": 5, "has_search_context": True},
        {"order_stage": "AWAITING_CONFIRMATION", "has_cart": True, "cart_size": 4, "has_search_context": False},
        {"order_stage": "CONFIRMED", "has_cart": True, "cart_size": 0, "has_search_context": False},
    ],
    "SEARCH": [
        {"order_stage": "IDLE", "has_cart": False, "cart_size": 0, "has_search_context": False},
        {"order_stage": "IDLE", "has_cart": True, "cart_size": 2, "has_search_context": True},
        {"order_stage": "BUILDING", "has_cart": True, "cart_size": 4, "has_search_context": True},
        {"order_stage": "AWAITING_CONFIRMATION", "has_cart": True, "cart_size": 5, "has_search_context": False},
    ],
    "PAYMENT": [
        {"order_stage": "IDLE", "has_cart": False, "cart_size": 0, "has_search_context": False},
        {"order_stage": "BUILDING", "has_cart": True, "cart_size": 6, "has_search_context": False},
        {"order_stage": "AWAITING_CONFIRMATION", "has_cart": True, "cart_size": 5, "has_search_context": False},
        {"order_stage": "CONFIRMED", "has_cart": True, "cart_size": 0, "has_search_context": False},
    ],
    "CHAT": [
        {"order_stage": "IDLE", "has_cart": False, "cart_size": 0, "has_search_context": False},
        {"order_stage": "IDLE", "has_cart": True, "cart_size": 2, "has_search_context": True},
        {"order_stage": "BUILDING", "has_cart": True, "cart_size": 4, "has_search_context": True},
        {"order_stage": "AWAITING_CONFIRMATION", "has_cart": True, "cart_size": 6, "has_search_context": False},
        {"order_stage": "CONFIRMED", "has_cart": True, "cart_size": 0, "has_search_context": False},
    ],
}

AMBI_UTTERANCES = {
    "ừ": {"AWAITING_CONFIRMATION": "ORDER", "IDLE": "CHAT", "BUILDING": "CHAT"},
    "ok": {"AWAITING_CONFIRMATION": "ORDER", "IDLE": "CHAT", "BUILDING": "CHAT"},
    "ok em": {"AWAITING_CONFIRMATION": "ORDER", "IDLE": "CHAT"},
    "được": {"AWAITING_CONFIRMATION": "ORDER", "IDLE": "CHAT", "BUILDING": "CHAT"},
    "đúng rồi": {"AWAITING_CONFIRMATION": "ORDER", "CONFIRMED": "CHAT", "IDLE": "CHAT"},
    "đúng rồi đó": {"AWAITING_CONFIRMATION": "ORDER", "IDLE": "CHAT"},
    "chuẩn": {"AWAITING_CONFIRMATION": "ORDER", "IDLE": "CHAT"},
    "đi": {"AWAITING_CONFIRMATION": "ORDER", "IDLE": "CHAT", "BUILDING": "CHAT"},
    "chốt luôn đi em": {"AWAITING_CONFIRMATION": "ORDER", "BUILDING": "ORDER", "IDLE": "ORDER"},
    "xác nhận đơn cho anh": {"any": "ORDER"},
}


def _is_ambiguous(utterance: str) -> str | None:
    """Return normalized key if utterance is ambiguous (context-dependent)."""
    normalized = utterance.lower().strip().rstrip(".,!?")
    for key in AMBI_UTTERANCES:
        if normalized in (key, key + ".", key + "!", key + "?", key + "..."):
            return key
        if normalized.startswith(key) and len(normalized) - len(key) <= 3:
            return key
    return None


def _resolve_intent_for_context(intent: str, utterance: str, ctx: dict) -> str:
    """Determine the correct intent given utterance + context.

    Most utterances keep their original intent. Only ambiguous utterances
    (short affirmations, fillers) may change based on order_stage.
    """
    ambi_key = _is_ambiguous(utterance)
    if not ambi_key:
        return intent

    mapping = AMBI_UTTERANCES[ambi_key]
    stage = ctx.get("order_stage", "IDLE")

    if "any" in mapping:
        return mapping["any"]
    return mapping.get(stage, mapping.get("IDLE", "CHAT"))


def augment(records: list[dict[str, Any]], ambi_multiplier: int = 5) -> list[dict[str, Any]]:
    """Generate context-augmented training examples.

    For each utterance, apply context variations from CONTEXT_RULES. For
    ambiguous utterances (short affirmations), generate EXTRA variations
    across all order_stages because these are the hardest to classify.
    """
    augmented: list[dict[str, Any]] = []
    random.seed(42)

    for record in records:
        utterance = record["utterance"]
        original_intent = record["intent"]
        is_ambi = _is_ambiguous(utterance) is not None
        rules = CONTEXT_RULES.get(original_intent, [{"order_stage": "IDLE", "has_cart": False, "cart_size": 0, "has_search_context": False}])

        for ctx in rules:
            resolved_intent = _resolve_intent_for_context(original_intent, utterance, ctx)
            example = {
                "utterance": utterance,
                "intent": resolved_intent,
                "original_intent": original_intent,
                "order_stage": ctx["order_stage"],
                "has_cart": ctx["has_cart"],
                "cart_size": ctx["cart_size"],
                "has_search_context": ctx["has_search_context"],
                "search_context_size": random.randint(0, 10) if ctx["has_search_context"] else 0,
                "utterance_length": len(utterance),
                "is_ambiguous": is_ambi,
            }
            augmented.append(example)

        if is_ambi:
            all_stages = ["IDLE", "BUILDING", "AWAITING_CONFIRMATION", "CONFIRMED", "MODIFYING"]
            for _ in range(ambi_multiplier):
                stage = random.choice(all_stages)
                has_cart = random.choice([True, False]) if stage in ("BUILDING", "AWAITING_CONFIRMATION") else (stage != "IDLE")
                ctx = {
                    "order_stage": stage,
                    "has_cart": has_cart,
                    "cart_size": random.randint(0, 5) if has_cart else 0,
                    "has_search_context": random.random() > 0.5,
                }
                resolved_intent = _resolve_intent_for_context(original_intent, utterance, ctx)
                example = {
                    "utterance": utterance,
                    "intent": resolved_intent,
                    "original_intent": original_intent,
                    "order_stage": ctx["order_stage"],
                    "has_cart": ctx["has_cart"],
                    "cart_size": ctx["cart_size"],
                    "has_search_context": ctx["has_search_context"],
                    "search_context_size": random.randint(0, 15) if ctx["has_search_context"] else 0,
                    "utterance_length": len(utterance),
                    "is_ambiguous": True,
                }
                augmented.append(example)

    random.shuffle(augmented)
    logger.info(
        "Augmented %d records → %d examples (%d ambiguous)",
        len(records), len(augmented),
        sum(1 for e in augmented if e["is_ambiguous"]),
    )
    return augmented


def augment_file(
    input_path: Path,
    output_path: Path | None = None,
    ambi_multiplier: int = 5,
) -> list[dict[str, Any]]:
    with open(input_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    augmented = augment(records, ambi_multiplier=ambi_multiplier)

    output_path = Path(output_path) if output_path else DATA_DIR / "synthetic_augmented.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(augmented, f, ensure_ascii=False, indent=2)

    logger.info("Saved %d augmented examples to %s", len(augmented), output_path)
    return augmented

def build_ambiguous_set(count: int = 100) -> list[dict[str, Any]]:
    """Generate additional ambiguous short utterances for training."""
    ambi_phrases = [
        ("ừ", "CHAT"),
        ("ok", "CHAT"),
        ("ok em", "CHAT"),
        ("được", "CHAT"),
        ("đi", "CHAT"),
        ("đúng rồi", "CHAT"),
        ("rành", "CHAT"),
        ("chuẩn", "CHAT"),
        ("ừm", "CHAT"),
        ("à", "CHAT"),
        ("để xem đã", "CHAT"),
        ("từ từ", "CHAT"),
        ("khoan đã", "CHAT"),
        ("à mà thôi", "CHAT"),
        ("để anh suy nghĩ tí", "CHAT"),
        ("chưa biết nữa", "CHAT"),
        ("chờ xíu", "CHAT"),
        ("ok luôn đi em", "ORDER"),
        ("chốt đi em", "ORDER"),
        ("xác nhận giùm anh", "ORDER"),
        ("đúng đơn đó rồi", "ORDER"),
        ("lên đơn đi em", "ORDER"),
        ("gọi món đó đi em", "ORDER"),
    ]

    records = []
    for phrase, default_intent in ambi_phrases:
        for _ in range(count // len(ambi_phrases)):
            stage = random.choice(ORDER_STAGES)
            has_cart = stage in ("BUILDING", "AWAITING_CONFIRMATION", "CONFIRMED")
            ctx = {
                "order_stage": stage,
                "has_cart": has_cart,
                "cart_size": random.randint(0, 5) if has_cart else 0,
                "has_search_context": random.random() > 0.5,
            }
            resolved = _resolve_intent_for_context(default_intent, phrase, ctx)
            records.append({
                "utterance": phrase,
                "intent": resolved,
                "original_intent": default_intent,
                "order_stage": ctx["order_stage"],
                "has_cart": ctx["has_cart"],
                "cart_size": ctx["cart_size"],
                "has_search_context": ctx["has_search_context"],
                "search_context_size": random.randint(0, 10) if ctx["has_search_context"] else 0,
                "utterance_length": len(phrase),
                "is_ambiguous": True,
            })

    random.shuffle(records)
    return records
