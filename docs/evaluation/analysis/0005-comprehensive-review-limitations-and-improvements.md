# 0005: Comprehensive Review — Limitations & Improvements

A full-system review conducted via code analysis and eval result examination. Covers component-level deep dives (router, search, payment, models), architecture-level gaps (missing interfaces, perception, web), and a prioritized roadmap toward production.

---

## Executive Summary: Where We Stand

### Layer Map

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERFACE LAYER ❌                        │
│  stt_phowhisper.py [STUB]       tts_engine.py [STUB]       │
│  vad_silero.py     [STUB]       ws_server.py   [STUB]      │
│  ros_client.py     [STUB]       ai_brain_node  [MISSING]   │
│  ai_waiter_msgs/   [EMPTY]                                  │
│  src/frontends/    [.gitkeep only]                          │
│  src/central_server/ [empty dirs]                           │
├─────────────────────────────────────────────────────────────┤
│                 ORCHESTRATION LAYER ✅                      │
│  graph.py (LangGraph)      hybrid_router_node.py            │
│  order_worker_node          search_worker_node              │
│  payment_worker_node        chat_worker_node                │
│  deterministic_validator_node   critic_node [BYPASSED]     │
├─────────────────────────────────────────────────────────────┤
│                       TOOLS ✅                              │
│  search (BM25+FAISS+RRF)    sync_cart                       │
│  confirm_order (SQLite)     request_payment (VietQR)        │
├─────────────────────────────────────────────────────────────┤
│                  INFRASTRUCTURE ✅                           │
│  config (pydantic-settings)   schemas (Pydantic models)     │
│  memory (MemorySaver)         logging + LangSmith tracing   │
│  prompt_utils (KV-cache)      menu_manager                  │
└─────────────────────────────────────────────────────────────┘
```

**The Orchestration, Tools, and Infrastructure layers are strong. The Interface layer is nearly non-existent.** The brain is excellent — but the robot has no ears, no mouth, no skin, and nobody to talk to.

### Overall Grade

| Layer | Grade | One-Line Verdict |
|---|---|---|
| Agent Workflow | **A** | LangGraph state machine with 3-step verification is production-quality |
| Hybrid Router | **A** | Semantic+SLM cascading with 91.25% accuracy on 80 benchmarks |
| Validation | **A-** | Deterministic validator with fuzzy matching is solid; critic bypassed |
| Search Engine | **A-** | BM25+FAISS+RRF with VN tokenizer; missing ingredients in index |
| Tool Design | **B+** | Well-isolated; string protocol fragile, payment reads from LLM not state |
| Schemas & Config | **B+** | Typed throughout; config not wired to ROS, no model registry |
| ROS Integration | **F** | Entry point doesn't exist. Can't `ros2 run`. No custom messages. |
| Perception (STT/VAD/TTS) | **F** | 0 lines of code across 3 empty files |
| Web/UI Layer | **F** | Customer UI, Kitchen KDS, Central Server all `.gitkeep` only |
| Testing | **C** | 1 integration test. No unit tests. No CI. |

---

## A. Hybrid Router (Semantic + SLM)

### Current Performance

- **Latest eval (80 cases):** 91.25% accuracy (73/80)
- **31/80 routed by SEMANTIC** (fast path, ~15ms)
- **49/80 routed by SLM** (slow path, ~1-2s single, ~2-3s multi)
- **7 failures**, all "hard" difficulty

### 7 Failure Cases

| ID | Input | Expected | Got | Root Cause |
|----|-------|----------|-----|------------|
| RT-006 | "Ừ, mình đồng ý với đơn đó" | [ORDER] | [CHAT] | Implicit confirm without food names. SLM needs conversation context. |
| RT-032 | "Dị ứng tôm, có món nào thay thế cho Tôm Sú Chiên Xù không?" | [SEARCH] | [SEARCH, ORDER] | "thay thế cho" falsely triggers ORDER intent. |
| RT-046 | "Bàn mình gọi 3 món rồi, tổng hết bao nhiêu rồi nhỉ?" | [PAYMENT] | [SEARCH] | "bao nhiêu" triggers SEARCH. SLM can't distinguish price inquiry from bill total. |
| RT-067 | "Hủy Mực Nướng rồi gọi Sườn Non thay vào, và cho tôi xem menu đồ uống" | [ORDER, SEARCH] | [SEARCH, ORDER] | Correct intents, WRONG ORDER. Temporal grammar ("rồi", "và") not parsed. |
| RT-069 | "Cho mình xem tổng hóa đơn, nếu dưới 200k thì gọi thêm Chè Khúc Bạch" | [PAYMENT, ORDER] | [SEARCH, ORDER] | "Xem hóa đơn" classified as SEARCH, not PAYMENT. |
| RT-078 | "Cho mình hỏi Đậu Hũ Lướt Ván là chay không? Nếu chay thì gọi 2 phần, rồi in bill" | [SEARCH, ORDER, PAYMENT] | [SEARCH, ORDER] | **Dropped 3rd intent** (PAYMENT). Zero triple-intent few-shot examples exist. |
| RT-079 | "Mình ăn xong Phở rồi, giờ cho xem menu đồ uống rồi tính tiền luôn" | [SEARCH, PAYMENT] | [CHAT, PAYMENT] | "Ăn xong" classified as CHAT instead of recognizing full multi-intent flow. |

### Pattern: 5 of 7 failures are SEARCH vs PAYMENT confusion

The SLM defaults to SEARCH for any query containing "bao nhiêu", "xem", "hóa đơn" — words shared by both SEARCH and PAYMENT.

### Improvements

| Priority | Issue | Fix | Effort |
|----------|-------|-----|--------|
| **P1** | SEARCH vs PAYMENT confusion | Add 2 PAYMENT-specific few-shots ("xem hóa đơn", "tổng bao nhiêu") to `router.json` | Edit 1 file |
| **P1** | Dropped 3rd intent | Add 2-3 triple-intent few-shots to `router.json` | Edit 1 file |
| **P2** | Single global threshold (0.85) hurts ORDER recall | Calibrate per-intent thresholds from eval data (ORDER=0.78, SEARCH=0.80, PAYMENT=0.82, CHAT=0.76) | ~10 lines in hybrid_router_node.py |
| **P2** | 1-NN semantic matching is brittle (single utterance dominates) | Switch to centroid-based classification (mean embedding per intent) | ~15 lines in semantic_router_node.py |
| **P3** | Intent order penalized but temporal grammar not parseable | Add partial credit metric in eval and/or Vietnamese temporal keyword rules in system prompt | Edit eval + router_agent.md |
| **P3** | No SLM confidence score | Add `confidence: float` to `IntentPrediction` schema + meta-confidence combining semantic + SLM | Edit schema + hybrid_router |
| **P4** | BAAI/bge-m3 is generic multilingual | Test `keepitreal/vietnamese-sbert` for better VN intent separation | 1 model swap + re-eval |
| **P4** | Utterance imbalance (ORDER=46, PAYMENT=18) | Add 10+ PAYMENT utterances to `utterances.json` | Edit 1 file |

---

## B. Search Worker & Hybrid Retriever

### BM25

**Good:** Uses `underthesea.word_tokenize` (best VN tokenizer), parallel execution with `ThreadPoolExecutor(max_workers=2)`, pickle-based persistence.

**Limitations:**

| Issue | Detail | Fix |
|-------|--------|-----|
| **BM25 only indexes metadata, not full page_content** | Only `name + title + taste_profile + tags` are indexed. `ingredients` and `description` are NOT in BM25. User searching "tôm" finds only dishes with "tôm" in name/tags, not in ingredients. | Add `ingredients` + truncated `description` to BM25 text in `bm25.py:34-39` |
| **RRF gatekeeper too aggressive** | `top_vector_score >= 0.35` hardcoded threshold. Conceptual queries ("món cho trẻ em") get 0.25 even for correct documents and are silently rejected. | Make configurable, or add fallback "popular dishes" path |
| **ThreadPoolExecutor never shut down** | `self.executor` created in `__init__` but never `shutdown()`. Leaks threads on multiple instantiations. | Add `__del__` or explicit `close()` method |

### Vector Store (FAISS)

**Good:** Uses `AITeamVN/Vietnamese_Embedding` (VN-specific embedding model), LangChain FAISS wrapper for persistence.

**Limitations:**

| Issue | Detail | Fix |
|-------|--------|-----|
| L2 distance normalized to 0-1, not directly comparable to BM25 scores | Weighted fusion (0.6 BM25 + 0.4 Vector) adds incomparable score types | Calibrate weights from retrieval eval data |

### Search Tool Output

**Limitation:** The `search` tool returns plain text:
```python
return "\n---\n".join([f"[{r.doc_type}] {r.document.page_content}" ...])
```
The LLM receives the full page_content text and must re-parse Vietnamese-formatted fields (price, diet_type, category) from unstructured text. This is error-prone.

**Fix:** Return structured text with explicit field labels:
```python
f"[{r.doc_type}] {name} | Giá: {price:,}đ | Loại: {diet_type} | Danh mục: {category}\n{description}"
```

### Retrieval Eval Results (25 cases × 2 modes)

| Metric | RRF | Weighted |
|--------|-----|----------|
| Avg Precision@3 | 0.493 | 0.493 |
| Avg Recall | 0.71 | 0.74 |
| MRR | 0.80 | 0.79 |
| Hit Rate | 0.88 | 0.88 |

**3 queries with 0% hit rate:**
- SR-016: "món nhiều đạm, tốt cho sức khỏe"
- SR-017: "món nước thanh mát"
- SR-025: "gọi thứ ngon nhất cho 2 đứa trẻ"

**Root cause:** `menu.json` lacks metadata fields like `health_tags`, `kid_friendly`, `meal_type`, `spice_level`. These conceptual queries cannot match against existing tags.

**Fix:** Add fields to `menu.json`:
```json
{
  "health_tags": ["giàu đạm", "ít béo", "bổ dưỡng"],
  "suitable_for": ["trẻ em", "người già"],
  "meal_type": ["món nước", "món khô", "tráng miệng"],
  "spice_level": 2
}
```
And include them in BM25 text.

---

## C. Payment Worker

### Current State

- `PaymentManager` generates VietQR image links via `img.vietqr.io`
- Hardcoded bank credentials: `bank_id="ICB"`, `account_no="123456789"`
- `request_payment` tool takes `amount` from LLM args (not from state)
- No payment status tracking in AgentState
- No webhook/callback for payment confirmation
- Uses generic `waiter_agent.md` prompt (same as chat_worker)

### Improvements

| Priority | Issue | Fix | Effort |
|----------|-------|-----|--------|
| **P2** | No payment state machine | Add `payment_status: Literal["UNPAID", "PENDING", "PAID", "FAILED"]` and `payment_amount` to AgentState | Edit state.py |
| **P2** | Amount from LLM, not state | Read `total_price` from `state["active_cart"]` instead of trusting LLM args. Flag discrepancies. | ~5 lines in payment.py |
| **P2** | No payment-specific system prompt | Create `payment_agent.md` prompt (cart total confirmation, payment methods, split bill, payment verification) | New file + edit payment_worker |
| **P2** | No error handling | Add try/except around LLM invoke in `payment_worker_node.py` | ~5 lines |
| **P3** | Hardcoded mock credentials | Extract bank_id/account_no to `.env` config | Edit .env.template |
| **P4** | No webhook for payment confirmation | Add webhook endpoint to receive VietQR/IPN callbacks | New endpoint |
| **P4** | No idempotency | Calling `request_payment` twice generates two different links. Add idempotency key from cart hash. | Edit payment tool |

---

## D. Model Selection

### Current Stack

| Component | Current Model | Assessment |
|-----------|--------------|------------|
| Semantic Router | `BAAI/bge-m3` (SentenceTransformer) | Good multilingual. VN-specific may be better. |
| SLM Router | `qwen2.5:3b` (Ollama) | Good for edge. Lightweight, reasonable VN support. |
| Worker LLM | `llama3.1:latest` (Ollama) | **Poor choice.** Weak Vietnamese support. |
| Vector Store | `AITeamVN/Vietnamese_Embedding` (HuggingFace) | **Excellent.** VN-specific. |
| BM25 Tokenizer | `underthesea.word_tokenize` | **Excellent.** Best VN tokenizer. |

### llama3.1 Problem

`llama3.1:latest` (Meta) has weak Vietnamese. Your prompts are in English but responses must be Vietnamese. Evidence: E2E-003 Turn 3 — user asks for "Chả Giò Tôm Cua", LLM responds about completely different items (Lẩu Thái, Bò Nướng) from stale/previous cart state. The model struggles with Vietnamese item tracking.

### Recommended Alternatives

| Model | Size | Vietnamese Quality | Jetson Latency | Recommendation |
|-------|------|-------------------|----------------|----------------|
| `qwen2.5:7b` | 7B | Good (Alibaba-trained) | ~2-4s | **Best quality/speed tradeoff** |
| `qwen2.5:3b` | 3B | Decent, fast | ~0.5-1s | Use if latency > quality |
| `gemma2:9b` | 9B | Strong multilingual | ~3-5s | Good quality, slower |
| `vilm/vinallama-7b-chat` | 7B | Native Vietnamese | ~2-4s | Best VN quality |

### Improvements

| Priority | Issue | Fix | Effort |
|----------|-------|-----|--------|
| **P0** | llama3.1 has weak VN support | Swap `WORKER_MODEL` to `qwen2.5:7b` or `qwen2.5:3b` | 1 config line in `.env` |
| **P3** | BAAI/bge-m3 may suboptimal for VN intent classification | Test `keepitreal/vietnamese-sbert` for semantic router | 1 model swap + re-eval |
| **P4** | No fallback model if Ollama crashes | Add `FALLBACK_MODEL` config + retry logic (2 retries, exponential backoff) | ~15 lines |

---

## E. System Architecture

### Strengths (confirmed)

- **Blackboard pattern** via LangGraph `AgentState` (TypedDict) — clean shared state
- **3-step verification** (IDLE → DRAFTING → AWAITING_CONFIRMATION → CONFIRMED) with Python-only state transitions — production-grade
- **Hybrid router** (semantic fast-path + SLM fallback) — correct cascading pattern
- **Tool isolation** — each worker only has the tools it needs (chat_worker has zero tools)
- **Structured output** via Pydantic schemas throughout

### Weaknesses & Fixes

#### Critical

| Issue | Detail | Fix | Effort |
|-------|--------|-----|--------|
| **Database wipe on init** | `order_db.py:20` → `DROP TABLE IF EXISTS orders` on every startup. Destroys production data. | Add env check: `if settings.ENV == "production": raise RuntimeError` | ~3 lines |
| **Live API key in .env** | `lsv2_pt_10bf1897...` is a live LangSmith key in plaintext | Rotate immediately on LangSmith dashboard. Confirm `.env` is in `.gitignore`. | 5 min |
| **Circuit breaker never fires** | `loop_count` is incremented but no edge checks it. Stuck LLM loops infinitely: `order_worker → validator → order_worker → ...` | Add `if loop_count >= 3: return END` in `route_after_validator()` | 3 lines in graph.py |
| **Stale search_context** | `chat()` method restores `order_stage` from checkpointer but doesn't reset `search_context`. Stale search results leak to next turn. | Add `"search_context": None` to `chat()` inputs | 1 line |

#### High

| Issue | Detail | Fix | Effort |
|-------|--------|-----|--------|
| **String protocol for tool→graph communication** | `"SYNC_CART_SUCCESS:" in content` — one typo breaks entire ordering flow silently. | Add `ToolResult` Pydantic model with `action: Literal[...]` enum. Return from tools, parse in `state_updater`. | ~30 lines |
| **3 worker nodes missing error handling** | `chat_worker`, `payment_worker`, `search_worker` have no try/except around LLM calls. Ollama crash = graph crash. | Copy pattern from `order_worker_node.py:108-112` | ~12 lines |
| **sync_cart no error handling** | `sync_cart.py:17-27` — if `menu_manager.get_price()` throws or `cart.model_dump_json()` fails, graph crashes. | Add try/except with ERROR return | ~6 lines |
| **No input length guard** | 50KB message → blows LLM context → OOM crash. | Add pre-processing node that rejects messages > 1000 chars | ~10 lines |
| **routing_meta not declared in AgentState** | `hybrid_router_node` returns `routing_meta` field but `AgentState` TypedDict doesn't declare it. Checkpointer may silently drop it. | Add `routing_meta: Optional[Dict[str, Any]]` to AgentState | 1 line |

#### Medium

| Issue | Detail | Fix | Effort |
|-------|--------|-----|--------|
| **critic_node is implemented but not wired** | 61 lines of LLM reflection logic. Graph comment says `# Skips Critic!`. Either integrate or remove. | Delete file or keep as reference. | — |
| **eval_e2e.py / eval_pizza.py duplication** | ~90% identical code. Bug fix in one doesn't apply to other. | Merge into single script with `--data-file` CLI arg | ~20 lines |
| **E2E eval only 4 scenarios** | 3/4 pass (75%). Need 20+ for statistical confidence. | Add scenarios for ambiguous items, modifications, payment flow, multi-intent, typos | Edit JSON files |
| **MenuManager initialized at import time** | If menu JSON is missing/corrupt, import crashes before any request served. | Lazy-load or wrap in try/except | ~5 lines |
| **Payment worker uses generic prompt** | No `payment_agent.md`. Uses same `waiter_agent.md` as chat_worker. | Create dedicated payment prompt | New file |
| **No rate limiting** | User can spam orders endlessly. | Simple per-session rate limiter | ~20 lines |
| **No auth/roles** | No distinction between admin, customer, kitchen staff. | Future: JWT or API key auth | Architecture decision |

