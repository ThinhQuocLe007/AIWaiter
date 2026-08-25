"""Evaluate the trained router on the full synthetic dataset."""

from __future__ import annotations

from sklearn.metrics import classification_report

from src.agent_brain.warehouse.router.data import build_dataset
from src.agent_brain.warehouse.router.model import MLPRouter


def main() -> None:
    router = MLPRouter.load()
    rows = build_dataset()
    texts = [r["text"] for r in rows]
    labels = [r["intent"] for r in rows]

    preds = [router.classify(t)[0].value for t in texts]

    print("=== Router evaluation (full synthetic set) ===")
    print(classification_report(labels, preds, zero_division=0))


if __name__ == "__main__":
    main()
