"""Scenario E — Grilled Meat → Hotpot switch → Call again → Remove confirmed → New order → Payment (10 turns).

Kịch bản: Hỏi thịt nướng → order gà → đổi lẩu → thêm món → confirm → gọi lại → cố xóa món đã confirm → order món mới → confirm → tính tiền.
"""

from .base import Conversation, Turn

GRILL_TO_HOTPOT = Conversation(
    name="E — Grill to Hotpot Switch",
    table_id="T5",
    party_size=2,
    turns=[
        Turn("Quán có món thịt nướng nào không em?",
             "ask about grilled meat", "SEARCH"),
        Turn("Cho mình 2 Chân Gà Nướng với 1 Chân Gà Xốt Thái",
             "order grilled meat", "ORDER"),
        Turn("Thôi đổi ý rồi, bỏ Chân Gà Nướng và Chân Gà Xốt Thái đi, đổi qua Lẩu Thái cho mình",
             "replace all meat with hotpot", "ORDER"),
        Turn("Lấy 1 Lẩu Thái, thêm 2 Bia Sài Gòn",
             "order hotpot + drinks", "ORDER"),
        Turn("Ok xác nhận đơn luôn nha",
             "confirm order #1", "ORDER_CONFIRM"),
        Turn("Em ơi lại đây chút",
             "call waiter back", "CHAT"),
        Turn("Bỏ món Chân Gà Xốt Thái ra khỏi đơn cho anh",
             "try to remove confirmed item", "ORDER"),
        Turn("Thêm cho anh 1 Gỏi Bò Khoai Môn với 2 Bò Nướng Lá Lốt",
             "order new items", "ORDER"),
        Turn("Ok xác nhận luôn đi em",
             "confirm order #2", "ORDER_CONFIRM"),
        Turn("Tính tiền giúp anh",
             "request payment", "PAYMENT"),
    ],
)
