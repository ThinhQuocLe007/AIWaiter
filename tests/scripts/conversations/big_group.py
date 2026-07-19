"""Scenario B — Big Group (12 turns)."""

from .base import Conversation, Turn

BIG_GROUP = Conversation(
    name="B — Big Group",
    table_id="T2",
    party_size=6,
    turns=[
        Turn("Xin chào, tụi mình 6 người. Tư vấn vài món cho bàn đông người đi em",
             "group-size recommendations", "SEARCH"),
        Turn("Tụi mình có 2 người ăn chay. Có món chay nào không em?",
             "diet-constrained search (chay)", "SEARCH"),
        Turn("Có lẩu nào cho 6 người không? Tầm giá dưới 1 triệu",
             "budget-constrained search", "SEARCH"),
        Turn("Nhóm mặn gọi trước. Cho 2 Lẩu Thái, 2 Ốc Hương Xốt Trứng Muối, 3 Tôm Thẻ Nướng Muối Ớt",
             "large multi-item order", "ORDER"),
        Turn("Nhóm chay: 2 Mì Xào Rau với 2 Bánh Mì Bơ Tỏi",
             "vegetarian order", "ORDER"),
        Turn("Cả bàn 6 Bia Sài Gòn với 3 Nước Suối nữa",
             "drinks", "ORDER"),
        Turn("Đổi 2 Bia Sài Gòn qua 2 Bia Heineken đi. Với cho hỏi Bánh Mì Bơ Tỏi có hành không? Có đứa dị ứng hành",
             "remove+add + allergen query", "ORDER"),
        Turn("À tụi mình thêm 1 Lẩu Khổ Qua Cá Thác Lác, nghe nói món đó cũng ngon mà đỡ cay hơn Lẩu Thái",
             "comparison-based add", "ORDER"),
        Turn("Xem lại full đơn cả bàn đi em",
             "cart review", "SEARCH"),
        Turn("Bỏ bớt 1 Lẩu Thái, thay bằng 2 Soup Tomyum Thố Nhỏ. Rồi chốt luôn",
             "substitution + confirm", "ORDER"),
        Turn("Ok xác nhận",
             "confirm", "ORDER_CONFIRM"),
        Turn("Tính tiền đi em",
             "request payment", "PAYMENT"),
    ],
)
