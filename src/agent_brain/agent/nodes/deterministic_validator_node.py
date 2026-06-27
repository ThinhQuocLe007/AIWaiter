import logging
from typing import Dict, Any, List
from langchain_core.messages import ToolMessage
from src.agent_brain.agent.state import AgentState
from src.agent_brain.utils import resolve_menu_name

logger = logging.getLogger(__name__)

def deterministic_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    Pure Python guardrail node.
    Performs fast, zero-hallucination validations on LLM tool calls (spelling, stage checks) before execution.

    Menu name handling (no longer exact-match-only):
      - exact / single prefix match -> auto-resolved to the official name and kept in the cart.
      - generic name matching SEVERAL variants ("Ốc Hương" -> 11 sauces) -> captured into
        `ambiguous_items` (not added to cart, not blocking) so the response node asks the
        customer which variant they want.
      - genuinely off-menu -> captured into `unavailable_items` and surfaced to the customer.
    Only structural problems (bad quantity, missing name, wrong confirmation stage) still
    block and loop for correction.
    """
    last_message = state["messages"][-1]

    # 1. No tool calls? Conversational chat is always structurally valid
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"is_valid": True, "feedback": None}

    errors = []
    unavailable_items: List[Dict[str, Any]] = []
    ambiguous_items: List[Dict[str, Any]] = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        args = tool_call.get("args", {})

        # table_id is a SESSION parameter, not something the LLM should guess. The
        # worker often copies the "T1" example from its prompt, which dumps every
        # order/payment onto one shared table. Override it deterministically from the
        # session state so orders, billing and verification always hit the right table.
        if tool_name in ("confirm_order", "request_payment", "verify_payment"):
            session_table_id = state.get("table_id")
            if session_table_id:
                args["table_id"] = session_table_id

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

                # Check 2c: Menu Name Resolution (exact / single / ambiguous / none)
                resolution = resolve_menu_name(name)
                kind = resolution["kind"]

                if kind in ("exact", "single"):
                    # Resolve to the official menu name so the cart, pricing and the
                    # downstream confirm_order all use the canonical spelling.
                    item["name"] = resolution["resolved"]
                    item["is_valid"] = True
                    if quantity > 0:
                        valid_items.append(item)
                    if kind == "single":
                        logger.info(
                            "[validator] auto-resolved %r -> %r (single prefix match).",
                            name, resolution["resolved"],
                        )
                elif kind == "ambiguous":
                    # Generic name matching several variants: do NOT add to cart and do
                    # NOT let the worker pick one silently. Surface for clarification.
                    ambiguous_items.append({"name": name, "candidates": resolution["candidates"]})
                    logger.warning(
                        "[validator] ambiguous item %r matches %d menu variants -> "
                        "asking customer to choose. candidates=%s",
                        name, len(resolution["candidates"]), resolution["candidates"][:5],
                    )
                else:
                    # Genuinely off-menu.
                    unavailable_items.append({"name": name, "suggestion": None})
                    logger.warning("[validator] dropped off-menu item %r (no match).", name)

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
                "ambiguous_items": ambiguous_items,
            }

        return {
            "is_valid": False,
            "feedback": error_feedback,
            "messages": tool_messages,
            "loop_count": loop_count,
            "unavailable_items": unavailable_items,
            "ambiguous_items": ambiguous_items,
        }

    # Passes all structural checks: allow tool execution. Out-of-menu items were
    # stripped and are reported via `unavailable_items`; generic names matching
    # several variants are reported via `ambiguous_items` for clarification.
    return {
        "is_valid": True,
        "feedback": None,
        "unavailable_items": unavailable_items,
        "ambiguous_items": ambiguous_items,
    }
