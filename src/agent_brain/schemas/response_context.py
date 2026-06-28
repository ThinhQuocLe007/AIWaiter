"""Response context schemas — the typed handoff from the implement stage to the response stage.

Each turn produces a single Pydantic ``ResponseContext`` (one of 5 types). The new
``response_node`` is a pure rewriter that reads that context and produces a Vietnamese
reply. The schemas are the control surface — the rewriter's prompt is small because
the context is structured.

Field conventions
-----------------
- ``kind`` / ``tool`` / ``status`` use ``Literal`` for typed discrimination
  (cheap ``isinstance`` dispatch in the rewriter, no Pydantic machinery at runtime).
- ``status`` mirrors the ``status`` field on the tool's response model
  (``SyncCartResponse.status``, ``SearchResponse.status``, etc.) so
  ``state_outcome_node`` can copy it across without renaming.
- Per-turn fields default to empty / ``None`` so the rewriter never has to handle
  "missing" cases — the context always carries the full picture for the turn.
- Money fields (``total_vnd``, ``amount_vnd``) are pre-formatted Vietnamese strings
  (``"170.000"``) so the templates can embed them directly without re-parsing.
- ``chat_history`` (in ``ChatResponseContext`` only) carries the full
  conversation history as ``List[BaseMessage]`` so the LLM can resolve
  follow-up references. ``ChatResponseContext`` uses
  ``arbitrary_types_allowed=True`` to accept ``BaseMessage``.
"""

from typing import Literal, Optional, List, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.messages import BaseMessage

from .order import Cart, OrderItem, OrderStage
from .search import SearchResult
from .routing import IntentType


class OffMenuItem(BaseModel):
    """Item the customer asked for that is NOT on the menu.

    ``suggestion`` is filled by the validator (Phase 2) via
    ``find_nearest_menu_name`` — the closest menu name to offer as an
    alternative. ``None`` when no near neighbor exists.
    """

    name: str                          # as the customer said it
    suggestion: Optional[str] = None   # closest menu name (Phase 2)


class AmbiguousItem(BaseModel):
    """Item matching several menu variants — the customer must pick one.

    Example: customer says "Ốc Hương" which matches 11 sauces. The validator
    doesn't add any to the cart; it surfaces the candidates so the
    rewriter can ask the customer which one they want.
    """

    name: str
    candidates: List[str]


class OrderResponseContext(BaseModel):
    """Context for sync_cart / confirm_order turns.

    Built by ``state_outcome_node`` after the tool runs. Consumed by
    ``_rewrite_order`` in response_node. Fields set per sub-case:

    - sync_cart success: ``cart``, ``total_vnd``, ``off_menu``, ``ambiguous``, ``stage``
    - sync_cart error:   ``error_message``, ``cart`` (may be empty after validator strips)
    - confirm_order success: ``cart``, ``order_id``, ``stage="CONFIRMED"``
    - confirm_order error: ``error_message``
    """

    kind: Literal["ORDER"] = "ORDER"
    tool: Literal["sync_cart", "confirm_order"]
    status: Literal["success", "error"] = "success"
    cart: List[OrderItem] = Field(default_factory=list)
    total_vnd: str = "0"               # pre-formatted Vietnamese ("170.000")
    off_menu: List[OffMenuItem] = Field(default_factory=list)
    ambiguous: List[AmbiguousItem] = Field(default_factory=list)
    order_id: Optional[int] = None     # set when tool == confirm_order and success
    stage: OrderStage = "IDLE"
    ui_action: Optional[str] = None    # "open_menu" / "open_payment" / None
    error_message: Optional[str] = None


class SearchResponseContext(BaseModel):
    """Context for search turns (search tool).

    Built by ``state_outcome_node`` after the search tool runs. Consumed by
    ``_rewrite_search``. The rewriter projects ``results`` to a compact
    text form (``name — price``) before passing to the LLM.
    """

    kind: Literal["SEARCH"] = "SEARCH"
    tool: Literal["search"]
    status: Literal["success", "error"] = "success"
    query: str
    results: List[SearchResult] = Field(default_factory=list)
    ui_action: Optional[str] = None
    error_message: Optional[str] = None


