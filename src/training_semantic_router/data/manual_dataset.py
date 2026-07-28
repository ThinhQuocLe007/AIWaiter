#!/usr/bin/env python3
"""Manually curated intent-classification dataset for the MLP router.

Every utterance is hand-written against the real menu (assets/data/menu.json).
No LLM generation — full control over quality, vocabulary coverage, and
intent boundaries.

Design targets (based on eval weaknesses from collected-results.md):
  1. CHAT (F1=0.792):  heavy on casual/edge/ambiguous utterances to reduce
     the 5/29 CHAT→ORDER confusion.
  2. SEARCH (F1=0.857):  clear separation between price-inquiry (SEARCH) and
     payment-request (PAYMENT); strong coverage of "tôi", "quận", "ship".
  3. Fragment style:  verbless, particle-free clauses matching the rewriter's
     output shape, so multi-intent turns route correctly.
  4. PAYMENT (F1=0.898):  already strong; maintain with diverse trigger vocab.

Usage:
    # Save raw dataset only:
    PYTHONPATH=. uv run python src/training_semantic_router/data/manual_dataset.py

    # Save raw + augment + retrain:
    PYTHONPATH=. uv run python src/training_semantic_router/data/manual_dataset.py --augment --retrain
"""  # noqa: E501

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = Path(__file__).resolve().parent
RAW_OUTPUT = DATA_DIR / "synthetic_raw.json"

# ═══════════════════════════════════════════════════════════════════════
# MANUAL DATASET — edit these lists freely.  Format:
#   (utterance, intent, style, [notes])
# intents: ORDER | SEARCH | PAYMENT | CHAT
# styles:  formal | casual | dialect | edge | fragment
# ═══════════════════════════════════════════════════════════════════════

MANUAL_UTTERANCES: list[tuple[str, str, str, str]] = []

# ── ORDER / formal ───────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Cho em 2 phần Ốc Hương Xốt Trứng Muối ạ", "ORDER", "formal", "gọi món lịch sự đầy đủ"),
    ("Dạ cho em gọi 1 Lẩu Thái và 3 chai Bia Saigon ạ", "ORDER", "formal", "gọi nhiều món kèm bia"),
    ("Em muốn đặt 1 phần Hàu Nướng Phô Mai ạ", "ORDER", "formal", "đặt món với chủ ngữ"),
    ("Cho em xin 2 phần Tôm Thẻ Xốt Me ạ", "ORDER", "formal", "xin món lịch sự"),
    ("Dạ vui lòng cho em 1 phần Sò Điệp Nướng Mỡ Hành ạ", "ORDER", "formal", "rất lịch sự"),
    ("Em xin gọi thêm 1 phần Mì Xào Sò ạ", "ORDER", "formal", "gọi thêm"),
    ("Cho em hỏi, em có thể gọi thêm 2 Trứng Cút Lộn được không ạ", "ORDER", "formal", "hỏi để gọi thêm"),
    ("Dạ cho em đặt 1 phần Mực Cháy Tỏi và 1 Gỏi Xoài Bạch Tuộc ạ", "ORDER", "formal", "đặt nhiều món"),
    ("Làm ơn cho em xoá món Ốc Hương Xốt Phô Mai khỏi đơn ạ", "ORDER", "formal", "xoá món lịch sự"),
    ("Em muốn huỷ món Chả Giò Hải Sản và đổi sang Chả Cá Thác Lác ạ", "ORDER", "formal", "huỷ và đổi món"),
    ("Cho em xin 1 phần Lẩu Cá Tầm Măng Chua ạ", "ORDER", "formal", "gọi lẩu"),
    ("Dạ em muốn thêm 2 lon Coca vào giỏ hàng ạ", "ORDER", "formal", "thêm đồ uống"),
    ("Cho em xin 1 phần Ốc Len Xào Dừa ạ", "ORDER", "formal", "gọi món ốc"),
    ("Em muốn giảm Ốc Hương Xốt Muối Tắc xuống còn 1 phần ạ", "ORDER", "formal", "giảm số lượng"),
    ("Dạ cho em sửa đơn, bỏ món Nghêu Hấp Sả và thêm 1 Cháo Hàu ạ", "ORDER", "formal", "sửa đơn"),
    ("Cho em xin 2 phần Cơm Chiên Hải Sản ạ", "ORDER", "formal", "gọi cơm"),
    ("Em muốn gọi 1 phần Gỏi Xoài Ốc Giác và 2 Bia Tiger ạ", "ORDER", "formal", "gọi kèm bia"),
    ("Dạ cho em đặt 3 phần Ốc Hương Xốt Bơ Cay ạ", "ORDER", "formal", "đặt số lượng lớn"),
    ("Xin phép cho em gọi 1 phần Cua Rang Me ạ", "ORDER", "formal", "xin phép gọi món"),
    ("Em muốn thêm 1 phần Sò Huyết Hấp Sả vào đơn ạ", "ORDER", "formal", "thêm vào đơn"),
]

# ── ORDER / casual ───────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Cho 2 ốc hương đi em", "ORDER", "casual", "gọi món tự nhiên"),
    ("Lấy 1 lẩu thái với 3 chai bia", "ORDER", "casual", "lấy món ngắn gọn"),
    ("Gọi thêm 5 con hàu nướng nha", "ORDER", "casual", "gọi thêm casual"),
    ("Cho mình 2 dĩa khoai tây lắc phô mai", "ORDER", "casual", "dùng mình"),
    ("Bỏ món mực chiên sả ra khỏi đơn giúp mình", "ORDER", "casual", "bỏ món"),
    ("Đổi 2 bia saigon thành 2 bia 333 đi", "ORDER", "casual", "đổi món"),
    ("Thêm dĩa ốc bulot nữa", "ORDER", "casual", "thêm không nêu số lượng rõ"),
    ("Cho tôi 2 phần ốc hương xốt trứng muối", "ORDER", "casual", "dùng tôi"),
    ("1 lẩu cá tầm măng chua luôn nha", "ORDER", "casual", "số lượng đứng đầu"),
    ("Xoá hết giỏ hàng của tôi đi", "ORDER", "casual", "xoá giỏ hàng"),
    ("Xóa món ốc hương ra khỏi giỏ đi em", "ORDER", "casual", "xóa món"),
    ("Bỏ hết giỏ hàng rồi gọi lại từ đầu", "ORDER", "casual", "làm lại đơn"),
    ("Làm lại đơn mới giùm anh", "ORDER", "casual", "làm lại"),
    ("Giảm ốc hương xuống còn 1 phần thôi", "ORDER", "casual", "giảm số lượng"),
    ("Thêm 2 bia tiger với 1 trà tắc", "ORDER", "casual", "thêm đồ uống"),
    ("Cho anh 3 phần tôm thẻ xốt me", "ORDER", "casual", "gọi món"),
    ("Lấy 1 cháo hàu với 1 mì xào sò", "ORDER", "casual", "gọi nhiều món"),
    ("Tôi muốn gọi thêm 1 phần sò điệp nướng", "ORDER", "casual", "dùng tôi"),
    ("Cho mình 1 gỏi xoài bạch tuộc với 2 bia heineken", "ORDER", "casual", "dùng mình"),
    ("Hủy món chả giò hải sản dùm em", "ORDER", "casual", "hủy món"),
    ("Dọn sạch giỏ hàng rồi bắt đầu lại", "ORDER", "casual", "dọn giỏ hàng"),
    ("Ok chốt đơn đi em", "ORDER", "casual", "chốt đơn"),
    ("Lên đơn giúp anh", "ORDER", "casual", "lên đơn"),
    ("Xác nhận đặt luôn nhé", "ORDER", "casual", "xác nhận"),
    ("Ừ đặt luôn đi em", "ORDER", "casual", "xác nhận ngắn"),
]

