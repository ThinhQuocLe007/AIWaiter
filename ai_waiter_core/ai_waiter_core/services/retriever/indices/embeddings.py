from functools import lru_cache
from typing import List

import numpy as np
import underthesea
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

from ai_waiter_core.config import settings

# Default embedding model when settings.EMBEDDING_MODEL is unset.
EMBEDDING_MODEL_NAME = "AITeamVN/Vietnamese_Embedding"

# A/B registry. Flip settings.EMBEDDING_MODEL (.env: EMBEDDING_MODEL) to swap the
# model, then rebuild: `python scripts/setup.py --embeddings-only`.
#
# Each model needs its own encode-time preprocessing. The SAME profile MUST be
# applied at index-build, query, AND centroid time (see encode_documents /
# encode_queries below) — otherwise the stored vectors and the query vectors are
# produced differently and retrieval silently degrades. Unknown models fall back
# to the no-op default profile.
#   query_prefix / passage_prefix : asymmetric instruction prefixes (e5 family)
#   word_segment                  : underthesea word segmentation (PhoBERT models)
#   normalize                     : L2-normalize embeddings (cosine retrieval)
#   trust_remote_code             : models shipping custom modeling code (gte)
EMBEDDING_PROFILES: dict[str, dict] = {
    # bge-m3 finetune, ~560M params, 1024-dim, ~2.2GB. Top Vietnamese quality, heavy.
    "AITeamVN/Vietnamese_Embedding": {
        "query_prefix": "", "passage_prefix": "",
        "word_segment": False, "normalize": False, "trust_remote_code": False,
    },
    # PhoBERT-base bi-encoder, ~135M, 768-dim, ~0.5GB. VN-specialized, needs word-seg.
    "bkai-foundation-models/vietnamese-bi-encoder": {
        "query_prefix": "", "passage_prefix": "",
        "word_segment": True, "normalize": True, "trust_remote_code": False,
    },
    # PhoBERT-base SBERT (dangvantuan), ~135M, 768-dim. Augmented-SBERT for Vietnamese.
    "dangvantuan/vietnamese-embedding": {
        "query_prefix": "", "passage_prefix": "",
        "word_segment": True, "normalize": True, "trust_remote_code": False,
    },
    # PhoBERT-base SBERT (keepitreal), ~135M, 768-dim. The community "sBERT-Vi".
    "keepitreal/vietnamese-sbert": {
        "query_prefix": "", "passage_prefix": "",
        "word_segment": True, "normalize": True, "trust_remote_code": False,
    },
    # Multilingual e5, ~118M, 384-dim, ~0.47GB. Lightest/fastest, needs query/passage prefix.
    "intfloat/multilingual-e5-small": {
        "query_prefix": "query: ", "passage_prefix": "passage: ",
        "word_segment": False, "normalize": True, "trust_remote_code": False,
    },
    # Multilingual e5, ~278M, 768-dim, ~1.1GB. Stronger than -small, same prefix scheme.
    "intfloat/multilingual-e5-base": {
        "query_prefix": "query: ", "passage_prefix": "passage: ",
        "word_segment": False, "normalize": True, "trust_remote_code": False,
    },
    # GTE multilingual, ~305M, 768-dim, ~1.2GB, 8k ctx. High quality, custom code.
    "Alibaba-NLP/gte-multilingual-base": {
        "query_prefix": "", "passage_prefix": "",
        "word_segment": False, "normalize": True, "trust_remote_code": True,
    },
}

_DEFAULT_PROFILE = {
    "query_prefix": "", "passage_prefix": "",
    "word_segment": False, "normalize": False, "trust_remote_code": False,
}


def active_model_name() -> str:
    """The embedding model currently in effect (settings override or default)."""
    return settings.EMBEDDING_MODEL or EMBEDDING_MODEL_NAME


def get_profile() -> dict:
    """Preprocessing profile for the active model (no-op default if unregistered)."""
    return EMBEDDING_PROFILES.get(active_model_name(), _DEFAULT_PROFILE)


@lru_cache(maxsize=1)
def get_sentence_transformer() -> SentenceTransformer:
    """Single shared SentenceTransformer instance.

    Loaded once and reused by both the retriever (vector index) and the semantic
    router, so the embedding model only occupies memory once instead of being
    loaded twice. Critical on the Jetson Orin 8GB unified-memory target.

    Model: settings.EMBEDDING_MODEL (falls back to EMBEDDING_MODEL_NAME).
    Device: settings.EMBEDDING_DEVICE (falls back to the global DEVICE). Keeping
    the embedding model off the iGPU frees unified RAM for the Ollama LLM. float16
    is only used on CUDA — on CPU PyTorch lacks fast/complete half-precision
    kernels, so float32 is both faster and safer there.
    """
    device = settings.EMBEDDING_DEVICE or settings.DEVICE
    torch_dtype = "float16" if device == "cuda" else "float32"
    return SentenceTransformer(
        active_model_name(),
        device=device,
        trust_remote_code=get_profile()["trust_remote_code"],
        model_kwargs={"torch_dtype": torch_dtype},
    )


def _preprocess(texts: List[str], prefix: str, word_segment: bool) -> List[str]:
    out: List[str] = []
    for t in texts:
        if word_segment:
            t = underthesea.word_tokenize(t, format="text")
        out.append(prefix + t if prefix else t)
    return out


def encode_documents(texts: List[str]) -> np.ndarray:
    """Encode passages (menu/docs) with the active model's passage-side profile."""
    p = get_profile()
    return get_sentence_transformer().encode(
        _preprocess(texts, p["passage_prefix"], p["word_segment"]),
        convert_to_numpy=True,
        normalize_embeddings=p["normalize"],
    )


def encode_queries(texts: List[str]) -> np.ndarray:
    """Encode queries/utterances with the active model's query-side profile.

    Shared by FAISS search, the semantic router, and centroid building so every
    query-time vector is produced identically to the others (and comparable to the
    indexed documents).
    """
    p = get_profile()
    return get_sentence_transformer().encode(
        _preprocess(texts, p["query_prefix"], p["word_segment"]),
        convert_to_numpy=True,
        normalize_embeddings=p["normalize"],
    )


class SharedEmbeddings(Embeddings):
    """LangChain Embeddings adapter over the shared SentenceTransformer singleton.

    Routes document/query encoding through the model-aware helpers above so the
    correct preprocessing (prefixes / word-seg / normalization) is applied for
    whichever EMBEDDING_MODEL is active.
    """

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return encode_documents(texts).tolist()

    def embed_query(self, text: str) -> List[float]:
        return encode_queries([text])[0].tolist()


def get_embedding_model() -> Embeddings:
    return SharedEmbeddings()
