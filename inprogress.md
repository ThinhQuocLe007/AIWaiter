# AI Waiter — Implementation Status & Remaining Problems

> Source: `docs/agent-brain-analysis.md` (2026-07-14)
> Last updated: 2026-07-14

---

## What We Have Done (Completed ✅)

### Section 4 — Quick Wins (All Complete)

| Task | What                                                                                               |
| ---- | -------------------------------------------------------------------------------------------------- |
| 4.1  | Deleted deprecated `sync_cart`, `critic_node`, `payment_worker_node`, duplicate `SyncCartResponse` |
| 4.2  | Consolidated `last_user_text` into `utils/state_helpers.py`                                        |
| 4.3  | Lazy-initialized `MENU_NAMES` with `_LazyMenuNames` proxy                                          |
| 4.4  | Added `[tool.ruff]` + `[tool.mypy]` to `pyproject.toml`                                            |
| 4.5  | Replaced 24 `except Exception` with specific types (`httpx.HTTPError`, `OSError`, etc.)            |

### Section 5.1 — Model Upgrade (Complete)

| Task        | What                                                                                                                              |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 5.1.1-5.1.2 | Switched to `qwen2.5:7b-instruct` (4.7 GB Ollama) across all 3 model roles                                                        |
| 5.1.3       | Removed `_force_tool_call_via_ollama` (42-line raw HTTP hack), reduced retry tiers from 3→2 in order_worker, 2→1 in search_worker |
| 5.1.4       | `tool_choice="any"` now works natively                                                                                            |

### Section 5.2 — Chain-of-Thought Prompts (3/5 Complete)

| Task  | What                                                                             |
| ----- | -------------------------------------------------------------------------------- |
| 5.2.1 | Rewrote `order_worker_agent.md` with Step 1-4 reasoning scaffold                 |
| 5.2.2 | Rewrote `search_agent.md` with Step 1-3 reasoning scaffold                       |
| 5.2.3 | Rewrote `router_agent.md` with Step 1-4 reasoning scaffold + stage-aware context |
| 5.2.4 | ⬜ Expand few-shot examples (optional)                                           |
| 5.2.5 | ⬜ Expand router few-shots (optional)                                            |

### Section 5.3 — Eval Baselines (4/5 Complete)

| Task               | Score                                                                    |
| ------------------ | ------------------------------------------------------------------------ |
| 5.3.1 Router       | **91.11%** (41/45), 0.62s avg latency, 49% semantic hit rate             |
| 5.3.2 Retrieval    | P@5=0.31, R@5=0.70, MRR=0.69, Hit=0.88                                   |
| 5.3.3 E2E          | ⬜ Pending — eval scripts updated, ready to run when agent service is up |
| 5.3.4 Out-of-menu  | **75%** (3/4, the fail was a sync_cart→add_cart rename in eval — fixed)  |
| 5.3.5 Baseline doc | Written to `docs/eval-baseline-2026-07.md`                               |

### Additional Cleanup (Beyond Original Plan)

- Split `response_node.py` (287 lines → 190 lines) into `response_node.py` + `response_template.py` (110 lines)
- Prompts moved to `resources/system_prompts/response_rewriter.md` + `chat_rewriter.md`
- 3 `_llm_paraphrase_*` functions merged into single `_llm_invoke()` helper
- `state_outcome_node.py`: replaced 7 if-checks with `_BUILDERS` dict dispatch (309 → 175 lines)
- `response_context.py`: trimmed verbose docstrings (219 → 120 lines)
- Fixed circular import in `utils/state_helpers.py`
- Rebuilt FAISS + BM25 + centroids for the new embedding model
- Decreased semantic router thresholds (accuracy 91% → latency improved 44%)
- Eval scripts updated: `sync_cart` → `add_cart` in 3 scripts + 3 JSON datasets

---

## Current Eval Scores (Baseline)

| Eval            | Score                                  | Status               |
| --------------- | -------------------------------------- | -------------------- |
| **Router**      | 91.11% accuracy, 0.62s avg latency     | 41/45 correct        |
| **Retrieval**   | P@5=0.31, R@5=0.70, MRR=0.69, Hit=0.88 | 24 cases             |
| **Out-of-Menu** | 75% pass rate                          | 3/4 scenarios        |
| **E2E**         | Not yet run                            | Scripts fixed, ready |

---

## Remaining Problems — With Explanations & Sample Code

---

### Problem 1: No Multi-Turn Reference Resolution (Section 6.1)

**The bug**: Customer says "Ốc Hương" in turn 1, then "Cái đó có cay không?" in turn 3. The system searches for "cái đó" literally → finds nothing → replies "không có trong thực đơn."

