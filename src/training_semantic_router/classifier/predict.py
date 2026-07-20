from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import torch
from dotenv import load_dotenv

load_dotenv()

from src.training_semantic_router.classifier.features import extract_context_features
from src.training_semantic_router.classifier.model import (
    EMBEDDING_DIM,
    IntentClassifier,
    INTENT_LABELS,
    load_label_encoder,
)

logger = logging.getLogger(__name__)

_MODULE_DIR = Path(__file__).resolve().parent
_DEFAULT_MODEL_PATH = _MODULE_DIR / "saved" / "model.pt"
_DEFAULT_LABEL_PATH = _MODULE_DIR / "saved" / "label_encoder.json"
_DEFAULT_SCALER_PATH = _MODULE_DIR / "saved" / "scaler.npz"

_model: IntentClassifier | None = None
_label_encoder: dict[str, int] | None = None
_scaler_mean: np.ndarray | None = None
_scaler_scale: np.ndarray | None = None
_embed_fn: Any = None


def _get_embed_fn():
    global _embed_fn
    if _embed_fn is None:
        from sentence_transformers import SentenceTransformer

        # Deliberately NOT settings.EMBEDDING_MODEL: that one selects the *retriever's*
        # model (AITeamVN, 1024-dim) and the saved classifier weights are dimension-locked
        # to whatever they were trained on -- bkai, 768-dim. Reading the shared variable
        # would load a 1024-dim encoder into a 778-input network and blow up on the first
        # utterance, which is now the agent's entry point (graph.py: START -> classifier_router).
        # Retrain via src/training_semantic_router/scripts/train.py before changing this.
        model_name = os.getenv(
            "CLASSIFIER_EMBEDDING_MODEL", "bkai-foundation-models/vietnamese-bi-encoder"
        )
        # Same precedence as the retriever's get_embedding_model(): EMBEDDING_DEVICE wins so
        # the encoders can be pushed off the iGPU independently of the LLM, else the global
        # DEVICE. float16 only on CUDA -- PyTorch's CPU half-precision kernels are slower.
        device = os.getenv("EMBEDDING_DEVICE") or os.getenv("DEVICE") or "cpu"
        torch_dtype = "float16" if device == "cuda" else "float32"
        _embed_fn = SentenceTransformer(
            model_name,
            device=device,
            trust_remote_code=True,
            model_kwargs={"torch_dtype": torch_dtype},
        )
    return _embed_fn


def _encode(utterance: str) -> np.ndarray:
    import underthesea

    model = _get_embed_fn()
    segmented = underthesea.word_tokenize(utterance, format="text")
    embedding = model.encode([segmented], convert_to_numpy=True, normalize_embeddings=True)
    return embedding[0].astype(np.float32)


def _load_artifacts(
    model_path: Path | None = None,
    label_path: Path | None = None,
    scaler_path: Path | None = None,
) -> None:
    global _model, _label_encoder, _scaler_mean, _scaler_scale

    mp = Path(model_path) if model_path else _DEFAULT_MODEL_PATH
    lp = Path(label_path) if label_path else _DEFAULT_LABEL_PATH
    sp = Path(scaler_path) if scaler_path else _DEFAULT_SCALER_PATH

    if _label_encoder is None and lp.exists():
        _label_encoder = load_label_encoder(lp)

    if _model is None and mp.exists():
        _model = IntentClassifier()
        _model.load(mp)
        _model.eval()

    if _scaler_mean is None and sp.exists():
        data = np.load(sp)
        _scaler_mean = data["mean"]
        _scaler_scale = data["scale"]


def classify(
    utterance: str,
    state: dict | None = None,
    *,
    embedding: np.ndarray | None = None,
    model_path: Path | None = None,
    label_path: Path | None = None,
    scaler_path: Path | None = None,
) -> dict[str, Any]:
    _load_artifacts(model_path, label_path, scaler_path)

    if _model is None:
        raise FileNotFoundError(f"Model not found at {model_path or _DEFAULT_MODEL_PATH}")

    if embedding is not None:
        emb = embedding.astype(np.float32)
    else:
        emb = _encode(utterance)

    if emb.shape[0] != EMBEDDING_DIM:
        raise ValueError(
            f"Encoder produced {emb.shape[0]}-dim embeddings but the trained classifier "
            f"expects {EMBEDDING_DIM}. CLASSIFIER_EMBEDDING_MODEL is pointing at a model "
            f"the checkpoint was not trained on -- retrain before switching encoders."
        )

    context_features = extract_context_features(state, utterance)

    if _scaler_mean is not None and _scaler_scale is not None:
        context_features = (context_features - _scaler_mean) / np.maximum(_scaler_scale, 1e-8)

    combined = np.concatenate([emb, context_features]).astype(np.float32)
    tensor = torch.from_numpy(combined).unsqueeze(0)

    probs = _model.predict_proba(tensor)[0]
    predicted_idx = int(np.argmax(probs))
    confidence = float(probs[predicted_idx])

    label_map = _label_encoder or {i: l for i, l in enumerate(INTENT_LABELS)}
    idx_to_label = {v: k for k, v in label_map.items()}
    intent = idx_to_label.get(predicted_idx, INTENT_LABELS[predicted_idx])

    all_probs = {
        idx_to_label.get(i, INTENT_LABELS[i]): float(probs[i])
        for i in range(len(probs))
    }

    return {
        "intent": intent,
        "confidence": confidence,
        "all_probs": all_probs,
    }
