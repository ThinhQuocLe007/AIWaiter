"""Answer / response worker — phrases the Vietnamese reply for structured intents.

Runs after retrieval for both `answer` and `navigate` intents:
- `navigate`: deterministic "đang dẫn bạn đến … (khu X)" (action set by navigation worker).
- `answer`: deterministic phrasing for locate / stock / supplier / category / handling / barcode /
  reorder / "khu X có gì" questions; falls back to the LLM planner for anything ambiguous.

The chat/planner already produce their own reply, so this node only fills the gaps.
"""

from __future__ import annotations

from src.agent_brain.warehouse.types import Intent
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.tools import live_tools
from src.agent_brain.warehouse.services import warehouse_info


def _answer_reply(state: AgentState) -> dict:
    text = (state.get("user_text") or "").lower()
    item = state.get("item")

    # "khu X có gì" — list items in a section.
    for sec in warehouse_info.section_names():
        if f"khu {sec.lower()}" in text or f"khu {sec}" in text:
            items = [it.item for it in live_tools.get_data().all_items() if it.section == sec]
            if items:
                return {"reply": f"Khu {sec} có: " + ", ".join(items) + "."}

    if item:
        name = item["item"]
        section, aisle, bin_, qty, unit = (
            item["section"],
            item["aisle"],
            item["bin"],
            item["quantity"],
            item["unit"],
        )
        if any(k in text for k in ["còn", "bao nhiêu", "tồn kho", "số lượng", "hết"]):
            return {"reply": f"{name} hiện còn {qty} {unit}."}
        if any(k in text for k in ["nhà cung cấp", "cung cấp", "supplier"]):
            return {"reply": f"{name} do {item.get('supplier') or 'không rõ'} cung cấp."}
        if any(k in text for k in ["danh mục", "thuộc", "loại"]):
            return {"reply": f"{name} thuộc danh mục {item.get('category') or 'không rõ'}."}
        if any(k in text for k in ["lưu ý", "bảo quản", "cẩn thận", "nguy hiểm"]):
            h = item.get("handling")
            return {"reply": f"{name}: {h}" if h else f"{name} không có lưu ý đặc biệt."}
        if any(k in text for k in ["mã", "barcode", "vạch"]):
            return {"reply": f"Mã vạch của {name} là {item.get('barcode') or 'không rõ'}."}
        if any(k in text for k in ["nhập thêm", "đặt thêm", "cần", "tối thiểu", "restock"]):
            mn = item.get("min_stock") or 0
            if qty <= mn:
                return {"reply": f"{name} chỉ còn {qty} {unit}, dưới mức tối thiểu {mn} {unit}. Cần nhập thêm."}
            return {"reply": f"{name} còn {qty} {unit}, trên mức tối thiểu {mn} {unit}. Chưa cần nhập thêm."}
        # default: locate
        return {"reply": f"{name} nằm ở khu {section}, lối {aisle}, bin {bin_}."}

    # No warehouse entity and no section matched — graceful out-of-scope / not-found reply
    # (replaces the old validator's "unknown" guard; we don't free-wheel the LLM here).
    return {"reply": "Xin lỗi, tôi không tìm thấy thông tin đó trong kho."}


def _navigate_reply(state: AgentState) -> dict:
    place = state.get("navigated_place")
    if place:
        sec = (state.get("action") or {}).get("position", {}).get("section") or ""
        return {"reply": f"Đang dẫn bạn đến {place} (khu {sec})."}
    item = state.get("item")
    if item:
        return {"reply": f"Đang dẫn bạn đến {item['item']} (khu {item['section']})."}
    return {"reply": "Không tìm thấy vị trí đó trong kho."}


def response_worker_node(state: AgentState) -> dict:
    if state.get("reply"):  # chat / planner already produced a reply
        return {}

    intent = state.get("intent")
    if intent == Intent.NAVIGATE.value:
        return _navigate_reply(state)
    return _answer_reply(state)
