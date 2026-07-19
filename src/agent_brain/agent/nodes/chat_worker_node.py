"""chat_worker_node — builds a ChatResponseContext for the CHAT path.

Pure function: no LLM call, no tool call. Reads the user message +
the current state (cart, stage, search_context) and projects them into the typed
``ChatResponseContext`` the rewriter will read.

Symmetric with the tool-calling workers (order/search/payment): every
intent has a worker that produces a typed context. The CHAT path is
no exception.

Why a worker (and not the router)
---------------------------------
Originally the proposal had the router's inline helper build
``ChatResponseContext`` directly. That broke the "every intent has a
worker" symmetry: ORDER had ``order_worker``, SEARCH had
``search_worker``, PAYMENT had ``payment_dispatch``, but CHAT had
nothing. By promoting the context builder to its own node, the graph
becomes uniform and the router's job stays simple (decide intent →
route to the right worker).
"""

from typing import Any

from src.agent_brain.agent.state import AgentState
from src.agent_brain.schemas import ChatResponseContext
from src.agent_brain.schemas.order import Cart
from src.agent_brain.schemas.response_context import CuratedDish
from src.agent_brain.utils.state_helpers import get_worker_query


def _to_curated_memory(search_results, max_items: int = 5) -> list[CuratedDish]:
    """Convert AgentState.search_context (List[SearchResult]) to curated memory.

    Only includes menu-type documents; skips restaurant info, bestseller,
    and promo documents. Caps at ``max_items`` to avoid prompt bloat.
    Tags are stored as a comma-separated string in metadata — split to list.
    """
    dishes = []
    for r in (search_results or []):
        meta = r.document.metadata
        if meta.get("type") != "menu":
            continue
        tags_str = meta.get("tags", "")
        tag_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        price_val = meta.get("price")
        dishes.append(CuratedDish(
            name=meta.get("name", ""),
            price=int(price_val) if price_val else None,
            tags=tag_list,
            taste_profile=meta.get("taste_profile"),
            category=meta.get("category"),
        ))
    return dishes[:max_items]


def chat_worker_node(state: AgentState) -> dict[str, Any]:
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

    The ``curated_memory`` field carries a converted list of dishes from
    ``state["search_context"]`` (populated by prior SEARCH turns). This
    gives the chat LLM structured dish metadata it can use to answer
    follow-up questions without hitting the RAG pipeline again.
    """
    messages = state.get("messages") or []
    search_results = state.get("search_context")
    return {
        "response_context": ChatResponseContext(
            kind="CHAT",
            intent="CHAT",
            user_message=get_worker_query(state, "CHAT"),
            active_cart=state.get("active_cart") or Cart(),
            order_stage=state.get("order_stage", "IDLE"),
            chat_history=list(messages),
            curated_memory=_to_curated_memory(search_results),
            delegate_reason=state.get("delegate_reason"),
        ),
    }
