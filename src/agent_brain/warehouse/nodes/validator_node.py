"""Final contract guard — the one node every path flows through before the reply leaves the brain
(answer, navigate, chat, and the LLM planner all converge here).

It only enforces the output contract, never business logic:
  - reply must be non-empty,
  - a `navigate` action must reference a known section (else it is stripped),
  - `chat` never carries an action.
This is the single safety net for the planner path too, which bypasses the answer worker.
"""

from __future__ import annotations

from src.agent_brain.warehouse.types import Intent
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.services import warehouse_info
from src.agent_brain.warehouse.tools import live_tools


def _known_sections() -> set[str]:
    sections = warehouse_info.section_names()
    sections |= {it.position_token for it in live_tools.get_data().all_items()}
    sections |= {a.position.token for a in warehouse_info.build_named_places().values()}
    return sections


def validator_node(state: AgentState) -> dict:
    intent = state.get("intent")
    action = state.get("action")
    reply = state.get("reply") or ""

    # chat never carries an action
    if intent == Intent.CHAT.value and action is not None:
        action = None

    # a navigate action must reference a known section; otherwise drop it
    if action is not None and action.get("type") == "navigate":
        token = (action.get("position", {}) or {}).get("token") or ""
        if token not in _known_sections():
            action = None
            reply = (reply + " (không tìm thấy vị trí trên bản đồ)").strip()

    if not reply:
        reply = "Xin lỗi, tôi chưa có thông tin này."

    return {"action": action, "reply": reply}
