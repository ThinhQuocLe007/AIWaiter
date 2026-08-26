"""Executor node — runs a decomposed plan through the deterministic workers, in order.

The decomposer produced a list of atomic steps; here each step is handed to the same worker the
router would have picked for it (retrieval → navigation → response for navigate, etc.). State is
threaded across steps so a later step sees what an earlier one resolved — e.g. a `deliver` step
reads `current_item` set by the preceding `fetch` step. The result is one combined reply plus a
list of actions (one per executed step) for the robot to run in sequence.
"""

from __future__ import annotations

from src.agent_brain.utils import logger as log
from src.agent_brain.warehouse.nodes.chat_worker_node import chat_worker_node
from src.agent_brain.warehouse.nodes.control_worker_node import control_worker_node
from src.agent_brain.warehouse.nodes.motion_worker_node import motion_worker_node
from src.agent_brain.warehouse.nodes.navigation_worker_node import navigation_worker_node
from src.agent_brain.warehouse.nodes.response_node import response_worker_node
from src.agent_brain.warehouse.nodes.retrieval_worker_node import retrieval_worker_node
from src.agent_brain.warehouse.state import AgentState

# Which workers each intent step runs through. Navigate/answer share retrieval + response; navigate
# adds the navigation worker to emit the token. This mirrors the single-command graph edges.
_STEP_WORKERS = {
    "navigate": (retrieval_worker_node, navigation_worker_node, response_worker_node),
    "answer": (retrieval_worker_node, response_worker_node),
    "control": (control_worker_node,),
    "motion": (motion_worker_node,),
    "chat": (chat_worker_node,),
}


def _apply(worker, running: dict) -> None:
    try:
        running.update(worker(running))
    except Exception:  # noqa: BLE001 — one bad step must not abort the whole plan
        log.exception("step worker %s failed", getattr(worker, "__name__", worker))


def executor_node(state: AgentState) -> dict:
    steps = state.get("plan") or []
    running = dict(state)  # mutable working copy we thread through every step
    replies: list[str] = []
    actions: list[dict] = []

    for step in steps:
        intent = (step.get("intent") or "answer").lower()
        running["user_text"] = step.get("text") or state.get("user_text", "")
        running["intent"] = intent
        # Reset per-step outputs so this step's worker actually produces fresh reply/item/action
        # instead of seeing the previous step's leftovers (response_worker_node no-ops if `reply`
        # is already set). `current_item`/`current_section` are kept so a later step can build on a
        # prior one (e.g. a `deliver` step reads the fetch step's resolved item).
        running["reply"] = ""
        running["action"] = None
        running["item"] = None
        running["candidates"] = []
        running["navigated_place"] = None
        for worker in _STEP_WORKERS.get(intent, _STEP_WORKERS["answer"]):
            _apply(worker, running)
        if running.get("reply"):
            replies.append(running["reply"])
        if running.get("action"):
            actions.append(running["action"])

    return {
        "reply": " ".join(replies).strip(),
        "actions": actions,
        "action": actions[-1] if actions else None,
    }
