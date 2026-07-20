import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage

from src.agent_brain.agent.nodes.keyword_detector import should_invoke_rewriter
from src.agent_brain.agent.nodes.rewriter_node import rewriter_node
from src.agent_brain.agent.nodes.semantic_router_node import (
    MIN_SIM_THRESHOLD,
    get_router,
    semantic_router_node,
)
from src.agent_brain.agent.state import AgentState
from src.agent_brain.utils import trace_latency

logger = logging.getLogger(__name__)


@trace_latency("Hybrid Router Node", run_type="chain")
def hybrid_router_node(state: AgentState) -> dict[str, Any]:
    start_time = time.time()

    last_user_message = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        "",
    )

    semantic_result = semantic_router_node(state)
    metadata = semantic_result.get("metadata", {})
    sem_intent = metadata.get("intent")
    max_sim = metadata.get("max_sim", 0.0)
    all_sims = metadata.get("all_similarities", {})

    should_rewrite, rewrite_reason = should_invoke_rewriter(last_user_message, max_sim)

    current_intents: list[str] = []
    intent_queries: dict[str, str] = {}
    decided_by = "SEMANTIC_ARGMX"

    if not should_rewrite:
        current_intents = [sem_intent] if sem_intent else ["CHAT"]
        logger.info(
            "[Hybrid Router] Fast-tracked by SEMANTIC. Intent: %s (max_sim=%.3f, groups=%s)",
            current_intents[0], max_sim, rewrite_reason,
        )
    else:
        logger.info(
            "[Hybrid Router] Rewriter triggered. Reason: %s (max_sim=%.3f)",
            rewrite_reason, max_sim,
        )

        rewriter_result = rewriter_node(state)
        fragments: list[str] = rewriter_result.get("fragments", [])

        if not fragments:
            logger.warning("[Hybrid Router] Rewriter produced no fragments, routing to CHAT")
            current_intents = ["CHAT"]
            decided_by = "REWRITER_EMPTY"
        else:
            router = get_router()
            l4_triggered = False
            fragment_intents: list[str] = []
            per_fragment_sims: dict[str, dict[str, float]] = {}

            for fragment in fragments:
                frag_result = router.route(fragment)
                frag_intent = frag_result.get("intent")
                frag_max_sim = frag_result.get("max_sim", 0.0)
                per_fragment_sims[fragment] = frag_result.get("all_similarities", {})

                if frag_intent is None or frag_max_sim < MIN_SIM_THRESHOLD:
                    logger.warning(
                        "[Hybrid Router] Fragment unclassifiable "
                        "(max_sim=%.3f): '%s' → L4 fallback",
                        frag_max_sim, fragment,
                    )
                    l4_triggered = True
                    break

                fragment_intents.append(frag_intent)
                existing = intent_queries.get(frag_intent)
                if existing:
                    intent_queries[frag_intent] = f"{existing}; {fragment}"
                else:
                    intent_queries[frag_intent] = fragment

            if l4_triggered:
                current_intents = ["CHAT"]
                decided_by = "L4_ASK_CUSTOMER"
                logger.info("[Hybrid Router] L4 fallback — routing to CHAT (ask customer rephrase)")
            else:
                current_intents = list(dict.fromkeys(fragment_intents))
                decided_by = "REWRITER"
                logger.info(
                    "[Hybrid Router] Rewriter resolved: %d fragments → intents %s",
                    len(fragments), current_intents,
                )

    latency = time.time() - start_time

    routing_meta = {
        "decided_by": decided_by,
        "rewrite_reason": rewrite_reason if should_rewrite else None,
        "max_sim": round(max_sim, 4),
        "semantic_intent": sem_intent,
        "semantic_all_sims": {k: round(v, 4) for k, v in all_sims.items()},
        "latency_seconds": latency,
        "l4_triggered": decided_by == "L4_ASK_CUSTOMER",
    }

    return {
        "current_intents": current_intents,
        "routing_meta": routing_meta,
        "intent_queries": intent_queries if intent_queries else None,
    }
