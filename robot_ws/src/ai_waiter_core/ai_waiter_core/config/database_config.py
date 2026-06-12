from pathlib import Path
from .base_settings import BaseSystemSettings

class DatabaseSettings(BaseSystemSettings):
    @property
    def VECTOR_DB_PATH(self) -> Path:
        return self.storage_dir / "vector" / "faiss_index"

    @property
    def BM25_PATH(self) -> Path:
        return self.storage_dir / "vector" / "bm25.pkl"

    @property
    def RESTAURANT_DB_PATH(self) -> Path:
        return self.storage_dir / "db" / "restaurant.db"
        
    @property
    def CHECKPOINTS_DB_PATH(self) -> Path:
        return self.storage_dir / "db" / "checkpoints.db"
