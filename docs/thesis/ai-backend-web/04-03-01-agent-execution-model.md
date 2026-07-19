## 4.3.1 Agent Execution Model

> **Status:** draft
> **Cross-refs:** §4.3.2–§4.3.7 detail each pipeline stage; §4.8 for deployment
> **Source:** `src/agent_brain/agent/graph.py` (283 lines), `state.py` (93 lines), `memory/checkpointer.py` (35 lines)
> **Figures needed:** Fig 4.3.1 (StateGraph visualization with nodes, edges, routing decisions)

---

The conversational agent is implemented as a LangGraph `StateGraph` — a directed graph where each node is a processing function, edges carry typed state between nodes, and conditional edges branch based on runtime state values. This architecture was chosen over a monolithic LLM call for three reasons:

1. **Deterministic code between LLM calls.** The graph interleaves LLM inference nodes (router, workers, response) with deterministic Python nodes (validator, state updater, state outcome). This means every LLM output is inspected by code before it becomes a system action. The LLM cannot directly modify the cart, confirm an order, or request payment — it can only propose actions that the graph's deterministic nodes validate and execute.

2. **Inspectable execution path.** Every utterance follows a traceable path through the graph: `router → worker → tools → validator → state_updater → (repeat for multi-intent) → state_outcome → response_node → END`. A debugger or LangSmith trace shows exactly which node ran, what state it received, and what state it produced. This visibility is essential for both thesis analysis (§5.3–§5.4) and production debugging.

3. **Bounded execution with circuit breakers.** The graph cannot loop indefinitely. The `MAX_RETRY_LOOPS = 3` constant guarantees that even if the LLM produces repeatedly invalid output, the validator's circuit breaker will trigger and the graph will terminate with an apology response.

---

### 4.3.1.1 Graph Structure

The `AIWaiterGraph` class in `graph.py:121` builds and compiles the StateGraph. It defines **10 nodes**, connected by **5 normal edges** and **6 conditional edges**.

**Nodes:**

| # | Node | Type | Responsibility |
|---|------|------|----------------|
| 1 | `router` | LLM + deterministic | Classifies user intent; dispatches to appropriate worker (§4.3.2) |
| 2 | `order_worker` | LLM | Decides cart CRUD actions for ORDER/ORDER_CONFIRM intents (§4.3.3) |
| 3 | `search_worker` | LLM | Rewrites queries and invokes menu retrieval for SEARCH intent (§4.3.3) |
| 4 | `payment_dispatch` | Deterministic | Emits `request_payment` tool call for PAYMENT intent (§4.3.3) |
| 5 | `chat_worker` | Deterministic | Builds curated memory context for CHAT intent and delegated turns (§4.3.3) |
| 6 | `validator` | Deterministic | Inspects LLM tool call arguments for hallucinations and ambiguity (§4.3.4) |
| 7 | `tools` | LangGraph ToolNode | Executes tool calls (7 tools: cart CRUD, search, payment) (§4.3.5) |
| 8 | `state_updater` | Deterministic | Merges tool results into AgentState; advances cart state machine (§4.3.5) |
| 9 | `state_outcome` | Deterministic | Builds typed ResponseContext; resets per-turn ephemeral fields (§4.3.6) |
| 10 | `response_node` | LLM + templates | Generates Vietnamese spoken reply from typed context (§4.3.6) |

**Normal edges** (unconditional):

| From | To | Purpose |
|------|----|---------|
| `START` | `router` | Every utterance begins with intent classification |
| `tools` | `state_updater` | Tool execution always merges results into state |
| `chat_worker` | `state_outcome` | CHAT worker is a leaf — no tools, builds ChatResponseContext directly |
| `state_outcome` | `response_node` | Typed context always verbalized into a spoken reply |
| `response_node` | `END` | Response is the final output of every turn |

**Conditional edges** (runtime routing):

