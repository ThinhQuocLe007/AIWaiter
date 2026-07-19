from langchain_core.tools import tool

from src.agent_brain.schemas.search import SearchInput, SearchResponse
from src.agent_brain.services.retriever.builder import IndexBuilder
from src.agent_brain.services.retriever.hybrid_retriever import RetrieverManager
from src.agent_brain.utils import logger, trace_latency

builder = IndexBuilder()
builder.load_database()
retriever = RetrieverManager(
    vector_engine=builder.vector_engine,
    bm25_engine=builder.bm25_engine
)


def _split_query(query: str) -> list[str]:
    parts = [p.strip() for p in query.split(",") if p.strip()]
    return parts if len(parts) > 1 else [query.strip()]


@tool(response_format="content_and_artifact", args_schema=SearchInput)
@trace_latency("Search Tool", run_type="tool")
def search(query: str,
           max_price: float | None = None,
           min_price: float | None = None) -> SearchResponse:
    """
    Search the restaurant menu for food, drinks, prices, and ingredients.
    Use this for discovery and general questions about what we serve.

    When the query contains commas, each segment is searched independently
    and results are merged — this makes multi-keyword queries
    like "ốc, tôm, hải sản" work well instead of failing as one blob.
    """
    sub_queries = _split_query(query)

    if len(sub_queries) == 1:
        results = retriever.search(
            query=sub_queries[0],
            k=6,
            max_price=max_price,
            min_price=min_price,
        )
    else:
        results = _multi_search(sub_queries, max_price, min_price)

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


def _multi_search(sub_queries: list[str], max_price: float | None,
                  min_price: float | None) -> list:
    all_results: list = []
    seen: set[str] = set()

    for q in sub_queries:
        try:
            batch = retriever.search(
                query=q,
                k=6,
                max_price=max_price,
                min_price=min_price,
            )
        except Exception:
            logger.warning("Sub-search failed for '%s'", q)
            continue
        for r in batch:
            name = r.document.metadata.get("name", "")
            if name and name not in seen:
                seen.add(name)
                all_results.append(r)

    all_results.sort(key=lambda r: r.score, reverse=True)
    logger.info(
        "Multi-search: %d sub-queries → %d unique results (top-6 returned)",
        len(sub_queries), len(all_results),
    )
    return all_results[:6]
