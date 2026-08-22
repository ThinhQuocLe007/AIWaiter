"""Build the router training corpus from the real restaurant data in ``assets/``.

Design notes, because the previous corpus got these wrong:

* One row = one UNIQUE utterance. There is no context augmentation. The MLP router is
  text-only, so duplicating an utterance under different cart/stage values leaves the 768
  embedding dims bit-identical and teaches the model nothing (measured: x5.2 duplication
  bought +0.008 accuracy, inside the noise band).
* Short affirmations are labelled ORDER, not CHAT. ``order_worker`` binds ``delegate`` and
  can fall back to chat, while ``chat_worker`` is a leaf with no tools — so a CHAT
  mislabel loses an order confirmation outright, whereas an ORDER mislabel costs one extra
  LLM hop. Deferrals ("thôi", "khoan đã") stay CHAT: the worker answers those with
  ``clear_cart``, which would wipe a live cart.
* Dish names are slot-filled across the whole menu. The old corpus mentioned 30 of 234
  dishes; ORDER and SEARCH are exactly the two intents where the dish name is the signal.
"""

from __future__ import annotations

import json
import random
import unicodedata
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS = PROJECT_ROOT / "assets" / "data"

STYLES = ("formal", "casual", "dialect", "fragment", "edge")


# --------------------------------------------------------------------------- menu slots

def load_menu() -> list[dict[str, Any]]:
    with open(ASSETS / "menu.json", "r", encoding="utf-8") as f:
        return json.load(f)


# Counting words differ per dish. Getting these wrong is the fastest way to make a
# slot-filled corpus read like a machine wrote it ("2 tô Ốc Hương" is not something
# anyone says).
UNITS_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "Ốc & Sò": ("phần", "dĩa"),
    "Tôm": ("phần", "dĩa", "con"),
    "Món Nướng": ("phần", "dĩa", "con"),
    "Món Chính": ("phần", "dĩa"),
    "Lặt Vặt Ăn Chơi": ("phần", "dĩa"),
    "Gỏi & Trộn": ("phần", "dĩa"),
    "Chiên & Khai Vị": ("phần", "dĩa"),
    "Khô Lai Rai": ("phần", "dĩa"),
    "Mì - Cháo - Cơm": ("tô", "phần"),
    "Rau & Canh": ("phần", "dĩa"),
    "Món Lẩu": ("nồi", "phần"),
    "Giải Khát": ("lon", "chai", "ly"),
    "Tráng Miệng": ("ly", "phần", "chén"),
}
_FALLBACK_UNITS = ("phần", "dĩa")

QUANTITIES = (1, 1, 1, 2, 2, 2, 3, 3, 4, 5, 6)

SPECIAL_REQUESTS = (
    "không cay", "ít cay thôi", "cay nhiều vô", "đừng bỏ hành",
    "ít dầu mỡ", "làm đậm vị giùm", "không bỏ đậu phộng", "thêm nước mắm",
    "làm nhanh giùm em", "cho ít đá", "đừng bỏ rau răm", "cho thêm chén mắm",
)

# From restaurant_info.txt — the chain is real, use its real facts.
HOTLINE = "0968 955 331"
BRANCHES = (
    "Mũi Né", "Phan Thiết", "Đà Lạt", "Bảo Lộc",
    "Bà Rịa", "Long An", "Thủ Đức", "Vinhomes Central Park",
)
OCCASIONS = (
    "nhóm 4 người", "hai đứa em", "cả nhà 6 người", "đi nhậu lai rai",
    "trẻ con ăn được", "người ăn chay", "khách không ăn được cay",
    "sinh nhật bạn em", "tiếp khách", "ăn nhẹ thôi",
)
TASTE_WORDS = ("cay", "béo", "ngọt", "thanh đạm", "đậm đà", "giòn", "chua chua", "mặn")
PAY_METHODS = (
    "tiền mặt", "chuyển khoản", "quẹt thẻ", "quét QR",
    "Momo", "VNPay", "ZaloPay", "thẻ tín dụng",
)
# Cash has no terminal and needs no signal, so templates that talk about a machine or a
# dropped connection must not draw "tiền mặt" — that produced "trả tiền mặt mà sóng yếu".
PAY_METHODS_ELECTRONIC = tuple(m for m in PAY_METHODS if m != "tiền mặt")

# Khu vực giao hàng — eval hỏi ship theo quận, corpus đầu tiên không có câu nào.
DELIVERY_AREAS = (
    "quận 1", "quận 3", "quận 7", "quận 10", "Tân Bình", "Bình Thạnh",
    "Gò Vấp", "Thủ Đức", "Phú Nhuận", "quận 2", "Bình Tân", "Nhà Bè",
)


# ------------------------------------------------------------------- ORDER templates
# {d} dish, {q} quantity, {u} unit, {r} special request.
# Each entry: (template_id, style, text). Slots are filled by build_slot_records().

