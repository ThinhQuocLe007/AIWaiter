import difflib
from typing import Dict, Any, List
from langchain_core.messages import ToolMessage
from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.schemas.menu_registry import MENU_NAMES

def deterministic_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    Pure Python guardrail node.
    Performs fast, zero-hallucination validations on LLM tool calls (spelling, stage checks) before execution.

    Out-of-menu handling: items the customer asked for that are NOT on the menu are
    NOT treated as a blocking error (which previously made the worker silently drop
    or substitute them). Instead they are captured into `unavailable_items`, stripped
    from the cart so the valid items still go through, and surfaced to the response
    node which explicitly tells the customer. Only structural problems (bad quantity,
    missing name, wrong confirmation stage) still block and loop for correction.
    """
    last_message = state["messages"][-1]

    # 1. No tool calls? Conversational chat is always structurally valid
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"is_valid": True, "feedback": None}

    errors = []
    unavailable_items: List[Dict[str, Any]] = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        args = tool_call.get("args", {})

        # 2. Validate Cart Drafting (Spelling and Math)
        if tool_name == "sync_cart":
            items = args.get("items", [])
            valid_items = []

            for item in items:
                name = item.get("name")
                quantity = item.get("quantity", 1)

                # Check 2a: Quantity Check (structural -> blocking)
                if quantity <= 0:
                    errors.append(f"Số lượng món '{name}' phải lớn hơn 0. Hiện tại: {quantity}.")

                # Check 2b: Missing name guard (LLM omitted/nulled the field)
                if not name or not isinstance(name, str):
                    errors.append("Món trong giỏ hàng thiếu tên (name). Hãy gọi lại sync_cart với tên món đúng từ thực đơn.")
                    continue

                # Check 2c: Strict Menu Name Validation
                if name in MENU_NAMES:
                    if quantity > 0:
                        item["is_valid"] = True
                        valid_items.append(item)
                else:
                    # Not on the menu: capture it (with the closest match as a hint),
                    # do NOT block and do NOT let the worker substitute a different dish.
                    matches = difflib.get_close_matches(name, MENU_NAMES, n=1, cutoff=0.7)
                    unavailable_items.append({"name": name, "suggestion": matches[0] if matches else None})

            # Strip unavailable items in-place so the tool executes with valid items only.
            # `sync_cart` always receives the full intended cart, so keeping only the
            # valid items leaves the existing/valid cart correct.
            args["items"] = valid_items

        # 3. State Guardrail for Order Confirmation
        elif tool_name == "confirm_order":
            if state.get("order_stage") != "AWAITING_CONFIRMATION":
                errors.append("Chưa thể xác nhận đơn hàng! Bạn phải gọi sync_cart trước và hỏi khách xác nhận.")
                
        # 4. Validate Payment Tool Arguments
        elif tool_name == "request_payment":
            table_id = args.get("table_id")
            if not table_id:
                errors.append("Thiếu tham số 'table_id' cho yêu cầu thanh toán.")
                
    # 5. Process Validation Result
    if errors:
        loop_count = state.get("loop_count", 0) + 1
        error_feedback = "[Lỗi Xác Thực]:\n" + "\n".join([f"- {err}" for err in errors])

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

        if loop_count >= 3:
            return {
                "is_valid": False,
                "feedback": "Quá nhiều lần thử không hợp lệ. Hãy xin lỗi khách và đề nghị họ nói lại yêu cầu.",
                "messages": tool_messages,
                "loop_count": loop_count,
                "unavailable_items": unavailable_items,
            }

        return {
            "is_valid": False,
            "feedback": error_feedback,
            "messages": tool_messages,
            "loop_count": loop_count,
            "unavailable_items": unavailable_items,
        }

    # Passes all structural checks: allow tool execution. Any out-of-menu items were
    # stripped from the cart and are reported downstream via `unavailable_items`.
    return {
        "is_valid": True,
        "feedback": None,
        "unavailable_items": unavailable_items,
    }
