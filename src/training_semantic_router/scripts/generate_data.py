#!/usr/bin/env python3
"""Generate synthetic training data for intent classifier.

Usage:
    # Generate 50 per intent with Ollama (local):
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/generate_data.py \\
        --provider ollama --count 50

    # Generate 200 per intent with Gemini:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/generate_data.py \\
        --provider gemini --count 200

    # Generate + augment in one pass:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/generate_data.py \\
        --provider ollama --count 50 --augment

    # Only augment existing raw data:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/generate_data.py \\
        --only-augment
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("generate_data")

INTENTS = ["ORDER", "SEARCH", "PAYMENT", "CHAT"]


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic intent classifier training data")
    parser.add_argument("--provider", choices=["gemini", "ollama"], default="ollama")
    parser.add_argument("--count", type=int, default=200, help="Total examples per intent")
    parser.add_argument("--model", default="qwen2.5:7b-instruct", help="Ollama model name")
    parser.add_argument("--api-key", default=os.getenv("GEMINI_API_KEY"))
    parser.add_argument("--augment", action="store_true", help="Run augmenter after generation")
    parser.add_argument("--only-augment", action="store_true")
    parser.add_argument("--raw-input", default=str(DATA_DIR / "synthetic_raw.json"))
    parser.add_argument("--raw-output", default=str(DATA_DIR / "synthetic_raw.json"))
    parser.add_argument("--augmented-output", default=str(DATA_DIR / "synthetic_augmented.json"))
    parser.add_argument("--ambi-count", type=int, default=80, help="Extra ambiguous examples to generate")
    args = parser.parse_args()

    if args.only_augment:
        from src.training_semantic_router.data.augmenter import augment_file, build_ambiguous_set

        raw_path = Path(args.raw_input)
        if not raw_path.exists():
            logger.error("Raw data not found at %s", raw_path)
            sys.exit(1)

        augmented = augment_file(raw_path, Path(args.augmented_output))
        ambi = build_ambiguous_set(args.ambi_count)
        all_data = augmented + ambi
        logger.info("Added %d extra ambiguous examples, total %d", len(ambi), len(all_data))

        output_path = Path(args.augmented_output)
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        logger.info("Final augmented dataset saved to %s", output_path)

        _print_stats(all_data)
        return

    from src.training_semantic_router.data.generator import generate_all

    if args.provider == "gemini" and not args.api_key:
        logger.error("GEMINI_API_KEY not set. Set in .env or pass --api-key.")
        sys.exit(1)

    counts = {intent: args.count for intent in INTENTS}
    logger.info(
        "Generating %d examples per intent × %d intents = %d total via %s",
        args.count, len(INTENTS), args.count * len(INTENTS), args.provider,
    )

    raw_path = Path(args.raw_output)
    records = generate_all(
        counts=counts,
        provider=args.provider,
        api_key=args.api_key,
        model=args.model,
        output_path=raw_path,
    )

    _print_raw_stats(records)

    if args.augment and records:
        from src.training_semantic_router.data.augmenter import augment_file, build_ambiguous_set

        augmented = augment_file(raw_path, Path(args.augmented_output))
        ambi = build_ambiguous_set(args.ambi_count)
        all_data = augmented + ambi

        import json
        with open(Path(args.augmented_output), "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        logger.info("Added %d extra ambiguous examples, total %d", len(ambi), len(all_data))
        _print_stats(all_data)


def _print_raw_stats(records: list):
    if not records:
        return
    from collections import Counter
    intent_counts = Counter(r.get("intent", r.get("expected_route", "?")) for r in records)
    style_counts = Counter(r.get("style", "?") for r in records)
    logger.info("--- Raw Data Stats ---")
    logger.info("Total: %d records", len(records))
    for intent in sorted(intent_counts):
        logger.info("  %s: %d", intent, intent_counts[intent])
    for style in sorted(style_counts):
        logger.info("  style=%s: %d", style, style_counts[style])


def _print_stats(examples: list):
    from collections import Counter
    intent_counts = Counter(e["intent"] for e in examples)
    stage_counts = Counter(e["order_stage"] for e in examples)
    ambi_count = sum(1 for e in examples if e.get("is_ambiguous"))
    logger.info("--- Augmented Data Stats ---")
    logger.info("Total: %d examples", len(examples))
    logger.info("Ambiguous: %d (%.1f%%)", ambi_count, ambi_count / len(examples) * 100)
    for intent in sorted(intent_counts):
        logger.info("  %s: %d", intent, intent_counts[intent])
    for stage in sorted(stage_counts):
        logger.info("  stage=%s: %d", stage, stage_counts[stage])


if __name__ == "__main__":
    main()