#### Low

| Issue | Detail | Fix | Effort |
|-------|--------|-----|--------|
| **Diagram outdated** | `the_diagram.md` shows `menu_worker_node` but code uses `search_worker_node`. Shows simplified edges (menu_worker → END) but actual code routes through tools/state_updater. | Update diagram to match current `graph.py` | Edit 1 file |
| **graph_diagram.md shows Phase 2 as IN PROGRESS** | The popping stack router and dispatcher acknowledgment are not yet in graph.py. | Implement ADR 0004 Phase 2 | Significant |
| **No TTL on conversation storage** | SQLite checkpointer sessions accumulate indefinitely. | Add session expiry or max sessions config | ~10 lines |
| **ROS2 navigation empty** | `ai_waiter_nav/config/`, `launch/`, `maps/` are empty directories. | Fill or remove | — |
| **WebSocket server exists but not integrated** | `ws_server.py` stub not wired into main application. | Integrate or remove | — |

---

## F. Missing Interface Layer — Critical Gaps

The brain is strong. Everything that connects the brain to the real world is missing.

### F.1 — ROS 2 Entry Point Does Not Exist

`setup.py:61` declares:
```python
'ai_brain = ai_waiter_core.interfaces.ros_nodes.ai_brain_node:main'
```

But `interfaces/ros_nodes/ai_brain_node.py` does not exist. The directory contains only an empty `__init__.py`. You **cannot launch** the system via `ros2 run`. The LangGraph brain has no bridge to the ROS ecosystem.

