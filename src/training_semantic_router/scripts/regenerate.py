"""Regenerate router training data: keep original Gemini corpus, add
fragment-style and critical-vocabulary examples via local Ollama.

The original 3,712 samples were Gemini-generated (high quality, narrow vocab).
This script generates ONLY the missing categories via Ollama and appends them,
so the original quality is preserved while vocabulary coverage is expanded.

Usage:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/regenerate.py
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/regenerate.py --count 250
"""

import json
import logging
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ORIGINAL = DATA_DIR / "synthetic_augmented.json"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("regenerate")


def backup_original():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"synthetic_augmented_{ts}.json"
    shutil.copy2(ORIGINAL, backup)
    logger.info("Backed up %s -> %s", ORIGINAL.name, backup)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=250,
                        help="Examples per intent (fragment style only)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(ORIGINAL, "r", encoding="utf-8") as f:
        original = json.load(f)
    logger.info("Loaded %d original samples", len(original))

    # Generate fragment-style examples via Ollama
    from src.training_semantic_router.data.generator import generate_all

    counts = {"ORDER": args.count, "SEARCH": args.count,
              "PAYMENT": args.count, "CHAT": args.count}

    # Fragment only — the original data already covers formal/casual/dialect/edge
    logger.info("Generating %d fragment examples per intent via Ollama...", args.count)
    fragments = generate_all(
        counts=counts,
        styles=["fragment"],
        provider="ollama",
        output_path=DATA_DIR / "synthetic_fragments.json",
    )

    logger.info("Generated %d fragment examples", len(fragments))

    # Merge
    merged = original + fragments
    logger.info("Merged: %d original + %d fragment = %d total",
                len(original), len(fragments), len(merged))

    # Stats
    all_text = " ".join(item["utterance"] for item in merged)
    all_tokens = all_text.split()
    unique_tokens = len(set(all_tokens))

    old_text = " ".join(item["utterance"] for item in original)
    old_tokens = len(set(old_text.split()))

    logger.info("Unique tokens: %d -> %d (+%d)", old_tokens, unique_tokens,
                unique_tokens - old_tokens)

    dist = Counter(item.get("intent", "?") for item in merged)
    logger.info("Intent distribution:")
    for intent in sorted(dist):
        logger.info("  %s: %d (%.1f%%)", intent, dist[intent],
                    dist[intent] / len(merged) * 100)

    # Check critical vocab
    for word in ["tôi", "xoá", "xóa", "giỏ hàng", "quận", "ship", "shop"]:
        count = all_text.lower().count(word)
        status = "OK" if count > 0 else "MISSING"
        logger.info("  '%s': %d  %s", word, count, status)

    if args.dry_run:
        logger.info("DRY RUN — no changes written")
        return

    backup_original()

    with open(ORIGINAL, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d total samples to %s", len(merged), ORIGINAL)

    # Retrain
    logger.info("\nRetraining classifier...")
    import subprocess
    train_script = Path(__file__).resolve().parent / "train.py"
    result = subprocess.run(
        [sys.executable, str(train_script)],
        cwd=PROJECT_ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    if result.returncode != 0:
        logger.error("Training failed with code %d", result.returncode)
        sys.exit(1)

    # Evaluate holdout
    logger.info("\nEvaluating holdout...")
    eval_script = Path(__file__).resolve().parent / "evaluate.py"
    subprocess.run(
        [sys.executable, str(eval_script)],
        cwd=PROJECT_ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )

    # Run router ablation
    logger.info("\nRunning six-arm router ablation...")
    ablation_script = PROJECT_ROOT / "evals" / "scripts" / "eval_router_arms.py"
    subprocess.run(
        [sys.executable, str(ablation_script)],
        cwd=PROJECT_ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )


if __name__ == "__main__":
    main()