# ── ORDER / dialect ──────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Cho anh 2 phần ốc hương xốt trứng muối nghen", "ORDER", "dialect", "Nam Bộ nghen"),
    ("Lấy 1 lẩu thái hông hành nha em", "ORDER", "dialect", "Nam Bộ hông"),
    ("Mình kêu 3 con hàu nướng phô mai đi", "ORDER", "dialect", "Nam Bộ kêu"),
    ("Cho chị 2 phần tôm thẻ xốt me nha", "ORDER", "dialect", "miền Nam điệu đà"),
    ("Bỏ món mực cháy tỏi dùm chị nghen", "ORDER", "dialect", "Nam Bộ dùm nghen"),
    ("Xoá hết giỏ hàng dùm anh cái coi", "ORDER", "dialect", "Nam Bộ cái coi"),
    ("Thêm 1 bia saigon vô nghen em", "ORDER", "dialect", "Nam Bộ vô"),
    ("Cho anh 1 phần ốc len xào dừa nghen", "ORDER", "dialect", "Nam Bộ nghen"),
    ("Tính ra đơn cũ sai rồi, gọi lại từ đầu nghen", "ORDER", "dialect", "làm lại"),
    ("Ủa gọi lộn rồi, bỏ món đó đi em", "ORDER", "dialect", "Nam Bộ ủa"),
    ("Cho anh 1 lẩu khổ qua cá thác lác nghen", "ORDER", "dialect", "gọi lẩu Nam Bộ"),
    ("Kêu thêm 1 phần sò huyết hấp sả nha", "ORDER", "dialect", "kêu thêm"),
    ("Đổi món này qua món kia dùm anh", "ORDER", "dialect", "đổi món Nam Bộ"),
    ("Tăng sò điệp lên 3 phần dùm em nghen", "ORDER", "dialect", "tăng số lượng"),
    ("Cho chế 1 phần chả giò ốc quậy nha", "ORDER", "dialect", "Nam Bộ giản dị"),
    ("Kêu 1 cơm chiên hải sản với 2 coca đi", "ORDER", "dialect", "kêu món"),
    ("Cho em xin 1 tô cháo hàu nha chị", "ORDER", "dialect", "tô cháo"),
    ("Bỏ bớt món trứng cút lộn ra dùm em", "ORDER", "dialect", "bỏ bớt"),
    ("Ừ đúng đơn đó rồi, chốt luôn đi em", "ORDER", "dialect", "xác nhận Nam Bộ"),
]

# ── ORDER / edge ─────────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Ừ", "ORDER", "edge", "xác nhận ngắn nhất"),
    ("Ok", "ORDER", "edge", "xác nhận tiếng Anh"),
    ("Ok em", "ORDER", "edge", "xác nhận ngắn"),
    ("Được", "ORDER", "edge", "đồng ý"),
    ("Đúng rồi", "ORDER", "edge", "xác nhận"),
    ("Chuẩn", "ORDER", "edge", "đồng ý"),
    ("Đi", "ORDER", "edge", "ra lệnh gọn"),
    ("Chốt luôn đi", "ORDER", "edge", "chốt đơn gọn"),
    ("Lên đơn luôn", "ORDER", "edge", "lên đơn gọn"),
    ("Xác nhận giùm anh", "ORDER", "edge", "xác nhận"),
    ("Đúng đơn đó rồi", "ORDER", "edge", "xác nhận đơn"),
    ("Ok chốt", "ORDER", "edge", "chốt gọn"),
    ("Gọi món đó đi", "ORDER", "edge", "ra lệnh"),
    ("Đặt đi em", "ORDER", "edge", "đặt gọn"),
    ("Ừm", "ORDER", "edge", "ừm xác nhận"),
    ("Uh đúng rồi đó", "ORDER", "edge", "xác nhận dạng nói"),
    ("Đúng rồi đó", "ORDER", "edge", "xác nhận"),
    ("Ok em", "ORDER", "edge", "xác nhận ngắn"),
]

# ── ORDER / fragment ─────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Cho 2 Ốc Hương", "ORDER", "fragment", "fragment gọi món"),
    ("Thêm 1 Lẩu Thái", "ORDER", "fragment", "fragment thêm món"),
    ("Bỏ món Ốc Hương", "ORDER", "fragment", "fragment bỏ món"),
    ("Xoá hết giỏ hàng", "ORDER", "fragment", "fragment xoá giỏ"),
    ("Xóa giỏ hàng", "ORDER", "fragment", "fragment xóa giỏ"),
    ("Chốt đơn", "ORDER", "fragment", "fragment chốt đơn"),
    ("Lấy thêm 2 Bia Saigon", "ORDER", "fragment", "fragment thêm bia"),
    ("Gọi 1 phần Cơm Chiên", "ORDER", "fragment", "fragment gọi cơm"),
    ("Cho 3 Trứng Cút Lộn", "ORDER", "fragment", "fragment gọi món"),
    ("Đổi sang Lẩu Thái", "ORDER", "fragment", "fragment đổi món"),
    ("Hủy món Ốc Hương", "ORDER", "fragment", "fragment hủy món"),
    ("Thêm 1 phần nữa", "ORDER", "fragment", "fragment thêm"),
    ("Cho tôi 1 Lẩu Cá Tầm", "ORDER", "fragment", "fragment gọi lẩu"),
    ("Gọi cho tôi 2 Bia Heineken", "ORDER", "fragment", "fragment gọi bia"),
    ("Cho mình 1 phần Gỏi Hải Sản", "ORDER", "fragment", "fragment gọi gỏi"),
    ("2 Ốc Hương Xốt Trứng Muối", "ORDER", "fragment", "fragment chỉ số lượng tên món"),
    ("1 Lẩu Thái với 3 Bia", "ORDER", "fragment", "fragment gọi nhiều món"),
    ("Xoá món Hàu Nướng", "ORDER", "fragment", "fragment xoá món"),
    ("Bỏ hết giỏ hàng", "ORDER", "fragment", "fragment bỏ giỏ"),
    ("Làm lại đơn mới", "ORDER", "fragment", "fragment làm lại"),
    ("Giảm Ốc Hương xuống 1", "ORDER", "fragment", "fragment giảm số lượng"),
    ("Tăng Cơm Chiên lên 3", "ORDER", "fragment", "fragment tăng số lượng"),
    ("Dọn giỏ hàng", "ORDER", "fragment", "fragment dọn giỏ"),
    ("Lên đơn", "ORDER", "fragment", "fragment lên đơn"),
    ("Xác nhận đơn", "ORDER", "fragment", "fragment xác nhận"),
    ("Bắt đầu lại với 1 Lẩu Thái", "ORDER", "fragment", "fragment bắt đầu lại"),
    ("3 Hàu Nướng Phô Mai", "ORDER", "fragment", "fragment số lượng tên món"),
    ("Thêm 2 Bia và 1 Trà Tắc", "ORDER", "fragment", "fragment thêm đồ uống"),
    ("Bỏ hết đồ uống", "ORDER", "fragment", "fragment bỏ đồ uống"),
    ("Đổi Tôm Xốt Me sang Tôm Xốt Phô Mai", "ORDER", "fragment", "fragment đổi món"),
]

