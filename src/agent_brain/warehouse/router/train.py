"""Train the intent router MLP and save its weights.

Run: `uv run python -m src.agent_brain.warehouse.router.train`  (or `make train-router`).
Embeds the synthetic dataset, fits a small `MLPClassifier`, prints an evaluation report,
and writes `storage/router/mlp_router.joblib`.
"""

from __future__ import annotations

import joblib
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder

from src.agent_brain.warehouse.rag import embed as _embed_mod
from src.agent_brain.warehouse.router.data import build_dataset
from src.agent_brain.warehouse.router.model import ARTIFACT, MLPRouter
from src.agent_brain.warehouse.types import Intent


def train(force: bool = False) -> MLPRouter:
    if ARTIFACT.exists() and not force:
        return MLPRouter.load()

    rows = build_dataset()
    texts = [r["text"] for r in rows]
    labels = [r["intent"] for r in rows]

    X = np.asarray(_embed_mod.embed(texts), dtype="float32")
    le = LabelEncoder()
    y = le.fit_transform(labels)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.15, stratify=y, random_state=42
    )

    clf = MLPClassifier(
        hidden_layer_sizes=(256, 128),
        alpha=1e-4,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=12,
        max_iter=400,
        batch_size=64,
        random_state=42,
    )
    clf.fit(X_tr, y_tr)

    pred = clf.predict(X_te)
    target_names = [Intent(n).value for n in le.classes_]
    print("=== Router training evaluation ===")
    print(classification_report(y_te, pred, target_names=target_names, zero_division=0))
    print("confusion rows=true, cols=predicted:", le.classes_.tolist())
    print(confusion_matrix(y_te, pred))

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"clf": clf, "le": le}, ARTIFACT)
    print(f"Saved router -> {ARTIFACT}")
    return MLPRouter.load()


if __name__ == "__main__":
    train(force=True)
