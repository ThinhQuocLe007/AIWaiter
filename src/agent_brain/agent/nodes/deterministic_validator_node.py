import logging
import re
from typing import Any

from langchain_core.messages import ToolMessage

from src.agent_brain.agent.state import AgentState
from src.agent_brain.utils import find_nearest_menu_name, last_user_text, resolve_menu_name

logger = logging.getLogger(__name__)

_ADDITIVE_MARKERS = ("thêm", "nữa", "lấy thêm", "gọi thêm", "cho thêm")
_DESTRUCTIVE_MARKERS = (
    "bỏ", "hủy", "huỷ", "xóa", "xoá", "đổi", "thay", "bớt", "giảm",
    "chỉ lấy", "chỉ cần", "thôi không", "không lấy", "không đặt",
)

_MODIFIER_PATTERNS = [
    re.compile(r"\((.+?)\)\s*$"),
    re.compile(r",\s*(.+?)\s*$"),
    re.compile(r"-\s*(.+?)\s*$"),
]


def _is_item_mentioned(name: str, user_text: str) -> bool:
    """Check if item was mentioned in an ORDERING context (not comparison/description).

    Words like 'nghe nói', 'đỡ', 'hơn' signal a comparison clause.
    Only the portion before the first such word counts as ordering context.

    For multi-word names, requires the first word PLUS a contiguous n-gram
    starting at word 0 to appear in the text. This prevents false positives
    when two menu items share suffix words (e.g. "Hàu Nướng Phô Mai" and
    "Sò Điệp Nướng Phô Mai" — the individual words scatter-match across
    two different items the customer actually said).
    """
    text_lower = user_text.lower()
    name_lower = name.lower()

    _COMPARISON_SEPS = ("nghe nói", "mà", "nhưng", "đỡ ", "hơn ", "so với",
                        "tuy nhiên", "còn ", "trong khi")
    sep_pos = len(text_lower)
    for sep in _COMPARISON_SEPS:
        pos = text_lower.find(sep)
        if 0 < pos < sep_pos:
            sep_pos = pos
    order_part = text_lower[:sep_pos]

    if name_lower in order_part:
        return True
    words = name_lower.split()
    if len(words) < 2:
        return False
    first_word = words[0]
    if first_word not in order_part:
        return False
    for n in range(2, len(words) + 1):
        ngram = " ".join(words[:n])
        if ngram in order_part:
            return True
    return False


def _deduplicate_against_cart(
    state: AgentState, valid_items: list[dict], is_additive: bool
) -> list[dict]:
    if not is_additive:
        return valid_items
    cart = state.get("active_cart")
    if not cart or not cart.items:
        return valid_items
    user_text = last_user_text(state)

    existing_names = {it.name.lower(): it for it in cart.items}
    delta: list[dict] = []
    stripped: list[str] = []
    for item in valid_items:
        name_lower = item.get("name", "").lower()
        if name_lower in existing_names:
            if _is_item_mentioned(item["name"], user_text):
                delta.append(item)
            else:
                stripped.append(item["name"])
        else:
            delta.append(item)

    if stripped:
        logger.warning(
            "[validator] stripped %d existing item(s) from add_cart "
            "(context copy, not mentioned by customer): %s",
            len(stripped), stripped,
        )
    return delta


def _resolve_remove_name(raw: str, cart) -> str | None:
    raw_lower = raw.lower().strip()
    for item in cart.items:
        if item.name.lower() == raw_lower:
            return item.name
    for item in cart.items:
        if raw_lower in item.name.lower() or item.name.lower() in raw_lower:
            return item.name
    resolution = resolve_menu_name(raw)
    if resolution["kind"] in ("exact", "single"):
        resolved_name = resolution["resolved"]
        for item in cart.items:
            if item.name.lower() == resolved_name.lower():
                return item.name
    return None


def _clamp_remove_quantity(raw, resolved_name: str, cart) -> int | None:
    """Normalise remove_cart's ``quantity`` against what the cart actually holds.

    None means "bỏ cả món" and stays None. Anything else is coerced to an int in
    [1, số lượng đang có]; a quantity that covers the whole line collapses back to None so the
    handler drops the line instead of leaving a 0-portion ghost. Garbage (non-numeric, ≤0) is
    treated as None rather than rejected — the customer clearly wants the dish gone, and failing
    the turn over a bad argument would be a worse answer than removing it whole.
    """
    if raw is None:
        return None
    try:
        qty = int(raw)
    except (TypeError, ValueError):
        logger.warning("[validator] remove_cart quantity %r isn't a number — removing whole item", raw)
        return None
    if qty <= 0:
        return None
    in_cart = next((i.quantity for i in cart.items if i.name == resolved_name), 0)
    return qty if qty < in_cart else None


def _restore_cart_if_additive(state: AgentState, valid_items: list[dict]) -> list[dict]:
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
        result = valid_items
    else:
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
        result = restored + valid_items

    return _deduplicate_against_cart(state, result, additive)


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


