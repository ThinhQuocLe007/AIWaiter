#!/usr/bin/env python3
"""Five-arm ablation of the intent routing layer (thesis §5.4.1).

Every arm is scored on the *same* items in a single pass, so the comparisons are paired and
McNemar's exact test applies. Running the arms in separate passes would force the much weaker
comparison of two independent accuracy figures, which cannot resolve a five-point difference
at the sample sizes available here.

    Arm  Name       What it isolates
    ---  ---------  -----------------------------------------------------------------
    A    centroid   Unsupervised semantic baseline (cosine to intent centroids)
    B    slm        Prompted classification by a small model, no semantic prefilter
    C    hybrid     Semantic -> rewriter -> SLM: the system this thesis replaces
    D    mlp        Trained text-only MLP  (PROPOSED)
    F    llm        Prompted classification by the 14B deployment model

D vs C is the arm that earns the contribution: it compares the proposed router against the
system it replaces, on identical items. D vs A shows the supervised model beating the
unsupervised baseline. D vs F sets the accuracy ceiling and, read with the latency column,
states the real claim: comparable accuracy at a small fraction of the cost.

There is no with/without-context pair. The v2 classifier is text-only and predict.classify()
ignores the `state` argument, so such a pair would run identical code and return identical
labels by construction. Removing the v1 context block is a design decision, not a measured
ablation, and the thesis reports it as one.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_router_arms.py
    PYTHONPATH=. uv run python evals/scripts/eval_router_arms.py --arms D F --runs 5
    PYTHONPATH=. uv run python evals/scripts/eval_router_arms.py --dataset holdout
    PYTHONPATH=. uv run python evals/scripts/eval_router_arms.py --dataset all --json out.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from evals.lib.stats import (  # noqa: E402
    LatencySummary,
    Proportion,
    compare_paired,
    fmt_proportion,
    markdown_table,
)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("router_arms")

DATA_DIR = PROJECT_ROOT / "evals" / "data" / "router"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
SAVED_DIR = PROJECT_ROOT / "src" / "training_semantic_router" / "classifier" / "saved_v2"
HOLDOUT_PATH = PROJECT_ROOT / "src" / "training_semantic_router" / "data" / "test_holdout.json"

# Only the single-intent sets are pooled. Three files were retired on 2026-07-31 and are kept on
# disk rather than deleted:
#   router_eval.json          v1 hybrid-router set, 5 labels. 32 of its 39 single-intent cases are
#                             already in single_intent_eval and 29 in semantic_eval, so it added 2
#                             utterances the other two did not have.
#   router_context_eval.json  superseded prototype of context_dependent_eval, 21 cases over 14
#                             unique utterances, and the only source of conflicting labels.
#   context_dependent_eval.json
#                             61 pairs of one utterance at two order stages with different labels.
#                             A text-only router cannot exceed 62/123 on it by construction, so
#                             pooling it capped every arm at ~50 % on a third of the set. The router
#                             is text-only by design and order stage is enforced downstream by the
#                             validator, so the property is out of scope here.
DATASETS = {
    "single": DATA_DIR / "single_intent_eval.json",
    "semantic": DATA_DIR / "semantic_eval.json",
    "holdout": HOLDOUT_PATH,
}

# The trained classifier predicts four classes; ORDER_CONFIRM is a sub-case of ORDER and is
# merged before scoring so that all five arms are graded against the same label set.
LABELS = ["ORDER", "SEARCH", "PAYMENT", "CHAT"]
MERGE = {"ORDER_CONFIRM": "ORDER"}

# Arm B is deliberately a *small* model and arm F the deployment model, so the pair brackets
# the prompted-classifier approach by capacity while holding the prompt fixed.
SLM_MODEL = "qwen2.5:3b"
# Deployment runs qwen2.5:14b-instruct-q6_K. This development machine cannot hold it, so arm F is
# measured against the 7B instruct model instead and the reported figures are re-taken on the
# server before they reach the thesis. The 7B result is a lower bound on the deployment model.
LLM_MODEL = "qwen2.5:7b-instruct"

PROMPT = """Bạn là bộ phân loại ý định cho một nhà hàng hải sản Việt Nam.
Phân loại câu nói của khách vào ĐÚNG MỘT nhãn:

ORDER — gọi món, thêm/bớt/đổi/hủy món, xác nhận chốt đơn.
SEARCH — hỏi thông tin: giá, món ăn, nguyên liệu, vị, thực đơn, giờ mở cửa, khuyến mãi, giao hàng.
PAYMENT — thanh toán, tính tiền, hóa đơn, chuyển khoản, mã QR, tổng tiền.
CHAT — chào hỏi, cảm ơn, tán gẫu, phàn nàn, câu không thuộc ba nhãn trên.

Chỉ trả lời bằng một từ: ORDER, SEARCH, PAYMENT hoặc CHAT."""


# --------------------------------------------------------------------------------------
# Dataset loading
# --------------------------------------------------------------------------------------


def canon(label: str) -> str:
    return MERGE.get(label, label)


def load_cases(names: list[str]) -> list[dict[str, Any]]:
    """Load and normalise cases from one or more router datasets.

    The four files disagree on field names (`input`/`expected_route` vs `utterance`/`intent`)
    because they were written at different points in the project; normalising here keeps that
    history out of the scoring code. Multi-intent cases are dropped: three of the five arms emit
    a single label by construction, so including them would score arms on different tasks.
    """
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in names:
        path = DATASETS[name]
        raw = json.loads(path.read_text(encoding="utf-8"))
        for c in raw["cases"]:
            utterance = c.get("input") or c.get("utterance") or ""
            expected = c.get("expected_route", c.get("intent"))
            if isinstance(expected, list):
                continue  # multi-intent: not a single-label task
            ctx = c.get("context") or ({"order_stage": c["order_stage"]} if c.get("order_stage") else None)
            # The key must include the order stage. router_context_eval deliberately repeats one
            # utterance across several stages -- "ok" is CHAT at IDLE but ORDER at
            # AWAITING_CONFIRMATION -- and those pairs are the whole point of the context
            # ablation. Keying on text alone silently deleted a third of that dataset.
            key = (utterance.strip().lower(), (ctx or {}).get("order_stage", ""))
            if key in seen:
                continue  # holdout is derived from router_eval; de-duplicate on genuine overlap
            seen.add(key)
            cases.append(
                {
                    "id": c.get("id", f"{name}-{len(cases)}"),
                    "dataset": name,
                    "utterance": utterance,
                    "expected": canon(expected),
                    "difficulty": c.get("difficulty", "?"),
                    "context": ctx,
                }
            )
    return cases


# --------------------------------------------------------------------------------------
# The five arms
# --------------------------------------------------------------------------------------


def arm_centroid(case: dict) -> str:
    """A — cosine similarity to per-intent centroids, argmax above the 0.35 floor."""
    from src.agent_brain.agent.nodes.semantic_router_node import get_router

    result = get_router().route(case["utterance"])
    return canon(result.get("intent") or "CHAT")


def _build_state(case: dict) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage

    state: dict[str, Any] = {
        "messages": [HumanMessage(content=case["utterance"])],
        "current_intents": [],
        "routing_meta": None,
        "intent_queries": None,
        "table_id": "",
        "table_context": None,
        "active_cart": None,
        "order_stage": "IDLE",
        "search_context": None,
        "is_valid": True,
        "feedback": None,
        "loop_count": 0,
        "unavailable_items": None,
        "ambiguous_items": None,
        "last_tool": None,
        "ui_action": None,
        "order_confirmed": False,
        "response_context": None,
        "delegate_reason": None,
        "shown_dishes": None,
    }
    if case.get("context", {}) and case["context"].get("order_stage"):
        state["order_stage"] = case["context"]["order_stage"]
    return state


def arm_hybrid(case: dict) -> str:
    """C — the previous production router: semantic fast path, rewriter + SLM fallback."""
    from src.agent_brain.agent.nodes.hybrid_router_node import hybrid_router_node

    result = hybrid_router_node(_build_state(case))
    intents = result.get("current_intents") or ["CHAT"]
    return canon(intents[0])


def arm_mlp(case: dict) -> str:
    """D -- the trained text-only MLP, which is the proposed router.

    There is deliberately no with/without-context pair here. The v2 classifier takes a
    768-d sentence embedding and nothing else; predict.classify() accepts a `state` argument
    and ignores it. Two arms differing only in that argument would run the same code and
    return identical labels by construction, which measures nothing. Removing the v1 context
    block is reported as a design decision, not as an ablation result.
    """
    from src.training_semantic_router.classifier.predict import classify

    result = classify(
        case["utterance"],
        model_path=SAVED_DIR / "model.pt",
        label_path=SAVED_DIR / "label_encoder.json",
    )
    return canon(result["intent"])


_prompted_cache: dict[str, Any] = {}


def _prompted(case: dict, model: str, seed: int) -> str:
    """Arms B and F — identical prompt, different model capacity.

    Held at temperature 0 so that the prompted arms are given their best shot rather than a
    handicapped sampled one; the seed still varies across runs because Ollama's greedy decode
    is not bit-identical across calls and the residual spread belongs in the reported range.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    # `seed` is a model parameter, not an invoke kwarg: passing it to invoke() raises
    # TypeError inside the ollama client, which the caller's except clause would quietly
    # convert into a CHAT prediction for every single case. Cache per (model, seed) so the
    # constructor carries it.
    key = f"{model}@{seed}"
    if key not in _prompted_cache:
        _prompted_cache[key] = ChatOllama(
            model=model, temperature=0.0, num_ctx=2048, keep_alive=-1, seed=seed
        )
    llm = _prompted_cache[key]
    reply = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content=case["utterance"])])
    text = (reply.content or "").strip().upper()
    for label in LABELS:  # tolerate "Nhãn: ORDER" and similar preamble
        if label in text:
            return label
    return "CHAT"


