#!/usr/bin/env python3
"""Train the intent classifier.

Usage:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/train.py
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/train.py --epochs 50 --lr 0.001
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/train.py --batch-size 128 --patience 15
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.training_semantic_router.classifier.features import extract_context_features, FEATURE_DIM
from src.training_semantic_router.classifier.model import (
    IntentClassifier,
    EMBEDDING_DIM,
    INPUT_DIM,
    INTENT_LABELS,
    get_label_encoder,
    save_label_encoder,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAVED_DIR = Path(__file__).resolve().parent.parent / "classifier" / "saved"


def _precompute_embeddings(utterances: list[str], batch_size: int = 64) -> np.ndarray:
    """Encode all utterances once via frozen SentenceTransformer."""
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


def _extract_features(records: list[dict]) -> np.ndarray:
    features = np.zeros((len(records), FEATURE_DIM), dtype=np.float32)
    for i, r in enumerate(records):
        features[i] = extract_context_features(r, r.get("utterance", ""))
    return features


def _build_dataset(
    data_path: Path,
    val_split: float = 0.2,
    seed: int = 42,
):
    with open(data_path, "r", encoding="utf-8") as f:
        records = json.load(f)
    logger.info("Loaded %d records from %s", len(records), data_path)

    utterances = [r["utterance"] for r in records]
    intents = [r["intent"] for r in records]

    label_encoder = get_label_encoder()
    y = np.array([label_encoder[i] for i in intents], dtype=np.int64)

    X_emb = _precompute_embeddings(utterances)
    X_ctx = _extract_features(records)

    X_train_emb, X_val_emb, X_train_ctx, X_val_ctx, y_train, y_val = train_test_split(
        X_emb, X_ctx, y, test_size=val_split, random_state=seed, stratify=y,
    )

    scaler = StandardScaler()
    X_train_ctx = scaler.fit_transform(X_train_ctx).astype(np.float32)
    X_val_ctx = scaler.transform(X_val_ctx).astype(np.float32)

    logger.info("Train: %d  Val: %d", len(y_train), len(y_val))
    return (X_train_emb, X_train_ctx, y_train), (X_val_emb, X_val_ctx, y_val), scaler


def _compute_class_weights(y: np.ndarray, num_classes: int) -> np.ndarray:
    from collections import Counter

    counts = Counter(y)
    total = len(y)
    weights = np.ones(num_classes, dtype=np.float32)
    for c in range(num_classes):
        if counts.get(c, 0) > 0:
            weights[c] = total / (num_classes * counts[c])
    logger.info("Class weights: %s", dict(enumerate(weights)))
    return weights


def _train_epoch(
    model: nn.Module,
    loader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float]:
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch_emb, batch_ctx, batch_y in loader:
        x = torch.cat([batch_emb, batch_ctx], dim=1).to(device)
        y = batch_y.to(device)

        optimizer.zero_grad()
        logits = model(x)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * x.size(0)
        preds = logits.argmax(dim=1)
        correct += (preds == y).sum().item()
        total += x.size(0)

    return total_loss / total, correct / total


@torch.no_grad()
def _eval_epoch(
    model: nn.Module,
    loader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch_emb, batch_ctx, batch_y in loader:
        x = torch.cat([batch_emb, batch_ctx], dim=1).to(device)
        y = batch_y.to(device)

        logits = model(x)
        loss = criterion(logits, y)

        total_loss += loss.item() * x.size(0)
        preds = logits.argmax(dim=1)
        correct += (preds == y).sum().item()
        total += x.size(0)

    return total_loss / total, correct / total


class TensorDataset(torch.utils.data.Dataset):
    def __init__(self, emb: np.ndarray, ctx: np.ndarray, y: np.ndarray):
        self.emb = torch.from_numpy(emb)
        self.ctx = torch.from_numpy(ctx)
        self.y = torch.from_numpy(y)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.emb[idx], self.ctx[idx], self.y[idx]


def main():
    parser = argparse.ArgumentParser(description="Train intent classifier")
    parser.add_argument("--data", default=str(DATA_DIR / "synthetic_augmented.json"))
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-output", default=str(SAVED_DIR / "model.pt"))
    parser.add_argument("--label-output", default=str(SAVED_DIR / "label_encoder.json"))
    parser.add_argument("--scaler-output", default=str(SAVED_DIR / "scaler.npz"))
    parser.add_argument("--no-cuda", action="store_true")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu")
    logger.info("Device: %s", device)

    data_path = Path(args.data)
    if not data_path.exists():
        logger.error("Data file not found: %s", data_path)
        sys.exit(1)

    (X_train_emb, X_train_ctx, y_train), (X_val_emb, X_val_ctx, y_val), scaler = _build_dataset(
        data_path, val_split=args.val_split, seed=args.seed,
    )

    class_weights = _compute_class_weights(y_train, len(INTENT_LABELS))
    criterion = nn.CrossEntropyLoss(weight=torch.from_numpy(class_weights).to(device))

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    model = IntentClassifier().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    train_dataset = TensorDataset(X_train_emb, X_train_ctx, y_train)
    val_dataset = TensorDataset(X_val_emb, X_val_ctx, y_val)

    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=args.batch_size * 2, shuffle=False)

    best_val_acc = 0.0
    best_state = None
    patience_counter = 0

    logger.info("Starting training (%d epochs, patience=%d) ...", args.epochs, args.patience)
    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = _train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc = _eval_epoch(model, val_loader, criterion, device)

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
    logger.info("Best val accuracy: %.2f%%", best_val_acc * 100)

    model_output = Path(args.model_output)
    model.save(model_output)

    label_output = Path(args.label_output)
    save_label_encoder(label_output)

    scaler_output = Path(args.scaler_output)
    scaler_output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        scaler_output,
        mean=scaler.mean_.astype(np.float32),
        scale=scaler.scale_.astype(np.float32),
    )
    logger.info("Scaler saved to %s", scaler_output)
    logger.info("Done.")


if __name__ == "__main__":
    main()
