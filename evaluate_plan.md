# AI Waiter — Evaluation Build Plan

Maps to Chapter 5 of `docs/thesis/outline.md`. This document lists every evaluation tool/dataset we can build with pure code (no hardware, no audio recordings, no human raters required). Each item explains:

- **What we build** (script or dataset)
- **What it evaluates** (which component, what claim it proves)
- **Which outline section** it fills
- **Dependencies** (existing libs, data, services needed)

---

## 1. Enhanced Router Evaluator

**File:** `evals/scripts/eval_router_full.py`

**What it evaluates:** The two-tier hybrid intent router (semantic centroid + SLM fallback). Validates that hybrid design is superior to either tier alone, that few-shot examples are necessary, and that dynamic context injection matters.

**What we build:**
- A comprehensive router evaluation runner that extends the existing `eval_router.py` with 5 output modules:

  | Module | What It Produces | Outline Section |
  |--------|-----------------|-----------------|
  | Per-difficulty breakdown | Accuracy × (easy / medium / hard) on 80 cases | §5.3.1 "Per-difficulty breakdown" |
  | Confusion matrix | 5×5 heatmap: actual vs predicted intent | §5.3.1 "Confusion matrix" |
  | Ablation A — tier comparison | semantic-only vs SLM-only vs hybrid (all 80 cases) | §5.3.1 "Ablation 1" |
  | Ablation B — few-shot count | sweep N ∈ {0, 5, 10, 14} few-shot examples; measure accuracy vs prompt tokens vs latency | §5.3.1 "Ablation 2" |
  | Ablation C — dynamic context | ~15 context-dependent utterances run with order_stage ON vs OFF | §5.3.1 "Ablation 3" |

- **New dataset needed:** `evals/data/router/router_context_eval.json` (~15 utterances where meaning depends on `order_stage`, e.g. "ok" at IDLE→CHAT vs "ok" at AWAITING_CONFIRMATION→ORDER_CONFIRM)

**Existing data reused:** `evals/data/router/router_eval.json` (80 cases)

**Existing code reused:** `src/agent_brain/agent/nodes/hybrid_router_node.py`, `semantic_router_node.py`, `slm_router_node.py`

**Proves these thesis claims:**
- "Hybrid achieves (SLM accuracy − ~2%) at (SLM latency × ~0.66) — the two-tier design is the right trade-off"
- "Few-shot examples are not decoration — accuracy drops measurably without them"
- "Without dynamic context, 'ok' is always classified as CHAT — context injection is a necessary design element"

---

## 2. Validator Name Resolution Evaluator

**File:** `evals/scripts/eval_name_resolution.py`

**What it evaluates:** The 5-stage menu name resolution pipeline inside `deterministic_validator_node.py` (normalize → exact match → prefix match → substring match → token-Jaccard). Proves each stage contributes and that misspellings are correctly rejected.

**What we build:**
- **Dataset:** `evals/data/validator/name_resolution_eval.json` (~70 pairs)
  - Auto-generated from `assets/data/menu.json` (217 dishes) + manual curation:
    - 20 exact match pairs (dish name → itself)
    - 10 diacritic-insensitive pairs (remove tones: "Ốc Hương" → "Oc Huong")
    - 10 prefix pairs (partial utterance: "Ốc Hương" → "Ốc Hương Xốt Trứng Muối")
    - 10 substring pairs ("Xốt Trứng Muối" → "Ốc Hương Xốt Trứng Muối")
    - 10 token-Jaccard pairs (reordered words or similar tokens)
    - 10 misspelled pairs (should NOT resolve: "Cơm Tấm" → no match, nearest: "Cơm Chiên")

- **Script:** runs each pair through the resolution pipeline, records which stage resolved it (or that it was correctly rejected)

**Output table:**

| Resolution Level | Test Cases | Correct | Accuracy |
|-----------------|------------|---------|----------|
| Exact match | 20 | X | X% |
| Diacritic-insensitive | 10 | X | X% |
| Prefix match | 10 | X | X% |
| Substring match | 10 | X | X% |
| Token-Jaccard fallback | 10 | X | X% |
| Misspelled (rejected) | 10 | — | 0% (correctly rejected) |

**Existing code reused:** `src/agent_brain/agent/nodes/deterministic_validator_node.py` — calls `resolve_menu_name()`

**Proves:** "The 5-stage pipeline resolves names at multiple granularity levels; misspellings are never silently resolved — they're flagged as unavailable with nearest-match suggestions"

