"""Production-level retrieval eval — passes raw queries through the search_worker LLM
before calling the retriever.

The existing eval_retrieval_full.py tests the retriever in ISOLATION (raw user
utterances fed directly to RetrieverManager). In production, the search_worker LLM
rewrites vibe/feeling queries into keyword-rich search terms:

    User: "trời lạnh, muốn ăn gì ấm bụng"
      → search_worker LLM: search(query="cháo, lẩu, súp nóng, món ấm bụng")
      → retriever: gets keyword-rich vector → better results

This script bridges that gap by running the LLM rewrite step before retrieval.

Usage:
    # Raw mode (same as eval_retrieval_full.py — no LLM, for local)
    PYTHONPATH=. uv run python evals/scripts/eval_retrieval_with_rewrite.py

    # Rewrite mode (with LLM — production-realistic)
    PYTHONPATH=. uv run python evals/scripts/eval_retrieval_with_rewrite.py --rewrite

    # Specific dataset
    PYTHONPATH=. uv run python evals/scripts/eval_retrieval_with_rewrite.py --rewrite --dataset retrieval_eval_v2.json
"""
from __future__ import annotations

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
from src.agent_brain.services.retriever.fusion.rrf import gate_decision
from src.agent_brain.services.retriever.filters import by_menu_metadata
from src.agent_brain.services.retriever.indices.embeddings import get_profile
from src.agent_brain.config import settings
from src.agent_brain.utils.prompt_utils import (
    build_system_prompt,
    build_few_shot_examples,
    build_dynamic_suffix,
)
from evals.lib.stats import percentile

RESULTS_DIR = settings.PROJECT_ROOT / "evals" / "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

_dataset_arg = None
_use_rewrite = False
_args = sys.argv[1:]
for i, a in enumerate(_args):
    if a == "--dataset" and i + 1 < len(_args):
        _dataset_arg = _args[i + 1]
    if a == "--rewrite":
        _use_rewrite = True

EVAL_DATA_PATH = settings.PROJECT_ROOT / "evals" / "data" / "retrieval" / (_dataset_arg or "retrieval_eval.json")

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
_tag = Path(EVAL_DATA_PATH).stem
_mode = "rewrite" if _use_rewrite else "raw"
LOG_PATH = RESULTS_DIR / f"retrieval_{_mode}_{_tag}_{TS}.log"
REPORT_PATH = RESULTS_DIR / f"retrieval_{_mode}_{_tag}_{TS}.json"

MODES = ["bm25", "faiss", "rrf"]


def log(msg: str):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _get_rewrite_model():
    """Lazy-load the search_worker's ChatOllama model (same as production)."""
    from langchain_ollama import ChatOllama
    from src.agent_brain.agent.tools import delegate, search
    return ChatOllama(
        model=settings.WORKER_MODEL,
        temperature=0.1,
        num_ctx=settings.LLM_NUM_CTX,
        keep_alive=settings.llm_keep_alive,
        metadata={"ls_model_name": settings.WORKER_MODEL, "ls_provider": "ollama"},
    ).bind_tools([delegate, search], tool_choice="any")


_rewrite_model = None
_rewrite_messages_cache: list | None = None


def _build_rewrite_input(user_query: str) -> list:
    """Build the exact same input messages the search_worker LLM receives."""
    global _rewrite_messages_cache
    if _rewrite_messages_cache is None:
        static_system = build_system_prompt("search_agent.md")
        static_few_shot = build_few_shot_examples("search_worker.json")
        _rewrite_messages_cache = [static_system] + static_few_shot
    dynamic_suffix = build_dynamic_suffix(table_id="eval", dynamic_context=None)
    from langchain_core.messages import HumanMessage
    return _rewrite_messages_cache + [dynamic_suffix, HumanMessage(content=user_query)]


def rewrite_query(user_query: str) -> dict:
    """Call the search_worker LLM to rewrite a raw query.

    Returns {"query": str, "max_price": float|None, "min_price": float|None}
    or {"query": user_query, ...} on fallback.
    """
    global _rewrite_model
    if _rewrite_model is None:
        _rewrite_model = _get_rewrite_model()

    fallback = {"query": user_query, "max_price": None, "min_price": None}
    try:
        messages = _build_rewrite_input(user_query)
        response = _rewrite_model.invoke(messages)
    except Exception as e:
        log(f"    [LLM rewrite error: {e}]")
        return fallback

    if not response.tool_calls:
        log(f"    [LLM produced no tool_calls — using raw query]")
        return fallback

    for tc in response.tool_calls:
        if tc.get("name") == "search":
            args = tc.get("args", {})
            return {
                "query": args.get("query", user_query),
                "max_price": args.get("max_price"),
                "min_price": args.get("min_price"),
            }
        elif tc.get("name") == "delegate":
            reason = tc.get("args", {}).get("reason", "")
            log(f"    [LLM delegated: {reason}]")
            return fallback

    return fallback


