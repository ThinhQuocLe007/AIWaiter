import difflib
from typing import Dict, Any
from langchain_core.messages import ToolMessage
from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.schemas.menu_registry import MENU_NAMES

def deterministic_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    Pure Python guardrail node.
    Performs fast, zero-hallucination validations on LLM tool calls (spelling, stage checks) before execution.
    """
    last_message = state["messages"][-1]
    
    # 1. No tool calls? Conversational chat is always structurally valid
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"is_valid": True, "feedback": None}
        
    errors = []
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        args = tool_call.get("args", {})
        
        # 2. Validate Cart Drafting (Spelling and Math)
        if tool_name == "sync_cart":
            items = args.get("items", [])
            
            for item in items:
                name = item.get("name")
                quantity = item.get("quantity", 1)
                
                # Check 2a: Quantity Check
                if quantity <= 0:
                    errors.append(f"Quantity must be greater than 0 for item '{name}'. Got: {quantity}.")
                
                # Check 2b: Strict Menu Name Validation (Fuzzy Match)
                if name not in MENU_NAMES:
                    suggestions = difflib.get_close_matches(name, MENU_NAMES, n=2, cutoff=0.7)
                    if suggestions:
                        # Auto-correct hint
                        errors.append(f"Item '{name}' not found. Did you mean '{suggestions[0]}'? You MUST use exact spelling.")
                    else:
                        errors.append(f"Item name '{name}' does not exist on the menu. Ask the customer to clarify.")
                
                # If this item passes all menu checks, set is_valid = True in the tool arguments in-place
                if quantity > 0 and name in MENU_NAMES:
                    item["is_valid"] = True
                        
        # 3. State Guardrail for Order Confirmation
        elif tool_name == "confirm_order":
            if state.get("order_stage") != "AWAITING_CONFIRMATION":
                errors.append("You CANNOT confirm the order yet! You must first summarize the cart and explicitly ask the user for confirmation.")
                
        # 4. Validate Payment Tool Arguments
        elif tool_name == "request_payment":
            table_id = args.get("table_id")
            if not table_id:
                errors.append("Payment request missing required 'table_id' argument.")
                
    # 5. Process Validation Result
    if errors:
        error_feedback = "[Deterministic Validator Error]:\n" + "\n".join([f"- {err}" for err in errors])
        
        # Build ToolMessage for each tool call that failed
        tool_messages = []
        for tool_call in last_message.tool_calls:
            tool_call_id = tool_call.get("id") or "dummy_id"
            tool_name = tool_call.get("name")
            tool_messages.append(
                ToolMessage(
                    content=error_feedback,
                    name=tool_name,
                    tool_call_id=tool_call_id
                )
            )
            
        return {
            "is_valid": False,
            "feedback": error_feedback,
            "messages": tool_messages,
            "loop_count": state.get("loop_count", 0) + 1
        }
        
    # Passes all deterministic checks, allow Tool execution
    return {
        "is_valid": True,
        "feedback": None
    }