# ── SEARCH / formal ──────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Dạ cho em hỏi Ốc Hương giá bao nhiêu ạ", "SEARCH", "formal", "hỏi giá lịch sự"),
    ("Cho em hỏi quán mình có món chay không ạ", "SEARCH", "formal", "hỏi món chay"),
    ("Em muốn hỏi Lẩu Thái có cay không ạ", "SEARCH", "formal", "hỏi độ cay"),
    ("Dạ cho em hỏi quán mở cửa đến mấy giờ ạ", "SEARCH", "formal", "hỏi giờ mở cửa"),
    ("Cho em hỏi món nào bán chạy nhất ở đây ạ", "SEARCH", "formal", "hỏi best seller"),
    ("Em muốn xem thực đơn của quán ạ", "SEARCH", "formal", "xem thực đơn"),
    ("Dạ cho em hỏi quán có giao hàng không ạ", "SEARCH", "formal", "hỏi giao hàng"),
    ("Cho em hỏi Hàu Nướng có những kiểu chế biến nào ạ", "SEARCH", "formal", "hỏi biến thể món"),
    ("Em muốn biết món này làm từ nguyên liệu gì ạ", "SEARCH", "formal", "hỏi nguyên liệu"),
    ("Dạ cho em hỏi quán có chỗ đậu xe không ạ", "SEARCH", "formal", "hỏi chỗ đậu xe"),
    ("Cho em hỏi có ship về quận 7 không ạ", "SEARCH", "formal", "hỏi ship quận"),
    ("Em muốn hỏi phí ship bao nhiêu ạ", "SEARCH", "formal", "hỏi phí ship"),
    ("Dạ quán mình có món lẩu nào ạ", "SEARCH", "formal", "hỏi danh mục lẩu"),
    ("Cho em hỏi đồ uống có những gì ạ", "SEARCH", "formal", "hỏi đồ uống"),
    ("Em muốn biết món nào đang khuyến mãi ạ", "SEARCH", "formal", "hỏi khuyến mãi"),
    ("Dạ cho em hỏi quán có wifi không ạ", "SEARCH", "formal", "hỏi wifi"),
    ("Cho em hỏi món này có cay quá không ạ", "SEARCH", "formal", "hỏi độ cay"),
    ("Em muốn hỏi có món gì hợp cho nhóm 4 người không ạ", "SEARCH", "formal", "hỏi gợi ý"),
    ("Dạ cho em hỏi quán có nhận đặt bàn trước không ạ", "SEARCH", "formal", "hỏi đặt bàn"),
    ("Cho em hỏi Tôm Càng Hấp Sả có tươi không ạ", "SEARCH", "formal", "hỏi chất lượng"),
    ("Dạ cho em hỏi Ốc Hương có những kiểu chế biến nào ạ", "SEARCH", "formal", "hỏi kiểu chế biến"),
    ("Em muốn biết Hàu Nướng có mấy cách làm ạ", "SEARCH", "formal", "hỏi cách chế biến"),
    ("Cho em hỏi món Lẩu Thái có những biến thể nào ạ", "SEARCH", "formal", "hỏi biến thể"),
    ("Dạ quán mình có những kiểu ốc nào ạ", "SEARCH", "formal", "hỏi các kiểu ốc"),
]

# ── SEARCH / casual ──────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Ốc hương giá bao nhiêu vậy", "SEARCH", "casual", "hỏi giá"),
    ("Quán mình có món chay không", "SEARCH", "casual", "hỏi món chay"),
    ("Lẩu thái cay không em", "SEARCH", "casual", "hỏi độ cay"),
    ("Có món gì hợp cho nhóm 4 người nhậu không", "SEARCH", "casual", "hỏi gợi ý"),
    ("Quán mở cửa tới mấy giờ vậy", "SEARCH", "casual", "hỏi giờ"),
    ("Món nào bán chạy nhất ở đây", "SEARCH", "casual", "best seller"),
    ("Ốc bulot làm từ nguyên liệu gì thế", "SEARCH", "casual", "hỏi nguyên liệu"),
    ("Có ship về quận 7 ko shop", "SEARCH", "casual", "hỏi ship"),
    ("Bia heineken nhiêu 1 lon z", "SEARCH", "casual", "hỏi giá teencode"),
    ("Cho mình xem menu với", "SEARCH", "casual", "xem menu"),
    ("Có món lẩu nào không", "SEARCH", "casual", "hỏi lẩu"),
    ("Món này giá sao vậy em", "SEARCH", "casual", "hỏi giá"),
    ("Quán có giao hàng tận nhà không", "SEARCH", "casual", "hỏi giao hàng"),
    ("Ship về quận tân bình bao nhiêu tiền", "SEARCH", "casual", "hỏi phí ship quận"),
    ("Tôi muốn xem thực đơn", "SEARCH", "casual", "xem thực đơn dùng tôi"),
    ("Có món nào rẻ rẻ không", "SEARCH", "casual", "hỏi món rẻ"),
    ("Cho hỏi có bia không", "SEARCH", "casual", "hỏi bia"),
    ("Món nào ngon nhất ở đây", "SEARCH", "casual", "hỏi món ngon"),
    ("Có món gì mới không em", "SEARCH", "casual", "hỏi món mới"),
    ("Shop có giao hàng tối không", "SEARCH", "casual", "hỏi shop"),
    ("Tôi ở quận 3, ship được không", "SEARCH", "casual", "hỏi ship quận 3"),
    ("Có khuyến mãi gì hôm nay không", "SEARCH", "casual", "hỏi khuyến mãi"),
    ("Món này có cay quá không", "SEARCH", "casual", "hỏi cay"),
    ("Thực đơn hôm nay có gì mới", "SEARCH", "casual", "thực đơn"),
    ("Cho tôi xem menu quán mình", "SEARCH", "casual", "xem menu"),
    ("Hàu nướng có những kiểu chế biến nào vậy em", "SEARCH", "casual", "hỏi kiểu chế biến"),
    ("Ốc hương có mấy cách làm khác nhau", "SEARCH", "casual", "hỏi cách làm"),
    ("Món này có những biến thể nào không", "SEARCH", "casual", "hỏi biến thể"),
    ("Có bao nhiêu kiểu ốc ở đây", "SEARCH", "casual", "hỏi kiểu ốc"),
]