ORDER_TEMPLATES: list[tuple[str, str, str]] = [
    # -- formal ---------------------------------------------------------------
    ("ORD-F01", "formal", "Cho em xin {q} {u} {d} ạ"),
    ("ORD-F02", "formal", "Em muốn gọi {q} {u} {d} ạ"),
    ("ORD-F03", "formal", "Anh chị cho em đặt {q} {u} {d} nhé"),
    ("ORD-F04", "formal", "Làm ơn cho tôi {q} {u} {d}"),
    ("ORD-F05", "formal", "Vui lòng thêm {q} {u} {d} vào đơn giúp tôi"),
    ("ORD-F06", "formal", "Em xin phép gọi thêm {q} {u} {d} nữa ạ"),
    ("ORD-F07", "formal", "Cho tôi đổi món vừa gọi sang {d}"),
    ("ORD-F08", "formal", "Tôi muốn bỏ {d} ra khỏi đơn ạ"),
    ("ORD-F09", "formal", "Nhờ em ghi cho {q} {u} {d}, {r} ạ"),
    ("ORD-F10", "formal", "Cho em đặt trước {q} {u} {d} nha em"),
    # -- casual ---------------------------------------------------------------
    ("ORD-C01", "casual", "cho {q} {u} {d} đi em"),
    ("ORD-C02", "casual", "lấy {q} {u} {d} nha"),
    ("ORD-C03", "casual", "thêm {q} {u} {d} nữa"),
    ("ORD-C04", "casual", "gọi thêm {d} đi"),
    ("ORD-C05", "casual", "kêu giùm anh {q} {u} {d}"),
    ("ORD-C06", "casual", "cho anh {q} {u} {d} rồi tính sau"),
    ("ORD-C07", "casual", "bỏ {d} ra giùm em"),
    ("ORD-C08", "casual", "bớt {d} lại còn {q} {u} thôi"),
    ("ORD-C09", "casual", "đổi {d} thành {q} {u} nha em"),
    ("ORD-C10", "casual", "order {q} {u} {d} nhé"),
    ("ORD-C11", "casual", "cho món {d} mà {r}"),
    ("ORD-C12", "casual", "em ơi {q} {u} {d} nha"),
    ("ORD-C13", "casual", "làm cho anh {q} {u} {d} với"),
    ("ORD-C14", "casual", "xóa {d} khỏi đơn giùm anh"),
    # -- dialect (Nam Bộ) -----------------------------------------------------
    ("ORD-D01", "dialect", "cho anh {q} {u} {d} nghen"),
    ("ORD-D02", "dialect", "lấy giùm anh {q} {u} {d} cái coi"),
    ("ORD-D03", "dialect", "{q} {u} {d} hen em"),
    ("ORD-D04", "dialect", "làm cho tui {q} {u} {d} đi mậy"),
    ("ORD-D05", "dialect", "cho thêm {q} {u} {d} nữa nghen"),
    ("ORD-D06", "dialect", "em ơi cho {q} {u} {d}, nhớ {r} nha"),
    ("ORD-D07", "dialect", "thôi bỏ {d} đi, đừng làm nữa"),
    ("ORD-D08", "dialect", "kêu {d} cho bàn này cái coi em"),
    ("ORD-D09", "dialect", "cho anh {q} {u} {d} lẹ giùm cái"),
    # -- fragment (câu cụt, kiểu nói nhanh) -----------------------------------
    ("ORD-G01", "fragment", "{q} {u} {d}"),
    ("ORD-G02", "fragment", "{d} {q} {u}"),
    ("ORD-G03", "fragment", "thêm {d}"),
    ("ORD-G04", "fragment", "{q} {d} nữa"),
    ("ORD-G05", "fragment", "bỏ {d}"),
    ("ORD-G06", "fragment", "{d} {r}"),
    ("ORD-G07", "fragment", "cho {d}"),
    ("ORD-G08", "fragment", "{q} {u} {d} nha"),
    # -- edge (dài dòng, nhiều mệnh đề nhưng vẫn một ý ORDER) -----------------
    ("ORD-E01", "edge", "em ơi cho anh gọi {q} {u} {d}, mà nhớ {r} giùm anh nha"),
    ("ORD-E02", "edge", "cho em hỏi là em muốn đặt {q} {u} {d} thì có lâu không ạ"),
    ("ORD-E03", "edge", "anh lấy {q} {u} {d}, còn lại để anh coi thêm rồi gọi sau"),
    ("ORD-E04", "edge", "nãy anh gọi {d} rồi mà giờ anh muốn tăng lên {q} {u}"),
    ("ORD-E05", "edge", "em cho anh {q} {u} {d} trước đi, mấy món kia lát nữa gọi tiếp"),
    ("ORD-E06", "edge", "cho tôi {q} {u} {d} nhưng mà làm {r} giùm tôi với nhé"),
    ("ORD-E07", "edge", "thôi em bỏ {d} ra giùm anh, anh đổi ý rồi"),
    ("ORD-E08", "edge", "bàn anh đông nên cho {q} {u} {d} luôn cho đủ nha em"),
    # Quản lý đơn — không có slot món. Eval hỏi ("Làm lại đơn mới giùm anh"),
    # corpus đầu tiên không có mẫu nào nên model đẩy sang PAYMENT.
    ("ORD-M01", "casual", "xóa hết đơn giùm anh"),
    ("ORD-M02", "casual", "làm lại đơn mới giùm anh"),
    ("ORD-M03", "casual", "bỏ hết đi gọi lại từ đầu"),
    ("ORD-M04", "casual", "hủy đơn giùm anh em ơi"),
    ("ORD-M05", "formal", "Cho tôi hủy toàn bộ đơn hiện tại ạ"),
    ("ORD-M06", "formal", "Em xóa giỏ hàng rồi ghi lại từ đầu giúp anh nhé"),
    ("ORD-M07", "dialect", "dẹp hết đơn đi em, gọi lại cái coi"),
    ("ORD-M08", "fragment", "hủy đơn"),
    ("ORD-M09", "fragment", "xóa hết"),
    ("ORD-M10", "fragment", "làm lại đơn"),
    ("ORD-M11", "edge", "em xóa hết mấy món nãy giùm anh rồi anh gọi lại từ đầu nha"),
]

# Câu ĐỒNG Ý / lệnh chốt đơn — nhãn ORDER. Đo được: giỏ chờ xác nhận thì worker
# confirm_order 15/15; giỏ trống thì nhóm đồng ý thuần delegate 8/8.
ORDER_AFFIRMATIONS: list[tuple[str, str]] = [
    ("casual", "ừ"), ("casual", "ừm"), ("casual", "ừ đi"), ("casual", "ok"),
    ("casual", "ok em"), ("casual", "ok luôn"), ("casual", "oke nha"),
    ("casual", "được"), ("casual", "được đó"), ("casual", "được rồi đó em"),
    ("casual", "chuẩn"), ("casual", "chuẩn luôn"), ("casual", "chính xác"),
    ("casual", "đúng rồi"), ("casual", "đúng rồi đó"), ("casual", "uh đúng rồi đó"),
    ("casual", "đúng đơn đó rồi"), ("casual", "vậy đi"), ("casual", "vậy nha"),
    ("casual", "đi"), ("casual", "làm đi"), ("casual", "ngon"),
    ("formal", "Dạ đúng ạ"), ("formal", "Vâng đúng rồi ạ"), ("formal", "Dạ em xác nhận ạ"),
    ("formal", "Đúng như vậy ạ"), ("formal", "Vâng ạ, cho em chốt đơn"),
    ("formal", "Tôi đồng ý với đơn hàng này"), ("formal", "Em xác nhận đơn nhé"),
    ("casual", "chốt đi em"), ("casual", "chốt luôn đi"), ("casual", "chốt đơn nha"),
    ("casual", "lên đơn đi em"), ("casual", "gửi bếp đi em"), ("casual", "cho vô bếp đi"),
    ("casual", "xác nhận giùm anh"), ("casual", "xác nhận đơn cho anh"),
    ("casual", "anh chốt nhiêu đó thôi"), ("casual", "nhiêu đó đủ rồi, chốt nha"),
    ("dialect", "ừ chốt nghen"), ("dialect", "chốt cho anh cái coi"),
    ("dialect", "đặng rồi đó em"), ("dialect", "vậy là được rồi hen"),
    ("dialect", "ừa đúng rồi đó em"), ("dialect", "cho lên đơn giùm cái coi"),
    ("dialect", "y chang vậy đó em"), ("dialect", "khỏi thêm gì nữa, chốt hen"),
    ("fragment", "chốt"), ("fragment", "xác nhận"), ("fragment", "đồng ý"),
    ("fragment", "ừ chốt"), ("fragment", "gửi bếp"), ("fragment", "lên đơn"),
    ("fragment", "oke chốt"), ("fragment", "đúng"),
    ("edge", "ừ đúng rồi đó em, chốt giùm anh luôn đi"),
    ("edge", "dạ đúng rồi ạ, em cho chốt đơn giùm em nha"),
    ("edge", "nhiêu đó là đủ rồi em, em gửi bếp giùm anh"),
    ("edge", "anh coi lại thấy đúng rồi, em lên đơn đi"),
    ("edge", "ok em, đơn vậy là chuẩn rồi đó, chốt nha"),
    ("edge", "đúng rồi em ơi, anh không đổi gì nữa đâu, chốt đi"),
    # Hàng xóm của các mẫu bị bộ lọc eval loại (ừ / ok / được / chuẩn / đúng rồi).
    ("casual", "ừa"), ("casual", "ừ ừ"), ("casual", "uh"), ("casual", "ukm"),
    ("casual", "okie"), ("casual", "ok nha em"), ("casual", "được nha"),
    ("casual", "được vậy đi"), ("casual", "chuẩn rồi em"), ("casual", "chuẩn không cần chỉnh"),
    ("casual", "đúng y vậy"), ("casual", "đúng vậy đó em"), ("casual", "phải rồi"),
    ("casual", "dạ phải"), ("casual", "chốt vậy nha"), ("casual", "vậy là xong nha em"),
    ("casual", "khỏi thêm gì nữa"), ("casual", "nhiêu đó thôi em"),
    ("fragment", "ừa"), ("fragment", "uh"), ("fragment", "okla"), ("fragment", "duyệt"),
    ("dialect", "ừa hen"), ("dialect", "đúng y chang"), ("dialect", "vậy là ngon rồi"),
]


