# Agent Brain — Deep Analysis & Enhancement Roadmap

> **Date**: 2026-07-14  
> **Scope**: `src/agent_brain/` — the LLM application (agent graph, tools, prompts, RAG, eval)  
> **Purpose**: Identify limitations preventing the agent from reaching production quality, and propose a concrete, phased roadmap for breaking through.

---

## Table of Contents

1. [Architecture Review](#1-architecture-review)
2. [What Works Well](#2-what-works-well)
3. [The Wall — Critical Limitations](#3-the-wall--critical-limitations)
   - [3.1 Model Reliability Is the Root Constraint](#31-model-reliability-is-the-root-constraint)
   - [3.2 Prompt Engineering Is Fragile and Uncharted](#32-prompt-engineering-is-fragile-and-uncharted)
   - [3.3 No Multi-Turn Coherence](#33-no-multi-turn-coherence)
   - [3.4 Sequential Multi-Intent Is Inefficient](#34-sequential-multi-intent-is-inefficient)
   - [3.5 Rigid Order Stage FSM](#35-rigid-order-stage-fsm)
   - [3.6 No Streaming Response](#36-no-streaming-response)
   - [3.7 Evaluation Gap](#37-evaluation-gap)
   - [3.8 Menu Updates Require Rebuild](#38-menu-updates-require-rebuild)
4. [Quick Wins (This Week)](#4-quick-wins-this-week)
5. [Phase 1: Foundation Fixes (2-3 weeks)](#5-phase-1-foundation-fixes-2-3-weeks)
6. [Phase 2: Architecture Deepening (3-4 weeks)](#6-phase-2-architecture-deepening-3-4-weeks)
7. [Phase 3: Advanced Features (4-6 weeks)](#7-phase-3-advanced-features-4-6-weeks)
8. [Summary & Priority Matrix](#8-summary--priority-matrix)

---

## 1. Architecture Review

The agent is a **LangGraph StateGraph** with 10 nodes in a pipeline:

```
START
  │
  ▼
┌──────────┐     ┌─────────────┐     ┌───────────────┐
│  Router  │────▶│   Worker    │────▶│   Validator   │
│ (hybrid) │     │ (order/     │     │ (deterministic)│
│          │     │  search/    │     │               │
│ sem→slm  │     │  pay/chat)  │     │ pure Python   │
└──────────┘     └─────────────┘     └───────┬───────┘
                                              │
                              ┌───── retry ───┤ (invalid, < 3)
                              │               │
                              ▼               ▼
                        ┌──────────┐    ┌──────────┐
                        │  Tools   │    │  Tools   │ (valid)
                        │ (retry)  │    │ (exec)   │
                        └──────────┘    └────┬─────┘
                                             │
                                             ▼
                                     ┌──────────────┐
                                     │ State Updater│
                                     └──────┬───────┘
                                            │
                          ┌─ more intents? ─┤
                          │                 │ (no)
                          ▼                 ▼
                    ┌──────────┐    ┌──────────────┐
                    │  Worker  │    │State Outcome │
                    │ (next)   │    │(build typed  │
                    └──────────┘    │ context)     │
                                    └──────┬───────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │ Response Node│
                                    │  (rewriter)  │
                                    └──────┬───────┘
                                           │
                                           ▼
                                          END
```

### Key Files

| File | Lines | Role |
|------|-------|------|
| `agent/graph.py` | 313 | Graph builder, routing conditions, `chat()` entry point |
| `agent/state.py` | 80 | `AgentState` TypedDict — 20+ annotated fields |
| `agent/nodes/hybrid_router_node.py` | 58 | Two-tier router: semantic fast-track → SLM fallback |
| `agent/nodes/semantic_router_node.py` | 143 | Centroid-based vector intent classification + softmax gap gating |
| `agent/nodes/slm_router_node.py` | 130 | LLM-based intent classification with structured output |
| `agent/nodes/order_worker_node.py` | 154 | LLM worker for cart CRUD (add/remove/clear/confirm) |
| `agent/nodes/search_worker_node.py` | 114 | LLM worker for search parameter extraction |
| `agent/nodes/payment_dispatch_node.py` | 43 | Deterministic payment request emitter (no LLM) |
| `agent/nodes/chat_worker_node.py` | 95 | Pure Python ChatResponseContext builder (no LLM) |
| `agent/nodes/deterministic_validator_node.py` | 290 | Menu name resolution, modifier extraction, cart restoration, circuit breaker |
| `agent/nodes/update_state_node.py` | 138 | State updater after tool execution, intent queue management |
| `agent/nodes/state_outcome_node.py` | 322 | Builds typed `ResponseContext` from tool results, per-turn cleanup |
| `agent/nodes/response_node.py` | 488 | Rewriter: 5-type dispatch, templates + 3 LLM paraphrase cases |
| `schemas/response_context.py` | 219 | Typed discriminated union: ORDER, SEARCH, PAYMENT, CHAT, RETRY |
| `services/retriever/hybrid_retriever.py` | 52 | Parallel BM25 + FAISS with RRF fusion |
| `utils/prompt_utils.py` | 114 | Prompt loading, few-shot building, KV-cache-friendly assembly |
| `agent/resources/system_prompts/` | 5 `.md` files | Router, order worker, search agent, payment worker, waiter agent prompts |
| `agent/resources/few_shots/` | 5 `.json` files | Few-shot examples for router (14), order (9), search (9), payment (5), utterances |

### Model Assignment

All three roles share the same model (`gemma4:e2b-it-qat`, ~4B params, qat quantized):

```
ROUTER_MODEL  = gemma4:e2b-it-qat  →  semantic_router.py (centroid math, no LLM)
                                   →  slm_router_node.py (SLM fallback)
WORKER_MODEL  = gemma4:e2b-it-qat  →  order_worker_node.py, search_worker_node.py
RESPONSE_MODEL = gemma4:e2b-it-qat →  response_node.py (3 LLM paraphrase cases)
```

Context window: `LLM_NUM_CTX = 8192`, `LLM_KEEP_ALIVE = -1` (model pinned in RAM).

---

## 2. What Works Well

| Component | Why It's Strong |
|-----------|----------------|
| **Two-phase design** (worker → rewriter) | Workers decide *what to do* (tool calls / typed context). Rewriter decides *what to say*. Clean separation — the LLM never decides both simultaneously. |
| **Deterministic validator** | Pure Python guardrail — no LLM hallucination risk. Resolves diacritic-insensitive menu names, extracts inline modifiers (`(không cay)`), detects off-menu items with suggestions (`find_nearest_menu_name`), protects cart on additive turns, injects confirm_order items from state. |
| **Typed ResponseContext discriminated union** | 5 Pydantic variants dispatched via `isinstance`. Clean contract between `state_outcome_node` (producer) and `response_node` (consumer). No stringly-typed context. |
| **Hybrid router** (centroid → SLM fallback) | Fast path via cosine similarity against precomputed centroids with softmax+gap gating. Only calls the LLM when uncertain. Code is clean: `semantic_router_node.py:24-68` for the gating math, `hybrid_router_node.py:14-58` for the orchestration. |
| **Static + dynamic prompt split** | Static system prompts and few-shot examples at the front (KV-cache reusable across turns). Dynamic context (cart, feedback, table_id) appended at the end. Patterned correctly in `prompt_utils.py:106-113` and used consistently by all workers. |
| **Circuit breaker** (max 3 retries) | `graph.py:23` defines `MAX_RETRY_LOOPS = 3`. After 3 validation failures, the graph exits the retry loop and produces an apology response. |
| **Parallel RAG** | BM25 + FAISS run concurrently via `ThreadPoolExecutor(max_workers=2)` in `hybrid_retriever.py:45-52`. Fused with Reciprocal Rank Fusion (RRF, `k=60`). |
| **Per-turn state cleanup** | `state_outcome_node._finalize()` (line 263) clears `unavailable_items`, `ambiguous_items`, `feedback`, `last_tool` every turn. Prevents context leakage. |
| **Module-level chain compilation** | Router chain, worker LLMs, and response LLM are all compiled once at module import time — not reconstructed per-turn. |
| **Orchestrator client seam** | Agent tools write through REST to the backend (`orchestrator_client.py`). Agent never touches `orchestrator.db` directly. Single-writer principle. |

---

## 3. The Wall — Critical Limitations

### 3.1 Model Reliability Is the Root Constraint

The entire system depends on `gemma4:e2b-it-qat` (~4B params, quantized). The evidence of unreliability is **written into your code** as multi-layered defenses:

**Layer 1 — `tool_choice="any"` binding** (every worker):
```python
# order_worker_node.py:23, search_worker_node.py:24
.bind_tools([...], tool_choice="any")
```
The LLM is told "always produce a tool call" at the API level.

**Layer 2 — Retry with instructional prompt** (both workers):
```python
# order_worker_node.py:124-141, search_worker_node.py:91-109
if not ai_msg.tool_calls:
    retry_prompt = SystemMessage(content="⚠ CRITICAL: Bạn PHẢI gọi một tool call...")
    ai_msg = _llm.invoke([retry_prompt] + list(input_messages))
```

**Layer 3 — Ollama native `tool_choice=required` via raw HTTP** (order worker only):
```python
# order_worker_node.py:28-69
def _force_tool_call_via_ollama(messages: list) -> AIMessage:
    resp = httpx.post("http://localhost:11434/api/chat", json={
        "tool_choice": "required", ...
    })
```

**Layer 4 — Search worker openly admits the limitation**:
```python
# search_worker_node.py:24-30
# NOTE: `tool_choice="any"` is currently ignored by ChatOllama (see its
# bind_tools docstring: "not supported by Ollama").
```

**Impact**: Every turn has a non-trivial probability of the LLM producing text instead of a tool call. When this happens, the system enters a retry loop that 2-3x the latency. The wall is that **you are fighting the model, not engineering the agent**.

**Root cause**: The 4B quantized model does not reliably support function calling / tool use. The Open LLM Leaderboard shows that reliable tool calling begins at ~7B parameters for most open-weight models.

---

### 3.2 Prompt Engineering Is Fragile and Uncharted

#### Current State

Your prompts are manually crafted with no systematic optimization:

| Prompt | Lines | Style | Issues |
|--------|-------|-------|--------|
| `order_worker_agent.md` | 55 | Declarative rules + mapping table | No reasoning template. Rule #0 says "NEVER reply in text" — the system prompt is begging the model to behave. |
| `search_agent.md` | 82 | Parameter extraction rules + examples | Good query→parameter mapping, but no chain-of-thought. The model is told *what* to produce, not *how* to think. |
| `router_agent.md` | 74 | Intent definitions + rules | No reasoning scaffold. The SLM router gets few-shot examples with `reasoning` fields but the system prompt itself doesn't teach a reasoning pattern. |
| `few_shots/order_worker.json` | 180 | 9 example pairs | Examples are basic (add, remove, clear, confirm). Missing edge cases: ambiguous quantity ("vài phần"), teencode ("cho e 2 oc huog"), substitution with partial name. |
| `few_shots/router.json` | ~14 examples | Labeled intents + reasoning | Good coverage. But the SLM router prompt only gets last 2 turns of history — can't disambiguate reference-heavy utterances. |

#### Problem Analysis

Small models (~4B) need **structured reasoning templates**, not just declarative rules. Current prompt style:

```markdown
# Current: "1. ONE tool per turn for standard operations."
# The model is told WHAT the output should be, not HOW to reason about it.
```

Better approach — add an explicit reasoning step before the tool call:

```markdown
# Improved:
"## Reasoning Protocol
Before calling any tool, analyze the user's utterance in this order:
1. **Identify the action**: Is the customer adding, removing, clearing, confirming, or substituting?
2. **Extract items**: List every item mentioned. For each: name, quantity, special_requests.
3. **Check for substitutions**: Is there a "đổi"/"thay" pattern? If yes, plan remove+add.
4. **Validate quantities**: Default quantity=1 unless specified.
Then produce exactly the tool call(s) that match your analysis."

# This teaches the model a reasoning pattern it can follow, not just rules to obey.
```

---

### 3.3 No Multi-Turn Coherence

Each turn is processed atomically with narrow context windows:

| Component | History Window | Source |
|-----------|---------------|--------|
| Router (SLM) | Last **2** turns | `slm_router_node.py:115` |
| Order Worker | Last **3** turns | `order_worker_node.py:115` |
| Search Worker | Last **1** turn | `search_worker_node.py:74` |
| CHAT Rewriter | Full history | `ChatResponseContext.chat_history` |

#### The Reference Resolution Problem

```
Turn 3: Customer: "Cái đó có cay không?"
```

How the system resolves "cái đó" (that thing):

1. **Router** classifies as SEARCH (correct)
2. **`_should_shortcut_search()`** (graph.py:71) checks:
   - Is "cái đó" in cart item names? → **No** (exact string match only)
   - Is "cái đó" in `curated_memory` names? → **No**
   - Result: routes to SEARCH worker
3. **SEARCH worker** calls `search(query="cái đó")` → **Returns nothing useful**
4. **Response**: "Dạ, cái đó không có trong thực đơn..."

The system has no **entity tracker** that maintains a running list of mentioned dishes across turns. The customer said "Ốc Hương Xốt Trứng Muối" in turn 1, but by turn 3 it's irretrievable unless it's in the cart or was searched.

#### Curated Memory Is One-Directional

`curated_memory` is populated **only by SEARCH turns** (`chat_worker_node._to_curated_memory`). If a dish was added via ORDER (never searched), it never enters curated memory. The CHAT path can only answer follow-up questions about searched dishes, not ordered dishes.

**Consequence**: "Món Ốc Hương vừa gọi có cay không?" → LLM has no structured data about Ốc Hương (wasn't searched, only ordered) → hallucinates or deflects.

---

### 3.4 Sequential Multi-Intent Is Inefficient

The router supports multi-intent classification (`["SEARCH", "ORDER"]`), but the graph processes intents **sequentially in the same turn**:

```
User: "Món này cay không? Nếu không cay thì lấy 2 phần."
Router: ["SEARCH", "ORDER"]

Execution:
  SEARCH worker → validator → tools → state_updater
  → ORDER worker → validator → tools → state_updater
  → state_outcome → response_node
```

**Problems**:

1. **Latency multiplication**: Each intent runs the full validator+tools pipeline. `["SEARCH", "ORDER", "PAYMENT"]` = 3x the latency of a single-intent turn.

2. **Single combined response**: The response_node only speaks after **all** intents finish. The customer gets one reply covering everything. For `["SEARCH", "ORDER"]`, the natural flow would be:
   - "Món này không cay đâu ạ" (answer the question)
   - "Em đã thêm vào giỏ hàng" (confirm the action)
   
   But these arrive as one monolithic message.

3. **No dependency tracking**: If SEARCH returns "not found" and ORDER was conditional ("nếu không cay thì lấy"), the ORDER step should be skipped. But the graph blindly executes it because there's no conditional logic between sequential intents.

4. **Validator runs per-intent**: Each intent passes through the validator independently. If SEARCH and ORDER are in the same turn, the validator runs twice — once for search (trivial — nothing to validate), once for order. Unnecessary computational overhead.

---

### 3.5 Rigid Order Stage FSM

The order lifecycle is a simple linear FSM:

```
IDLE → AWAITING_CONFIRMATION → CONFIRMED → (session closed)
```

Real restaurant interactions require:

| Scenario | Customer says | Current behavior | Should |
|----------|--------------|------------------|--------|
| Add after confirm | "Cho anh thêm 1 bia nữa" | `confirm_order` rejects — already CONFIRMED | Create a new cart draft, add item, ask to confirm again |
| Modify confirmed | "Hủy cái Lẩu Thái đi, đổi qua Cháo Hàu" | Rejected | Cancel existing confirmed order, create new draft |
| Split bill | "Tính tiền 2 đứa riêng nha" | Not supported at all | Create separate payment requests per person |
| Takeaway addition | "Cho anh gọi thêm mang về" | Rejected (CONFIRMED) | Flag new items as takeaway, process separately |
| Partial payment | "Cho anh trả trước 500k" | Not supported | Partial payment + remaining balance tracking |

The validator enforces these restrictions:
```python
# deterministic_validator_node.py:210-214
elif tool_name == "confirm_order":
    if state.get("order_stage") != "AWAITING_CONFIRMATION":
        errors.append("Chưa thể xác nhận đơn hàng! ...")
```

The stage machine needs to become a **multi-state automaton** with transitions for post-confirmation modifications and edge cases.

---

### 3.6 No Streaming Response

The current voice pipeline is fully blocking:

```
mic → VAD → STT → HTTP POST → [agent pipeline 2-10s] → HTTP response → TTS → speaker
```

The agent pipeline must complete entirely before TTS begins. In a face-to-face voice interaction, 2-5 seconds of silence after speaking feels unnatural to humans (normal conversation turn-taking gap is ~200ms).

**Where streaming would help**:

1. **`response_node` LLM calls** — `_llm_paraphrase_search`, `_llm_paraphrase_order`, `_llm_paraphrase_chat` all call `_response_llm.invoke()`. These could `stream()` token-by-token.

2. **The entire pipeline** — Even the non-LLM templates could be streamed as soon as `state_outcome` finishes. The rewriter dispatches to templates in ~1ms, but the TTS still waits for the full HTTP response round-trip.

3. **Perceived responsiveness** — Streaming the first token within 500ms of the user finishing speaking (while the rest of the response streams) cuts perceived latency by 60-80%.

**Architecture note**: Streaming requires changes across three layers:
- `response_node` → yield tokens instead of return string
- `server.py` → Server-Sent Events (SSE) or WebSocket streaming
- `edge_voice/main.py` → receive streaming response, feed to TTS incrementally

---

### 3.7 Evaluation Gap

You have evaluation infrastructure but it's unused in daily development:

| What Exists | Location | Status |
|------------|----------|--------|
| Router eval (45 cases) | `evals/data/router/router_eval.json` | Dataset exists; script works manually |
| Retrieval eval (24 cases) | `evals/data/retrieval/retrieval_eval.json` | Dataset exists; script works manually |
| E2E eval (19 scenarios) | `evals/data/e2e/` (4 JSON files) | Dataset exists; script works manually |
| Out-of-menu eval (4 cases) | `evals/data/e2e/e2e_out_of_menu_test.json` | Dataset exists; script works manually |
| Eval runner scripts | `evals/scripts/` (8 `.py` files) | All manual, no automation |

**What's missing**:

1. **No CI integration** — Changing a prompt has no automated feedback loop. You can break the router accuracy from 90% to 60% with no alert.

2. **No regression testing** — Every prompt change is unvalidated. The eval scripts aren't run before/after changes.

3. **No baseline documented** — What's the current router accuracy? E2E pass rate? Latency p50/p95/p99? Without baselines, you can't measure improvement.

4. **No latency benchmarks** — How long does each node take? Where is the time spent? The `@trace_latency` decorator exists but metrics aren't collected systematically.

5. **No A/B testing framework** — Can't compare prompt variant A vs B on real traffic.

6. **Evals don't block deployment** — You can deploy a broken agent. No automated gate.

---

### 3.8 Menu Updates Require Rebuild

When the restaurant menu changes (`assets/data/menu.json`), the following must happen:

1. Run `scripts/setup.py` to rebuild FAISS index and BM25 index
2. Run `scripts/build_centroids.py` to recompute intent centroids
3. Restart the agent service to reload indices

**Problems**:

- **No hot-reload** — The agent holds indices in memory. Menu changes require a full restart.
- **Manual process** — No file watcher, no automatic rebuild trigger.
- **Centroids depend on embedding model** — If the embedding model changes, the fingerprint check in `semantic_router_node.py:84` will fail, requiring a rebuild. But the error message just says "fingerprint mismatch" — no guidance on what to do.
- **No versioning** — If the menu.json changes while the system is running, there's no mechanism to detect drift.

---

## 4. Quick Wins (This Week)

These are small, high-ROI changes requiring no architectural changes:

### 4.1 Delete Deprecated Code

| What | Where | Why |
|------|-------|-----|
| `sync_cart` tool | `tools/sync_cart.py`, `tools/__init__.py` (export), `state_outcome_node.py:219-220`, `deterministic_validator_node.py:231-236` | Deprecated since add_cart/remove_cart/clear_cart were introduced. Confuses the codebase. |
| `critic_node.py` | `agent/nodes/critic_node.py`, `nodes/__init__.py` | Legacy LLM-based validator superseded by deterministic validator. Not connected to the graph. |
| Commented-out Phase 5 code | `response_node.py` ~100 lines at bottom | Marked "Phase 5 will delete." Phase 5 is now. |
| Duplicate `SyncCartResponse` | `schemas/order.py` lines 39-44 and 72-76 | Two identical class definitions. |
| Legacy `payment_worker_node.py` | `agent/nodes/payment_worker_node.py` | Superseded by `payment_dispatch_node.py`. Still imported in `nodes/__init__.py`. |

### 4.2 Fix Code Duplication

```python
# Both files define the same function with different implementations:

# deterministic_validator_node.py:28-33
def _last_user_text(state: AgentState) -> str:
    for msg in reversed(state.get("messages", [])):
        if getattr(msg, "type", None) == "human":
            return msg.content if isinstance(msg.content, str) else ""
    return ""

# state_outcome_node.py:47-56 (public version)
def last_user_text(state: AgentState) -> str:
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return m.content
    return ""
```

Move one canonical implementation to `utils/` and have both nodes import it.

### 4.3 Remove Module-Level Side Effects

```python
# menu_utils.py (at module level)
MENU_NAMES = get_menu_names()  # Runs at import time, adds startup latency
```

Move to lazy initialization (`@functools.cached_property` or a singleton accessor) so it's computed on first use, not at import.

### 4.4 Add Ruff + Mypy Configuration

```toml
# pyproject.toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.10"
strict = false
warn_return_any = true
warn_unused_configs = true
```

### 4.5 Standardize Error Handling

Replace broad `except Exception` catches with specific exception types. Current pattern spreads across multiple files:

```python
# slm_router_node.py:126-128
except Exception:
    logger.exception("SLM Router LLM call failed, defaulting to CHAT")
    intents = ["CHAT"]

# Should be:
except (httpx.HTTPError, ConnectionError, TimeoutError) as e:
    logger.exception("SLM Router LLM call failed: %s", e)
    intents = ["CHAT"]
```

---

## 5. Phase 1: Foundation Fixes (2-3 weeks)

These address the root causes and give the largest leverage.

### 5.1 Upgrade the Base Model

**Current**: `gemma4:e2b-it-qat` (4B params, qat quantized)

**Options**:

| Model | Size | Tool Calling | VRAM (8K ctx) | Notes |
|-------|------|-------------|---------------|-------|
| `qwen2.5:7b-instruct` | 7B | Excellent (native) | ~6GB | Best all-around. Native function calling, strong Vietnamese. |
| `llama3.2:3b` | 3B | Good | ~3GB | Smaller but better trained for tool use than Gemma 4B. |
| `mistral:7b` | 7B | Good | ~6GB | Solid general-purpose, weaker Vietnamese. |
| `qwen2.5:14b` (optional) | 14B | Excellent | ~12GB | Needs GPU with 12GB+ VRAM. |

**Recommendation**: `qwen2.5:7b-instruct` — it natively supports function calling (`tool_choice` works correctly with Ollama), has strong Vietnamese support (trained on multilingual data), and fits in 8GB VRAM.

**Expected impact**:
- 3-tier retry mechanism becomes unnecessary (model reliably produces tool calls)
- `tool_choice="any"` actually works
- `_force_tool_call_via_ollama` can be removed
- Turn latency drops by removing retry overhead
- Router accuracy improves with better reasoning

**Fallback architecture** (optional enhancement):

```python
# Hybrid model strategy: local for fast path, cloud for reliability
def invoke_with_fallback(messages, local_llm, cloud_llm, timeout=3.0):
    try:
        return local_llm.invoke(messages)  # Try local first
    except (ToolCallFailure, TimeoutError):
        return cloud_llm.invoke(messages)  # Fall back to cloud
```

### 5.2 Add Chain-of-Thought Prompting

Replace declarative rules with reasoning templates for all workers.

**Before** (order_worker_agent.md):
```markdown
1. ONE tool per turn for standard operations.
2. Only use items the customer EXPLICITLY mentioned.
7. add_cart(items): Pass only the NEW items — the system merges.
```

**After** (add reasoning scaffold):
```markdown
## Reasoning Protocol

Trước khi gọi tool, hãy phân tích câu của khách theo các bước sau:

### Step 1: Xác định hành động
- "cho"/"lấy"/"gọi"/"thêm" → ADD
- "bỏ"/"hủy"/"thôi không lấy" → REMOVE
- "hủy đơn"/"thôi không đặt nữa" → CLEAR
- "xác nhận"/"chốt đơn"/"đúng rồi"/"ok đặt đi" → CONFIRM
- "đổi A thành B"/"thay A bằng B" → SUBSTITUTE (REMOVE A + ADD B)

### Step 2: Trích xuất món
Với mỗi món được nhắc tới, xác định:
- Tên món (dùng đúng từ khách nói)
- Số lượng (mặc định = 1 nếu không được nói rõ)
- Ghi chú đặc biệt (không cay, ít đường, thêm đá...)

### Step 3: Kiểm tra thay thế
Nếu có pattern "đổi A thành B" hoặc "thay A bằng B" → lên kế hoạch gọi remove_cart(A) + add_cart(B)

### Step 4: Sản xuất tool call
Dựa trên phân tích ở trên, gọi chính xác tool call tương ứng.
```

**Expected impact**:
- Reduction in tool-call failures (model has explicit mental model to follow)
- Better handling of edge cases (substitutions, ambiguous quantities)
- More consistent behavior across turns

### 5.3 Establish Evaluation Baselines

Run all evals and document the scores:

```bash
# 1. Router accuracy
python evals/scripts/eval_router.py
# Expected: record accuracy per intent, semantic vs SLM split, avg latency

# 2. Retrieval quality
python evals/scripts/eval_retrieval.py
# Expected: Precision@5, Recall@5, MRR, Hit Rate

# 3. E2E scenarios
python evals/scripts/eval_e2e.py --datasets e2e_conversations_part1.json e2e_conversations_part2.json e2e_real_life.json
# Expected: pass rate per scenario, per-turn success rate, tool call accuracy

# 4. Out-of-menu handling
python evals/scripts/eval_out_of_menu.py
# Expected: rejection rate, suggestion quality
```

Create a baseline document at `docs/eval-baseline-2026-07.md` with:
- Current scores for each eval
- Current model and prompt versions
- Known failures and their root causes

### 5.4 Add CI Eval Gate

```yaml
# .github/workflows/agent-eval.yml
name: Agent Evaluation
on:
  pull_request:
    paths:
      - 'src/agent_brain/**'
      - 'evals/**'
  push:
    branches: [main]

jobs:
  eval:
    runs-on: [self-hosted, gpu]  # or use a cloud GPU
    steps:
      - uses: actions/checkout@v4
      - name: Setup Ollama
        run: |
          ollama serve &
          sleep 5
          ollama pull qwen2.5:7b-instruct
      - name: Run Evals
        run: |
          python evals/scripts/eval_router.py --ci
          python evals/scripts/eval_retrieval.py --ci
          python evals/scripts/eval_e2e.py --ci
      - name: Check Regression
        run: |
          python evals/scripts/check_regression.py \
            --router-threshold 0.85 \
            --e2e-threshold 0.80
```

---

## 6. Phase 2: Architecture Deepening (3-4 weeks)

### 6.1 Entity Tracker for Multi-Turn Reference Resolution

Add an entity tracking layer that maintains a running inventory of all mentioned dishes across the conversation:

```python
# New file: src/agent_brain/agent/nodes/entity_tracker.py

class EntityTracker:
    """Tracks all dishes mentioned across the conversation for reference resolution."""
    
    def __init__(self):
        self.entities: dict[str, EntityRecord] = {}
    
    def register_from_cart(self, cart: Cart, turn: int):
        for item in cart.items:
            self.entities[item.name.lower()] = EntityRecord(
                name=item.name,
                source="cart",
                last_turn=turn,
                metadata={"quantity": item.quantity, "price": item.unit_price}
            )
    
    def register_from_search(self, results: list[SearchResult], turn: int):
        for r in results:
            name = r.document.metadata["name"]
            self.entities[name.lower()] = EntityRecord(
                name=name,
                source="search",
                last_turn=turn,
                metadata={
                    "price": r.document.metadata.get("price"),
                    "tags": r.document.metadata.get("tags"),
                    "taste_profile": r.document.metadata.get("taste_profile"),
                }
            )
    
    def resolve_reference(self, user_text: str) -> Optional[EntityRecord]:
        """Resolve 'cái đó', 'món đó', 'món lúc nãy' to the most recent entity."""
        # Check for generic references
        if any(r in user_text.lower() for r in ("cái đó", "món đó", "món lúc nãy", "nó")):
            # Return the most recently mentioned entity
            return max(self.entities.values(), key=lambda e: e.last_turn, default=None)
        # Check for partial name match
        for key, entity in self.entities.items():
            if key in user_text.lower():
                return entity
        return None
```

**Integration point**: `_should_shortcut_search` in `graph.py` — replace the current string-matching logic with `entity_tracker.resolve_reference()`.

### 6.2 Conversation Planner (Macro Orchestrator)

Add a planning layer that decomposes complex multi-turn conversations:

```python
# New file: src/agent_brain/agent/nodes/conversation_planner.py

class ConversationPlanner:
    """Plans multi-turn conversation sequences for complex customer requests."""
    
    def plan(self, state: AgentState) -> ConversationPlan:
        """
        Given the current state and user input, produce a plan for the
        next few turns if needed. For simple single-intent turns, returns
        a single-step plan (transparent passthrough).
        """
        user_msg = last_user_text(state)
        intents = state.get("current_intents", [])
        
        if len(intents) <= 1:
            return ConversationPlan(steps=[PlanStep(intent=intents[0])])
        
        # Multi-intent: plan sequential execution
        steps = []
        for intent in intents:
            step = PlanStep(intent=intent)
            # Add dependencies between steps
            if intent == "ORDER" and any(s.intent == "SEARCH" for s in steps):
                step.condition = "SEARCH_HAS_RESULTS"  # Skip if search returns nothing
            steps.append(step)
        
        return ConversationPlan(steps=steps)
```

### 6.3 Upgrade Order Stage FSM

Replace the linear `IDLE → AWAITING_CONFIRMATION → CONFIRMED` with a richer state machine:

```python
class OrderStage(str, Enum):
    IDLE = "IDLE"
    BUILDING = "BUILDING"               # Items being added
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"             # Order sent to kitchen
    MODIFYING = "MODIFYING"             # Post-confirmation changes in progress
    MODIFICATION_PENDING = "MODIFICATION_PENDING"  # New items added, awaiting re-confirm
    PARTIALLY_PAID = "PARTIALLY_PAID"   # Split bill in progress
    PAID = "PAID"

# Valid transitions
VALID_TRANSITIONS = {
    OrderStage.IDLE: {OrderStage.BUILDING, OrderStage.AWAITING_CONFIRMATION},
    OrderStage.BUILDING: {OrderStage.BUILDING, OrderStage.AWAITING_CONFIRMATION, OrderStage.IDLE},
    OrderStage.AWAITING_CONFIRMATION: {OrderStage.CONFIRMED, OrderStage.IDLE},
    OrderStage.CONFIRMED: {OrderStage.MODIFYING, OrderStage.AWAITING_CONFIRMATION},
    OrderStage.MODIFYING: {OrderStage.MODIFICATION_PENDING, OrderStage.CONFIRMED},
    OrderStage.MODIFICATION_PENDING: {OrderStage.CONFIRMED, OrderStage.IDLE},
    OrderStage.PARTIALLY_PAID: {OrderStage.PAID},
}
```

### 6.4 Multi-Intent Conditional Execution

Add dependency tracking between sequential intents in a turn:

```python
# In graph.py, _route_after_updater: check if next intent should be skipped
def _should_skip_intent(state: AgentState, intent: str) -> bool:
    if intent == "ORDER":
        # Skip ORDER if previous SEARCH in this turn returned empty
        search_context = state.get("search_context")
        if search_context is not None and len(search_context) == 0:
            prev_intents = state.get("current_intents")  # already consumed
            # Check if ORDER was conditional ("nếu có thì lấy")
            user_msg = last_user_text(state).lower()
            if any(c in user_msg for c in ("nếu có", "nếu không cay", "nếu còn")):
                logger.info("Skipping ORDER — conditional SEARCH returned empty")
                return True
    return False
```

---

## 7. Phase 3: Advanced Features (4-6 weeks)

### 7.1 Streaming Response Pipeline

**Goal**: First token delivered to TTS within 500ms of user finishing speaking.

**Architecture change**:

```
Current (blocking):
  agent.invoke() → complete response → HTTP response → TTS

Proposed (streaming):
  agent.stream() → SSE tokens → edge_voice accumulates sentences → TTS plays incrementally
```

**Implementation plan**:

1. **`response_node`** — Replace `_response_llm.invoke()` with `_response_llm.stream()` for the 3 LLM paraphrase cases. Templates (already instant) can be yielded immediately.

2. **`server.py`** — Add `POST /chat/stream` endpoint that returns `text/event-stream`:
   ```python
   @app.post("/chat/stream")
   async def chat_stream(request: ChatRequest):
       async def generate():
           for token in agent.stream(request.query, request.table_id):
               yield f"data: {json.dumps({'token': token})}\n\n"
       return StreamingResponse(generate(), media_type="text/event-stream")
   ```

3. **`edge_voice/main.py`** — Connect to `/chat/stream`, accumulate tokens into sentences (break on `.`, `!`, `?`, `ạ`), feed each complete sentence to TTS for playback. This allows the TTS to start playing sentence 1 while sentence 2 is still being generated.

**Expected impact**: Perceived latency drops from 2-5s to <1s (first token appears quickly, user hears speech begin while generation continues).

### 7.2 Proactive Service Model

Add initiative-taking behaviors to the agent:

```python
# New tool: proactive_suggest
# Triggers at key moments in the conversation flow

PROACTIVE_TRIGGERS = {
    "after_add_no_drinks": {
        "condition": lambda state: state.cart_has_food and not state.cart_has_drinks,
        "suggestion": "Dạ, anh/chị có muốn gọi thêm đồ uống không ạ?",
    },
    "after_confirm": {
        "condition": lambda state: state.order_stage == "CONFIRMED",
        "suggestion": "Dạ, món sẽ được chuẩn bị trong khoảng 15-20 phút. Anh/chị cần thêm gì không ạ?",
    },
    "empty_table_long": {
        "condition": lambda state: state.idle_time > 180,  # 3 minutes
        "suggestion": "Dạ, anh/chị đã muốn gọi món chưa ạ?",
    },
    "food_pairing": {
        "condition": lambda state: state.cart_has_specific_dish("Ốc Hương"),
        "suggestion": "Dạ, món Ốc Hương ăn kèm bánh mì rất ngon, anh/chị có muốn thêm không ạ?",
    },
}
```

### 7.3 Conversation Memory Summarization

Long conversations (>15 turns) exceed the 8192 token context window. Add periodic summarization:

```python
# In state_outcome_node, after every 8 turns:
def _maybe_summarize(state: AgentState) -> Optional[str]:
    turn_count = count_turns(state["messages"])
    if turn_count % 8 == 0 and turn_count > 0:
        summary = _response_llm.invoke([
            SystemMessage(content="Tóm tắt cuộc hội thoại này bằng tiếng Việt..."),
            HumanMessage(content=format_history_for_llm(state["messages"]))
        ])
        state["conversation_summary"] = summary.content
        # Next turns use summary instead of full history to save tokens
```

### 7.4 Hot-Reload Menu & Indices

```python
# New file: src/agent_brain/services/menu_watcher.py
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class MenuChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("menu.json"):
            logger.info("Menu changed — rebuilding indices...")
            builder = IndexBuilder()
            builder.rebuild()  # Rebuild FAISS + BM25
            CentroidBuilder().rebuild()  # Recompute centroids
            # Reload in-memory references
            menu_manager.reload()
            logger.info("Indices rebuilt and reloaded.")

# Start watcher in server.py lifespan
observer = Observer()
observer.schedule(MenuChangeHandler(), path=str(PROJECT_ROOT / "assets/data"))
observer.start()
```

### 7.5 A/B Testing Framework

```python
# In graph.py
class AIWaiterGraph:
    def __init__(self, prompt_variant: str = "default"):
        self.prompt_variant = prompt_variant
        # Load variant-specific prompts from resources/prompts/{variant}/
```

Run variants side-by-side on production traffic, route a percentage to each variant, collect metrics. This allows systematic prompt optimization backed by data.

### 7.6 Comprehensive Latency Profiling

Build on the existing `@trace_latency` decorator to collect per-node timing:

```python
# Collect metrics per node
METRICS = {
    "router": {"p50": [], "p95": [], "p99": [], "errors": 0},
    "order_worker": {"p50": [], "p95": [], "p99": [], "errors": 0},
    "search_worker": {"p50": [], "p95": [], "p99": [], "errors": 0},
    "validator": {"p50": [], "p95": [], "p99": []},
    "tools": {"p50": [], "p95": [], "p99": []},
    "response_node": {"p50": [], "p95": [], "p99": []},
    "total_turn": {"p50": [], "p95": [], "p99": []},
}
```

Export as Prometheus metrics for Grafana dashboards.

---

## 8. Summary & Priority Matrix

| Priority | Phase | Change | Effort | Impact | Risk |
|----------|-------|--------|--------|--------|------|
| P0 | Quick Win | Delete deprecated code (sync_cart, critic, commented code) | 1 day | Low | None |
| P0 | Quick Win | Fix code duplication (last_user_text, SyncCartResponse) | 1 day | Low | None |
| P0 | Quick Win | Remove module-level side effects (MENU_NAMES) | 0.5 day | Low | None |
| P0 | Quick Win | Add ruff + mypy config | 0.5 day | Medium | None |
| P0 | Phase 1 | **Upgrade model to qwen2.5:7b** | 2 days | **Very High** | Low (Ollama pull + config change) |
| P0 | Phase 1 | Add chain-of-thought prompts | 3 days | **High** | Low (reversible, eval-backed) |
| P0 | Phase 1 | Run evals, establish baselines | 2 days | High | None |
| P1 | Phase 1 | Add CI eval gate | 3 days | High | Medium (needs GPU runner) |
| P1 | Phase 2 | Entity tracker for reference resolution | 4 days | High | Medium (new module) |
| P1 | Phase 2 | Upgrade order stage FSM | 5 days | High | High (state machine changes) |
| P1 | Phase 2 | Multi-intent conditional execution | 3 days | Medium | Medium |
| P2 | Phase 2 | Conversation planner (macro orchestrator) | 5 days | Medium | Medium |
| P2 | Phase 3 | Streaming response pipeline | 8 days | **Very High** | High (cross-layer changes) |
| P2 | Phase 3 | Proactive service model | 5 days | Medium | Low |
| P2 | Phase 3 | Conversation memory summarization | 3 days | Medium | Low |
| P3 | Phase 3 | Hot-reload menu & indices | 3 days | Low | Low |
| P3 | Phase 3 | A/B testing framework | 5 days | Medium | Low |
| P3 | Phase 3 | Latency profiling dashboard | 3 days | Low | None |

### The Critical Path

```
Quick Wins (1 week)
    ↓
Upgrade Model + CoT Prompts (1 week)
    ↓
Eval Baselines + CI Gate (1 week)
    ↓  ← THE WALL IS HERE. Once through:
Entity Tracker → Order Stage FSM → Streaming → Proactive Service
```

---

## Appendix: Current Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        AGENT BRAIN                               │
│                                                                  │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│  │  Router  │   │   Workers    │   │     Guardrails          │  │
│  │          │   │              │   │                        │  │
│  │ Semantic │   │ order_worker │   │ deterministic_validator│  │
│  │  (fast)  │──▶│ search_worker│──▶│   - menu resolution    │  │
│  │    │     │   │ pay_dispatch │   │   - modifier extraction │  │
│  │    ▼     │   │ chat_worker  │   │   - cart restoration   │  │
│  │   SLM    │   │              │   │   - circuit breaker     │  │
│  │ (fallbk) │   └──────────────┘   └───────────┬────────────┘  │
│  └──────────┘                                  │               │
│                                                ▼               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      Data Layer                           │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │  │
│  │  │  Tools   │  │   RAG    │  │   State Management   │   │  │
│  │  │ add/rm/  │  │ FAISS    │  │ active_cart          │   │  │
│  │  │ confirm/ │  │ + BM25   │  │ order_stage          │   │  │
│  │  │ pay/     │  │ + RRF    │  │ search_context        │   │  │
│  │  │ search   │  │ fusion   │  │ checkpoints.db       │   │  │
│  │  └──────────┘  └──────────┘  └──────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                │               │
│                                                ▼               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Response Layer                         │  │
│  │  state_outcome → typed ResponseContext → response_node   │  │
│  │  (build context)   (discriminated union)   (rewriter)    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```
