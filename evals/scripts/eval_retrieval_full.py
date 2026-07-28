"""Retrieval Evaluator — per-difficulty breakdown, BM25-only and FAISS-only standalone
modes, RRF fusion, and dual-lane gatekeeper analysis.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_retrieval_full.py
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
from src.agent_brain.config import settings
from evals.lib.stats import percentile

EVAL_DATA_PATH = settings.PROJECT_ROOT / "evals" / "data" / "retrieval" / "retrieval_eval.json"
RESULTS_DIR = settings.PROJECT_ROOT / "evals" / "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = RESULTS_DIR / f"retrieval_full_{TS}.log"
REPORT_PATH = RESULTS_DIR / f"retrieval_full_{TS}.json"

GATEKEEPER_SEMANTIC_THRESHOLD = 0.35
MODES = ["bm25", "faiss", "rrf"]


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


def gatekeeper_check(vector_engine, query: str) -> dict:
    """Dual-lane gatekeeper: query the vector engine directly for its raw top-1 score
    (before any fusion), then check lexical match against the top document.

    This is the same logic as the production gatekeeper in rrf.py: semantic pass when
    the raw FAISS score (converted to cosine via the active model's profile) reaches
    the threshold, lexical pass when a query keyword appears in the top-ranked
    document's content."""
    raw_results, _ = run_standalone_search(vector_engine, query, k=1)
    raw_top = raw_results[0][1] if raw_results else 0.0
    cos_sim = _raw_score_to_cosine(raw_top)
    semantic_pass = cos_sim >= GATEKEEPER_SEMANTIC_THRESHOLD

    query_lower = query.lower().replace("?", "").replace(".", "")
    keywords = [kw.strip() for kw in query_lower.split(",") if kw.strip()]
    if len(keywords) == 1 and " " in keywords[0]:
        keywords = [w.strip() for w in keywords[0].split() if w.strip()]

    lexical_pass = False
    if keywords:
        top_docs_text = ""
        if raw_results:
            top_docs_text += raw_results[0][0].page_content.lower()
        if any(kw in top_docs_text for kw in keywords):
            lexical_pass = True

    passed = semantic_pass or lexical_pass

    return {
        "semantic_pass": bool(semantic_pass),
        "lexical_pass": bool(lexical_pass),
        "passed": bool(passed),
        "raw_top": round(float(raw_top), 4),
        "cos_sim": round(float(cos_sim), 4),
        "top_doc_name": str(raw_results[0][0].metadata.get("name", "?")) if raw_results else "?",
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
        retriever.search("warmup", k=5, mode="rrf") if _m == "rrf" else None
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
            if mode == "rrf":
                start = time.time()
                results = retriever.search(query, k=5, mode="rrf")
                elapsed = time.time() - start
                retrieved_names = [
                    r.document.metadata.get("name") or r.document.metadata.get("title") or "Unknown"
                    for r in results
                ]
                latency_ms = round(elapsed * 1000, 1)
                top_faiss = 0.0  # RRF results carry fusion scores, not raw FAISS
            else:
                engine = builder.bm25_engine if mode == "bm25" else builder.vector_engine
                raw, elapsed = run_standalone_search(engine, query, k=5)
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
        gk = gatekeeper_check(builder.vector_engine, query)
        gatekeeper_results.append(gk)
        log(f"    [Gatekeeper] raw_top={gk['raw_top']:.4f} cos={gk['cos_sim']:.4f} "
            f"semantic={gk['semantic_pass']} lexical={gk['lexical_pass']} "
            f"passed={gk['passed']} (top_doc={gk['top_doc_name']})")

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
