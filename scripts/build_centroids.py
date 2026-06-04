#!/usr/bin/env python3
import json
import argparse
import sys
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer


# ---- Paths (relative to this script's location) ----
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PACKAGE_RESOURCES = (
    PROJECT_ROOT
    / "robot_ws/src/ai_waiter_core/ai_waiter_core/agent/resources"
)

DEFAULT_UTTERANCES = PACKAGE_RESOURCES / "few_shots" / "utterances.json"
DEFAULT_CENTROIDS_DIR = PACKAGE_RESOURCES / "centroids"
DEFAULT_MODEL = "AITeamVN/Vietnamese_Embedding"


def build_centroids(
    utterances_path: Path,
    output_dir: Path,
    model_name: str,
) -> None:
    print(f"Loading utterances from: {utterances_path}")
    with open(utterances_path, "r", encoding="utf-8") as f:
        routes = json.load(f)

    total = sum(len(u) for u in routes.values())
    print(f"Loaded {len(routes)} intents, {total} total utterances:")
    for intent, utts in routes.items():
        print(f"  {intent:8s}: {len(utts):3d} utterances")

    print(f"\nLoading embedding model: {model_name} ...")
    model = SentenceTransformer(model_name)

    centroids: dict[str, np.ndarray] = {}
    print("\nComputing centroids (np.mean per class):")
    for intent, utterances in routes.items():
        embeddings = model.encode(utterances, show_progress_bar=False)
        centroid = np.mean(embeddings, axis=0)
        centroids[intent] = centroid
        print(f"  {intent:8s}: {len(utterances):3d} utterances → centroid shape {centroid.shape}")

    # Save centroids
    output_dir.mkdir(parents=True, exist_ok=True)
    npz_path = output_dir / "centroids.npz"
    np.savez(npz_path, **centroids)
    size_kb = npz_path.stat().st_size / 1024
    print(f"\nCentroids saved to: {npz_path} ({size_kb:.1f} KB)")

    # Quick verification: load back and check
    print("\nVerifying — loading centroids.npz back ...")
    data = np.load(str(npz_path))
    loaded = {k: data[k] for k in data.files}
    for intent, centroid in loaded.items():
        assert np.allclose(centroid, centroids[intent], rtol=1e-6), \
            f"Mismatch in {intent} centroid!"
    print(f"  All {len(loaded)} centroids verified ✓")
    print("\nDone.")


def main() -> None:
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
        default=DEFAULT_MODEL,
        help="SentenceTransformer model name (default: AITeamVN/Vietnamese_Embedding)",
    )
    args = parser.parse_args()

    if not args.utterances.exists():
        print(f"ERROR: utterances.json not found at {args.utterances}", file=sys.stderr)
        sys.exit(1)

    build_centroids(
        utterances_path=args.utterances,
        output_dir=args.output_dir,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
