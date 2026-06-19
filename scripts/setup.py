#!/usr/bin/env python3
"""
setup.py — One-time project initialization.

Creates all databases, builds vector indexes, and centroids.
Run before first launch or after a clean clone.

Usage:
    python scripts/setup.py
    python scripts/setup.py --skip-centroids
    python scripts/setup.py --force
"""
import argparse
import sys
import os
import sqlite3
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT / "ai_waiter_core"))
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["PROJECT_ROOT"] = str(PROJECT_ROOT)

import ai_waiter_core  # noqa: E402 ensure path is set before other imports
from ai_waiter_core.config import settings
from ai_waiter_core.services.restaurant_db import RestaurantDB
from ai_waiter_core.services.retriever.builder import IndexBuilder
from scripts.build_centroids import main as build_centroids_main


REQUIRED_FILES = [
    # Assets
    "assets/data/menu.json",
    "assets/data/best_seller.json",
    "assets/data/discounts.json",
    "assets/data/customer_info.json",
    "assets/data/restaurant_info.txt",
    # Few-shots
    "ai_waiter_core/ai_waiter_core/agent/resources/few_shots/utterances.json",
    "ai_waiter_core/ai_waiter_core/agent/resources/few_shots/router.json",
    "ai_waiter_core/ai_waiter_core/agent/resources/few_shots/search_worker.json",
    # Prompts
    "ai_waiter_core/ai_waiter_core/agent/resources/system_prompts/router_agent.md",
    "ai_waiter_core/ai_waiter_core/agent/resources/system_prompts/order_worker_agent.md",
    "ai_waiter_core/ai_waiter_core/agent/resources/system_prompts/search_agent.md",
    "ai_waiter_core/ai_waiter_core/agent/resources/system_prompts/waiter_agent.md",
    "ai_waiter_core/ai_waiter_core/agent/resources/skills/hospitality.md",
    "ai_waiter_core/ai_waiter_core/agent/resources/skills/menu_grounding.md",
    "ai_waiter_core/ai_waiter_core/agent/resources/skills/no_service_response.md",
    # Centroids
    "evals/data/router/router_eval.json",
    "evals/data/retrieval/retrieval_eval.json",
]

CENTROIDS_PATH = (
    PROJECT_ROOT
    / "ai_waiter_core/ai_waiter_core/agent/resources/centroids/centroids.npz"
)


def verify_assets() -> bool:
    missing = [p for p in REQUIRED_FILES if not (PROJECT_ROOT / p).exists()]
    if missing:
        print("❌ Missing required files:")
        for p in missing:
            print(f"   {p}")
        return False
    return True


def create_directories():
    for rel_path in ["storage/db", "storage/vector", "storage/indexes", "evals/results"]:
        (PROJECT_ROOT / rel_path).mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {rel_path}/")


def _wipe_db(db_path: str):
    """Remove the SQLite database file and its WAL/SHM sidecars."""
    for suffix in ("", "-wal", "-shm"):
        p = Path(db_path + suffix)
        if p.exists():
            p.unlink()


def init_restaurant_db(force: bool = False):
    if force:
        _wipe_db(str(settings.RESTAURANT_DB_PATH))
        print("  → Wiped existing Restaurant DB (--force)")
    db = RestaurantDB()
    print(f"  ✓ Restaurant DB at {db.db_path}")


def init_checkpoints_db(force: bool = False):
    db_path = str(settings.CHECKPOINTS_DB_PATH)
    if force:
        _wipe_db(db_path)
        print("  → Wiped existing Checkpoints DB (--force)")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.close()
    print(f"  ✓ Checkpoints DB at {db_path}")


def build_search_indexes(force: bool):
    builder = IndexBuilder()
    if not force and builder.load_database():
        print("  ✓ Search indexes already exist (use --force to rebuild)")
        return
    assets_dir = str(PROJECT_ROOT / "assets" / "data")
    success = builder.build([assets_dir])
    if success:
        print("  ✓ FAISS index + BM25 index built")
    else:
        print("  ❌ Failed to build search indexes")


def build_centroids(force: bool, skip: bool):
    if skip:
        print("  → Skipped centroids (--skip-centroids)")
        return
    if not force and CENTROIDS_PATH.exists():
        print("  ✓ Centroids already exist (use --force to rebuild)")
        return
    try:
        build_centroids_main([])
        print("  ✓ Centroids built")
    except Exception as e:
        print(f"  ❌ Failed to build centroids: {e}")


def main():
    parser = argparse.ArgumentParser(description="Initialize the AI Waiter project.")
    parser.add_argument("--force", action="store_true", help="Rebuild everything even if exists")
    parser.add_argument("--skip-centroids", action="store_true", help="Skip centroid building")
    args = parser.parse_args()

    print("\n🔧 AI Waiter — Setup\n")

    print("1. Verifying assets...")
    if not verify_assets():
        sys.exit(1)
    print("   ✓ All required files present\n")

    print("2. Creating directories...")
    create_directories()
    print()

    print("3. Initializing Restaurant DB...")
    init_restaurant_db(args.force)
    print()

    print("4. Initializing Checkpoints DB...")
    init_checkpoints_db(args.force)
    print()

    print("5. Building search indexes (FAISS + BM25)...")
    build_search_indexes(args.force)
    print()

    print("6. Building centroid embeddings...")
    build_centroids(args.force, args.skip_centroids)
    print()

    print("✅ Setup complete.")


if __name__ == "__main__":
    main()
