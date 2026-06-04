from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.agent.memory.checkpointer import get_checkpointer, create_thread_config
from ai_waiter_core.agent.tools import search, sync_cart, confirm_order, request_payment
from ai_waiter_core.agent.nodes.hybrid_router_node import hybrid_router_node
from ai_waiter_core.agent.nodes.order_worker_node import order_worker_node
from ai_waiter_core.agent.nodes.search_worker_node import search_worker_node
from ai_waiter_core.agent.nodes.payment_worker_node import payment_worker_node
from ai_waiter_core.agent.nodes.chat_worker_node import chat_worker_node
from ai_waiter_core.agent.nodes.deterministic_validator_node import deterministic_validator_node
from ai_waiter_core.schemas.order import Cart, SyncCartResponse, ConfirmOrderResponse


def state_updater_node(state: AgentState) -> Dict[str, Any]:
    """Intercepts tool outputs and updates AgentState."""
    last_msg = state["messages"][-1]

    if last_msg.type == "tool":
        result = last_msg.content

        if isinstance(result, SyncCartResponse) and result.status == "success":
            return {
                "active_cart": Cart(items=result.items, total_price=result.total_price),
                "order_stage": "AWAITING_CONFIRMATION"
            }
        if isinstance(result, ConfirmOrderResponse) and result.status == "success":
            return {
                "order_stage": "CONFIRMED"
            }
    return {}


def _route_by_intent(state: AgentState) -> str:
    """Routes to the correct worker based on the first unprocessed intent."""
    intents = state.get("current_intents") or []
    if not intents:
        return "chat_worker"

    current = intents[0]
    if current in ("ORDER", "ORDER_CONFIRM"):
        return "order_worker"
    elif current == "SEARCH":
        return "search_worker"
    elif current == "PAYMENT":
        return "payment_worker"
    elif current == "CHAT":
        return "chat_worker"
    return "chat_worker"


def _route_if_tool_call(state: AgentState) -> Literal["tools", "end"]:
    """Routes to tools if the last message has tool calls, otherwise ends."""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return "end"


def _route_after_validator(state: AgentState) -> Literal["tools", "order_worker"]:
    """Routes to tools if valid, otherwise back to order_worker for correction."""
    if state.get("is_valid"):
        return "tools"
    return "order_worker"


def _route_after_updater(state: AgentState) -> str:
    """Routes to the next worker if more intents remain, otherwise ends."""
    intents = state.get("current_intents") or []

    if intents:
        remaining = intents[1:]
        state["current_intents"] = remaining

        if remaining:
            current = remaining[0]
            if current in ("ORDER", "ORDER_CONFIRM"):
                return "order_worker"
            elif current == "SEARCH":
                return "search_worker"
            elif current == "PAYMENT":
                return "payment_worker"
            elif current == "CHAT":
                return "chat_worker"

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
        workflow.add_node("chat_worker", chat_worker_node)
        workflow.add_node("validator", deterministic_validator_node)
        workflow.add_node("tools", ToolNode([search, sync_cart, confirm_order, request_payment]))
        workflow.add_node("state_updater", state_updater_node)

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
                "chat_worker": "chat_worker",
            },
        )

        # Worker → validator (if tool call) | END (if no tool call)
        for worker in ("order_worker", "search_worker", "payment_worker"):
            workflow.add_conditional_edges(
                worker,
                _route_if_tool_call,
                {"tools": "validator", "end": END},
            )
        workflow.add_conditional_edges(
            "chat_worker",
            _route_if_tool_call,
            {"tools": "tools", "end": END},
        )

        # Validator → tools (valid) | order_worker (invalid)
        workflow.add_conditional_edges(
            "validator",
            _route_after_validator,
            {"tools": "tools", "order_worker": "order_worker"},
        )

        # Tools → state_updater
        workflow.add_edge("tools", "state_updater")

        # state_updater → next worker (more intents) | END (all done)
        workflow.add_conditional_edges(
            "state_updater",
            _route_after_updater,
            {
                "order_worker": "order_worker",
                "search_worker": "search_worker",
                "payment_worker": "payment_worker",
                "chat_worker": "chat_worker",
                "end": END,
            },
        )

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
