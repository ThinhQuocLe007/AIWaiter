# Conversation Planner — Per-Intent Sub-Query Extraction

> Proposed: 2026-07-15
> Replaces the "search worker retry" quick-fix (Option C) with a deeper solution that also
> implements Problem 2 (Conversation Planner) from `inprogress.md`.

---

## Problem Recap — Two bugs, one root cause

| Symptom | Root cause |
|---|---|
| Search worker freezes on multi-intent turns (no tool call → END, kills remaining intents) | Worker sees full mixed-intent utterance; ordering language confuses a SEARCH worker that only has `search` + `delegate` |
| No conditional execution ("Nếu không cay thì lấy") | `current_intents: ["SEARCH", "ORDER"]` is just a blind sequence — ORDER always runs regardless of SEARCH result |

**One fix solves both**: Instead of `list[str]`, the router emits `list[{intent, query}]` — each worker only sees the sub-query relevant to its intent.

---

## Design: Router-Extracted Sub-Queries

### Core idea

The SLM router already classifies intents AND produces reasoning (e.g., "Khách hỏi về độ cay của Gỏi Xoài Ốc Giác rồi đặt thêm"). We extend the output format so it also extracts per-intent sub-queries:

```
Input:  "Gỏi Xoài Ốc Giác có ngon không? Anh tính gọi thêm 1 phần mà sợ cay quá"

Current: {"intents": ["SEARCH", "ORDER"], "reasoning": "..."}

Proposed: {
  "steps": [
    {"intent": "SEARCH", "query": "Gỏi Xoài Ốc Giác có ngon không, có cay không?"},
    {"intent": "ORDER",  "query": "gọi thêm 1 phần Gỏi Xoài Ốc Giác"}
  ],
  "reasoning": "Khách hỏi độ cay Gỏi Xoài Ốc Giác trước, rồi đặt thêm 1 phần."
}
```

### Why this works

1. **Search worker sees only `"Gỏi Xoài Ốc Giác có ngon không, có cay không?"`** — no "gọi thêm 1 phần" to cause paralysis. Clean search signal.
2. **Order worker sees only `"gọi thêm 1 phần Gỏi Xoài Ốc Giác"`** — clean order signal, with dish name resolved by the router.
3. **Conversation history still available** — workers still read `last_n_turns()` for context ("nó", "cái đó"), but the current turn's user text is replaced with the sub-query.

---

## Architecture: 3 Phases

```
Phase 1: Schema + Router          Phase 2: Graph + Update State        Phase 3: Workers
              ──                          ──                               ──
IntentStep (new dataclass)        _route_by_intent                      Workers read
IntentPrediction.steps            _route_after_updater                  state["current_step"].query
hybrid_router_node                update_state_node                     instead of
slm_router_node                   pop steps[1:]                         last_user_text()
router_agent.md prompt            _route_if_tool_call                   as primary signal
router.json few-shots
```

---

## Phase 1 — Schema + Router

### 1.1 New `IntentStep` dataclass

```python
# New file: src/agent_brain/schemas/intent_step.py

from dataclasses import dataclass
from typing import Literal

IntentType = Literal["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT"]

@dataclass
class IntentStep:
    intent: IntentType
    query: str
    # FUTURE (Phase 4 — Conditional Execution):
    # condition: Literal["always", "search_success", "search_empty"] = "always"
```

| Field | Purpose |
|---|---|
| `intent` | Worker routing key (replaces raw string in current `current_intents`) |
| `query` | The sub-utterance this worker should process |

### 1.2 Update `IntentPrediction`

```python
# src/agent_brain/schemas/routing.py — OLD:
class IntentPrediction(BaseModel):
    intents: List[IntentType]
    reasoning: str

# NEW:
class IntentPrediction(BaseModel):
    steps: List[IntentStep]       # <-- changed: intents -> steps
    reasoning: str
```

### 1.3 Update `AgentState`

```python
# src/agent_brain/agent/state.py

from src.agent_brain.schemas.intent_step import IntentStep

class AgentState(TypedDict):
    # ... existing fields ...

    # OLD:
    # current_intents: list[Literal["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT"]]

    # NEW:
    current_intents: list[IntentStep]
```

No new `current_step` needed — workers can read `state["current_intents"][0]` directly.

### 1.4 Update `router_agent.md` prompt

Add to the output section:

```
## Output Format

{
  "steps": [
    {"intent": "SEARCH", "query": "sub-query for search worker"},
    {"intent": "ORDER",  "query": "sub-query for order worker"}
  ],
  "reasoning": "Brief Vietnamese reasoning."
}

Rules for query extraction:
- Single-intent: steps has 1 entry, query = full original utterance verbatim.
- Multi-intent: extract the relevant clause for each intent. Resolve pronouns
  ("nó", "món đó", "cái này") into concrete dish names. The ORDER step MUST
  include the dish name even if the customer implied it ("gọi thêm 1 phần"
  → "gọi thêm 1 phần [dish name]").
- Every step's query must be a valid, complete Vietnamese sentence. Do not
  output fragments or placeholder text.
```

### 1.5 Update `router.json` few-shots

All 13 examples need the `steps` format. Key new multi-intent examples:

```json
{
  "query": "Lẩu Thái có cay không? Nếu không cay thì lấy cho 2 phần nhé",
  "steps": [
    {"intent": "SEARCH", "query": "Lẩu Thái có cay không?"},
    {"intent": "ORDER", "query": "lấy 2 phần Lẩu Thái"}
  ],
  "reasoning": "Khách hỏi độ cay trước, đặt món sau nếu hài lòng."
},
{
  "query": "Mình muốn gọi 2 Tôm Càng Xanh Nướng Phô Mai, nhưng trước đó cho hỏi phần này ăn mấy người?",
  "steps": [
    {"intent": "SEARCH", "query": "Tôm Càng Xanh Nướng Phô Mai ăn mấy người?"},
    {"intent": "ORDER", "query": "gọi 2 Tôm Càng Xanh Nướng Phô Mai"}
  ],
  "reasoning": "Khách muốn đặt nhưng hỏi khẩu phần trước để kiểm tra."
},
{
  "query": "Cho 1 Lẩu Thái và tính tiền luôn",
  "steps": [
    {"intent": "ORDER", "query": "cho 1 Lẩu Thái"},
    {"intent": "PAYMENT", "query": "tính tiền"}
  ],
  "reasoning": "Hai hành động: đặt món rồi thanh toán."
}
```

### 1.6 Update `slm_router_node.py`

- `_router_chain` uses `with_structured_output(IntentPrediction)` — Pydantic handles the new format.
- Lines 120-131: `result.intents` becomes `result.steps`.
- Return `{"current_intents": result.steps}`.

### 1.7 Update `hybrid_router_node.py`

Semantic router can only produce single-intent (no sub-query). Wrap as a step:

```python
# hybrid_router_node.py — fast-track path (single intent):
from src.agent_brain.schemas.intent_step import IntentStep
from src.agent_brain.utils.state_helpers import last_user_text

if sem_intent:
    current_intents = [IntentStep(intent=sem_intent, query=last_user_text(state))]
    # single-intent: full query is fine, no splitting needed

# SLM fallback path:
current_intents = slm_result.get("current_intents", [])
# already list[IntentStep] from slm_router_node
```

Multi-intent turns always go through SLM (semantic router can only output 1 intent). This is fine — semantic already falls through 51% of the time.

---

## Phase 2 — Graph Routing

### 2.1 `_get_next_worker` and `_route_by_intent`

```python
# graph.py — current:
def _get_next_worker(state: AgentState) -> str:
    intents = state.get("current_intents") or []
    if not intents:
        return DEFAULT_WORKER
    return INTENT_TO_WORKER.get(intents[0], DEFAULT_WORKER)

# New — accesses .intent instead of raw string:
def _get_next_worker(state: AgentState) -> str:
    steps = state.get("current_intents") or []
    if not steps:
        return DEFAULT_WORKER
    return INTENT_TO_WORKER.get(steps[0].intent, DEFAULT_WORKER)
```

Same pattern in `_route_if_tool_call` line 90:
```python
# OLD:
if intents and intents[0] in ("ORDER", "ORDER_CONFIRM"):
# NEW:
if intents and intents[0].intent in ("ORDER", "ORDER_CONFIRM"):
```

### 2.2 `update_state_node` — no change needed

```python
# update_state_node.py:135-137 — current:
intents = state.get("current_intents") or []
if intents:
    result["current_intents"] = intents[1:]  # list[IntentStep] — slicing works identically
```

### 2.3 `_route_if_tool_call` — fix the no-tool-call fallback

