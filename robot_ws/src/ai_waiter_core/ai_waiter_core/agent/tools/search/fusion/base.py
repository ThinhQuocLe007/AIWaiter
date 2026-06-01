from abc import ABC, abstractmethod
from typing import List, Tuple
from langchain_core.documents import Document
from ai_waiter_core.schemas.search import SearchResult

class BaseFusion(ABC):
    @abstractmethod
    def fuse(self, 
             bm25_results: List[Tuple[Document, float]], 
             vector_results: List[Tuple[Document, float]], 
             k: int, 
             **kwargs) -> List[SearchResult]:
        """
        Base method to combine results from multiple search engines.
        """
        pass

    def _format_results(self, final_results: list, k: int) -> List[SearchResult]:
        """ Helper to sort and slice the final list. """
        return sorted(final_results, key=lambda x: x.score, reverse=True)[:k]