**Fix:** Create `ai_brain_node.py` as an `rclpy.Node` subclass wrapping `AIWaiterGraph`:
- Subscribe to `/waiter/user_text` (text from STT node)
- Publish to `/waiter/response_text` (TTS + state updates)
- Publish cart/order state to typed topics for frontend sync
- Use ROS params for runtime config overrides

**Effort:** 1 day

### F.2 — Custom ROS Messages Do Not Exist

`ai_waiter_msgs/` is an empty directory. All inter-node communication is string-based with no type safety.

**Fix:** Define `.msg` files:
- `TableRequest.msg` — `string table_id`, `string user_text`
- `WaiterResponse.msg` — `string text`, `string action`, `string order_stage`
- `CartUpdate.msg` — `OrderItem[] items`, `float32 total_price`

**Effort:** 0.5 day

### F.3 — Perception Pipeline: Zero Lines of Code

| Component | File | Status |
|-----------|------|--------|
| Voice Activity Detection | `perception/vad_silero.py` | Empty file |
| Speech-to-Text | `perception/stt_phowhisper.py` | Empty file |
| Text-to-Speech | `output/tts_engine.py` | Empty file |

The system is text-only. Without these, customers cannot speak to the robot.

**Implementation order:**
1. **STT first** — `faster-whisper` with `openai/whisper-large-v3-turbo` + Silero VAD chunking. Skip PhoWhisper v1 — Turbo is good enough for restaurant Vietnamese and 4x faster.
2. **TTS second** — XTTS v2 with voice cloning, or Edge TTS for MVP (free, zero setup).
3. **VAD last** — Silero VAD as gating filter before STT.