| Source | Routing Function | Possible Destinations | Logic |
|--------|-----------------|-----------------------|-------|
| `router` | `_route_by_intent` | `order_worker`, `search_worker`, `payment_dispatch`, `chat_worker` | Routes to the worker matching the first unprocessed intent in `current_intents` queue |
| `order_worker` | `_route_if_tool_call` | `tools`, `chat_worker`, `response_node`, `state_updater` | If LLM produced a tool call → `tools` (executes → validator). If LLM called only `delegate()` → `chat_worker`. If no tool call (defensive) → `state_updater` |
| `search_worker` | `_route_if_tool_call` | Same as above | Same logic: tool call → execute, delegate → chat, no call → defensive |
| `payment_dispatch` | `_route_if_tool_call` | Same as above | Always produces `request_payment` tool call (deterministic), but defender covers edge cases |
| `validator` | `_route_after_validator` | `tools`, `order_worker`, `search_worker`, `payment_dispatch`, `state_outcome` | If valid → `tools` (execute the validated tool call). If invalid AND `loop_count < 3` → return to worker for correction. If `loop_count ≥ 3` → `state_outcome` (circuit breaker) |
| `state_updater` | `_route_after_updater` | `order_worker`, `search_worker`, `payment_dispatch`, `state_outcome` | If more intents remain in queue → dispatch next worker. If queue empty → `state_outcome` (finalize turn) |

---

### 4.3.1.2 Execution Flow

Every customer utterance traces the following path through the graph. The path branches at conditional edges, but the overall sequence of stages is invariant.

```
                              ┌──────────────────────────┐
                              │       START               │
                              └──────────┬───────────────┘
                                         │
                                         ▼
                              ┌──────────────────────────┐
                              │        router             │  Stage I: UNDERSTAND
                              │  (hybrid semantic + SLM)  │  §4.3.2
                              └──────┬───────┬───────┬───┘
                                     │       │       │
                            ┌────────┘  ┌────┘  ┌────┘
                            ▼           ▼       ▼
                   ┌────────────┐ ┌──────────┐ ┌──────────────┐
                   │order_worker│ │search_   │ │payment_      │  Stage II: DECIDE
                   │            │ │worker    │ │dispatch /    │  §4.3.3
                   │ chat_worker│ │          │ │chat_worker   │
                   └─────┬──────┘ └────┬─────┘ └──────┬───────┘
                         │             │               │
                         │  ┌──────────┘               │
                         │  │  delegate-only →         │
                         │  │  chat_worker             │
                         │  │                          │
                         ▼  ▼                          ▼
                   ┌──────────────────────────────────────┐
                   │             tools                     │  Stage IV: EXECUTE
                   │  (LangGraph ToolNode, 7 tools)        │  §4.3.5
                   └──────────────┬───────────────────────┘
                                  │
                                  ▼
                   ┌──────────────────────────────────────┐
                   │          validator                    │  Stage III: VALIDATE
                   │  (deterministic safety net)           │  §4.3.4
                   └──┬──────────┬──────────────┬─────────┘
                      │ pass     │ retry        │ circuit breaker
                      ▼          ▼              ▼
                   ┌──────┐ ┌──────────┐ ┌──────────────┐
                   │tools │ │back to   │ │ state_outcome│
                   │(exec)│ │worker    │ │ (apology)    │
                   └──┬───┘ └──────────┘ └──────┬───────┘
                      │                          │
                      ▼                          │
                   ┌──────────────────────────┐  │
                   │     state_updater         │  │
                   │  (merge results,          │  │
                   │   advance cart state,     │  │
                   │   pop intent queue)       │  │
                   └──────┬───────────┬───────┘  │
                          │ more      │ queue    │
                          │ intents   │ empty    │
                          ▼           ▼          │
                   ┌──────────┐ ┌──────────────┐ │
                   │ back to  │ │state_outcome │◄┘
                   │ next     │ │(build typed  │  Stage V: RESPOND
                   │ worker   │ │response ctx) │  §4.3.6
                   └──────────┘ └──────┬───────┘
                                       │
                                       ▼
                               ┌──────────────┐
                               │response_node │
                               │(verbalize)   │
                               └──────┬───────┘
                                      │
                                      ▼
                               ┌──────────────┐
                               │     END      │
                               └──────────────┘
```

**Key invariants of this flow:**