def calculate_metrics(retrieved_names: list[str], expected_relevant: list[str], k: int = 5):
    expected_lower = [e.lower() for e in expected_relevant]
    retrieved_lower = [r.lower() for r in retrieved_names]

    hits = [r for r in retrieved_lower if r in expected_lower]
    precision = len(hits) / len(retrieved_lower) if retrieved_lower else (0.0 if expected_lower else 0.0)
    recall = len(hits) / len(expected_lower) if expected_lower else (0.0 if not retrieved_lower else 0.0)
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
    start = time.time()
    results = engine.search(query, k=k)
    elapsed = time.time() - start
    return results, elapsed


def _extract_names(results):
    names = []
    seen = set()
    for doc, _score in results:
        name = doc.metadata.get("name") or doc.metadata.get("title") or "Unknown"
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def main():
    mode_label = "WITH LLM REWRITE" if _use_rewrite else "RAW QUERY (no rewrite)"
    log(f"RETRIEVAL EVALUATION — {mode_label}")
    log(f"Dataset: {EVAL_DATA_PATH}")
    log(f"Model: {settings.WORKER_MODEL}" if _use_rewrite else "Model: (not used in raw mode)")

    if not EVAL_DATA_PATH.exists():
        log(f"ERROR: Dataset not found at {EVAL_DATA_PATH}")
        sys.exit(1)

    with open(EVAL_DATA_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    cases = dataset.get("cases", [])
    log(f"Loaded {len(cases)} test cases")

    builder = IndexBuilder()
    if not builder.load_database():
        log("Building indices...")
        data_path = settings.PROJECT_ROOT / "assets" / "data"
        builder.build([str(data_path)])

    retriever = RetrieverManager(
        vector_engine=builder.vector_engine,
        bm25_engine=builder.bm25_engine,
    )

    log("Warming embedding model and indices ...")
    for _m in ["rrf"]:
        retriever.search("warmup", k=5, mode="rrf")
    run_standalone_search(builder.vector_engine, "warmup", k=5)
    run_standalone_search(builder.bm25_engine, "warmup", k=5)
    log("Warm-up complete.")

    per_mode = {m: {"total": 0, "precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0, "latencies": []}
                for m in MODES}
    per_difficulty = {m: defaultdict(lambda: {"total": 0, "precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0})
                      for m in MODES}
    per_stratum = {m: defaultdict(lambda: {"total": 0, "precision": 0.0, "recall": 0.0, "mrr": 0.0, "hit_rate": 0.0})
                   for m in MODES}
    gatekeeper_results = []
    detailed = []

    for case in cases:
        raw_query = case["query"]
        case_id = case["id"]
        difficulty = case.get("difficulty", "unknown")
        stratum = case.get("rewrite_stratum", "unknown")
        expected = case["expected_relevant"]

        if _use_rewrite:
            rewritten = rewrite_query(raw_query)
            search_query = rewritten["query"]
            max_price = rewritten.get("max_price")
            min_price = rewritten.get("min_price")
            query_label = f"'{raw_query}' → LLM: '{search_query}'"
            if max_price or min_price:
                query_label += f" [price: {min_price}-{max_price}]"
        else:
            search_query = raw_query
            max_price = None
            min_price = None
            query_label = f"'{raw_query}' (no rewrite)"

        log(f"\n  [{case_id}] {difficulty:6s} {query_label}")
        log(f"    Expected relevant ({len(expected)}): {expected[:5]}{'...' if len(expected) > 5 else ''}")

        case_result = {"id": case_id, "raw_query": raw_query, "difficulty": difficulty,
                       "rewrite_stratum": stratum, "modes": {}}
        if _use_rewrite:
            case_result["search_query"] = search_query

        for mode in MODES:
            if mode == "rrf":
                start = time.time()
                results = retriever.search(
                    search_query, k=5, mode="rrf",
                    max_price=max_price, min_price=min_price,
                )
                elapsed = time.time() - start
                retrieved_names = [
                    r.document.metadata.get("name") or r.document.metadata.get("title") or "Unknown"
                    for r in results
                ]
                latency_ms = round(elapsed * 1000, 1)
            else:
                engine = builder.bm25_engine if mode == "bm25" else builder.vector_engine
                raw, elapsed = run_standalone_search(engine, search_query, k=15)
                raw = by_menu_metadata(raw, max_price=max_price, min_price=min_price)[:5]
                retrieved_names = _extract_names(raw)
                latency_ms = round(elapsed * 1000, 1)

            metrics = calculate_metrics(retrieved_names, expected)
            case_result["modes"][mode] = {
                "retrieved": retrieved_names,
                "metrics": metrics,
                "latency_ms": latency_ms,
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

            ps = per_stratum[mode][stratum]
            ps["total"] += 1
            ps["precision"] += metrics["precision"]
            ps["recall"] += metrics["recall"]
            ps["mrr"] += metrics["mrr"]
            ps["hit_rate"] += metrics["hit_rate"]

            log(f"    [{mode.upper()}] P@5={metrics['precision']:.3f} R@5={metrics['recall']:.3f} "
                f"MRR={metrics['mrr']:.3f} Hit={metrics['hit_rate']} ({latency_ms:.0f}ms) "
                f"→ {retrieved_names}")

        # Gatekeeper
        bm25_results, _ = run_standalone_search(builder.bm25_engine, search_query, k=15)
        vector_results, _ = run_standalone_search(builder.vector_engine, search_query, k=15)
        bm25_results = by_menu_metadata(bm25_results, max_price=max_price, min_price=min_price)
        vector_results = by_menu_metadata(vector_results, max_price=max_price, min_price=min_price)
        gate = gate_decision(bm25_results, vector_results, search_query)
        gatekeeper_results.append({
            "semantic_pass": gate["semantic_pass"],
            "lexical_pass": gate["lexical_pass"],
            "passed": gate["passed"],
            "cos_sim": round(gate["cos_sim"], 4),
            "matched_terms": gate["matched_terms"],
            "bm25_top": str(bm25_results[0][0].metadata.get("name", "?")) if bm25_results else "?",
            "faiss_top": str(vector_results[0][0].metadata.get("name", "?")) if vector_results else "?",
        })

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
    log("PER-DIFFICULTY BREAKDOWN (RRF)")
    log(f"{'='*60}")
    for diff in sorted(per_difficulty["rrf"].keys()):
        d = per_difficulty["rrf"][diff]
        n = d["total"]
        log(f"    {diff} (n={n}): P@5={d['precision']/n:.4f}  R@5={d['recall']/n:.4f}  "
            f"MRR={d['mrr']/n:.4f}  Hit={d['hit_rate']/n:.4f}")

    log(f"\n{'='*60}")
    log("PER-STRATUM BREAKDOWN (RRF)")
    log(f"{'='*60}")
    log(f"  {'Stratum':<22s} {'n':>3s}  {'P@5':>6s}  {'R@5':>6s}  {'MRR':>6s}  {'Hit':>6s}")
    log(f"  {'-'*22} {'---'}  {'------'}  {'------'}  {'------'}  {'------'}")
    for s in sorted(per_stratum["rrf"].keys()):
        d = per_stratum["rrf"][s]
        n = d["total"]
        log(f"  {s:<22s} {n:>3d}  {d['precision']/n:>6.4f}  {d['recall']/n:>6.4f}  "
            f"{d['mrr']/n:>6.4f}  {d['hit_rate']/n:>6.4f}")

    gk_passed = sum(1 for g in gatekeeper_results if g["passed"])
    gk_rejected = sum(1 for g in gatekeeper_results if not g["passed"])
    log(f"\n{'='*60}")
    log("GATEKEEPER SUMMARY")
    log(f"{'='*60}")
    log(f"  Queries:   {len(gatekeeper_results)}")
    log(f"  Passed:    {gk_passed}")
    log(f"  Rejected:  {gk_rejected}")

    report = {
        "timestamp": TS,
        "mode": "rewrite" if _use_rewrite else "raw",
        "summary": {
            "modes": {
                mode: {
                    # "total" is the denominator, not a metric: dividing it by itself wrote 1.0
                    # into every result file instead of the case count.
                    k: round(v / pm["total"], 4) if k not in ("latencies", "total") and pm["total"] > 0 else v
                    for k, v in pm.items() if k != "latencies"
                } | {
                    "latency_p50_ms": round(percentile(pm["latencies"], 50), 1),
                    "latency_p95_ms": round(percentile(pm["latencies"], 95), 1),
                }
                for mode, pm in per_mode.items()
            },
            "per_difficulty": {
                mode: {
                    diff: {
                        k: round(v / d["total"], 4) if k != "total" and d["total"] > 0 else v
                        for k, v in d.items()
                    }
                    for diff, d in diffs.items()
                }
                for mode, diffs in per_difficulty.items()
            },
            "per_stratum": {
                mode: {
                    s: {
                        k: round(v / d["total"], 4) if k != "total" and d["total"] > 0 else v
                        for k, v in d.items()
                    }
                    for s, d in strata.items()
                }
                for mode, strata in per_stratum.items()
            },
            "gatekeeper": {
                "total": len(gatekeeper_results),
                "passed": gk_passed,
                "rejected": gk_rejected,
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