Each should be a **separate ROS node**, not embedded in the brain node. This preserves modularity and allows swapping implementations.

### F.4 — Web Frontend: Zero Lines of Code

```
src/frontends/customer_ui/   → .gitkeep only
src/frontends/kitchen_kds/   → .gitkeep only
src/central_server/api/      → empty directory
src/central_server/db/       → empty directory
```

There is no web server, no API, no frontend. The `ws_server.py` stub was intended as the WebSocket gateway but was never started.

### F.5 — ROS Navigation Packages Empty

`ai_waiter_nav/config/`, `launch/`, `maps/` are empty. `ai_hw_bridge/` is disabled with `COLCON_IGNORE`. The robot has no navigation or motor control software.

---

## G. Web Integration — Architecture & Plan

### G.1 — Target Architecture

```
                          ┌──────────────────────┐
                          │    Central Server     │
                          │  (FastAPI + WS)       │
                          │  - REST API           │
                          │  - WebSocket Gateway  │
                          │  - PostgreSQL         │
                          └──────┬───────────────┘
                                 │ WebSocket
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
        ┌──────────┐    ┌──────────────┐   ┌──────────┐
        │ Customer │    │   Kitchen    │   │  Admin   │
        │   UI     │    │     KDS      │   │  Panel   │
        │ (React)  │    │  (React)     │   │ (React)  │
        └──────────┘    └──────────────┘   └──────────┘

                         ▲
                         │ WebSocket
                         │
              ┌──────────┴──────────┐
              │    Robot (Jetson)    │
              │  ws_server.py [NEW]  │
              │  AIWaiterGraph       │
              │  STT / TTS / VAD     │
              │  ROS2 brain node     │
              └─────────────────────┘
```