class PaymentResponseContext(BaseModel):
    """Context for request_payment / verify_payment turns.

    Built by ``state_outcome_node`` after the payment tool runs. Consumed by
    ``_rewrite_payment``. ``amount_vnd`` and ``qr_url`` are set only on
    request_payment success.
    """

    kind: Literal["PAYMENT"] = "PAYMENT"
    tool: Literal["request_payment", "verify_payment"]
    status: Literal["success", "error"] = "success"
    amount_vnd: Optional[str] = None    # pre-formatted ("450.000"); request_payment success
    qr_url: Optional[str] = None        # request_payment success
    table_id: str
    ui_action: Optional[str] = None
    error_message: Optional[str] = None


class ChatResponseContext(BaseModel):
    """Context for CHAT turns (no tool ran this turn).

    Built by ``chat_worker_node`` (the CHAT-path worker). Consumed by
    ``_rewrite_chat``. Carries the user's message + the current state
    (active_cart, order_stage) so the LLM in ``_llm_paraphrase_chat`` can
    answer cart-status questions ('what did I order?', 'how much so far?')
    naturally — no read tool, no hardcoded pattern list.

    Also carries the full conversation history (``chat_history``) so the
    LLM can handle follow-up questions that reference earlier turns
    ("cái đó" / "món lúc nãy" / "vừa nãy") — without history, the LLM
    has no way to know what the customer is referring to. The rewriter
    decides how much history to include in the LLM prompt (we store
    the full list, the rewriter trims if needed).

    Notes:
    - ``active_cart`` defaults to empty ``Cart()`` so the rewriter never
      has to handle ``None``. The rewriter checks ``ctx.active_cart.items``
      for "is the cart empty?".
    - ``order_stage`` is the same enum the legacy code used. It propagates
      so the chat LLM can phrase "đơn đã được chuẩn bị" vs "chờ xác nhận".
    - ``tool`` and ``status`` are pinned to ``None`` — a chat turn has
      no tool result. This makes the discriminated union cleaner.
    - ``chat_history`` is a shallow copy of ``state["messages"]`` at the
      moment ``chat_worker_node`` ran. ``BaseMessage`` is an arbitrary
      type so this model sets ``arbitrary_types_allowed=True``.
    """

    # BaseMessage is a non-Pydantic class, so we need
    # arbitrary_types_allowed=True for the field to validate.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    kind: Literal["CHAT"] = "CHAT"
    tool: None = None
    status: None = None
    intent: IntentType
    user_message: str
    active_cart: Cart = Field(default_factory=Cart)
    order_stage: OrderStage = "IDLE"
    chat_history: List[BaseMessage] = Field(default_factory=list)
    ui_action: None = None
    error_message: None = None


class RetryResponseContext(BaseModel):
    """Context for turns where the validator rejected the worker's tool call.

    Built by ``state_outcome_node`` when the previous turn ended with
    ``is_valid=False`` and ``feedback`` is set. Consumed by ``_rewrite_retry``.
    The rewriter translates the (Vietnamese) validator feedback into a polite
    customer-facing explanation.
    """

    kind: Literal["RETRY"] = "RETRY"
    tool: str                          # the tool the worker tried to call
    feedback: str                      # the validator's feedback (in Vietnamese)
    intent: IntentType
    ui_action: None = None
    error_message: None = None


# --- Discriminated union (the rewriter's input type) -----------------------
#
# At runtime this is just ``Union[...]`` — the rewriter uses ``isinstance``
# to dispatch. Pydantic's discriminated union support is for type-checker /
# schema-generation benefits only; we don't use ``Union`` discriminator
# serialization.
#
# The rewriter's input type is the union; the rewriter's output type is
# ``str``. That's the whole rewriter contract.

ResponseContext = Union[
    OrderResponseContext,
    SearchResponseContext,
    PaymentResponseContext,
    ChatResponseContext,
    RetryResponseContext,
]
