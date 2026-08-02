import re
import unicodedata
from typing import List, Tuple
from langchain_core.documents import Document
from src.agent_brain.schemas.search import SearchResult
from src.agent_brain.services.retriever.indices.embeddings import get_profile
from src.agent_brain.utils import logger

SEMANTIC_THRESHOLD = 0.25

# Lane weights for reciprocal rank fusion. Equal weights let the dense lane demote a
# lexical exact match: on a menu corpus the customer types the words printed on the
# menu, so BM25 is the stronger lane nearly everywhere and the dense lane earns its
# place by covering the queries BM25 misses, not by voting equally on the ones it does
# not. Set from the sweep in evals/scripts/eval_rrf_weights.py.
BM25_WEIGHT = 3.0
VECTOR_WEIGHT = 1.0


def compute_reciprocal_rank(rank: int, k: int = 60) -> float:
    rank = max(1, rank)
    return 1.0 / (k + rank)


def _raw_score_to_cosine(raw_score: float, normalize: bool) -> float:
    if not normalize:
        return float(raw_score)
    cosine = max(0.0, min(1.0, 1.0 - raw_score / 2.0))
    return cosine


def _keywords(query: str) -> list[str]:
    """Split a query into the terms the lexical lane looks for.

    Common Vietnamese function words are stripped because they match in virtually every
    menu document. A query like "cho xem món pizza" would otherwise pass the lexical gate
    on "món" alone and admit a hallucinated result set for a dish the kitchen cannot
    produce.
    """
    _STOPWORDS = {
        "có", "món", "gì", "cho", "không", "với", "nào", "này",
        "kia", "đó", "là", "và", "thì", "mà", "nên", "sẽ", "đã",
        "đang", "cũng", "chỉ", "vẫn",
    }
    clean = query.lower().replace("?", "").replace(".", "")
    parts = [kw.strip() for kw in clean.split(",") if kw.strip()]
    if len(parts) == 1 and " " in parts[0]:
        parts = [w.strip() for w in parts[0].split() if w.strip()]
    return [p for p in parts if p not in _STOPWORDS]


def _contains_term(haystack: str, term: str) -> bool:
    """Whole-term containment, not substring.

    A plain `in` test matches across word boundaries, which on a Vietnamese menu is
    almost always a false positive: "đông" in "có gì cho nhóm đông người chia sẻ"
    matches inside "Cải Thìa Xào Nấm Đông Cô" and admits a query the corpus cannot
    answer. Single syllables are common enough that substring matching makes the
    lexical lane fire on nearly every query.
    """
    if not term:
        return False
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", haystack) is not None


def gate_decision(
    bm25_results: List[Tuple[Document, float]],
    vector_results: List[Tuple[Document, float]],
    query: str,
    normalize: bool | None = None,
) -> dict:
    """The dual-lane gatekeeper decision, in one place.

    Both the deployed retriever and the evaluation harness call this. They used to
    implement it separately and had drifted: the harness checked query terms against
    the dense lane's top document only, so it recorded rejections the deployed gate
    would never make.

    The semantic lane passes when the dense engine's top-1 cosine similarity reaches
    the threshold. The lexical lane passes when a query term appears, as a whole term,
    in the top-3 documents of either lane (top-1 was too strict — vibe terms like
    "ấm bụng" sitting at rank 2-3 were missed). A query is admitted when either lane
    passes.
    """
    if normalize is None:
        normalize = get_profile().get("normalize", False)

    raw_top = vector_results[0][1] if vector_results else 0.0
    cos_sim = _raw_score_to_cosine(raw_top, normalize)
    semantic_pass = cos_sim >= SEMANTIC_THRESHOLD

    haystack = ""
    for _, (doc, _) in enumerate(bm25_results[:3]):
        haystack += doc.page_content.lower() + " "
    for _, (doc, _) in enumerate(vector_results[:3]):
        haystack += doc.page_content.lower() + " "
    haystack = unicodedata.normalize("NFC", haystack)

    terms = _keywords(query)
    matched = [t for t in terms if _contains_term(haystack, unicodedata.normalize("NFC", t))]
    lexical_pass = bool(matched)

    return {
        "semantic_pass": bool(semantic_pass),
        "lexical_pass": lexical_pass,
        "passed": bool(semantic_pass or lexical_pass),
        "raw_top": float(raw_top),
        "cos_sim": float(cos_sim),
        "matched_terms": matched,
    }


class RRFFusion:
    def fuse(self, 
             bm25_results: List[Tuple[Document, float]], 
             vector_results: List[Tuple[Document, float]], 
             k: int, 
             **kwargs) -> List[SearchResult]:
        
        query = kwargs.get("query", "")
        rrf_k = kwargs.get("rrf_k", 60)
        w_bm25 = kwargs.get("w_bm25", BM25_WEIGHT)
        w_vector = kwargs.get("w_vector", VECTOR_WEIGHT)
        normalize = get_profile().get("normalize", False)

        # --- 1. DUAL-LANE GATEKEEPER ---
        gate = gate_decision(bm25_results, vector_results, query, normalize)

        if not gate["passed"]:
            logger.info(
                f"[GATEKEEPER] Rejected query: '{query}' "
                f"(raw={gate['raw_top']:.3f}, cos={gate['cos_sim']:.3f} "
                f"< {SEMANTIC_THRESHOLD}, Lexical Match: False)"
            )
            return []

        logger.info(
            f"[GATEKEEPER] Approved query: '{query}' "
            f"(raw={gate['raw_top']:.3f}, cos={gate['cos_sim']:.3f}, "
            f"Lexical Match: {gate['lexical_pass']} {gate['matched_terms']})"
        )

        fusion_scores = {}

        for rank, (doc, raw_score) in enumerate(bm25_results, 1):
            doc_id = hash(doc.page_content)
            fusion_scores[doc_id] = {
                "doc": doc,
                "score": w_bm25 * compute_reciprocal_rank(rank, rrf_k),
                "bm25_score": raw_score,
                "vector_score": 0.0
            }

        for rank, (doc, raw_score) in enumerate(vector_results, 1):
            doc_id = hash(doc.page_content)
            rrf_contrib = w_vector * compute_reciprocal_rank(rank, rrf_k)

            if doc_id in fusion_scores:
                fusion_scores[doc_id]["score"] += rrf_contrib
                fusion_scores[doc_id]["vector_score"] = raw_score
            else:
                fusion_scores[doc_id] = {
                    "doc": doc,
                    "score": rrf_contrib,
                    "bm25_score": 0.0,
                    "vector_score": raw_score
                }

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
                doc_type=doc.metadata.get("type", "unknown")
            ))

        return self._format_results(final_list, k)

    def _format_results(self, results: list, k: int) -> list[SearchResult]:
        sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for r in sorted_results:
            meta = r.document.metadata
            # Menu dishes dedupe on `name`; restaurant_info.txt sections carry
            # `title` instead. Keying on `name` alone silently dropped every
            # info doc here, so no opening-hours / address / policy question
            # could ever be answered from the index even though the metadata
            # filter deliberately lets those docs through.
            key = meta.get("name") or meta.get("title") or r.document.page_content
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped[:k]
