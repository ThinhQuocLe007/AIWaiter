## 4.3.5 Stage IV — Execution: Tools & State Management

> **Status:** draft
> **Cross-refs:** §4.3.3 for worker tool selection, §4.3.4 for validation, §4.3.6 for response generation
> **Source:** `src/agent_brain/agent/tools/` (9 files), `src/agent_brain/agent/nodes/update_state_node.py` (139 lines), `src/agent_brain/agent/nodes/state_outcome_node.py` (211 lines)
> **Figures needed:** Fig 4.3.5 (cart state machine diagram)

---

Once the validator approves a tool call, execution proceeds in two phases: the `ToolNode` executes the tool (Phase 1), and the `state_updater` merges the result into `AgentState` (Phase 2). This two-phase design — execute then update — ensures that tool execution failures (network errors, database constraints) leave no residue in the agent's state. Only successful tool calls modify `AgentState`.

### 4.3.5.1 Tool Architecture

The system defines seven LangChain tools, each annotated with `@tool` and a Pydantic schema for its arguments. They fall into three architectural categories:

#### In-Memory Cart Tools

These tools operate entirely on `AgentState.active_cart` — they involve no network I/O, no database writes, and no external service calls. The cart exists only in the agent's state graph, managed by the `state_updater`.

| Tool | Arguments | Operation | Return |
|------|-----------|-----------|--------|
| `add_cart` | `items: list[{name, quantity, special_requests}]` | Adds items to cart; same-name items merge by incrementing quantity | `Cart {items, total_price}` |
| `remove_cart` | `name: str` | Removes one item by exact name from cart | `Cart {items, total_price}` with `removed: str` |
| `clear_cart` | (none) | Clears all items; resets cart to empty | `Cart {}` |

The `add_cart` tool merges quantities: if the customer says "thêm 1 Ốc Hương" and the cart already has 2, the result is 3 — the tool does not create a duplicate line item. Prices are recomputed from the `MenuManager` singleton, which loads `menu.json` once at startup and provides `get_price(name) → int` lookups.

**Cart is a Pydantic model** (`src/agent_brain/schemas/order.py`), not a plain dict. Each `CartItem` has fields `name`, `quantity`, `unit_price`, `special_requests`, and `is_valid`. `Cart` computes `total_price` as the sum of `unit_price × quantity` across all items. This typed design ensures that every node in the graph reads and writes the same cart structure — no dict-key typos or missing fields.

#### Orchestrator API Tools

These tools make HTTP POST calls to the orchestrator backend, which owns the business ledger (SQLite `orchestrator.db`). They bridge the stateless agent to the persistent restaurant state.

| Tool | HTTP Call | Side Effect |
|------|-----------|-------------|
| `confirm_order` | `POST /orders` with serialized cart | Creates order in DB; emits `order.created` WebSocket event; kitchen panel displays order |
| `request_payment` | `POST /payments` with `table_id` | Computes session total (sum of all confirmed order totals); returns VietQR URL + amount |
| `verify_payment` | `POST /payments/verify` | Marks session CLOSED; marks table DA_THANH_TOAN; cancels pending robot tasks |

**Separation of concerns.** The `confirm_order` tool serializes the cart and delegates to the orchestrator, which performs: database insertion, session linking, price verification (double-checks against menu prices), and WebSocket fan-out. The agent does not write to the database directly — it only proposes that an action should happen. This separation means the orchestrator can enforce business rules (e.g., a table without an active session cannot place an order) that the agent might not know about.

#### Search Tool (RAG Pipeline)

The `search` tool wraps the hybrid retrieval pipeline — it is the only tool with no orchestrator dependency. When the search worker calls `search(query="món nước ấm")`:

1. The query is tokenized for Vietnamese via `underthesea.word_tokenize()`.
2. Two parallel retrievals execute: BM25 (sparse lexical) and FAISS (dense semantic with SentenceTransformer embeddings at 768-dim).
3. Results are fused via Reciprocal Rank Fusion: `score(d) = Σ 1/(60 + rank_d)` where `k=60` is the smoothing constant.
4. A dual-lane gatekeeper filters results: the top FAISS result must have cosine ≥ 0.35, or the query keywords must appear in the top BM25 document text. If both fail, the result set is empty.
5. Metadata post-filters (price range, dietary type, category) are applied if specified in the query.