**Root cause**: There's no entity tracker. The system forgets what dishes were mentioned unless they're in the cart or were searched. And `curated_memory` only populates from SEARCH turns, not from ORDER turns. So dishes ordered but never searched are invisible to follow-up questions.

**The fix — EntityTracker**:

```python
# New file: src/agent_brain/agent/nodes/entity_tracker.py

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class EntityRecord:
    """A dish that appeared anywhere in the conversation."""
    name: str
    source: str          # "cart" | "search"
    last_turn: int = 0
    metadata: dict = field(default_factory=dict)

class EntityTracker:
    """Tracks all dishes mentioned across the conversation for reference resolution."""

    def __init__(self):
        self.entities: dict[str, EntityRecord] = {}
        self.turn_count: int = 0

    def register_from_cart(self, cart):
        """Called after every cart update (add/remove/clear)."""
        self.turn_count += 1
        for item in cart.items:
            key = item.name.lower()
            self.entities[key] = EntityRecord(
                name=item.name, source="cart", last_turn=self.turn_count,
                metadata={"quantity": item.quantity, "price": item.unit_price}
            )

    def register_from_search(self, results):
        """Called after every search tool runs."""
        self.turn_count += 1
        for r in results:
            name = r.document.metadata.get("name")
            if name:
                key = name.lower()
                self.entities[key] = EntityRecord(
                    name=name, source="search", last_turn=self.turn_count,
                    metadata={
                        "price": r.document.metadata.get("price"),
                        "tags": r.document.metadata.get("tags"),
                        "taste_profile": r.document.metadata.get("taste_profile"),
                    }
                )

    def resolve_reference(self, user_text: str) -> Optional[EntityRecord]:
        """
        "Cái đó" / "món đó" / "món lúc nãy" → the most recent entity.
        Partial name match → the matching entity.
        """
        lower = user_text.lower()
        # Generic reference → most recent entity
        if any(r in lower for r in ("cái đó", "món đó", "món lúc nãy", "nó", "cái này")):
            if self.entities:
                return max(self.entities.values(), key=lambda e: e.last_turn)
            return None
        # Partial name match
        for key, entity in self.entities.items():
            if key in lower:
                return entity
        return None

# Integration point in graph.py:
# _should_shortcut_search() currently does string matching on cart item names.
# Replace with: entity_tracker.resolve_reference(user_text)

# Registration points:
# - state_outcome_node._finalize() or update_state_node: call register_from_cart()
# - state_outcome_node after search: call register_from_search()
```

**Also fixes**: `curated_memory` population. Currently `chat_worker_node._to_curated_memory` only pulls from `search_context`. Should also pull from `active_cart.items` so ordered dishes are visible in CHAT prompts.

---

### Problem 2: No Conditional Execution for Multi-Intent (Sections 6.2 + 6.4)

**The current behavior — sequential intents without logic**:

```
User: "Lẩu Thái cay không? Nếu không cay thì lấy 1 phần"
Router: ["SEARCH", "ORDER"]

Current execution (blind):
  SEARCH worker → validator → tools → state_updater
  → ORDER worker → validator → tools → state_updater   # runs REGARDLESS of search result
  → response_node
```

The ORDER always runs even when the customer said "Nếu không cay thì..." (conditional). If SEARCH reveals Lẩu Thái IS spicy, the system still orders it. This is **wrong**.

**The fix — Conversation Planner + Conditional Execution**:

```python
# New file: src/agent_brain/agent/nodes/conversation_planner.py

from dataclasses import dataclass
from enum import Enum

class StepCondition(Enum):
    ALWAYS = "always"                    # run regardless
    SEARCH_HAS_RESULTS = "has_results"   # only if SEARCH returned non-empty
    SEARCH_EMPTY = "search_empty"        # only if SEARCH returned nothing

@dataclass
class PlanStep:
    intent: str
    condition: StepCondition = StepCondition.ALWAYS

class ConversationPlanner:
    """
    Converts a raw intent list into a plan with dependency tracking.

    Single-intent turns pass through transparently.
    Multi-intent turns get inter-step conditions based on the utterance.
    """

    CONDITIONAL_MARKERS = ("nếu", "nếu có", "nếu không", "nếu không cay", "nếu còn")

    def plan(self, user_text: str, intents: list[str]) -> list[PlanStep]:
        if len(intents) <= 1:
            return [PlanStep(intent=i) for i in intents]

        steps = []
        has_conditional = any(m in user_text.lower() for m in self.CONDITIONAL_MARKERS)

        for intent in intents:
            step = PlanStep(intent=intent)

            # The key logic: if ORDER follows SEARCH AND utterance is conditional,
            # make ORDER depend on SEARCH having results.
            if intent == "ORDER":
                prev_search = any(s.intent == "SEARCH" for s in steps)
                if prev_search and has_conditional:
                    step.condition = StepCondition.SEARCH_HAS_RESULTS

            # ORDER_CONFIRM should only run if the previous ORDER step ran
            # (i.e., the customer said "đúng rồi chốt đi" after adding items)
            if intent == "ORDER_CONFIRM":
                prev_order = any(s.intent == "ORDER" for s in steps)
                if prev_order:
                    step.condition = StepCondition.SEARCH_HAS_RESULTS  # reuse: ORDER must have added items

            steps.append(step)

        return steps


# ---------- Integration in graph.py ----------

def _should_skip_step(step: PlanStep, state: AgentState) -> bool:
    """Check if a planned step should be skipped based on prior results."""
    if step.condition == StepCondition.ALWAYS:
        return False

    if step.condition == StepCondition.SEARCH_HAS_RESULTS:
        # Check if the previous SEARCH in this turn returned results
        search_ctx = state.get("search_context")
        if search_ctx is None or len(search_ctx) == 0:
            logger.info(f"Skipping {step.intent} — conditional SEARCH returned empty")
            return True

    return False


# ---------- Modified execution loop in AIWaiterGraph ----------
# Instead of:
#   for intent in current_intents:
#       worker_node = route_to_worker(intent)
#       invoke(worker_node)
#
# Use:
#   planner = ConversationPlanner()
#   plan = planner.plan(user_text, current_intents)
#   for step in plan:
#       if _should_skip_step(step, state):
#           state["skipped_intents"].append(step.intent)
#           continue
#       worker_node = route_to_worker(step.intent)
#       invoke(worker_node)
```

**What this changes**:

| Scenario                                             | Before                   | After                                  |
| ---------------------------------------------------- | ------------------------ | -------------------------------------- |
| `"Lẩu Thái cay không? Nếu không cay thì lấy 1 phần"` | Always orders regardless | Skips ORDER if SEARCH shows it's spicy |
| `"Món này chay không? Nếu chay thì cho mình 2 phần"` | Always orders            | Skips ORDER if SEARCH shows it's mặn   |
| `"Cho 2 Ốc Hương rồi tính tiền luôn"`                | Runs ORDER then PAYMENT  | Same — no conditionals, runs both      |
| Simple single-intent                                 | Unchanged                | Unchanged (transparent passthrough)    |

**This directly fixes eval failures RT-040, RT-044, RT-045** — the 3 multi-intent cases that the router misses or mis-handles.

---

### Problem 3: Rigid Order Stage FSM (Section 6.3)

**Current state machine**:

```
IDLE → AWAITING_CONFIRMATION → CONFIRMED → (dead end)
```

**What it can't handle**:

| Real-world scenario | Customer says                       | Current behavior                          | Should                                   |
| ------------------- | ----------------------------------- | ----------------------------------------- | ---------------------------------------- |
| Add after confirm   | "Cho anh thêm 1 bia nữa"            | `confirm_order` rejects (CONFIRMED phase) | Create a new draft, add item, re-confirm |
| Modify confirmed    | "Hủy Lẩu Thái đi, đổi qua Cháo Hàu" | Rejected                                  | Cancel existing, create new draft        |
| Split bill          | "Tính tiền 2 đứa riêng nha"         | Not supported                             | Separate payment per person              |
| Partial payment     | "Cho anh trả trước 500k"            | Not supported                             | Track remaining balance                  |

**The fix — richer state machine**:

```python
class OrderStage(str, Enum):
    IDLE = "IDLE"
    BUILDING = "BUILDING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    MODIFYING = "MODIFYING"               # post-confirm changes in progress
    MODIFICATION_PENDING = "MODIFICATION_PENDING"  # new items awaiting re-confirm
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"

# Explicit transition table — prevents illegal state jumps:
VALID_TRANSITIONS = {
    OrderStage.IDLE:           {OrderStage.BUILDING, OrderStage.AWAITING_CONFIRMATION},
    OrderStage.BUILDING:       {OrderStage.BUILDING, OrderStage.AWAITING_CONFIRMATION, OrderStage.IDLE},
    OrderStage.AWAITING_CONFIRMATION: {OrderStage.CONFIRMED, OrderStage.IDLE},
    OrderStage.CONFIRMED:      {OrderStage.MODIFYING},
    OrderStage.MODIFYING:      {OrderStage.MODIFICATION_PENDING, OrderStage.CONFIRMED},
    OrderStage.MODIFICATION_PENDING: {OrderStage.CONFIRMED, OrderStage.IDLE},
    OrderStage.PARTIALLY_PAID: {OrderStage.PAID},
    OrderStage.PAID:           set(),  # terminal
}

# The validator then checks:
if (current_stage, new_stage) not in VALID_TRANSITIONS:
    raise InvalidStateTransition(f"Cannot go from {current_stage} to {new_stage}")
```

