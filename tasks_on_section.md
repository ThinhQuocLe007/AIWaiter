# Tasks from Agent Brain Analysis

> Source: `docs/agent-brain-analysis.md` (2026-07-14)

---

## Section 4: Quick Wins (This Week)

### 4.1 Delete Deprecated Code

- [x] **4.1.1** Remove `sync_cart` tool — `tools/sync_cart.py`, `tools/__init__.py` (export), `state_outcome_node.py:219-220`, `deterministic_validator_node.py:231-236`. Deprecated since add_cart/remove_cart/clear_cart were introduced.
- [x] **4.1.2** Remove `critic_node.py` — `agent/nodes/critic_node.py`, `nodes/__init__.py`. Legacy LLM-based validator superseded by deterministic validator. Not connected to the graph.
- [x] **4.1.3** Remove commented-out Phase 5 code — `response_node.py` ~100 lines at bottom. Marked "Phase 5 will delete." *(Already clean — updated docstring only.)*
- [x] **4.1.4** Remove duplicate `SyncCartResponse` class — `schemas/order.py` lines 39-44 and 72-76. Two identical class definitions.
- [x] **4.1.5** Remove legacy `payment_worker_node.py` — `agent/nodes/payment_worker_node.py`. Superseded by `payment_dispatch_node.py`. Still imported in `nodes/__init__.py`.

### 4.2 Fix Code Duplication

- [x] **4.2.1** Consolidate `last_user_text` — `deterministic_validator_node.py:28-33` and `state_outcome_node.py:47-56` define the same function. Move one canonical implementation to `utils/` and have both nodes import it.

### 4.3 Remove Module-Level Side Effects

- [x] **4.3.1** Lazy-initialize `MENU_NAMES` in `menu_utils.py` — `MENU_NAMES = get_menu_names()` runs at import time. Move to lazy initialization (`_LazyMenuNames` proxy + `_get_normalized_menu` cached) so it's computed on first use.

### 4.4 Add Ruff + Mypy Configuration

- [x] **4.4.1** Add `[tool.ruff]` config to `pyproject.toml` — target-version py310, line-length 100, select E/F/I/N/W/UP/B/C4/SIM rules.
- [x] **4.4.2** Add `[tool.mypy]` config to `pyproject.toml` — python_version 3.10, strict=false, warn_return_any=true, warn_unused_configs=true.

### 4.5 Standardize Error Handling

- [x] **4.5.1** Replace broad `except Exception` catches with specific exception types across the codebase (e.g. `slm_router_node.py:126-128`). Use `httpx.HTTPError`, `ConnectionError`, `TimeoutError` etc.

---

## Section 5: Phase 1 — Foundation Fixes (2-3 weeks)

### 5.1 Upgrade the Base Model

- [x] **5.1.1** Pull `qwen2.5:7b-instruct` via Ollama. *(Done — 4.7 GB)*
- [x] **5.1.2** Update `.env` / config to use `qwen2.5:7b-instruct` for ROUTER_MODEL, WORKER_MODEL, RESPONSE_MODEL.
- [x] **5.1.3** Remove 3-tier retry mechanism (`_force_tool_call_via_ollama`, `tool_choice` retry prompts) once model reliably produces tool calls.
- [x] **5.1.4** Verify `tool_choice="any"` works correctly with ChatOllama. *(qwen2.5 natively supports tool_choice; outdated comment removed from search_worker.)*
- [ ] **5.1.5** (Optional) Implement hybrid model fallback architecture: local LLM for fast path, cloud LLM for reliability.

### 5.2 Add Chain-of-Thought Prompting

- [x] **5.2.1** Rewrite `order_worker_agent.md` — add reasoning scaffold (Step 1: Identify action, Step 2: Extract items, Step 3: Check substitutions, Step 4: Produce tool call).
- [x] **5.2.2** Rewrite `search_agent.md` — add reasoning scaffold (Step 1: Classify search type, Step 2: Extract parameters/filters, Step 3: Produce tool call).
- [x] **5.2.3** Rewrite `router_agent.md` — add reasoning scaffold (Step 1: Check context/stage, Step 2: Identify primary intent, Step 3: Check sequential intents, Step 4: Produce JSON).
- [ ] **5.2.4** Expand `few_shots/order_worker.json` — add edge cases: ambiguous quantity ("vài phần"), teencode ("cho e 2 oc huog"), substitution with partial name.
- [ ] **5.2.5** Expand `few_shots/router.json` — add reference-heavy utterances requiring multi-turn context.

### 5.3 Establish Evaluation Baselines

- [x] **5.3.1** Run `eval_router.py` — 95.56% accuracy (43/45). Semantic: 18%, SLM: 82%. Avg latency 1.11s.
- [x] **5.3.2** Run `eval_retrieval.py` — P@5=0.31, R@5=0.70, MRR=0.69, Hit Rate=0.88.
- [ ] **5.3.3** Run `eval_e2e.py` — record pass rate per scenario, per-turn success rate, tool call accuracy across all 4 datasets. *(Eval scripts need sync_cart → add_cart update first.)*
- [x] **5.3.4** Run `eval_out_of_menu.py` — 75% pass rate (3/4). 1 fail due to deprecated `sync_cart` in eval script; agent behavior was correct.
- [x] **5.3.5** Create baseline document at `docs/eval-baseline-2026-07.md` with current scores, model/prompt versions, known failures and root causes.

### 5.4 Add CI Eval Gate

- [ ] **5.4.1** Create `.github/workflows/agent-eval.yml` — triggers on PR changes to `src/agent_brain/**` or `evals/**`, and push to main.
- [ ] **5.4.2** Workflow steps: setup Ollama, pull model, run all 3 evals (`--ci` mode), check regression thresholds.
- [ ] **5.4.3** Implement regression check — router threshold 0.85, e2e threshold 0.80.