# ── SEARCH / dialect ─────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Ốc hương giá bao nhiêu dạ", "SEARCH", "dialect", "Nam Bộ dạ"),
    ("Món ni giá bao nhiêu rứa em", "SEARCH", "dialect", "Trung rứa"),
    ("Quán mình có món chay hông", "SEARCH", "dialect", "Nam Bộ hông"),
    ("Có món chi rẻ rẻ hông em", "SEARCH", "dialect", "Trung chi, Nam hông"),
    ("Lẩu ni cay hông ta", "SEARCH", "dialect", "Nam Bộ hông ta"),
    ("Quán có giao hàng hông shop", "SEARCH", "dialect", "Nam Bộ hông"),
    ("Món mô ngon nhất ở đây rứa", "SEARCH", "dialect", "Trung mô rứa"),
    ("Cho anh xem thực đơn cái coi", "SEARCH", "dialect", "Nam Bộ cái coi"),
    ("Quận 7 giao hông em", "SEARCH", "dialect", "Nam Bộ hông"),
    ("Có món gì đặc biệt hông quán", "SEARCH", "dialect", "Nam Bộ"),
    ("Ship về quận gò vấp nhiêu tiền", "SEARCH", "dialect", "Nam Bộ nhiêu"),
    ("Đồ uống có những chi rứa em", "SEARCH", "dialect", "Trung chi rứa"),
    ("Món này bao nhiêu tiền rứa", "SEARCH", "dialect", "Trung rứa"),
    ("Giờ mở cửa tới mấy giờ dạ", "SEARCH", "dialect", "Nam Bộ dạ"),
    ("Có món lẩu mô hông em", "SEARCH", "dialect", "Trung mô hông"),
    ("Bia heineken nhiêu 1 chai dạ", "SEARCH", "dialect", "Nam Bộ"),
    ("Món ni nguyên liệu chi rứa", "SEARCH", "dialect", "Trung ni chi rứa"),
    ("Có món nào khuyến mãi hông ta", "SEARCH", "dialect", "Nam Bộ"),
    ("Tôi muốn coi thực đơn cái nghen", "SEARCH", "dialect", "Nam Bộ"),
    ("Bánh mì bơ tỏi giá sao rứa em", "SEARCH", "dialect", "Trung"),
]

# ── SEARCH / edge ────────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Giá sao", "SEARCH", "edge", "hỏi giá siêu ngắn"),
    ("Có không", "SEARCH", "edge", "hỏi siêu ngắn"),
    ("Bao nhiêu", "SEARCH", "edge", "hỏi giá"),
    ("Có cay không", "SEARCH", "edge", "hỏi cay ngắn"),
    ("Có ship không", "SEARCH", "edge", "hỏi ship"),
    ("Menu đâu", "SEARCH", "edge", "hỏi menu"),
    ("Có gì ngon", "SEARCH", "edge", "hỏi gợi ý"),
    ("Còn món gì", "SEARCH", "edge", "hỏi món"),
    ("Hết bao nhiêu", "SEARCH", "edge", "hỏi giá - dễ nhầm PAYMENT"),
    ("Ship được không", "SEARCH", "edge", "hỏi ship"),
    ("Giao được không", "SEARCH", "edge", "hỏi giao"),
    ("Có lẩu không", "SEARCH", "edge", "hỏi lẩu"),
    ("Mấy giờ đóng cửa", "SEARCH", "edge", "hỏi giờ"),
    ("Còn bàn trống không", "SEARCH", "edge", "hỏi bàn"),
    ("Nhiêu", "SEARCH", "edge", "hỏi giá teencode cực ngắn"),
]

# ── SEARCH / fragment ────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Có món chay không", "SEARCH", "fragment", "fragment hỏi chay"),
    ("Ốc Hương giá bao nhiêu", "SEARCH", "fragment", "fragment hỏi giá"),
    ("Còn món nào cay không", "SEARCH", "fragment", "fragment hỏi cay"),
    ("Menu có gì ngon", "SEARCH", "fragment", "fragment hỏi menu"),
    ("Có ship không", "SEARCH", "fragment", "fragment hỏi ship"),
    ("Quận 7 có giao không", "SEARCH", "fragment", "fragment hỏi quận"),
    ("Cho xem thực đơn", "SEARCH", "fragment", "fragment xem thực đơn"),
    ("Có món lẩu không", "SEARCH", "fragment", "fragment hỏi lẩu"),
    ("Món nào best seller", "SEARCH", "fragment", "fragment best seller"),
    ("Tôi muốn xem menu", "SEARCH", "fragment", "fragment xem menu"),
    ("Quán có món gì đặc biệt", "SEARCH", "fragment", "fragment hỏi đặc biệt"),
    ("Đồ uống có những gì", "SEARCH", "fragment", "fragment hỏi đồ uống"),
    ("Có món nào rẻ không", "SEARCH", "fragment", "fragment hỏi rẻ"),
    ("Món này bao nhiêu tiền", "SEARCH", "fragment", "fragment hỏi tiền"),
    ("Cho hỏi có bia không", "SEARCH", "fragment", "fragment hỏi bia"),
    ("Phí ship bao nhiêu", "SEARCH", "fragment", "fragment phí ship"),
    ("Có giao hàng không shop", "SEARCH", "fragment", "fragment giao hàng"),
    ("Quán mở cửa mấy giờ", "SEARCH", "fragment", "fragment giờ"),
    ("Món này nguyên liệu gì", "SEARCH", "fragment", "fragment nguyên liệu"),
    ("Còn bàn không", "SEARCH", "fragment", "fragment hỏi bàn"),
    ("Có những kiểu chế biến nào", "SEARCH", "fragment", "fragment hỏi kiểu"),
    ("Có mấy cách làm", "SEARCH", "fragment", "fragment hỏi cách"),
    ("Ốc Hương có mấy kiểu", "SEARCH", "fragment", "fragment hỏi kiểu ốc"),
    ("Những biến thể của Lẩu Thái", "SEARCH", "fragment", "fragment hỏi biến thể"),
]

