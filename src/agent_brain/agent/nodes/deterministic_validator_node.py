import logging
import re
from typing import Dict, Any, List
from langchain_core.messages import ToolMessage
from src.agent_brain.agent.state import AgentState
from src.agent_brain.utils import resolve_menu_name, find_nearest_menu_name, last_user_text

logger = logging.getLogger(__name__)

# Deterministic protection for the cart on ADDITIVE turns ("thêm 1 trà ổi"): small local
# models routinely violate the "pass the ENTIRE cart" contract and send only the new item,
# which would wipe everything ordered so far. When the guest's wording is clearly additive
# (and not destructive) and the LLM's list contains NONE of the existing cart items, we
# re-inject the existing items instead of trusting the LLM's amnesia.
_ADDITIVE_MARKERS = ("thêm", "nữa", "lấy thêm", "gọi thêm", "cho thêm")
_DESTRUCTIVE_MARKERS = (
    "bỏ", "hủy", "huỷ", "xóa", "xoá", "đổi", "thay", "bớt", "giảm",
    "chỉ lấy", "chỉ cần", "thôi không", "không lấy", "không đặt",
)

_MODIFIER_PATTERNS = [
    re.compile(r"\((.+?)\)\s*$"),          # "Gỏi Xoài Ốc Giác (không cay)"
    re.compile(r",\s*(.+?)\s*$"),          # "Gỏi Xoài Ốc Giác, không cay"
    re.compile(r"-\s*(.+?)\s*$"),          # "Gỏi Xoài Ốc Giác - không cay"
]


def _restore_cart_if_additive(state: AgentState, valid_items: List[dict]) -> List[dict]:
    """If this is an additive turn but the LLM forgot every existing cart item, prepend them.

    Conservative on purpose: if the LLM included ANY existing item in its list, we assume it
    did the merge deliberately (it may also be removing something) and leave it alone.
    """
    prev_cart = state.get("active_cart")
    if not prev_cart or not prev_cart.items:
        return valid_items

    text = last_user_text(state).lower()
    additive = any(m in text for m in _ADDITIVE_MARKERS)
    destructive = any(m in text for m in _DESTRUCTIVE_MARKERS)
    if not additive or destructive:
        return valid_items

    new_names = {i.get("name", "").lower() for i in valid_items}
    if any(it.name.lower() in new_names for it in prev_cart.items):
        return valid_items  # LLM kept (some of) the cart — trust its list

    restored = [
        {
            "name": it.name,
            "quantity": it.quantity,
            "special_requests": it.special_requests,
            "is_valid": True,
        }
        for it in prev_cart.items
    ]
    logger.warning(
        "[validator] additive turn but the LLM dropped the existing cart — restored %d item(s): %s",
        len(restored), [r["name"] for r in restored],
    )
    return restored + valid_items


def _extract_modifier(name: str) -> tuple[str, str | None]:
    for pattern in _MODIFIER_PATTERNS:
        m = pattern.search(name)
        if m:
            modifier = m.group(1).strip()
            clean = pattern.sub("", name).strip().rstrip(",").strip()
            if clean and modifier and clean != modifier:
                return clean, modifier
    return name, None


def _validate_menu_items(
    items: list, errors: list, unavailable: list, ambiguous: list
) -> list:
    """Validate a list of item dicts against the menu. Returns valid_items only."""
    valid_items = []
    for item in items:
        name = item.get("name")
        quantity = item.get("quantity", 1)

        if quantity <= 0:
            errors.append(f"Số lượng món '{name}' phải lớn hơn 0. Hiện tại: {quantity}.")
        if not name or not isinstance(name, str):
            errors.append("Món trong giỏ hàng thiếu tên (name).")
            continue

        resolution = resolve_menu_name(name)
        kind = resolution["kind"]

        if kind in ("exact", "single"):
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
            ambiguous.append({"name": name, "candidates": resolution["candidates"]})
            logger.warning(
                "[validator] ambiguous item %r matches %d menu variants -> asking customer.",
                name, len(resolution["candidates"]),
            )
        else:
            clean_name, modifier = _extract_modifier(name)
            if modifier and clean_name != name:
                retry = resolve_menu_name(clean_name)
                if retry["kind"] in ("exact", "single"):
                    item["name"] = retry["resolved"]
                    existing = item.get("special_requests", "")
                    item["special_requests"] = (
                        f"{existing}, {modifier}" if existing else modifier
                    )
                    item["is_valid"] = True
                    if quantity > 0:
                        valid_items.append(item)
                    logger.info(
                        "[validator] stripped modifier %r from %r -> %r (special_requests=%r).",
                        modifier, name, retry["resolved"], item["special_requests"],
                    )
                    continue

            suggestion = find_nearest_menu_name(name)
            unavailable.append({"name": name, "suggestion": suggestion})
            if suggestion:
                logger.warning(
                    "[validator] off-menu item %r; suggesting %r.", name, suggestion,
                )
            else:
                logger.warning(
                    "[validator] off-menu item %r (no near neighbor).", name,
                )
    return valid_items