# ------------------------------------------------------------------ SEARCH templates
# {d} dish, {d2} another dish, {g} group, {c} category, {t} tag, {w} taste word,
# {o} occasion.

SEARCH_DISH_TEMPLATES: list[tuple[str, str, str]] = [
    ("SEA-F01", "formal", "Cho em hỏi {d} giá bao nhiêu ạ"),
    ("SEA-F02", "formal", "Món {d} có cay không ạ"),
    ("SEA-F03", "formal", "{d} được chế biến như thế nào vậy em"),
    ("SEA-F04", "formal", "Quán mình còn {d} không ạ"),
    ("SEA-F05", "formal", "Em cho anh xin thông tin món {d} với"),
    ("SEA-F06", "formal", "{d} ăn được mấy người ạ"),
    ("SEA-F07", "formal", "Món {d} có phù hợp cho người ăn chay không ạ"),
    ("SEA-C01", "casual", "{d} bao nhiêu tiền vậy em"),
    ("SEA-C02", "casual", "{d} làm từ gì thế"),
    ("SEA-C03", "casual", "món {d} ngon không em"),
    ("SEA-C04", "casual", "bên mình bán {d} chứ em"),
    ("SEA-C05", "casual", "{d} ăn có ngán không"),
    ("SEA-C06", "casual", "cho xem hình {d} coi"),
    ("SEA-C07", "casual", "{d} với {d2} món nào ngon hơn"),
    ("SEA-C08", "casual", "{d} có nhiều không em"),
    ("SEA-C09", "casual", "giá {d} sao em"),
    ("SEA-C10", "casual", "{d} có đồ chấm gì kèm không"),
    ("SEA-D01", "dialect", "{d} mắc hông em"),
    ("SEA-D02", "dialect", "quán có {d} hông em"),
    ("SEA-D03", "dialect", "{d} ăn ra sao vậy em, kể anh nghe coi"),
    ("SEA-D04", "dialect", "cho coi món {d} cái coi"),
    ("SEA-D05", "dialect", "{d} có cay dữ hông"),
    ("SEA-D06", "dialect", "món {d} bên mình làm kiểu gì hen"),
    ("SEA-G01", "fragment", "{d} bao nhiêu"),
    ("SEA-G02", "fragment", "giá {d}"),
    ("SEA-G03", "fragment", "có {d} không"),
    ("SEA-G04", "fragment", "{d} mặn hay ngọt"),
    ("SEA-G05", "fragment", "{d} gồm gì"),
    ("SEA-G06", "fragment", "xem {d}"),
    ("SEA-E01", "edge", "cho em hỏi là món {d} bên mình có bị cay quá không, tại em ăn cay dở lắm"),
    ("SEA-E02", "edge", "anh đang phân vân giữa {d} với {d2}, em tư vấn giùm anh cái"),
    ("SEA-E03", "edge", "món {d} này ăn với {o} thì có hợp không em"),
    ("SEA-E04", "edge", "em ơi cho anh hỏi {d} giá nhiêu mà ăn có no không"),
    ("SEA-E05", "edge", "nghe nói {d} bên mình ngon lắm, em kể anh nghe món đó làm sao"),
]

SEARCH_BROWSE_TEMPLATES: list[tuple[str, str, str]] = [
    ("SEB-F01", "formal", "Cho em xem thực đơn với ạ"),
    ("SEB-F02", "formal", "Quán mình có những món {c} nào ạ"),
    ("SEB-F03", "formal", "Bên mình có món {t} nào không ạ"),
    ("SEB-F04", "formal", "Em tư vấn giúp anh món hợp cho {o} với"),
    ("SEB-F05", "formal", "Nhóm {g} có bao nhiêu kiểu ạ"),
    ("SEB-F06", "formal", "Có món nào {w} mà không quá đắt không em"),
    ("SEB-C01", "casual", "cho xem menu đi em"),
    ("SEB-C02", "casual", "quán có món {t} gì không"),
    ("SEB-C03", "casual", "món nào bán chạy nhất ở đây"),
    ("SEB-C04", "casual", "gợi ý vài món cho {o} đi em"),
    ("SEB-C05", "casual", "{g} có mấy kiểu vậy em"),
    ("SEB-C06", "casual", "có món nào {w} không"),
    ("SEB-C07", "casual", "bên mình có {c} không em"),
    ("SEB-C08", "casual", "món nào rẻ rẻ mà ngon chỉ anh coi"),
    ("SEB-C09", "casual", "hôm nay có món gì mới không em"),
    ("SEB-C10", "casual", "món nào đặc trưng của quán vậy"),
    ("SEB-D01", "dialect", "menu đâu em, đưa anh ngó cái"),
    ("SEB-D02", "dialect", "{c} bên mình làm mấy kiểu hen"),
    ("SEB-D03", "dialect", "kể anh nghe mấy món {t} coi"),
    ("SEB-D04", "dialect", "có gì {w} hông em, kêu thử coi"),
    ("SEB-D05", "dialect", "{g} bên mình làm mấy kiểu dzậy"),
    ("SEB-D06", "dialect", "chỉ giùm anh món nào hợp {o} cái coi"),
    ("SEB-G01", "fragment", "menu"),
    ("SEB-G02", "fragment", "món {t}"),
    ("SEB-G03", "fragment", "có {c} không"),
    ("SEB-G04", "fragment", "món {w}"),
    ("SEB-G05", "fragment", "best seller"),
    ("SEB-G06", "fragment", "{g} có gì"),
    ("SEB-E01", "edge", "em ơi bàn anh {o}, em gợi ý giùm anh mấy món cho hợp đi"),
    ("SEB-E02", "edge", "cho em hỏi quán mình có món nào {w} mà {o} ăn được không ạ"),
    ("SEB-E03", "edge", "anh mới tới lần đầu, em kể anh nghe mấy món {t} của quán coi"),
    ("SEB-E04", "edge", "em cho anh biết nhóm {g} bên mình có những kiểu gì để anh chọn"),
    ("SEB-E05", "edge", "quán mình món {c} với món {t} thì cái nào đáng thử hơn em"),
]


