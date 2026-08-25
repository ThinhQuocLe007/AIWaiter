"""Live tools — the primitives the retrieval worker and planner call.

`resolve_item` uses the hybrid index (fixed corpus) to map a spoken phrase → canonical item;
the other tools read *live* facts from `warehouse_data` (never from the index).
"""

from __future__ import annotations

from functools import lru_cache

from src.agent_brain.warehouse.rag.index import HybridIndex
from src.agent_brain.warehouse.rag.loader import load_all_docs
from src.agent_brain.warehouse.services.warehouse_data import Item, WarehouseData
from src.agent_brain.warehouse.paths import settings


@lru_cache(maxsize=1)
def get_data() -> WarehouseData:
    d = WarehouseData()
    d.reload()
    return d


@lru_cache(maxsize=1)
def get_index() -> HybridIndex:
    return HybridIndex(load_all_docs(get_data()))


def resolve_item(text: str, k: int = 3) -> list[Item]:
    """Map free-text → candidate items via semantic search over the fixed corpus.

    Items whose name is explicitly mentioned in the query are boosted to the front, so an explicit
    "đường" wins over a fuzzy neighbour even when the embedding is noisy. Candidates that fail the
    relevance gate in `HybridIndex.search` (no lexical overlap and below `retrieval_min_score`) are
    already dropped there, so out-of-scope queries resolve to an empty list.
    """
    hits = get_index().search(text, k=k, min_score=settings.retrieval_min_score)
    data = get_data()
    q = text.lower()
    out: list[Item] = []
    ranked = sorted(
        hits,
        key=lambda ds: (0 if ds[0].meta.get("item", "").lower() in q else 1, -ds[1]),
    )
    for doc, _score in ranked:
        sku = doc.meta.get("sku")
        if sku:
            item = data.get_item_by_sku(sku)
            if item and item not in out:
                out.append(item)
    return out


def get_stock(sku: str) -> float | None:
    return get_data().get_stock(sku)


def get_location(sku: str) -> dict | None:
    return get_data().get_location(sku)


def get_sop(topic: str, k: int = 2) -> list[str]:
    hits = get_index().search(topic, k=k)
    return [d.text for d, _ in hits if d.meta.get("kind") == "sop"]


def search_items(query: str, limit: int = 5) -> list[Item]:
    return get_data().search(query, limit)
