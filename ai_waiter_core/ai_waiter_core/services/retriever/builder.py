import os
from typing import List
from langchain_core.documents import Document

from ai_waiter_core.config import settings
from ai_waiter_core.utils import logger
from ai_waiter_core.services.retriever.document_loader import DocumentLoader
from ai_waiter_core.services.retriever.indices.vector import VectorStore
from ai_waiter_core.services.retriever.indices.bm25 import BM25Index


class IndexBuilder:
    def __init__(self):
        self.loader = DocumentLoader()
        self.vector_engine = VectorStore(db_path=settings.VECTOR_DB_PATH)
        self.bm25_engine = BM25Index(db_path=settings.BM25_PATH)

    def _load_documents(self, directory_path: str) -> List[Document]:
        all_documents = []
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            if os.path.isfile(file_path):
                docs = self.loader.load(file_path)
                all_documents.extend(docs)
        logger.info(f"Found {len(all_documents)} docs in {directory_path}")
        return all_documents

    def build(self, data_paths: List[str]) -> bool:
        logger.info(f"Building database from {len(data_paths)} paths...")
        documents = []
        for path in data_paths:
            if os.path.isdir(path):
                documents.extend(self._load_documents(path))
            elif os.path.isfile(path):
                documents.extend(self.loader.load(path))
        if not documents:
            logger.error("No documents successfully loaded")
            return False
        if self.vector_engine.build(documents) and self.bm25_engine.build(documents):
            logger.info("Database built successfully")
            return True
        return False

    def load_database(self) -> bool:
        logger.info("Loading database from disk...")
        if self.vector_engine.load() and self.bm25_engine.load():
            return True
        return False
