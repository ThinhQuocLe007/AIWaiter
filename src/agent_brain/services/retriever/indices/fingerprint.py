"""Embedding-model fingerprint for embedding-dependent artifacts.

Each artifact built from embeddings — the FAISS vector index and the router
centroids — is produced by ONE specific embedding model and is only meaningful
when queried with that SAME model. Switch EMBEDDING_MODEL without rebuilding and
the stored vectors silently mismatch the query vectors (different dimensions /
distributions), so retrieval degrades or crashes deep in a CUDA/FAISS call with
no hint at the real cause.

To make that failure loud and obvious we stamp the active model name next to each
artifact at build time (`write_fingerprint`) and check it at load time
(`verify_fingerprint`).
"""
from pathlib import Path

from src.agent_brain.utils import logger
from src.agent_brain.services.retriever.indices.embeddings import active_model_name

FINGERPRINT_FILENAME = "embedding_model.txt"


class EmbeddingModelMismatch(RuntimeError):
    """An artifact was built with a different embedding model than the active one."""


def write_fingerprint(artifact_dir: Path) -> None:
    """Record the active embedding model name next to an artifact."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / FINGERPRINT_FILENAME).write_text(
        active_model_name(), encoding="utf-8"
    )


def verify_fingerprint(artifact_dir: Path) -> None:
    """Raise EmbeddingModelMismatch if the stored model != the active model.

    A missing fingerprint (artifact built before fingerprinting existed) cannot be
    verified, so we warn and continue instead of blocking — the dimensions may
    still happen to line up, and a hard failure here would break older indexes.
    """
    fp = Path(artifact_dir) / FINGERPRINT_FILENAME
    active = active_model_name()
    if not fp.exists():
        logger.warning(
            f"[embedding] No model fingerprint at {fp}; cannot verify this artifact "
            f"matches the active model '{active}'. Rebuild to stamp it: "
            f"python scripts/setup.py --embeddings-only"
        )
        return
    stored = fp.read_text(encoding="utf-8").strip()
    if stored != active:
        raise EmbeddingModelMismatch(
            f"Embedding model mismatch in '{Path(artifact_dir).name}': artifact was "
            f"built with '{stored}' but the active model is '{active}'. The stored "
            f"vectors are incompatible with query vectors. "
            f"Rebuild: python scripts/setup.py --embeddings-only"
        )
