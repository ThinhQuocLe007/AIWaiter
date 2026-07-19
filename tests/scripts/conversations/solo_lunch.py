"""Scenario D — Solo Quick Lunch (8 turns)."""

from .base import Conversation, Turn

SOLO_LUNCH = Conversation(
    name="D — Solo Quick Lunch",
    table_id="T4",
    party_size=1,
    turns=[
        Turn("1 mình, ăn trưa nhanh, dưới 100k",
             "ultra-minimal greeting + budget constraint", "SEARCH"),
        Turn("Mì Xào Rau với Mì Xào Hải Sản khác gì nhau? Món nào no hơn?",
             "comparison query", "SEARCH"),
        Turn("Lấy 1 Mì Xào Hải Sản, cho thêm ớt nha. Với 1 Bia Sài Gòn",
             "order with special_request", "ORDER"),
        Turn("Cho thêm 1 trứng ốp la vô mì được không? Có tính thêm tiền hông?",
             "OFF-MENU customization (Trứng Ốp La)", "SEARCH"),
        Turn("Mà quán nhận thẻ tín dụng không em?",
             "payment method query — not in menu", "SEARCH"),
        Turn("À có món tráng miệng gì không? Chè hay rau câu gì đó",
             "OFF-MENU — no desserts in menu", "SEARCH"),
        Turn("Thôi kệ. Xác nhận đơn luôn đi em",
             "confirm", "ORDER_CONFIRM"),
        Turn("Tính tiền",
             "request payment", "PAYMENT"),
    ],
)