1. **Validation gates every tool call.** The LLM proposes; the validator disposes. No tool executes without passing validation first.
2. **Retry is bounded.** After 3 failed validation attempts (`MAX_RETRY_LOOPS`), the circuit breaker triggers and the system apologizes rather than looping indefinitely.
3. **State is updated after execution, not before.** The `state_updater` runs only after tools complete successfully, ensuring that failed attempts leave no residue in `AgentState`.
4. **Multi-intent turns are sequential.** If the router classifies `[ORDER, PAYMENT]`, the ORDER worker runs first, cart state updates, then PAYMENT runs on the updated state. This ensures the payment total reflects the just-added items.
5. **Every turn ends at `response_node`.** Regardless of success, retry, or circuit breaker, the graph always terminates by generating a spoken response. The customer always hears something.

---

### 4.3.1.3 AgentState — Typed Shared Memory

The `AgentState` TypedDict (`state.py:13`) is the shared memory that flows through every node. It contains **18 fields** organized into five categories by lifecycle. LangGraph's state management uses reducer functions: by default, fields overwrite on update, but `messages` uses `add_messages` (append semantics) to accumulate conversation history.

**Category 1 — Conversation History** (1 field, persists across turns):

| Field | Type | Reducer | Purpose |
|-------|------|---------|---------|
| `messages` | `Annotated[list, add_messages]` | append | Full conversation history: user messages, AI responses, and ToolMessage results. Grows monotonically within a session. |

**Category 2 — Task State** (4 fields, persist across turns):

| Field | Type | Purpose |
|-------|------|---------|
| `table_id` | `str` | Identifies the physical table (e.g., `"T1"`). Used for orchestrator API calls and voice routing. |
| `active_cart` | `Cart \| None` | The current in-progress order. `Cart` is a Pydantic model with `items: list[CartItem]`. `None` means no cart exists (distinct from empty cart). |
| `order_stage` | `OrderStage` | Cart state machine position: `IDLE`, `DRAFTING`, `AWAITING_CONFIRMATION`, or `CONFIRMED`. Drives context-dependent routing (§4.3.2) and response generation (§4.3.6). |
| `search_context` | `list[SearchResult] \| None` | Top-K results from the most recent menu search. Retained across turns so the CHAT worker can answer follow-up questions ("món đó có cay không?") without re-searching. |

**Category 3 — Routing State** (2 fields, persist within a turn):

| Field | Type | Purpose |
|-------|------|---------|
| `current_intents` | `list[Literal["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT"]]` | FIFO queue of intents to process. Router fills it; state_updater pops from it. Enables multi-intent turns. |
| `routing_meta` | `dict[str, Any] \| None` | Debug/tracing metadata from the router (which tier handled the utterance, confidence scores, routing reason). |

**Category 4 — Inter-Node Contract** (8 fields, per-turn — written by one node, read and cleared by another):

| Field | Type | Writer | Reader | Purpose |
|-------|------|--------|--------|---------|
| `is_valid` | `bool` | validator | `_route_after_validator` | Gate for tool execution |
| `feedback` | `str \| None` | validator | workers (on retry) | Corrective instruction for LLM ("Món 'Cơm Tấm' không có trong menu. Gợi ý: 'Cơm Chiên'.") |
| `loop_count` | `int` | state_updater (increment) | `_route_after_validator` | Circuit breaker counter |
| `unavailable_items` | `list[dict] \| None` | validator | state_outcome | Off-menu items with nearest-match suggestions |
| `ambiguous_items` | `list[dict] \| None` | validator | state_outcome | Generic names matching multiple menu items |
| `last_tool` | `str \| None` | validator | state_outcome | Tool name for RetryResponseContext |
| `delegate_reason` | `str \| None` | workers (via delegate tool) | chat_worker → state_outcome | Why the worker delegated to CHAT |
| `intent_queries` | `dict[str, str] \| None` | router | workers | Per-intent sub-queries for multi-intent turns |

**Category 5 — Output** (3 fields, per-turn — consumed by response_node, cleared by state_outcome):