**Decision:** Split into three tiers:
1. **Central Server** (hosted/VPS) — API + WebSocket broker + DB. Single source of truth for web-facing state.
2. **Robot Edge** (Jetson) — AI inference, perception, local tool execution. Upstream sync via WebSocket.
3. **Web Frontends** — React SPA apps for customer tablet, kitchen KDS, and admin panel.

### G.2 — Tech Stack Recommendations (2026)

| Tier | Recommendation | Why |
|------|---------------|-----|
| Backend | **FastAPI** | Native async, built-in WebSocket, auto-docs. Lighter than Django. |
| ORM | **SQLAlchemy 2.0** (async) | Mature, Alembic migrations. |
| Robot Bridge | **`websockets`** library | Bidirectional, persistent connection, automatic reconnect. |
| Frontend | **React + Vite + Tailwind** | Vite SPA (not Next.js, no SSR needed). Tailwind for rapid tablet UI. |
| State Sync | **TanStack Query** | Server state caching, optimistic updates for cart/orders. |
| STT | **faster-whisper** (turbo) | 4x faster than Whisper, good enough VN accuracy. |
| TTS | **XTTS v2** or **Edge TTS** | XTTS for offline; Edge TTS free for MVP. |

### G.3 — Phased Implementation Plan

**Phase A: Central Server (3 days)**
```
src/central_server/api/
├── main.py              # FastAPI app
├── routes/
│   ├── orders.py        # Order CRUD
│   ├── menu.py          # Menu read endpoints
│   ├── sessions.py      # Table sessions
│   └── ws_bridge.py     # WebSocket robot ↔ frontend
├── models/database.py   # SQLAlchemy models
└── schemas/api_schemas.py
```
Key endpoints: `POST /api/sessions`, `GET /api/menu`, `GET /api/orders/{table_id}`, `WS /ws/robot/{id}`, `WS /ws/table/{id}`

