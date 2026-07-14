# Evaluation Baseline — 2026-07-14

> Established after Section 4 (Quick Wins) and Section 5.1-5.2 (Model Upgrade + CoT Prompts).

---

## Environment

| Setting | Value |
|---------|-------|
| **Base model** | `qwen2.5:7b-instruct` (4.7 GB, Ollama) |
| **Embedding model** | `bkai-foundation-models/vietnamese-bi-encoder` (768-dim) |
| **Context window** | 8192 tokens |
| **Tool choice** | `tool_choice="any"` (natively supported) |
| **Router** | Hybrid: semantic centroid (cosine + softmax gap) → SLM fallback |
| **Retriever** | Hybrid: FAISS (vector) + BM25 (keyword) with RRF fusion (k=60) |

### Prompt versions (CoT rewrites — 2026-07-14)

| Prompt file | Status | Reasoning scaffold |
|-------------|--------|--------------------|
| `order_worker_agent.md` | ✅ CoT | Step 1: Identify action → Step 2: Extract items → Step 3: Check substitution → Step 4: Produce tool call |
| `search_agent.md` | ✅ CoT | Step 1: Classify search type → Step 2: Extract parameters/filters → Step 3: Produce tool call |
| `router_agent.md` | ✅ CoT | Step 1: Check context/stage → Step 2: Identify primary intent → Step 3: Check sequential intents → Step 4: Produce JSON |
| `response_rewriter.md` | ✅ Externalized | Prompt moved to `resources/system_prompts/` |
| `chat_rewriter.md` | ✅ Externalized | Prompt moved to `resources/system_prompts/` |

### Response pipeline

- `response_node.py` split into `response_node.py` (LLM orchestrator) + `response_template.py` (pure string templates)
- 3 `_llm_paraphrase_*` functions merged into single `_llm_invoke()` helper
- Templates extracted to `response_template.py` with named functions per reply type

---

## 1. Router Evaluation

| Metric | Value |
|--------|-------|
| **Total cases** | 45 |
| **Correct** | 43 |
| **Accuracy** | **95.56%** |
| **Overall avg latency** | 1.11s |
| **Semantic hits** | 8 (17.8%) — 0.01s each |
| **SLM fallbacks** | 37 (82.2%) — avg 1.1s each |

### Per-intent breakdown

| Intent | Avg latency |
|--------|-------------|
| `["ORDER"]` | 1.08s |
| `["SEARCH"]` | 1.08s |
| `["PAYMENT"]` | 1.00s |
| `["CHAT"]` | 1.22s |
| `["ORDER", "PAYMENT"]` | 1.28s |
| `["SEARCH", "ORDER"]` | 1.32s |
| `["ORDER_CONFIRM", "ORDER"]` | 1.22s |
| `["PAYMENT", "SEARCH"]` | 1.28s |
| `["ORDER", "ORDER_CONFIRM"]` | 1.35s |

### Failures (2)

| Case | Expected | Got | Root cause |
|------|----------|-----|------------|
| RT-044 `"Cho mình xem qua menu rồi lấy 1 cháo hàu"` | `["SEARCH", "ORDER"]` | `["ORDER"]` | Model collapsed "xem menu" into the order action; missed the search intent |
| RT-045 `"Thêm 3 hàu nướng nữa rồi chốt đơn cho anh"` | `["ORDER", "ORDER_CONFIRM"]` | `["ORDER"]` | Model saw "thêm" (add) as dominant; missed "chốt đơn" (confirm) |

---

## 2. Retrieval Evaluation

| Metric | Value |
|--------|-------|
| **Total cases** | 24 |
| **Precision@5** | **0.31** |
| **Recall@5** | **0.70** |
| **MRR** | **0.69** |
| **Hit rate** | **0.88** |

### Analysis

- **Hit rate 88%** — the correct item appears in top-5 for most queries, but often at position 2-3 (explains MRR of 0.69)
- **Precision 31%** — the Vietnamese menu has many similar dish names (`Ốc Hương` matches 11 sauce variants), inflating false positives
- **Recall 70%** — decent for an untuned hybrid search; BM25 helps with fragmented Vietnamese queries but struggles with semantic similarity across menu variants

### Failures (3 misses)

| Case | Query | Expected | Issue |
|------|-------|----------|-------|
| SR-001 | `"phần ốc hương bao nhiêu"` | `Ốc Hương`, `Ốc Hương Hấp Sả` | Returned sauce variants but missed the base `Ốc Hương` document |
| SR-006 | `"tôm càng xanh nướng"` | `Tôm Càng Xanh` | Returned all Tôm Càng Xanh variants but missed the generic `Tôm Càng Xanh` doc |
| SR-018 | `"đồ nhắm lai rai với bia"` | `Khô Mực Nướng`, `Khô Bò Lá Bông` | Semantic drift — "bia" dominated the search, returning beer items instead of snacks |

---

## 3. Out-of-Menu Evaluation

| Metric | Value |
|--------|-------|
| **Total scenarios** | 4 |
| **Passed** | 3 |
| **Pass rate** | **75%** |

### Details

| Scenario | Outcome | Notes |
|----------|---------|-------|
| OOM-001: Single invalid item | ✅ PASS | "Trà Sữa Trân Châu" rejected, "Ốc Hương" correctly flagged as ambiguous (11 variants) |
| OOM-002: Mix of valid + invalid | ⚠️ FAIL | Eval expected `sync_cart` tool but we migrated to `add_cart`; agent behavior was correct — added valid item, rejected invalid one, asked for clarification |
| OOM-003: All items invalid | ✅ PASS | "Sushi Cá Hồi" + "Pizza Hải Sản" both rejected, LLM suggested "Gỏi Hải Sản" as alternative |
| OOM-004: Near-match suggestions | ✅ PASS | "Bia Corona" → suggested "Bia 333", "Lẩu Hải Sản" → suggested "Gỏi Hải Sản" |

> **Note:** OOM-002 failure is a test maintenance issue (eval script references deprecated `sync_cart` tool name), not an agent behavior regression. Actual agent output was correct.

---

## Known Issues

1. **Eval scripts reference deprecated tool `sync_cart`** — the out-of-menu and potentially E2E evals need updating to use `add_cart` after the tool rename.
2. **Semantic router coverage is low** (18%) — the centroid-based router is conservative; most cases fall through to SLM. This explains the 1.1s avg latency. Tuning the gating threshold might improve coverage.
3. **Retrieval precision low** — 31% P@5 means the top-5 results have ~1.5 relevant items on average. The menu has 210 items with many near-duplicates by name.
4. **Multi-intent edge cases** — the 2 router failures are both on sequential multi-intent utterances. These align with the analysis doc's recommendation for a Conversation Planner (Section 6.2).
5. **No latency except router** — the other nodes (workers, validator, tools, response) haven't been profiled yet per-node. The analysis doc recommends comprehensive profiling (Section 7.6).

---

## Next Steps (ordered)

1. **Fix eval scripts** — update `sync_cart` references to `add_cart` in `eval_out_of_menu.py` and other E2E eval scripts
2. **Tune semantic router gating** — try lowering the gap threshold to increase semantic fast-track rate (reduce SLM latency)
3. **Expand retrieval eval** — add more edge cases, tune RRF `k` parameter
4. **Run E2E evals** — after updating eval scripts for the `add_cart` rename
5. **CI eval gate** (Section 5.4) — wire router + retrieval evals into GitHub Actions
