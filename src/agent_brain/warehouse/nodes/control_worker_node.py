"""Control worker — turns an immediate robot command into a ControlAction or a LiftAction.

Immediate means: names no destination, needs no inventory lookup, and nothing the LLM could add
would improve it — "dừng lại", "đi tiếp", "hủy chuyến", "nâng càng lên", "hạ càng xuống".

This is the **slow path**. The Jetson matches the same phrases on the raw STT text and fires the
command over UDP before the request ever reaches this graph (see `edge_voice/command_link.py`), so
by the time a control turn arrives here the robot has usually already stopped. The node still runs
because the fast path only covers phrasings in `control_phrases`; anything it missed reaches the
router, and routing a missed stop to `chat` would have the robot answering pleasantly while it
keeps driving. Duplicated commands are harmless: stop, resume and cancel are all idempotent.
"""

from __future__ import annotations

from src.agent_brain.warehouse import control_phrases
from src.agent_brain.warehouse.state import AgentState
from src.agent_brain.warehouse.types import ControlAction, ControlVerb, LiftAction, LiftDirection

# Wording lives in control_phrases so the Jetson fast path says the same sentence.


def control_worker_node(state: AgentState) -> dict:
    verb_str = control_phrases.match(state.get("user_text") or "")
    if verb_str is None:
        # The router sent us a turn the phrase matcher does not recognise. Stopping on a guess is
        # worse than saying so: a spurious stop mid-demo looks like a crash.
        return {"reply": "Tôi chưa rõ ý lệnh điều khiển. Bạn nói “dừng lại” hoặc “đi tiếp” nhé.",
                "action": None}
    if verb_str in control_phrases.RUN_VERBS:
        action = ControlAction(verb=ControlVerb(verb_str))
    else:
        # The only other thing this matcher returns is a lift command. Reading the direction off
        # the verb's suffix keeps the two enums from having to know about each other.
        action = LiftAction(direction=LiftDirection(verb_str.removeprefix("lift_")))
    return {"reply": control_phrases.REPLY[verb_str], "action": action.model_dump()}
