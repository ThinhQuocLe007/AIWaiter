"""Inject fragment-style and critical-vocabulary examples into the MLP training corpus.

The current corpus has zero fragment-shaped utterances (verbless, particle-free, 2-6 word
clauses matching what the rewriter emits) and is missing critical Vietnamese words (tôi,
xoá, xóa, giỏ hàng, quận, ship, shop).  This script generates examples covering both
gaps and appends them to the training data.

Usage:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/inject_examples.py
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/inject_examples.py --retrain
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRAINING_FILE = DATA_DIR / "synthetic_augmented.json"
OUTPUT_FILE = DATA_DIR / "synthetic_augmented.json"

# ── Fragment examples ──────────────────────────────────────────────
# Short, verbless/particle-free clauses matching what the rewriter produces
# when splitting multi-clause utterances on boundary markers.

FRAGMENT_EXAMPLES = [
    # ORDER fragments
    ("Cho 2 Ốc Hương", "ORDER"),
    ("Thêm 1 Lẩu Thái", "ORDER"),
    ("Bỏ món Ốc Hương", "ORDER"),
    ("Xoá hết giỏ hàng", "ORDER"),
    ("Xóa giỏ hàng", "ORDER"),
    ("Chốt đơn", "ORDER"),
    ("Lấy thêm 2 Bia Sài Gòn", "ORDER"),
    ("Gọi 1 phần Cơm Chiên", "ORDER"),
    ("Cho 3 Trứng Cút Lộn", "ORDER"),
    ("Đổi sang Lẩu Thái", "ORDER"),
    ("Hủy món Ốc Hương", "ORDER"),
    ("Thêm 1 phần nữa", "ORDER"),
    ("Cho tôi 1 Lẩu Cá Tầm", "ORDER"),
    ("Gọi cho tôi 2 Bia Heineken", "ORDER"),
    ("Cho mình 1 phần Gỏi Hải Sản", "ORDER"),
    ("2 Ốc Hương Xốt Trứng Muối", "ORDER"),
    ("1 Lẩu Thái với 3 Bia", "ORDER"),
    ("Xoá món Hàu Nướng", "ORDER"),
    ("Bỏ hết giỏ hàng", "ORDER"),
    ("Làm lại đơn mới", "ORDER"),
    # SEARCH fragments
    ("Có món chay không", "SEARCH"),
    ("Ốc Hương giá bao nhiêu", "SEARCH"),
    ("Còn món nào cay không", "SEARCH"),
    ("Menu có gì ngon", "SEARCH"),
    ("Có ship không", "SEARCH"),
    ("Quận 7 có giao không", "SEARCH"),
    ("Cho xem thực đơn", "SEARCH"),
    ("Có món lẩu không", "SEARCH"),
    ("Món nào best seller", "SEARCH"),
    ("Tôi muốn xem menu", "SEARCH"),
    ("Quán có món gì đặc biệt", "SEARCH"),
    ("Đồ uống có những gì", "SEARCH"),
    ("Có món nào rẻ không", "SEARCH"),
    ("Món này bao nhiêu tiền", "SEARCH"),
    ("Cho hỏi có bia không", "SEARCH"),
    # PAYMENT fragments
    ("Tính tiền", "PAYMENT"),
    ("Thanh toán", "PAYMENT"),
    ("Cho xin bill", "PAYMENT"),
    ("Tổng bao nhiêu", "PAYMENT"),
    ("Trả tiền", "PAYMENT"),
    ("Bill hết bao nhiêu", "PAYMENT"),
    ("Tính tổng giùm", "PAYMENT"),
    # CHAT fragments
    ("Cảm ơn", "CHAT"),
    ("Ngon quá", "CHAT"),
    ("Chào em", "CHAT"),
    ("Cảm ơn em", "CHAT"),
    ("Ngon thiệt", "CHAT"),
    ("Ok", "CHAT"),
    ("Tôi no quá", "CHAT"),
]

# ── Critical-vocabulary examples ──────────────────────────────────
# Full-sentence examples containing words absent from the training corpus.
# These teach the classifier the distribution of tokens it has never seen.

VOCAB_EXAMPLES = [
    # "tôi" — Vietnamese first-person pronoun
    ("Cho tôi 2 phần Ốc Hương Xốt Trứng Muối", "ORDER"),
    ("Tôi muốn gọi thêm 1 Lẩu Thái", "ORDER"),
    ("Tôi muốn xoá giỏ hàng", "ORDER"),
    ("Cho tôi xem thực đơn của quán", "SEARCH"),
    ("Tôi muốn tìm món chay", "SEARCH"),
    ("Cho tôi hỏi có món nào cay không", "SEARCH"),
    ("Tôi ở quận 7, có giao hàng không", "SEARCH"),
    ("Tính tiền cho tôi", "PAYMENT"),
    ("Cho tôi thanh toán", "PAYMENT"),
    ("Tôi cảm ơn em", "CHAT"),
    ("Cho tôi gọi 3 phần Cháo Hàu", "ORDER"),
    ("Tôi muốn đặt 1 Bia Heineken", "ORDER"),
    # "xoá"/"xóa" — delete/clear
    ("Xoá hết giỏ hàng của tôi đi", "ORDER"),
    ("Em xoá giùm món Ốc Hương", "ORDER"),
    ("Xoá đơn hàng này giúp anh", "ORDER"),
    ("Cho anh xoá hết giỏ hàng", "ORDER"),
    ("Xóa giỏ hàng rồi gọi lại từ đầu", "ORDER"),
    ("Xoá món Cháo Hàu khỏi giỏ hàng", "ORDER"),
    # "giỏ hàng" — shopping cart
    ("Cho anh xem lại giỏ hàng", "ORDER"),
    ("Giỏ hàng của tôi có những món gì", "ORDER"),
    ("Cập nhật giỏ hàng giùm em", "ORDER"),
    # "quận" — district (delivery query)
    ("Có ship về quận 7 không", "SEARCH"),
    ("Quận Gò Vấp có giao không shop", "SEARCH"),
    ("Ship về quận Tân Bình bao nhiêu tiền", "SEARCH"),
    ("Quán có giao hàng tận quận 1 không", "SEARCH"),
    ("Tôi ở quận 3, ship được không", "SEARCH"),
    # "ship" / "shop" — delivery / store
    ("Có ship không em", "SEARCH"),
    ("Phí ship bao nhiêu", "SEARCH"),
    ("Shop có giao hàng tối không", "SEARCH"),
    ("Cho hỏi shop mở cửa đến mấy giờ", "SEARCH"),
    # "thực đơn" — menu
    ("Cho anh xem thực đơn", "SEARCH"),
    ("Thực đơn hôm nay có gì mới không", "SEARCH"),
    # "gọi món" / "đặt món" — ordering
    ("Tôi muốn gọi món", "ORDER"),
    ("Cho tôi đặt món 2 phần Cơm Chiên", "ORDER"),
    ("Em ơi cho anh gọi món", "ORDER"),
    # context-dependent affirmations (short, hard cases)
    ("Ok chốt đơn đi em", "ORDER"),
    ("Ừ đúng rồi đặt luôn", "ORDER"),
    ("Ok gọi món đó cho anh", "ORDER"),
    ("Ừ lấy 2 phần đi", "ORDER"),
]

# ── Context-feature examples ───────────────────────────────────────
# The same utterance at different order_stage values, forcing the
# classifier to use context features rather than memorizing the text.

CONTEXT_EXAMPLES = [
    # "ok" at different stages
    ({"utterance": "Ok", "intent": "CHAT", "order_stage": "IDLE"}),
    ({"utterance": "Ok", "intent": "CHAT", "order_stage": "DRAFTING"}),
    ({"utterance": "Ok", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),
    # "ừ" at different stages
    ({"utterance": "Ừ", "intent": "CHAT", "order_stage": "IDLE"}),
    ({"utterance": "Ừ", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),
    # "được" at different stages
    ({"utterance": "Được", "intent": "CHAT", "order_stage": "IDLE"}),
    ({"utterance": "Được", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),
    # "chốt đơn" — always ORDER regardless of stage
    ({"utterance": "Chốt đơn đi em", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),
    ({"utterance": "Chốt đơn luôn", "intent": "ORDER", "order_stage": "DRAFTING"}),
    # "thêm" with empty cart vs with cart
    ({"utterance": "Thêm 1 phần nữa", "intent": "ORDER", "order_stage": "DRAFTING"}),
    ({"utterance": "Thêm 1 phần nữa", "intent": "CHAT", "order_stage": "IDLE"}),
    # "tính tiền" — always PAYMENT
    ({"utterance": "Tính tiền đi em", "intent": "PAYMENT", "order_stage": "AWAITING_CONFIRMATION"}),
    ({"utterance": "Tính tiền đi em", "intent": "PAYMENT", "order_stage": "IDLE"}),
]


def load_training_data():
    with open(TRAINING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_training_data(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def make_record(utterance, intent, style, source):
    return {
        "utterance": utterance,
        "intent": intent,
        "style": style,
        "source": source,
    }


def main():
    data = load_training_data()
    original_count = len(data)
    print(f"Loaded {original_count} training samples")

    new = []

    # 1. Fragment examples
    for utterance, intent in FRAGMENT_EXAMPLES:
        new.append(make_record(utterance, intent, "fragment", "manual"))
    print(f"  Fragment examples: {len(new)}")

    # 2. Critical-vocabulary examples
    before_vocab = len(new)
    for utterance, intent in VOCAB_EXAMPLES:
        new.append(make_record(utterance, intent, "critical_vocab", "manual"))
    print(f"  Vocabulary examples: {len(new) - before_vocab}")

    # 3. Context-feature examples
    before_ctx = len(new)
    for ex in CONTEXT_EXAMPLES:
        new.append(make_record(ex["utterance"], ex["intent"],
                                f"context_{ex['order_stage']}", "manual"))
    print(f"  Context examples: {len(new) - before_ctx}")

    # Count existing tokens for comparison
    all_text = " ".join(item["utterance"] for item in data)
    old_unique = len(set(all_text.split()))
    print(f"\nBefore: {original_count} samples, {old_unique} unique tokens")

    # Inject
    data.extend(new)
    save_training_data(data)

    all_text_new = " ".join(item["utterance"] for item in data)
    new_unique = len(set(all_text_new.split()))
    distinct = new_unique - old_unique
    print(f"After:  {len(data)} samples, {new_unique} unique tokens (+{distinct} new)")

    # Show new tokens
    old_tokens = set(all_text.split())
    new_tokens = set(all_text_new.split()) - old_tokens
    print(f"\nNew tokens ({len(new_tokens)}): {sorted(new_tokens)[:50]}")

    # Intent distribution
    from collections import Counter
    dist = Counter(item["intent"] for item in data)
    print(f"\nIntent distribution:")
    for intent in sorted(dist):
        print(f"  {intent}: {dist[intent]} ({dist[intent]/len(data)*100:.1f}%)")


if __name__ == "__main__":
    retrain = "--retrain" in sys.argv
    main()

    if retrain:
        print("\nRetraining classifier...")
        import subprocess
        train_script = Path(__file__).resolve().parent / "train.py"
        result = subprocess.run(
            [sys.executable, str(train_script)],
            cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )
        if result.returncode == 0:
            print("Retrain complete.")

            # Evaluate holdout
            eval_script = Path(__file__).resolve().parent.parent.parent / "evals" / "scripts"
            print("\nEvaluating holdout...")
            subprocess.run(
                [sys.executable, str(train_script.parent / "evaluate.py")],
                cwd=PROJECT_ROOT,
                env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT)},
            )
