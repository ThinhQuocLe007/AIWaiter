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


def _turn_index(state: AgentState) -> int:
    """Number of guest utterances so far — one per turn, so a stable turn counter.

    ``len(messages)`` is not usable for this: it also grows mid-turn as tool results and
    worker replies are appended, so the count at validation time depends on how many
    retries happened.
    """
    return sum(
        1 for m in (state.get("messages") or []) if getattr(m, "type", None) == "human"
    )


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

    # (tool_name | None, message). The tool name has to travel WITH the message:
    # errors used to be bare strings and the per-tool ToolMessage was rebuilt by
    # substring-matching the tool name inside the text, which mostly failed and fell
    # back to handing every tool every error.
    errors: list[tuple[str | None, str]] = []
    # Rejections the worker cannot fix by rewriting its call, because they describe a
    # STATE fact rather than a malformed argument: an empty cart has nothing to confirm,
    # a missing dish cannot be removed, an unconfirmed cancel needs the guest's answer.
    # Sending these back to the worker asks a 7B model to re-derive a conclusion this
    # node already reached; measured, it re-issued the same rejected tool 4 times out of
    # 4. When this list is non-empty the turn is routed straight to the chat system.
    delegate_reasons: list[str] = []
    unavailable_items: list[dict[str, Any]] = []
    ambiguous_items: list[dict[str, Any]] = []

    tool_names = {tc.get("name") for tc in last_message.tool_calls}
    _CART_TOOLS = {"add_cart", "remove_cart", "clear_cart"}
    _needs_confirm_revisit = False
    # Set when a clear_cart was refused for lack of confirmation. Stamps the turn index on
    # the way out so the NEXT turn — and only the next — may go through with the clear.
    _clear_needs_confirm = False
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

    def _with_clear_mark(result: dict) -> dict:
        """Stamp the clear-confirmation window. Deliberately never writes None: the
        permission expires on its own (see AgentState.clear_confirm_at), and a reset path
        here would let an unrelated valid tool call in the SAME turn erase the stamp the
        refusal had just written."""
        if _clear_needs_confirm:
            result["clear_confirm_at"] = _turn_index(state)
        return result

    def _with_confirm_revisit(result: dict) -> dict:
        if not _needs_confirm_revisit:
            return _with_clear_mark(result)
        queue = (state.get("current_intents") or [])[:]
        if "ORDER_CONFIRM" not in queue:
            queue.append("ORDER_CONFIRM")
        result["current_intents"] = queue
        queries = dict(state.get("intent_queries") or {})
        queries["ORDER_CONFIRM"] = "Xác nhận đơn hàng"
        result["intent_queries"] = queries
        return _with_clear_mark(result)

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        args = tool_call.get("args", {})

        if tool_name in ("confirm_order", "request_payment", "verify_payment"):
            session_table_id = state.get("table_id")
            if session_table_id:
                args["table_id"] = session_table_id

        if tool_name == "add_cart":
            items = args.get("items", [])
            item_errors: list[str] = []
            valid_items = _validate_menu_items(
                items, item_errors, unavailable_items, ambiguous_items
            )
            errors.extend((tool_name, e) for e in item_errors)
            args["items"] = _restore_cart_if_additive(state, valid_items)

        elif tool_name == "remove_cart":
            name = args.get("name")
            if not name or not isinstance(name, str):
                errors.append((tool_name, "Thiếu tên món cần xóa (name)."))
            else:
                cart = state.get("active_cart")
                if not cart or not cart.items:
                    if state.get("order_stage") == "CONFIRMED":
                        errors.append((tool_name,
                            "Đơn hàng đã được xác nhận và gửi xuống bếp rồi, "
                            "không thể xóa món được nữa. Anh/chị có muốn gọi thêm món mới không ạ?"
                        ))
                        delegate_reasons.append(
                            "đơn đã gửi bếp rồi nên không xóa món được, hỏi khách có muốn gọi thêm không")
                    else:
                        errors.append((tool_name, "Giỏ hàng trống, không thể xóa món."))
                        delegate_reasons.append("giỏ hàng đang trống, không có món nào để xóa")
                else:
                    resolved = _resolve_remove_name(name, cart)
                    if resolved:
                        args["name"] = resolved
                        args["quantity"] = _clamp_remove_quantity(
                            args.get("quantity"), resolved, cart
                        )
                    else:
                        cart_names = ", ".join(i.name for i in cart.items)
                        errors.append((tool_name,
                            f"Món '{name}' không có trong giỏ hàng hiện tại. "
                            f"Giỏ hàng đang có: {cart_names}."
                        ))
                        delegate_reasons.append(
                            f"khách muốn bỏ '{name}' nhưng món đó không có trong giỏ; "
                            f"giỏ đang có: {cart_names}")

        elif tool_name == "clear_cart":
            # The guard used to fire ONLY when the cart was already empty, which protected
            # the harmless case and waved through the damaging one: a guest saying "thôi"
            # over a full cart had it wiped, and because clear_cart is in
            # CART_MUTATING_TOOLS the wipe was mirrored onto the tablet draft too.
            cart = state.get("active_cart")
            if not cart or not cart.items:
                errors.append((tool_name, "Giỏ hàng đã trống, không cần xóa thêm."))
                delegate_reasons.append("giỏ hàng đang trống nên không có gì để hủy")
            elif state.get("clear_confirm_at") != _turn_index(state) - 1:
                _clear_needs_confirm = True
                delegate_reasons.append(
                    "hỏi khách có chắc muốn hủy TOÀN BỘ đơn không, liệt kê các món đang có")
                errors.append((tool_name,
                    f"Giỏ hàng đang có {len(cart.items)} món — KHÔNG được xóa khi chưa hỏi khách. "
                    "Hãy gọi delegate với lý do: hỏi khách có chắc muốn hủy toàn bộ đơn không. "
                    "Nếu lượt sau khách đồng ý thì mới gọi clear_cart."
                ))

        elif tool_name == "confirm_order":
            cart = state.get("active_cart")
            if not cart or not cart.items:
                # Empty cart first, and never point at add_cart here: the guest said
                # something like "chốt đi em" without naming a dish, so there is nothing
                # to add. The old text sent the worker to add_cart, which it cannot
                # satisfy, and the retry loop converged on delegate only 1 time in 7.
                errors.append((tool_name,
                    "Giỏ hàng đang trống nên KHÔNG có gì để xác nhận."
                ))
                delegate_reasons.append(
                    "giỏ hàng đang trống, chưa có món nào để xác nhận đơn")
            elif state.get("order_stage") != "AWAITING_CONFIRMATION":
                errors.append((tool_name,
                    "Chưa thể xác nhận đơn hàng khi chưa hỏi khách."
                ))
                delegate_reasons.append(
                    "đọc lại giỏ hàng cho khách và hỏi khách xác nhận trước khi chốt đơn")
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
                errors.append((tool_name, "Thiếu tham số 'table_id' cho yêu cầu thanh toán."))

        elif tool_name == "verify_payment":
            if not args.get("table_id"):
                errors.append((tool_name, "Thiếu tham số 'table_id' cho xác nhận thanh toán."))

    if errors:
        loop_count = state.get("loop_count", 0) + 1

        tool_messages: list[ToolMessage] = []
        tool_names: list[str] = []
        for tool_call in last_message.tool_calls:
            tool_call_id = tool_call.get("id") or "dummy_id"
            t_name = tool_call.get("name")
            tool_names.append(t_name)
            # Owner-matched, not substring-matched. `None` means the error is not tied to
            # one tool and applies to all of them. A tool with nothing against it gets a
            # neutral note rather than the whole turn's errors — every tool_call still
            # needs exactly one ToolMessage, but it must not be told to fix someone
            # else's problem.
            tool_errors = [msg for owner, msg in errors if owner in (None, t_name)]
            if tool_errors:
                per_tool_feedback = (
                    "[Lỗi Xác Thực cho " + t_name + "]:\n"
                    + "\n".join(f"- {err}" for err in tool_errors)
                )
            else:
                per_tool_feedback = (
                    f"[{t_name} không có lỗi. Lượt này bị chặn vì tool khác — "
                    f"đừng sửa {t_name}.]"
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
            # Set only for state-based rejections. _route_after_validator reads it and sends
            # the turn to the chat system instead of round-tripping the worker.
            "delegate_reason": "; ".join(delegate_reasons) if delegate_reasons else None,
            "feedback": "\n".join(f"- {msg}" for _, msg in errors),
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
