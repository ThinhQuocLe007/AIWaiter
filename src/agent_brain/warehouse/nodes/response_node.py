"""Answer / response worker — phrases the Vietnamese reply for structured intents.

Runs after retrieval for both `answer` and `navigate` intents:
- `navigate`: deterministic "đang dẫn bạn đến … (khu X, ô Y)" (action set by navigation worker).
- `answer`: deterministic phrasing for locate / stock / supplier / category / handling / barcode /
  reorder / stock-audit / "khu X có gì" questions; falls back to the LLM planner for anything
  ambiguous.

The chat/planner already produce their own reply, so this node only fills the gaps.
"""

from __future__ import annotations

from src.agent_brain.warehouse.types import Intent
from src.agent_brain.warehouse.colors import vi as color_vi
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.tools import live_tools
from src.agent_brain.warehouse.services import warehouse_info

# A shortage question is warehouse-wide only when it asks *which* — "gạo còn thiếu không" is about
# one item and belongs to the per-item reorder branch further down. Requiring both halves keeps
# "bột mì ở khu nào" (a locate question that also contains "khu nào") out of the audit.
_SHORTAGE_KW = ["thiếu", "đủ hàng", "đủ đồ", "dưới mức", "sắp hết", "hết hàng", "cần nhập"]
_SCOPE_KW = ["kệ nào", "khu nào", "hàng nào", "mặt hàng nào", "chỗ nào", "cái nào",
             "những gì", "toàn kho", "cả kho", "kiểm kê", "tồn kho thấp"]


def _stock_audit_reply() -> dict:
    """Which racks are below their minimum — the 'kệ nào thiếu đồ, kệ nào đủ' question."""
    items = live_tools.get_data().all_items()
    short = [it for it in items if it.quantity < it.min_stock]
    if not short:
        sections = sorted({it.section for it in items})
        return {"reply": f"Tất cả {len(sections)} khu đều đủ hàng, không có mặt hàng nào dưới mức tối thiểu."}

    parts = []
    for sec in sorted({it.section for it in short}):
        listed = ", ".join(
            f"{it.item} (còn {it.quantity:g} {it.unit}, tối thiểu {it.min_stock:g})"
            for it in short if it.section == sec
        )
        parts.append(f"Khu {sec} thiếu {listed}")
    ok = sorted({it.section for it in items} - {it.section for it in short})
    tail = f" Các khu còn lại ({', '.join(ok)}) đủ hàng." if ok else ""
    return {"reply": ". ".join(parts) + "." + tail}


def _answer_reply(state: AgentState) -> dict:
    text = (state.get("user_text") or "").lower()
    item = state.get("item")

    # "kệ nào thiếu đồ" — warehouse-wide stock audit, before any single-item branch.
    if any(k in text for k in _SHORTAGE_KW) and any(k in text for k in _SCOPE_KW):
        return _stock_audit_reply()

    # "khu X có gì" — list items in a section.
    for sec in warehouse_info.section_names():
        if f"khu {sec.lower()}" in text or f"khu {sec}" in text:
            listed = [
                f"{it.item} (ô {it.slot}, hộp màu {color_vi(it.color)})"
                for it in live_tools.get_data().all_items() if it.section == sec
            ]
            if listed:
                return {"reply": f"Khu {sec} có: " + ", ".join(listed) + "."}

    if item:
        name = item["item"]
        section, slot, color, qty, unit = (
            item["section"],
            item["slot"],
            item["color"],
            item["quantity"],
            item["unit"],
        )
        if any(k in text for k in ["còn", "bao nhiêu", "tồn kho", "số lượng", "hết"]):
            return {"reply": f"{name} hiện còn {qty:g} {unit}."}
        if any(k in text for k in ["màu", "màu gì", "hộp nào", "thùng nào"]):
            return {"reply": f"{name} là hộp màu {color_vi(color)}, nằm ở ô {slot} khu {section}."}
        if any(k in text for k in ["nhà cung cấp", "cung cấp", "supplier"]):
            return {"reply": f"{name} do {item.get('supplier') or 'không rõ'} cung cấp."}
        if any(k in text for k in ["danh mục", "thuộc", "loại"]):
            return {"reply": f"{name} thuộc danh mục {item.get('category') or 'không rõ'}."}
        if any(k in text for k in ["lưu ý", "bảo quản", "cẩn thận", "nguy hiểm"]):
            h = item.get("handling")
            return {"reply": f"{name}: {h}" if h else f"{name} không có lưu ý đặc biệt."}
        if any(k in text for k in ["mã", "barcode", "vạch"]):
            return {"reply": f"Mã vạch của {name} là {item.get('barcode') or 'không rõ'}."}
        if any(k in text for k in ["nhập thêm", "đặt thêm", "cần", "tối thiểu", "restock", "thiếu"]):
            mn = item.get("min_stock") or 0
            if qty < mn:
                return {"reply": f"{name} chỉ còn {qty:g} {unit}, dưới mức tối thiểu {mn:g} {unit}. Cần nhập thêm."}
            return {"reply": f"{name} còn {qty:g} {unit}, trên mức tối thiểu {mn:g} {unit}. Chưa cần nhập thêm."}
        # default: locate
        return {"reply": f"{name} nằm ở khu {section}, ô {slot}, hộp màu {color_vi(color)}."}

    # No warehouse entity and no section matched — graceful out-of-scope / not-found reply
    # (replaces the old validator's "unknown" guard; we don't free-wheel the LLM here).
    return {"reply": "Xin lỗi, tôi không tìm thấy thông tin đó trong kho."}


def _navigate_reply(state: AgentState) -> dict:
    position = (state.get("action") or {}).get("position") or {}
    item = state.get("item")
    if item:
        return {
            "reply": f"Đang dẫn bạn đến {item['item']} — khu {item['section']}, "
                     f"ô {item['slot']}, hộp màu {color_vi(item['color'])}."
        }
    place = state.get("navigated_place")
    if place:
        slot, color = position.get("slot"), position.get("color")
        if slot:
            return {"reply": f"Đang đi tới {place}, ô {slot}, hộp màu {color_vi(color)}."}
        return {"reply": f"Đang đi tới {place}."}
    return {"reply": "Không tìm thấy vị trí đó trong kho."}


def response_worker_node(state: AgentState) -> dict:
    if state.get("reply"):  # chat / planner already produced a reply
        return {}

    intent = state.get("intent")
    if intent == Intent.NAVIGATE.value:
        return _navigate_reply(state)
    return _answer_reply(state)