**Phase B: Robot WebSocket Bridge (2 days)**
Implement `ws_server.py` as a WebSocket client connecting robot → central server. Acts as a transparent bridge: receives user text from server, passes to `AIWaiterGraph.chat()`, streams responses back with state updates.

**Phase C: Frontends (7 days)**
- **Customer UI** (4 days) — Menu browsing, cart, voice/text input, QR payment
- **Kitchen KDS** (3 days) — Order queue, status management, alerts

**Phase D: Perception Integration (3.5 days)**
- STT ROS node publishing to `/waiter/user_text`
- TTS ROS node subscribing to `/waiter/response_text`
- VAD gating before STT

---

## H. Architectural Principles

1. **ROS = Hardware layer only.** The brain (LangGraph), tools, schemas remain ROS-agnostic. Only `interfaces/` depends on `rclpy`. Preserves testability and allows both ROS and web scenarios.

2. **WebSocket is primary protocol for web ↔ robot.** Not REST, not ROS topics across network. Central server acts as message broker.

3. **State owned by robot, mirrored to server.** LangGraph `AgentState` is source of truth. Server stores replica for frontend queries. Conflicts resolve to robot's state.

4. **STT/TTS are separate ROS nodes.** Publish/subscribe to standard topics. Brain node only reads/produces text. Allows swapping implementations without touching the brain.

