from langchain_core.tools import tool
from typing import Optional
from ai_waiter_core.schemas.search import SearchInput, SearchResponse
from ai_waiter_core.services.retriever.builder import IndexBuilder
from ai_waiter_core.services.retriever.hybrid_retriever import RetrieverManager
from ai_waiter_core.utils import trace_latency

builder = IndexBuilder()
builder.load_database()
retriever = RetrieverManager(
    vector_engine=builder.vector_engine,
    bm25_engine=builder.bm25_engine
)


@tool(response_format="content_and_artifact", args_schema=SearchInput)
@trace_latency("Search Tool", run_type="tool")
def search(query: str,
           max_price: Optional[float] = None,
           min_price: Optional[float] = None,
           diet_type: Optional[str] = None,
           category: Optional[str] = None) -> SearchResponse:
    """
    Search the restaurant menu for food, drinks, prices, and ingredients.
    Use this for discovery and general questions about what we serve.
    """
    results = retriever.search(
        query=query,
        k=3,
        max_price=max_price,
        min_price=min_price,
        diet_type=diet_type,
        category=category
    )

    if not results:
        result = SearchResponse(
            status="success",
            results=[],
            message="Không tìm thấy món ăn phù hợp."
        )
        return (result.message, result)

    result = SearchResponse(
        status="success",
        results=results,
        message=f"Tìm thấy {len(results)} kết quả."
    )
    return (result.message, result)
