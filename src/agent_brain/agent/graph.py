import logging
from typing import Any, Literal

import httpx
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from src.agent_brain.agent.actions import build_action, emit_action
from src.agent_brain.agent.memory.checkpointer import create_thread_config, get_checkpointer
from src.agent_brain.agent.nodes.chat_worker_node import chat_worker_node
from src.agent_brain.agent.nodes.deterministic_validator_node import deterministic_validator_node
from src.agent_brain.agent.nodes.hybrid_router_node import hybrid_router_node
from src.agent_brain.agent.nodes.order_worker_node import order_worker_node
from src.agent_brain.agent.nodes.payment_dispatch_node import payment_dispatch_node
from src.agent_brain.agent.nodes.response_node import response_node
from src.agent_brain.agent.nodes.search_worker_node import search_worker_node
from src.agent_brain.agent.nodes.state_outcome_node import state_outcome_node
from src.agent_brain.agent.nodes.update_state_node import update_state_node
from src.agent_brain.agent.state import AgentState
from src.agent_brain.agent.tools import (
    add_cart,
    clear_cart,
    confirm_order,
    remove_cart,
    request_payment,
    search,
    verify_payment,
)
from src.agent_brain.services.orchestrator_client import OrchestratorClient

logger = logging.getLogger(__name__)

MAX_RETRY_LOOPS = 3  # caps validation retries; after 3 invalid attempts, fall back to response_node

INTENT_TO_WORKER = {
    "ORDER": "order_worker",
    "ORDER_CONFIRM": "order_worker",
    "SEARCH": "search_worker",
    "PAYMENT": "payment_dispatch",
    "CHAT": "chat_worker",
}

DEFAULT_WORKER = "chat_worker"
TOOL_WORKERS = ("order_worker", "search_worker", "payment_dispatch")
CHAT_WORKERS = ("chat_worker",)  # leaf worker that builds the chat context, no tool calls


def _get_next_worker(state: AgentState) -> str:
    """Get next worker from intent queue."""
    intents = state.get("current_intents") or []
    if not intents:
        return DEFAULT_WORKER
    return INTENT_TO_WORKER.get(intents[0], DEFAULT_WORKER)


def _route_by_intent(state: AgentState) -> str:
    """Routes to the correct worker based on the first unprocessed intent."""
    return _get_next_worker(state)


def _route_if_tool_call(state: AgentState) -> Literal["tools", "chat_worker", "response_node"]:
    """
    Routes worker output:
        - has tool_calls -> "tools" (validator runs next)
        - no tool_calls + ORDER/ORDER_CONFIRM intent -> "chat_worker"
          (question routed to ORDER by mistake — let CHAT handle it with curated memory)
        - no tool_calls + other intent -> "response_node" (defensive verbalization)

    With ``tool_choice="any"`` in the worker LLMs the no-tool-calls branch should
    be unreachable. Kept as defense-in-depth: if Ollama or a model ever ignores
    the tool choice, the response is still verbalized instead of silently dropped.
    """
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        non_delegate = [tc for tc in last_msg.tool_calls if tc.get("name") != "delegate"]
        if non_delegate:
            if len(non_delegate) < len(last_msg.tool_calls):
                logger.info(
                    "Stripped %d delegate call(s) — %d CRUD call(s) remain",
                    len(last_msg.tool_calls) - len(non_delegate), len(non_delegate),
                )
                last_msg.tool_calls = non_delegate
            return "tools"
        logger.info(
            "Worker called only delegate — routing to chat_worker "
            "(question / review / unclear intent)"
        )
        return "chat_worker"
    intents = state.get("current_intents") or []
    if intents and intents[0] in ("ORDER", "ORDER_CONFIRM"):
        logger.info(
            "ORDER worker produced no tool call — redirecting to chat_worker "
            "(question misrouted to ORDER)"
        )
        return "chat_worker"
    logger.warning(
        "Worker produced no tool_calls despite tool_choice='any'; "
        "routing to response_node for verbalization."
    )
    return "response_node"


def _route_after_validator(state: AgentState) -> str:
    """
    Routes after the deterministic validator runs.

    Order matters — check circuit breaker FIRST:
        1. loop_count >= MAX_RETRY_LOOPS -> state_outcome (build retry context, then verbalize)
        2. is_valid -> tools (execute the tool call)
        3. otherwise -> back to the current worker for correction
    """
    if state.get("loop_count", 0) >= MAX_RETRY_LOOPS:
        return "state_outcome"
    if state.get("is_valid"):
        return "tools"
    return _get_next_worker(state)


def _route_after_updater(state: AgentState) -> str:
    """Routes to the next worker if more intents remain, otherwise to ``state_outcome``.

    After Phase 1.7, ``state_outcome`` always runs at the end of every
    turn (it finalizes per-turn resets and builds the response context
    for ``response_node`` to consume). It then routes to
    ``response_node``, which goes to ``END``.

    The previous "end" branch is gone: ``state_outcome`` always runs
    after the last worker finishes, even on the defensive path where
    the last message isn't a tool result.
    """
    intents = state.get("current_intents") or []
    if intents:
        return _get_next_worker(state)
    return "state_outcome"


