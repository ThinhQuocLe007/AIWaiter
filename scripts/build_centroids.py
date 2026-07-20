#!/usr/bin/env python3
"""Build centroid .npz from utterances.json for the semantic router.

Encodes utterances with the ACTIVE embedding model (settings.EMBEDDING_MODEL /
.env) using the exact same query-side preprocessing as the router (via
encode_queries), so the centroids stay consistent with query-time vectors.
Pass --model to override the active model for a single run.
"""
import json
import argparse
import os
import sys
import numpy as np
from pathlib import Path


# ---- Paths (relative to this script's location) ----
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PACKAGE_RESOURCES = (
    PROJECT_ROOT
    / "src/agent_brain/agent/resources"
)

DEFAULT_UTTERANCES = PACKAGE_RESOURCES / "few_shots" / "utterances.json"
DEFAULT_CENTROIDS_DIR = PACKAGE_RESOURCES / "centroids"


def build_centroids(
    utterances_path: Path,
    output_dir: Path,
    encode_queries,
    model_name: str,
) -> None:
    from sklearn.cluster import KMeans

    print(f"Loading utterances from: {utterances_path}")
    with open(utterances_path, "r", encoding="utf-8") as f:
        routes = json.load(f)

    total = sum(len(u) for u in routes.values())
    print(f"Loaded {len(routes)} intents, {total} total utterances:")
    for intent, utts in routes.items():
        print(f"  {intent:8s}: {len(utts):3d} utterances")

    print(f"\nEmbedding model (active): {model_name}")

    centroids: dict[str, np.ndarray] = {}
    print("\nComputing multi-centroids (k-means per class):")
    for intent, utterances in routes.items():
        n = len(utterances)
        k = max(1, min(3, n // 10))
        embeddings = encode_queries(utterances)

        if k == 1:
            sub_centroids = [np.mean(embeddings, axis=0)]
        else:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)
            sub_centroids = []
            for i in range(k):
                cluster_embeddings = embeddings[labels == i]
                sub_centroids.append(np.mean(cluster_embeddings, axis=0))

        for i, cent in enumerate(sub_centroids):
            centroids[f"{intent}_{i}"] = cent
        print(f"  {intent:8s}: {n:3d} utterances → {k} sub-centroids")

    # Save centroids
    output_dir.mkdir(parents=True, exist_ok=True)
    npz_path = output_dir / "centroids.npz"
    np.savez(npz_path, **centroids)
    size_kb = npz_path.stat().st_size / 1024
    print(f"\nCentroids saved to: {npz_path} ({size_kb:.1f} KB)")

    # Stamp the model name so the router can detect a stale/mismatched centroid set.
    from src.agent_brain.services.retriever.indices.fingerprint import write_fingerprint
    write_fingerprint(output_dir)
    print(f"Stamped embedding model fingerprint: {model_name}")

    # Quick verification: load back and check
    print("\nVerifying — loading centroids.npz back ...")
    data = np.load(str(npz_path))
    loaded = {k: data[k] for k in data.files}
    for key, centroid in loaded.items():
        assert np.allclose(centroid, centroids[key], rtol=1e-6), \
            f"Mismatch in {key} centroid!"
    print(f"  All {len(loaded)} sub-centroids verified ✓")
    print("\nDone.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build centroid .npz from utterances.json for the semantic router"
    )
    parser.add_argument(
        "--utterances",
        type=Path,
        default=DEFAULT_UTTERANCES,
        help="Path to utterances.json (default: resources/few_shots/utterances.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_CENTROIDS_DIR,
        help="Directory to write centroids.npz",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the active embedding model for this run "
             "(default: settings.EMBEDDING_MODEL / .env)",
    )
    args = parser.parse_args(argv)

    if not args.utterances.exists():
        print(f"ERROR: utterances.json not found at {args.utterances}", file=sys.stderr)
        sys.exit(1)

    # Make repo root importable so scripts.build_centroids (this file) is reachable
    # when called as a module from setup.py. The src/ tree is importable by default from
    # repo root, so no extra path shim is needed for the src.agent_brain.* imports.
    # --model is applied to the environment BEFORE settings is first imported so it
    # overrides .env. (When invoked from setup.py settings is already loaded, so that
    # path uses setup's EMBEDDING_MODEL rather than --model.)
    sys.path.insert(0, str(PROJECT_ROOT))
    if args.model:
        os.environ["EMBEDDING_MODEL"] = args.model
    from dotenv import load_dotenv
    load_dotenv()  # does not override already-set env vars
    from src.agent_brain.services.retriever.indices.embeddings import (
        encode_queries,
        active_model_name,
    )

    build_centroids(
        utterances_path=args.utterances,
        output_dir=args.output_dir,
        encode_queries=encode_queries,
        model_name=active_model_name(),
    )


if __name__ == "__main__":
    main()