# ------------------------------------------------------------------- PAYMENT literals
PAYMENT_LITERALS: list[tuple[str, str]] = [
    ("formal", "Cho em xin hóa đơn ạ"),
    ("formal", "Em muốn thanh toán ạ"),
    ("formal", "Cho tôi thanh toán hóa đơn nhé"),
    ("formal", "Tổng cộng hết bao nhiêu tiền vậy em"),
    ("formal", "Em tính tiền giúp anh với ạ"),
    ("formal", "Cho em xin hóa đơn đỏ ạ"),
    ("formal", "Em cần xuất hóa đơn công ty được không ạ"),
    ("formal", "Anh muốn kiểm tra lại hóa đơn trước khi trả ạ"),
    ("formal", "Cho em hỏi đã bao gồm thuế chưa ạ"),
    ("formal", "Em xin biên lai thanh toán được không ạ"),
    ("casual", "tính tiền đi em"),
    ("casual", "cho xin bill"),
    ("casual", "bill đi em"),
    ("casual", "thanh toán nha em"),
    ("casual", "hết nhiêu tiền rồi em ơi"),
    ("casual", "tổng hết bao nhiêu"),
    ("casual", "cho anh trả tiền"),
    ("casual", "em ơi cho thanh toán"),
    ("casual", "tính giùm anh cái bill"),
    ("casual", "anh trả tiền rồi về nha"),
    ("casual", "cho xin cái hóa đơn coi lại"),
    ("casual", "bàn này hết nhiêu vậy em"),
    ("casual", "em cộng lại giùm anh coi đúng chưa"),
    ("casual", "nãy giờ ăn hết nhiêu rồi"),
    ("casual", "cho anh biết tổng tiền đi"),
    ("casual", "em ơi thanh toán giùm bàn anh"),
    ("casual", "trả tiền kiểu gì vậy em"),
    ("casual", "anh gửi tiền nha"),
    ("casual", "tính chung một bill nha em"),
    ("casual", "chia đôi bill giùm anh"),
    ("casual", "tách bill ra hai phần nha"),
    ("casual", "mỗi người trả riêng được không em"),
    ("casual", "cho anh hỏi có phụ thu gì không"),
    ("casual", "có tính phí phục vụ không em"),
    ("casual", "anh có voucher xài được không"),
    ("casual", "mã giảm giá này còn dùng được không"),
    ("casual", "anh là thành viên có được giảm không"),
    ("casual", "tiền thừa em khỏi thối nha"),
    ("dialect", "tính tiền cái coi em"),
    ("dialect", "hết nhiêu dzậy em"),
    ("dialect", "cho anh gửi tiền nghen"),
    ("dialect", "bill đâu em, đưa anh coi"),
    ("dialect", "tính giùm cái coi, anh về"),
    ("dialect", "nhiêu tiền hen em"),
    ("dialect", "em ơi cho thanh toán cái coi"),
    ("dialect", "bữa nay hết nhiêu dzậy"),
    ("dialect", "cộng lại giùm anh cái coi đúng hông"),
    ("dialect", "anh trả tiền mặt nghen em"),
    ("fragment", "tính tiền"),
    ("fragment", "bill"),
    ("fragment", "thanh toán"),
    ("fragment", "hết nhiêu"),
    ("fragment", "hóa đơn"),
    ("fragment", "tổng tiền"),
    ("fragment", "trả tiền"),
    ("fragment", "cho xin bill"),
    ("fragment", "bao nhiêu tiền"),
    ("fragment", "chia bill"),
    ("edge", "em ơi anh ăn xong rồi, em tính tiền giùm anh với nha"),
    ("edge", "cho anh hỏi tổng hết bao nhiêu để anh chuẩn bị tiền"),
    ("edge", "em kiểm tra lại bill giùm anh, hình như dư một món"),
    ("edge", "anh thấy bill hơi cao, em coi lại giùm anh mấy món đã gọi"),
    ("edge", "bàn anh có 4 người, em tách bill làm 4 phần bằng nhau giùm nha"),
    ("edge", "em cho anh thanh toán trước rồi anh ngồi thêm chút nữa được không"),
    ("edge", "anh muốn trả một nửa tiền mặt một nửa chuyển khoản được không em"),
    ("edge", "cho em hỏi là bên mình thanh toán xong có xuất hóa đơn điện tử không ạ"),
    # khiếu nại / sai sót trên bill
    ("casual", "sao mắc dữ vậy em"),
    ("casual", "anh đâu có gọi món này"),
    ("casual", "em tính dư một dĩa rồi"),
    ("casual", "món này anh trả lại mà sao còn trên bill"),
    ("casual", "em coi lại số lượng giùm anh"),
    ("casual", "hình như thiếu món khuyến mãi rồi em"),
    ("casual", "giá này khác với trên menu mà em"),
    ("formal", "Em kiểm tra lại giúp anh khoản này với ạ"),
    ("formal", "Anh nghĩ có nhầm lẫn trong hóa đơn ạ"),
    ("dialect", "sao nhiều dữ dzậy em, coi lại cái coi"),
    ("dialect", "món này anh có kêu đâu mà tính"),
    # tiền thối / đưa tiền
    ("casual", "em thối lại giùm anh"),
    ("casual", "anh đưa dư rồi đó"),
    ("casual", "em có tiền lẻ không"),
    ("casual", "khỏi thối, em giữ đi"),
    ("casual", "anh chỉ có tờ năm trăm thôi"),
    ("dialect", "thối lại bao nhiêu dzậy em"),
    ("fragment", "thối tiền"), ("fragment", "tiền lẻ"),
    # thời điểm trả
    ("casual", "anh trả trước rồi ngồi tiếp được không"),
    ("casual", "để lát nữa anh trả một lượt"),
    ("casual", "anh gửi trước phần của anh nha"),
    ("formal", "Anh muốn thanh toán ngay bây giờ ạ"),
    ("edge", "em cho anh trả trước phần nhậu, còn đồ ăn lát tính sau nha"),
    # chứng từ
    ("casual", "in cho anh hai bản nha"),
    ("casual", "gửi hóa đơn qua zalo giùm anh"),
    ("casual", "anh cần mã số thuế công ty"),
    ("formal", "Em xuất hóa đơn theo thông tin công ty giúp anh ạ"),
    ("fragment", "hóa đơn điện tử"), ("fragment", "xuất hóa đơn"),
    # phụ thu / cọc
    ("casual", "anh đặt cọc hôm trước rồi đó em"),
    ("casual", "tiền cọc có trừ vào đây không"),
    ("casual", "khăn lạnh có tính tiền không em"),
    ("casual", "đậu phộng dọn sẵn có tính không"),
    ("dialect", "mấy món dọn sẵn có tính tiền hông em"),
]