ARMS: dict[str, dict[str, Any]] = {
    "A": {"name": "centroid", "label": "Centroid (semantic only)", "fn": lambda c, s: arm_centroid(c), "stochastic": False},
    "B": {"name": "slm", "label": f"SLM only ({SLM_MODEL})", "fn": lambda c, s: _prompted(c, SLM_MODEL, s), "stochastic": True},
    "C": {"name": "hybrid", "label": "Hybrid semantic->SLM (previous)", "fn": lambda c, s: arm_hybrid(c), "stochastic": True},
    "D": {"name": "mlp", "label": "MLP, text-only (PROPOSED)", "fn": lambda c, s: arm_mlp(c), "stochastic": False},
    "F": {"name": "llm", "label": f"LLM zero-shot ({LLM_MODEL})", "fn": lambda c, s: _prompted(c, LLM_MODEL, s), "stochastic": True},
}

# Comparisons that carry an argument in the thesis. Every other pair is reported in the
# accuracy table but not tested, to avoid multiplying hypotheses that nothing depends on.
KEY_PAIRS = [("D", "C"), ("D", "F"), ("D", "A"), ("D", "B")]


# --------------------------------------------------------------------------------------
# GPU memory
# --------------------------------------------------------------------------------------


def gpu_mb() -> float | None:
    """Currently used GPU memory in MB, or None when no NVIDIA GPU is visible."""
    import subprocess

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return float(out.stdout.strip().splitlines()[0])
    except Exception:
        return None


# --------------------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------------------


