"""Retrieval Evaluator — per-difficulty breakdown, BM25-only and FAISS-only standalone
modes, RRF fusion, and dual-lane gatekeeper analysis.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_retrieval_full.py
    PYTHONPATH=. uv run python evals/scripts/eval_retrieval_full.py --dataset retrieval_eval_v2.json
    PYTHONPATH=. uv run python evals/scripts/eval_retrieval_full.py --only gatekeeper
"""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.agent_brain.services.retriever.builder import IndexBuilder
from src.agent_brain.services.retriever.hybrid_retriever import RetrieverManager
from src.agent_brain.services.retriever.indices.embeddings import get_profile
from src.agent_brain.services.retriever.fusion.rrf import gate_decision
from src.agent_brain.services.retriever.filters import by_menu_metadata
from src.agent_brain.config import settings
from evals.lib.stats import percentile

RESULTS_DIR = settings.PROJECT_ROOT / "evals" / "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

_dataset_arg = None
_args = sys.argv[1:]
for i, a in enumerate(_args):
    if a == "--dataset" and i + 1 < len(_args):
        _dataset_arg = _args[i + 1]

EVAL_DATA_PATH = settings.PROJECT_ROOT / "evals" / "data" / "retrieval" / (_dataset_arg or "retrieval_eval.json")

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
_tag = Path(EVAL_DATA_PATH).stem
LOG_PATH = RESULTS_DIR / f"retrieval_full_{_tag}_{TS}.log"
REPORT_PATH = RESULTS_DIR / f"retrieval_full_{_tag}_{TS}.json"

GATEKEEPER_SEMANTIC_THRESHOLD = 0.35
MODES = ["bm25", "faiss", "rrf", "linear"]


def log(msg: str):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _raw_score_to_cosine(raw_score: float) -> float:
    """Convert a FAISS raw score to cosine similarity, using the active model's
    normalisation profile.  The same conversion used by the RRF gatekeeper in the
    production retriever."""
    p = get_profile()
    if p.get("normalize", False):
        return max(0.0, min(1.0, 1.0 - raw_score / 2.0))
    return float(raw_score)


def calculate_metrics(retrieved_names: list[str], expected_relevant: list[str], k: int = 5):
    expected_lower = [e.lower() for e in expected_relevant]
    retrieved_lower = [r.lower() for r in retrieved_names]

    hits = [r for r in retrieved_lower if r in expected_lower]
    precision = len(hits) / len(retrieved_lower) if retrieved_lower else 0
    recall = len(hits) / len(expected_lower) if expected_lower else 0
    hit_rate = 1 if hits else 0

    mrr_val = 0.0
    for i, name in enumerate(retrieved_lower):
        if name in expected_lower:
            mrr_val = 1.0 / (i + 1)
            break

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "mrr": round(mrr_val, 4),
        "hit_rate": hit_rate,
        "retrieved": retrieved_names,
        "hits": hits,
    }


def run_standalone_search(engine, query: str, k: int) -> tuple:
    """Run a single engine (BM25 or FAISS) standalone, returning (doc, score) list and latency."""
    start = time.time()
    results = engine.search(query, k=k)
    elapsed = time.time() - start
    return results, elapsed


def gatekeeper_check(bm25_engine, vector_engine, query: str) -> dict:
    """Run the deployed gatekeeper against one query.

    This calls `gate_decision` from the production fusion module rather than
    reimplementing it. An earlier version of this function did reimplement it and had
    drifted: it checked query terms against the dense lane's top document only, while
    the deployed gate checks both lanes' top documents. That harness reported
    rejections the deployed system would never make, so the gatekeeper figures it
    produced described a gate that did not exist.
    """
    bm25_results, _ = run_standalone_search(bm25_engine, query, k=15)
    vector_results, _ = run_standalone_search(vector_engine, query, k=15)

    # The deployed gate runs inside RRFFusion.fuse, which RetrieverManager calls with
    # metadata-filtered lists. Filter here too, or the gate sees documents the deployed
    # one never gets to see.
    bm25_results = by_menu_metadata(bm25_results)
    vector_results = by_menu_metadata(vector_results)

    gate = gate_decision(bm25_results, vector_results, query)

    return {
        "semantic_pass": gate["semantic_pass"],
        "lexical_pass": gate["lexical_pass"],
        "passed": gate["passed"],
        "raw_top": round(gate["raw_top"], 4),
        "cos_sim": round(gate["cos_sim"], 4),
        "matched_terms": gate["matched_terms"],
        "bm25_top_doc_name": str(bm25_results[0][0].metadata.get("name", "?")) if bm25_results else "?",
        "vector_top_doc_name": str(vector_results[0][0].metadata.get("name", "?")) if vector_results else "?",
    }