PAYMENT_METHOD_TEMPLATES: list[tuple[str, str, str]] = [
    ("PAY-M01", "casual", "quán có nhận {m} không em"),
    ("PAY-M02", "casual", "anh trả bằng {m} được không"),
    ("PAY-M03", "formal", "Bên mình có hỗ trợ {m} không ạ"),
    ("PAY-M04", "casual", "cho anh thanh toán {m} nha"),
    ("PAY-M05", "dialect", "trả {m} được hông em"),
    ("PAY-M06", "fragment", "{m} được không"),
    ("PAY-M07", "formal", "Em cho anh xin thông tin để {m} ạ"),
    ("PAY-M08", "edge", "em ơi anh không mang đủ tiền mặt, cho anh {m} phần còn lại nha"),
    ("PAY-M09", "casual", "máy {e} của quán còn hoạt động không em"),
    ("PAY-M10", "dialect", "bên mình xài {m} được hen"),
    ("PAY-M11", "edge", "anh định trả {e} mà sóng yếu quá, em chờ anh chút nha"),
    ("PAY-M12", "formal", "Nếu thanh toán {m} thì có mất phí gì không ạ"),
]

# Chia bill theo số người — {n} slot. Đây là tình huống nhà hàng nhậu gặp liên tục.
PAYMENT_SPLIT_TEMPLATES: list[tuple[str, str, str]] = [
    ("PAY-S01", "casual", "bàn anh {n} người, chia đều ra nha em"),
    ("PAY-S02", "casual", "tách hóa đơn thành {n} phần giùm anh"),
    ("PAY-S03", "formal", "Em chia hóa đơn cho {n} người giúp anh với ạ"),
    ("PAY-S04", "dialect", "tụi anh {n} đứa, chia ra cái coi em"),
    ("PAY-S05", "fragment", "chia {n} phần"),
    ("PAY-S06", "edge", "nhóm anh có {n} người nhưng hai người về trước rồi, em tính riêng giùm"),
    ("PAY-S07", "casual", "{n} người trả chung một thẻ được không em"),
]


# --------------------------------------------------------------- SEARCH service templates
# Tra cứu phi cá nhân về quán: ship, giờ giấc, chỗ đậu xe, đặt tiệc, khuyến mãi, chi nhánh.
# Đây là SEARCH chứ không phải CHAT vì restaurant_info.txt NẰM TRONG chỉ mục RAG
# (scripts/setup.py, document_loader.py), nên search tool trả lời được. Bản corpus đầu tiên
# gán nhóm này là CHAT và đó là nguyên nhân lớn nhất khiến model mới thua model cũ.
SEARCH_SERVICE_TEMPLATES: list[tuple[str, str, str]] = [
    # -- ship / giao hàng (corpus đầu gần như trắng nhóm này) -------------------
    ("SES-01", "casual", "quán có ship về {z} không"),
    ("SES-02", "casual", "ship về {z} bao nhiêu tiền vậy em"),
    ("SES-03", "casual", "giao hàng về {z} mất bao lâu"),
    ("SES-04", "formal", "Bên mình có giao hàng về {z} không ạ"),
    ("SES-05", "dialect", "có giao về {z} hông em"),
    ("SES-06", "fragment", "ship {z}"),
    ("SES-07", "casual", "shop có giao hàng buổi tối không"),
    ("SES-08", "casual", "quán mình có giao tận nơi không em"),
    ("SES-09", "formal", "Phí giao hàng bên mình tính thế nào ạ"),
    ("SES-10", "edge", "anh ở {z}, không biết quán mình có ship tới đó không em"),
    # -- chi nhánh -------------------------------------------------------------
    ("SES-11", "casual", "quán mình ở {b} còn mở không em"),
    ("SES-12", "formal", "Chi nhánh {b} nằm ở đường nào ạ"),
    ("SES-13", "dialect", "chi nhánh {b} đông hông em"),
    ("SES-14", "fragment", "chi nhánh {b}"),
    ("SES-15", "casual", "quán {b} có chỗ đậu xe hơi không"),
    ("SES-16", "formal", "Bên {b} có nhận đặt tiệc không ạ"),
    ("SES-17", "edge", "anh hay đi công tác {b}, quán mình có chi nhánh bên đó không em"),
    # -- giờ giấc / tiện ích ---------------------------------------------------
    ("SES-18", "casual", "quán đóng cửa lúc mấy giờ vậy em"),
    ("SES-19", "formal", "Nhà hàng mình phục vụ tới khung giờ nào ạ"),
    ("SES-20", "dialect", "quán mở từ mấy giờ dzậy em"),
    ("SES-21", "fragment", "giờ mở cửa"),
    ("SES-22", "casual", "quán mình có chỗ để xe máy không"),
    ("SES-23", "casual", "bên mình có phòng máy lạnh riêng không em"),
    ("SES-24", "formal", "Quán mình có khu vực cho gia đình có trẻ nhỏ không ạ"),
    ("SES-25", "dialect", "quán có chỗ gửi xe hông em"),
    ("SES-26", "fragment", "chỗ đậu xe"),
    ("SES-27", "casual", "wifi bên mình tên gì vậy em"),
    ("SES-28", "casual", "bên mình có nhận đặt bàn trước không"),
    ("SES-29", "formal", "Quán có nhận đặt tiệc sinh nhật không ạ"),
    ("SES-30", "edge", "quán mình có chỗ ngồi ngoài trời không, anh muốn dẫn nhóm bạn tới"),
    # -- khuyến mãi (tra cứu, khác với việc áp mã lúc trả tiền) -----------------
    ("SES-31", "casual", "hôm nay có chương trình khuyến mãi gì không em"),
    ("SES-32", "formal", "Bên mình đang có ưu đãi nào không ạ"),
    ("SES-33", "dialect", "có giảm giá gì hông em"),
    ("SES-34", "fragment", "khuyến mãi"),
    ("SES-35", "casual", "quán có combo nào rẻ hơn không"),
    ("SES-36", "casual", "hotline quán mình số mấy vậy em"),
]

