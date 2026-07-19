"""Response context schemas — typed handoff from implement stage to response stage.

Each turn produces a single Pydantic ``ResponseContext`` (5 types). The
``response_node`` rewriter dispatches on ``isinstance`` and produces a
Vietnamese reply.
"""

from typing import Literal, Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.messages import BaseMessage

from .order import Cart, OrderItem, OrderStage
from .search import SearchResult
from .routing import IntentType


class OffMenuItem(BaseModel):
    """Item the customer asked for that is NOT on the menu.

    ``suggestion`` — closest menu name from ``find_nearest_menu_name``, or None.
    """
    name: str
    suggestion: Optional[str] = None


class AmbiguousItem(BaseModel):
    """Item matching several menu variants — customer must pick one."""
    name: str
    candidates: List[str]


class CuratedDish(BaseModel):
    """Dish from a previous SEARCH turn, stored as conversational memory.

    Populated by ``chat_worker_node._to_curated_memory`` from SearchResult metadata.
    """
    name: str
    price: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    taste_profile: Optional[str] = None
    category: Optional[str] = None


class OrderResponseContext(BaseModel):
    """Context for order-domain turns (add_cart, remove_cart, clear_cart, confirm_order)."""
    kind: Literal["ORDER"] = "ORDER"
    tool: Literal["add_cart", "remove_cart", "clear_cart", "confirm_order"]
    status: Literal["success", "error"] = "success"
    cart: List[OrderItem] = Field(default_factory=list)
    total_vnd: str = "0"
    off_menu: List[OffMenuItem] = Field(default_factory=list)
    ambiguous: List[AmbiguousItem] = Field(default_factory=list)
    order_id: Optional[int] = None
    stage: OrderStage = "IDLE"
    ui_action: Optional[str] = None
    error_message: Optional[str] = None


class SearchResponseContext(BaseModel):
    """Context for search turns."""
    kind: Literal["SEARCH"] = "SEARCH"
    tool: Literal["search"]
    status: Literal["success", "error"] = "success"
    query: str
    results: List[SearchResult] = Field(default_factory=list)
    shown_dishes: list[str] = Field(default_factory=list)
    ui_action: Optional[str] = None
    error_message: Optional[str] = None


class PaymentResponseContext(BaseModel):
    """Context for request_payment / verify_payment turns."""
    kind: Literal["PAYMENT"] = "PAYMENT"
    tool: Literal["request_payment", "verify_payment"]
    status: Literal["success", "error"] = "success"
    amount_vnd: Optional[str] = None
    qr_url: Optional[str] = None
    table_id: str
    ui_action: Optional[str] = None
    error_message: Optional[str] = None


class ChatResponseContext(BaseModel):
    """Context for CHAT turns (no tool ran this turn)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    kind: Literal["CHAT"] = "CHAT"
    tool: None = None
    status: None = None
    intent: IntentType
    user_message: str
    active_cart: Cart = Field(default_factory=Cart)
    order_stage: OrderStage = "IDLE"
    chat_history: List[BaseMessage] = Field(default_factory=list)
    curated_memory: List[CuratedDish] = Field(default_factory=list)
    ui_action: None = None
    error_message: None = None
    delegate_reason: Optional[str] = None


class RetryResponseContext(BaseModel):
    """Context for turns where the validator rejected the worker's tool call."""
    kind: Literal["RETRY"] = "RETRY"
    tool: str
    feedback: str
    intent: IntentType
    ui_action: None = None
    error_message: None = None


ResponseContext = Union[
    OrderResponseContext,
    SearchResponseContext,
    PaymentResponseContext,
    ChatResponseContext,
    RetryResponseContext,
]