def _extract_names(results):
    """Extract dish names from a list of (Document, score) tuples."""
    names = []
    seen = set()
    for doc, _score in results:
        name = doc.metadata.get("name") or doc.metadata.get("title") or "Unknown"
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def main():
    log("RETRIEVAL EVALUATION — BM25 | FAISS | RRF")

    if not EVAL_DATA_PATH.exists():
        log(f"ERROR: Dataset not found at {EVAL_DATA_PATH}")
        sys.exit(1)

    with open(EVAL_DATA_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    cases = dataset.get("cases", [])
    log(f"Loaded {len(cases)} test cases from {EVAL_DATA_PATH.name}")

    builder = IndexBuilder()
    if not builder.load_database():
        log("Building indices...")
        data_path = settings.PROJECT_ROOT / "assets" / "data"
        builder.build([str(data_path)])

    retriever = RetrieverManager(
        vector_engine=builder.vector_engine,
        bm25_engine=builder.bm25_engine,
    )

    # Warm the embedding model and both indices before timing anything.  Without this the
    # first query pays a ~10 s model-load penalty that lands entirely on whichever mode
    # runs first, and RRF fusion (which always ran third) appeared faster than FAISS-only
    # because it inherited an already-loaded model.
    log("Warming embedding model and indices ...")
    for _m in MODES:
        if _m in ("rrf", "linear"):
            retriever.search("warmup", k=5, mode=_m)
    run_standalone_search(builder.vector_engine, "warmup", k=5)
    run_standalone_search(builder.bm25_engine, "warmup", k=5)
    log("Warm-up complete.")

    per_mode = {m: {"total": 0, "precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0, "latencies": []}
                for m in MODES}
    per_difficulty = {m: defaultdict(lambda: {"total": 0, "precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0})
                      for m in MODES}
    gatekeeper_results = []
    detailed = []

    for case in cases:
        query = case["query"]
        case_id = case["id"]
        difficulty = case.get("difficulty", "unknown")
        expected = case["expected_relevant"]

        log(f"\n  [{case_id}] '{query}' (difficulty={difficulty})")
        log(f"    Expected relevant: {expected}")

        case_result = {"id": case_id, "query": query, "difficulty": difficulty, "modes": {}}

        for mode in MODES:
            if mode in ("rrf", "linear"):
                start = time.time()
                results = retriever.search(query, k=5, mode=mode)
                elapsed = time.time() - start
                retrieved_names = [
                    r.document.metadata.get("name") or r.document.metadata.get("title") or "Unknown"
                    for r in results
                ]
                latency_ms = round(elapsed * 1000, 1)
                top_faiss = 0.0  # RRF results carry fusion scores, not raw FAISS
            else:
                # Fetch the same candidate depth the fused mode uses and apply the same
                # metadata filter, then cut to k. Without this the single-lane baselines
                # are scored on raw engine output while RRF is scored on filtered output,
                # so the three modes are not compared over the same document population:
                # a customer record could occupy a baseline's top-5 but never RRF's.
                engine = builder.bm25_engine if mode == "bm25" else builder.vector_engine
                raw, elapsed = run_standalone_search(engine, query, k=15)
                raw = by_menu_metadata(raw)[:5]
                retrieved_names = _extract_names(raw)
                latency_ms = round(elapsed * 1000, 1)
                top_faiss = raw[0][1] if raw else 0.0

            metrics = calculate_metrics(retrieved_names, expected)
            case_result["modes"][mode] = {
                "retrieved": retrieved_names,
                "metrics": metrics,
                "latency_ms": latency_ms,
                "top_faiss_raw": round(float(top_faiss), 4),
            }

            pm = per_mode[mode]
            pm["total"] += 1
            pm["precision"] += metrics["precision"]
            pm["recall"] += metrics["recall"]
            pm["mrr"] += metrics["mrr"]
            pm["hit_rate"] += metrics["hit_rate"]
            pm["latencies"].append(latency_ms)

            pd = per_difficulty[mode][difficulty]
            pd["total"] += 1
            pd["precision"] += metrics["precision"]
            pd["recall"] += metrics["recall"]
            pd["mrr"] += metrics["mrr"]
            pd["hit_rate"] += metrics["hit_rate"]

            log(f"    [{mode.upper()}] P@5={metrics['precision']:.3f} R@5={metrics['recall']:.3f} "
                f"MRR={metrics['mrr']:.3f} Hit={metrics['hit_rate']} ({latency_ms:.0f}ms) "
                f"-> {retrieved_names}")

        # Gatekeeper — uses the raw vector engine scores, independent of fusion
        gk = gatekeeper_check(builder.bm25_engine, builder.vector_engine, query)
        gatekeeper_results.append(gk)
        log(f"    [Gatekeeper] raw_top={gk['raw_top']:.4f} cos={gk['cos_sim']:.4f} "
            f"semantic={gk['semantic_pass']} lexical={gk['lexical_pass']} "
            f"passed={gk['passed']} matched={gk['matched_terms']} "
            f"(bm25_top={gk['bm25_top_doc_name']}, faiss_top={gk['vector_top_doc_name']})")

        detailed.append(case_result)

    # --- Aggregate ---
    log(f"\n{'='*60}")
    log("PER-MODE SUMMARY")
    log(f"{'='*60}")

    for mode in MODES:
        pm = per_mode[mode]
        n = pm["total"]
        log(f"  {mode.upper()} (n={n}):")
        log(f"    P@5:   {pm['precision']/n:.4f}")
        log(f"    R@5:   {pm['recall']/n:.4f}")
        log(f"    MRR:   {pm['mrr']/n:.4f}")
        log(f"    Hit:   {pm['hit_rate']/n:.4f}")
        lats = sorted(pm["latencies"])
        log(f"    Latency p50: {percentile(lats, 50):.1f} ms  p95: {percentile(lats, 95):.1f} ms")

    log(f"\n{'='*60}")
    log("PER-DIFFICULTY BREAKDOWN")
    log(f"{'='*60}")
    for mode in ["rrf"]:
        log(f"  {mode.upper()}:")
        for diff in sorted(per_difficulty[mode].keys()):
            d = per_difficulty[mode][diff]
            n = d["total"]
            log(f"    {diff} (n={n}): P@5={d['precision']/n:.4f}  R@5={d['recall']/n:.4f}  "
                f"MRR={d['mrr']/n:.4f}  Hit={d['hit_rate']/n:.4f}")

    # --- Gatekeeper summary ---
    gk_passed = sum(1 for g in gatekeeper_results if g["passed"])
    gk_sem_only = sum(1 for g in gatekeeper_results if g["semantic_pass"] and not g["lexical_pass"])
    gk_lex_only = sum(1 for g in gatekeeper_results if g["lexical_pass"] and not g["semantic_pass"])
    gk_both = sum(1 for g in gatekeeper_results if g["semantic_pass"] and g["lexical_pass"])
    gk_neither = sum(1 for g in gatekeeper_results if not g["semantic_pass"] and not g["lexical_pass"])

    log(f"\n{'='*60}")
    log("GATEKEEPER SUMMARY")
    log(f"{'='*60}")
    log(f"  Queries:              {len(gatekeeper_results)}")
    log(f"  Passed (allowed):     {gk_passed}")
    log(f"  Rejected (blocked):   {gk_neither}")
    log(f"  Semantic-only pass:   {gk_sem_only}")
    log(f"  Lexical-only pass:    {gk_lex_only}")
    log(f"  Both pass:            {gk_both}")

    # --- JSON report ---
    report = {
        "timestamp": TS,
        "summary": {
            "modes": {
                mode: {
                    k: round(v / pm["total"], 4) if k not in ("total", "latencies") and pm["total"] > 0 else v
                    for k, v in pm.items()
                    if k != "latencies"
                } | {
                    "latency_p50_ms": round(percentile(pm["latencies"], 50), 1),
                    "latency_p95_ms": round(percentile(pm["latencies"], 95), 1),
                }
                for mode, pm in per_mode.items()
            },
            "per_difficulty": {
                mode: {
                    diff: {
                        k: round(v / d["total"], 4) if d["total"] > 0 else v
                        for k, v in d.items()
                    }
                    for diff, d in diffs.items()
                }
                for mode, diffs in per_difficulty.items()
            },
            "gatekeeper": {
                "total": len(gatekeeper_results),
                "passed": gk_passed,
                "rejected": gk_neither,
                "semantic_only": gk_sem_only,
                "lexical_only": gk_lex_only,
                "both": gk_both,
            },
        },
        "detailed": detailed,
        "gatekeeper_details": gatekeeper_results,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    log(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
