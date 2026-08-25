"""Trained MLP router — loads weights and classifies an utterance by its embedding.

The classifier is a small sklearn `MLPClassifier` trained in `train.py` and serialized to
`storage/router/mlp_router.joblib` (gitignored). `classify` returns the top intent and its
softmax probability, which `mlp_router_node` uses as a calibrated confidence.

Embeddings are fetched through the `rag.embed` module attribute so tests can stub it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from src.agent_brain.warehouse.rag import embed as _embed_mod
from src.agent_brain.warehouse.paths import storage_path
from src.agent_brain.warehouse.types import Intent


ARTIFACT = storage_path() / "router" / "mlp_router.joblib"


class RouterNotTrained(RuntimeError):
    """Raised when the router weights are missing — train first (`make train-router`)."""


class MLPRouter:
    def __init__(self, clf, label_encoder) -> None:
        self.clf = clf
        self.le = label_encoder

    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> "MLPRouter":
        p = Path(path) if path else ARTIFACT
        if not p.exists():
            raise RouterNotTrained(
                f"No trained router at {p}. Run `make train-router` "
                "(or `uv run python -m src.agent_brain.warehouse.router.train`)."
            )
        import joblib

        blob = joblib.load(p)
        return cls(blob["clf"], blob["le"])

    def probabilities(self, text: str) -> dict[Intent, float]:
        x = np.asarray(_embed_mod.embed([text]), dtype="float32")
        probs = self.clf.predict_proba(x)[0]
        return {Intent(name): float(p) for name, p in zip(self.le.classes_, probs)}

    def classify(self, text: str) -> tuple[Intent, float]:
        probs = self.probabilities(text)
        intent = max(probs, key=probs.get)
        return intent, probs[intent]
