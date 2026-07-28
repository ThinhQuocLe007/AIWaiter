#!/usr/bin/env python3
"""Build the recording manifest for the cascade experiment (thesis §5.4.5).

The cascade experiment measures what the recogniser costs the components downstream of it.
Every other AI experiment in Chapter 5 feeds the agent clean typed text, so nothing currently
answers the question the thesis actually depends on: does routing accuracy survive real
Vietnamese speech in a noisy dining room?

Sampling is stratified and deterministic (fixed seed), drawing from the sets that already
carry ground-truth labels so that one recording session serves three experiments:

    - §5.4.1 WER/CER          — needs a reference transcript      (all utterances)
    - §5.4.2 VAD boundaries   — needs speech/silence ground truth (all utterances)
    - §5.4.5 cascade delta    — needs an intent label             (router-sourced utterances)

Utterances are chosen to over-represent dish names, because dish tokens are what the
validator resolves on and what a generic multilingual recogniser is least likely to get right.

Usage:
    PYTHONPATH=. uv run python evals/scripts/build_cascade_manifest.py
    PYTHONPATH=. uv run python evals/scripts/build_cascade_manifest.py --n 80 --speakers 4
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

ROUTER_DIR = PROJECT_ROOT / "evals" / "data" / "router"
E2E_DIR = PROJECT_ROOT / "evals" / "data" / "e2e"
HOLDOUT = PROJECT_ROOT / "src" / "training_semantic_router" / "data" / "test_holdout.json"
MENU = PROJECT_ROOT / "assets" / "data" / "menu.json"
OUT = PROJECT_ROOT / "evals" / "data" / "cascade" / "manifest.json"

MERGE = {"ORDER_CONFIRM": "ORDER"}

# Noise is mixed in digitally after recording, so a speaker reads each line exactly once and
# the noise axis costs no extra session time. Clean is kept as the within-speaker reference.
SNR_LEVELS = ["clean", "20db", "10db", "0db"]


def dish_tokens(menu_path: Path) -> set[str]:
    """Lowercased word tokens appearing in menu dish names, minus generic connectives."""
    stop = {"xốt", "và", "với", "kiểu", "nhỏ", "lớn", "thố", "phần"}
    names = [i["name"] for i in json.loads(menu_path.read_text(encoding="utf-8"))]
    tokens = {t for n in names for t in re.findall(r"\w+", n.lower())}
    return tokens - stop


def collect() -> list[dict]:
    """Pull labelled utterances from every source that has both text and an intent."""
    pool: list[dict] = []

    for name, path in [
        ("holdout", HOLDOUT),
        ("router", ROUTER_DIR / "router_eval.json"),
        ("semantic", ROUTER_DIR / "semantic_eval.json"),
        ("context", ROUTER_DIR / "router_context_eval.json"),
    ]:
        for c in json.loads(path.read_text(encoding="utf-8"))["cases"]:
            text = c.get("input") or c.get("utterance") or ""
            intent = c.get("expected_route", c.get("intent"))
            if not text or isinstance(intent, list):
                continue
            pool.append({
                "text": text.strip(),
                "intent": MERGE.get(intent, intent),
                "source": f"{name}:{c.get('id', '?')}",
                "difficulty": c.get("difficulty", "?"),
                "order_stage": (c.get("context") or {}).get("order_stage") or c.get("order_stage"),
            })

    # Multi-intent turns are included but marked: they exercise the recogniser on long
    # utterances, which is where end-of-utterance detection is most likely to truncate.
    mi = json.loads((E2E_DIR / "multi_intent_eval.json").read_text(encoding="utf-8"))
    for c in mi["cases"]:
        pool.append({
            "text": c["utterance"].strip(),
            "intent": "+".join(c["expected_intents"]),
            "source": f"multi_intent:{c['id']}",
            "difficulty": c.get("difficulty", "?"),
            "order_stage": None,
        })

    seen: set[str] = set()
    unique = []
    for item in pool:
        key = item["text"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=60, help="utterances to record (default: 60)")
    ap.add_argument("--speakers", type=int, default=3, help="speakers reading the whole set")
    ap.add_argument("--seed", type=int, default=20260723, help="sampling seed, fixed for reproducibility")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    pool = collect()
    dishes = dish_tokens(MENU)

    def has_dish(text: str) -> bool:
        return bool({t for t in re.findall(r"\w+", text.lower())} & dishes)

    # Stratify by intent so no class is left with too few items to compute a per-class WER,
    # and inside each class prefer utterances containing dish names -- those are the tokens
    # the validator resolves on, so an error there costs the pipeline more than an error in a
    # function word does.
    by_intent: dict[str, list[dict]] = {}
    for item in pool:
        by_intent.setdefault(item["intent"].split("+")[0], []).append(item)

    for items in by_intent.values():
        rng.shuffle(items)
        items.sort(key=lambda x: not has_dish(x["text"]))

    chosen: list[dict] = []
    intents = sorted(by_intent)
    i = 0
    while len(chosen) < args.n and any(by_intent.values()):
        bucket = by_intent[intents[i % len(intents)]]
        if bucket:
            chosen.append(bucket.pop(0))
        i += 1

    items = []
    for idx, item in enumerate(chosen, 1):
        uid = f"CAS-{idx:03d}"
        items.append({
            "id": uid,
            "text": item["text"],
            "intent": item["intent"],
            "source": item["source"],
            "difficulty": item["difficulty"],
            "order_stage": item["order_stage"],
            "contains_dish_name": has_dish(item["text"]),
            # One file per speaker. The recorder only ever produces these; the SNR variants
            # are generated from them by eval_cascade.py, never recorded separately.
            "files": [f"{uid}_spk{s}.wav" for s in range(1, args.speakers + 1)],
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "dataset": "cascade_manifest",
        "version": "1.0",
        "description": (
            "Danh sách câu cần thu âm cho thí nghiệm cascade (§5.4.5). Mỗi câu được đọc bởi "
            f"{args.speakers} người, thu SẠCH một lần; các mức nhiễu được trộn bằng phần mềm "
            "sau đó nên không phát sinh thêm thời gian thu. Ground-truth transcript chính là "
            "trường 'text' — người đọc phải đọc đúng câu, không diễn đạt lại."
        ),
        "seed": args.seed,
        "speakers": args.speakers,
        "snr_levels": SNR_LEVELS,
        "audio_spec": {"format": "wav", "sample_rate": 16000, "channels": 1, "bit_depth": 16},
        "total_utterances": len(items),
        "total_recordings": len(items) * args.speakers,
        "total_eval_items": len(items) * args.speakers * len(SNR_LEVELS),
        "items": items,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    by_class: dict[str, int] = {}
    for it in items:
        by_class[it["intent"]] = by_class.get(it["intent"], 0) + 1
    with_dish = sum(1 for it in items if it["contains_dish_name"])

    print(f"  wrote {OUT.relative_to(PROJECT_ROOT)}")
    print(f"  {len(items)} utterances x {args.speakers} speakers = {len(items) * args.speakers} recordings")
    print(f"  x {len(SNR_LEVELS)} SNR levels = {len(items) * args.speakers * len(SNR_LEVELS)} eval items")
    print(f"  containing a dish name: {with_dish}/{len(items)}")
    print(f"  intent distribution: {dict(sorted(by_class.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
