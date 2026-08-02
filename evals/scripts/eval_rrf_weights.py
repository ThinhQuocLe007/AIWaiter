#!/usr/bin/env python3
"""Sweep the reciprocal-rank-fusion lane weights against the retrieval eval set.

Equal-weight RRF was measured demoting BM25's exact matches: on "cho xem lẩu thái"
BM25 ranks Lẩu Thái first and the fused list ranks Lẩu Gà Lá É first. This sweep asks
whether any weighting of the two lanes beats the lexical lane on its own, and by how
much, so the deployed weights are chosen from a measurement rather than assumed.

    PYTHONPATH=. uv run python evals/scripts/eval_rrf_weights.py

Writes evals/results/rrf_weights_<ts>.json and prints the table. The two single-lane
baselines are computed over the same filtered candidate pool as the fused arms, so all
arms are scored on the same document population.

Caveat the caller must carry: the sweep selects on the same 24 queries it reports, so
the winning weight is fitted to this set. It is a design decision informed by evidence,
not a held-out result, and the thesis reports it as such.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.agent_brain.services.retriever.builder import IndexBuilder
from src.agent_brain.services.retriever.hybrid_retriever import RetrieverManager
from src.agent_brain.services.retriever.filters import by_menu_metadata
from src.agent_brain.config import settings

EVAL_DATA = settings.PROJECT_ROOT / "evals" / "data" / "retrieval" / "retrieval_eval.json"
RESULTS_DIR = settings.PROJECT_ROOT / "evals" / "results"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

# w_bm25 : w_vector. 1.0/0.0 is BM25 alone through the fusion path, which is the arm the
# fused ones have to beat.
WEIGHTS = [(1.0, 1.0), (1.5, 1.0), (2.0, 1.0), (3.0, 1.0), (4.0, 1.0), (6.0, 1.0), (1.0, 0.0)]


def metrics(retrieved: list[str], relevant: list[str], k: int = 5) -> dict:
    rel = {r.lower() for r in relevant}
    got = [r.lower() for r in retrieved][:k]
    hits = [r for r in got if r in rel]
    mrr = 0.0
    for i, name in enumerate(got):
        if name in rel:
            mrr = 1.0 / (i + 1)
            break
    return {
        "precision": len(hits) / k if k else 0.0,
        "recall": len(hits) / len(rel) if rel else 0.0,
        "mrr": mrr,
        "hit_rate": 1.0 if hits else 0.0,
    }


def name_of(doc) -> str:
    return doc.metadata.get("name") or doc.metadata.get("title") or "Unknown"


def main() -> int:
    cases = json.loads(EVAL_DATA.read_text(encoding="utf-8"))["cases"]

    builder = IndexBuilder()
    if not builder.load_database():
        builder.build([str(settings.PROJECT_ROOT / "assets" / "data")])
    retriever = RetrieverManager(vector_engine=builder.vector_engine,
                                 bm25_engine=builder.bm25_engine)
    retriever.search("warmup", k=5, mode="rrf")

    # BM25 alone, outside the fusion path, as the reference the sweep has to beat.
    base = {"precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0}
    per_diff_base: dict[str, list] = {}
    for c in cases:
        raw = builder.bm25_engine.search(c["query"], k=15)
        names = [name_of(d) for d, _ in by_menu_metadata(raw)][:5]
        m = metrics(names, c["expected_relevant"])
        for k in base:
            base[k] += m[k] / len(cases)
        per_diff_base.setdefault(c.get("difficulty", "?"), []).append(m)

    rows = []
    for w_b, w_v in WEIGHTS:
        agg = {"precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0}
        per_diff: dict[str, list] = {}
        for c in cases:
            res = retriever.search(c["query"], k=5, mode="rrf", w_bm25=w_b, w_vector=w_v)
            names = [name_of(r.document) for r in res]
            m = metrics(names, c["expected_relevant"])
            for k in agg:
                agg[k] += m[k] / len(cases)
            per_diff.setdefault(c.get("difficulty", "?"), []).append(m)
        rows.append({
            "w_bm25": w_b, "w_vector": w_v, **{k: round(v, 4) for k, v in agg.items()},
            "per_difficulty": {
                d: {k: round(sum(x[k] for x in v) / len(v), 4) for k in agg}
                for d, v in per_diff.items()
            },
        })

    print(f"\n{'w_bm25:w_vec':>14s} {'P@5':>7s} {'R@5':>7s} {'MRR':>7s} {'Hit':>7s}")
    print(f"{'BM25 alone':>14s} {base['precision']:7.3f} {base['recall']:7.3f} "
          f"{base['mrr']:7.3f} {base['hit_rate']:7.3f}   (reference)")
    for r in rows:
        tag = f"{r['w_bm25']:g}:{r['w_vector']:g}"
        flag = "  <- beats BM25 on R@5" if r["recall"] > base["recall"] else ""
        print(f"{tag:>14s} {r['precision']:7.3f} {r['recall']:7.3f} "
              f"{r['mrr']:7.3f} {r['hit_rate']:7.3f}{flag}")

    best = max(rows, key=lambda r: (r["recall"], r["mrr"]))
    print(f"\nbest by R@5 then MRR: w_bm25={best['w_bm25']:g} w_vector={best['w_vector']:g}")
    print("per-difficulty at that weight:")
    for d in ("easy", "medium", "hard"):
        if d in best["per_difficulty"]:
            v = best["per_difficulty"][d]
            print(f"  {d:7s} P@5={v['precision']:.3f} R@5={v['recall']:.3f} "
                  f"MRR={v['mrr']:.3f} Hit={v['hit_rate']:.3f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"rrf_weights_{TS}.json"
    out.write_text(json.dumps({
        "timestamp": TS, "n_queries": len(cases),
        "bm25_alone": {k: round(v, 4) for k, v in base.items()},
        "arms": rows, "best": best,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nsaved {out.relative_to(settings.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
