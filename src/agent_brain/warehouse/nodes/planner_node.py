"""Planner node — LLM escalation for low-confidence / ambiguous / compound requests.

It reuses the same live tools as the workers: resolves candidate items, pulls live facts, then asks
the LLM to compose a grounded Vietnamese answer (no hallucinated stock). If the request implies
movement, it attaches a navigate action for the best candidate.
"""

from __future__ import annotations

from src.agent_brain.warehouse.actions import navigate_action
from src.agent_brain.warehouse.colors import vi as color_vi
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.tools import live_tools
from src.agent_brain.warehouse.services.llm_client import chat
from src.agent_brain.warehouse.services.warehouse_data import Item

_MOVE_KW = ["đi", "tới", "đến", "dẫn", "chỉ đường", "đưa tôi", "dắt", "navigate"]


_SYSTEM = (
    "Bạn là trợ lý kho thông minh. Dưới đây là dữ liệu THỰC TẾ từ kho (đã truy xuất). "
    "Chỉ dùng thông tin này để trả lời, bằng tiếng Việt, ngắn gọn. "
    "Nếu không có dữ liệu liên quan, nói rõ là không tìm thấy."
)


def _build_context(items: list[Item], sop: list[str]) -> str:
    parts = []
    for it in items:
        parts.append(
            f"- {it.item} (SKU {it.sku}): {it.desc}. "
            f"Vị trí: khu {it.section}, ô {it.slot}, hộp màu {color_vi(it.color)}. "
            f"Tồn kho: {it.quantity} {it.unit}."
        )
    for s in sop:
        parts.append(f"- Tài liệu: {s[:500]}")
    return "\n".join(parts) if parts else "(không có dữ liệu kho liên quan)"


def planner_node(state: AgentState) -> dict:
    text = state["user_text"]
    items = live_tools.resolve_item(text, k=3)
    sop = live_tools.get_sop(text, k=2)
    context = _build_context(items, sop)

    try:
        reply = chat([
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Dữ liệu kho:\n{context}\n\nYêu cầu nhân viên: {text}"},
        ])
    except Exception as e:
        reply = "Xin lỗi, tôi không xử lý được yêu cầu này lúc này."
        return {"reply": reply, "error": str(e), "routed_to_planner": True}

    action: dict | None = None
    if items and any(kw in text.lower() for kw in _MOVE_KW):
        action = navigate_action(items[0]).model_dump()
    return {"reply": reply, "action": action, "routed_to_planner": True,
            "item": None if not items else _item_dict(items[0])}


def _item_dict(it: Item) -> dict:
    from src.agent_brain.warehouse.actions import item_to_dict
    return item_to_dict(it)