def deterministic_validator_node(state: AgentState) -> dict[str, Any]:
    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"is_valid": True, "feedback": None}

    errors: list[str] = []
    unavailable_items: list[dict[str, Any]] = []
    ambiguous_items: list[dict[str, Any]] = []

    tool_names = {tc.get("name") for tc in last_message.tool_calls}
    _CART_TOOLS = {"add_cart", "remove_cart", "clear_cart"}
    _needs_confirm_revisit = False
    if "confirm_order" in tool_names and _CART_TOOLS & tool_names:
        cart_tools_present = _CART_TOOLS & tool_names
        last_message.tool_calls = [
            tc for tc in last_message.tool_calls
            if tc.get("name") != "confirm_order"
        ]
        _needs_confirm_revisit = True
        logger.info(
            "[validator] stripped confirm_order from mixed turn "
            "(cart tools: %s) — ORDER_CONFIRM will re-invoke worker",
            cart_tools_present,
        )

    def _with_confirm_revisit(result: dict) -> dict:
        if not _needs_confirm_revisit:
            return result
        queue = (state.get("current_intents") or [])[:]
        if "ORDER_CONFIRM" not in queue:
            queue.append("ORDER_CONFIRM")
        result["current_intents"] = queue
        queries = dict(state.get("intent_queries") or {})
        queries["ORDER_CONFIRM"] = "Xác nhận đơn hàng"
        result["intent_queries"] = queries
        return result

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        args = tool_call.get("args", {})

        if tool_name in ("confirm_order", "request_payment", "verify_payment"):
            session_table_id = state.get("table_id")
            if session_table_id:
                args["table_id"] = session_table_id

        if tool_name == "add_cart":
            items = args.get("items", [])
            valid_items = _validate_menu_items(
                items, errors, unavailable_items, ambiguous_items
            )
            args["items"] = _restore_cart_if_additive(state, valid_items)

        elif tool_name == "remove_cart":
            name = args.get("name")
            if not name or not isinstance(name, str):
                errors.append("Thiếu tên món cần xóa (name).")
            else:
                cart = state.get("active_cart")
                if not cart or not cart.items:
                    errors.append("Giỏ hàng trống, không thể xóa món.")
                else:
                    resolved = _resolve_remove_name(name, cart)
                    if resolved:
                        args["name"] = resolved
                        args["quantity"] = _clamp_remove_quantity(
                            args.get("quantity"), resolved, cart
                        )
                    else:
                        cart_names = ", ".join(i.name for i in cart.items)
                        errors.append(
                            f"Món '{name}' không có trong giỏ hàng hiện tại. "
                            f"Giỏ hàng đang có: {cart_names}."
                        )

        elif tool_name == "clear_cart":
            cart = state.get("active_cart")
            if not cart or not cart.items:
                errors.append("Giỏ hàng đã trống, không cần xóa thêm.")

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
                args["items"] = [
                    {
                        "name": i.name,
                        "quantity": i.quantity,
                        "special_requests": i.special_requests,
                        "is_valid": i.is_valid,
                    }
                    for i in cart.items
                ]

        elif tool_name == "request_payment":
            if not args.get("table_id"):
                errors.append("Thiếu tham số 'table_id' cho yêu cầu thanh toán.")

        elif tool_name == "verify_payment":
            if not args.get("table_id"):
                errors.append("Thiếu tham số 'table_id' cho xác nhận thanh toán.")

    if errors:
        loop_count = state.get("loop_count", 0) + 1

        tool_messages: list[ToolMessage] = []
        tool_names: list[str] = []
        for tool_call in last_message.tool_calls:
            tool_call_id = tool_call.get("id") or "dummy_id"
            t_name = tool_call.get("name")
            tool_names.append(t_name)
            tool_errors = [e for e in errors if t_name in e or "add_cart" in e]
            if not tool_errors:
                tool_errors = errors
            per_tool_feedback = (
                "[Lỗi Xác Thực cho " + t_name + "]:\n"
                + "\n".join(f"- {err}" for err in tool_errors)
            )
            tool_messages.append(
                ToolMessage(content=per_tool_feedback, name=t_name, tool_call_id=tool_call_id)
            )

        last_tool = tool_names[0] if tool_names else None

        if loop_count >= 3:
            return _with_confirm_revisit({
                "is_valid": False,
                "feedback": "Quá nhiều lần thử không hợp lệ. Hãy xin lỗi khách và đề nghị họ nói lại yêu cầu.",
                "messages": tool_messages,
                "loop_count": loop_count,
                "last_tool": last_tool,
                "unavailable_items": unavailable_items,
                "ambiguous_items": ambiguous_items,
            })

        return _with_confirm_revisit({
            "is_valid": False,
            "feedback": "\n".join(
                f"- {e}" for e in errors
            ),
            "messages": tool_messages,
            "loop_count": loop_count,
            "last_tool": last_tool,
            "unavailable_items": unavailable_items,
            "ambiguous_items": ambiguous_items,
        })

    return _with_confirm_revisit({
        "is_valid": True,
        "feedback": None,
        "unavailable_items": unavailable_items,
        "ambiguous_items": ambiguous_items,
    })
