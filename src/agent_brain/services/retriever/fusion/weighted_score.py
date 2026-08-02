"""Score-based linear fusion — an alternative to Reciprocal Rank Fusion.

RRF discards score magnitudes: a BM25 score of 25.0 and 0.01 are treated
identically (just ranks). Linear fusion normalises both lanes to [0, 1] and
combines them as a weighted sum, preserving score magnitudes so a decisive
BM25 match is not demoted by a weak FAISS result.
"""
import unicodedata
from typing import List, Tuple

from langchain_core.documents import Document

from src.agent_brain.schemas.search import SearchResult
from src.agent_brain.services.retriever.indices.embeddings import get_profile
from src.agent_brain.services.retriever.fusion.rrf import (
    gate_decision,
    _raw_score_to_cosine,
    _keywords,
    _contains_term,
)
from src.agent_brain.utils import logger

# Default lane weights for linear fusion. Unlike RRF where weights multiply
# reciprocal ranks (range ~0.016), linear weights multiply normalised scores in
# [0, 1], so the semantics differ. Start equal and let a sweep decide.
BM25_WEIGHT = 1.0
VECTOR_WEIGHT = 1.0


def _normalise_bm25(results: List[Tuple[Document, float]]) -> dict[int, float]:
    """Normalise BM25 scores to [0, 1] within the result set.

    Each score is divided by the highest score in the set so the strongest match
    always contributes 1.0. An empty set returns no entries.
    """
    if not results:
        return {}
    max_score = max(s for _, s in results)
    if max_score <= 0:
        return {}
    return {hash(doc.page_content): score / max_score for doc, score in results}


def _cosine_scores(results: List[Tuple[Document, float]], normalize: bool) -> dict[int, float]:
    """Convert FAISS raw L2 distances to cosine similarities in [0, 1]."""
    return {hash(doc.page_content): _raw_score_to_cosine(score, normalize)
            for doc, score in results}


class LinearScoreFusion:
    def fuse(self,
             bm25_results: List[Tuple[Document, float]],
             vector_results: List[Tuple[Document, float]],
             k: int,
             **kwargs) -> List[SearchResult]:

        query = kwargs.get("query", "")
        w_bm25 = kwargs.get("w_bm25", BM25_WEIGHT)
        w_vector = kwargs.get("w_vector", VECTOR_WEIGHT)
        normalize = get_profile().get("normalize", False)

        # --- 1. GATEKEEPER (same as RRF) ---
        gate = gate_decision(bm25_results, vector_results, query, normalize)
        if not gate["passed"]:
            logger.info(
                f"[LINEAR] Rejected query: '{query}' "
                f"(raw={gate['raw_top']:.3f}, cos={gate['cos_sim']:.3f})"
            )
            return []

        logger.info(
            f"[LINEAR] Approved query: '{query}' "
            f"(cos={gate['cos_sim']:.3f}, Lexical: {gate['lexical_pass']} {gate['matched_terms']})"
        )

        # --- 2. NORMALISE BOTH LANES TO [0, 1] ---
        bm25_norm = _normalise_bm25(bm25_results)
        vector_cos = _cosine_scores(vector_results, normalize)

        # --- 3. WEIGHTED SCORE FUSION ---
        fusion_scores = {}

        for doc, raw_score in bm25_results:
            doc_id = hash(doc.page_content)
            norm_score = bm25_norm.get(doc_id, 0.0)
            fusion_scores[doc_id] = {
                "doc": doc,
                "score": w_bm25 * norm_score,
                "bm25_score": raw_score,
                "vector_score": 0.0,
            }

        for doc, raw_score in vector_results:
            doc_id = hash(doc.page_content)
            cos = vector_cos.get(doc_id, 0.0)
            contrib = w_vector * cos
            if doc_id in fusion_scores:
                fusion_scores[doc_id]["score"] += contrib
                fusion_scores[doc_id]["vector_score"] = raw_score
            else:
                fusion_scores[doc_id] = {
                    "doc": doc,
                    "score": contrib,
                    "bm25_score": 0.0,
                    "vector_score": raw_score,
                }

        # --- 4. FORMAT AND RETURN ---
        final_list = []
        for entry in fusion_scores.values():
            doc = entry["doc"]
            final_list.append(SearchResult(
                document=doc,
                score=entry["score"],
                bm25_score=entry["bm25_score"],
                bm25_normalized=0.0,
                vector_score=entry["vector_score"],
                source=doc.metadata.get("source", "unknown"),
                doc_type=doc.metadata.get("type", "unknown"),
            ))

        # same dedup as RRF
        sorted_results = sorted(final_list, key=lambda x: x.score, reverse=True)
        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for r in sorted_results:
            meta = r.document.metadata
            key = meta.get("name") or meta.get("title") or r.document.page_content
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped[:k]