The search tool returns a list of `SearchResult` objects, each wrapping a `Document` with metadata (name, price, category, tags, taste profile). This structured output enables the `search_context` field to persist results across turns, and the `chat_worker` to convert them into `CuratedDish` objects for conversational memory.

### 4.3.5.2 ToolNode Execution

The `ToolNode` (`graph.py:155-158`) is LangGraph's built-in node that executes tool calls. It iterates over all `tool_calls` in the last AI message, calls each tool function with the arguments provided by the LLM, and appends a `ToolMessage` to the message history with the return value stored in the `artifact` attribute.

The `ToolNode` is configured with `messages_key="messages"`, meaning it reads tool calls from and writes results to the `messages` field in `AgentState`. This is the standard LangGraph pattern for tool execution.

### 4.3.5.3 State Update — Merging Results

The `state_updater` node (`update_state_node.py:90`) runs **after** the `ToolNode` and processes all `ToolMessage` artifacts from the current turn. It dispatches to per-tool handler functions:

| Tool | Handler | State Update |
|------|---------|-------------|
| `add_cart` | `_handle_add_cart_result` | Merges items into `active_cart` (additive); sets `order_stage = AWAITING_CONFIRMATION` |
| `remove_cart` | `_handle_remove_cart_result` | Filters item by name from `active_cart`; recalculates total; sets stage |
| `clear_cart` | `_handle_clear_cart_result` | Replaces `active_cart` with empty `Cart()`; sets `order_stage = IDLE` |
| `confirm_order` | `_handle_confirm_order_result` | Sets `order_stage = CONFIRMED`; sets `order_confirmed = True` |
| `search` | `_handle_search_result` | Sets `search_context = tool_result.results` |
| `request_payment` | (no handler) | The UI action `open_payment` is set, but cart state is unchanged |
| `verify_payment` | (no handler) | State is finalized by the orchestrator; agent resets on next session |

**Multi-ToolMessage processing.** The `state_updater` processes *all* `ToolMessage` objects from the current turn, not just the last one. When the worker emits multiple tool calls (e.g., `add_cart` for two items in one message), the `ToolNode` produces one `ToolMessage` per call. Each is handled independently, and their state updates are merged.

**Price recalculation.** After any cart mutation, `_recalc_cart` (`update_state_node.py:15-25`) recomputes `total_price` and per-item `unit_price` from the `MenuManager` singleton. This ensures prices are always sourced from the authoritative menu data, not from the LLM (which might hallucinate prices).

**Intent queue management.** After processing all tool messages, the `state_updater` pops the first intent from `current_intents` (`update_state_node.py:135-137`). If more intents remain in the queue, the routing function `_route_after_updater` dispatches the next worker. If the queue is empty, execution proceeds to `state_outcome`.

### 4.3.5.4 Cart State Machine

The order workflow is governed by a finite state machine with four states (`OrderStage` enum), enforced by the `state_updater`:

```
IDLE ──(add_cart)──→ DRAFTING ──(agent echoes cart)──→ AWAITING_CONFIRMATION
  ↑                        ↑                                    │
  │                        │ add_cart/remove_cart               │ confirm_order
  │                        └────────────────────────────────────┘
  │                                                             │
  └────────────────────(payment verified)───────────────────────┘
                                                              CONFIRMED
```

| State | Meaning | Allowed Actions |
|-------|---------|-----------------|
| **IDLE** | No cart exists; no order in progress | `add_cart` → DRAFTING; any search/chat |
| **DRAFTING** | Cart is being built | `add_cart`/`remove_cart`/`clear_cart` → DRAFTING or AWAITING_CONFIRMATION |
| **AWAITING_CONFIRMATION** | Cart is complete; waiting for customer confirmation | `add_cart`/`remove_cart` → DRAFTING (re-echo cart); `confirm_order` → CONFIRMED |
| **CONFIRMED** | Order sent to kitchen | Payment flow; new `add_cart` starts a fresh DRAFTING cycle |

**Stage enforcement rule:** Any `add_cart` or `remove_cart` at `AWAITING_CONFIRMATION` loops back to `DRAFTING`. The `state_updater` sets the stage to `AWAITING_CONFIRMATION` after cart mutation, and the response node echoes the cart. This prevents the LLM from silently adding items and confirming without the customer seeing the updated cart. The customer always sees what they're about to order before `confirm_order` is called.