5. **Validator → Tools → StateUpdater pattern applies to all workers.** Search and Payment should also route through validation before tool execution, not just Order.

6. **One LLM instance, many toolsets.** A single `ChatOllama` client shared across workers, with tools bound per-intent at invocation time. Reduces memory pressure on Jetson.

---

## I. Testing & Quality

### Current State

- **59 eval result files** in `evals/results/` (May 16-23) — thorough ML-style evaluation
- Router eval: 80 cases, per-intent precision/recall/F1, confusion matrix, per-difficulty tracking
- Retrieval eval: 25 cases × 2 modes, Precision@K, Recall@K, MRR, Hit Rate
- E2E eval: 4 scenarios with structured assertion grammar (tool_called, tool_output_contains, etc.)
- **9 files in `robot_ws/tests/`** — manual debugging scripts (print-based, no pytest, broken imports from refactoring)

### Improvements

| Priority | Issue | Fix | Effort |
|----------|-------|-----|--------|
| **P2** | No metric trend tracking across eval runs | Write script that reads all `*_report.json` files and plots accuracy/recall/MRR over time to detect regressions | ~20 lines |
| **P2** | Only 4 E2E scenarios | Add 10+ scenarios covering: ambiguous item resolution, modifications, payment, multi-intent, typos | Edit JSON |
| **P2** | eval_e2e + eval_pizza duplication | Merge into one script | ~20 lines |
| **P4** | No CI pipeline | Add GitHub Actions workflow that runs eval suite on push | New file |

---

## J. Consolidated Priority Roadmap

### Priority Legend
- **P0** = Critical (system unsafe/broken, fix now)
- **P1** = High (blocks core functionality or causes frequent failures)
- **P2** = Medium (quality/robustness improvement)
- **P3** = Low (cleanup, optimization)
- **P4** = Future (nice to have)

### P0: Critical — Fix Immediately

| # | Action | Component | Effort |
|---|--------|-----------|--------|
| 1 | Rotate LangSmith API key, verify `.env` in `.gitignore` | Security | 5 min |
| 2 | Swap `WORKER_MODEL` from `llama3.1` → `qwen2.5:7b` | Model | 1 config line |
| 3 | Add circuit breaker on `loop_count` (`>=3 → END`) in `route_after_validator()` | Graph | 3 lines |
| 4 | Reset `search_context` per turn in `chat()` | Graph | 1 line |
| 5 | Guard `DROP TABLE IF EXISTS orders` with env check | Database | 3 lines |
| 6 | Add try/except to 3 unprotected worker nodes + `sync_cart` | Error handling | ~18 lines |
| 7 | Add `routing_meta` to `AgentState` TypedDict | State | 1 line |
| 8 | Add input length guard node (reject > 1000 chars) | Graph | ~10 lines |
| 9 | Replace string protocol (`"SYNC_CART_SUCCESS:" in content`) with `ToolResult` Pydantic model | Graph/Tools | ~30 lines |

### P1: High — This Week

| # | Action | Component | Effort |
|---|--------|-----------|--------|
| 10 | **Create `ai_brain_node.py`** — ROS 2 node wrapping AIWaiterGraph | Interface | 1 day |
| 11 | **Define `ai_waiter_msgs/`** — TableRequest, WaiterResponse, CartUpdate messages | Interface | 0.5 day |
| 12 | **Switch MemorySaver → SqliteSaver** for persistent checkpoints | Persistence | 0.5 day |
| 13 | Add 2 PAYMENT-specific + 3 triple-intent few-shots to `router.json` | Router | Edit 1 file |
| 14 | Per-intent thresholds from eval data (ORDER=0.78, SEARCH=0.80, etc.) | Router | ~10 lines |
| 15 | Add payment state machine (`payment_status`, `payment_amount`) to AgentState | Payment | Edit state.py |
| 16 | Read payment amount from `state["active_cart"]`, not LLM args | Payment | ~5 lines |
| 17 | Add ingredients + description to BM25 text index | Search | ~5 lines |
| 18 | Structured search output with explicit field labels | Search | ~5 lines |

