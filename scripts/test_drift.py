"""Test embedding drift detection on multi-intent vs single-intent utterances.

Walks through utterance word-by-word (via underthesea tokenizer), encodes each
prefix, classifies, and checks if the winning centroid shifts.

Usage:
    PYTHONPATH=. uv run python scripts/test_drift.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from underthesea import word_tokenize
from src.agent_brain.agent.nodes.semantic_router_node import SemanticRouterNode

# ── Test cases ─────────────────────────────────────────────────────────────

MULTI_INTENT = [
    ("Cho 2 Ốc Hương rồi tính tiền luôn", ["ORDER", "PAYMENT"]),
    ("Lẩu Thái cay không? Không cay thì cho mình 1 phần", ["SEARCH", "ORDER"]),
    ("Xác nhận đơn cũ và thêm 2 bia Tiger", ["ORDER_CONFIRM", "ORDER"]),
    ("Tính tiền đi, à mà món nào đang giảm giá vậy?", ["PAYMENT", "SEARCH"]),
    ("Cho mình xem qua menu rồi lấy 1 cháo hàu", ["SEARCH", "ORDER"]),
    ("Thêm 3 hàu nướng nữa rồi chốt đơn cho anh", ["ORDER", "ORDER_CONFIRM"]),
    # Extra multi-intent patterns
    ("Gọi 1 lẩu và cho hỏi có cay không?", ["ORDER", "SEARCH"]),
    ("Bỏ món mực đi rồi gọi thêm ốc hương", ["ORDER", "ORDER"]),
    ("Thanh toán đi, trước đó cho xin bill xem sao", ["PAYMENT", "PAYMENT"]),
    ("Cho 2 bia, với 1 lẩu, rồi thêm 1 gỏi", ["ORDER", "ORDER", "ORDER"]),
]

SINGLE_INTENT = [
    ("Cho tôi 2 phần Ốc Hương Xốt Trứng Muối", "ORDER"),
    ("Lấy 1 Lẩu Thái với 3 chai bia Tiger", "ORDER"),
    ("Ốc Hương giá bao nhiêu vậy?", "SEARCH"),
    ("Lẩu Thái cay không em?", "SEARCH"),
    ("Tính tiền giùm anh", "PAYMENT"),
    ("Xin chào shop", "CHAT"),
    ("Đúng rồi xác nhận đặt luôn", "ORDER_CONFIRM"),
    ("Đồ ăn ở đây ngon quá trời", "CHAT"),
    ("Mình đặt 1 Mực Cháy Tỏi với 2 ly Trà Tắc", "ORDER"),
    ("Thanh toán chuyển khoản được không?", "PAYMENT"),
]


def drift_test(utterance: str, true_intents: list[str]) -> dict:
    """Walk word-by-word and track centroid dominance shifts."""
    tokens = word_tokenize(utterance)
    if not tokens:
        return {"utterance": utterance, "tokens": [], "steps": [], "drifts": [], "detected": False}

    router = SemanticRouterNode()
    steps = []
    active = None
    drift_points = []

    for i in range(1, len(tokens) + 1):
        prefix = " ".join(tokens[:i])
        r = router.route(prefix)
        winner = max(r["all_similarities"], key=r["all_similarities"].get)
        cos = r["all_similarities"][winner]

        steps.append({
            "prefix": prefix,
            "winner": winner,
            "cos": round(cos, 4),
        })

        if active is not None and winner != active:
            drift_points.append({
                "at_index": i - 1,
                "token": tokens[i - 1],
                "from_intent": active,
                "to_intent": winner,
                "prefix_before": " ".join(tokens[:i]),
            })
        active = winner

    detected = len(drift_points) > 0
    unique_intents = list(dict.fromkeys(s["winner"] for s in steps))

    return {
        "utterance": utterance,
        "tokens": tokens,
        "steps": steps,
        "drifts": drift_points,
        "detected": detected,
        "unique_intents": unique_intents,
        "true_intents": true_intents,
        "correct": unique_intents == true_intents,
    }


def main():
    router = SemanticRouterNode()
    print("=" * 70)
    print("EMBEDDING DRIFT DETECTOR — feasibility test")
    print("=" * 70)

    tp = fp = fn = tn = 0

    # ── Multi-intent cases: should detect drift ───────────────────────
    print("\n── Multi-intent (should detect drift) ──\n")
    for utt, true in MULTI_INTENT:
        r = drift_test(utt, true)
        detected = r["detected"]
        full_result = router.route(utt)
        top = max(full_result["all_similarities"], key=full_result["all_similarities"].get)

        if true[0] != true[-1] or len(true) == 1:
            # Genuinely multi-intent (different first and last intent)
            if detected:
                tp += 1
                tag = "✓ TP"
            else:
                fn += 1
                tag = "✗ FN"
        else:
            # Same intent multiple times (like ORDER + ORDER)
            if detected:
                fp += 1
                tag = "⚠ FP (same intent repeated)"
            else:
                tn += 1
                tag = "✓ TN"
            # Correction: if all expected are same, and we detected drift but it's same-on-same, it's FP

        print(f"  {tag} \"{utt[:70]}\"")
        print(f"     True: {true} | Detected: {detected} | "
              f"Full argmax: {top} | Drift: {r['unique_intents']}")
        if r["drifts"]:
            for d in r["drifts"]:
                print(f"     ↳ '{d['token']}' → {d['from_intent']}→{d['to_intent']} "
                      f"[{d['prefix_before'][:50]}]")

    print(f"\n  Multi-intent results: TP={tp} FN={fn} FP={fp} TN={tn}")

    # ── Single-intent cases: should NOT detect drift ──────────────────
    tp_s = fp_s = 0
    print("\n── Single-intent (should NOT detect drift) ──\n")
    for utt, true in SINGLE_INTENT:
        r = drift_test(utt, [true])
        detected = r["detected"]

        if not detected:
            tp_s += 1
            tag = "✓ (no drift)"
        else:
            fp_s += 1
            tag = "✗ FP (drift detected)"

        print(f"  {tag} \"{utt[:60]}\"")
        print(f"     True: [{true}] | Drift: {detected} | Unique: {r['unique_intents']}")
        if r["drifts"]:
            for d in r["drifts"]:
                print(f"     ↳ '{d['token']}' → {d['from_intent']}→{d['to_intent']}")

    precision = tp / (tp + fp_s) * 100 if (tp + fp_s) else 0
    recall = tp / (tp + fn) * 100 if (tp + fn) else 0

    print(f"\n  Single-intent results: correct_no_drift={tp_s} false_drift={fp_s}")
    print(f"\n  OVERALL: precision={precision:.0f}% recall={recall:.0f}%")


if __name__ == "__main__":
    main()
