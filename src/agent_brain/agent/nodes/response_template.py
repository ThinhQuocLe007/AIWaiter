"""Response templates — pure string builders for the response rewriter.

All functions are pure (ctx → str), no LLM call, no side effects.
Imported by ``response_node.py`` and used by the per-type rewriters.
"""

from src.agent_brain.schemas import OrderResponseContext

_FALLBACK_REPLY = "Xin lỗi, em chưa rõ, anh/chị nói lại giúp em nhé ạ."


# ── Formatting helpers ──────────────────────────────────────────────────────
def _vnd(amount) -> str:
    return f"{int(amount):,}".replace(",", ".") + "₫"


def _normalize(msg: str) -> str:
    return (msg or "").lower().strip()


def _is_greeting(msg: str) -> bool:
    m = _normalize(msg)
    return (
        m in {"chào", "chào bạn", "chào em", "xin chào", "hello", "hi"}
        or m.startswith(("chào ", "xin chào ", "hello", "hi "))
    )


def _is_thanks(msg: str) -> bool:
    return any(t in _normalize(msg) for t in ("cảm ơn", "cám ơn", "thank", "tks", "thanks"))


def _format_cart_lines(items) -> str:
    """Render OrderItems as '- Name ×qty (price/phần)' lines."""
    lines = []
    for item in items:
        price_str = f"{_vnd(item.unit_price)}/phần" if item.unit_price else "?₫/phần"
        line = f"  - {item.name} ×{item.quantity} ({price_str})"
        if item.special_requests:
            line += f" (Ghi chú: {item.special_requests})"
        lines.append(line)
    return "\n".join(lines)


# ── Order-domain templates ──────────────────────────────────────────────────
def _format_ambiguity(ctx: OrderResponseContext) -> str:
    """Customer named a generic dish matching several variants — ask which one."""
    parts = []
    if ctx.cart:
        lines = _format_cart_lines(ctx.cart)
        parts.append(f"Dạ, giỏ hàng của anh/chị hiện có:\n{lines}\nTổng tạm tính {ctx.total_vnd}₫.")
    if ctx.off_menu:
        names = ", ".join(o.name for o in ctx.off_menu if o.name)
        parts.append(f"Món {names} hiện không có trong thực đơn ạ.")
    for a in ctx.ambiguous:
        cands = "\n".join(f"  - {c}" for c in a.candidates)
        parts.append(
            f"Dạ, món **{a.name}** bên em có nhiều loại ạ, "
            f"anh/chị muốn chọn loại nào ạ?\n{cands}"
        )
    return "\n\n".join(parts)


def _format_off_menu(ctx: OrderResponseContext) -> str:
    """Off-menu items WITHOUT a suggestion — pure template apology."""
    names = ", ".join(o.name for o in ctx.off_menu if o.name)
    return f"Dạ, món {names} hiện không có trong thực đơn ạ. Anh/chị muốn chọn món khác không ạ?"


def _format_off_menu_with_suggestions(ctx: OrderResponseContext) -> str:
    """Off-menu items WITH suggestions — deterministic template with alternatives."""
    parts: list[str] = []
    no_suggest: list[str] = []
    suggest_lines: list[str] = []

    for o in ctx.off_menu:
        if o.suggestion:
            suggest_lines.append(f"  - {o.suggestion} (thay cho {o.name})")
        elif o.name:
            no_suggest.append(o.name)

    if no_suggest:
        names = ", ".join(no_suggest)
        parts.append(f"Dạ, món {names} hiện không có trong thực đơn ạ.")

    if suggest_lines:
        parts.append("Anh/chị có thể tham khảo các món tương tự:\n" + "\n".join(suggest_lines))

    parts.append("Anh/chị có muốn đổi sang món nào trong số này không ạ?")
    return "\n\n".join(parts)


def _format_order_error(ctx: OrderResponseContext) -> str:
    msg = ctx.error_message or "Anh/chị thử lại giúp em nhé ạ."
    return f"Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. {msg}"


def _format_cart_echo(ctx: OrderResponseContext) -> str:
    """Echo the cart + ask for confirmation (add_cart / remove_cart success)."""
    if not ctx.cart:
        return "Dạ, giỏ hàng hiện đang trống ạ. Anh/chị muốn gọi món gì không ạ?"
    cart = _format_cart_lines(ctx.cart)
    suffix = "\nAnh/chị xác nhận đặt hàng chưa ạ?" if ctx.stage == "AWAITING_CONFIRMATION" else ""
    return (
        f"Dạ, giỏ hàng của anh/chị hiện có:\n{cart}\n"
        f"Tổng tạm tính {ctx.total_vnd}₫"
        f"{'.' + suffix if suffix else '.'}"
    )


def _format_confirm_reply(order_id: int) -> str:
    return f"Dạ, em đã xác nhận đơn hàng #{order_id} ạ. Món đang được chuẩn bị, anh/chị chờ một chút nhé."


def _format_remove_reply(ctx: OrderResponseContext) -> str:
    return f"Dạ, em đã bỏ món khỏi giỏ hàng ạ.\n{_format_cart_echo(ctx)}"


def _format_clear_reply() -> str:
    return "Dạ, em đã hủy toàn bộ đơn hàng ạ. Anh/chị muốn gọi món khác không ạ?"


# ── Greeting / thanks ───────────────────────────────────────────────────────
def _format_greeting() -> str:
    return "Dạ, em chào anh/chị ạ. Em có thể giúp gì cho anh/chị ạ?"


def _format_thanks() -> str:
    return "Dạ, không có gì ạ. Anh/chị cần em hỗ trợ gì thêm không ạ?"