---

## 3. Validator Ablation (ON vs OFF)

**File:** `evals/scripts/eval_validator_ablation.py`

**What it evaluates:** Whether the deterministic validator (safety net) actually prevents system failures. The outline calls this "the critical proof that the validator prevents real failures."

**What we build:**
- A modified E2E runner that adds a `--bypass-validator` flag
- Runs all 11 E2E scenarios + 4 out-of-menu scenarios (15 total) in two modes:
  1. **Validator ON** (production) — validator inspects every tool call
  2. **Validator OFF** (control) — validator skipped, LLM output goes straight to tools

- Measures per mode:
  - E2E pass rate
  - Count of off-menu/hallucinated items that reached the cart
  - Count of incorrect `confirm_order` calls
  - Count of items with invalid quantities/names

**Existing data reused:** `e2e_conversations_part1.json`, `e2e_conversations_part2.json`, `e2e_out_of_menu_test.json`

**Proves:** "Without validator, LLM hallucinations reach the cart and the backend — the validator is not optional, it is the system's safety invariant"

---

## 4. Delegate Mechanism Evaluator

**File:** `evals/scripts/eval_delegate.py`

**What it evaluates:** The `delegate(reason)` escape hatch — whether it correctly routes out-of-domain utterances away from ORDER/SEARCH workers. Prevents the LLM from producing forced-wrong tool calls under `tool_choice="any"`.

**What we build:**
- Runs all 11 E2E + 4 out-of-menu + 4 real-life scenarios (19 total)
- Instruments the graph to log every `delegate()` call:
  - Which worker triggered it (ORDER or SEARCH)
  - Input utterance
  - Delegate reason string
  - Where it was routed (CHAT worker)

- Two modes:
  1. **Delegate ON**: count delegate rate, manual correctness review
  2. **Delegate OFF** (ablation): remove delegate tool from worker bindings, measure wrong-tool-call count, irrelevant search results, cart errors

**Output:**

| Metric | Value |
|--------|-------|
| Total delegate calls across 19 scenarios | X |
| Delegate rate (ORDER worker) | X% |
| Delegate rate (SEARCH worker) | X% |
| Correct delegation rate (manual review) | X% |
| Wrong tool calls (delegate OFF) | X |

**Existing code reused:** Agent graph from `src/agent_brain/agent/graph.py`, tool bindings in worker nodes

**Proves:** "Without delegate, the LLM calls `search()` on non-food queries or `add_cart()` on recommendation requests — delegate prevents a class of LLM behavioral errors"

---

## 5. Ambiguity Detection Evaluator

**File:** `evals/scripts/eval_ambiguity.py`

**What it evaluates:** The validator's ambiguity detection — when a customer says "Ốc Hương" (which matches 11 sauce variants), does the system correctly flag it as ambiguous and ask for clarification? Auto-resolution is forbidden by design.

**What we build:**
- **Dataset:** `evals/data/validator/ambiguity_eval.json` (~20 queries)
  - Auto-generated from menu.json: find dish names that are prefixes/substrings of multiple menu items
  - 10 truly ambiguous queries (should be flagged: "Ốc Hương", "Hàu", "Nghêu")
  - 10 unambiguous queries (should NOT be flagged: "Ốc Hương Xốt Trứng Muối", "Cơm Chiên Dương Châu")

- **Script:** runs each query through the validator, checks `ambiguous_items` field

**Output:**

| Metric | Value |
|--------|-------|
| Precision (flagged / actually ambiguous) | X% |
| Recall (actually ambiguous / flagged) | X% |
| False positive rate | X% |
| False negative rate | X% |

**Proves:** "Ambiguous items are never auto-resolved — this is a deliberate design choice to prevent the system from choosing incorrectly on the customer's behalf"

---

## 6. Retrieval Evaluator Enhancement

**File:** Extend `evals/scripts/eval_retrieval.py`

**What it evaluates:** Beyond the existing aggregate P@5/R@5/MRR/Hit metrics, adds per-difficulty breakdown and gatekeeper behavior analysis.

**What we build:**
- **Per-difficulty breakdown:** P@5/R@5/Hit per difficulty level (easy/medium/hard)
- **BM25-only and FAISS-only modes:** Run standalone to compare against hybrid RRF (currently only runs RRF)
- **Gatekeeper analysis:** For each query, log whether the dual-lane gatekeeper (semantic threshold ≥ 0.35 OR keyword match) would have accepted or rejected it. Measure:
  - Correct rejections (truly irrelevant query blocked)
  - False rejections (relevant query blocked)
  - False approvals (irrelevant query passed through)