# ---------------------------------------------------------------------- CHAT literals
CHAT_LITERALS: list[tuple[str, str]] = [
    # chào hỏi / cảm ơn
    ("formal", "Xin chào em"), ("formal", "Chào em nhé"),
    ("formal", "Em khỏe không"), ("formal", "Cảm ơn em nhiều ạ"),
    ("formal", "Cảm ơn em đã phục vụ ạ"), ("formal", "Em vất vả rồi"),
    ("formal", "Chúc quán mình buôn may bán đắt ạ"), ("formal", "Hẹn gặp lại em nhé"),
    ("casual", "alo em ơi"), ("casual", "chào em"), ("casual", "hi em"),
    ("casual", "cảm ơn em"), ("casual", "cảm ơn nhiều nha"), ("casual", "thanks em"),
    ("casual", "ok cảm ơn em nhiều"), ("casual", "em dễ thương ghê"),
    ("casual", "chào nha em, anh về đây"), ("casual", "bữa sau anh ghé nữa"),
    ("dialect", "ê em ơi"), ("dialect", "chào em nghen"),
    ("dialect", "cảm ơn em nhiều nghen"), ("dialect", "em giỏi quá hen"),
    ("dialect", "thôi anh dzìa nghen em"), ("dialect", "bữa nào ghé nữa nghen"),
    ("fragment", "chào em"), ("fragment", "cảm ơn"), ("fragment", "hello"),
    ("fragment", "alo"), ("fragment", "bye em"), ("fragment", "ok thanks"),
    # khen / chê
    ("casual", "đồ ăn ở đây ngon quá trời"),
    ("casual", "món này ngon dữ vậy"),
    ("casual", "quán trang trí đẹp ghê"),
    ("casual", "nhạc ở đây nghe cũng được á"),
    ("casual", "phục vụ nhanh ghê em"),
    ("casual", "ốc tươi thiệt luôn"),
    ("casual", "hơi mặn so với anh"),
    ("casual", "món này nguội mất rồi em"),
    ("casual", "sao lâu quá vậy em"),
    ("casual", "quán đông ghê ha"),
    ("casual", "bàn này hơi ồn em ơi"),
    ("casual", "máy lạnh yếu quá em"),
    ("formal", "Món ăn rất vừa miệng ạ"),
    ("formal", "Anh thấy chất lượng ổn lắm"),
    ("formal", "Em cho anh góp ý một chút nhé"),
    ("dialect", "ngon bá cháy luôn em ơi"),
    ("dialect", "quán này được đó nghen"),
    ("dialect", "ăn đã miệng thiệt chớ"),
    # nhu cầu cá nhân chạm tới tiện ích — eval gán CHAT cho dạng "Tôi ...",
    # và gán SEARCH cho dạng tra cứu phi cá nhân "Quán có ...". Ranh giới theo chủ ngữ.
    ("casual", "anh muốn đặt bàn trước cho tối mai"),
    ("casual", "anh có con nhỏ nên cần ghế em bé"),
    ("casual", "anh mang bánh sinh nhật vào được không"),
    ("casual", "anh gửi xe ngoài kia có sao không"),
    ("casual", "anh ngồi bàn này được chưa em"),
    ("casual", "tụi anh muốn ngồi ngoài trời cho mát"),
    ("casual", "anh đợi bạn tới rồi gọi món sau"),
    ("casual", "anh tính ra cũng gần nhà thôi"),
    ("casual", "để anh tính lại đã"),
    ("formal", "Tôi muốn đặt chỗ cho sáu người tối nay ạ"),
    ("formal", "Tôi cần một chỗ yên tĩnh để tiếp khách ạ"),
    ("formal", "Tôi đi cùng người lớn tuổi nên cần bàn dễ ngồi ạ"),
    ("dialect", "tui ngồi đại đây nghen em"),
    ("dialect", "anh dắt nguyên nhà tới đó nghen"),
    ("edge", "anh muốn giữ chỗ cho nhóm mười người tối thứ bảy, em ghi giùm anh nha"),
    # gọi nhân viên / linh tinh trong bàn
    ("casual", "em ơi qua đây chút"),
    ("casual", "cho anh xin thêm chén"),
    ("casual", "cho xin đôi đũa nữa em"),
    ("casual", "lấy giùm anh mấy tờ khăn giấy"),
    ("casual", "cho xin thêm đá"),
    ("casual", "dọn bớt dĩa trên bàn giùm em"),
    ("casual", "cho anh mượn cái mở bia"),
    ("casual", "em lau bàn giùm anh cái"),
    ("dialect", "em ơi lại đây cái coi"),
    ("dialect", "cho xin cái khăn cái coi em"),
    ("fragment", "em ơi"), ("fragment", "cho xin chén"),
    ("fragment", "thêm đũa"), ("fragment", "khăn giấy"),
    # ngoài phạm vi
    ("casual", "trời hôm nay mưa to thật"),
    ("casual", "kẹt xe quá trời luôn"),
    ("casual", "tối nay có đá banh không em"),
    ("casual", "em làm ở đây lâu chưa"),
    ("casual", "em tên gì vậy"),
    ("casual", "em là người thật hay máy vậy"),
    ("casual", "em có biết đường ra biển không"),
    ("casual", "mai anh đi Đà Lạt chơi"),
    ("casual", "dạo này làm ăn sao rồi em"),
    ("formal", "Em có biết gần đây có khách sạn nào không ạ"),
    ("formal", "Anh hỏi ngoài lề chút được không em"),
    ("dialect", "nay trời nóng quá hen"),
    ("dialect", "em người ở đây luôn hả"),
    ("fragment", "trời mưa quá"), ("fragment", "nóng quá"),
    ("edge", "em ơi anh hỏi thật chứ em là robot hay là người vậy, nghe giọng lạ lạ"),
    ("edge", "nay cuối tuần chắc quán đông lắm ha em, anh thấy bãi xe kín hết rồi"),
    ("edge", "anh ở Sài Gòn xuống chơi, nghe bạn giới thiệu quán này nên ghé thử"),
    ("edge", "em ơi cho anh hỏi ngoài lề chút, gần đây có chỗ nào đi dạo được không"),
    # dị ứng / kiêng khem — lấy từ customer_info.json
    ("casual", "anh dị ứng đậu phộng nha em"),
    ("casual", "anh không ăn được cay đâu"),
    ("casual", "vợ anh đang ăn chay đó"),
    ("casual", "bé nhà anh không ăn được hải sản"),
    ("casual", "anh đang kiêng dầu mỡ"),
    ("formal", "Em lưu ý giúp anh là anh bị dị ứng hải sản ạ"),
    ("formal", "Nhà anh có người ăn chay trường ạ"),
    ("dialect", "anh ăn cay dở lắm nghen em"),
    ("fragment", "dị ứng đậu phộng"), ("fragment", "ăn chay"),
    # khách quen / ưu đãi
    ("casual", "anh là khách quen ở đây đó"),
    ("casual", "anh có thẻ thành viên"),
    ("casual", "lần trước anh ngồi bàn ngoài kia"),
    ("formal", "Anh đã đăng ký thành viên bên mình rồi ạ"),
    ("dialect", "anh ghé đây hoài à nghen"),
    # trẻ em / nhóm
    ("casual", "cho anh xin cái ghế cho bé"),
    ("casual", "bàn anh có con nít nên để xa bếp nha"),
    ("casual", "lát nữa có thêm hai người tới"),
    ("casual", "ghép bàn cho tụi anh được không em"),
    ("formal", "Bên mình có khu vực riêng cho gia đình không ạ"),
    # không khí quán
    ("casual", "mở nhạc nhỏ lại chút được không em"),
    ("casual", "quạt chỗ này không chạy em ơi"),
    ("casual", "đèn bàn này hơi tối"),
    ("casual", "chỗ này nắng quá, đổi bàn được không"),
    ("dialect", "ở đây muỗi dữ hen em"),
    # nhân viên
    ("casual", "em làm ca tối hoài hả"),
    ("casual", "quán mình đông nhân viên ghê"),
    ("casual", "cho anh gặp quản lý chút"),
    ("formal", "Anh muốn khen ngợi nhân viên phục vụ ạ"),
    # tạm biệt / hẹn gặp
    ("casual", "thôi anh về nha em"),
    ("casual", "lần sau anh dẫn bạn tới"),
    ("formal", "Cảm ơn quán đã phục vụ chu đáo ạ"),
    ("dialect", "bữa nào rảnh anh ghé lại nghen"),
    # ngoài phạm vi thêm
    ("casual", "em biết chỗ nào hát karaoke gần đây không"),
    ("casual", "taxi ở đây dễ bắt không em"),
    ("casual", "mai có bão không ta"),
    ("casual", "em thấy đội nào vô địch"),
    ("formal", "Em có biết đường ra bến xe không ạ"),
    ("edge", "anh hỏi thiệt chứ giọng em nghe như người máy vậy, quán mình xài công nghệ gì thế"),
    # kể chuyện / cảm nhận cá nhân — eval gán CHAT cho nhóm này
    ("casual", "lần đầu anh tới quán nè"),
    ("casual", "quán này mới mở hả em"),
    ("casual", "anh no quá rồi"),
    ("casual", "hôm nay quán vắng ha"),
    ("casual", "em nói chuyện dễ thương ghê"),
    ("casual", "anh thấy quán mình đông khách ghê"),
    ("casual", "anh đọc review trên mạng thấy khen quán mình quá trời"),
    ("casual", "bạn anh giới thiệu chỗ này đó"),
    ("casual", "anh đi ngang thấy quán đẹp nên ghé thử"),
    ("casual", "anh muốn gọi thêm mà quên tên món rồi"),
    ("casual", "anh ăn ở đây hoài mà nay mới thấy em"),
    ("casual", "chỗ này hợp đi nhậu ghê"),
    ("casual", "anh no rồi khỏi gọi thêm"),
    ("casual", "nay anh ăn hơi nhiều"),
    ("casual", "anh thấy vui khi ghé đây"),
    ("formal", "Lần đầu tôi tới nhà hàng mình ạ"),
    ("formal", "Tôi rất hài lòng với bữa ăn hôm nay ạ"),
    ("formal", "Tôi muốn gửi lời khen tới bếp ạ"),
    ("formal", "Tôi thấy không gian quán rất dễ chịu ạ"),
    ("formal", "Tôi sẽ giới thiệu quán cho bạn bè ạ"),
    ("dialect", "lần đầu tui ghé đây đó nghen"),
    ("dialect", "chỗ này vui dữ hen"),
    ("dialect", "anh no cành hông rồi"),
    ("dialect", "nghe đồn quán này ngon nên tới thử"),
    ("fragment", "no rồi"), ("fragment", "vui ghê"), ("fragment", "lần đầu tới"),
    ("fragment", "quán đẹp"), ("fragment", "ngon thiệt"),
    ("edge", "anh bị dị ứng hải sản nên hơi ngại, em coi giùm anh có gì ăn được không"),
    ("edge", "anh ăn no quá rồi, chắc lát nữa mới gọi thêm được"),
    ("edge", "anh với bạn anh lần đầu tới quán nên chưa biết gọi gì cho hợp"),
]

