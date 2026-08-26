"""Agent graph — assembles the router → workers → answer → validator flow.

Entry: router. Then:
  - control                     → control (phrase match)   → validator
  - motion                      → motion (phrase match)    → validator
  - low confidence / compound   → decompose (LLM breaks the request into atomic steps)
                                  → executor (runs each step through the workers) → validator
  - chat                        → chat (LLM)               → validator
  - answer | navigate           → retrieval (collect RAG context)
                                  ├─ navigate → navigation → answer
                                  └─ answer   → answer (response)
                                 then → validator (final contract guard) → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agent_brain.warehouse.types import Intent
from src.agent_brain.warehouse.nodes.chat_worker_node import chat_worker_node
from src.agent_brain.warehouse.nodes.control_worker_node import control_worker_node
from src.agent_brain.warehouse.nodes.decompose_node import decompose_node
from src.agent_brain.warehouse.nodes.executor_node import executor_node
from src.agent_brain.warehouse.nodes.mlp_router_node import route
from src.agent_brain.warehouse.nodes.motion_worker_node import motion_worker_node
from src.agent_brain.warehouse.nodes.navigation_worker_node import navigation_worker_node
from src.agent_brain.warehouse.nodes.response_node import response_worker_node
from src.agent_brain.warehouse.nodes.retrieval_worker_node import retrieval_worker_node
from src.agent_brain.warehouse.nodes.validator_node import validator_node
from src.agent_brain.warehouse.state import AgentState


def _router(state: AgentState) -> dict:
    intent, conf, escalate = route(state["user_text"])
    # Reset per-turn outputs; keep `current_item` so follow-ups ("còn bao nhiêu?") still resolve.
    return {
        "intent": intent.value,
        "confidence": conf,
        "routed_to_planner": escalate,
        "item": None,
        "candidates": [],
        "plan": [],
        "actions": [],
        "reply": "",
        "action": None,
        "navigated_place": None,
        "error": None,
    }


def _after_router(state: AgentState) -> str:
    # Control jumps straight out of the graph's retrieval half: "dừng lại" names no item, so
    # running RAG on it would only burn latency on the one intent that cannot afford any.
    if state.get("intent") == Intent.CONTROL.value:
        return "control"
    # Motion is likewise destination-free and immediate — no retrieval, straight to the worker.
    if state.get("intent") == Intent.MOTION.value:
        return "motion"
    # A complex/compound/low-confidence turn → LLM decomposes it, then the executor runs the steps.
    if state.get("routed_to_planner"):
        return "decompose"
    if state.get("intent") == Intent.CHAT.value:
        return "chat"
    return "retrieval"


def _after_retrieval(state: AgentState) -> str:
    if state.get("intent") == Intent.NAVIGATE.value:
        return "navigation"
    return "answer"


def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("router", _router)
    g.add_node("retrieval", retrieval_worker_node)
    g.add_node("navigation", navigation_worker_node)
    g.add_node("answer", response_worker_node)
    g.add_node("chat", chat_worker_node)
    g.add_node("control", control_worker_node)
    g.add_node("motion", motion_worker_node)
    g.add_node("decompose", decompose_node)
    g.add_node("executor", executor_node)
    g.add_node("validator", validator_node)

    g.add_edge(START, "router")
    g.add_conditional_edges("router", _after_router,
                            ["decompose", "chat", "control", "motion", "retrieval"])
    g.add_conditional_edges("retrieval", _after_retrieval, ["navigation", "answer"])
    g.add_edge("navigation", "answer")
    g.add_edge("answer", "validator")
    g.add_edge("chat", "validator")
    g.add_edge("control", "validator")
    g.add_edge("motion", "validator")
    g.add_edge("decompose", "executor")
    g.add_edge("executor", "validator")
    g.add_edge("validator", END)

    return g.compile(checkpointer=checkpointer)
