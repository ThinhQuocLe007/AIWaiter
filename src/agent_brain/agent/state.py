from typing import Annotated, TypedDict, List, Optional, Literal, Dict, Any
from langgraph.graph.message import add_messages

# Import our decoupled schemas
from ai_waiter_core.schemas.order import Cart, OrderStage
from ai_waiter_core.schemas.search import SearchResult

class AgentState(TypedDict):
    # Save conversation history only ( user + ai conversations )
    messages: Annotated[list, add_messages]
    
    # Use to load context
    table_id: str
    
    # Intent to work with 
    current_intents: List[Literal["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT"]]

    
    active_cart: Optional[Cart]
    order_stage: OrderStage
    
    search_context: Optional[List[SearchResult]]
    
    # Determistic Validator state
    is_valid: bool           # Python validator flag
    feedback: Optional[str]  # Actionable error message
    loop_count: int          # Circuit breaker limit

    # Items the customer requested that are NOT on the menu. Captured by the
    # validator (after stripping them from the cart) so the response node can
    # explicitly tell the customer instead of silently dropping/substituting.
    # Each entry: {"name": <as requested>, "suggestion": <closest menu name or None>}
    unavailable_items: Optional[List[Dict[str, Any]]]

    # Items the customer named generically that match SEVERAL menu variants
    # (e.g. "Ốc Hương" -> 11 sauces). Captured by the validator (not added to the
    # cart, not blocking) so the response node can ask the customer which variant.
    # Each entry: {"name": <as requested>, "candidates": [<official menu names>]}
    ambiguous_items: Optional[List[Dict[str, Any]]]

    # Router metadata for debugging/evaluation
    routing_meta: Optional[Dict[str, Any]]

    # Action command the agent emits this turn for the table's tablet (mục 12). One of
    # "open_menu" | "open_payment" | None. Set deterministically from the tool that ran
    # (see agent/actions.py); the conversation reply is spoken, this drives the screen.
    # Reset to None at the start of every turn so a command never leaks to the next.
    ui_action: Optional[str]
