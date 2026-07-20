import json
from typing import Any

import numpy as np
from langchain_core.messages import HumanMessage
from sklearn.metrics.pairwise import cosine_similarity

from src.agent_brain.agent.state import AgentState
from src.agent_brain.config import settings
from src.agent_brain.services.retriever.indices.embeddings import encode_queries
from src.agent_brain.services.retriever.indices.fingerprint import verify_fingerprint
from src.agent_brain.utils import log_struct, trace_latency

UTTERANCES_PATH = settings.resources_dir / "few_shots" / "utterances.json"
CENTROIDS_PATH = settings.resources_dir / "centroids" / "centroids.npz"

MIN_SIM_THRESHOLD = 0.35


class SemanticRouterNode:
    def __init__(self):
        # Encoding goes through the shared encode_queries() helper, which reuses
        # the single SentenceTransformer singleton (same instance as the retriever)
        # and applies the active model's query-side preprocessing.
        self.route_centroids: dict[str, np.ndarray] = {}
        self._load_centroids()

    def _load_centroids(self):
        if CENTROIDS_PATH.exists():
            verify_fingerprint(CENTROIDS_PATH.parent)
            log_struct("Loading pre-computed centroids from disk", path=str(CENTROIDS_PATH))
            data = np.load(str(CENTROIDS_PATH))
            sub_centroids: dict[str, list[np.ndarray]] = {}
            for key in data.files:
                intent = key.rsplit("_", 1)[0]
                sub_centroids.setdefault(intent, []).append(data[key])
            for intent, sc_list in sub_centroids.items():
                self.route_centroids[intent] = np.stack(sc_list)
        else:
            log_struct("Centroids not found, falling back to utterance encoding",
                       path=str(CENTROIDS_PATH))
            path = UTTERANCES_PATH
            with open(path, encoding="utf-8") as f:
                routes = json.load(f)
            log_struct("Encoding semantic router utterances", route_count=len(routes))
            for route_name, utterances in routes.items():
                embeddings = encode_queries(utterances)
                self.route_centroids[route_name] = np.expand_dims(
                    np.mean(embeddings, axis=0), axis=0)

    def route(self, query: str) -> dict[str, Any]:
        query_vec = encode_queries([query])[0]
        similarities: dict[str, float] = {}
        best_route = None
        max_sim = -1.0

        for route_name, centroids in self.route_centroids.items():
            if centroids.ndim == 1:
                centroids = np.expand_dims(centroids, axis=0)
            sims = cosine_similarity([query_vec], centroids)[0]
            best_cluster_sim = float(np.max(sims))
            similarities[route_name] = best_cluster_sim
            if best_cluster_sim > max_sim:
                max_sim = best_cluster_sim
                best_route = route_name

        return {
            "intent": best_route if max_sim >= MIN_SIM_THRESHOLD else None,
            "max_sim": max_sim,
            "all_similarities": similarities,
        }


# Pre-instantiate the router class once globally to prevent reloading models on every query
_router_instance = None


def get_router() -> SemanticRouterNode:
    """Return the shared SemanticRouterNode singleton.

    Safe to call from any module — avoids ``sys.modules[...]`` access
    or coupling to the private ``_router_instance`` variable.
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticRouterNode()
    return _router_instance


@trace_latency("Semantic Router Node", run_type="chain")
def semantic_router_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph node that performs centroid-based vector intent classification
    with argmax (no softmax gating). Returns the top intent and all similarities
    for downstream keyword detector and rewriter decisions.
    """
    router = get_router()

    last_user_message = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        "",
    )

    routing_result = router.route(last_user_message)
    return {
        "metadata": routing_result
    }
