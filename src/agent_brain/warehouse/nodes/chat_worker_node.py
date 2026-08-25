"""Chat worker — general/fallback conversation via the LLM (no RAG)."""

from __future__ import annotations

from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.services.llm_client import chat


_SYSTEM = (
    "Bạn là trợ lý kho thông minh, giao tiếp tiếng Việt với nhân viên kho. "
    "Trả lời ngắn gọn, thân thiện, đúng ngữ cảnh công việc kho bãi. "
    "Không bịa thông tin hàng hóa."
)


def chat_worker_node(state: AgentState) -> dict:
    try:
        reply = chat([
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": state["user_text"]},
        ])
    except Exception as e:  # network/LLM down → graceful fallback, no action
        reply = "Xin lỗi, tôi chưa kết nối được trợ lý lúc này."
        return {"reply": reply, "error": str(e)}
    return {"reply": reply}
