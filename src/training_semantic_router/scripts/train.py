#!/usr/bin/env python3
"""Train the text-only intent classifier on corpus_v2.

Usage:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/train.py
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/train.py --epochs 80 --lr 5e-4

Two things differ from the previous version, both of which were producing inflated numbers:

* The split groups by utterance instead of by row. The old corpus emitted 4-5 context
  copies of every utterance and split by row, so 427 of 427 validation rows shared their
  utterance with the training set and validation accuracy measured memorisation. corpus_v2
  has no duplicates, but grouping stays: it makes the failure impossible to reintroduce.
* No context features and no StandardScaler. See model.py for the measurement.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import unicodedata
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from dotenv import load_dotenv
from sklearn.model_selection import GroupShuffleSplit

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.training_semantic_router.classifier.model import (
    IntentClassifier,
    INTENT_LABELS,
    get_label_encoder,
    save_label_encoder,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAVED_DIR = Path(__file__).resolve().parent.parent / "classifier" / "saved_v2"


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s.lower().strip().rstrip(".,!?"))


def _precompute_embeddings(utterances: list[str], batch_size: int = 64) -> np.ndarray:
    """Encode all utterances once via the frozen SentenceTransformer."""
    import underthesea
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("CLASSIFIER_EMBEDDING_MODEL", "bkai-foundation-models/vietnamese-bi-encoder")
    device = os.getenv("EMBEDDING_DEVICE") or os.getenv("DEVICE") or "cpu"
    logger.info("Loading embedding model %s on %s ...", model_name, device)
    model = SentenceTransformer(model_name, device=device, trust_remote_code=True)

    segmented = [underthesea.word_tokenize(u, format="text") for u in utterances]
    logger.info("Encoding %d utterances (batch_size=%d) ...", len(segmented), batch_size)
    embeddings = model.encode(
        segmented,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    logger.info("Embeddings shape: %s", embeddings.shape)
    return embeddings.astype(np.float32)


def _build_dataset(data_path: Path, val_split: float = 0.2, seed: int = 42):
    with open(data_path, "r", encoding="utf-8") as f:
        records = json.load(f)
    logger.info("Loaded %d records from %s", len(records), data_path)

    utterances = [r["utterance"] for r in records]
    label_encoder = get_label_encoder()
    y = np.array([label_encoder[r["intent"]] for r in records], dtype=np.int64)
    groups = np.array([_norm(u) for u in utterances])

    X = _precompute_embeddings(utterances)

    splitter = GroupShuffleSplit(n_splits=1, test_size=val_split, random_state=seed)
    train_idx, val_idx = next(splitter.split(X, y, groups))

    overlap = set(groups[train_idx]) & set(groups[val_idx])
    if overlap:
        raise RuntimeError(f"Group split leaked {len(overlap)} utterances across the split")

    logger.info("Train: %d  Val: %d  (0 shared utterances)", len(train_idx), len(val_idx))
    return (X[train_idx], y[train_idx]), (X[val_idx], y[val_idx])


def _compute_class_weights(y: np.ndarray, num_classes: int) -> np.ndarray:
    from collections import Counter

    counts = Counter(y.tolist())
    total = len(y)
    weights = np.ones(num_classes, dtype=np.float32)
    for c in range(num_classes):
        if counts.get(c, 0) > 0:
            weights[c] = total / (num_classes * counts[c])
    logger.info("Class weights: %s", {INTENT_LABELS[i]: round(float(w), 3) for i, w in enumerate(weights)})
    return weights


def _run_epoch(model, loader, criterion, device, optimizer=None) -> tuple[float, float]:
    training = optimizer is not None
    model.train() if training else model.eval()
    total_loss = correct = total = 0

    with torch.set_grad_enabled(training):
        for batch_x, batch_y in loader:
            x, y = batch_x.to(device), batch_y.to(device)
            if training:
                optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            if training:
                loss.backward()
                optimizer.step()
            total_loss += loss.item() * x.size(0)
            correct += (logits.argmax(dim=1) == y).sum().item()
            total += x.size(0)

    return total_loss / total, correct / total


class TensorDataset(torch.utils.data.Dataset):
    def __init__(self, x: np.ndarray, y: np.ndarray):
        self.x = torch.from_numpy(x)
        self.y = torch.from_numpy(y)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.x[idx], self.y[idx]


def main():
    parser = argparse.ArgumentParser(description="Train text-only intent classifier")
    parser.add_argument("--data", default=str(DATA_DIR / "corpus_v2.json"))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-output", default=str(SAVED_DIR / "model.pt"))
    parser.add_argument("--label-output", default=str(SAVED_DIR / "label_encoder.json"))
    parser.add_argument("--no-cuda", action="store_true")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu")
    logger.info("Device: %s", device)

    data_path = Path(args.data)
    if not data_path.exists():
        logger.error("Data file not found: %s", data_path)
        sys.exit(1)

    (X_train, y_train), (X_val, y_val) = _build_dataset(
        data_path, val_split=args.val_split, seed=args.seed,
    )

    class_weights = _compute_class_weights(y_train, len(INTENT_LABELS))
    criterion = nn.CrossEntropyLoss(weight=torch.from_numpy(class_weights).to(device))

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    model = IntentClassifier().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    train_loader = torch.utils.data.DataLoader(
        TensorDataset(X_train, y_train), batch_size=args.batch_size, shuffle=True)
    val_loader = torch.utils.data.DataLoader(
        TensorDataset(X_val, y_val), batch_size=args.batch_size * 2, shuffle=False)

    best_val_acc = 0.0
    best_state = None
    patience_counter = 0

    logger.info("Starting training (%d epochs, patience=%d) ...", args.epochs, args.patience)
    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = _run_epoch(model, train_loader, criterion, device, optimizer)
        val_loss, val_acc = _run_epoch(model, val_loader, criterion, device)

        logger.info(
            "Epoch %3d/%3d | train loss: %.4f  acc: %.2f%% | val loss: %.4f  acc: %.2f%%",
            epoch, args.epochs, train_loss, train_acc * 100, val_loss, val_acc * 100,
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                logger.info("Early stopping at epoch %d", epoch)
                break

    if best_state is None:
        logger.warning("No improvement, saving last state")
        best_state = model.state_dict()

    model.load_state_dict(best_state)
    logger.info("Best val accuracy: %.2f%% (held-out utterances, no leakage)", best_val_acc * 100)

    model.save(Path(args.model_output))
    save_label_encoder(Path(args.label_output))
    logger.info("Done.")


if __name__ == "__main__":
    main()
