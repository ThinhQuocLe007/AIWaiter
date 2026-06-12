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
    
    # Router metadata for debugging/evaluation
    routing_meta: Optional[Dict[str, Any]]