# ── PAYMENT / formal ─────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Dạ cho em tính tiền ạ", "PAYMENT", "formal", "tính tiền lịch sự"),
    ("Em muốn thanh toán ạ", "PAYMENT", "formal", "thanh toán"),
    ("Cho em xin hóa đơn ạ", "PAYMENT", "formal", "xin hoá đơn"),
    ("Dạ cho em hỏi thanh toán chuyển khoản được không ạ", "PAYMENT", "formal", "hỏi phương thức"),
    ("Em muốn thanh toán bằng thẻ ạ", "PAYMENT", "formal", "thanh toán thẻ"),
    ("Cho em xin mã QR để thanh toán ạ", "PAYMENT", "formal", "xin QR"),
    ("Dạ cho em hỏi tổng tiền bao nhiêu ạ", "PAYMENT", "formal", "hỏi tổng tiền"),
    ("Em muốn kiểm tra hoá đơn trước khi thanh toán ạ", "PAYMENT", "formal", "kiểm tra bill"),
    ("Cho em hỏi quẹt thẻ được không ạ", "PAYMENT", "formal", "hỏi quẹt thẻ"),
    ("Dạ em muốn trả tiền mặt ạ", "PAYMENT", "formal", "trả tiền mặt"),
    ("Cho em xin bill ạ", "PAYMENT", "formal", "xin bill"),
    ("Em muốn thanh toán qua ví điện tử ạ", "PAYMENT", "formal", "ví điện tử"),
    ("Dạ cho em kiểm tra đã thanh toán chưa ạ", "PAYMENT", "formal", "kiểm tra đã thanh toán"),
    ("Cho em xin hoá đơn đỏ ạ", "PAYMENT", "formal", "hoá đơn đỏ"),
    ("Em muốn thanh toán riêng từng người ạ", "PAYMENT", "formal", "thanh toán riêng"),
]

# ── PAYMENT / casual ─────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Tính tiền đi em", "PAYMENT", "casual", "tính tiền"),
    ("Thanh toán cho anh", "PAYMENT", "casual", "thanh toán"),
    ("Cho xin bill", "PAYMENT", "casual", "xin bill"),
    ("Tổng bao nhiêu", "PAYMENT", "casual", "hỏi tổng"),
    ("Bill hết bao nhiêu", "PAYMENT", "casual", "hỏi bill"),
    ("Tính tổng giùm", "PAYMENT", "casual", "tính tổng"),
    ("Quẹt thẻ được hông em", "PAYMENT", "casual", "quẹt thẻ"),
    ("Ck cho mình cái qr với", "PAYMENT", "casual", "ck QR"),
    ("Hết nhiêu tiền rồi em ơi", "PAYMENT", "casual", "hỏi tổng"),
    ("Cho xin mã qr thanh toán", "PAYMENT", "casual", "xin QR"),
    ("Bill đi em", "PAYMENT", "casual", "bill ngắn"),
    ("Trả tiền cho anh", "PAYMENT", "casual", "trả tiền"),
    ("Thanh toán chuyển khoản luôn", "PAYMENT", "casual", "chuyển khoản"),
    ("Tính tổng thiệt hại đi em", "PAYMENT", "casual", "tổng thiệt hại"),
    ("Cho xin cái bill với", "PAYMENT", "casual", "xin bill"),
    ("Tiền đâu trả đây", "PAYMENT", "casual", "hỏi trả tiền"),
    ("Tôi muốn thanh toán", "PAYMENT", "casual", "dùng tôi"),
    ("Check bill giúp mình", "PAYMENT", "casual", "check bill"),
]

# ── PAYMENT / dialect ────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Tính tiền nghen em", "PAYMENT", "dialect", "Nam Bộ"),
    ("Thanh toán cho chị cái nghen", "PAYMENT", "dialect", "Nam Bộ"),
    ("Cho xin cái bill coi", "PAYMENT", "dialect", "Nam Bộ"),
    ("Tổng bao nhiêu rứa em", "PAYMENT", "dialect", "Trung rứa"),
    ("Quẹt thẻ được hông ta", "PAYMENT", "dialect", "Nam Bộ"),
    ("Tính hết bao nhiêu dạ", "PAYMENT", "dialect", "Nam Bộ dạ"),
    ("Cho chị gửi tiền nghen", "PAYMENT", "dialect", "Nam Bộ"),
    ("Bill nhiêu dạ", "PAYMENT", "dialect", "Nam Bộ nhiêu dạ"),
    ("Trả tiền mặt được hông", "PAYMENT", "dialect", "Nam Bộ"),
    ("Tính tổng thiệt hại nghen", "PAYMENT", "dialect", "Nam Bộ"),
    ("Làm bill dùm anh cái", "PAYMENT", "dialect", "Nam Bộ"),
    ("Thanh toán chuyển khoản nghen", "PAYMENT", "dialect", "Nam Bộ"),
    ("Có nhận tiền mặt hông shop", "PAYMENT", "dialect", "Nam Bộ"),
]

# ── PAYMENT / edge ───────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Tính tiền", "PAYMENT", "edge", "ngắn nhất"),
    ("Thanh toán", "PAYMENT", "edge", "thanh toán ngắn"),
    ("Bill", "PAYMENT", "edge", "bill tiếng Anh"),
    ("Trả tiền", "PAYMENT", "edge", "trả tiền ngắn"),
    ("Check bill", "PAYMENT", "edge", "check bill"),
    ("Tổng", "PAYMENT", "edge", "tổng ngắn"),
    ("QR", "PAYMENT", "edge", "QR siêu ngắn"),
    ("Hết bao nhiêu tiền", "PAYMENT", "edge", "hỏi tổng ngắn"),
    ("Hết nhiêu", "PAYMENT", "edge", "hỏi tổng teencode"),
    ("Tính tổng", "PAYMENT", "edge", "tính tổng ngắn"),
    ("Cho xin bill", "PAYMENT", "edge", "xin bill ngắn"),
    ("Cho tính tiền", "PAYMENT", "edge", "tính tiền ngắn"),
]

# ── PAYMENT / fragment ───────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Tính tiền", "PAYMENT", "fragment", "fragment tính tiền"),
    ("Thanh toán", "PAYMENT", "fragment", "fragment thanh toán"),
    ("Cho xin bill", "PAYMENT", "fragment", "fragment bill"),
    ("Tổng bao nhiêu", "PAYMENT", "fragment", "fragment tổng"),
    ("Trả tiền", "PAYMENT", "fragment", "fragment trả tiền"),
    ("Bill hết bao nhiêu", "PAYMENT", "fragment", "fragment bill"),
    ("Tính tổng giùm", "PAYMENT", "fragment", "fragment tính tổng"),
    ("Cho xin mã QR", "PAYMENT", "fragment", "fragment QR"),
    ("Hết bao nhiêu tiền", "PAYMENT", "fragment", "fragment hết tiền"),
    ("Kiểm tra bill", "PAYMENT", "fragment", "fragment kiểm tra"),
]