# Câu HOÃN / lấp chỗ trống — bắt buộc là CHAT.
# Đo được: gán ORDER thì worker gọi clear_cart và xóa sạch giỏ đang có món.
CHAT_DEFERRALS: list[tuple[str, str]] = [
    ("casual", "thôi"), ("casual", "thôi khỏi"), ("casual", "à mà thôi"),
    ("casual", "thôi để lát nữa"), ("casual", "khoan đã"), ("casual", "khoan em"),
    ("casual", "từ từ"), ("casual", "từ từ đã em"), ("casual", "chờ xíu"),
    ("casual", "đợi anh chút"), ("casual", "để xem đã"), ("casual", "để anh coi lại"),
    ("casual", "để anh suy nghĩ tí"), ("casual", "chưa biết nữa"),
    ("casual", "anh chưa quyết được"), ("casual", "để anh hỏi mọi người đã"),
    ("casual", "đợi bạn anh tới rồi gọi"), ("casual", "chút nữa gọi tiếp nha em"),
    ("casual", "anh coi menu thêm chút"), ("casual", "chưa gọi vội em"),
    ("formal", "Cho em suy nghĩ thêm một chút ạ"),
    ("formal", "Anh xem thêm rồi gọi sau nhé"),
    ("formal", "Em đợi anh một lát nhé"),
    ("formal", "Anh chưa quyết định được, để lát nữa ạ"),
    ("dialect", "khoan cái coi em"), ("dialect", "từ từ hen em"),
    ("dialect", "để anh ngó lại cái coi"), ("dialect", "chờ chút nghen em"),
    ("dialect", "thôi khoan, để tính lại đã"),
    ("fragment", "khoan"), ("fragment", "đợi"), ("fragment", "chờ chút"),
    ("fragment", "để xem"), ("fragment", "chưa"), ("fragment", "từ từ"),
    ("edge", "khoan em ơi, để anh coi lại menu chút rồi anh gọi một thể"),
    ("edge", "thôi để lát nữa bạn anh tới rồi anh gọi luôn một lần cho tiện"),
    ("edge", "anh chưa quyết được, em cho anh thêm vài phút nha"),
    ("edge", "từ từ đã em, anh còn đang phân vân mấy món"),
    # Hàng xóm của các mẫu hoãn bị bộ lọc eval loại (thôi / thôi khỏi / à mà thôi / khoan đã).
    ("casual", "thôi kệ đi"), ("casual", "thôi bỏ đi"), ("casual", "thôi khỏi cần"),
    ("casual", "à quên"), ("casual", "à thôi khỏi"), ("casual", "ấy khoan"),
    ("casual", "gượm đã em"), ("casual", "hượm cái"), ("casual", "để coi đã"),
    ("casual", "để tính sau"), ("casual", "chuyện đó tính sau"), ("casual", "lát nữa hẵng hay"),
    ("casual", "chưa chắc nữa"), ("casual", "chưa nghĩ ra"), ("casual", "hên xui à"),
    ("casual", "để anh cân nhắc"), ("casual", "anh đang lưỡng lự"),
    ("fragment", "thôi kệ"), ("fragment", "gượm"), ("fragment", "chưa quyết"),
    ("dialect", "khoan cái đã hen"), ("dialect", "thủng thẳng đã em"),
    ("edge", "chưa biết nữa em ơi, để anh tính sau rồi nói em hay"),
    ("edge", "thôi kệ đi, lát nữa tính tiếp cũng được mà"),
]


# ------------------------------------------------------------------------ generation

def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s.lower().strip().rstrip(".,!?"))


def _units_for(dish: dict[str, Any]) -> tuple[str, ...]:
    return UNITS_BY_CATEGORY.get(dish["category"], _FALLBACK_UNITS)


def _dish_surface(name: str, rng: random.Random, style: str) -> str:
    """Whisper capitalises inconsistently; formal/edge keep the menu casing, the
    casual/dialect/fragment registers are usually transcribed lower case."""
    if style in ("formal", "edge"):
        return name
    return name.lower() if rng.random() < 0.65 else name


def _cap_first(text: str, style: str) -> str:
    if style in ("formal", "edge") and text:
        return text[0].upper() + text[1:]
    return text


