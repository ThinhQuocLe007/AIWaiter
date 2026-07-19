from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor
from src.agent_brain.utils import logger
from src.agent_brain.schemas.search import SearchResult
from src.agent_brain.services.retriever.fusion import get_fusion_strategy
from src.agent_brain.services.retriever.filters import by_menu_metadata


class RetrieverManager:
    def __init__(self, vector_engine, bm25_engine, score_threshold: float = 0.3, k: int = 5):
        self.vector_engine = vector_engine
        self.bm25_engine = bm25_engine
        self.score_threshold = score_threshold
        self.k = k
        self.executor = ThreadPoolExecutor(max_workers=2)

    def search(self,
               query: str,
               k: int = None,
               threshold: float = None,
               mode: str = "rrf",
               rrf_k: int = 60,
               max_price: float = None,
               min_price: float = None,
               diet_type: str = None,
               category: str = None) -> List[SearchResult]:
        k = k or self.k
        threshold = threshold or self.score_threshold

        bm25_raw, vector_raw = self._get_raw_scores(query, k=15)

        bm25_raw = by_menu_metadata(bm25_raw, max_price, min_price, diet_type, category)
        vector_raw = by_menu_metadata(vector_raw, max_price, min_price, diet_type, category)

        strategy = get_fusion_strategy(mode)
        return strategy.fuse(
            bm25_results=bm25_raw,
            vector_results=vector_raw,
            k=k,
            threshold=threshold,
            rrf_k=rrf_k,
            query=query
        )

    def _get_raw_scores(self, query: str, k: int) -> Tuple[list, list]:
        future_bm25 = self.executor.submit(self.bm25_engine.search, query, k=k)
        future_vector = self.executor.submit(self.vector_engine.search, query, k=k)

        bm25 = future_bm25.result()
        vector = future_vector.result()

        return bm25, vector