**Open question: where to route on no tool call?**

Current behavior: `response_node → END` kills remaining intents. Proposed: route to `state_updater` which pops the failed step and routes to next worker. Change:

```python
# _route_if_tool_call — fallback path:
# OLD (line 96-100):
return "response_node"

# NEW:
return "state_updater"
# state_updater pops the failed intent (steps[1:]),
# then _route_after_updater routes to next worker or state_outcome
```

And update the conditional edge map (line 183):
```python
workflow.add_conditional_edges(
    worker,
    _route_if_tool_call,
    {"tools": "validator", "chat_worker": "chat_worker",
     "response_node": "response_node", "state_updater": "state_updater"},  # <-- added
)
```

**Discussion point**: `state_updater` currently collects ToolMessages from the message list. If there are no tool calls, there are no ToolMessages — the loop at lines 104-110 finds nothing, and only the intent pop at lines 135-137 runs. This is correct behavior for the fallback case.

---

## Phase 3 — Workers

### 3.1 Each worker reads the current step's query

Pattern applied to `search_worker_node`, `order_worker_node`, and `chat_worker_node`:

```python
def search_worker_node(state: AgentState) -> dict[str, Any]:
    table_id = state.get("table_id", "T1")

    # Get the current step's query — fall back to last_user_text for safety
    steps = state.get("current_intents") or []
    worker_query = steps[0].query if steps else _fallback_last_user_text(state)

    static_system_message = build_system_prompt("search_agent.md")
    static_few_shot_messages = build_few_shot_examples("search_worker.json")
    dynamic_context = _build_search_dynamic_context(state)
    dynamic_suffix_message = build_dynamic_suffix(
        table_id=table_id, dynamic_context=dynamic_context
    )

    # Build history with sub-query replacing the current turn's user text
    history = last_n_turns(state["messages"], n=2)
    for i in range(len(history) - 1, -1, -1):
        if isinstance(history[i], HumanMessage):
            history[i] = HumanMessage(content=worker_query)
            break

    input_messages = (
        [static_system_message]
        + static_few_shot_messages
        + [dynamic_suffix_message]
        + history
    )
    # ... rest unchanged
```

Key points:
- Only the **last** HumanMessage in history is replaced (the current turn). Prior turns are untouched.
- Fallback to `last_user_text()` if `current_intents` is empty (defensive — should never happen).
- This adds ~6 lines per worker, minimal diff.

### 3.2 `payment_dispatch_node`

No change — it's deterministic, doesn't read the user query.

### 3.3 `chat_worker_node`

```python
# line 87: change user_message source
# OLD:
user_message=last_user_text(state),

# NEW:
user_message=steps[0].query if (steps := state.get("current_intents") or []) else last_user_text(state),
```

---

## Phase 4 — Conditional Execution (FUTURE)

Once the step pipeline is stable (Phases 1-3), add conditions:

### 4.1 Add `condition` field to `IntentStep`

```python
from typing import Literal

@dataclass
class IntentStep:
    intent: IntentType
    query: str
    condition: Literal["always", "search_success", "search_empty"] = "always"
```

### 4.2 Router prompt update

```
When the customer uses conditional language ("nếu", "nếu không", "nếu còn"),
the ORDER step's condition should be "search_success" (order only if search
finds the item) or "search_empty" (order only if search finds nothing).
```

### 4.3 `_route_after_updater` — skip logic

```python
def _route_after_updater(state: AgentState) -> str:
    steps = state.get("current_intents") or []
    if not steps:
        return "state_outcome"

    next_step = steps[0]

    # Conditional skip: ORDER depends on prior SEARCH result
    if getattr(next_step, "condition", "always") == "search_success":
        search_ctx = state.get("search_context")
        if not search_ctx:
            logger.info("Skipping %s — conditional SEARCH returned empty", next_step.intent)
            steps.pop(0)  # consume the skipped step
            return "state_outcome"

    if getattr(next_step, "condition", "always") == "search_empty":
        search_ctx = state.get("search_context")
        if search_ctx:
            steps.pop(0)
            return "state_outcome"

    return _get_next_worker(state)
```

---

## Files Changed — Summary

