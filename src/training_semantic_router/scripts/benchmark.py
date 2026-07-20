#!/usr/bin/env python3
"""Latency benchmark: trained classifier vs semantic_router_node.

Usage:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/benchmark.py
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/benchmark.py --iterations 500 --warmup 30
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.training_semantic_router.classifier.features import extract_context_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark")

SAVED_DIR = Path(__file__).resolve().parent.parent / "classifier" / "saved"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

BENCH_SAMPLES = [
    "Cho em 2 phần Ốc Hương Xốt Trứng Muối ạ",
    "Dạ cho em hỏi quán mình có món chay không ạ",
    "Tính tiền đi em",
    "xin chào em",
    "cho anh thêm 1 bia tiger nữa",
    "món này có cay không em",
    "cho xin hóa đơn thanh toán",
    "cảm ơn em nhiều nha",
    "lấy 1 lẩu thái với 3 chai bia",
    "quán mở cửa tới mấy giờ vậy em",
    "quẹt thẻ được hông em",
    "đồ ăn ở đây ngon quá trời",
    "đúng rồi chốt đơn đi em",
    "có món nào bán chạy nhất không",
    "thanh toán chuyển khoản được không",
    "trời hôm nay mưa to thật",
    "bỏ món mực chiên xù ra khỏi đơn",
    "ốc hương giá bao nhiêu vậy",
    "bill đi em",
    "ok em",
]


def _load_centroids():
    from src.agent_brain.agent.nodes.semantic_router_node import SemanticRouterNode

    router = SemanticRouterNode()
    return router.route_centroids


def _load_classifier():
    import torch

    from src.training_semantic_router.classifier.model import IntentClassifier, load_label_encoder

    model = IntentClassifier()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.load(SAVED_DIR / "model.pt")
    model.to(device)
    model.eval()

    label_encoder = load_label_encoder(SAVED_DIR / "label_encoder.json")
    idx_to_label = {v: k for k, v in label_encoder.items()}

    scaler_data = np.load(SAVED_DIR / "scaler.npz")
    scaler_mean = scaler_data["mean"]
    scaler_scale = scaler_data["scale"]

    return model, idx_to_label, scaler_mean, scaler_scale, device


def _precompute_embeddings(samples: list[str]) -> list[np.ndarray]:
    from underthesea import word_tokenize
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("EMBEDDING_MODEL", "bkai-foundation-models/vietnamese-bi-encoder")
    model = SentenceTransformer(model_name, device="cpu", trust_remote_code=True)
    segmented = [word_tokenize(s, format="text") for s in samples]
    embeddings = model.encode(segmented, convert_to_numpy=True, normalize_embeddings=True)
    return [embeddings[i].astype(np.float32) for i in range(len(samples))]


def _bench_embedding_only(samples: list[str], iterations: int) -> dict[str, float]:
    from underthesea import word_tokenize
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("EMBEDDING_MODEL", "bkai-foundation-models/vietnamese-bi-encoder")
    model = SentenceTransformer(model_name, device="cpu", trust_remote_code=True)

    latencies: list[float] = []
    for i in range(iterations):
        utterance = samples[i % len(samples)]
        t0 = time.perf_counter()
        segmented = word_tokenize(utterance, format="text")
        model.encode([segmented], convert_to_numpy=True, normalize_embeddings=True)
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)
    return _compute_stats(latencies)


def _bench_centroid_routing(
    centroids: dict[str, np.ndarray],
    embeddings: list[np.ndarray],
    iterations: int,
) -> dict[str, float]:
    latencies: list[float] = []
    for i in range(iterations):
        query_vec = np.expand_dims(embeddings[i % len(embeddings)], axis=0)
        t0 = time.perf_counter()
        max_sim = -1.0
        for route_name, centroid in centroids.items():
            if centroid.ndim == 1:
                centroid = np.expand_dims(centroid, axis=0)
            sims = cosine_similarity(query_vec, centroid)[0]
            best = float(np.max(sims))
            if best > max_sim:
                max_sim = best
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)
    return _compute_stats(latencies)


def _bench_mlp_routing(
    model,
    scaler_mean: np.ndarray,
    scaler_scale: np.ndarray,
    samples: list[str],
    embeddings: list[np.ndarray],
    iterations: int,
    device: Any,
) -> dict[str, float]:
    import torch

    latencies: list[float] = []
    state = {
        "order_stage": "IDLE", "has_cart": False, "cart_size": 0,
        "has_search_context": False, "search_context_size": 0,
    }

    for i in range(iterations):
        idx = i % len(embeddings)
        utterance = samples[idx]
        emb = embeddings[idx]
        ctx = extract_context_features(state, utterance)
        ctx_scaled = (ctx - scaler_mean) / np.maximum(scaler_scale, 1e-8)
        combined = np.concatenate([emb, ctx_scaled]).astype(np.float32)

        t0 = time.perf_counter()
        tensor = torch.from_numpy(combined).unsqueeze(0).to(device)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.softmax(logits, dim=-1)
            _ = int(probs.argmax(dim=1).item())
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)

    return _compute_stats(latencies)


def _compute_stats(latencies: list[float]) -> dict[str, float]:
    arr = np.array(latencies) * 1000
    return {
        "count": len(arr),
        "mean_ms": float(np.mean(arr)),
        "std_ms": float(np.std(arr)),
        "min_ms": float(np.min(arr)),
        "max_ms": float(np.max(arr)),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
    }


def main():
    parser = argparse.ArgumentParser(description="Latency benchmark: classifier vs semantic router")
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--warmup", type=int, default=30)
    args = parser.parse_args()

    logger.info("Loading centroids ...")
    centroids = _load_centroids()
    logger.info("  %d intent centroid groups loaded", len(centroids))

    logger.info("Loading trained classifier ...")
    cls_model, _, cls_scaler_mean, cls_scaler_scale, cls_device = _load_classifier()

    logger.info("Precomputing %d embeddings (CPU) ...", len(BENCH_SAMPLES))
    all_embeddings = _precompute_embeddings(BENCH_SAMPLES)

    logger.info("Warming up (%d iterations) ...", args.warmup)
    for _ in range(args.warmup):
        _bench_centroid_routing(centroids, all_embeddings, 1)
        _bench_mlp_routing(cls_model, cls_scaler_mean, cls_scaler_scale, BENCH_SAMPLES, all_embeddings, 1, cls_device)

    logger.info("Benchmarking embedding only (%d iterations) ...", args.iterations)
    emb_stats = _bench_embedding_only(BENCH_SAMPLES, args.iterations)

    logger.info("Benchmarking centroid routing (%d iterations) ...", args.iterations)
    centroid_stats = _bench_centroid_routing(centroids, all_embeddings, args.iterations)

    logger.info("Benchmarking MLP routing (%d iterations) ...", args.iterations)
    mlp_stats = _bench_mlp_routing(cls_model, cls_scaler_mean, cls_scaler_scale, BENCH_SAMPLES, all_embeddings, args.iterations, cls_device)

    sr_total_p50 = emb_stats["p50_ms"] + centroid_stats["p50_ms"]
    cls_total_p50 = emb_stats["p50_ms"] + mlp_stats["p50_ms"]
    sr_total_p95 = emb_stats["p95_ms"] + centroid_stats["p95_ms"]
    cls_total_p95 = emb_stats["p95_ms"] + mlp_stats["p95_ms"]

    print(f"\n{'=' * 80}")
    print(f"  Latency Benchmark ({args.iterations} iterations) — Component Breakdown")
    print(f"{'=' * 80}")
    print(f"\n{'Component':<28} {'p50 (ms)':>12} {'p95 (ms)':>12} {'p99 (ms)':>12} {'mean (ms)':>12}")
    print("-" * 80)
    print(f"{'Embedding (Vietnamese-BE, CPU)':<28} {emb_stats['p50_ms']:>12.3f} {emb_stats['p95_ms']:>12.3f} {emb_stats['p99_ms']:>12.3f} {emb_stats['mean_ms']:>12.3f}")
    print(f"{'Centroid cosine similarity':<28} {centroid_stats['p50_ms']:>12.3f} {centroid_stats['p95_ms']:>12.3f} {centroid_stats['p99_ms']:>12.3f} {centroid_stats['mean_ms']:>12.3f}")
    print(f"{'MLP forward (778→256→64→4)':<28} {mlp_stats['p50_ms']:>12.3f} {mlp_stats['p95_ms']:>12.3f} {mlp_stats['p99_ms']:>12.3f} {mlp_stats['mean_ms']:>12.3f}")

    print(f"\n{'=' * 80}")
    print(f"  Total Latency (Embedding + Routing Logic)")
    print(f"{'=' * 80}")
    print(f"\n{'Method':<30} {'p50 (ms)':>15} {'p95 (ms)':>15}")
    print("-" * 65)
    print(f"{'Semantic Router (centroid)':<30} {sr_total_p50:>15.3f} {sr_total_p95:>15.3f}")
    print(f"{'Trained Classifier (MLP)':<30} {cls_total_p50:>15.3f} {cls_total_p95:>15.3f}")

    ratio_p50 = cls_total_p50 / max(sr_total_p50, 0.001)
    ratio_p95 = cls_total_p95 / max(sr_total_p95, 0.001)
    print(f"\n  Classifier / Semantic Router ratio:")
    print(f"    p50: {ratio_p50:.2f}x   p95: {ratio_p95:.2f}x")
    print(f"    Routing-only: centroid={centroid_stats['p50_ms']:.3f}ms vs MLP={mlp_stats['p50_ms']:.3f}ms")

    print(f"\n  Gate G4: p95 < 20ms?   {'PASS' if cls_total_p95 < 20 else 'FAIL'} ({cls_total_p95:.2f} ms)")
    print(f"  Gate G4: < 2x semantic? {'PASS' if ratio_p95 < 2 else 'FAIL'} ({ratio_p95:.1f}x)")
    print(f"{'=' * 80}")

    output = {
        "iterations": args.iterations,
        "embedding": {k: round(v, 4) for k, v in emb_stats.items()},
        "centroid_routing": {k: round(v, 4) for k, v in centroid_stats.items()},
        "mlp_routing": {k: round(v, 4) for k, v in mlp_stats.items()},
        "total_semantic_p50_ms": round(sr_total_p50, 4),
        "total_classifier_p50_ms": round(cls_total_p50, 4),
        "total_semantic_p95_ms": round(sr_total_p95, 4),
        "total_classifier_p95_ms": round(cls_total_p95, 4),
        "ratio_p50": round(ratio_p50, 4),
        "ratio_p95": round(ratio_p95, 4),
        "gate_p95_under_20ms": cls_total_p95 < 20,
        "gate_under_2x_semantic": ratio_p95 < 2,
    }
    output_path = DATA_DIR / "benchmark_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info("Benchmark report saved to %s", output_path)


if __name__ == "__main__":
    main()
