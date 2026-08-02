#!/usr/bin/env python3
"""Build corpus_v2.json and refuse to write it unless every quality gate passes.

Usage:
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/build_corpus.py
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/build_corpus.py --dry-run
    PYTHONPATH=. uv run python src/training_semantic_router/scripts/build_corpus.py --seed 123

The gates exist because the previous corpus failed all of them silently: it named 30 of
234 dishes, overlapped the eval sets by 45%, and carried 3 utterances under two labels.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import itertools
import json
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.training_semantic_router.data.corpus_builder import (  # noqa: E402
    ORDER_TEMPLATES,
    PAYMENT_METHOD_TEMPLATES,
    PAYMENT_SPLIT_TEMPLATES,
    SEARCH_BROWSE_TEMPLATES,
    SEARCH_DISH_TEMPLATES,
    SEARCH_SERVICE_TEMPLATES,
    build_corpus,
    load_menu,
)

DATA_DIR = PROJECT_ROOT / "src" / "training_semantic_router" / "data"
OUTPUT = DATA_DIR / "corpus_v2.json"

EVAL_FILES = [
    PROJECT_ROOT / "evals" / "data" / "router" / "single_intent_eval.json",
    PROJECT_ROOT / "evals" / "data" / "router" / "context_dependent_eval.json",
    PROJECT_ROOT / "evals" / "data" / "router" / "multi_intent_detection.json",
    DATA_DIR / "test_holdout.json",
]

LABELS = ["ORDER", "SEARCH", "PAYMENT", "CHAT"]
STYLES = ["formal", "casual", "dialect", "fragment", "edge"]

# Literals are compared as token SETS: two hand-written sentences sharing most of their
# vocabulary are the same sentence with a different particle.
NEAR_DUP_THRESHOLD = 0.6

# Templates need a different metric, and the obvious ones are both wrong. Set-Jaccard
# scores "{q} {u} {d}" against "{d} {q} {u}" as 1.00 because the slot tokens are identical,
# yet those produce "2 phần Ốc Hương" and "Ốc Hương 2 phần" — different surface forms.
# Plain SequenceMatcher on the raw template has a milder version of the same bug: in
# "cho {q} {u} {d} đi em" the slots are half the characters, so any two ordering frames
# score ~0.75 on shared slots alone.
#
# What actually distinguishes two templates is the LEXICAL FRAME — the words around the
# slots — plus the slot order. So: same slot sequence AND similar skeleton = duplicate.
# A different slot order is never a duplicate; it is a different sentence.
TEMPLATE_DUP_THRESHOLD = 0.75
_SLOT_RE = __import__("re").compile(r"\{[a-z0-9]+\}")


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s.lower().strip().rstrip(".,!?"))


def jaccard(a: str, b: str) -> float:
    A, B = set(a.split()), set(b.split())
    return len(A & B) / len(A | B) if A | B else 0.0


def seq_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def template_signature(tpl: str) -> tuple[tuple[str, ...], str]:
    """(slot sequence, lexical skeleton) — the two things that make a template distinct."""
    n = norm(tpl)
    slots = tuple(_SLOT_RE.findall(n))
    skeleton = " ".join(_SLOT_RE.sub(" ", n).split())
    return slots, skeleton


def template_similarity(a: str, b: str) -> float:
    """Similarity of the lexical frame, given the same slot order.

    0.0 when the slot order differs: "{q} {u} {d}" and "{d} {q} {u}" render as
    "2 phần Ốc Hương" and "Ốc Hương 2 phần", two different sentences.
    1.0 only when both frames are bare slots with no words at all to tell them apart.
    """
    slots_a, skel_a = template_signature(a)
    slots_b, skel_b = template_signature(b)
    if slots_a != slots_b:
        return 0.0
    if not skel_a and not skel_b:
        return 1.0
    return seq_ratio(skel_a, skel_b)


def eval_utterances() -> set[str]:
    out: set[str] = set()
    for path in EVAL_FILES:
        if not path.exists():
            continue
        blob = json.load(open(path, "r", encoding="utf-8"))
        cases = blob.get("cases") if isinstance(blob, dict) else blob
        if not isinstance(cases, list):
            continue
        for c in cases:
            if isinstance(c, dict) and c.get("utterance"):
                out.add(norm(c["utterance"]))
    return out


def prune_near_duplicate_literals(records: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Slot-filled rows legitimately share a skeleton — that IS the dish coverage mechanism,
    so near-duplicate pruning applies only to hand-written literals, where a high overlap
    means two rows really are the same sentence with a different particle."""
    kept: list[dict] = []
    dropped: list[tuple[str, str]] = []
    per_intent: dict[str, list[str]] = collections.defaultdict(list)
    for r in records:
        if not str(r["source"]).startswith("handwritten"):
            kept.append(r)
            continue
        n = norm(r["utterance"])
        clash = next((p for p in per_intent[r["intent"]] if jaccard(n, p) >= NEAR_DUP_THRESHOLD), None)
        if clash:
            dropped.append((r["utterance"], clash))
            continue
        per_intent[r["intent"]].append(n)
        kept.append(r)
    return kept, dropped


