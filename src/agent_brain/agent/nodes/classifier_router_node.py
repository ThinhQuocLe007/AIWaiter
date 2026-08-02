"""classifier_router_node — trained MLP intent classifier replacing the centroid router.

Uses the text-only 4-class MLP trained in ``src/training_semantic_router/`` on corpus_v2
(94.0% on 149 eval utterances, none of which appear in its training data).
Replaces ``semantic_router_node`` + ``keyword_detector``; the rewriter stays for
multi-intent decomposition on low-confidence or multi-clause utterances.

Architecture:
    utterance → [shared embedding] → [trained MLP] → intent + confidence
                                                        │
                             confidence >= 0.7  +  no boundary markers?
                                   │                            │
                              fast path                    rewriter path
                            single intent              decompose → per-fragment classify
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from src.agent_brain.agent.nodes.rewriter_node import rewriter_node
from src.agent_brain.agent.state import AgentState
from src.agent_brain.services.retriever.indices.embeddings import encode_queries
from src.agent_brain.utils import trace_latency
from src.agent_brain.utils.boundary_utils import has_boundary_markers
from src.agent_brain.utils.state_helpers import last_user_text

logger = logging.getLogger(__name__)

_classify_fn = None
_CLASSIFY_IMPORT_FAILED = False

CLASSIFIER_THRESHOLD = 0.7

# SEARCH gets a higher bar: dish-name tokens bias the MLP toward SEARCH even when the
# utterance carries ORDER markers ("cho mình 1 Mực Cháy Tỏi" → SEARCH 0.740). Raising
# the SEARCH threshold sends borderline SEARCH classifications through the rewriter
# where fragments are decomposed and reclassified independently — a single-intent ORDER
# utterance with dish names produces one fragment that reclassifies correctly.
SEARCH_THRESHOLD = 0.85


def _classify_one(
    utterance: str,
    embedding_cache: dict[str, np.ndarray],
) -> dict[str, Any]:
    global _classify_fn, _CLASSIFY_IMPORT_FAILED

    if _classify_fn is None and not _CLASSIFY_IMPORT_FAILED:
        try:
            from src.training_semantic_router.classifier.predict import classify as _fn

            _classify_fn = _fn
        except Exception:
            _CLASSIFY_IMPORT_FAILED = True
            logger.exception(
                "Trained classifier not available — model.pt missing or "
                "training module not installed. Falling back to CHAT for all requests."
            )

    if _classify_fn is None:
        return {"intent": "CHAT", "confidence": 0.0, "all_probs": {}}

    emb = embedding_cache.get(utterance)
    if emb is None:
        emb = encode_queries([utterance])[0]
        embedding_cache[utterance] = emb
    return _classify_fn(utterance, embedding=emb)


def _safe_classify(
    utterance: str,
    embedding_cache: dict[str, np.ndarray],
) -> dict[str, Any]:
    try:
        return _classify_one(utterance, embedding_cache)
    except Exception:
        logger.exception("Classifier inference failed for '%s' — falling back to CHAT", utterance)
        return {"intent": "CHAT", "confidence": 0.0, "all_probs": {}}


@trace_latency("Classifier Router Node", run_type="chain")
def classifier_router_node(state: AgentState) -> dict[str, Any]:
    start_time = time.time()
    user_text = last_user_text(state)

    embedding_cache: dict[str, np.ndarray] = {}
    result = _safe_classify(user_text, embedding_cache)

    confidence = result["confidence"]
    intent = result["intent"]
    decided_by = "CLASSIFIER_FAST"
    current_intents: list[str] = ["CHAT"]
    intent_queries: dict[str, str] | None = None

    threshold = SEARCH_THRESHOLD if intent == "SEARCH" else CLASSIFIER_THRESHOLD
    if confidence >= threshold and not has_boundary_markers(user_text):
        current_intents = [intent]
        logger.info(
            "[Classifier Router] Fast path. Intent: %s (confidence=%.4f, threshold=%.2f)",
            intent, confidence, threshold,
        )
    else:
        if has_boundary_markers(user_text):
            reason = f"boundary_markers (conf={confidence:.4f})"
        elif intent == "SEARCH" and confidence < SEARCH_THRESHOLD:
            reason = f"search_threshold (conf={confidence:.4f} < {SEARCH_THRESHOLD})"
        else:
            reason = f"low_confidence (conf={confidence:.4f})"
        logger.info("[Classifier Router] Rewriter triggered. Reason: %s", reason)

        rewriter_result = rewriter_node(state)
        fragments: list[str] = rewriter_result.get("fragments", [])

        if not fragments:
            logger.warning("[Classifier Router] Rewriter produced no fragments, routing to CHAT")
            current_intents = ["CHAT"]
            decided_by = "REWRITER_EMPTY"
        else:
            fragment_intents: list[str] = []
            intent_queries = {}

            for fragment in fragments:
                frag_result = _safe_classify(fragment, embedding_cache)
                frag_intent = frag_result["intent"]
                frag_conf = frag_result["confidence"]
                logger.info(
                    "[Classifier Router] Fragment '%s' → %s (conf=%.4f)",
                    fragment, frag_intent, frag_conf,
                )
                fragment_intents.append(frag_intent)
                existing = intent_queries.get(frag_intent)
                if existing:
                    intent_queries[frag_intent] = f"{existing}; {fragment}"
                else:
                    intent_queries[frag_intent] = fragment

            current_intents = list(dict.fromkeys(fragment_intents))
            decided_by = "REWRITER"

    latency = time.time() - start_time

    routing_meta = {
        "decided_by": decided_by,
        "confidence": round(confidence, 4),
        "all_probs": {k: round(v, 4) for k, v in result.get("all_probs", {}).items()},
        "latency_seconds": latency,
    }

    return {
        "current_intents": current_intents,
        "routing_meta": routing_meta,
        "intent_queries": intent_queries,
    }
