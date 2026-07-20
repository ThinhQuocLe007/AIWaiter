from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

INTENT_LABELS = ["ORDER", "SEARCH", "PAYMENT", "CHAT"]
EMBEDDING_DIM = 768
CONTEXT_DIM = 10
INPUT_DIM = EMBEDDING_DIM + CONTEXT_DIM


class IntentClassifier(nn.Module):
    def __init__(
        self,
        input_dim: int = INPUT_DIM,
        hidden_dims: tuple[int, ...] = (256, 64),
        num_classes: int = 4,
        dropout: float = 0.2,
    ):
        super().__init__()
        layers = []
        prev = input_dim
        for h in hidden_dims:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev = h
        layers.append(nn.Linear(prev, num_classes))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

    def predict_proba(self, x: torch.Tensor) -> np.ndarray:
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            probs = torch.softmax(logits, dim=-1)
            return probs.cpu().numpy()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.state_dict(), path)
        logger.info("Model saved to %s", path)

    def load(self, path: Path) -> None:
        state = torch.load(path, map_location="cpu", weights_only=True)
        self.load_state_dict(state)
        self.eval()
        logger.info("Model loaded from %s", path)


def get_label_encoder() -> dict[str, int]:
    return {label: i for i, label in enumerate(INTENT_LABELS)}


def save_label_encoder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoder = get_label_encoder()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(encoder, f, ensure_ascii=False, indent=2)
    logger.info("Label encoder saved to %s", path)


def load_label_encoder(path: Path) -> dict[str, int]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
