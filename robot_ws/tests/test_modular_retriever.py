from ai_waiter_core.services.retriever.builder import IndexBuilder
from ai_waiter_core.services.retriever.hybrid_retriever import RetrieverManager
from ai_waiter_core.config import settings


def test_retriever():
    print("--- Building IndexBuilder ---")
    builder = IndexBuilder()
    project_root = settings.PROJECT_ROOT
    data_path = project_root / "assets" / "data"

    print(f"--- Building Database from {data_path} ---")
    if builder.build([str(data_path)]):
        print("Success: Database built.\n")
    else:
        print("Error: Database build failed.")
        return

    retriever = RetrieverManager(
        vector_engine=builder.vector_engine,
        bm25_engine=builder.bm25_engine
    )

    query = "Lẩu thái hải sản"
    print(f"--- Testing Query: '{query}' ---")

    print("\n[MODE: RRF]")
    results_rrf = retriever.search(query, mode="rrf", k=3)
    for i, res in enumerate(results_rrf, 1):
        name = res.document.metadata.get('name', 'N/A')
        print(f"{i}. {name} (Score: {res.score:.4f})")
        print(f"   Tags: {res.document.metadata.get('tags', 'N/A')}")
        print(f"   Taste: {res.document.metadata.get('taste_profile', 'N/A')}")


if __name__ == "__main__":
    test_retriever()