class AIWaiterGraph:
    def __init__(self):
        self.checkpointer = get_checkpointer()
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile(checkpointer=self.checkpointer)
        # Used to resolve a table's current serving session so thread_id tracks it (see chat()).
        self.orchestrator = OrchestratorClient()

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        # Nodes
        workflow.add_node("router", hybrid_router_node)
        workflow.add_node("order_worker", order_worker_node)
        workflow.add_node("search_worker", search_worker_node)
        workflow.add_node("payment_dispatch", payment_dispatch_node)
        workflow.add_node("chat_worker", chat_worker_node)
        workflow.add_node("validator", deterministic_validator_node)
        workflow.add_node("tools", ToolNode(
            [search, add_cart, remove_cart, clear_cart, confirm_order, request_payment, verify_payment],
            messages_key="messages"
        ))
        workflow.add_node("state_updater", update_state_node)
        workflow.add_node("state_outcome", state_outcome_node)
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
                "payment_dispatch": "payment_dispatch",
                "chat_worker": "chat_worker",
            },
        )

        # Worker → validator (if tool call) | chat_worker (ORDER w/ no tool call) | response_node (defensive)
        for worker in TOOL_WORKERS:
            workflow.add_conditional_edges(
                worker,
                _route_if_tool_call,
                {"tools": "validator", "chat_worker": "chat_worker", "response_node": "response_node"},
            )

        # Validator → tools (valid) | worker (invalid correction) | state_outcome (circuit breaker)
        workflow.add_conditional_edges(
            "validator",
            _route_after_validator,
            {
                "tools": "tools",
                "order_worker": "order_worker",
                "search_worker": "search_worker",
                "payment_dispatch": "payment_dispatch",
                "state_outcome": "state_outcome",
            },
        )

        # Tools → state_updater
        workflow.add_edge("tools", "state_updater")

        # Chat worker → state_outcome (direct edge, no tool calls).
        # chat_worker is a leaf: it builds the ChatResponseContext and
        # state_outcome finalizes (per-turn resets) before response_node
        # verbalizes.
        workflow.add_edge("chat_worker", "state_outcome")

        # state_updater → next worker (more intents) | state_outcome (finalize)
        workflow.add_conditional_edges(
            "state_updater",
            _route_after_updater,
            {
                "order_worker": "order_worker",
                "search_worker": "search_worker",
                "payment_dispatch": "payment_dispatch",
                "state_outcome": "state_outcome",
            },
        )

        # state_outcome → response_node (always). state_outcome builds
        # the typed ResponseContext (or finalizes if chat_worker set it),
        # then response_node verbalizes.
        workflow.add_edge("state_outcome", "response_node")

        # response_node → END
        workflow.add_edge("response_node", END)

        return workflow

    def reset_thread(self, table_id: str) -> str:
        """Wipe the conversation memory for a table's CURRENT thread ("cuộc trò chuyện mới").

        Resolves the thread exactly like chat() does (active backend session → thread_id, else
        the table-scoped fallback) and deletes its checkpoints — messages, order stage and cart
        draft all start from zero on the next turn. The backend session itself is untouched:
        the visit/bill continues, only the LLM's memory is reset.
        """
        session_id = None
        try:
            sess = self.orchestrator.get_active_session(table_id)
            session_id = sess["id"] if sess else None
        except httpx.HTTPError as e:
            logger.warning("Backend unreachable on reset — using table-scoped thread: %s", e)
        config = create_thread_config(table_id, session_id)
        thread_id = config["configurable"]["thread_id"]
        self.checkpointer.delete_thread(thread_id)
        logger.info("Conversation thread %s reset (table %s)", thread_id, table_id)
        return thread_id

    def chat(self, query: str, table_id: str = "T1", session_id: str = None) -> dict[str, Any]:
        # Resolve the table's CURRENT backend session so the LangGraph thread tracks it. Callers
        # should pass session_id=None every turn: within a visit this returns the same id (memory
        # persists); after payment closes the session it returns None until the next seating opens
        # a new one → a fresh thread → no context bleed between guests.
        table_context = None
        if session_id is None:
            try:
                sess = self.orchestrator.get_active_session(table_id)
                session_id = sess["id"] if sess else None
                # Remember WHO we're serving: the kiosk seating recorded the table + party size
                # on the session. Surfaced to the LLM as one context line ("Bàn 3 · 2 khách").
                if sess:
                    table_no = sess.get("table_id", table_id)
                    party = sess.get("party_size")
                    table_context = f"Bàn {table_no}" + (f" · {party} khách" if party else "")
            except httpx.HTTPError as e:
                logger.warning("Backend unreachable — falling back to table-scoped thread: %s", e)
        config = create_thread_config(table_id, session_id)
        current_state = self.app.get_state(config)
        existing_stage = current_state.values.get("order_stage", "IDLE") if current_state and current_state.values else "IDLE"

        inputs = {
            "messages": [("user", query)],
            "table_id": table_id,
            "table_context": table_context,
            "loop_count": 0,
            "is_valid": True,
            "order_stage": existing_stage,
            "ui_action": None,  # reset each turn so a command never leaks to the next
            "order_confirmed": False,  # per-turn flag, same lifecycle as ui_action
        }
        result = self.app.invoke(inputs, config)

        # The agent doesn't just talk — it also acts on the table's tablet (open menu / bill).
        # `action` is None when nothing happened this turn. emit_action is the bridge seam.
        action = build_action(result.get("ui_action"))
        if action:
            emit_action(table_id, action)

        # Serialize the live cart draft so the tablet can mirror voice-ordered items into its own
        # cart UI. None (not []) when there is no cart, so "no cart" and "cart emptied" differ.
        active_cart = result.get("active_cart")
        cart = (
            [
                {"name": i.name, "quantity": i.quantity, "note": i.special_requests}
                for i in active_cart.items
            ]
            if active_cart is not None
            else None
        )

        return {
            "response": result["messages"][-1].content,
            "session_id": config["configurable"]["thread_id"],
            "status": "success",
            "final_stage": result["order_stage"],
            "action": action,
            "cart": cart,
            "order_confirmed": bool(result.get("order_confirmed")),
        }
