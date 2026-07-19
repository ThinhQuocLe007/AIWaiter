from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.documents import Document

class SearchResult(BaseModel):
    document: Document
    score: float
    bm25_score: float
    bm25_normalized: float
    vector_score: float
    source: str
    doc_type: str

    class Config:
        arbitrary_types_allowed = True # Allow Document objects

class SearchInput(BaseModel):
    query: str = Field(
        ...,
        description=(
            "The optimized search query for database lookup. If the customer's request is conversational, "
            "emotional, or implicit (e.g. 'ấm bụng', 'giải nhiệt', 'trời lạnh quá'), DO NOT search that exact sentence. "
            "Instead, rewrite it into concrete dish names, categories, or tags (e.g. 'cháo, lẩu, súp nóng' or "
            "'nước ép, sinh tố, trà đá, thanh nhiệt') so the search engine can match the database entries correctly."
        )
    )
    max_price: Optional[float] = Field(None, description="Max price in VND if specified (e.g. 100000 for 'dưới 100k' or 'nhỏ hơn 100 ngàn').")
    min_price: Optional[float] = Field(None, description="Min price in VND if specified.")


class SearchResponse(BaseModel):
    status: Literal["success", "error"]
    results: List[SearchResult]
    message: str
