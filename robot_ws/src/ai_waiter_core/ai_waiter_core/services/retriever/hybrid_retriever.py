import os
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor
from ai_waiter_core.config import settings
from ai_waiter_core.utils import logger
from ai_waiter_core.schemas.search import SearchResult
from langchain_core.documents import Document

from ai_waiter_core.services.retriever.indices.bm25 import BM25Index
from ai_waiter_core.services.retriever.indices.vector import VectorStore
from ai_waiter_core.services.retriever.loaders.document_loader import DocumentLoader
from ai_waiter_core.services.retriever.normalization import normalize_vector_score
from ai_waiter_core.services.retriever.fusion import get_fusion_strategy


class RetrieverManager: 
    def __init__(self, score_threshold: float = 0.3, k: int = 5): 
        self.loader = DocumentLoader()
        self.score_threshold = score_threshold
        self.k = k

        self.vector_engine = VectorStore(db_path=settings.VECTOR_DB_PATH)
        self.bm25_engine = BM25Index(db_path=settings.BM25_PATH)

        self.is_ready = False 
        self._documents = [] 
        self.executor = ThreadPoolExecutor(max_workers=2) 

    def load_directory(self, directory_path: str) -> List[Document]:
        all_documents = []
        
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            
            if os.path.isfile(file_path):
                docs = self.loader.load(file_path)
                all_documents.extend(docs)
                
        logger.info(f"Scaled Loading: Found {len(all_documents)} docs in {directory_path}")
        return all_documents

    def build_database(self, data_paths: List[str]) -> bool: 
        logger.info(f"[INFO] Building database from {len(data_paths)} paths...")
        self._documents = []

        for path in data_paths:
            if os.path.isdir(path):
                self._documents.extend(self.load_directory(path))
            elif os.path.isfile(path):
                self._documents.extend(self.loader.load(path))
        
        if not self._documents: 
            logger.error("[ERROR] No documents successfully loaded")
            return False 

        if self.vector_engine.build(self._documents) and self.bm25_engine.build(self._documents):
            self.is_ready = True 
            logger.info("[INFO] Database built successfully")
            return True 

        return False 

    def hybrid_search(self, 
                      query: str, 
                      k: int = None, 
                      threshold: float = None, 
                      mode: str = "rrf", 
                      rrf_k: int = 60,
                      max_price: float = None,
                      min_price: float = None,
                      diet_type: str = None,
                      category: str = None) -> List[SearchResult]:
        if not self.is_ready:
            logger.warning("Retriever not ready. Run build or load first.")
            return []
        
        k = k or self.k
        threshold = threshold or self.score_threshold
        
        bm25_raw, vector_raw = self._get_raw_scores(query, k=10)
        
        def filter_results(results):
            filtered = []
            for doc, score in results:
                if doc.metadata.get("type") == "menu":
                    doc_price = doc.metadata.get("price", 0.0)
                    doc_diet = doc.metadata.get("diet_type", "")
                    doc_cat = doc.metadata.get("category", "")
                    
                    if max_price is not None and doc_price > max_price:
                        continue
                    if min_price is not None and doc_price < min_price:
                        continue
                    if diet_type is not None and diet_type.lower() not in doc_diet.lower():
                        continue
                    if category is not None and category.lower() not in doc_cat.lower():
                        continue
                filtered.append((doc, score))
            return filtered

        bm25_raw = filter_results(bm25_raw)
        vector_raw = filter_results(vector_raw)
        
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
        
        vector_norm = [(doc, normalize_vector_score(s)) for doc, s in vector]
        return bm25, vector_norm

    def load_database(self) -> bool: 
        logger.info("[INFO] Loading database from disk...")
        if self.vector_engine.load() and self.bm25_engine.load():
            self.is_ready = True 
            return True 
        return False