| Field | Type | Writer | Reader | Purpose |
|-------|------|--------|--------|---------|
| `response_context` | `ResponseContext \| None` | chat_worker or state_outcome | response_node | Typed context for response generation (OrderResponseContext, SearchResponseContext, etc.) |
| `ui_action` | `str \| None` | state_updater | `chat()` → emit_action() | Tablet UI command: `"open_menu"`, `"open_payment"`, or `None` |
| `order_confirmed` | `bool` | state_updater | `chat()` | Per-turn flag: did `confirm_order` run this turn? Drives tablet cart→ordered transition. |

---

### 4.3.1.4 Conversation Memory — Session-Scoped Persistence

The graph is compiled with LangGraph's `SqliteSaver` checkpointer (`memory/checkpointer.py:10`), which persists the full `AgentState` after every node execution. The checkpoint database (`storage/db/checkpoints.db`) stores conversation state keyed by `thread_id`.

The critical design choice is that **`thread_id` equals the orchestrator's `session_id`** (`checkpointer.py:22`). A session begins when a party is seated at the kiosk (`POST /seatings` creates an `ACTIVE` session) and ends when payment is verified (`POST /payments/verify` marks it `CLOSED`). This alignment means:

- **Within a guest visit:** All turns share the same `thread_id`. The checkpointer restores the full AgentState (cart, order stage, search context, conversation history) before each new turn, enabling multi-turn memory.
- **Between guest visits:** Payment closes the session → the next seating creates a new session with a new `session_id` → `thread_id` changes → the checkpointer sees a fresh thread → all state is blank. No context bleeds from the previous guest.
- **Fallback:** If no session exists yet (e.g., a customer speaks before kiosk check-in), the thread falls back to `table-{table_id}-nosession` — a table-scoped thread that is replaced once a real session opens.

This design avoids the need for manual state cleanup between guests. The session lifecycle (§4.5.5) naturally partitions conversation memory.

---

### 4.3.1.5 The `chat()` Entry Point

The `AIWaiterGraph.chat()` method (`graph.py:213`) is the single entry point called by the FastAPI server (`server.py`) for every customer utterance. Its responsibilities:

1. **Session resolution** (lines 219–225): Queries the orchestrator for the table's active session. If the session has changed (new guest seated), the `thread_id` changes and the checkpointer returns a fresh state. Falls back to table-scoped thread if the orchestrator is unreachable.

2. **State initialization** (lines 226–232): Builds the input dict for `app.invoke()`. Sets `messages` to the new user utterance. Preserves `order_stage` from the previous turn (read from existing checkpoint). Resets per-turn fields: `loop_count=0`, `is_valid=True`, `ui_action=None`, `order_confirmed=False`.

3. **Graph invocation** (line 232): Calls `self.app.invoke(inputs, config)` — this is the synchronous LangGraph execution that runs the full pipeline. Returns the final `AgentState` after `response_node → END`.

4. **Action emission** (lines 236–239): If the agent set `ui_action` (`"open_menu"` or `"open_payment"`), calls `emit_action()` which POSTs to the orchestrator's voice bridge, mirroring the UI command to the customer's tablet.

5. **Cart serialization** (lines 242–250): Converts the Pydantic `Cart` model to a JSON-serializable list of `{name, quantity, note}` dicts so the tablet can mirror voice-ordered items into its visual cart.

6. **Response assembly** (lines 252–260): Returns a dict with the spoken response text, session ID, order stage, UI action, cart data, and confirmation flag — consumed by the FastAPI server to build the HTTP response.

---

### 4.3.1.6 Routing Functions — Decoupling Graph Topology from Business Logic

The four routing functions (`_route_by_intent`, `_route_if_tool_call`, `_route_after_validator`, `_route_after_updater`) are pure functions from `AgentState → str`. They encapsulate the graph's branching logic, keeping the StateGraph construction declarative. Each function's detailed logic is described in its respective stage section:

- `_route_by_intent` — maps the first intent in `current_intents` to a worker node (§4.3.2)
- `_route_if_tool_call` — inspects the last AI message for tool calls, delegates, or missing calls (§4.3.3)
- `_route_after_validator` — implements the retry/circuit-breaker logic (§4.3.4)
- `_route_after_updater` — manages the multi-intent FIFO queue (§4.3.5)

This separation means that adding a new worker or changing retry logic requires only modifying a routing function — the graph topology itself stays constant.