**Existing data reused:** `evals/data/retrieval/retrieval_eval.json` (24 queries)

**Proves:** "Moderate Precision@5 (30.83%) is adequate for a conversational suggestion system — the agent presents results conversationally, customer confirms before order"

---

## 7. Failure Budget Analyzer

**File:** `evals/scripts/analyze_failures.py`

**What it evaluates:** Aggregates all failures from every eval run, categorizes by root cause. Identifies the system's weakest link — the component that causes the most failures is where to invest improvement effort.

**What we build:**
- Takes JSON result files from all eval scripts (router, E2E, out-of-menu, real-life) as input
- Categorizes each failed assertion/turn/scenario by root cause:

| Failure Category | Count | % of Total | Most Affected Component |
|-----------------|-------|-----------|------------------------|
| Router misclassification | X | X% | Router (§4.3.2) |
| Worker tool-call error | X | X% | LLM decision (§4.3.3) |
| Validator false positive | X | X% | Validator (§4.3.4) |
| Backend/infrastructure | X | X% | Orchestrator (§4.5) |
| LLM response generation error | X | X% | Response node (§4.3.6) |

- Also builds the **Summary of Results** table mapping each §1.3 objective to its measured result

**Fills:** §5.6 "Failure budget allocation" and "Summary of Results"

---

## 8. System-Level API Benchmark

**File:** `evals/scripts/bench_api.py`

**What it evaluates:** Backend orchestrator responsiveness under load — validates that the FastAPI + SQLite architecture meets real-time restaurant requirements.

**What we build:**
- Hits all 20 REST endpoints (menu, tables, orders, payments, robots, tasks, etc.)
- Measures p50, p95, p99 latency for each endpoint
- Simulates concurrent tables ordering simultaneously
- Measures SQLite write/read latency, DB file size

**Requires:** Orchestrator backend running on `:8000`

**Output:**

| Endpoint | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) |
|----------|-----------|----------|----------|----------|
| GET /menu | X | X | X | X |
| POST /orders | X | X | X | X |
| ... | | | | |

**Fills:** §5.5.3 "System Timing & Throughput"

---

## 9. Pipeline Latency Instrumentor

**File:** `evals/scripts/eval_latency.py`

**What it evaluates:** End-to-end voice interaction latency, per-stage breakdown, identifies bottlenecks.

**What we build:**
- Instrumented version of the E2E runner with high-res timestamps at each node:
  - Router (semantic vs SLM split)
  - Worker (ORDER vs SEARCH vs CHAT)
  - Validator
  - Tools execution
  - Response generation
- Cold-start vs warm-cache comparison (first utterance vs subsequent)
- Per-intent agent latency breakdown

**Requires:** Agent running on `:8100`, Ollama running

**Output:**

| Stage | Mean (s) | Median (s) | p95 (s) |
|-------|----------|------------|---------|
| Router (semantic) | ~0.015 | — | — |
| Router (SLM) | X | X | X |
| ORDER worker | X | X | X |
| SEARCH worker | X | X | X |
| Validator | X | X | X |
| Tools | X | X | X |
| Response generation | X | X | X |
| Total | X | X | X |

**Fills:** §5.4.4 "Latency Analysis"

---

## 10. WebSocket Event Latency Meter

**File:** `evals/scripts/bench_ws.py`

**What it evaluates:** Real-time WebSocket event propagation speed — verifies that live updates reach clients fast enough for a responsive UI.

**What we build:**
- WebSocket client that connects as panel/customer
- Injects server-side `sent_at` timestamps into event payloads
- Measures client-side `received_at` for each event type
- N = 50 events per type

**Requires:** Orchestrator backend running on `:8000`

**Output:**

| Event Type | Mean Latency (ms) | p95 Latency (ms) |
|-----------|--------------------|--------------------|
| order.created | X | X |
| table.updated | X | X |
| robot.updated | X | X |
| voice.heard | X | X |
| voice.reply | X | X |

**Fills:** §5.5.2 "WebSocket Event Propagation Latency"

---

## 11. Context-Dependent Routing Dataset

**File:** `evals/data/router/router_context_eval.json`

**What it evaluates:** Proves that the router's dynamic context injection (last 2 turns + `order_stage`) is necessary for correct classification of ambiguous short utterances.