def _fill(template: str, style: str, dish: dict, menu: list[dict], rng: random.Random) -> str:
    out = template
    if "{d}" in out:
        out = out.replace("{d}", _dish_surface(dish["name"], rng, style))
    if "{d2}" in out:
        other = rng.choice([m for m in menu if m["name"] != dish["name"]])
        out = out.replace("{d2}", _dish_surface(other["name"], rng, style))
    if "{q}" in out:
        out = out.replace("{q}", str(rng.choice(QUANTITIES)))
    if "{u}" in out:
        out = out.replace("{u}", rng.choice(_units_for(dish)))
    if "{r}" in out:
        out = out.replace("{r}", rng.choice(SPECIAL_REQUESTS))
    if "{g}" in out:
        groups = sorted({m["group"] for m in menu if m.get("group")})
        out = out.replace("{g}", rng.choice(groups))
    if "{c}" in out:
        out = out.replace("{c}", rng.choice(sorted({m["category"] for m in menu})))
    if "{t}" in out:
        tags = sorted({t.strip() for m in menu for t in m.get("tags", "").split(",") if t.strip()})
        out = out.replace("{t}", rng.choice(tags))
    if "{w}" in out:
        out = out.replace("{w}", rng.choice(TASTE_WORDS))
    if "{o}" in out:
        out = out.replace("{o}", rng.choice(OCCASIONS))
    if "{m}" in out:
        out = out.replace("{m}", rng.choice(PAY_METHODS))
    if "{e}" in out:
        out = out.replace("{e}", rng.choice(PAY_METHODS_ELECTRONIC))
    if "{z}" in out:
        out = out.replace("{z}", rng.choice(DELIVERY_AREAS))
    if "{n}" in out:
        out = out.replace("{n}", str(rng.choice((2, 3, 4, 5, 6, 7, 8))))
    if "{b}" in out:
        out = out.replace("{b}", rng.choice(BRANCHES))
    return _cap_first(out, style)


def _dish_cycle(menu: list[dict], rng: random.Random) -> Iterator[dict]:
    """Every dish before any repeat, so 234-dish coverage is structural, not luck."""
    while True:
        order = list(menu)
        rng.shuffle(order)
        yield from order


def build_slot_records(
    templates: list[tuple[str, str, str]],
    intent: str,
    target: int,
    menu: list[dict],
    rng: random.Random,
    dish_driven: bool = True,
) -> list[dict[str, Any]]:
    """Cycle templates x dishes so each template is reused with a different dish."""
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    cycle = _dish_cycle(menu, rng)
    guard = 0
    while len(records) < target and guard < target * 40:
        # Advance on the attempt counter, not on len(records): a slot-free template
        # (e.g. the ORD-M order-management ones) renders the same string every time, so
        # indexing by len(records) would pin the cycle to it and spin until the guard.
        tid, style, tpl = templates[guard % len(templates)] if dish_driven else rng.choice(templates)
        guard += 1
        dish = next(cycle)
        text = _fill(tpl, style, dish, menu, rng)
        key = _norm(text)
        if key in seen:
            continue
        seen.add(key)
        records.append({
            "utterance": text,
            "intent": intent,
            "style": style,
            "source": "template",
            "dish": dish["name"] if "{d}" in tpl else None,
            "template_id": tid,
        })
    return records


def build_literal_records(
    literals: list[tuple[str, str]],
    intent: str,
    source: str = "handwritten",
) -> list[dict[str, Any]]:
    return [
        {"utterance": text, "intent": intent, "style": style,
         "source": source, "dish": None, "template_id": None}
        for style, text in literals
    ]


def ensure_dish_coverage(
    records: list[dict[str, Any]],
    menu: list[dict],
    templates: list[tuple[str, str, str]],
    intent: str,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Append utterances for any dish the sampler missed. Coverage is a hard requirement:
    the previous corpus named 30 of 234 dishes and that ceiling showed up directly in
    unseen-utterance accuracy."""
    covered = {r["dish"] for r in records if r["dish"]}
    missing = [m for m in menu if m["name"] not in covered]
    seen = {_norm(r["utterance"]) for r in records}
    dish_templates = [t for t in templates if "{d}" in t[2]]
    extra: list[dict[str, Any]] = []
    for i, dish in enumerate(missing):
        for attempt in range(len(dish_templates)):
            tid, style, tpl = dish_templates[(i + attempt) % len(dish_templates)]
            text = _fill(tpl, style, dish, menu, rng)
            if _norm(text) not in seen:
                seen.add(_norm(text))
                extra.append({
                    "utterance": text, "intent": intent, "style": style,
                    "source": "template-coverage", "dish": dish["name"], "template_id": tid,
                })
                break
    return extra


EVAL_FILES = (
    PROJECT_ROOT / "evals" / "data" / "router" / "single_intent_eval.json",
    PROJECT_ROOT / "evals" / "data" / "router" / "context_dependent_eval.json",
    PROJECT_ROOT / "evals" / "data" / "router" / "multi_intent_detection.json",
    Path(__file__).resolve().parent / "test_holdout.json",
)


def eval_utterances() -> set[str]:
    """Every utterance already spoken for by an eval set. The corpus must not contain
    these — 45% of single_intent_eval and 51% of test_holdout leaked into the previous
    training data, which is why its reported accuracy was not a held-out number."""
    out: set[str] = set()
    for path in EVAL_FILES:
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            blob = json.load(f)
        cases = blob.get("cases") if isinstance(blob, dict) else blob
        if not isinstance(cases, list):
            continue
        for c in cases:
            if isinstance(c, dict) and c.get("utterance"):
                out.add(_norm(c["utterance"]))
    return out


def build_corpus(seed: int = 20260729) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    menu = load_menu()

    order = build_slot_records(ORDER_TEMPLATES, "ORDER", 450, menu, rng)
    order += ensure_dish_coverage(order, menu, ORDER_TEMPLATES, "ORDER", rng)
    order += build_literal_records(ORDER_AFFIRMATIONS, "ORDER")

    search = build_slot_records(SEARCH_DISH_TEMPLATES, "SEARCH", 300, menu, rng)
    search += ensure_dish_coverage(search, menu, SEARCH_DISH_TEMPLATES, "SEARCH", rng)
    search += build_slot_records(SEARCH_BROWSE_TEMPLATES, "SEARCH", 150, menu, rng, dish_driven=False)
    search += build_slot_records(SEARCH_SERVICE_TEMPLATES, "SEARCH", 105, menu, rng, dish_driven=False)

    payment = build_literal_records(PAYMENT_LITERALS, "PAYMENT")
    payment += build_slot_records(PAYMENT_METHOD_TEMPLATES, "PAYMENT", 85, menu, rng, dish_driven=False)
    payment += build_slot_records(PAYMENT_SPLIT_TEMPLATES, "PAYMENT", 56, menu, rng, dish_driven=False)

    chat = build_literal_records(CHAT_LITERALS, "CHAT")
    chat += build_literal_records(CHAT_DEFERRALS, "CHAT", source="handwritten-deferral")

    records = order + search + payment + chat

    # Global exact-dedup + eval exclusion; first occurrence wins so handwritten beats
    # generated. The eval filter runs here, not as a post-hoc gate, so an utterance that
    # collides with a benchmark is simply never minted.
    reserved = eval_utterances()
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in records:
        k = _norm(r["utterance"])
        if k in seen or k in reserved:
            continue
        seen.add(k)
        unique.append(r)

    rng.shuffle(unique)
    for i, r in enumerate(unique, 1):
        r["id"] = f"OQ-{i:04d}"
    return unique
