from typing import Annotated, TypedDict, List, Optional, Literal, Dict, Any
from langgraph.graph.message import add_messages

# Import our decoupled schemas
from src.agent_brain.schemas.order import Cart, OrderStage
from src.agent_brain.schemas.search import SearchResult
from src.agent_brain.schemas.response_context import ResponseContext

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

    # ── Inter-node contract: validator → state_outcome (+ workers on retry) ──
    # The three fields below are NOT user-facing state. They're how the
    # validator communicates per-turn findings to (a) state_outcome_node
    # (which builds the typed ResponseContext from them) and (b) the workers
    # on retry (which read ``feedback`` to know what to fix).
    #
    # Lifecycle:
    #   1. validator writes them (raw dicts) in its return dict
    #   2. workers read ``feedback`` on retry
    #   3. state_outcome reads ``unavailable_items`` / ``ambiguous_items``
    #      to build OrderResponseContext, then clears all three via _finalize
    #   4. response_node never reads these directly — it reads the typed
    #      context (which has these fields as Pydantic lists)
    #
    # Don't remove without rewriting the validator ↔ state_outcome contract.

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

    # The typed handoff from the implement stage to the response stage.
    # Set by chat_worker (CHAT path) or state_outcome (tool path), read and
    # cleared by response_node. Nothing else in the graph touches it.
    response_context: Optional[ResponseContext]
