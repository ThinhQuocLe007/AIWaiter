import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.agent.memory.checkpointer import get_checkpointer, create_thread_config
from ai_waiter_core.agent.tools import search, sync_cart, confirm_order, request_payment, verify_payment
from ai_waiter_core.agent.nodes.hybrid_router_node import hybrid_router_node
from ai_waiter_core.agent.nodes.order_worker_node import order_worker_node
from ai_waiter_core.agent.nodes.search_worker_node import search_worker_node
from ai_waiter_core.agent.nodes.payment_worker_node import payment_worker_node
from ai_waiter_core.agent.nodes.deterministic_validator_node import deterministic_validator_node
from ai_waiter_core.agent.nodes.update_state_node import update_state_node
from ai_waiter_core.agent.nodes.response_node import response_node

logger = logging.getLogger(__name__)

MAX_RETRY_LOOPS = 3

INTENT_TO_WORKER = {
    "ORDER": "order_worker",
    "ORDER_CONFIRM": "order_worker",
    "SEARCH": "search_worker",
    "PAYMENT": "payment_worker",
    "CHAT": "response_node",
}

DEFAULT_WORKER = "response_node"
TOOL_WORKERS = ("order_worker", "search_worker", "payment_worker")


def _get_next_worker(state: AgentState) -> str:
    """Get next worker from intent queue."""
    intents = state.get("current_intents") or []
    if not intents:
        return DEFAULT_WORKER
    return INTENT_TO_WORKER.get(intents[0], DEFAULT_WORKER)


def _route_by_intent(state: AgentState) -> str:
    """Routes to the correct worker based on the first unprocessed intent."""
    return _get_next_worker(state)


def _route_if_tool_call(state: AgentState) -> Literal["tools", "end"]:
    """Routes to tools if the last message has tool calls, otherwise ends."""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return "end"


def _route_after_validator(state: AgentState) -> str:
    """Routes to tools if valid, otherwise back to the correct worker for correction."""
    if state.get("is_valid"):
        return "tools"
    if state.get("loop_count", 0) >= MAX_RETRY_LOOPS:
        return "response_node"
    return _get_next_worker(state)


def _route_after_updater(state: AgentState) -> str:
    """Routes to the next worker if more intents remain, otherwise generates response or ends."""
    intents = state.get("current_intents") or []
    if intents:
        return _get_next_worker(state)
    
    messages = state.get("messages", [])
    if messages and messages[-1].type == "tool":
        return "response_node"
    return "end"


class AIWaiterGraph:
    def __init__(self):
        self.checkpointer = get_checkpointer()
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile(checkpointer=self.checkpointer)

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        # Nodes
        workflow.add_node("router", hybrid_router_node)
        workflow.add_node("order_worker", order_worker_node)
        workflow.add_node("search_worker", search_worker_node)
        workflow.add_node("payment_worker", payment_worker_node)
        workflow.add_node("validator", deterministic_validator_node)
        workflow.add_node("tools", ToolNode(
            [search, sync_cart, confirm_order, request_payment, verify_payment],
            messages_key="messages"
        ))
        workflow.add_node("state_updater", update_state_node)
        workflow.add_node("response_node", response_node)

        # START → router
        workflow.add_edge(START, "router")

        # Router → worker (sequential by first intent)
        workflow.add_conditional_edges(
            "router",
            _route_by_intent,
            {
                "order_worker": "order_worker",
                "search_worker": "search_worker",
                "payment_worker": "payment_worker",
                "response_node": "response_node",
            },
        )

        # Worker → validator (if tool call) | END (if no tool call)
        for worker in TOOL_WORKERS:
            workflow.add_conditional_edges(
                worker,
                _route_if_tool_call,
                {"tools": "validator", "end": END},
            )

        # Validator → tools (valid) | worker (invalid correction) | END (circuit breaker)
        workflow.add_conditional_edges(
            "validator",
            _route_after_validator,
            {
                "tools": "tools",
                "order_worker": "order_worker",
                "search_worker": "search_worker",
                "payment_worker": "payment_worker",
                "response_node": "response_node",
            },
        )

        # Tools → state_updater
        workflow.add_edge("tools", "state_updater")

        # state_updater → next worker (more intents) | response_node (all done) | END
        workflow.add_conditional_edges(
            "state_updater",
            _route_after_updater,
            {
                "order_worker": "order_worker",
                "search_worker": "search_worker",
                "payment_worker": "payment_worker",
                "response_node": "response_node",
                "end": END,
            },
        )

        # response_node → END
        workflow.add_edge("response_node", END)

        return workflow

    def chat(self, query: str, table_id: str = "T1", session_id: str = None) -> Dict[str, Any]:
        config = create_thread_config(table_id, session_id)
        current_state = self.app.get_state(config)
        existing_stage = current_state.values.get("order_stage", "IDLE") if current_state and current_state.values else "IDLE"

        inputs = {
            "messages": [("user", query)],
            "table_id": table_id,
            "loop_count": 0,
            "is_valid": True,
            "order_stage": existing_stage,
        }
        result = self.app.invoke(inputs, config)

        return {
            "response": result["messages"][-1].content,
            "session_id": config["configurable"]["thread_id"],
            "status": "success",
            "final_stage": result["order_stage"],
        }
