## 4.3.3 Stage II — Decision: Action Selection via Tool-Calling LLM

> **Status:** draft
> **Cross-refs:** §4.3.1 for execution model, §4.3.2 for intent routing, §4.3.4 for validation, §4.3.5 for tools
> **Source:** `src/agent_brain/agent/nodes/order_worker_node.py` (120 lines), `search_worker_node.py` (161 lines), `payment_dispatch_node.py` (43 lines), `chat_worker_node.py` (94 lines)
> **Figures needed:** None (tool bindings table in text is sufficient; delegate flow is diagrammed in Fig 4.3.1)

---

Once the router classifies intent, the graph dispatches to the appropriate worker node. Each worker decides *what action to take* given the customer's utterance and current state. For ORDER and SEARCH intents, this requires an LLM to reason about the utterance and select the correct tool with the correct arguments. For PAYMENT, the action is deterministic — the router already decided the intent, and `request_payment` is the only payment action. For CHAT, no tool call is needed — the worker builds a curated context for the response generator.

### 4.3.3.1 Worker Taxonomy

The four workers form a symmetric design: every intent has exactly one worker node that produces either a tool call (ORDER, SEARCH, PAYMENT) or a typed response context (CHAT). This symmetry simplifies the graph topology — the router's job is "classify and dispatch to one worker," and every worker knows how to handle its domain.

| Worker | Intent(s) | Bound Tools | LLM Called? | Model | Temperature |
|--------|-----------|-------------|-------------|-------|-------------|
| `order_worker` | ORDER, ORDER_CONFIRM | `add_cart`, `remove_cart`, `clear_cart`, `confirm_order`, `delegate` | Yes | Qwen2.5 7B | 0.1 |
| `search_worker` | SEARCH | `search`, `delegate` | Yes | Qwen2.5 7B | 0.1 |
| `payment_dispatch` | PAYMENT | `request_payment` | No (deterministic) | N/A | N/A |
| `chat_worker` | CHAT | (none) | No (pure function) | N/A | N/A |

### 4.3.3.2 LLM Worker Design — Shared Patterns

The two LLM-based workers (`order_worker` and `search_worker`) share an identical architectural pattern (`graph.py:23-31`), differing only in tool bindings, system prompts, and few-shot examples:

**1. Tool choice is forced.** Both workers bind the LLM with `tool_choice="any"` — the model must produce exactly one tool call per invocation. This eliminates the failure mode where the LLM produces a text response instead of a tool call (e.g., "Dạ, em sẽ thêm món đó vào giỏ hàng" without actually calling `add_cart`). With `tool_choice="any"`, Ollama guarantees a tool call in every response.

**2. Temperature is 0.1, not 0.0.** The slightly-above-zero temperature allows minor variation in tool argument phrasing (e.g., `"it cay"` vs `"ít cay"` for "less spicy") while keeping the tool selection near-deterministic. A temperature of 0.0 would reject all variant phrasings, making the system brittle to informal Vietnamese.

**3. The menu is deliberately excluded from the prompt.** The LLM does not need to know the 217-item menu to decide *which tool to call*. When a customer says "Cho 2 Ốc Hương Xốt Trứng Muối," the LLM only needs to recognize this as an ordering action and call `add_cart` with the raw item name — the validator (§4.3.4) resolves the name against the actual menu. Excluding the menu keeps prompt context at ~200 tokens instead of ~3000, reducing latency and avoiding the LLM hallucinating menu items it "remembers" from the prompt.

**4. KV-cache optimization via prefix ordering.** System prompts and few-shot examples are static — identical across all turns for the same worker. They are placed at the *beginning* of the prompt sequence, followed by dynamic content (cart state, validation feedback, conversation history). Ollama caches attention KV pairs for the static prefix, so only the dynamic suffix requires fresh computation per turn.

**5. Defensive retry for missing tool calls.** Despite `tool_choice="any"`, both workers include a defensive retry path: if the LLM produces no tool call (which should be unreachable), a forced-retry prompt is injected ("CRITICAL: Bạn PHẢI gọi một tool call...") and the LLM is invoked again. If that also fails, the worker returns a text apology that the `state_updater` routes to the `response_node` for verbalization. This is defense-in-depth — the system should never reach this path, but if it does, the customer hears a graceful fallback rather than silence.

### 4.3.3.3 Order Worker

The `order_worker` handles cart CRUD operations and order confirmation. It is bound to five tools:

| Tool | Purpose | LLM Decision Logic |
|------|---------|-------------------|
| `add_cart` | Add items to cart with quantities and notes | Customer says "cho", "gọi", "lấy", "thêm" + item name |
| `remove_cart` | Remove a named item from cart | Customer says "bỏ", "hủy", "xóa", "đổi", "thay" + item name |
| `clear_cart` | Empty the entire cart | Customer says "xóa hết", "bỏ hết", "hủy đơn" |
| `confirm_order` | Send the composed order to kitchen | Customer confirms: "xác nhận", "chốt đơn", "ok đặt" |
| `delegate` | Pass the utterance to CHAT worker | LLM cannot map the utterance to any cart CRUD action |

**Tool call arguments.** Each tool has a Pydantic schema defining its expected arguments. For `add_cart`, the LLM must produce `items: list[{name, quantity, special_requests}]`. The LLM is responsible for extracting structured information from natural Vietnamese:
- "Cho 2 Ốc Hương" → `{name: "Ốc Hương", quantity: 2}`
- "Lấy 1 phần Lẩu Thái, ít cay" → `{name: "Lẩu Thái", quantity: 1, special_requests: "ít cay"}`
- "Thêm 1 Bia Sài Gòn và 1 Nước Suối" → two items in one `add_cart` call

**Dynamic context.** The order worker injects the current cart state and validation feedback into the prompt (`order_worker_node.py:32-57`):
- **Cart context:** Lists all items currently in `active_cart` with quantities and prices. This enables the LLM to make additive decisions (add to existing cart rather than replacing it) and avoid re-adding items already present.
- **Validator feedback:** When the validator rejected the previous turn's tool call, the `feedback` field carries corrective instructions (e.g., "Món 'Cơm Tấm' không có trong menu. Gợi ý món gần nhất: 'Cơm Chiên'"). The LLM sees this and must fix its tool call on retry.

### 4.3.3.4 Search Worker

The `search_worker` handles menu queries, restaurant information lookups, and recommendations. It is bound to two tools:

| Tool | Purpose | LLM Decision Logic |
|------|---------|-------------------|
| `search` | Execute a RAG query over menu + knowledge base | Customer asks about menu items, prices, ingredients, recommendations |
| `delegate` | Pass to CHAT (non-search queries, already-satisfied queries) | LLM cannot map utterance to a meaningful search |

**Query rewriting.** The LLM's primary job is to rewrite conversational Vietnamese queries into concrete search keywords. The customer might say "món gì ấm bụng cho ngày lạnh?" — the LLM translates this to a search query like "lẩu súp nóng" that the RAG pipeline can retrieve against. The rewritten query is placed in the `search` tool call's arguments.

**"ĐÃ BIẾT" context.** The search worker injects a list of already-known items (`search_worker_node.py:34-69`), drawn from both the current `search_context` (results from prior SEARCH turns) and `active_cart` (ordered items). This prevents the LLM from re-searching topics the customer has already discussed. If the customer asks "món đó có cay không?" and the item was returned in a prior search, the "ĐÃ BIẾT" list includes it — the LLM should `delegate` to CHAT rather than re-search.

**Non-food delegation trigger.** The search worker's system prompt (`search_agent.md`) includes explicit instructions for what is *not* a menu search: restaurant hours, parking availability, WiFi password, music requests, and complaints. The LLM must recognize these as outside its domain and call `delegate()` with a reason like "restaurant info query, not menu search."

### 4.3.3.5 Payment Dispatch — Deterministic Action

The `payment_dispatch` node (`payment_dispatch_node.py:25`) is the simplest worker: it always emits a `request_payment` tool call with the table's `table_id`. No LLM is called, no keyword matching is performed.

**Why deterministic?** The router already classified the intent as PAYMENT. There is only one payment action the agent can initiate: `request_payment`. Additional payment logic (computing the session total, generating the VietQR URL, verifying payment) is handled by the orchestrator backend, not the agent. The agent's responsibility is simply to request the bill.

The `verify_payment` tool exists in the tool set but is called by the backend's mock verification flow, not by the agent on a customer turn. The agent does not verify payments — the backend does.

### 4.3.3.6 Chat Worker — Pure Function

The `chat_worker` (`chat_worker_node.py:56`) is a pure function: no LLM call, no tool call, no side effects. It reads the current `AgentState` and builds a `ChatResponseContext` — a typed data structure containing everything the response generator needs to produce a conversational reply:

- **User message:** The raw customer utterance.
- **Active cart:** Current cart contents and total, so the response can reference what's been ordered.
- **Order stage:** Current cart state machine position, so the response is stage-appropriate.
- **Conversation history:** The full message list, for memory-grounded responses.
- **Curated memory:** Up to 5 dishes from the most recent `search_context`, converted to `CuratedDish` objects with structured metadata (name, price, tags, taste profile, category). This enables the CHAT response to answer follow-up questions ("món đó có cay không?") without re-searching.
- **Delegate reason:** If the worker was reached via delegation, the reason explains *why* the domain worker passed control to CHAT (e.g., "restaurant info query, not menu search").

The `chat_worker` is a leaf node in the graph — it connects directly to `state_outcome` via a normal edge. No validation occurs, since there is no tool call to validate. The `state_outcome` sees that `response_context` is already set (by `chat_worker`) and simply finalizes the per-turn state reset before passing to `response_node`.

### 4.3.3.7 Robustness Mechanisms

Three mechanisms prevent LLM errors from corrupting system state. They apply to the ORDER and SEARCH workers, which are the only workers that call an LLM.

#### Delegate Escape Hatch

Both ORDER and SEARCH workers bind `delegate` alongside their domain tools, with `tool_choice="any"`. This forces the LLM to always produce a tool call — but some utterances genuinely fall outside the worker's domain. For example, if the SEARCH worker receives "mấy giờ đóng cửa?" (what time do you close?), the correct action is not `search()` — there is no menu item matching this query. Forcing a `search()` call would return irrelevant results or an empty list.

The `delegate(reason)` tool provides a non-destructive escape hatch. When the LLM cannot map the utterance to a meaningful domain action, it calls `delegate()` instead. The routing function `_route_if_tool_call` (`graph.py:61-100`) detects delegate-only tool calls and routes the utterance to `chat_worker`, which handles it conversationally.

**Design principle:** The LLM is never forced to produce a wrong action. When uncertain about its domain, it admits it rather than guessing. This prevents a class of errors where the LLM calls `search()` on a non-menu query (returning irrelevant dishes that confuse the customer) or calls `add_cart()` on a recommendation request (adding random items).

#### Retry with Corrective Feedback

When the validator (§4.3.4) rejects a tool call, it returns `is_valid=False` with a `feedback` string. The routing function `_route_after_validator` returns the utterance to the same worker, which injects `feedback` into its dynamic context block (`order_worker_node.py:49-55`, `search_worker_node.py:63-67`):

```
### SYSTEM FEEDBACK (MANDATORY FIX):
Món 'Cơm Tấm' không có trong menu. Gợi ý món gần nhất: 'Cơm Chiên'.
Fix the tool call arguments and retry immediately.
```

The LLM sees this feedback on retry and must correct its tool call. The feedback is specific — it names the exact problem (off-menu item) and provides a suggestion (nearest menu match). This enables the LLM to fix its output without re-reasoning from scratch.

#### Circuit Breaker

The `loop_count` field tracks retry iterations. After each failed validation, `loop_count` is incremented (`deterministic_validator_node.py:292`). At 3 failed attempts (`MAX_RETRY_LOOPS = 3`), the circuit breaker triggers: the validator returns with `loop_count ≥ 3`, the routing function routes to `state_outcome` instead of back to the worker, and a `RetryResponseContext` with an apology is built.

This guarantees bounded execution regardless of LLM behavior. Even if the LLM repeatedly produces invalid tool calls (due to hallucination, prompt confusion, or model error), the graph terminates after at most 3 retries with a graceful apology rather than looping indefinitely.

### 4.3.3.8 Worker Routing

The routing function `_route_if_tool_call` (`graph.py:61-100`) handles three post-worker paths:

1. **Tool calls present (non-delegate):** Route to `validator` for safety inspection. If the LLM produced both `add_cart` and `delegate` in one message, the delegate call is stripped and only the domain tool call proceeds.

2. **Delegate only:** Route to `chat_worker`. The delegate reason is stored in `agent_state["delegate_reason"]` and passed through to the CHAT response context.

3. **No tool calls (defensive):** Route to `chat_worker` for ORDER/ORDER_CONFIRM intents (misrouted questions), or to `state_updater` for other intents (advance to next intent in queue). This path should be unreachable with `tool_choice="any"`, but is kept as defense-in-depth.