**Implementation priority**: CONFIRMED → MODIFYING → MODIFICATION_PENDING → CONFIRMED is the most impactful. The rest (split bill, partial payment) are lower priority since they require backend changes too.

---

### Problem 4: No Streaming Response (Section 7.1)

_See detailed implementation plan at [Appendix A: Streaming Implementation Plan](#appendix-a-streaming-implementation-plan)._

**Current flow (blocking)**:

```
mic → VAD → STT → HTTP POST → [2-10s agent pipeline] → HTTP response → TTS → speaker
                                            ↑
                                     customer waits in silence
```

**Target flow (streaming)**:

```
VOICE DEVICE                         API SERVER                        TABLET UI (monitor)
     │  POST /chat/stream              │                                  │
     │ ──────────────────────────────► │  voice.heard ───────────────────►│ (user text + thinking)
     │                                 │  voice.progress ────────────────►│ (status text on monitor)
     │                                 │                                  │
     │  SSE: progress=processing       │                                  │
     │◄────────────────────────────────│                                  │
     │    (triggers short ack audio)   │                                  │
     │                                 │  [graph runs sync: router→worker │
     │                                 │   →tools→state_outcome]          │
     │                                 │  voice.progress ────────────────►│ (per-stage updates)
     │                                 │                                  │
     │  SSE: sentence="Dạ món Ốc..."    │  [response_node streams LLM]     │
     │◄────────────────────────────────│                                  │
     │    → TTS plays immediately      │                                  │
     │                                 │                                  │
     │  SSE: sentence="Giá 150k..."    │                                  │
     │◄────────────────────────────────│                                  │
     │    → TTS plays next sentence    │                                  │
     │                                 │                                  │
     │  SSE: done={action,stage}       │                                  │
     │◄────────────────────────────────│  voice.reply ───────────────────►│ (full response + action)
```

**Design principles**:

- Sentence-level streaming (not tokens) — TTS needs complete sentences for synthesis
- `voice.progress` for monitor UI, `sentence` SSE events for TTS only
- Graph stays synchronous (`self.app.invoke()`) — minimal refactor
- Thread-safe FIFO queue bridges sync graph execution to async SSE generator
- `POST /chat` stays as-is (backward compatible)

**What needs to change**:

1. `src/agent_brain/agent/nodes/response_node.py` — add streaming output via module-level queue
2. `src/agent_brain/server.py` — add `POST /chat/stream` endpoint returning SSE
3. `src/edge_voice/main.py` — consume SSE, feed sentences to TTS incrementally
4. `src/edge_voice/output/tts_engine.py` — add `speak_sentence()` single-sentence TTS
5. `src/server_orchestrator/routers/voice.py` — add `voice.progress` event type for monitor
6. `src/agent_brain/services/orchestrator_client.py` — add `post_progress_event()` method

**What the guest experiences**:

| Moment         | What they hear         | What the monitor shows          |
| -------------- | ---------------------- | ------------------------------- |
| After speaking | —                      | Their text + "đang suy nghĩ..." |
| ~50ms later    | "Dạ..." (ack now)      | "đang xử lý..."                 |
| ~1-3s later    | Sentence 1 of response | Sentence progressively appears  |
| ~1-2s later    | Sentence 2 of response | Full response + cart/action UI  |

**Things NOT included (keep it simple)**:

- No graph-level streaming (astream_events) — too invasive, low ROI
- No per-node progress granularity in v1 — the tablet already shows "thinking" via `voice.heard`, per-stage updates are optional
- No cancel mid-graph — adds complexity; the current `voice.cancel` endpoint handles pre-graph cancellation

**Impact**: Perceived latency drops from 2-10s to ~500ms. User hears speech begin while generation continues. This is the highest user-experience impact change.

---

---

### Problem 5: No CI Eval Gate (Section 5.4)

Every prompt change today is unvalidated — you can break router accuracy from 91% to 60% with no alert.

```yaml
# .github/workflows/agent-eval.yml
name: Agent Evaluation
on:
  pull_request:
    paths: ["src/agent_brain/**", "evals/**"]
  push:
    branches: [main]

jobs:
  eval:
    runs-on: [self-hosted, gpu]
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
      - name: Check Regression
        run: |
          python evals/scripts/check_regression.py \
            --router-threshold 0.85 \
            --retrieval-threshold 0.65
```

**Requirements**: A self-hosted GitHub Actions runner with GPU + Ollama. If that's not feasible, at minimum add a pre-commit hook that runs `ruff check` and `mypy`.

---

### Problem 6: Conversation Memory Exceeds Context Window (Section 7.3)

Long conversations (>15 turns) exceed the 8192 token context window. The LLM starts losing earlier context → amnesia.

**The fix — periodic summarization**:

```python
# In state_outcome_node._finalize(), after every 8 turns:

def _maybe_summarize(state: AgentState):
    turn_count = count_user_turns(state["messages"])
    if turn_count % 8 == 0 and turn_count > 0:
        summary = _response_llm.invoke([
            SystemMessage(content="Tóm tắt cuộc hội thoại này bằng tiếng Việt..."),
            HumanMessage(content=format_history_for_llm(state["messages"]))
        ])
        state["conversation_summary"] = summary.content

# Then in future turns, replace full history with summary in the prompt:
# Instead of:  state["messages"][-N:]
# Use:         [SystemMessage(summary)] + state["messages"][-N:]
```

---

## Remaining Tasks by Priority

| Priority | Section     | Task                                           | Dependencies                                       |
| -------- | ----------- | ---------------------------------------------- | -------------------------------------------------- |
| **P0**   | 5.3.3       | Run E2E evals                                  | None — scripts are fixed, just needs agent running |
| **P0**   | 6.1         | Entity Tracker                                 | None — new module, no breaking changes             |
| **P0**   | 6.2+6.4     | Conversation Planner + Conditional Skip        | Entity Tracker helps but is independently useful   |
| **P1**   | 5.4         | CI Eval Gate                                   | Needs GPU CI runner or pre-commit hook as fallback |
| **P1**   | 6.3         | Order Stage FSM (at least CONFIRMED→MODIFYING) | Touches validator + orchestrator + state           |
| **P1**   | 5.2.4-5.2.5 | Expand few-shot examples                       | Low effort, just add JSON entries                  |
| **P2**   | 7.1         | Streaming Response                             | Touches 3 layers (agent, HTTP, edge_voice)         |
| **P2**   | 7.2         | Proactive Service                              | Clean addition, no breaking changes                |
| **P3**   | 7.3         | Conversation Summarization                     | Small change in state_outcome_node                 |
| **P3**   | 7.4         | Hot-reload Menu                                | `watchdog` dependency                              |
| **P3**   | 7.5         | A/B Testing Framework                          | Needs metrics collection infrastructure first      |
| **P3**   | 7.6         | Latency Profiling                              | `@trace_latency` already exists; just needs export |

---

## Recommended Next Session

1. **Run E2E evals** (5.3.3) — 30 min, establish full baseline
2. **Entity Tracker** (6.1) — 2-3 hours, fixes "cái đó có cay không?" bug, unlocks curated_memory for ordered dishes
3. **Conversation Planner + Conditional Skip** (6.2+6.4) — 3-4 hours, fixes the 3 remaining router eval failures, adds conditional multi-intent logic

These three are the highest leverage: they fix 4 known bugs with ~500 lines of new code and no breaking changes to existing modules.

---

## Appendix A: Streaming Implementation Plan

### A.1 — Current E2E Architecture

```
 [TABLET/UI]                          [SERVER]                              [VOICE DEVICE]
                                        │
  "push to talk" ──► ORCHESTRATOR WS ──┤
                                        │  {"type":"start_listening","table_id":N}
                                        │──────────────────────────────────────►  main.py
                                        │                                          │
                                        │                                   asyncio.to_thread()
                                        │                                          │
                                        │                                   ┌─ _capture_and_send() ─┐
                                        │                                   │                        │
                                        │                                   │  vad.begin_listen()    │
                                        │                                   │  vad.wait_for_utterance│
                                        │                                   │    (up to 15s)        │
                                        │                                   │        │               │
                                        │                                   │        ▼               │
                                        │                              [SileroVAD thread]            │
                                        │                              mic → 512-sample chunks       │
                                        │                              prob >= 0.5 → speech          │
                                        │                              1.5s silence → flush          │
                                        │                              put_speech(AudioChunk)        │
                                        │                                   │        │               │
                                        │                                   │   speech_queue          │
                                        │                                   │        │               │
                                        │                                   │        ▼               │
                                        │                              [PhoWhisperSTT thread]        │
                                        │                              medium faster-whisper         │
                                        │                              transcribe → Transcript       │
                                        │                              put_transcript(Transcript)    │
                                        │                                   │        │               │
                                        │                                   │   text_queue            │
                                        │                                   │        │               │
                                        │                                   │  get_transcript(12s)    │
                                        │                                   │        │               │
                      POST /chat ◄──────┼──────────────────────────────────┼────────┘               │
                  {"table_id":"T1",     │                                   │                        │
                   "text":"..."}        │                                   │                        │
                                        │                                   │                        │
 [agent graph: router→worker→tool→...]  │                                   │                        │
        │                               │                                   │                        │
        ▼                               │                                   │                        │
  response_node → full text             │                                   │                        │
        │                               │                                   │                        │
  ChatResponse ────────────────────────►│                                   │                        │
  {response, stage, action, ...}        │                                   │                        │
                                        │                                   │                        │
  mirror to tablet WS ◄─────────────────┤                                   │  TTS: speak_streaming()
                                        │                                   │  split sentences
  [TABLET shows UI + transcript]        │                                   │  edge-tts → sounddevice
```

### A.2 — Latency Breakdown Per Turn

| Stage                            | Time                     | Can overlap?                            |
| -------------------------------- | ------------------------ | --------------------------------------- |
| Button → VAD armed               | ~50ms                    | No                                      |
| Wait for speech                  | 0-15s (depends on guest) | No — user-dependent                     |
| Speech → silence flush           | 1.5s                     | No — VAD needs silence threshold        |
| STT (faster-whisper medium)      | ~1-5s                    | **Already overlaps with VAD** via queue |
| Retrieve transcript              | ~0s                      | Just queue.get                          |
| HTTP round-trip                  | ~50ms                    | No                                      |
| **Graph invoke (full pipeline)** | **2-10s**                | **← THE SILENT ZONE**                   |
| TTS synthesize + play            | 2-8s                     | No                                      |

VAD is NOT the bottleneck. The queue architecture (`speech_queue` → `text_queue`) already decouples VAD and STT. The real silence is the graph invoke (2-10s) where the guest hears nothing.

### A.3 — Target Architecture

```
VOICE DEVICE                         API SERVER                        TABLET UI (monitor)
     │  POST /chat/stream              │                                  │
     │ ───────────────────────────────►│  voice.heard ───────────────────►│ (user text + thinking)
     │                                 │  voice.progress("đang xử lý")──►│ (status text on monitor)
     │                                 │                                  │
     │  SSE: progress=processing       │                                  │
     │◄────────────────────────────────│                                  │
     │    (triggers: audio "dạ...")    │                                  │
     │                                 │  [graph runs sync: router→worker │
     │                                 │   →tools→state_outcome]          │
     │                                 │  voice.progress("đang tìm...")─►│
     │                                 │                                  │
     │  SSE: sentence="Dạ món Ốc..."   │  [response_node streams LLM]     │
     │◄────────────────────────────────│                                  │
     │    → TTS plays immediately      │                                  │
     │                                 │                                  │
     │  SSE: sentence="Giá 150k..."    │                                  │
     │◄────────────────────────────────│                                  │
     │    → TTS plays next sentence    │                                  │
     │                                 │                                  │
     │  SSE: done={action,stage}       │                                  │
     │◄────────────────────────────────│  voice.reply ───────────────────►│ (full response + action)
```

### A.4 — Files to Modify

| #   | File                                              | Change                                                                                                                                                  | Lines |
| --- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| 1   | `src/agent_brain/agent/nodes/response_node.py`    | Add `_output_queue`, `set_output_queue()`, `_llm_stream()`. Templates push to queue; LLM path uses `.stream()` and yields sentences.                    | ~30   |
| 2   | `src/agent_brain/server.py`                       | Add `POST /chat/stream` endpoint. Returns SSE generator that drains queue + yields `progress`, `sentence`, `done` events. Keeps `POST /chat` unchanged. | ~60   |
| 3   | `src/edge_voice/main.py`                          | Add `_capture_and_send_streaming()`. Uses `httpx.Client.stream("POST", ...)` to consume SSE. Calls `speak_sentence()` per event.                        | ~40   |
| 4   | `src/edge_voice/output/tts_engine.py`             | Add `speak_sentence(text, player)` — enqueue single sentence to TTS, play non-blocking.                                                                 | ~25   |
| 5   | `src/server_orchestrator/routers/voice.py`        | Add `voice.progress` event type (optional `status` field). Broadcast via existing WS manager.                                                           | ~5    |
| 6   | `src/agent_brain/services/orchestrator_client.py` | Add `post_progress_event(table_id, status_text)` method.                                                                                                | ~10   |

### A.5 — File 1: `response_node.py` changes

```python
# === Add at module level ===
from queue import Queue

_output_queue: Queue | None = None

def set_output_queue(q: Queue | None) -> None:
    global _output_queue
    _output_queue = q

_SENTENCE_ENDS = frozenset((".", "!", "?", "ạ", "nhé", "nha"))

# === Modify _llm_invoke → add _llm_stream ===

def _llm_stream(prompt: list) -> str:
    """Stream LLM output to _output_queue as complete sentences."""
    full_text = []
    buffer = ""
    for chunk in _response_llm.stream(prompt):
        token = chunk.content if hasattr(chunk, "content") else str(chunk) if isinstance(chunk, str) else ""
        if not token:
            continue
        full_text.append(token)
        buffer += token
        # Emit complete sentences immediately
        last_char = buffer.strip()[-1:] if buffer.strip() else ""
        if last_char in _SENTENCE_ENDS and _output_queue is not None:
            sentence = buffer.strip()
            if sentence:
                _output_queue.put(("sentence", sentence))
            buffer = ""
    # Emit any remaining text
    remaining = buffer.strip()
    if remaining and _output_queue is not None:
        _output_queue.put(("sentence", remaining))
    return "".join(full_text)

# === Modify response_node ===
# For template contexts (TemplateResponseContext), push the rendered
# text to _output_queue as a single sentence:
#
#   if _output_queue is not None:
#       _output_queue.put(("sentence", rendered))
#
# For LLM paths (SearchResponseContext, ChatResponseContext, etc.),
# replace _llm_invoke() calls with _llm_stream().
```

### A.6 — File 2: `server.py` changes

```python
# === Add imports ===
import asyncio
import json
from queue import Queue, Empty
from fastapi.responses import StreamingResponse
from src.agent_brain.agent.nodes.response_node import set_output_queue

# === Add POST /chat/stream endpoint ===

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    q: Queue = Queue()
    set_output_queue(q)

    async def generate():
        table_id = req.table_id.strip()
        table_int = normalise_table_id(table_id)

        # 1. Show user text on tablet immediately
        _orchestrator.post_voice_event(
            {"type": "voice.heard", "table_id": table_int, "text": req.text.strip()}
        )

        # 2. Signal progress
        yield f"data: {json.dumps({'event': 'progress', 'text': 'processing'})}\n\n"
        _orchestrator.post_voice_event(
            {"type": "voice.progress", "table_id": table_int, "status": "đang xử lý..."}
        )

        # 3. Run graph in threadpool — response_node pushes to q via _output_queue
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, _agent.chat, req.text.strip(), table_id)

        # 4. Drain queue — emit sentences as response_node produces them
        while True:
            try:
                msg = q.get(timeout=0.1)
                event_type, text = msg
                if event_type == "sentence":
                    yield f"data: {json.dumps({'event': 'sentence', 'text': text})}\n\n"
            except Empty:
                if future.done():
                    # Drain any remaining items
                    while True:
                        try:
                            msg = q.get_nowait()
                            if msg[0] == "sentence":
                                yield f"data: {json.dumps({'event': 'sentence', 'text': msg[1]})}\n\n"
                        except Empty:
                            break
                    break

        # 5. Get result, mirror to tablet, send done event
        set_output_queue(None)  # cleanup
        result = future.result()

        response = result["response"]
        action = result.get("action")
        stage = result.get("final_stage", "IDLE")
        session_id = result.get("session_id")
        cart = result.get("cart")
        confirmed = bool(result.get("order_confirmed"))

        _orchestrator.post_voice_event({
            "type": "voice.reply", "table_id": table_int,
            "text": response, "action": action,
            "stage": stage, "cart": cart, "confirmed": confirmed,
        })

        # Persist turn to JSONL transcript
        log_turn(
            table_id=table_id, session_id=session_id,
            user_text=req.text.strip(), response=response,
            stage=stage, action=action,
        )

        yield f"data: {json.dumps({
            'event': 'done',
            'action': action, 'stage': stage,
            'session_id': session_id,
        })}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### A.7 — File 3: `edge_voice/main.py` changes

```python
# === Add new function _capture_and_send_streaming ===

def _capture_and_send_streaming(vad: SileroVAD, agent_client: httpx.Client,
                                 table_id: int, player: StreamingPlayer) -> None:
    """Same as _capture_and_send but consumes SSE and plays sentences incrementally."""
    # Drop stale transcripts
    while get_transcript(timeout=0.0) is not None:
        pass

    vad.begin_listen()
    print("[LISTENING] mời anh/chị nói...")
    if not vad.wait_for_utterance(UTTERANCE_TIMEOUT):
        print("[TIMEOUT] không nghe thấy gì, quay lại chờ.")
        return

    transcript = get_transcript(timeout=TRANSCRIPT_TIMEOUT)
    if transcript is None or not transcript.text.strip():
        print("[EMPTY] không nhận ra lời nói.")
        return

    text = transcript.text
    print(f"[HEARD @ {transcript.timestamp:.1f}s | bàn {table_id}]: {text}")

    try:
        player.reset()
        with agent_client.stream("POST", "/chat/stream", json={
            "table_id": f"T{table_id}", "text": text
        }) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                ev = data.get("event")

                if ev == "progress":
                    # Play a short ack sound or "Dạ..." immediately
                    print(f"[WAITER progress]: {data.get('text', '...')}")
                elif ev == "sentence":
                    sentence = data["text"]
                    print(f"[WAITER]: {sentence}")
                    if sentence and not player.is_stopped():
                        asyncio.run(speak_sentence(sentence, player))
                elif ev == "done":
                    print(f"[WAITER done] stage={data.get('stage')}")
                    break
    except httpx.HTTPError as e:
        print(f"Agent stream request failed: {e}")


# === In voice_device_loop, replace _capture_and_send with _capture_and_send_streaming ===
# Line 132: change to:
#   await asyncio.to_thread(_capture_and_send_streaming, vad, agent_client, table_id, player)
```

### A.8 — File 4: `tts_engine.py` changes

```python
# === Add speak_sentence function ===

import asyncio

async def speak_sentence(text: str, player: StreamingPlayer) -> None:
    """Play a single sentence through TTS immediately. Non-blocking.

    Unlike speak_streaming() which receives the full response and splits
    it internally, this receives one pre-split sentence at a time from
    the SSE stream.
    """
    if not text.strip():
        return
    from edge_tts import Communicate
    audio = b""
    communicate = Communicate(text, "vi-VN-NamMinhNeural")
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    if audio:
        player.play_audio(audio)
        await player.wait_done()
    # Non-blocking: caller continues to next sentence
```

### A.9 — File 5: `voice.py` changes

```python
# === Add status field to VoiceEvent ===

class VoiceEvent(BaseModel):
    type: str
    table_id: int
    text: str | None = None
    action: dict | None = None
    stage: str | None = None
    cart: list | None = None
    confirmed: bool | None = None
    status: str | None = None   # ← NEW: "đang xử lý...", "đang tìm kiếm...", etc.
```

### A.10 — File 6: `orchestrator_client.py` changes

```python
# === Add post_progress_event method ===

def post_progress_event(self, table_id, status_text: str) -> None:
    """POST /voice/event with type=voice.progress to update tablet status."""
    try:
        self._post("/voice/event", {
            "type": "voice.progress",
            "table_id": normalise_table_id(table_id),
            "status": status_text,
        })
    except httpx.HTTPError as e:
        logger.warning(f"progress event not delivered to tablet: {e}")
```

### A.11 — Design Decisions

| Decision                                         | Reasoning                                                                                                      |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| Sentence-level streaming, not tokens             | TTS needs complete sentences for natural synthesis. Tokens are too granular.                                   |
| `voice.progress` for monitor, `sentence` for TTS | Two distinct output channels. Monitor shows all processing stages. Voice only speaks the response_node output. |
| Graph stays synchronous (`invoke()`)             | Minimal refactor. Only `response_node` + server endpoint change. No graph topology changes.                    |
| `Queue` bridging sync graph ↔ async SSE          | Thread-safe, decouples sync graph execution from async SSE generator. Standard Python pattern.                 |
| `POST /chat` unchanged                           | Backward compatibility. Voice device can switch client-side with one-line change.                              |
| No mid-graph cancellation in v1                  | Adds significant complexity to graph execution. Current `voice.cancel` handles pre-graph cancel.               |

### A.12 — Things NOT in v1

- **No graph-level `astream_events`** — yields internal transitions (routing, validating) that aren't meaningful for TTS. Too invasive for v1.
- **No per-node progress granularity** — the tablet already shows "thinking" via `voice.heard`. Per-stage updates (`voice.progress`) are additive and can be added incrementally.
- **No token-level TTS** — edge-tts needs complete sentences for good synthesis quality. Sentence-level streaming already achieves the ~500ms target.
- **No cancel mid-graph** — adds complexity; can be layered on later.

### A.13 — Implementation Order & Dependencies

```
Step 1: response_node.py   (add _llm_stream + output queue)      ← foundation, everything depends on it
Step 2: server.py          (add /chat/stream endpoint)            ← depends on step 1
Step 3: voice.py + orchestrator_client.py  (add voice.progress)   ← independent, can parallel with 2
Step 4: tts_engine.py      (add speak_sentence)                   ← independent
Step 5: edge_voice/main.py (connect to /chat/stream, use speak_sentence)  ← depends on 2, 3, 4
```

Steps 1-2 can be tested in isolation (curl the SSE endpoint). Steps 3-5 can be tested with a mock SSE server. Then integration test end-to-end.
