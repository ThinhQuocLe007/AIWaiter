from pathlib import Path
from .base_settings import BaseSystemSettings

class DatabaseSettings(BaseSystemSettings):
    @property
    def VECTOR_DB_PATH(self) -> Path:
        return self.storage_dir / "vector" / "faiss_index"

    @property
    def BM25_PATH(self) -> Path:
        return self.storage_dir / "vector" / "bm25.pkl"

    # Note: the business ledger DB (orchestrator.db) lives in the backend, which is its
    # only writer. The agent reaches it through the REST API (orchestrator_client.py),
    # so there is no RESTAURANT_DB_PATH here anymore.

    @property
    def CHECKPOINTS_DB_PATH(self) -> Path:
        return self.storage_dir / "db" / "checkpoints.db"
