from functools import lru_cache
from typing import List

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

from ai_waiter_core.config import settings

EMBEDDING_MODEL_NAME = "AITeamVN/Vietnamese_Embedding"


@lru_cache(maxsize=1)
def get_sentence_transformer(model_name: str = EMBEDDING_MODEL_NAME) -> SentenceTransformer:
    """Single shared SentenceTransformer instance.

    Loaded once and reused by both the retriever (vector index) and the
    semantic router, so the embedding model only occupies memory once instead
    of being loaded twice. Critical on the Jetson Orin 8GB unified-memory target.

    Runs on settings.EMBEDDING_DEVICE (falls back to the global DEVICE when unset)
    rather than always on DEVICE: keeping the embedding model off the iGPU frees
    unified RAM for the Ollama LLM. float16 is only used on CUDA — on CPU PyTorch
    lacks fast/complete half-precision kernels, so float32 is both faster and safer.
    """
    device = settings.EMBEDDING_DEVICE or settings.DEVICE
    torch_dtype = "float16" if device == "cuda" else "float32"
    return SentenceTransformer(model_name, device=device, model_kwargs={"torch_dtype": torch_dtype})


class SharedEmbeddings(Embeddings):
    """LangChain Embeddings adapter over the shared SentenceTransformer singleton.

    Produces the same vectors as the previous HuggingFaceEmbeddings wrapper
    (same model, default no-normalization encode), so existing FAISS indices
    remain valid without a rebuild.
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self._model = get_sentence_transformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._model.encode(texts, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self._model.encode([text], convert_to_numpy=True)[0].tolist()


def get_embedding_model() -> Embeddings:
    return SharedEmbeddings()
