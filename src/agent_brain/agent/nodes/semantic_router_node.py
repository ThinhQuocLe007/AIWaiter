import json
import numpy as np
from pathlib import Path
from typing import Dict, Any
from sklearn.metrics.pairwise import cosine_similarity

from langchain_core.messages import HumanMessage
from src.agent_brain.agent.state import AgentState
from src.agent_brain.config import settings
from src.agent_brain.services.retriever.indices.embeddings import encode_queries
from src.agent_brain.services.retriever.indices.fingerprint import verify_fingerprint
from src.agent_brain.utils import log_struct, trace_latency

UTTERANCES_PATH = settings.resources_dir / "few_shots" / "utterances.json"
CENTROIDS_PATH = settings.resources_dir / "centroids" / "centroids.npz"

# Softmax + Gap routing defaults (calibrated via scripts/calibrate_temperature.py)
SOFTMAX_TEMPERATURE = 0.20
PROB_THRESHOLD = 0.30
GAP_THRESHOLD = 0.20
MIN_SIM_THRESHOLD = 0.55


def softmax_routing(
    all_similarities: Dict[str, float],
    T: float = SOFTMAX_TEMPERATURE,
    prob_threshold: float = PROB_THRESHOLD,
    gap_threshold: float = GAP_THRESHOLD,
    min_sim_threshold: float = MIN_SIM_THRESHOLD,
) -> Dict[str, Any]:
    """
    Convert cosine similarities to a softmax probability distribution,
    then gate on top probability P1 and gap (P1 - P2).

    Returns:
        {"intent": resolved_intent or None, "confidence": P1, "all_similarities": {...}}
    """
    max_sim = max(all_similarities.values())
    if max_sim < min_sim_threshold:
        return {
            "intent": None,
            "confidence": max_sim,
            "all_similarities": all_similarities,
        }

    scores = np.array(list(all_similarities.values()))
    labels = list(all_similarities.keys())

    exp_scores = np.exp(scores / T)
    probs = exp_scores / exp_scores.sum()

    sorted_indices = np.argsort(probs)[::-1]
    P1, P2 = float(probs[sorted_indices[0]]), float(probs[sorted_indices[1]])
    best_label = labels[sorted_indices[0]]
    gap = P1 - P2

    if P1 >= prob_threshold and gap >= gap_threshold:
        return {
            "intent": best_label,
            "confidence": P1,
            "all_similarities": all_similarities,
        }

    return {
        "intent": None,
        "confidence": P1,
        "all_similarities": all_similarities,
    }


class SemanticRouterNode:
    def __init__(self):
        # Encoding goes through the shared encode_queries() helper, which reuses
        # the single SentenceTransformer singleton (same instance as the retriever)
        # and applies the active model's query-side preprocessing.
        self.route_centroids: dict[str, np.ndarray] = {}
        self._load_centroids()

    def _load_centroids(self):
        if CENTROIDS_PATH.exists():
            # Fail loudly if the centroids were built with a different embedding
            # model than the one now active (the router would otherwise compare
            # query vectors against mismatched centroids and route incorrectly).
            verify_fingerprint(CENTROIDS_PATH.parent)
            log_struct("Loading pre-computed centroids from disk", path=str(CENTROIDS_PATH))
            data = np.load(str(CENTROIDS_PATH))
            self.route_centroids = {k: data[k] for k in data.files}
        else:
            log_struct("Centroids not found, falling back to utterance encoding",
                       path=str(CENTROIDS_PATH))
            path = UTTERANCES_PATH
            with open(path, "r", encoding="utf-8") as f:
                routes = json.load(f)
            log_struct("Encoding semantic router utterances", route_count=len(routes))
            for route_name, utterances in routes.items():
                embeddings = encode_queries(utterances)
                self.route_centroids[route_name] = np.mean(embeddings, axis=0)

    def route(self, query: str) -> Dict[str, Any]:
        query_vec = encode_queries([query])[0]
        similarities: dict[str, float] = {}
        best_route = None
        max_sim = -1.0

        for route_name, centroid in self.route_centroids.items():
            sim = float(cosine_similarity([query_vec], [centroid])[0][0])
            similarities[route_name] = sim
            if sim > max_sim:
                max_sim = sim
                best_route = route_name

        return {
            "intent": best_route,
            "confidence": max_sim,
            "raw_intent": best_route,
            "all_similarities": similarities,
        }


# Pre-instantiate the router class once globally to prevent reloading models on every query
_router_instance = None


@trace_latency("Semantic Router Node", run_type="chain")
def semantic_router_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node that performs centroid-based vector intent classification
    with softmax + gap gating for confident fast-track decisions.
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticRouterNode()
    # Use the lastest message for route
    last_user_message = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        ""
    )

    routing_result = _router_instance.route(last_user_message)
    softmax_result = softmax_routing(routing_result["all_similarities"])
    return {
        "metadata": softmax_result
    }
