from typing import List, Tuple
from langchain_core.documents import Document
from ai_waiter_core.schemas.search import SearchResult
from ai_waiter_core.utils import logger
from ..utils.rrf import compute_reciprocal_rank
from .base import BaseFusion

class RRFFusion(BaseFusion):
    def fuse(self, 
             bm25_results: List[Tuple[Document, float]], 
             vector_results: List[Tuple[Document, float]], 
             k: int, 
             **kwargs) -> List[SearchResult]:
        
        query = kwargs.get("query", "")
        rrf_k = kwargs.get("rrf_k", 60)
        
        # --- 1. DUAL-LANE GATEKEEPER (NO INFORMATION SHIELD) ---
        top_vector_score = vector_results[0][1] if vector_results else 0.0
        semantic_match = top_vector_score >= 0.35
        
        # Clean query, split on commas first to preserve multi-word phrases, otherwise split by words
        lexical_match = False
        clean_query = query.lower().replace("?", "").replace(".", "")
        keywords = [kw.strip() for kw in clean_query.split(",") if kw.strip()]
        if len(keywords) == 1 and " " in keywords[0]:
            keywords = [w.strip() for w in keywords[0].split() if w.strip()]
            
        if keywords:
            # Check if any core keyword is present exactly inside the top BM25 or top Vector document
            top_docs_text = ""
            if bm25_results:
                top_docs_text += bm25_results[0][0].page_content.lower()
            if vector_results:
                top_docs_text += " " + vector_results[0][0].page_content.lower()
                
            if any(kw in top_docs_text for kw in keywords):
                lexical_match = True
                
        # Gatekeeper evaluation: Trigger NO INFORMATION fallback if both lanes fail
        if not semantic_match and not lexical_match:
            logger.info(
                f"[GATEKEEPER] Rejected query: '{query}' "
                f"(Top Vector Similarity: {top_vector_score:.3f} < 0.35, Lexical Match: {lexical_match})"
            )
            return []
            
        logger.info(
            f"[GATEKEEPER] Approved query: '{query}' "
            f"(Top Vector Similarity: {top_vector_score:.3f}, Lexical Match: {lexical_match})"
        )

        fusion_scores = {} # page_content_hash -> dict

        # 1. Process BM25
        for rank, (doc, raw_score) in enumerate(bm25_results, 1):
            doc_id = hash(doc.page_content)
            fusion_scores[doc_id] = {
                "doc": doc,
                "score": compute_reciprocal_rank(rank, rrf_k),
                "bm25_score": raw_score,
                "vector_score": 0.0
            }

        # 2. Process Vector
        for rank, (doc, raw_score) in enumerate(vector_results, 1):
            doc_id = hash(doc.page_content)
            rrf_contrib = compute_reciprocal_rank(rank, rrf_k)
            
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

        # 3. Format to SearchResult
        final_list = []
        for entry in fusion_scores.values():
            doc = entry["doc"]
            final_list.append(SearchResult(
                document=doc,
                score=entry["score"],
                bm25_score=entry["bm25_score"],
                bm25_normalized=0.0, # Not used in RRF
                vector_score=entry["vector_score"],
                source=doc.metadata.get("source", "unknown"),
                doc_type=doc.metadata.get("type", "unknown")
            ))

        return self._format_results(final_list, k)
