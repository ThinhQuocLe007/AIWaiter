import logging
from typing import Dict, Any

from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage

from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.config import settings
from ai_waiter_core.utils import trace_latency, MENU_NAMES
from ai_waiter_core.utils.prompt_utils import build_system_prompt, build_dynamic_suffix

# Import the native ordering tools
from ai_waiter_core.agent.tools.ordering.sync_cart import sync_cart
from ai_waiter_core.agent.tools.ordering.confirmation import confirm_order

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# LLM Initialization
# ------------------------------------------------------------

_llm = ChatOllama(
    model=settings.WORKER_MODEL,
    temperature=0.1,
    metadata={"ls_model_name": settings.WORKER_MODEL, "ls_provider": "ollama"}
).bind_tools([sync_cart, confirm_order])

# ------------------------------------------------------------
# Context Builder Helper (Dynamic Suffix Part)
# ------------------------------------------------------------

def _build_dynamic_context_block(state: AgentState, order_stage: str) -> str:
    """
    Assembles the dynamic session details (current order stage, active menu list,
    current cart items, and system validation feedback) into a structured text block.
    This dynamic block is passed as suffix context to keep the core prompt prefix cached.

    Example Output Structure (Scenario: Active drafting with misspelling feedback):
    -----------------------------------------------------------------------------
    Trạng thái đơn hàng (Current Stage): DRAFTING

    ### RESTAURANT MENU:
    You must strictly match items to these exact names:
    - Phở Bò Đặc Biệt
    - Trà Đá Ít Đường

    ### SYSTEM FEEDBACK (MANDATORY FIX):
    Lỗi: Món 'trà đá' viết chưa đúng tên khớp với thực đơn. Vui lòng hỏi khách...
    Politely apologize and clarify with the user.

    ### CURRENT ACTIVE CART:
    [CartItem(name='Phở Bò Đặc Biệt', quantity=1, price=80000.0)]
    -----------------------------------------------------------------------------
    """
    menu_str = "\n".join([f"- {name}" for name in MENU_NAMES])
    
    blocks = [
        f"Trạng thái đơn hàng (Current Stage): {order_stage}",
        "",
        "### RESTAURANT MENU:",
        "You must strictly match items to these exact names:",
        menu_str
    ]
    
    if state.get("feedback"):
        blocks.extend([
            "",
            "### SYSTEM FEEDBACK (MANDATORY FIX):",
            state["feedback"],
            "Politely apologize and clarify with the user."
        ])
        
    if state.get("active_cart"):
        blocks.extend([
            "",
            "### CURRENT ACTIVE CART:",
            str(state["active_cart"])
        ])
        
    return "\n".join(blocks)

# ------------------------------------------------------------
# The graph node
# ------------------------------------------------------------

@trace_latency("Order Worker Node", run_type="chain")
def order_worker_node(state: AgentState) -> Dict[str, Any]:
    """
    Decoupled LangGraph node that manages order taking natively using tools.
    """
    table_id = state.get("table_id", "T1")
    order_stage = state.get("order_stage", "IDLE")
    context_block = _build_dynamic_context_block(state, order_stage)
    
    # 1. Compile KV-Cache optimized static prompt elements
    static_system_message = build_system_prompt("order_worker_agent.md", ["hospitality.md"])
    
    # 2. Compile dynamic suffix elements (table metadata, active cart, and validation errors)
    dynamic_suffix_message = build_dynamic_suffix(table_id=table_id, dynamic_context=context_block)
    
    # 3. Assemble complete message array preserving prefix caching
    input_messages = (
        [static_system_message] 
        + [dynamic_suffix_message] 
        + state["messages"]
    )
    
    try:
        ai_msg = _llm.invoke(input_messages)
    except Exception as e:
        logger.error(f"Order Worker Failed: {e}")
        ai_msg = AIMessage(content="Xin lỗi, em xử lý thông tin bị lỗi. Anh/chị có thể nhắc lại được không ạ?")
        
    return {
        "messages": [ai_msg],
        "feedback": None  # Clear feedback once it has been processed
    }