def deterministic_validator_node(state: AgentState) -> Dict[str, Any]:
    """Pure Python guardrail node for all tool calls."""
    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"is_valid": True, "feedback": None}

    errors = []
    unavailable_items: List[Dict[str, Any]] = []
    ambiguous_items: List[Dict[str, Any]] = []

    # When the LLM emits confirm_order + add_cart together, drop add_cart —
    # confirm_order already reads cart items from state, so add_cart is
    # redundant and would double quantities / override the CONFIRMED stage.
    tool_names = {tc.get("name") for tc in last_message.tool_calls}
    if "confirm_order" in tool_names and "add_cart" in tool_names:
        last_message.tool_calls = [
            tc for tc in last_message.tool_calls
            if tc.get("name") == "confirm_order"
        ]
        logger.info(
            "[validator] stripped add_cart from confirm_order turn "
            "(items injected from state)"
        )

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        args = tool_call.get("args", {})

        # --- table_id injection for session-scoped tools ---
        if tool_name in ("confirm_order", "request_payment", "verify_payment"):
            session_table_id = state.get("table_id")
            if session_table_id:
                args["table_id"] = session_table_id

        # --- add_cart: validate ONLY the delta items ---
        if tool_name == "add_cart":
            items = args.get("items", [])
            valid_items = _validate_menu_items(
                items, errors, unavailable_items, ambiguous_items
            )
            args["items"] = _restore_cart_if_additive(state, valid_items)

        # --- remove_cart: check item exists in cart ---
        elif tool_name == "remove_cart":
            name = args.get("name")
            if not name or not isinstance(name, str):
                errors.append("Thiếu tên món cần xóa (name).")
            else:
                cart = state.get("active_cart")
                if not cart or not any(i.name == name for i in cart.items):
                    errors.append(f"Món '{name}' không có trong giỏ hàng hiện tại.")

        # --- clear_cart: check cart isn't already empty ---
        elif tool_name == "clear_cart":
            cart = state.get("active_cart")
            if not cart or not cart.items:
                errors.append("Giỏ hàng đã trống, không cần xóa thêm.")

        # --- confirm_order: inject items from state, validate stage ---
        elif tool_name == "confirm_order":
            if state.get("order_stage") != "AWAITING_CONFIRMATION":
                errors.append(
                    "Chưa thể xác nhận đơn hàng! "
                    "Phải gọi add_cart và hỏi khách xác nhận trước."
                )
            cart = state.get("active_cart")
            if not cart or not cart.items:
                errors.append("Giỏ hàng trống, không thể xác nhận đơn.")
            else:
                # Inject items from state — LLM never passes them, zero hallucination
                args["items"] = [
                    {
                        "name": i.name,
                        "quantity": i.quantity,
                        "special_requests": i.special_requests,
                        "is_valid": i.is_valid,
                    }
                    for i in cart.items
                ]

        # --- payment tools ---
        elif tool_name == "request_payment":
            if not args.get("table_id"):
                errors.append("Thiếu tham số 'table_id' cho yêu cầu thanh toán.")

        elif tool_name == "verify_payment":
            if not args.get("table_id"):
                errors.append("Thiếu tham số 'table_id' cho xác nhận thanh toán.")

    # --- Process validation result ---
    if errors:
        loop_count = state.get("loop_count", 0) + 1
        error_feedback = "[Lỗi Xác Thực]:\n" + "\n".join(f"- {err}" for err in errors)

        tool_messages = []
        tool_names = []
        for tool_call in last_message.tool_calls:
            tool_call_id = tool_call.get("id") or "dummy_id"
            t_name = tool_call.get("name")
            tool_names.append(t_name)
            tool_messages.append(
                ToolMessage(content=error_feedback, name=t_name, tool_call_id=tool_call_id)
            )

        last_tool = tool_names[0] if tool_names else None

        if loop_count >= 3:
            return {
                "is_valid": False,
                "feedback": "Quá nhiều lần thử không hợp lệ. Hãy xin lỗi khách và đề nghị họ nói lại yêu cầu.",
                "messages": tool_messages,
                "loop_count": loop_count,
                "last_tool": last_tool,
                "unavailable_items": unavailable_items,
                "ambiguous_items": ambiguous_items,
            }

        return {
            "is_valid": False,
            "feedback": error_feedback,
            "messages": tool_messages,
            "loop_count": loop_count,
            "last_tool": last_tool,
            "unavailable_items": unavailable_items,
            "ambiguous_items": ambiguous_items,
        }

    return {
        "is_valid": True,
        "feedback": None,
        "unavailable_items": unavailable_items,
        "ambiguous_items": ambiguous_items,
    }
