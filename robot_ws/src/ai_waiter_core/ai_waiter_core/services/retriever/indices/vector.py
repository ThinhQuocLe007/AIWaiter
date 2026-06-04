import os 
from typing import List, Tuple

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from ai_waiter_core.utils import logger
from ai_waiter_core.services.retriever.indices.embeddings import get_embedding_model
from ai_waiter_core.services.retriever.indices.base import SearchIndex

class VectorStore(SearchIndex):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.vector_db = None
        self.embedding = get_embedding_model()
        os.makedirs(self.db_path, exist_ok=True)
    
    def build(self, documents: List[Document]) -> bool:
        try:
            self.vector_db = FAISS.from_documents(documents, self.embedding)
            self.vector_db.save_local(self.db_path)
            logger.info(f'[INFO] Vector store saved to {self.db_path}')
            return True
        except Exception as e:
            logger.error(f'[ERROR] Creating vector store: {e}')
            return False
    
    def load(self) -> bool:
        try:
            self.vector_db = FAISS.load_local(self.db_path, self.embedding, allow_dangerous_deserialization=True)
            logger.info(f'[INFO] Vector store loaded from {self.db_path}')
            return True

        except Exception as e:
            logger.error(f'[ERROR] Loading vector store: {e}')
            return False
    
    def search(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        try:
            results = self.vector_db.similarity_search_with_score(query, k=k)
            return results
        except Exception as e:
            logger.error(f'[ERROR] Searching vector store: {e}')
            return []
