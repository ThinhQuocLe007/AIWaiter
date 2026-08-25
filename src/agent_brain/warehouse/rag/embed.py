"""Vietnamese embedding wrapper (singleton)."""

from __future__ import annotations

from functools import lru_cache

from src.agent_brain.warehouse.paths import settings


@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embed_model, device=settings.embed_device)


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return get_embedder().encode(texts, normalize_embeddings=True).tolist()