def check(records: list[dict]) -> list[str]:
    errors: list[str] = []
    menu = load_menu()
    menu_names = {m["name"] for m in menu}

    # 1 — dish coverage in the two intents where the dish name is the signal
    for intent in ("ORDER", "SEARCH"):
        covered = {r["dish"] for r in records if r["intent"] == intent and r["dish"]}
        missing = menu_names - covered
        if missing:
            errors.append(
                f"[1] {intent}: thiếu {len(missing)}/{len(menu_names)} món, ví dụ "
                + ", ".join(sorted(missing)[:5])
            )

    # 2 — template skeletons inside a class must not be near-duplicates of each other
    for name, tpls in (("ORDER", ORDER_TEMPLATES),
                       ("SEARCH_DISH", SEARCH_DISH_TEMPLATES),
                       ("SEARCH_BROWSE", SEARCH_BROWSE_TEMPLATES),
                       ("PAYMENT_METHOD", PAYMENT_METHOD_TEMPLATES),
                       ("PAYMENT_SPLIT", PAYMENT_SPLIT_TEMPLATES),
                       ("SEARCH_SERVICE", SEARCH_SERVICE_TEMPLATES)):
        for (ia, _, ta), (ib, _, tb) in itertools.combinations(tpls, 2):
            r = template_similarity(ta, tb)
            if r >= TEMPLATE_DUP_THRESHOLD:
                errors.append(f"[2] template {name} {ia} ~ {ib} trùng khung (sim={r:.2f})\n"
                              f"       {ta!r}\n       {tb!r}")

    # 2b — no near-duplicate literals survived the prune
    per_intent: dict[str, list[str]] = collections.defaultdict(list)
    for r in records:
        if not str(r["source"]).startswith("handwritten"):
            continue
        n = norm(r["utterance"])
        for p in per_intent[r["intent"]]:
            if jaccard(n, p) >= NEAR_DUP_THRESHOLD:
                errors.append(f"[2b] literal trùng: {r['utterance']!r} ~ {p!r}")
        per_intent[r["intent"]].append(n)

    # 3 — zero overlap with every eval set
    ev = eval_utterances()
    leaked = [r["utterance"] for r in records if norm(r["utterance"]) in ev]
    if leaked:
        errors.append(f"[3] {len(leaked)} câu trùng tập eval: " + ", ".join(leaked[:5]))

    # 4 — one label per surface string
    by_utt: dict[str, set[str]] = collections.defaultdict(set)
    for r in records:
        by_utt[norm(r["utterance"])].add(r["intent"])
    for u, labs in by_utt.items():
        if len(labs) > 1:
            errors.append(f"[4] {u!r} mang nhiều nhãn: {sorted(labs)}")

    # 5 — every class carries all five registers
    for intent in LABELS:
        got = {r["style"] for r in records if r["intent"] == intent}
        if missing_styles := set(STYLES) - got:
            errors.append(f"[5] {intent} thiếu style: {sorted(missing_styles)}")

    # 6 — all three length bands present per class (real speech is not all 6 words)
    for intent in LABELS:
        lens = [len(r["utterance"].split()) for r in records if r["intent"] == intent]
        bands = {
            "fragment(1-4)": sum(1 for x in lens if x <= 4),
            "vừa(5-11)": sum(1 for x in lens if 5 <= x <= 11),
            "dài(12-25)": sum(1 for x in lens if x >= 12),
        }
        for band, n in bands.items():
            if n == 0:
                errors.append(f"[6] {intent} không có câu nào ở dải {band}")
    return errors


def report(records: list[dict]) -> None:
    print(f"\ntổng: {len(records)} câu duy nhất")
    per = collections.Counter(r["intent"] for r in records)
    for k in LABELS:
        print(f"  {k:<8} {per[k]:4d}  ({per[k] / len(records):.0%})")
    print("\nstyle:")
    for k, v in collections.Counter(r["style"] for r in records).most_common():
        print(f"  {k:<10} {v:4d}")
    print("\nnguồn:")
    for k, v in collections.Counter(r["source"] for r in records).most_common():
        print(f"  {k:<20} {v:4d}")
    lens = [len(r["utterance"].split()) for r in records]
    print("\nđộ dài (từ):")
    print(f"  fragment 1-4 : {sum(1 for x in lens if x <= 4):4d}")
    print(f"  vừa      5-11: {sum(1 for x in lens if 5 <= x <= 11):4d}")
    print(f"  dài     12-25: {sum(1 for x in lens if x >= 12):4d}")
    print(f"  min {min(lens)}  median {sorted(lens)[len(lens) // 2]}  max {max(lens)}")
    menu = load_menu()
    for intent in ("ORDER", "SEARCH"):
        cov = {r["dish"] for r in records if r["intent"] == intent and r["dish"]}
        print(f"\nphủ món {intent}: {len(cov)}/{len(menu)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260729)
    ap.add_argument("--output", default=str(OUTPUT))
    ap.add_argument("--dry-run", action="store_true", help="chạy gate nhưng không ghi file")
    args = ap.parse_args()

    records = build_corpus(seed=args.seed)
    records, dropped = prune_near_duplicate_literals(records)
    if dropped:
        print(f"đã loại {len(dropped)} literal trùng nghĩa:")
        for a, b in dropped[:10]:
            print(f"   {a!r}  ~  {b!r}")

    report(records)

    errors = check(records)
    print("\n" + "=" * 62)
    if errors:
        print(f"GATE FAIL — {len(errors)} lỗi, KHÔNG ghi file:")
        for e in errors[:40]:
            print("  -", e)
        return 1

    print("GATE PASS — cả 6 điều kiện đều đạt")
    if args.dry_run:
        print("(dry-run, không ghi file)")
        return 0

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"đã ghi {len(records)} câu -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
