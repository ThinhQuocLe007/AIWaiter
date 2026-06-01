from typing import Literal
from ai_waiter_core.utils import MENU_NAMES


# Use to control the order_worker
# It can only select values in MenuItemLiteral when using tools: sync_cart 
if MENU_NAMES:
    MenuItemLiteral = Literal[tuple(MENU_NAMES) + ("UNKNOWN_ITEM",)]
else:
    MenuItemLiteral = Literal["UNKNOWN_ITEM"]
