import logging
import time
from typing import Dict, Any

from src.agent_brain.agent.state import AgentState
from src.agent_brain.agent.nodes.semantic_router_node import semantic_router_node
from src.agent_brain.agent.nodes.slm_router_node import slm_router_node
from src.agent_brain.utils import trace_latency

logger = logging.getLogger(__name__)


@trace_latency("Hybrid Router Node", run_type="chain")
def hybrid_router_node(state: AgentState) -> Dict[str, Any]:
    """
    Two-tier hybrid routing. Fast-track via semantic router when confident,
    fall back to SLM when uncertain.
    """
    start_time = time.time()

    # 1. Execute fast semantic routing (centroid similarities + softmax+gap gate)
    semantic_result = semantic_router_node(state)

    metadata = semantic_result.get("metadata", {})
    sem_intent = metadata.get("intent")
    sem_conf = metadata.get("confidence", 0.0)
    all_sims = metadata.get("all_similarities", {})

    # 2. If semantic router resolved an intent → fast-track
    if sem_intent:
        logger.info(f"[Hybrid Router] Fast-tracked by SEMANTIC. Intent: {sem_intent}")
        decided_by = "SEMANTIC"
        current_intents = [sem_intent]
        slm_predicted = None
    else:
        logger.info(f"[Hybrid Router] Falling back to SLM. Semantic: intent={sem_intent}")
        slm_result = slm_router_node(state)

        slm_predicted = slm_result.get("current_intents", [])
        current_intents = list(dict.fromkeys(slm_predicted))
        decided_by = "SLM"
        logger.info(f"[Hybrid Router] Resolved by SLM. Intents: {current_intents}")

    latency = time.time() - start_time

    routing_meta = {
        "decided_by": decided_by,
        "semantic_confidence": sem_conf,
        "semantic_intent": sem_intent if sem_intent else (current_intents[0] if current_intents else "NONE"),
        "semantic_all_sims": {k: round(v, 4) for k, v in all_sims.items()},
        "slm_intents": slm_predicted,
        "latency_seconds": latency,
    }

    return {
        "current_intents": current_intents,
        "routing_meta": routing_meta,
    }