# ── CHAT / formal ────────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Dạ em chào quán ạ", "CHAT", "formal", "chào lịch sự"),
    ("Cảm ơn quán nhiều ạ", "CHAT", "formal", "cảm ơn"),
    ("Dạ đồ ăn ở đây ngon quá ạ", "CHAT", "formal", "khen lịch sự"),
    ("Em cảm ơn em, quán phục vụ tốt quá", "CHAT", "formal", "khen phục vụ"),
    ("Dạ cho em hỏi, em có thể ngồi thêm một lát được không ạ", "CHAT", "formal", "hỏi ngồi thêm"),
    ("Cảm ơn quán đã phục vụ chu đáo ạ", "CHAT", "formal", "cảm ơn"),
    ("Dạ em chúc quán đông khách ạ", "CHAT", "formal", "chúc"),
    ("Đồ ăn hôm nay rất tuyệt vời ạ", "CHAT", "formal", "khen"),
    ("Dạ em xin phép ra về ạ", "CHAT", "formal", "tạm biệt"),
    ("Cảm ơn em nhé, lần sau anh sẽ quay lại", "CHAT", "formal", "cảm ơn hẹn gặp lại"),
    ("Em rất hài lòng với bữa ăn ạ", "CHAT", "formal", "khen"),
    ("Dạ quán trang trí đẹp quá ạ", "CHAT", "formal", "khen quán"),
    ("Chúc quán buôn may bán đắt ạ", "CHAT", "formal", "chúc"),
    ("Em tên là Lan, rất vui được gặp quán", "CHAT", "formal", "giới thiệu bản thân"),
    ("Dạ em hỏi nhà vệ sinh ở đâu ạ", "CHAT", "formal", "hỏi nhà vệ sinh"),
    ("Em muốn khen đầu bếp món này rất ngon ạ", "CHAT", "formal", "khen đầu bếp"),
    ("Dạ quán có nhận góp ý không ạ", "CHAT", "formal", "góp ý"),
    ("Em thấy không khí ở đây rất ấm cúng ạ", "CHAT", "formal", "khen không khí"),
    ("Cảm ơn quán, bữa nay gia đình em rất vui ạ", "CHAT", "formal", "cảm ơn gia đình"),
    ("Dạ em chào anh chị, em về trước ạ", "CHAT", "formal", "tạm biệt"),
]

# ── CHAT / casual ────────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Ê quán đông ghê ha", "CHAT", "casual", "tán gẫu"),
    ("Đồ ăn ở đây ngon quá trời", "CHAT", "casual", "khen"),
    ("Cảm ơn em nhiều nha", "CHAT", "casual", "cảm ơn"),
    ("Xin chào shop", "CHAT", "casual", "chào shop"),
    ("Trời hôm nay mưa to thật", "CHAT", "casual", "lạc đề"),
    ("Món này mặn quá em ơi", "CHAT", "casual", "chê mặn"),
    ("Lần đầu tới đây ăn nè", "CHAT", "casual", "lần đầu"),
    ("Quán này mới mở hả em", "CHAT", "casual", "hỏi quán"),
    ("Ngon thiệt chứ", "CHAT", "casual", "khen"),
    ("Bạn là người hay robot vậy", "CHAT", "casual", "hỏi về AI"),
    ("Tôi no quá rồi", "CHAT", "casual", "no"),
    ("Để anh suy nghĩ tí đã", "CHAT", "casual", "suy nghĩ - KHÔNG phải ORDER"),
    ("Từ từ đi em", "CHAT", "casual", "từ từ - KHÔNG phải ORDER"),
    ("Khoan đã đừng gọi vội", "CHAT", "casual", "khoan - KHÔNG phải ORDER"),
    ("À mà thôi", "CHAT", "casual", "đổi ý - KHÔNG phải ORDER"),
    ("Chưa biết nữa để tính sau", "CHAT", "casual", "chưa quyết định"),
    ("Chờ xíu nha", "CHAT", "casual", "chờ"),
    ("Để coi đã", "CHAT", "casual", "để coi"),
    ("Ủa gì vậy", "CHAT", "casual", "ngạc nhiên"),
    ("Hôm nay quán vắng ha", "CHAT", "casual", "quán vắng"),
    ("Có gì vui kể nghe đi", "CHAT", "casual", "tán gẫu"),
    ("Em nói chuyện dễ thương ghê", "CHAT", "casual", "khen AI"),
    ("Thôi kệ đi", "CHAT", "casual", "thôi kệ"),
    ("Hết hồn", "CHAT", "casual", "phản ứng"),
    ("Nói vậy thôi chứ", "CHAT", "casual", "tán gẫu"),
]

# ── CHAT / dialect ───────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Ngon quá trời quá đất luôn", "CHAT", "dialect", "Nam Bộ khen"),
    ("Cảm ơn em nhiều nghen", "CHAT", "dialect", "Nam Bộ"),
    ("Trời ơi đồ ăn ngon dã man", "CHAT", "dialect", "Nam Bộ dã man"),
    ("Quán ni đẹp ghê nơi", "CHAT", "dialect", "Trung ni nơi"),
    ("Ngon thiệt chứ đâu có đùa", "CHAT", "dialect", "Nam Bộ"),
    ("Dạ cảm ơn em nghen", "CHAT", "dialect", "Nam Bộ dạ"),
    ("Món ni mặn quá nè", "CHAT", "dialect", "Trung ni nè"),
    ("Trời hôm ni nắng dữ thần", "CHAT", "dialect", "Nam Bộ"),
    ("Tui no quá rồi bà ơi", "CHAT", "dialect", "Nam Bộ tui"),
    ("Ngon hết sảy luôn", "CHAT", "dialect", "Nam Bộ hết sảy"),
    ("Chưa biết nữa, để tui suy nghĩ cái coi", "CHAT", "dialect", "Nam Bộ tui"),
    ("Khoan khoan đừng có gọi vội", "CHAT", "dialect", "Nam Bộ"),
    ("Ủa gì dạ", "CHAT", "dialect", "Nam Bộ ủa dạ"),
    ("Quán này bữa ni vắng hén", "CHAT", "dialect", "Nam Bộ hén"),
    ("Tạm biệt em nghen, hẹn bữa sau", "CHAT", "dialect", "Nam Bộ"),
]

# ── CHAT / edge ──────────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Ừ", "CHAT", "edge", "gật đầu"),
    ("Ok", "CHAT", "edge", "ok"),
    ("Ừm", "CHAT", "edge", "ừm"),
    ("À", "CHAT", "edge", "à"),
    ("Hả", "CHAT", "edge", "hả"),
    ("Gì", "CHAT", "edge", "gì"),
    ("Sao", "CHAT", "edge", "sao"),
    ("Dạ", "CHAT", "edge", "dạ"),
    ("Ngon", "CHAT", "edge", "khen ngắn"),
    ("Cảm ơn", "CHAT", "edge", "cảm ơn ngắn"),
    ("Chào em", "CHAT", "edge", "chào"),
    ("Tạm biệt", "CHAT", "edge", "tạm biệt"),
    ("Hết hồn", "CHAT", "edge", "ngạc nhiên"),
    ("Trời ơi", "CHAT", "edge", "cảm thán"),
    ("Để xem đã", "CHAT", "edge", "chưa quyết định"),
    ("Từ từ", "CHAT", "edge", "chờ"),
    ("Khoan đã", "CHAT", "edge", "dừng lại"),
    ("À mà thôi", "CHAT", "edge", "đổi ý"),
    ("Chưa biết", "CHAT", "edge", "chưa quyết định"),
    ("Chờ xíu", "CHAT", "edge", "chờ"),
    ("Thôi", "CHAT", "edge", "thôi"),
    ("Kệ đi", "CHAT", "edge", "kệ"),
    ("Vậy hả", "CHAT", "edge", "phản ứng"),
    ("Thiệt hả", "CHAT", "edge", "ngạc nhiên"),
    ("Ngon thiệt", "CHAT", "edge", "khen"),
]