### P2: Medium — 1-2 Weeks

| # | Action | Component | Effort |
|---|--------|-----------|--------|
| 19 | Centroid-based semantic classification (not 1-NN) | Router | ~15 lines |
| 20 | Implement ADR 0004 Phase 2 (popping stack router, dispatcher ack) | Graph | 2 days |
| 21 | **Build Central Server skeleton** (FastAPI + WebSocket + DB) | Web | 3 days |
| 22 | Create dedicated `payment_agent.md` system prompt | Prompts | New file |
| 23 | Wire search & payment tool calls through validator (not just order) | Graph | ~15 lines |
| 24 | Add health_tags, kid_friendly, meal_type to `menu.json` | Data | Edit JSON |
| 25 | Shared LLM factory to reduce memory/Pool usage on Jetson | Infra | ~15 lines |
| 26 | Expand E2E scenarios from 4 to 20+ | Eval | Edit JSON |
| 27 | Merge `eval_e2e.py` and `eval_pizza.py` into single script | Eval | ~20 lines |
| 28 | Metric trend tracking script across eval runs | Eval | ~20 lines |
| 29 | Fix `setup.py` package listing (use `find_packages()`) | Build | ~10 lines |

### P3: Low — 2-4 Weeks

| # | Action | Component | Effort |
|---|--------|-----------|--------|
| 30 | **Implement `stt_phowhisper.py`** as ROS node (faster-whisper turbo) | Perception | 2 days |
| 31 | Add `confidence` field to `IntentPrediction` schema | Router | Edit schema |
| 32 | Test `keepitreal/vietnamese-sbert` for semantic router | Model | 1 swap + re-eval |
| 33 | Make RRF gatekeeper threshold configurable | Search | ~5 lines |
| 34 | Fix `ThreadPoolExecutor` leak in BM25 retriever | Search | ~5 lines |
| 35 | Extract bank credentials to `.env` config | Payment | Edit config |
| 36 | Idempotency key for payment link generation | Payment | ~10 lines |
| 37 | Lazy-load MenuManager (don't crash on missing JSON) | Infra | ~5 lines |
| 38 | Update `the_diagram.md` to match current `graph.py` | Docs | Edit 1 file |
| 39 | Update `waiter_agent.md` — remove reference to non-existent `verify_and_prepare_order` | Prompts | Edit 1 file |

### P4: Future — 1+ Months

| # | Action | Component | Effort |
|---|--------|-----------|--------|
| 40 | **Implement TTS** (XTTS v2 or Edge TTS) as ROS node | Output | 1.5 days |
| 41 | **Implement VAD** (Silero) as ROS node | Perception | 1 day |
| 42 | **Implement `ws_server.py`** robot WebSocket bridge | Interface | 2 days |
| 43 | **Build Customer UI** (React + Vite + Tailwind) | Frontend | 4 days |
| 44 | **Build Kitchen KDS** (React) | Frontend | 3 days |
| 45 | Payment webhook endpoint for VietQR IPN callbacks | Payment | 1 day |
| 46 | Wire critic node into graph (payment + confirmation only) | Graph | 1 day |
| 47 | Rate limiting per session | Infra | ~20 lines |
| 48 | Session expiry/TTL on conversation checkpoints | Infra | ~10 lines |
| 49 | Fill ROS2 navigation stack | ROS2 | Ongoing |
| 50 | CI/CD pipeline (GitHub Actions for eval suite on push) | DevOps | 1 day |
| 51 | Model registry for provider switching (Ollama / OpenAI / Anthropic) | Config | ~30 lines |
| 52 | Switch config to ROS param server for runtime overrides | Config | 1 day |
| 53 | Add unit test suite (pytest: validator, router, tools) | Testing | 3 days |
| 54 | Build Admin Panel UI (React) | Frontend | 3 days | |

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-05-31 | 2.0 | Merged with architecture-audit review. Added interface layer gap analysis (Sections F, G, H), web integration architecture plan, architectural principles. Consolidated roadmap expanded from 30 to 54 items with priority tiers. |
| 2026-05-27 | 1.0 | Initial comprehensive review from system audit |
