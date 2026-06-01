from typing import Dict, Any, Literal
import json
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.agent.memory.checkpointer import get_checkpointer, create_thread_config

# Import nodes directly from the clean, flat nodes/ folder
from ai_waiter_core.agent.nodes.hybrid_router_node import hybrid_router_node
from ai_waiter_core.agent.nodes.order_worker_node import order_worker_node
from ai_waiter_core.agent.nodes.search_worker_node import search_worker_node
from ai_waiter_core.agent.nodes.payment_worker_node import payment_worker_node
from ai_waiter_core.agent.nodes.chat_worker_node import chat_worker_node
from ai_waiter_core.agent.nodes.deterministic_validator_node import deterministic_validator_node

# Import the updated tools
from ai_waiter_core.agent.tools import search, sync_cart, confirm_order, request_payment

def state_updater_node(state: AgentState) -> Dict[str, Any]:
    """
    Hidden node that intercepts tool outputs and updates the strict State variables
    (active_cart, order_stage) to maintain message purity and state machine control.
    """
    last_msg = state["messages"][-1]
    
    if last_msg.type == "tool":
        content = last_msg.content
        if "SYNC_CART_SUCCESS:" in content:
            cart_json = content.split("SYNC_CART_SUCCESS: ")[1]
            cart_data = json.loads(cart_json)
            # The cart was successfully validated and synced. Shift to awaiting confirmation!
            return {
                "active_cart": cart_data,
                "order_stage": "AWAITING_CONFIRMATION" 
            }
        elif "CONFIRM_ORDER_SUCCESS" in content:
            # The order was confirmed by the user. Shift to confirmed!
            return {
                "order_stage": "CONFIRMED"
            }
    return {}


class AIWaiterGraph:
    def __init__(self):
        self.checkpointer = get_checkpointer()
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile(checkpointer=self.checkpointer)

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(AgentState)
        
        # --- 1. ADD NODES ---
        workflow.add_node("router", hybrid_router_node) 
        workflow.add_node("order_worker", order_worker_node)
        workflow.add_node("search_worker", search_worker_node)
        workflow.add_node("payment_worker", payment_worker_node)
        workflow.add_node("chat_worker", chat_worker_node)
        workflow.add_node("validator", deterministic_validator_node)
        
        # Standard ToolNode
        workflow.add_node("tools", ToolNode([search, sync_cart, confirm_order, request_payment]))
        workflow.add_node("state_updater", state_updater_node)
        
        # --- 2. ADD EDGES ---
        workflow.add_edge(START, "router")
        
        # Dynamic Intent-Based worker selector
        def route_to_worker(state: AgentState) -> Literal["order_worker", "search_worker", "payment_worker", "chat_worker"]:
            intents = state.get("current_intents") or []
            if not intents:
                return "chat_worker"
            
            # Select the most important worker node based on predicted intents.
            # Priority: ORDER > PAYMENT > SEARCH > CHAT
            if any(i in ("ORDER", "COMPLEX") for i in intents):
                return "order_worker"
            elif "PAYMENT" in intents:
                return "payment_worker"
            elif any(i in ("SEARCH", "MENU") for i in intents):
                return "search_worker"

            return "chat_worker"

        workflow.add_conditional_edges(
            "router", 
            route_to_worker,
            {
                "order_worker": "order_worker",
                "search_worker": "search_worker",
                "payment_worker": "payment_worker",
                "chat_worker": "chat_worker"
            }
        )
        
        # Route after Order Worker: Checks if LLM wants to execute tools
        def route_after_order(state: AgentState) -> Literal["validator", "end"]:
            last_msg = state["messages"][-1]
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                return "validator"
            return "end"

        workflow.add_conditional_edges(
            "order_worker",
            route_after_order,
            {"validator": "validator", "end": END}
        )
        
        # Route after Deterministic Validator: Skips Critic! Routes directly to Tools or back to Worker
        def route_after_validator(state: AgentState) -> Literal["tools", "order_worker"]:
            if state.get("is_valid"):
                return "tools"
            return "order_worker"  # Fast loop-back to order worker to report syntax/state error

        workflow.add_conditional_edges(
            "validator",
            route_after_validator,
            {"tools": "tools", "order_worker": "order_worker"}
        )
        
        # After tool execution, intercept the output to update the global State, then loop back to worker
        workflow.add_edge("tools", "state_updater")
        
        # Route after State Updater back to the corresponding worker
        def route_after_updater(state: AgentState) -> Literal["order_worker", "search_worker", "payment_worker"]:
            last_msg = state["messages"][-1]
            if last_msg.type == "tool":
                tool_name = last_msg.name
                if tool_name == "search":
                    return "search_worker"
                elif tool_name == "request_payment":
                    return "payment_worker"
            # Fallback/Default for sync_cart or confirm_order is order_worker
            return "order_worker"

        workflow.add_conditional_edges(
            "state_updater",
            route_after_updater,
            {
                "order_worker": "order_worker",
                "search_worker": "search_worker",
                "payment_worker": "payment_worker"
            }
        )
        
        # Non-ordering flows completely bypass the validation loops to minimize latency
        def route_after_search(state: AgentState) -> Literal["tools", "end"]:
            last_msg = state["messages"][-1]
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                return "tools"
            return "end"

        def route_after_payment(state: AgentState) -> Literal["tools", "end"]:
            last_msg = state["messages"][-1]
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                return "tools"
            return "end"

        workflow.add_conditional_edges(
            "search_worker",
            route_after_search,
            {"tools": "tools", "end": END}
        )
        workflow.add_conditional_edges(
            "payment_worker",
            route_after_payment,
            {"tools": "tools", "end": END}
        )
        workflow.add_edge("chat_worker", END)
        
        return workflow

    def chat(self, query: str, table_id: str = "T1", session_id: str = None) -> Dict[str, Any]:
        config = create_thread_config(table_id, session_id)
        
        # Fetch current state from checkpointer to preserve non-annotated fields like order_stage
        current_state = self.app.get_state(config)
        existing_stage = current_state.values.get("order_stage", "IDLE") if current_state and current_state.values else "IDLE"
        
        inputs = {
            "messages": [("user", query)],
            "table_id": table_id,
            "loop_count": 0,
            "is_valid": True,
            "order_stage": existing_stage
        }
        result = self.app.invoke(inputs, config)
        return {
            "response": result["messages"][-1].content,
            "session_id": config["configurable"]["thread_id"],
            "status": "success",
            "final_stage": result["order_stage"]
        }
