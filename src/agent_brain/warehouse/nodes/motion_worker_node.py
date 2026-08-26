"""Motion worker — turns a directional primitive into a MotionAction.

Immediate, names no destination, needs no inventory lookup, and nothing the LLM could add would
improve it — "đi thẳng", "lùi", "quẹo trái", "quẹo phải". Like the control worker this is the
*slow path*: the Jetson matches the same phrases on raw STT and fires the pulse over UDP before the
request reaches this graph (see `edge_voice/main.py`), so the robot usually already moved. This node
is the safety net for phrasings the fast path missed, and it supplies the spoken reply.
"""

from __future__ import annotations

from src.agent_brain.warehouse import motion_phrases
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.types import MotionAction, MotionDirection


def motion_worker_node(state: AgentState) -> dict:
    direction = motion_phrases.match(state.get("user_text") or "")
    if direction is None:
        # The router sent us a turn the matcher does not recognise. Guessing a direction is worse
        # than saying so — a spurious pulse mid-demo looks like the robot glitching.
        return {
            "reply": "Tôi chưa rõ hướng di chuyển. Nói “đi thẳng”, “lùi”, “quẹo trái” "
                     "hoặc “quẹo phải” nhé.",
            "action": None,
        }
    return {
        "reply": motion_phrases.REPLY[direction],
        "action": MotionAction(direction=MotionDirection(direction)).model_dump(),
    }
