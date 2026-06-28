"""chat_worker_node — builds a ChatResponseContext for the CHAT path.

Pure function: no LLM call, no tool call. Reads the user message +
the current state (cart, stage) and projects them into the typed
``ChatResponseContext`` the rewriter will read.

Symmetric with the tool-calling workers (order/search/payment): every
intent has a worker that produces a typed context. The CHAT path is
no exception.

Why a worker (and not the router)
---------------------------------
Originally the proposal had the router's inline helper build
``ChatResponseContext`` directly. That broke the "every intent has a
worker" symmetry: ORDER had ``order_worker``, SEARCH had
``search_worker``, PAYMENT had ``payment_worker``, but CHAT had
nothing. By promoting the context builder to its own node, the graph
becomes uniform and the router's job stays simple (decide intent →
route to the right worker).
"""

from typing import Dict, Any

from src.agent_brain.agent.state import AgentState
from src.agent_brain.schemas import ChatResponseContext
from src.agent_brain.schemas.order import Cart
from src.agent_brain.agent.nodes.state_outcome_node import last_user_text


def chat_worker_node(state: AgentState) -> Dict[str, Any]:
    """Build a ChatResponseContext for the CHAT path.

    The graph calls this when the router classifies the user turn as
    CHAT. After this node, ``state_outcome`` runs, sees the context
    is already set, and just runs the per-turn reset
    (clears ``unavailable_items``, ``ambiguous_items``, ``feedback``).

    Pure function: no LLM call, no tool call.

    The returned dict has ONLY ``response_context``. We deliberately
    don't clear the per-turn fields here — that's ``state_outcome``'s
    job, which runs after this node in the graph.

    The ``chat_history`` field carries a shallow copy of
    ``state["messages"]`` at the moment this node runs. The rewriter
    decides how much of the history to include in the LLM prompt (we
    don't trim here — the rewriter / projection layer is the right
    place to do that, since it knows the LLM's context budget).
    """
    messages = state.get("messages") or []
    return {
        "response_context": ChatResponseContext(
            kind="CHAT",
            intent="CHAT",
            user_message=last_user_text(state),
            active_cart=state.get("active_cart") or Cart(),
            order_stage=state.get("order_stage", "IDLE"),
            # Shallow copy so later mutations to the state's message list
            # don't retroactively change what the rewriter sees.
            chat_history=list(messages),
        ),
    }
