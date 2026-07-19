"""Scenario C — Picky Customer (14 turns)."""

from .base import Conversation, Turn

PICKY_CUSTOMER = Conversation(
    name="C — Picky Customer",
    table_id="T3",
    party_size=1,
    turns=[
        Turn("Dô, nay quán vắng quá vậy? Có gì ăn không em?",
             "informal, complaint-ish greeting", "SEARCH"),
        Turn("Cho anh xem món nào lạ miệng, đặc biệt một chút. Mấy món thường anh ăn chán rồi",
             "unique dish query", "SEARCH"),
        Turn("Mấy món cũng thường thôi. Ủa mà quán có món Cá Mặt Quỷ không em? Có báo viết khen lắm",
             "OFF-MENU — Cá Mặt Quỷ not in menu", "SEARCH"),
        Turn("Ủa kỳ, Cá Mặt Quỷ không có hả? Vậy cá gì lạ lạ ở đây cho anh coi",
             "push-back + alternative search", "SEARCH"),
        Turn("Cá Chim Nướng Sa Tế bao nhiêu? Mà có cay lắm không? Nghe sa tế là thấy cay rồi",
             "multi-question about found dish", "SEARCH"),
        Turn("Thôi được, cho anh 1 Sò Điệp Nướng Phô Mai, 1 Ốc Hương Xốt Trứng Muối. Mà khoan, giá sao vậy?",
             "order + price check", "SEARCH"),
        Turn("Cho thêm 1 Bào Ngư Nướng Bơ Tỏi đi. À mà Tôm Hùm ở đây có không em?",
             "order + OFF-MENU search (Tôm Hùm)", "ORDER"),
        Turn("Ủa Tôm Hùm cũng không có luôn hả? Vậy hải sản cao cấp nhất ở đây là món gì?",
             "push-back, asks for premium alternatives", "SEARCH"),
        Turn("Thôi kệ, lấy thêm 2 Hàu Nướng Phô Mai với 1 Gỏi Hải Sản đi. Đồ ăn có tươi không đó?",
             "order + subjective quality question", "ORDER"),
        Turn("Sò Điệp Nướng Phô Mai với Sò Điệp Nướng Mỡ Hành món nào ngon hơn?",
             "comparison between two variants", "SEARCH"),
        Turn("Lấy thêm 1 Sò Điệp Nướng Mỡ Hành đi. Rồi bỏ món Gỏi Hải Sản, đổi qua Gỏi Xoài Ốc Giác cho gọn",
             "substitution chain", "ORDER"),
        Turn("Xem lại đơn coi, thấy hơi ít, lấy thêm gì ta...",
             "cart review + browsing", "SEARCH"),
        Turn("Ok chốt đơn luôn, nhớ làm nhanh nha, đói bụng rồi",
             "urgency + confirm", "ORDER_CONFIRM"),
        Turn("Tính tiền",
             "request payment", "PAYMENT"),
    ],
)
