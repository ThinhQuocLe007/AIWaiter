from langchain_core.tools import tool
from typing import Optional
from .hybrid_retriever import RetrieverManager

# Initialize once
retriever = RetrieverManager()
retriever.load_database()

from pydantic import BaseModel, Field

class SearchMenuInput(BaseModel):
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
    diet_type: Optional[str] = Field(None, description="Diet type (e.g. 'chay' or 'mặn').")
    category: Optional[str] = Field(None, description="Menu category name.")

from ai_waiter_core.utils import trace_latency

@tool(args_schema=SearchMenuInput)
@trace_latency("Search Tool", run_type="tool")
def search(query: str, 
           max_price: Optional[float] = None, 
           min_price: Optional[float] = None, 
           diet_type: Optional[str] = None, 
           category: Optional[str] = None) -> str:
    """
    Search the restaurant menu for food, drinks, prices, and ingredients.
    Use this for discovery and general questions about what we serve.
    """
    results = retriever.hybrid_search(
        query=query, 
        k=3, 
        max_price=max_price, 
        min_price=min_price, 
        diet_type=diet_type, 
        category=category
    )
    if not results:
        return "No matching menu items found. Please try a different keywords."
    
    return "\n---\n".join([f"[{r.doc_type}] {r.document.page_content}" for r in results])