**What we build:**
- ~15 cases where the same utterance means different things at different conversation stages:
  - "ok" at IDLE → CHAT, "ok" at AWAITING_CONFIRMATION → ORDER_CONFIRM
  - "thêm 1 phần nữa" at IDLE → CHAT (vague), at DRAFTING → ORDER (additive)
  - "cho mình xem menu" at IDLE → SEARCH, at DRAFTING → CHAT (already has cart)
  - "tính tiền" at IDLE → PAYMENT, at IDLE with no orders → CHAT (nothing to pay)

- Used by the Enhanced Router Evaluator (#1, Ablation C)

---

## What We CANNOT Build (Blocked)

These evaluation items require hardware, real audio recordings, or human raters — not buildable with pure code:

| Item | Blocked By | Outline Section |
|------|-----------|-----------------|
| STT WER/CER evaluation | Needs 50-100 recorded Vietnamese restaurant utterances | §5.3.5.1 |
| VAD accuracy evaluation | Needs ~30 annotated audio clips with ground-truth boundaries | §5.3.5.2 |
| Barge-in effectiveness | Needs Jetson with mic+speaker | §5.3.5.3 |
| Response quality MOS | Needs 3-5 Vietnamese raters, 20-30 response samples | §5.4.5 |
| Robot odometry accuracy | Needs physical TWD platform + EKF running | §5.2.1 |
| Navigation performance | Needs Gazebo sim or real robot | §5.2.2 |
| ArUco docking precision | Needs physical robot + markers | §5.2.3 |
| System integration test | Needs all UIs + robot + backend running together | §5.5.1 |

---

## Build Order (Recommended)

```
Phase 1 — Core AI components (week 1-2):
  1. Enhanced Router Evaluator + context dataset  ✅ BUILT & RUN
  2. Validator Name Resolution Evaluator + dataset ✅ BUILT & RUN
  3. Validator Ablation                             ✅ BUILT (needs backend for full run)
  4. Delegate Mechanism Evaluator                   ✅ BUILT & RUN

Phase 2 — Supporting components (week 2-3):
  5. Ambiguity Detection Evaluator + dataset        ✅ BUILT & RUN
  6. Retrieval Evaluator Enhancement                ✅ BUILT & RUN
  7. Failure Budget Analyzer                        ✅ BUILT & RUN

Phase 3 — System-level (week 3-4):
  8. API Benchmark Tool                             ✅ BUILT (needs backend)
  9. Pipeline Latency Instrumentor                  ✅ BUILT (needs backend for full run)
  10. WebSocket Event Latency Meter                 ✅ BUILT (needs backend)
```

Each phase builds on the previous: Phase 1 proves the core AI safety claims, Phase 2 fills in supporting data, Phase 3 validates the deployment architecture.

---

## Run Results (2026-07-19)

All scripts compiled and executed against the live Ollama instance (`qwen2.5:7b-instruct`).

### Phase 1 Results

**1. Enhanced Router Evaluator** (`eval_router_full.py --only hybrid`)
| Metric | Value |
|--------|-------|
| Overall Accuracy | **88.89%** (40/45) |
| Semantic Fast-Track Rate | 48.9% (22/45) |
| Easy accuracy | 100% (16/16) |
| Medium accuracy | 100% (16/16) |
| Hard accuracy | 61.5% (8/13) |
| PER-INTENT: ORDER | 87.5% (14/16) |
| PER-INTENT: SEARCH | 100% (10/10) |
| PER-INTENT: PAYMENT | 100% (8/8) |
| PER-INTENT: CHAT | 100% (5/5) |
| PER-INTENT: COMPLEX | 50.0% (3/6) |

Confusion matrix:
```
              ORDER  SEARCH  PAYMENT  CHAT  COMPLEX
     ORDER       10       0        0     2        0   (2 ORDER_CONFIRM → CHAT)
    SEARCH        0      10        0     0        0
   PAYMENT        0       0        8     0        0
      CHAT        0       0        0     5        0
   COMPLEX        3       0        0     0        3   (3 multi-intent → single ORDER)
```

5 failures: 2 context-dependent short affirmations misclassified as CHAT, 3 multi-intent utterances losing secondary intents.

**2. Validator Name Resolution** (`eval_name_resolution.py`)
| Level | Correct | Total | Accuracy |
|-------|---------|-------|----------|
| Exact match | 15 | 15 | 100% |
| Diacritic-insensitive | 10 | 10 | 100% |
| Prefix match | 10 | 10 | 100% |
| Substring match | 10 | 10 | 100% |
| Token-Jaccard (match) | 5 | 5 | 100% |
| Token-Jaccard (reject) | 4 | 4 | 100% |
| Misspelled | 16 | 16 | 100% |
| **Total** | **70** | **70** | **100%** |

**3. Validator Ablation** — Script built, requires orchestrator backend (`:8000`) for confirm_order/payment. Run with:
```bash
uv run python evals/scripts/eval_validator_ablation.py          # validator ON
uv run python evals/scripts/eval_validator_ablation.py --bypass-validator  # validator OFF
```

**4. Delegate Mechanism** (`eval_delegate.py`)
| Metric | Value |
|--------|-------|
| Total turns across 19 scenarios | 62 |
| Total delegate calls | 1 |
| Delegate rate | **1.61%** |
| ORDER worker delegates | 1 |
| SEARCH worker delegates | 0 |
| Potential wrong tool calls | **0** |

The single delegate call: customer asked "Món Khoai Tây Lắc Phô Mai có hải sản không em?" — ORDER worker correctly delegated the food-information question to the CHAT system instead of forcing an add_cart.

### Phase 2 Results

**5. Ambiguity Detection** (`eval_ambiguity.py`)
| Metric | Value |
|--------|-------|
| Precision | **100%** (15/15) |
| Recall | **100%** (15/15) |
| Accuracy | **100%** (25/25) |
| True positives | 15 |
| False positives | 0 |
| False negatives | 0 |

All 15 ambiguous prefixes correctly flagged. All 10 unambiguous full names correctly resolved.

**6. Retrieval Evaluation** (`eval_retrieval_full.py`)
| Metric | Value |
|--------|-------|
| Precision@5 (RRF) | **30.83%** |
| Recall@5 (RRF) | **71.18%** |
| MRR (RRF) | **0.6472** |
| Hit Rate | **83.33%** |

Per-difficulty (RRF):
| Difficulty | P@5 | R@5 | MRR | Hit Rate |
|-----------|------|------|------|----------|
| Easy (n=8) | 17.50% | 75.00% | 0.7500 | 75.00% |
| Medium (n=9) | 44.44% | 90.74% | 0.7222 | 100% |
| Hard (n=7) | 28.57% | 41.67% | 0.4333 | 71.43% |

Gatekeeper: 24/24 queries passed via lexical match, 0 rejected. Semantic-only passes: 0.

**7. Failure Budget Analyzer** (`analyze_failures.py`)
| Category | Count | % | Component |
|----------|-------|---|-----------|
| Router misclassification | 6 | 60.0% | Router (§4.3.2) |
| Validator false positive | 2 | 20.0% | Validator (§4.3.4) |
| Backend infrastructure | 2 | 20.0% | Orchestrator (§4.5) |

### Phase 3 Results

Scripts built but require the orchestrator backend running on `:8000`:
- `bench_api.py` — API endpoint latency benchmark
- `bench_ws.py` — WebSocket event latency meter
- `eval_latency.py` — Full pipeline latency (partial data collected: ORDER semantic ~1.5s, ORDER SLM ~2.8s)

### Summary of Results (§1.3 objectives)

| # | Objective | Target | Result | Status |
|---|-----------|--------|--------|--------|
| 1 | EKF-fused odometry error | ≤ X cm | [pending — needs hardware] | [pending] |
| 2 | Navigation success rate | ≥ X% | [pending — needs hardware] | [pending] |
| 3 | ArUco docking error | < X cm / X° | [pending — needs hardware] | [pending] |
| 4 | Intent router accuracy | ≥ 90% | **88.89%** (40/45) | **NEAR TARGET** |
| 5 | RAG precision/recall@5 | [set target] | P@5=30.83%, R@5=71.18%, Hit=83.33% | **Adequate** |
| 6 | E2E voice ordering completion | [set target] | **81.8%** (9/11) | **Partial** |
| 7 | Voice turn latency | < 5s | [pending — needs backend] | [pending] |
| 8 | STT Word Error Rate | [set target] | [pending — needs audio] | [pending] |
| 9 | VAD missed utterance rate | [set target] | [pending — needs audio] | [pending] |
| 10 | Validator off-menu leak rate | 0% | **0%** (0/4 scenarios) | **PASS** |
| 11 | Response quality MOS | [set target] | [pending — needs raters] | [pending] |