# ── CHAT / fragment ──────────────────────────────────────────────────
MANUAL_UTTERANCES += [
    ("Cảm ơn", "CHAT", "fragment", "fragment cảm ơn"),
    ("Ngon quá", "CHAT", "fragment", "fragment khen"),
    ("Chào em", "CHAT", "fragment", "fragment chào"),
    ("Cảm ơn em", "CHAT", "fragment", "fragment cảm ơn"),
    ("Ngon thiệt", "CHAT", "fragment", "fragment khen"),
    ("Ok", "CHAT", "fragment", "fragment ok"),
    ("Tôi no quá", "CHAT", "fragment", "fragment no"),
    ("Cảm ơn em nhiều nha", "CHAT", "fragment", "fragment cảm ơn"),
    ("Xin chào shop", "CHAT", "fragment", "fragment chào"),
    ("Ở đây đẹp quá", "CHAT", "fragment", "fragment khen"),
    ("Âm nhạc hay quá", "CHAT", "fragment", "fragment khen"),
    ("Phục vụ tốt quá", "CHAT", "fragment", "fragment khen"),
    ("Không có gì", "CHAT", "fragment", "fragment đáp"),
    ("Không sao đâu", "CHAT", "fragment", "fragment"),
    ("Để anh suy nghĩ tí", "CHAT", "fragment", "fragment suy nghĩ"),
    ("Từ từ đi", "CHAT", "fragment", "fragment từ từ"),
    ("Chưa biết nữa", "CHAT", "fragment", "fragment chưa biết"),
    ("Chờ xíu", "CHAT", "fragment", "fragment chờ"),
    ("À mà thôi", "CHAT", "fragment", "fragment đổi ý"),
    ("Tính sau đi", "CHAT", "fragment", "fragment tính sau"),
]

# ═══════════════════════════════════════════════════════════════════════
# Critical vocabulary reinforcement — utterances repeating tokens that
# were absent from older corpus generations (tôi, xoá/xóa, giỏ hàng,
# quận, ship, shop, thực đơn) across all intents so the classifier
# cannot exploit vocabulary co-occurrence as a shortcut.
# ═══════════════════════════════════════════════════════════════════════

VOCAB_REINFORCEMENT: list[tuple[str, str, str, str]] = [
    # "tôi" — standard first-person pronoun
    ("Cho tôi 2 phần Ốc Hương Xốt Trứng Muối", "ORDER", "formal", "tôi ORDER"),
    ("Tôi muốn gọi thêm 1 Lẩu Thái", "ORDER", "casual", "tôi ORDER"),
    ("Tôi muốn xoá giỏ hàng", "ORDER", "casual", "tôi ORDER xoá"),
    ("Tôi muốn đặt 1 Bia Heineken", "ORDER", "casual", "tôi ORDER"),
    ("Tôi muốn xem thực đơn của quán", "SEARCH", "casual", "tôi SEARCH"),
    ("Tôi muốn tìm món chay", "SEARCH", "casual", "tôi SEARCH"),
    ("Cho tôi hỏi có món nào cay không", "SEARCH", "casual", "tôi SEARCH"),
    ("Tôi ở quận 7, có giao hàng không", "SEARCH", "casual", "tôi SEARCH"),
    ("Tôi muốn coi menu có gì ngon", "SEARCH", "dialect", "tôi SEARCH"),
    ("Tính tiền cho tôi", "PAYMENT", "casual", "tôi PAYMENT"),
    ("Cho tôi thanh toán", "PAYMENT", "casual", "tôi PAYMENT"),
    ("Tôi cảm ơn em", "CHAT", "casual", "tôi CHAT"),
    ("Tôi no quá rồi", "CHAT", "casual", "tôi CHAT"),
    ("Tôi muốn góp ý một chút", "CHAT", "casual", "tôi CHAT"),

    # "xoá" / "xóa" — delete/clear
    ("Xoá hết giỏ hàng của tôi đi", "ORDER", "casual", "xoá giỏ hàng"),
    ("Em xoá giùm món Ốc Hương", "ORDER", "casual", "xoá món"),
    ("Xoá đơn hàng này giúp anh", "ORDER", "casual", "xoá đơn"),
    ("Cho anh xoá hết giỏ hàng", "ORDER", "casual", "xoá giỏ"),
    ("Xóa giỏ hàng rồi gọi lại từ đầu", "ORDER", "casual", "xóa giỏ"),
    ("Xoá món Cháo Hàu khỏi giỏ hàng", "ORDER", "casual", "xoá món"),
    ("Xoá hết rồi bắt đầu lại", "ORDER", "fragment", "xoá fragment"),

    # "giỏ hàng" — shopping cart
    ("Cho anh xem lại giỏ hàng", "ORDER", "casual", "giỏ hàng ORDER"),
    ("Giỏ hàng của tôi có những món gì", "ORDER", "casual", "giỏ hàng"),
    ("Cập nhật giỏ hàng giùm em", "ORDER", "casual", "giỏ hàng"),
    ("Dọn giỏ hàng sạch rồi gọi lại", "ORDER", "casual", "giỏ hàng dọn"),
    ("Kiểm tra giỏ hàng giúp em", "ORDER", "casual", "giỏ hàng kiểm tra"),

    # "quận" — delivery district (always SEARCH)
    ("Có ship về quận 7 không", "SEARCH", "casual", "quận SEARCH"),
    ("Quận Gò Vấp có giao không shop", "SEARCH", "casual", "quận SEARCH"),
    ("Ship về quận Tân Bình bao nhiêu tiền", "SEARCH", "casual", "quận SEARCH"),
    ("Quán có giao hàng tận quận 1 không", "SEARCH", "casual", "quận SEARCH"),
    ("Tôi ở quận 3, ship được không", "SEARCH", "casual", "quận SEARCH"),
    ("Quận 9 có ship không em", "SEARCH", "casual", "quận SEARCH"),

    # "ship" / "shop" — delivery / store
    ("Có ship không em", "SEARCH", "casual", "ship SEARCH"),
    ("Phí ship bao nhiêu", "SEARCH", "casual", "ship SEARCH"),
    ("Shop có giao hàng tối không", "SEARCH", "casual", "shop SEARCH"),
    ("Cho hỏi shop mở cửa đến mấy giờ", "SEARCH", "casual", "shop SEARCH"),

    # "thực đơn" / "menu"
    ("Cho anh xem thực đơn", "SEARCH", "casual", "thực đơn SEARCH"),
    ("Thực đơn hôm nay có gì mới không", "SEARCH", "casual", "thực đơn SEARCH"),
    ("Cho tôi xem thực đơn của quán", "SEARCH", "casual", "thực đơn SEARCH"),
    ("Cho mình xem menu với", "SEARCH", "casual", "menu SEARCH"),
    ("Menu của quán đâu em", "SEARCH", "casual", "menu SEARCH"),

    # "gọi món" / "đặt món" — explicit ordering verbs
    ("Tôi muốn gọi món", "ORDER", "casual", "gọi món"),
    ("Cho tôi đặt món 2 phần Cơm Chiên", "ORDER", "casual", "đặt món"),
    ("Em ơi cho anh gọi món", "ORDER", "casual", "gọi món"),
]


