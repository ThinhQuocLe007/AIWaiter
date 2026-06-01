from typing import List
from abc import ABC, abstractmethod
from langchain_core.documents import Document

class SearchIndex(ABC):
    @abstractmethod
    def build(self, documents: List[Document]) -> bool:
        pass
    
    @abstractmethod
    def load(self) -> bool:
        pass
    
    @abstractmethod
    def search(self, query: str, k: int = 4) -> List[Document]:
        pass
