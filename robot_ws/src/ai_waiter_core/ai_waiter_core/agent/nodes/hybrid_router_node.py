import logging
import time
from typing import Dict, Any

from ai_waiter_core.agent.state import AgentState
from ai_waiter_core.agent.nodes.semantic_router_node import semantic_router_node
from ai_waiter_core.agent.nodes.slm_router_node import slm_router_node
from ai_waiter_core.utils import trace_latency

logger = logging.getLogger(__name__)

# The confidence similarity threshold for fast-tracking simple queries
HYBRID_CONFIDENCE_THRESHOLD = 0.85

@trace_latency("Hybrid Router Node", run_type="chain")
def hybrid_router_node(state: AgentState) -> Dict[str, Any]:
    """
    Orchestrates routing using semantic similarity. Fast-tracks simple, high-confidence
    queries directly. Delegates low-confidence or multi-intent queries to local SLM.
    """
    query = state["messages"][-1].content
    start_time = time.time()
    
    # 1. Execute fast semantic routing
    semantic_result = semantic_router_node(state)
    
    # Extract the legacy metadata dictionary safely
    metadata = semantic_result.get("metadata", {})
    sem_intent = metadata.get("intent")
    sem_conf = metadata.get("confidence", 0.0)
    
    # 2. Hybrid Decision Flow
    # If cosine similarity is highly confident, we fast-track it as a single intent list
    if sem_conf >= HYBRID_CONFIDENCE_THRESHOLD and sem_intent:
        logger.info(f"[Hybrid Router] Fast-tracked by SEMANTIC. Intent: {sem_intent} (Confidence: {sem_conf:.4f})")
        decided_by = "SEMANTIC"
        current_intents = [sem_intent]
        slm_predicted = None
    else:
        # Fallback to local Ollama SLM for detailed multi-intent parsing
        logger.info(f"[Hybrid Router] Falling back to SLM. Semantic confidence: {sem_conf:.4f}")
        slm_result = slm_router_node(state)
        
        # Extract the list of intents predicted by the SLM
        slm_predicted = slm_result.get("current_intents", [])
        
        # Deduplicate consecutive/redundant intents while preserving order (e.g. ["ORDER", "ORDER"] -> ["ORDER"])
        current_intents = list(dict.fromkeys(slm_predicted))
        decided_by = "SLM"
        logger.info(f"[Hybrid Router] Resolved by SLM. Intents: {current_intents}")

    latency = time.time() - start_time
    
    # Save routing metadata for performance evaluation
    routing_meta = {
        "decided_by": decided_by,
        "semantic_confidence": sem_conf,
        "semantic_intent": sem_intent if sem_intent else "NONE",
        "slm_intents": slm_predicted,
        "latency_seconds": latency
    }
    
    return {
        "current_intents": current_intents,
        "routing_meta": routing_meta
    }