---

## Section 6: Phase 2 — Architecture Deepening (3-4 weeks)

### 6.1 Entity Tracker for Multi-Turn Reference Resolution

- [ ] **6.1.1** Create `src/agent_brain/agent/nodes/entity_tracker.py` — `EntityTracker` class maintaining inventory of all mentioned dishes across conversation. Methods: `register_from_cart()`, `register_from_search()`, `resolve_reference()`.
- [ ] **6.1.2** Integrate entity tracker into `_should_shortcut_search` in `graph.py` — replace current string-matching logic.
- [ ] **6.1.3** Register entities on cart updates and search results (in `update_state_node` or `state_outcome_node`).
- [ ] **6.1.4** Fix curated_memory population — also register ordered dishes (not just searched ones) so CHAT can answer questions about dishes that were ordered but never searched.

### 6.2 Conversation Planner (Macro Orchestrator)

- [ ] **6.2.1** Create `src/agent_brain/agent/nodes/conversation_planner.py` — `ConversationPlanner` class. Decomposes multi-turn conversations, adds dependency tracking (e.g. ORDER skipped if conditional SEARCH returns empty).
- [ ] **6.2.2** Integrate planner into the graph pipeline — single-intent passthrough, multi-intent sequential planning.

### 6.3 Upgrade Order Stage FSM

- [ ] **6.3.1** Replace linear `IDLE → AWAITING_CONFIRMATION → CONFIRMED` with richer state machine: IDLE, BUILDING, AWAITING_CONFIRMATION, CONFIRMED, MODIFYING, MODIFICATION_PENDING, PARTIALLY_PAID, PAID.
- [ ] **6.3.2** Implement `VALID_TRANSITIONS` table with explicit allowed transitions.
- [ ] **6.3.3** Support post-confirmation modifications — add after confirm creates new draft, modify confirmed order cancels and recreates.
- [ ] **6.3.4** Support split bill ("Tính tiền 2 đứa riêng nha") — create separate payment requests per person.
- [ ] **6.3.5** Support takeaway addition — flag new items as takeaway after order confirmed.
- [ ] **6.3.6** Support partial payment ("Cho anh trả trước 500k") — partial payment + remaining balance tracking.

### 6.4 Multi-Intent Conditional Execution

- [ ] **6.4.1** Add dependency tracking between sequential intents in a turn — in `graph.py`, `_should_skip_intent()` checks if next intent should be skipped based on previous results.
- [ ] **6.4.2** Handle conditional ORDER: skip ORDER if previous SEARCH returned empty AND utterance was conditional ("nếu có", "nếu không cay", "nếu còn").
- [ ] **6.4.3** Optimize validator runs — avoid redundant validator passes for sequential intents.

---

## Section 7: Phase 3 — Advanced Features (4-6 weeks)

### 7.1 Streaming Response Pipeline

- [ ] **7.1.1** Refactor `response_node` — replace `_response_llm.invoke()` with `_response_llm.stream()` for 3 LLM paraphrase cases. Yield tokens.
- [ ] **7.1.2** Add `POST /chat/stream` endpoint in `server.py` — returns `text/event-stream` (SSE) instead of blocking HTTP response.
- [ ] **7.1.3** Update `edge_voice/main.py` — connect to `/chat/stream`, accumulate tokens into sentences (break on `.`, `!`, `?`, `ạ`), feed each sentence to TTS incrementally.

### 7.2 Proactive Service Model

- [ ] **7.2.1** Add `proactive_suggest` tool with triggers: after_add_no_drinks, after_confirm, empty_table_long, food_pairing.
- [ ] **7.2.2** Integrate proactive triggers into the graph pipeline — check triggers after state_outcome and inject suggestion into response.

### 7.3 Conversation Memory Summarization

- [ ] **7.3.1** Add periodic summarization in `state_outcome_node` — every 8 turns, generate conversation summary via LLM.
- [ ] **7.3.2** Store summary in `AgentState.conversation_summary` — next turns use summary instead of full history to stay within 8192 token context window.

### 7.4 Hot-Reload Menu & Indices

- [ ] **7.4.1** Create `src/agent_brain/services/menu_watcher.py` — `watchdog`-based file watcher for `assets/data/menu.json`.
- [ ] **7.4.2** On menu change: auto-rebuild FAISS + BM25, recompute centroids, reload in-memory references.
- [ ] **7.4.3** Start watcher in `server.py` lifespan.

### 7.5 A/B Testing Framework

- [ ] **7.5.1** Add `prompt_variant` parameter to `AIWaiterGraph.__init__` — load variant-specific prompts from `resources/prompts/{variant}/`.
- [ ] **7.5.2** Route a configurable percentage of traffic to each variant, collect metrics.

### 7.6 Comprehensive Latency Profiling

- [ ] **7.6.1** Collect per-node timing metrics (p50, p95, p99, errors) for: router, order_worker, search_worker, validator, tools, response_node, total_turn.
- [ ] **7.6.2** Export as Prometheus metrics for Grafana dashboards.

---

## Summary by Priority

| Priority | Section | Tasks |
|----------|---------|-------|
| **P0** | 4.1-4.5 | Quick Wins — delete deprecated code, fix duplications, lazy init, ruff/mypy, error handling |
| **P0** | 5.1-5.3 | Upgrade model to qwen2.5:7b, CoT prompts, eval baselines |
| **P1** | 5.4 | CI eval gate |
| **P1** | 6.1-6.4 | Entity tracker, order stage FSM, multi-intent conditional, conversation planner |
| **P2** | 7.1-7.2 | Streaming response, proactive service |
| **P3** | 7.3-7.6 | Memory summarization, hot-reload, A/B testing, latency profiling |