# ═══════════════════════════════════════════════════════════════════════
# Context-dependent ambiguous examples — same utterance, different
# intent depending on order_stage.  These teach the model to use
# context features (features[0-9]) rather than memorizing the text.
# ═══════════════════════════════════════════════════════════════════════

AMBIGUOUS_CONTEXT: list[dict] = [
    # "ok" at different stages
    ({"utterance": "Ok", "intent": "CHAT", "order_stage": "IDLE"}),
    ({"utterance": "Ok", "intent": "CHAT", "order_stage": "BUILDING"}),
    ({"utterance": "Ok", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),
    ({"utterance": "Ok", "intent": "CHAT", "order_stage": "CONFIRMED"}),

    # "ừ" at different stages
    ({"utterance": "Ừ", "intent": "CHAT", "order_stage": "IDLE"}),
    ({"utterance": "Ừ", "intent": "CHAT", "order_stage": "BUILDING"}),
    ({"utterance": "Ừ", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),

    # "được" at different stages
    ({"utterance": "Được", "intent": "CHAT", "order_stage": "IDLE"}),
    ({"utterance": "Được", "intent": "CHAT", "order_stage": "BUILDING"}),
    ({"utterance": "Được", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),

    # "đúng rồi" at different stages
    ({"utterance": "Đúng rồi", "intent": "CHAT", "order_stage": "IDLE"}),
    ({"utterance": "Đúng rồi", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),

    # "ok em" at different stages
    ({"utterance": "Ok em", "intent": "CHAT", "order_stage": "IDLE"}),
    ({"utterance": "Ok em", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),

    # "chuẩn" at different stages
    ({"utterance": "Chuẩn", "intent": "CHAT", "order_stage": "IDLE"}),
    ({"utterance": "Chuẩn", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),

    # "thêm 1 phần nữa" — ORDER when cart exists, CHAT otherwise
    ({"utterance": "Thêm 1 phần nữa", "intent": "ORDER", "order_stage": "BUILDING"}),
    ({"utterance": "Thêm 1 phần nữa", "intent": "CHAT", "order_stage": "IDLE"}),

    # "chốt đơn" — always ORDER
    ({"utterance": "Chốt đơn đi em", "intent": "ORDER", "order_stage": "AWAITING_CONFIRMATION"}),
    ({"utterance": "Chốt đơn luôn", "intent": "ORDER", "order_stage": "BUILDING"}),

    # "tính tiền" — always PAYMENT regardless of stage
    ({"utterance": "Tính tiền đi em", "intent": "PAYMENT", "order_stage": "AWAITING_CONFIRMATION"}),
    ({"utterance": "Tính tiền đi em", "intent": "PAYMENT", "order_stage": "IDLE"}),
    ({"utterance": "Tính tiền đi em", "intent": "PAYMENT", "order_stage": "BUILDING"}),
]


# ═══════════════════════════════════════════════════════════════════════
# Build & save
# ═══════════════════════════════════════════════════════════════════════

def _clean(utterances: list) -> list:
    """Drop placeholder/misplaced entries."""
    return [
        (u, i, s, n) for (u, i, s, n) in utterances
        if u and "đã sửa thành" not in n
    ]


def build_raw_dataset() -> list[dict]:
    """Return the full manual raw dataset as a list of dicts."""
    records: list[dict] = []
    seen = set()

    all_utterances = list(MANUAL_UTTERANCES) + list(VOCAB_REINFORCEMENT)

    for utterance, intent, style, notes in _clean(all_utterances):
        key = (utterance.lower().strip(), intent, style)
        if key in seen:
            continue
        seen.add(key)
        records.append({
            "utterance": utterance,
            "intent": intent,
            "style": style,
            "source": "manual",
            "notes": notes,
        })
    return records


def print_stats(records: list[dict]) -> None:
    from collections import Counter
    n = len(records)
    intents = Counter(r["intent"] for r in records)
    styles = Counter(r["style"] for r in records)
    by_intent_style = Counter((r["intent"], r["style"]) for r in records)

    print(f"\n{'='*60}")
    print(f"Manual dataset: {n} raw records")
    print(f"{'='*60}")
    print("\nPer intent:")
    for i in ["ORDER", "SEARCH", "PAYMENT", "CHAT"]:
        print(f"  {i}: {intents.get(i, 0)}")
    print("\nPer style:")
    for s in ["formal", "casual", "dialect", "edge", "fragment"]:
        print(f"  {s}: {styles.get(s, 0)}")
    print("\nIntent × Style cross-tab:")
    for i in ["ORDER", "SEARCH", "PAYMENT", "CHAT"]:
        row = "  " + i.ljust(8)
        for s in ["formal", "casual", "dialect", "edge", "fragment"]:
            row += f" {s}: {by_intent_style.get((i, s), 0):>2}"
        print(row)

    all_text = " ".join(r["utterance"] for r in records)
    print(f"\nUnique tokens: {len(set(all_text.split()))}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build manual intent-classification dataset")
    parser.add_argument("--output", default=str(RAW_OUTPUT))
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--retrain", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()

    records = build_raw_dataset()
    print_stats(records)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\nSaved raw dataset to {out}")

    if args.augment:
        from src.training_semantic_router.data.augmenter import augment_file, build_ambiguous_set

        aug_out = DATA_DIR / "synthetic_augmented.json"
        augmented = augment_file(out, aug_out)
        ambi = build_ambiguous_set(100)
        all_data = augmented + ambi

        with open(aug_out, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        print(f"\nAugmented: {len(augmented)} examples + {len(ambi)} ambiguous = {len(all_data)} total")
        print(f"Saved to {aug_out}")

    if args.retrain:
        print("\nTraining classifier...")
        import subprocess
        train_script = Path(__file__).resolve().parent.parent / "scripts" / "train.py"
        result = subprocess.run(
            [sys.executable, str(train_script)],
            cwd=PROJECT_ROOT,
            env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )
        if result.returncode != 0:
            print("Training failed!", file=sys.stderr)
            sys.exit(result.returncode)

        if args.evaluate:
            print("\nEvaluating holdout...")
            eval_script = Path(__file__).resolve().parent.parent / "scripts" / "evaluate.py"
            subprocess.run(
                [sys.executable, str(eval_script)],
                cwd=PROJECT_ROOT,
                env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT)},
            )


if __name__ == "__main__":
    main()
