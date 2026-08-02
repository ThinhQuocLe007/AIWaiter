from functools import lru_cache
from typing import List

import numpy as np
import underthesea
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

from src.agent_brain.config import settings

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
    the embedding model off the iGPU frees unified RAM for the Ollama LLM.

    float32 on every device, CUDA included. This encoder is not retrieval-only: since the
    classifier router replaced the centroid one, its output also feeds the intent MLP,
    which holds float32 weights and decides on small margins. The float32 pin inside
    ``training_semantic_router/classifier/predict.py`` does NOT cover this path — that
    one only runs for the offline scripts — so dropping to float16 here would silently
    feed the router half-precision vectors. Cosine ranking would tolerate fp16; the
    router is the reason we don't.
    """
    device = settings.EMBEDDING_DEVICE or settings.DEVICE
    torch_dtype = "float32"
    return SentenceTransformer(
        active_model_name(),
        device=device,
        trust_remote_code=get_profile()["trust_remote_code"],
        model_kwargs={"torch_dtype": torch_dtype},
    )


def _segment(text: str) -> str:
    """Word-segment Vietnamese text one line at a time.

    `underthesea.word_tokenize` does not treat a newline as a token boundary. Run it
    over the whole multi-line menu document and it glues the last word of one line to
    the first of the next: the template

        Tên món: Lẩu Thái
        Giá: 255000

    segments to `... Lẩu Thái_Giá : 255000 ...`, so the dish name is destroyed at index
    time while the query "cho xem lẩu thái" segments cleanly to `lẩu_thái`. The two can
    then never match: measured cosine between that query and its own document was 0.06
    with whole-text segmentation against 0.49 without it.

    Segmenting per line keeps the boundary. Note that changing this function changes how
    documents are encoded, so the FAISS index must be rebuilt; the embedding-model
    fingerprint does not catch a preprocessing change because the model name is
    unchanged.
    """
    return "\n".join(
        underthesea.word_tokenize(line, format="text") if line.strip() else line
        for line in text.split("\n")
    )


def _preprocess(texts: List[str], prefix: str, word_segment: bool) -> List[str]:
    out: List[str] = []
    for t in texts:
        if word_segment:
            t = _segment(t)
        out.append(prefix + t if prefix else t)
    return out


# Word segmentation is a per-consumer choice, not a per-model one.
#
# The profile's `word_segment` is what PhoBERT-family models were pretrained on, and the
# intent classifier and the semantic router were trained on vectors produced with it, so
# they must keep it or their weights no longer match their input.
#
# Retrieval is the opposite case. Its documents are a multi-line `Field: value` template,
# and underthesea segments that template differently from the way it segments a natural
# customer question: the indexed text of Lẩu Thái came out with the dish name split
# across two tokens while the query "cho xem lẩu thái" came out as the compound
# `lẩu_thái`, so the two could never match. Measured over the 24-query evaluation set,
# turning segmentation off for retrieval moves the dense lane from R@5 0.434 to 0.529 and
# its hit rate from 0.583 to 0.708.
#
# Both consumers still share one SentenceTransformer instance; only this step differs.
RETRIEVAL_WORD_SEGMENT = False


def encode_documents(texts: List[str], word_segment: bool | None = None) -> np.ndarray:
    """Encode passages (menu/docs) with the active model's passage-side profile.

    `word_segment` overrides the profile default; see RETRIEVAL_WORD_SEGMENT above.
    """
    p = get_profile()
    seg = p["word_segment"] if word_segment is None else word_segment
    return get_sentence_transformer().encode(
        _preprocess(texts, p["passage_prefix"], seg),
        convert_to_numpy=True,
        normalize_embeddings=p["normalize"],
    )


def encode_queries(texts: List[str], word_segment: bool | None = None) -> np.ndarray:
    """Encode queries/utterances with the active model's query-side profile.

    Shared by FAISS search, the semantic router, and centroid building. Callers that do
    not pass `word_segment` get the profile default, which is what the trained router
    and classifier weights expect.
    """
    p = get_profile()
    seg = p["word_segment"] if word_segment is None else word_segment
    return get_sentence_transformer().encode(
        _preprocess(texts, p["query_prefix"], seg),
        convert_to_numpy=True,
        normalize_embeddings=p["normalize"],
    )


class SharedEmbeddings(Embeddings):
    """LangChain Embeddings adapter over the shared SentenceTransformer singleton.

    Used by the FAISS index only, so it applies the retrieval-side segmentation setting
    on both the document and the query side. Both sides must agree, or indexed vectors
    and query vectors are not comparable.
    """

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return encode_documents(texts, word_segment=RETRIEVAL_WORD_SEGMENT).tolist()

    def embed_query(self, text: str) -> List[float]:
        return encode_queries([text], word_segment=RETRIEVAL_WORD_SEGMENT)[0].tolist()


def get_embedding_model() -> Embeddings:
    return SharedEmbeddings()