| # | File | Change | Risk |
|---|---|---|---|
| 1 | `schemas/intent_step.py` | **NEW** — `IntentStep` dataclass | Low — isolated new file |
| 2 | `schemas/routing.py` | `IntentPrediction`: `intents` → `steps` | Medium — changes router output contract |
| 3 | `agent/state.py` | `current_intents` type: `list[str]` → `list[IntentStep]` | Medium — touches TypedDict definition |
| 4 | `agent/nodes/hybrid_router_node.py` | Semantic path wraps result as `IntentStep` | Low — ~4 lines changed |
| 5 | `agent/nodes/slm_router_node.py` | `result.intents` → `result.steps` | Low — ~2 lines changed |
| 6 | `resources/system_prompts/router_agent.md` | Add sub-query extraction rules | Medium — LLM prompt, needs eval |
| 7 | `resources/few_shots/router.json` | All examples rewritten with `steps` format | Medium — correctness depends on LLM learning from examples |
| 8 | `agent/graph.py` | 3 functions: `_get_next_worker`, `_route_if_tool_call`, edge map | Medium — routing logic |
| 9 | `agent/nodes/search_worker_node.py` | Read `steps[0].query`, replace last HumanMessage | Low — ~6 lines added |
| 10 | `agent/nodes/order_worker_node.py` | Same pattern as search | Low — ~6 lines added |
| 11 | `agent/nodes/chat_worker_node.py` | Read `steps[0].query` for `user_message` | Low — ~2 lines |
| 12 | `agent/nodes/update_state_node.py` | No change needed (slicing works) | None |
| 13 | `agent/nodes/payment_dispatch_node.py` | No change needed | None |

---

## Discussion Items

### Q1: Where to route on no-tool-call?

Current: `_route_if_tool_call` → `response_node` → `END` (terminal, kills remaining intents).

Proposed: route to `state_updater` which pops the failed step, then continues to next worker via `_route_after_updater`.

**Alternative**: Directly route to `state_outcome` which already has `_route_after_updater` semantics. But `state_outcome` builds the ResponseContext — doing that mid-sequence is wrong. `state_updater` is the more natural choice.

**Question**: Is `state_updater` the right node? It's designed for "tool executed → update state". The no-tool-call path has no tool results, so `state_updater` just pops the intent and does nothing else. Bit of a semantic mismatch but functionally correct.

### Q2: What about single-intent turns via semantic router?

Semantic router fast-tracks 49% of turns (single-intent only). For these, we wrap the full query in an `IntentStep` — no splitting. The worker sees the same text it currently sees. **No regression risk.**

### Q3: Fallback safety for workers?

If somehow `current_intents` is empty when a worker runs, we fall back to `last_user_text(state)`. This preserves current behavior. Should never trigger in normal operation but is cheap defense-in-depth.

### Q4: Do we need `current_step` on state?

No. Workers already read `state["current_intents"][0]` for their step. Adding a separate `current_step` field is redundant — it would always equal `current_intents[0]` and creates a sync problem (both need to be updated together).

### Q5: What happens to `_route_if_tool_call`'s ORDER special case?

Current line 89-94: if ORDER worker produces no tool call, route to `chat_worker` (question misrouted to ORDER). With sub-queries, the ORDER worker should rarely freeze since it only sees ordering language. But the special case still works — ORDER intent + no tool call → `chat_worker`.

### Q6: Should we also keep the search_worker retry (Option C)?

With sub-queries, the root cause is gone — the worker sees only search-relevant text. The retry becomes unnecessary. But keeping it as defense-in-depth is cheap. Decision: **skip retry for now**, add it later if eval shows it's still needed.

---

## Implementation Order

```
Step 1: intent_step.py       (new dataclass — foundation, zero dependencies)
Step 2: routing.py           (update IntentPrediction schema)
Step 3: state.py             (update AgentState type)
Step 4: router_agent.md      (prompt rewrite)
Step 5: router.json          (few-shots rewrite)
Step 6: slm_router_node.py   (plumb new schema)
Step 7: hybrid_router_node.py (wrap semantic result)
Step 8: graph.py             (routing functions + edge map)
Step 9: search_worker_node.py (sub-query integration)
Step 10: order_worker_node.py (sub-query integration)
Step 11: chat_worker_node.py  (sub-query integration)
Step 12: Run router evals     (validate no regression)
Step 13: Run long conversation test (validate multi-intent fix)
```

Steps 1-7 can be done together (no graph dependencies). Steps 8-11 are integration. Step 12-13 are validation.
