#!/usr/bin/env python3
"""Build evaluation datasets for the single-intent MLP router architecture.

Generates three eval files:
  1. single_intent_eval.json  — ~100 single-intent cases for accuracy measurement
  2. multi_intent_detection.json — 30 multi-intent cases; metric is conf < 0.7
  3. context_dependent_eval.json — context-dependent cases with/without context

Design principles:
  - MLP is a single-intent classifier.  Multi-intent utterances should trigger
    the rewriter path (low confidence), not be scored as classification errors.
  - ORDER_CONFIRM is merged to ORDER (4-class system).
  - All utterances are spoken Vietnamese (no teencode).
  - Balanced per-class with mixed difficulty.

Usage:
    PYTHONPATH=. uv run python evals/data/router/build_eval_datasets.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# ── Single-intent evaluation cases ──────────────────────────────────
# Format: (utterance, intent, difficulty, note)

SINGLE_INTENT_CASES: list[tuple[str, str, str, str]] = []

# ORDER — 25 cases
SINGLE_INTENT_CASES += [
    # Easy — clear ordering patterns
    ("Cho tôi 2 phần Ốc Hương Xốt Trứng Muối", "ORDER", "easy", "gọi món chuẩn số lượng tên đầy đủ"),
    ("Lấy 1 Lẩu Thái với 3 chai bia Tiger", "ORDER", "easy", "gọi nhiều món, vẫn một intent"),
    ("Mình muốn gọi thêm 5 con Hàu Nướng", "ORDER", "easy", "gọi thêm + đơn vị con"),
    ("Cho 2 dĩa Khoai Tây Lắc Phô Mai nha", "ORDER", "easy", "gọi món vặt"),
    ("1 lẩu cá tầm măng chua nhe bạn", "ORDER", "easy", "số lượng đứng đầu"),
    ("Đúng rồi, xác nhận đặt luôn", "ORDER", "easy", "xác nhận đơn rõ ràng"),
    ("Ok chốt đơn đi em", "ORDER", "easy", "chốt đơn rõ ràng"),
    ("Cho em 1 phần Cháo Hàu và 2 lon Coca", "ORDER", "easy", "gọi kèm đồ uống"),
    ("Tôi muốn gọi 3 phần Sò Điệp Nướng Mỡ Hành", "ORDER", "easy", "tôi + gọi"),

    # Medium — modify/remove patterns
    ("thêm dĩa ốc bulot nữa đi", "ORDER", "medium", "thêm món không nêu số lượng rõ"),
    ("bỏ món mực chiên xù ra khỏi đơn giúp mình", "ORDER", "medium", "huỷ món"),
    ("đổi 2 bia Sài Gòn thành 2 bia 333", "ORDER", "medium", "sửa đơn thay món"),
    ("chuẩn rồi, lên đơn giúp anh", "ORDER", "medium", "xác nhận bằng cách diễn đạt khác"),
    ("Xoá hết giỏ hàng của tôi đi", "ORDER", "medium", "xoá giỏ hàng"),
    ("Xóa món Ốc Hương ra khỏi giỏ đi em", "ORDER", "medium", "xóa món"),
    ("Bỏ hết giỏ hàng rồi gọi lại từ đầu", "ORDER", "medium", "làm lại đơn"),
    ("Giảm Ốc Hương xuống còn 1 phần thôi", "ORDER", "medium", "giảm số lượng"),

    # Hard — short/ambiguous ordering
    ("nghêu", "ORDER", "hard", "chỉ tên món, ngầm hiểu là gọi"),
    ("cho Ốc Hương đi", "ORDER", "hard", "gọi món ngắn"),
    ("Ừ đặt nha", "ORDER", "hard", "xác nhận ngắn, dễ nhầm CHAT"),
    ("Cho tôi 3 phần sò huyết hấp sả", "ORDER", "hard", "dùng tôi + gọi món dài"),
    ("Làm lại đơn mới giùm anh", "ORDER", "hard", "làm lại đơn"),
    ("Dọn sạch giỏ hàng rồi bắt đầu lại", "ORDER", "hard", "dọn giỏ hàng"),
    ("Xác nhận đơn cho anh", "ORDER", "hard", "xác nhận không có từ khoá chốt"),
    ("Tôi muốn đặt 1 Bia Heineken", "ORDER", "hard", "tôi + đặt, ngắn"),
]

# SEARCH — 25 cases
SINGLE_INTENT_CASES += [
    # Easy — clear info-seeking
    ("Ốc Hương giá bao nhiêu vậy?", "SEARCH", "easy", "hỏi giá"),
    ("Quán mình có món chay không?", "SEARCH", "easy", "hỏi menu/diet"),
    ("Lẩu Thái cay không em?", "SEARCH", "easy", "hỏi tính chất món"),
    ("Quán mở cửa tới mấy giờ vậy", "SEARCH", "easy", "hỏi giờ mở cửa"),
    ("Món nào bán chạy nhất ở đây", "SEARCH", "easy", "hỏi best seller"),
    ("Cho mình xem menu với", "SEARCH", "easy", "xem menu"),
    ("Có món lẩu nào không", "SEARCH", "easy", "hỏi danh mục lẩu"),
    ("Cho tôi hỏi có bia không", "SEARCH", "easy", "hỏi đồ uống"),
    ("bia heineken bao nhiêu một lon vậy em", "SEARCH", "easy", "hỏi giá bia"),

    # Medium — specific property queries
    ("Hàu nướng có những kiểu chế biến nào?", "SEARCH", "medium", "hỏi biến thể món"),
    ("có món gì hợp cho nhóm 4 người nhậu không", "SEARCH", "medium", "gợi ý theo nhu cầu"),
    ("ốc bulot làm từ nguyên liệu gì thế", "SEARCH", "medium", "hỏi thành phần"),
    ("Có ship về quận 7 không em", "SEARCH", "medium", "hỏi ship + quận"),
    ("quán mình có chỗ đậu xe không", "SEARCH", "medium", "hỏi tiện ích"),
    ("Tôi muốn xem thực đơn của quán", "SEARCH", "medium", "tôi + xem thực đơn"),
    ("Ship về quận Tân Bình bao nhiêu tiền", "SEARCH", "medium", "hỏi phí ship quận"),
    ("Có khuyến mãi gì hôm nay không", "SEARCH", "medium", "hỏi khuyến mãi"),

    # Hard — ambiguous asking vs ordering boundary
    ("Món này giá sao vậy em", "SEARCH", "hard", "hỏi giá, dễ nhầm ORDER"),
    ("có món nào cay cay không?", "SEARCH", "hard", "hỏi lọc món, dễ nhầm ORDER"),
    ("Shop có giao hàng tối không", "SEARCH", "hard", "hỏi shop"),
    ("Tôi ở quận 3, ship được không", "SEARCH", "hard", "hỏi ship + quận"),
    ("Thực đơn hôm nay có gì mới", "SEARCH", "hard", "thực đơn không từ khóa hỏi"),
    ("Quận Gò Vấp có giao không shop", "SEARCH", "hard", "quận + shop"),
    ("Ốc Hương có mấy kiểu chế biến", "SEARCH", "hard", "hỏi kiểu, dễ nhầm ORDER tên Ốc"),
    ("Có những kiểu ốc nào ở đây", "SEARCH", "hard", "hỏi kiểu ốc"),
]

# PAYMENT — 25 cases
SINGLE_INTENT_CASES += [
    # Easy — clear payment triggers
    ("Tính tiền giùm anh", "PAYMENT", "easy", "tính tiền chuẩn"),
    ("Cho xin hóa đơn", "PAYMENT", "easy", "xin hoá đơn"),
    ("Thanh toán chuyển khoản được không?", "PAYMENT", "easy", "hỏi phương thức"),
    ("cho xin mã qr thanh toán", "PAYMENT", "easy", "xin QR"),
    ("Cho tôi thanh toán", "PAYMENT", "easy", "tôi + thanh toán"),
    ("Tính tiền đi em", "PAYMENT", "easy", "tính tiền"),
    ("Em muốn thanh toán ạ", "PAYMENT", "easy", "thanh toán lịch sự"),
    ("Cho xin bill ạ", "PAYMENT", "easy", "xin bill"),
    ("Thanh toán cho anh", "PAYMENT", "easy", "thanh toán"),

    # Medium — alternative payment phrasing
    ("Quẹt thẻ được hông em", "PAYMENT", "medium", "hỏi quẹt thẻ"),
    ("chuyển khoản cho mình xin cái mã QR với", "PAYMENT", "medium", "chuyển khoản + QR"),
    ("hết nhiêu tiền rồi em ơi", "PAYMENT", "medium", "hỏi tổng tiền"),
    ("Tính tổng thiệt hại đi em", "PAYMENT", "medium", "tổng thiệt hại"),
    ("Cho xin cái bill với", "PAYMENT", "medium", "xin bill"),
    ("Tôi muốn thanh toán", "PAYMENT", "medium", "tôi + thanh toán"),
    ("Check bill giúp mình", "PAYMENT", "medium", "check bill"),
    ("Tính tổng giùm", "PAYMENT", "medium", "tính tổng ngắn"),

    # Hard — short/unusual payment triggers
    ("bill đi em", "PAYMENT", "hard", "rất ngắn, dùng bill tiếng Anh"),
    ("Trả tiền cho anh", "PAYMENT", "hard", "trả tiền, không có từ khoá mạnh"),
    ("Tiền đâu trả đây", "PAYMENT", "hard", "hỏi trả tiền kiểu đùa"),
    ("Kiểm tra bill đi em", "PAYMENT", "hard", "kiểm tra bill"),
    ("Tính tiền mặt được không", "PAYMENT", "hard", "tiền mặt + tính tiền"),
    ("Cho em xin hoá đơn đỏ ạ", "PAYMENT", "hard", "hoá đơn đỏ"),
    ("Thanh toán cho 2 đứa riêng nha", "PAYMENT", "hard", "thanh toán riêng"),
    ("Tổng thiệt hại hết bao nhiêu", "PAYMENT", "hard", "tổng + hết bao nhiêu"),
]

# CHAT — 25 cases
SINGLE_INTENT_CASES += [
    # Easy — clear conversation
    ("Xin chào shop", "CHAT", "easy", "chào hỏi"),
    ("Cảm ơn em nhiều nha", "CHAT", "easy", "cảm ơn"),
    ("Đồ ăn ở đây ngon quá trời", "CHAT", "easy", "khen"),
    ("Dạ em chào quán ạ", "CHAT", "easy", "chào lịch sự"),
    ("Cảm ơn quán nhiều ạ", "CHAT", "easy", "cảm ơn lịch sự"),

    # Medium — casual conversation
    ("ê quán đông ghê ha", "CHAT", "medium", "tán gẫu"),
    ("Món này mặn quá em ơi", "CHAT", "medium", "chê mặn"),
    ("Lần đầu tới đây ăn nè", "CHAT", "medium", "lần đầu"),
    ("Bạn là người hay robot vậy", "CHAT", "medium", "hỏi về AI"),
    ("Tôi no quá rồi", "CHAT", "medium", "no"),
    ("Quán này mới mở hả em", "CHAT", "medium", "hỏi quán"),
    ("Ngon thiệt chứ", "CHAT", "medium", "khen"),
    ("Hôm nay quán vắng ha", "CHAT", "medium", "quán vắng"),

    # Hard — ambiguous: could be ORDER in different context
    ("trời hôm nay mưa to thật", "CHAT", "hard", "lạc đề hoàn toàn"),
    ("Để anh suy nghĩ tí đã", "CHAT", "hard", "suy nghĩ - KHÔNG phải ORDER"),
    ("Từ từ đi em", "CHAT", "hard", "từ từ - KHÔNG phải ORDER"),
    ("Khoan đã đừng gọi vội", "CHAT", "hard", "khoan - dễ nhầm ORDER"),
    ("À mà thôi", "CHAT", "hard", "đổi ý - dễ nhầm ORDER"),
    ("Chưa biết nữa để tính sau", "CHAT", "hard", "chưa quyết định"),
    ("Chờ xíu nha", "CHAT", "hard", "chờ - dễ nhầm ORDER"),
    ("Để coi đã", "CHAT", "hard", "để coi - dễ nhầm SEARCH"),
    ("Thôi kệ đi", "CHAT", "hard", "thôi kệ"),
    ("Có gì vui kể nghe đi", "CHAT", "hard", "tán gẫu, dễ nhầm SEARCH"),
    ("Tôi cảm ơn em", "CHAT", "hard", "tôi + cảm ơn ngắn"),
    ("Em nói chuyện dễ thương ghê", "CHAT", "hard", "khen AI, dễ nhầm SEARCH hỏi về AI"),
]


# ── Multi-intent detection cases ────────────────────────────────────
# Format: (utterance, expected_intents_list, difficulty, note)
# Metric: does MLP produce confidence < 0.7?  (Not: which intent did it guess?)

MULTI_INTENT_CASES: list[tuple[str, list[str], str, str]] = []

# ORDER + PAYMENT — "gọi món rồi thanh toán"
MULTI_INTENT_CASES += [
    ("Cho 2 Ốc Hương rồi tính tiền luôn", ["ORDER", "PAYMENT"], "easy", "gọi món rồi thanh toán"),
    ("Thêm 3 bia Tiger rồi bill luôn nha", ["ORDER", "PAYMENT"], "easy", "thêm rồi bill"),
    ("Lấy 1 Lẩu Thái rồi thanh toán cho anh", ["ORDER", "PAYMENT"], "easy", "gọi rồi thanh toán"),
    ("Xác nhận đơn cũ và thanh toán luôn", ["ORDER", "PAYMENT"], "easy", "xác nhận + thanh toán"),
    ("Gọi thêm 1 phần xong tính tiền", ["ORDER", "PAYMENT"], "easy", "gọi xong tính tiền"),
    ("Cho 2 hàu nướng và tính tiền giùm anh", ["ORDER", "PAYMENT"], "medium", "gọi và tính tiền"),
    ("Xoá món cũ rồi thanh toán tổng luôn", ["ORDER", "PAYMENT"], "medium", "xoá rồi thanh toán"),
    ("Chốt đơn với bill luôn đi em", ["ORDER", "PAYMENT"], "hard", "chốt đơn + bill, gộp sát"),
]

# SEARCH + ORDER — "hỏi trước, gọi món có điều kiện"
MULTI_INTENT_CASES += [
    ("Lẩu Thái cay không? Không cay thì cho mình 1 phần", ["SEARCH", "ORDER"], "easy", "hỏi trước rồi gọi có điều kiện"),
    ("Ốc Hương giá bao nhiêu rồi lấy 2 phần luôn", ["SEARCH", "ORDER"], "easy", "hỏi giá rồi gọi"),
    ("Có món chay không? Có thì cho 2 phần", ["SEARCH", "ORDER"], "easy", "hỏi menu rồi gọi"),
    ("Cho mình xem menu rồi lấy 1 cháo hàu", ["SEARCH", "ORDER"], "easy", "xem menu rồi gọi món"),
    ("Món nào ngon, gợi ý rồi gọi cho 2 phần luôn", ["SEARCH", "ORDER"], "medium", "gợi ý rồi gọi"),
    ("Hàu nướng có những kiểu nào? Cho mình kiểu phô mai với 1 phần", ["SEARCH", "ORDER"], "medium", "hỏi kiểu rồi gọi"),
    ("Có Lẩu Cá Tầm không vậy, có thì cho 1 phần", ["SEARCH", "ORDER"], "medium", "hỏi có rồi gọi"),
    ("Món nào best seller, lấy 2 món đó cho anh", ["SEARCH", "ORDER"], "medium", "best seller rồi gọi"),
]

# ORDER + CHAT — "gọi món + tán gẫu"
MULTI_INTENT_CASES += [
    ("Cho 2 ốc hương, à mà quán đẹp ghê ha", ["ORDER", "CHAT"], "medium", "gọi món + khen quán"),
    ("Thêm 3 bia, mà quán đông quá hén", ["ORDER", "CHAT"], "medium", "gọi + tán gẫu"),
    ("Cảm ơn em, cho anh xin bill luôn nha", ["CHAT", "PAYMENT"], "medium", "cảm ơn + bill"),
    ("Gọi 1 lẩu thái nha, trời mưa ăn lẩu là đúng bài", ["ORDER", "CHAT"], "hard", "gọi + tán gẫu thời tiết"),
]

# PAYMENT + SEARCH — "thanh toán + hỏi thêm"
MULTI_INTENT_CASES += [
    ("Tính tiền đi, à mà món nào đang giảm giá vậy?", ["PAYMENT", "SEARCH"], "easy", "thanh toán trước rồi hỏi khuyến mãi"),
    ("Bill hết bao nhiêu, với ship về quận 7 không?", ["PAYMENT", "SEARCH"], "medium", "bill + hỏi ship"),
    ("Thanh toán rồi cho mình xin cái menu mang về nha", ["PAYMENT", "SEARCH"], "medium", "thanh toán + xin menu"),
    ("Tính tiền xong cho hỏi quán mở cửa tới mấy giờ", ["PAYMENT", "SEARCH"], "medium", "thanh toán + hỏi giờ"),
]

# Three+ intents
MULTI_INTENT_CASES += [
    ("Cho mình xem menu rồi lấy 1 cháo hàu xong tính tiền luôn", ["SEARCH", "ORDER", "PAYMENT"], "hard", "3 intents: xem + gọi + tính tiền"),
    ("Món này ngon quá, cho thêm 1 phần rồi bill luôn nha em", ["CHAT", "ORDER", "PAYMENT"], "hard", "3 intents: khen + gọi + bill"),
    ("Cảm ơn em, cho hỏi có ship quận 7 không rồi tính tiền luôn", ["CHAT", "SEARCH", "PAYMENT"], "hard", "3 intents: cảm ơn + hỏi + tính tiền"),
]

# Edge cases — one intent disguises as two
MULTI_INTENT_CASES += [
    ("Tính tiền rồi cho anh cái bill", ["PAYMENT"], "hard", "tính tiền + bill, thực chất cùng intent"),
    ("Cho xem thực đơn với menu có gì ngon", ["SEARCH"], "hard", "thực đơn + menu, thực chất cùng intent"),
    ("Gọi 2 ốc hương và lấy thêm 3 bia", ["ORDER"], "hard", "gọi + lấy thêm, vẫn cùng ORDER"),
]

# ── Context-dependent evaluation cases ──────────────────────────────
# Format: (utterance, intent_with_context, intent_without_context, context, difficulty, note)

CONTEXT_DEPENDENT_CASES: list[dict] = []  # Will be built inline

CONTEXT_DEPENDENT = [
    # Same utterance, different intent based on order_stage
    {
        "id": "CD-001", "utterance": "ok",
        "intent": "CHAT", "order_stage": "IDLE",
        "note": "Không có đơn hàng → CHAT",
    },
    {
        "id": "CD-002", "utterance": "ok",
        "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Đang chờ xác nhận → ORDER",
    },
    {
        "id": "CD-003", "utterance": "ừ",
        "intent": "CHAT", "order_stage": "IDLE",
        "note": "Gật gù không ngữ cảnh → CHAT",
    },
    {
        "id": "CD-004", "utterance": "ừ",
        "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Đang chờ xác nhận → ORDER",
    },
    {
        "id": "CD-005", "utterance": "đúng rồi",
        "intent": "CHAT", "order_stage": "IDLE",
        "note": "Khẳng định ở IDLE → CHAT",
    },
    {
        "id": "CD-006", "utterance": "đúng rồi",
        "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Xác nhận đơn → ORDER",
    },
    {
        "id": "CD-007", "utterance": "được",
        "intent": "CHAT", "order_stage": "IDLE",
        "note": "Được ở IDLE → CHAT",
    },
    {
        "id": "CD-008", "utterance": "được",
        "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Đồng ý xác nhận đơn → ORDER",
    },
    {
        "id": "CD-009", "utterance": "ok em",
        "intent": "CHAT", "order_stage": "IDLE",
        "note": "Không có đơn → CHAT",
    },
    {
        "id": "CD-010", "utterance": "ok em",
        "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Xác nhận đơn → ORDER, dễ nhầm CHAT",
    },
    {
        "id": "CD-011", "utterance": "thêm 1 phần nữa",
        "intent": "CHAT", "order_stage": "IDLE",
        "note": "Không có giỏ hàng → CHAT",
    },
    {
        "id": "CD-012", "utterance": "thêm 1 phần nữa",
        "intent": "ORDER", "order_stage": "BUILDING",
        "note": "Có giỏ hàng đang soạn → ORDER",
    },
    {
        "id": "CD-013", "utterance": "tính tiền đi",
        "intent": "PAYMENT", "order_stage": "IDLE",
        "note": "Yêu cầu thanh toán, không phụ thuộc ngữ cảnh",
    },
    {
        "id": "CD-014", "utterance": "tính tiền đi",
        "intent": "PAYMENT", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Tính tiền vẫn là PAYMENT, không đổi theo context",
    },
    {
        "id": "CD-015", "utterance": "chưa muốn đâu",
        "intent": "CHAT", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Từ chối xác nhận → CHAT, không phải ORDER",
    },
    {
        "id": "CD-016", "utterance": "Uh đúng rồi đó",
        "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Xác nhận đơn ở ngữ cảnh chờ xác nhận",
    },
    {
        "id": "CD-017", "utterance": "chuẩn",
        "intent": "CHAT", "order_stage": "IDLE",
        "note": "Chuẩn ở IDLE → CHAT",
    },
    {
        "id": "CD-018", "utterance": "chuẩn",
        "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Xác nhận đơn → ORDER",
    },
    {
        "id": "CD-019", "utterance": "Ok chốt đơn đi em",
        "intent": "ORDER", "order_stage": "IDLE",
        "note": "Chốt đơn luôn là ORDER, không cần context",
    },
    {
        "id": "CD-020", "utterance": "Ok chốt đơn đi em",
        "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION",
        "note": "Chốt đơn luôn là ORDER, không đổi",
    },
]


# ═══════════════════════════════════════════════════════════════════════
def build_single_intent() -> list[dict]:
    cases = []
    seen = set()
    for utterance, intent, difficulty, note in SINGLE_INTENT_CASES:
        key = utterance.lower().strip().rstrip(".?!")
        if key in seen:
            continue
        seen.add(key)
        cases.append({
            "utterance": utterance,
            "intent": intent,
            "difficulty": difficulty,
            "note": note,
        })
    return cases


def build_multi_intent_detection() -> list[dict]:
    cases = []
    for utterance, intents, difficulty, note in MULTI_INTENT_CASES:
        cases.append({
            "utterance": utterance,
            "intents": intents,
            "difficulty": difficulty,
            "note": note,
        })
    return cases


def build_context_dependent() -> list[dict]:
    cases = []
    for item in CONTEXT_DEPENDENT:
        ctx = {
            "order_stage": item["order_stage"],
            "has_cart": item["order_stage"] in ("BUILDING", "AWAITING_CONFIRMATION", "CONFIRMED", "MODIFYING"),
            "cart_size": 3 if item["order_stage"] in ("BUILDING", "AWAITING_CONFIRMATION") else 0,
            "has_search_context": False,
            "search_context_size": 0,
        }
        cases.append({
            "id": item["id"],
            "utterance": item["utterance"],
            "intent": item["intent"],
            "context": ctx,
            "difficulty": item.get("difficulty", "medium"),
            "note": item["note"],
        })
    return cases


def print_stats(cases: list[dict], label: str, intent_key: str = "intent"):
    from collections import Counter
    intents = Counter(c.get(intent_key, "?") if isinstance(c.get(intent_key), str) else str(c.get(intent_key)) for c in cases)
    difficulties = Counter(c.get("difficulty", "?") for c in cases)
    print(f"\n{label}: {len(cases)} cases")
    for i in sorted(intents):
        print(f"  {i}: {intents[i]}")
    for d in sorted(difficulties):
        print(f"  {d}: {difficulties[d]}")


def main():
    single = build_single_intent()
    multi = build_multi_intent_detection()
    ctx = build_context_dependent()

    print_stats(single, "Single-intent accuracy eval")
    print_stats(multi, "Multi-intent detection eval", "intents")
    print_stats(ctx, "Context-dependent eval")

    # Write files
    for name, data in [
        ("single_intent_eval.json", single),
        ("multi_intent_detection.json", multi),
        ("context_dependent_eval.json", ctx),
    ]:
        out = OUT_DIR / name
        with open(out, "w", encoding="utf-8") as f:
            json.dump({
                "dataset": name.replace(".json", ""),
                "version": "1.0",
                "description": {
                    "single_intent_eval.json": "Single-intent accuracy benchmark. MLP classifies each utterance into ORDER/SEARCH/PAYMENT/CHAT. Context features are not used.",
                    "multi_intent_detection.json": "Multi-intent detection benchmark. Metric: fraction of cases where MLP confidence < 0.7. The correct response to multi-intent input is the rewriter path, not a single-label guess.",
                    "context_dependent_eval.json": "Context-dependent evaluation. Same utterance evaluated with different order_stage context features. Tests whether the MLP uses context features.",
                }[name],
                "total_cases": len(data),
                "cases": data,
            }, f, ensure_ascii=False, indent=2)
        print(f"Wrote {out}")

    print(f"\nDone. Files in {OUT_DIR}")


if __name__ == "__main__":
    main()
