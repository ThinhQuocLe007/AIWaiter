"""Enhanced Retrieval Evaluator — extends eval_retrieval.py with per-difficulty
breakdown, BM25-only and FAISS-only standalone modes, and gatekeeper behavior analysis.

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
from src.agent_brain.config import settings

EVAL_DATA_PATH = settings.PROJECT_ROOT / "evals" / "data" / "retrieval" / "retrieval_eval.json"
RESULTS_DIR = settings.PROJECT_ROOT / "evals" / "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = RESULTS_DIR / f"retrieval_full_{TS}.log"
REPORT_PATH = RESULTS_DIR / f"retrieval_full_{TS}.json"

GATEKEEPER_SEMANTIC_THRESHOLD = 0.35


def log(msg: str):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def calculate_metrics(retrieved_names: list[str], expected_relevant: list[str], k: int = 5):
    expected_lower = [e.lower() for e in expected_relevant]
    retrieved_lower = [r.lower() for r in retrieved_names]

    hits = [r for r in retrieved_lower if r in expected_lower]
    precision = len(hits) / len(retrieved_lower) if retrieved_lower else 0
    recall = len(hits) / len(expected_lower) if expected_lower else 0
    hit_rate = 1 if hits else 0

    mrr = 0.0
    for i, name in enumerate(retrieved_lower):
        if name in expected_lower:
            mrr = 1.0 / (i + 1)
            break

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "mrr": round(mrr, 4),
        "hit_rate": hit_rate,
        "retrieved": retrieved_names,
        "hits": hits,
    }


def gatekeeper_check(retrieved_docs: list, query: str, top_faiss_score: float) -> dict:
    """Dual-lane gatekeeper: semantic (FAISS score) OR lexical (query keyword in doc text)."""
    query_lower = query.lower()
    query_words = set(query_lower.split())

    lexical_pass = False
    for doc in retrieved_docs[:5]:
        doc_text = " ".join(str(v).lower() for v in doc.document.metadata.values())
        for word in query_words:
            if len(word) >= 3 and word in doc_text:
                lexical_pass = True
                break
        if lexical_pass:
            break

    semantic_pass = top_faiss_score >= GATEKEEPER_SEMANTIC_THRESHOLD
    passed = semantic_pass or lexical_pass

    return {
        "semantic_pass": semantic_pass,
        "lexical_pass": lexical_pass,
        "passed": passed,
        "top_faiss_score": round(top_faiss_score, 4),
    }


def main():
    log("ENHANCED RETRIEVAL EVALUATION")

    if not EVAL_DATA_PATH.exists():
        log(f"ERROR: Dataset not found at {EVAL_DATA_PATH}")
        sys.exit(1)

    with open(EVAL_DATA_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    cases = dataset.get("cases", [])
    log(f"Loaded {len(cases)} test cases from {EVAL_DATA_PATH.name}")

    # Init retriever
    builder = IndexBuilder()
    if not builder.load_database():
        log("Building indices...")
        data_path = settings.PROJECT_ROOT / "assets" / "data"
        builder.build([str(data_path)])

    retriever = RetrieverManager(
        vector_engine=builder.vector_engine,
        bm25_engine=builder.bm25_engine,
    )

    # Results accumulators
    per_difficulty = defaultdict(lambda: {"total": 0, "precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0})
    per_mode = {
        "rrf": {"total": 0, "precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0},
    }
    gatekeeper_results = []
    detailed = []

    for case in cases:
        query = case["query"]
        case_id = case["id"]
        difficulty = case.get("difficulty", "unknown")
        expected = case["expected_relevant"]
        expected_irrelevant = case.get("expected_irrelevant", [])

        log(f"\n  [{case_id}] '{query}' (difficulty={difficulty})")
        log(f"    Expected relevant: {expected}")

        case_result = {"id": case_id, "query": query, "difficulty": difficulty, "modes": {}}

        for mode in ["rrf"]:
            start = time.time()
            results = retriever.search(query, k=5, mode=mode)
            elapsed = time.time() - start

            retrieved_names = []
            top_faiss = 0.0
            for r in results:
                name = r.document.metadata.get("name") or r.document.metadata.get("title") or "Unknown"
                retrieved_names.append(name)
                if not top_faiss and hasattr(r, "score"):
                    top_faiss = float(r.score) if mode == "faiss" else 0.0

            metrics = calculate_metrics(retrieved_names, expected)
            case_result["modes"][mode] = {
                "retrieved": retrieved_names,
                "metrics": metrics,
                "latency_ms": round(elapsed * 1000, 1),
            }

            pm = per_mode[mode]
            pm["total"] += 1
            pm["precision"] += metrics["precision"]
            pm["recall"] += metrics["recall"]
            pm["mrr"] += metrics["mrr"]
            pm["hit_rate"] += metrics["hit_rate"]

            pd = per_difficulty[difficulty]
            if mode == "rrf":
                pd["total"] += 1
                pd["precision"] += metrics["precision"]
                pd["recall"] += metrics["recall"]
                pd["mrr"] += metrics["mrr"]
                pd["hit_rate"] += metrics["hit_rate"]

            log(f"    [{mode.upper()}] P@5={metrics['precision']:.3f} R@5={metrics['recall']:.3f} MRR={metrics['mrr']:.3f} Hit={metrics['hit_rate']} ({elapsed*1000:.0f}ms) -> {retrieved_names}")

            # Gatekeeper on RRF mode
            if mode == "rrf":
                gk = gatekeeper_check(results, query, top_faiss)
                gatekeeper_results.append(gk)
                log(f"    [Gatekeeper] semantic={gk['semantic_pass']} lexical={gk['lexical_pass']} -> passed={gk['passed']}")

            if metrics["hit_rate"] == 0:
                log(f"    [MISS] Expected: {expected}")

        detailed.append(case_result)

    # Aggregate
    log(f"\n{'='*60}")
    log("PER-MODE SUMMARY")
    log(f"{'='*60}")

    for mode in ["rrf"]:
        pm = per_mode[mode]
        n = pm["total"]
        log(f"  {mode.upper()}:")
        log(f"    Precision@5: {pm['precision']/n:.4f}")
        log(f"    Recall@5:    {pm['recall']/n:.4f}")
        log(f"    MRR:         {pm['mrr']/n:.4f}")
        log(f"    Hit Rate:    {pm['hit_rate']/n:.4f}")

    log(f"\n{'='*60}")
    log("PER-DIFFICULTY BREAKDOWN (RRF)")
    log(f"{'='*60}")
    for diff in sorted(per_difficulty.keys()):
        d = per_difficulty[diff]
        n = d["total"]
        log(f"  {diff} (n={n}):")
        log(f"    P@5={d['precision']/n:.4f}  R@5={d['recall']/n:.4f}  MRR={d['mrr']/n:.4f}  Hit={d['hit_rate']/n:.4f}")

    # Gatekeeper summary
    gk_passed = sum(1 for g in gatekeeper_results if g["passed"])
    gk_rejected = sum(1 for g in gatekeeper_results if not g["passed"])
    gk_sem_only = sum(1 for g in gatekeeper_results if g["semantic_pass"] and not g["lexical_pass"])
    gk_lex_only = sum(1 for g in gatekeeper_results if g["lexical_pass"] and not g["semantic_pass"])
    gk_both = sum(1 for g in gatekeeper_results if g["semantic_pass"] and g["lexical_pass"])
    gk_neither = sum(1 for g in gatekeeper_results if not g["semantic_pass"] and not g["lexical_pass"])

    log(f"\n{'='*60}")
    log("GATEKEEPER SUMMARY")
    log(f"{'='*60}")
    log(f"  Queries:              {len(gatekeeper_results)}")
    log(f"  Passed (allowed):     {gk_passed}")
    log(f"  Rejected (blocked):   {gk_rejected}")
    log(f"  Semantic-only pass:   {gk_sem_only}")
    log(f"  Lexical-only pass:    {gk_lex_only}")
    log(f"  Both pass:            {gk_both}")
    log(f"  Neither (rejected):   {gk_neither}")

    report = {
        "timestamp": TS,
        "summary": {
            "modes": {
                mode: {
                    k.replace("_", "_"): (
                        round(v / pm["total"], 4) if k != "total" and pm["total"] > 0 else v
                    )
                    for k, v in pm.items()
                }
                for mode, pm in per_mode.items()
            },
            "per_difficulty": {
                diff: {
                    k: round(v / d["total"], 4) if d["total"] > 0 else v
                    for k, v in d.items()
                }
                for diff, d in per_difficulty.items()
            },
            "gatekeeper": {
                "total": len(gatekeeper_results),
                "passed": gk_passed,
                "rejected": gk_rejected,
                "semantic_only": gk_sem_only,
                "lexical_only": gk_lex_only,
                "both": gk_both,
                "neither": gk_neither,
            },
        },
        "detailed": detailed,
        "gatekeeper_details": gatekeeper_results,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
