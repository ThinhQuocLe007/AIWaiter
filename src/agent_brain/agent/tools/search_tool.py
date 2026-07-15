
from langchain_core.tools import tool

from src.agent_brain.schemas.search import SearchInput, SearchResponse
from src.agent_brain.services.retriever.builder import IndexBuilder
from src.agent_brain.services.retriever.hybrid_retriever import RetrieverManager
from src.agent_brain.utils import trace_latency

builder = IndexBuilder()
builder.load_database()
retriever = RetrieverManager(
    vector_engine=builder.vector_engine,
    bm25_engine=builder.bm25_engine
)


@tool(response_format="content_and_artifact", args_schema=SearchInput)
@trace_latency("Search Tool", run_type="tool")
def search(query: str,
           max_price: float | None = None,
           min_price: float | None = None,
           diet_type: str | None = None,
           category: str | None = None) -> SearchResponse:
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