def run_arm(key: str, cases: list[dict], seed: int) -> dict[str, Any]:
    """Score one arm over every case, recording correctness and per-item latency."""
    spec = ARMS[key]
    fn: Callable[[dict, int], str] = spec["fn"]
    correct: list[bool] = []
    predictions: list[str] = []
    latencies: list[float] = []
    errors: list[str] = []

    baseline_mem = gpu_mb()
    peak_mem = baseline_mem or 0.0

    for case in cases:
        t0 = time.perf_counter()
        try:
            pred = fn(case, seed)
        except Exception as exc:
            # Errors are recorded, not just defaulted. A silent fallback to CHAT turns a
            # broken arm into a plausible-looking low score -- which is exactly how the first
            # run of this script reported two different models at an identical 22.3%.
            errors.append(f"{case['id']}: {type(exc).__name__}: {exc}")
            pred = "CHAT"
        latencies.append((time.perf_counter() - t0) * 1000)
        predictions.append(pred)
        correct.append(pred == case["expected"])
        current = gpu_mb()
        if current is not None:
            peak_mem = max(peak_mem, current)

    if errors:
        logger.error(
            "arm %s raised on %d/%d cases -- its score is meaningless. First: %s",
            key, len(errors), len(cases), errors[0],
        )

    return {
        "arm": key,
        "name": spec["name"],
        "label": spec["label"],
        "seed": seed,
        "correct": correct,
        "predictions": predictions,
        "latency": LatencySummary(spec["label"], tuple(latencies)),
        "peak_gpu_mb": round(peak_mem, 1),
        "errors": errors,
        "accuracy": Proportion(sum(correct), len(correct)),
    }


