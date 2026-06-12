import math
from typing import List, Tuple
from langchain_core.documents import Document
from ai_waiter_core.schemas.search import SearchResult

def sigmoid_normalize(score: float, mean: float = 0.0, scale: float = 1.0) -> float:
    exponent = max(min(-scale * (score - mean), 500), -500)
    return 1.0 / (1.0 + math.exp(exponent))

def normalize_vector_score(distance: float) -> float:
    return 1.0 / (1.0 + distance)

def normalize_bm25_batch(scores: List[float]) -> List[float]:
    if not scores:
        return []
    mean = sum(scores) / len(scores)
    return [sigmoid_normalize(s, mean) for s in scores]

def calculate_hybrid_score(bm25_score: float, vector_score: float,
                           bm25_weight: float = 0.6, vector_weight: float = 0.4) -> float:
    return (sigmoid_normalize(bm25_score) * bm25_weight) + (vector_score * vector_weight)

class WeightedFusion:
    def fuse(self, 
             bm25_results: List[Tuple[Document, float]], 
             vector_results: List[Tuple[Document, float]], 
             k: int, 
             **kwargs) -> List[SearchResult]:
        
        bm25_weight = kwargs.get("bm25_weight", 0.6)
        vector_weight = kwargs.get("vector_weight", 0.4)
        threshold = kwargs.get("threshold", 0.3)

        lookup = {}

        for doc, score in bm25_results:
            doc_id = hash(doc.page_content)
            lookup[doc_id] = {"doc": doc, "bm25": score, "vector": 0.0}

        for doc, score in vector_results:
            doc_id = hash(doc.page_content)
            if doc_id in lookup:
                lookup[doc_id]["vector"] = score
            else:
                lookup[doc_id] = {"doc": doc, "bm25": 0.0, "vector": score}

        raw_bm25_scores = [v["bm25"] for v in lookup.values() if v["bm25"] > 0]
        norm_bm25_scores = normalize_bm25_batch(raw_bm25_scores)
        
        norm_map = {
            raw: norm 
            for raw, norm in zip(raw_bm25_scores, norm_bm25_scores)
        }

        final_list = []
        for entry in lookup.values():
            doc = entry["doc"]
            bm25_raw = entry["bm25"]
            bm25_norm = norm_map.get(bm25_raw, 0.0)
            vector_score = entry["vector"]

            hybrid_score = calculate_hybrid_score(
                bm25_norm, 
                vector_score, 
                bm25_weight=bm25_weight, 
                vector_weight=vector_weight
            )

            if hybrid_score >= threshold:
                final_list.append(SearchResult(
                    document=doc,
                    score=hybrid_score,
                    bm25_score=bm25_raw,
                    bm25_normalized=bm25_norm,
                    vector_score=vector_score,
                    source=doc.metadata.get("source", "unknown"),
                    doc_type=doc.metadata.get("type", "unknown")
                ))

        return self._format_results(final_list, k)

    def _format_results(self, results: list, k: int) -> List[SearchResult]:
        return sorted(results, key=lambda x: x.score, reverse=True)[:k]