### 4.3.5.5 Multi-Intent Iteration

The `current_intents` field is a FIFO queue processed sequentially. Each iteration:

1. The routing function `_get_next_worker` reads `current_intents[0]` and dispatches to the corresponding worker.
2. The worker produces a tool call → validator inspects → `ToolNode` executes → `state_updater` merges results.
3. The `state_updater` pops `current_intents[0]` via `result["current_intents"] = intents[1:]`.
4. `_route_after_updater` checks: if `intents[1:]` is non-empty, route to the next worker. If empty, route to `state_outcome`.

**Example:** "Cho 2 Ốc Hương rồi tính tiền luôn"
1. Router classifies [ORDER, PAYMENT] → `current_intents = ["ORDER", "PAYMENT"]`
2. ORDER worker → `add_cart(["Ốc Hương", quantity=2])` → validator OK → ToolNode executes → state_updater merges cart, sets `order_stage = AWAITING_CONFIRMATION` → pops ORDER → `current_intents = ["PAYMENT"]`
3. PAYMENT worker (payment_dispatch) → `request_payment(table_id)` → validator OK → ToolNode calls orchestrator → state_updater sets `ui_action = "open_payment"` → pops PAYMENT → `current_intents = []`
4. Queue empty → state_outcome builds a combined response context → response_node generates: "Dạ, em đã thêm 2 Ốc Hương Xốt Trứng Muối và tổng hóa đơn là 340k. Anh/chị quét mã QR để thanh toán ạ."

**Sequential execution is essential for correctness.** The PAYMENT intent runs *after* ORDER has updated the cart, so the payment total reflects the just-added items. If they ran in parallel, the payment total would miss the new items.

### 4.3.5.6 State Outcome — Finalizing the Turn

The `state_outcome` node (`state_outcome_node.py:191`) is the penultimate node before response generation. It runs after all intents have been processed and builds a typed `ResponseContext` from the tool execution results.

**Dispatch logic:**

1. If `response_context` is already set (by `chat_worker` for the CHAT path), skip building — just finalize.
2. If `is_valid=False` and `feedback` is set → build `RetryResponseContext` (circuit breaker triggered).
3. If the last message is a `ToolMessage` → dispatch to per-tool context builders (e.g., `_build_add_cart`, `_build_search`).
4. Otherwise (defensive fallback) → build a generic `ChatResponseContext`.

**Per-tool context builders** map tool results to typed context objects:

| Tool Result | ResponseContext Subtype | Key Fields |
|-------------|------------------------|------------|
| `add_cart` success | `OrderResponseContext` | `tool="add_cart"`, `cart=[...]`, `total_vnd`, `stage`, `off_menu`, `ambiguous` |
| `remove_cart` success | `OrderResponseContext` | `tool="remove_cart"`, `cart=[...]`, `total_vnd` |
| `confirm_order` success | `OrderResponseContext` | `tool="confirm_order"`, `order_id`, `cart=[...]` |
| `search` success | `SearchResponseContext` | `query`, `results=[SearchResult...]` |
| `request_payment` success | `PaymentResponseContext` | `amount_vnd`, `qr_url`, `table_id` |
| `verify_payment` success | `PaymentResponseContext` | `tool="verify_payment"`, `status="success"` |
| Any tool error | Respective context type | `status="error"`, `error_message` |

**Per-turn cleanup.** The `state_outcome` resets ephemeral fields that must not persist to the next turn (`state_outcome_node.py:175-188`): `unavailable_items`, `ambiguous_items`, `feedback`, `last_tool`, `delegate_reason`, and `intent_queries`. This is the only place these fields are cleared — all nodes safely assume they exist for the duration of one turn.

**UI action synthesis.** The `state_updater` sets `ui_action` based on the executed tool via `ui_action_for_tool()` (`src/agent_brain/agent/actions.py`):
- `confirm_order` → `None` (the cart→ordered transition is handled by `order_confirmed=True`)
- `request_payment` → `"open_payment"` (tablet navigates to payment screen)
- `search` → `"open_menu"` (tablet scrolls to relevant category)
- Cart tools → `None` (cart sync is handled by the `cart` field in the chat response)

These UI actions are fan-out via the orchestrator's voice bridge to the customer's tablet, where the frontend interprets them as navigation commands.