def per_class(cases: list[dict], predictions: list[str]) -> dict[str, dict[str, float]]:
    """Precision, recall and F1 per intent, plus support."""
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn_ = defaultdict(int)
    support = defaultdict(int)
    for case, pred in zip(cases, predictions):
        gold = case["expected"]
        support[gold] += 1
        if pred == gold:
            tp[gold] += 1
        else:
            fp[pred] += 1
            fn_[gold] += 1
    out = {}
    for label in LABELS:
        p = tp[label] / (tp[label] + fp[label]) if (tp[label] + fp[label]) else 0.0
        r = tp[label] / (tp[label] + fn_[label]) if (tp[label] + fn_[label]) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        out[label] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4), "support": support[label]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", nargs="+", default=["single", "semantic"],
                    choices=[*DATASETS, "all"], help="datasets to pool (default: single semantic)")
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS),
                    help="which arms to run (default: all five)")
    ap.add_argument("--runs", type=int, default=1,
                    help="repetitions for stochastic arms; §5.1.3 requires 5 for reported results")
    ap.add_argument("--json", metavar="PATH", help="write the full report here (default: timestamped)")
    args = ap.parse_args()

    names = list(DATASETS) if "all" in args.dataset else args.dataset
    cases = load_cases(names)
    if not cases:
        sys.exit("no cases loaded")

    dist = defaultdict(int)
    for c in cases:
        dist[c["expected"]] += 1

    print(f"\n{'=' * 78}")
    print("  Router ablation — five arms, paired on identical items")
    print(f"  {len(cases)} cases from: {', '.join(names)}")
    print(f"  class distribution: {dict(sorted(dist.items()))}")
    print(f"  runs: {args.runs} (stochastic arms only)")
    print(f"{'=' * 78}\n")

    arm_results: dict[str, list[dict[str, Any]]] = {}
    for key in args.arms:
        spec = ARMS[key]
        runs = args.runs if spec["stochastic"] else 1
        print(f"  [{key}] {spec['label']} — {runs} run(s) ... ", end="", flush=True)
        t0 = time.perf_counter()
        arm_results[key] = [run_arm(key, cases, seed=i) for i in range(runs)]
        best = arm_results[key][0]
        print(f"{best['accuracy'].point:.1%}  ({time.perf_counter() - t0:.1f}s)")

    # ---- accuracy table -------------------------------------------------------------
    rows = []
    for key in args.arms:
        runs = arm_results[key]
        acc = runs[0]["accuracy"]
        lat = runs[0]["latency"]
        spread = ""
        if len(runs) > 1:
            points = [r["accuracy"].point for r in runs]
            spread = f" [{min(points):.1%}-{max(points):.1%}]"
        rows.append([
            key,
            runs[0]["label"],
            f"{acc.successes}/{acc.total}",
            f"{acc.point:.1%}{spread}",
            f"{acc.interval[0]:.1%}-{acc.interval[1]:.1%}",
            f"{lat.p50:.0f}",
            f"{lat.p95:.0f}",
            f"{runs[0]['peak_gpu_mb']:.0f}",
        ])

    print(f"\n{'=' * 78}")
    print("  ACCURACY AND COST")
    print(f"{'=' * 78}\n")
    print(markdown_table(
        ["Arm", "System", "n", "Accuracy", "95% CI", "p50 ms", "p95 ms", "GPU MB"], rows))
    print(
        "\n  GPU MB is total device occupancy while the arm ran, not the arm's own footprint:"
        "\n  a model loaded by an earlier arm is still resident. For a per-arm figure to quote"
        "\n  in the thesis, run each arm alone (--arms E) from a cold GPU."
    )

    broken = [k for k in args.arms if arm_results[k][0]["errors"]]
    if broken:
        print(f"\n  !! ARMS WITH ERRORS: {', '.join(broken)} — their accuracies are not valid.")
        for k in broken:
            errs = arm_results[k][0]["errors"]
            print(f"     [{k}] {len(errs)}/{len(cases)} cases raised. First: {errs[0][:140]}")

    # ---- paired comparisons ---------------------------------------------------------
    print(f"\n{'=' * 78}")
    print("  PAIRED COMPARISONS (McNemar exact, same items)")
    print(f"{'=' * 78}\n")
    comparisons = []
    for a, b in KEY_PAIRS:
        if a not in arm_results or b not in arm_results:
            continue
        cmp = compare_paired(
            ARMS[a]["name"], arm_results[a][0]["correct"],
            ARMS[b]["name"], arm_results[b][0]["correct"],
        )
        comparisons.append(cmp)
        print(f"  {cmp}")

    # ---- per-class breakdown for the proposed arm -----------------------------------
    if "D" in arm_results:
        print(f"\n{'=' * 78}")
        print("  PER-CLASS — arm D (proposed)")
        print(f"{'=' * 78}\n")
        pc = per_class(cases, arm_results["D"][0]["predictions"])
        print(markdown_table(
            ["Intent", "Precision", "Recall", "F1", "Support"],
            [[k, f"{v['precision']:.3f}", f"{v['recall']:.3f}", f"{v['f1']:.3f}", v["support"]]
             for k, v in pc.items()]))

    # ---- disagreements worth reading ------------------------------------------------
    if "D" in arm_results and "F" in arm_results:
        print("\n  Cases where the prompted LLM (F) is right and the MLP (D) is wrong:")
        shown = 0
        for i, case in enumerate(cases):
            if arm_results["F"][0]["correct"][i] and not arm_results["D"][0]["correct"][i]:
                print(f"    [{case['id']}] \"{case['utterance'][:56]}\" "
                      f"gold={case['expected']} mlp={arm_results['D'][0]['predictions'][i]}")
                shown += 1
        if not shown:
            print("    (none)")

    # ---- report ---------------------------------------------------------------------
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(args.json) if args.json else RESULTS_DIR / f"router_arms_{stamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "generated": stamp,
        "datasets": names,
        "n_cases": len(cases),
        "class_distribution": dict(dist),
        "runs": args.runs,
        "slm_model": SLM_MODEL,
        "llm_model": LLM_MODEL,
        "arms": {
            key: {
                "name": ARMS[key]["name"],
                "label": ARMS[key]["label"],
                "stochastic": ARMS[key]["stochastic"],
                "accuracy": runs[0]["accuracy"].as_dict(),
                "accuracy_per_run": [r["accuracy"].as_dict() for r in runs],
                "latency": runs[0]["latency"].as_dict(),
                "peak_gpu_mb": runs[0]["peak_gpu_mb"],
                "per_class": per_class(cases, runs[0]["predictions"]),
                "predictions": runs[0]["predictions"],
            }
            for key, runs in arm_results.items()
        },
        "comparisons": [c.as_dict() for c in comparisons],
        "cases": [{"id": c["id"], "utterance": c["utterance"], "expected": c["expected"],
                   "dataset": c["dataset"], "difficulty": c["difficulty"]} for c in cases],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
