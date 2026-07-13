# Memory Design — Per-Agent Context Report

A code-verified report on what context each agent (worker) receives,
how that context is assembled, and how it flows through the pipeline.

Referenced source code (v1.7, July 2026):

| File | Role |
|------|------|
| `agent/nodes/chat_worker_node.py` | CHAT context builder |
| `agent/nodes/order_worker_node.py` | ORDER worker |
| `agent/nodes/search_worker_node.py` | SEARCH worker |
| `agent/nodes/payment_dispatch_node.py` | PAYMENT dispatcher |
| `agent/nodes/state_outcome_node.py` | Context finalizer |
| `agent/nodes/response_node.py` | Rewriter (verbalizer) |
| `agent/nodes/hybrid_router_node.py` | Intent router |
| `agent/nodes/deterministic_validator_node.py` | Tool-call validator |
| `agent/nodes/update_state_node.py` | State updater |
| `agent/graph.py` | LangGraph graph definition |
| `utils/prompt_utils.py` | Prompt assembly utilities |
| `schemas/response_context.py` | Typed context schemas |
| `resources/system_prompts/*.md` | Static system prompts |
| `resources/few_shots/*.json` | Few-shot example sequences |

---

## The Two-Phase Context System

Every agent in this pipeline operates in one of two phases:

| Phase | Agent(s) | Has LLM? | Output |
|-------|----------|----------|--------|
| **Worker phase** | `order_worker`, `search_worker`, `payment_dispatch`, `chat_worker` | ORDER + SEARCH only | Tool calls (ORDER, SEARCH, PAYMENT) or `ChatResponseContext` (CHAT) |
| **Rewriter phase** | `response_node` | 3 of 5 cases | Vietnamese spoken reply (`AIMessage`) |

The worker phase decides **what to do** (tool calls or context building).
The rewriter phase decides **what to say** (natural Vietnamese reply).

This separation means:
- Worker LLMs see tool-call-specialized context (system prompt + few-shot + cart/stage + conversation).
- Rewriter LLM sees verbalization-specialized context (rewriter prompt + structured context block).

---

## AgentState — The Shared Memory Canvas

```python
class AgentState(TypedDict):                          # LangGraph TypedDict
    messages: Annotated[list, add_messages]            # accumulate (never cleared)
    table_id: str                                      # overwrite
    current_intents: list[str]                         # router sets, updater drains
    active_cart: Optional[Cart]                        # order tools write, updater reads
    order_stage: OrderStage                            # IDLE | AWAITING_CONFIRMATION | CONFIRMED
    search_context: Optional[list[SearchResult]]       # SEARCH tool writes, CHAT reads
    is_valid: bool                                     # validator writes
    feedback: Optional[str]                            # validator writes, workers read on retry
    loop_count: int                                    # circuit breaker
    unavailable_items: Optional[list[dict]]            # validator writes, state_outcome clears
    ambiguous_items: Optional[list[dict]]              # validator writes, state_outcome clears
    routing_meta: Optional[dict]                       # router debug metadata
    last_tool: Optional[str]                           # validator writes, state_outcome clears
    ui_action: Optional[str]                           # updater writes, graph.chat() resets
    response_context: Optional[ResponseContext]        # chat_worker or state_outcome writes
```

### Memory lifecycle per field

| Field | Writer | Reader | Cleared by |
|---|---|---|---|
| `messages` | graph (`add_messages`), ToolNode, response_node | all workers, chat_worker, rewriter | Never (LangGraph checkpoint persists) |
| `active_cart` | updater (from tool artifacts) | order_worker, chat_worker, validator | `clear_cart` / session end |
| `order_stage` | updater (from tool artifacts) | order_worker, chat_worker, validator, payment_dispatch | Session end |
| `search_context` | updater (from SEARCH tool artifacts) | chat_worker (via `curated_memory`) | PAYMENT turns (context ended); overwritten each SEARCH |
| `is_valid` | validator | graph routing, state_outcome | state_outcome (`_finalize`) |
| `feedback` | validator | order_worker, search_worker (on retry) | workers set to `None`; state_outcome clears |
| `loop_count` | validator (increment) | graph routing | graph.chat() resets to 0 |
| `unavailable_items` | validator (raw dicts) | state_outcome (→ typed `OffMenuItem`) | state_outcome (`_finalize`) |
| `ambiguous_items` | validator (raw dicts) | state_outcome (→ typed `AmbiguousItem`) | state_outcome (`_finalize`) |
| `current_intents` | router | graph routing, updater | updater drains (pops first) |
| `response_context` | chat_worker (CHAT) / state_outcome (tool paths) | response_node | response_node (sets to `None`) |
| `ui_action` | updater | graph.chat() (`emit_action`) | graph.chat() resets to `None` |
| `last_tool` | validator | state_outcome (retry context) | state_outcome (`_finalize`) |

---

## Per-Agent Context Breakdown

### 1. ORDER Worker (`order_worker_node.py:54`)

**Type:** LLM-based, tool-calling agent.
**LLM:** `ChatOllama` with `WORKER_MODEL`, temperature=0.1, `num_ctx=LLM_NUM_CTX`, bound to `[add_cart, remove_cart, clear_cart, confirm_order]` with `tool_choice="any"` (`order_worker_node.py:16`).

#### Prompt Assembly Chain

The input to the LLM is assembled as a flat message list (`order_worker_node.py:64`):

```
input_messages = [static_system] + few_shot + [dynamic_suffix] + state["messages"]
```

**Layer 1 — Static system prompt** (`build_system_prompt("order_worker_agent.md")`):
Loaded from `resources/system_prompts/order_worker_agent.md` (50 lines). This is the static "persona + rules" prompt. It defines:
- Role: "cart CRUD agent" — map utterances to tool calls only
- Critical rules (one tool per turn, substitution exception, ORDER_CONFIRM → confirm only, verbatim names)
- Quick-reference mapping table (Vietnamese utterance → tool call)

**Layer 2 — Few-shot examples** (`build_few_shot_examples("order_worker.json")`):
Loaded from `resources/few_shots/order_worker.json` (180 lines). Contains 9 shot-pairs (18 messages total):
- Basic add (2 portions, single add, multi-item)
- Special requests ("không cay")
- Remove
- Clear cart
- Confirm order
- Substitution (2 examples: "bỏ...đổi qua..." and "thay...bằng...")

These are converted to `HumanMessage` / `AIMessage(tool_calls=[...])` and placed between the static system prompt and the conversation. They are **static**, so Ollama's prefix KV-cache reuses them across turns.

**Layer 3 — Dynamic suffix** (`build_dynamic_suffix(table_id, context_block)`, `prompt_utils.py:76`):
Assembles session metadata and runtime context into a `SystemMessage` placed **after** the few-shot examples but **before** the conversation history. This positioning preserves prefix caching for layers 1-2 while injecting turn-specific information.

The content:
```
SESSION METADATA:
- Bàn phục vụ (Table ID): T1

DYNAMIC CONTEXT:
Trạng thái đơn hàng (Current Stage): IDLE
### CURRENT ACTIVE CART:
- Ốc Hương Xốt Trứng Muối ×2 (85.000đ/phần)
Tổng: 170.000đ
```

On retry (validator feedback present), an additional block is appended:
```
### SYSTEM FEEDBACK (MANDATORY FIX):
[Món "Ốc Hương" có nhiều loại, anh/chị chọn: ...]
Fix the tool call arguments and retry immediately.
```

The dynamic context block is built by `_build_dynamic_context_block` (`order_worker_node.py:25`):
1. Stage line (`Trạng thái đơn hàng (Current Stage): {stage}`)
2. Cart block (`### CURRENT ACTIVE CART:\n{cart or "(trống)"}`)
3. Feedback block (only if `state["feedback"]` is set, on retry)

**Layer 4 — Full conversation history** (`state["messages"]`):
The entire LangGraph message list, including all prior user utterances, AI responses, tool calls, and tool results. The last `HumanMessage` is the current utterance.

#### Full Input Summary

```
[SystemMessage: order_worker_agent.md (role + rules + mapping table)]         ← static, KV-cached
[HumanMessage: "Cho em 2 phần Ốc Hương"]                                     ← few-shot
[AIMessage(tool_calls=[add_cart(...)])]                                       ← few-shot
... (8 more shot pairs)                                                        ← static, KV-cached
[SystemMessage: SESSION METADATA + DYNAMIC CONTEXT (cart + stage + feedback)] ← dynamic
[HumanMessage: turn 1 utterance]                                               ← conversation
[AIMessage: turn 1 response]                                                   ← conversation
[ToolMessage: turn 1 tool result]                                              ← conversation
[HumanMessage: turn 2 utterance]                                               ← conversation
...                                                                            ← conversation
[HumanMessage: CURRENT utterance]                                              ← NEW, the customer's latest
```

**Token budget:** ~200 tokens dynamic + ~1000 tokens few-shot + ~350 tokens system prompt + conversation (variable).
The full menu list is intentionally NOT included — the validator resolves names independently, keeping the context small.

#### What it reads from AgentState

| Field | Used in | Purpose |
|---|---|---|
| `state["table_id"]` | `table_id` default | Injected into dynamic suffix |
| `state["order_stage"]` | `_build_dynamic_context_block` | Informs the LLM of current stage |
| `state["active_cart"]` | `_build_dynamic_context_block` | Cart summary for the LLM |
| `state["feedback"]` | `_build_dynamic_context_block` | Validator error message on retry |
| `state["messages"]` | appended to input | Full conversation history |

#### What it writes to AgentState

| Field | Value | Purpose |
|---|---|---|
| `messages` | `[AIMessage(tool_calls=[...])]` | Tool call to execute, or error text |
| `feedback` | `None` | Clears validator feedback (consumed) |

#### Why no `search_context`?

The ORDER worker does NOT receive `search_context`. This is intentional:
- The ORDER worker should only reason about the cart and customer utterance
- If the customer says "cho món đó 2 phần", the LLM needs the cart (to resolve "món đó") not search results
- The router already classified this as ORDER — the LLM doesn't need to re-decide intent

---

### 2. SEARCH Worker (`search_worker_node.py:52`)

**Type:** LLM-based, tool-calling agent.
**LLM:** `ChatOllama` with `WORKER_MODEL`, temperature=0.1, bound to `[search]` with `tool_choice="any"` (note: `tool_choice="any"` may be ignored by Ollama — enforcement comes from system prompt + schema + few-shot; `search_worker_node.py:25`).

#### Prompt Assembly Chain

Identical structure to ORDER worker (`search_worker_node.py:70`):

```
input_messages = [static_system] + few_shot + [dynamic_suffix] + state["messages"]
```

**Layer 1 — Static system prompt** (`build_system_prompt("search_agent.md")`):
Loaded from `resources/system_prompts/search_agent.md` (82 lines). Defines:
- Role: "search parameter-extraction agent" — output ONLY `search()` tool calls
- Core rules: always call search, rewrite conversational queries to keywords, extract Vietnamese filters (price, diet, category)
- Comprehensive Vietnamese query → parameter mapping (vibe/feeling rewrites, price filters, diet & category, restaurant info, combined filters, direct lookup)
- Must-NOT-do list

**Layer 2 — Few-shot examples** (`build_few_shot_examples("search_worker.json")`):
Loaded from `resources/few_shots/search_worker.json` (160 lines). 9 shot-pairs:
- Conversational rewrite ("trời lạnh" → "cháo, lẩu, súp nóng")
- Vibe rewrite ("uống gì cho mát" → "trà tắc, nước ngọt, giải khát")
- Restaurant info ("wifi" → "wifi, mật khẩu, ssid")
- Restaurant info ("giờ mở cửa" → "giờ mở cửa, giờ đóng cửa, thời gian hoạt động")
- Price filter ("dưới 50k" → max_price=50000)
- Diet filter ("món chay" → diet_type="chay")
- Category filter ("đồ uống" → category="Giải Khát")
- Direct lookup ("Ốc Hương..." → query="Ốc Hương Xốt Trứng Muối")
- Combined filter ("món chay dưới 100k" → diet_type="chay", max_price=100000)

**Layer 3 — Dynamic suffix** (minimal for SEARCH):
```
SESSION METADATA:
- Bàn phục vụ (Table ID): T1
```

On retry (validator feedback present):
```
SESSION METADATA:
- Bàn phục vụ (Table ID): T1

DYNAMIC CONTEXT:
### SYSTEM FEEDBACK (MANDATORY FIX):
{feedback}
Fix the tool call arguments and retry immediately.
```

The search worker's dynamic context is simpler than ORDER's — it doesn't include cart or stage information. The SEARCH worker doesn't need to know what the customer has ordered to search for dishes.

**Layer 4 — Full conversation history** (`state["messages"]`).

#### What it reads from AgentState

| Field | Used in | Purpose |
|---|---|---|
| `state["table_id"]` | `table_id` default | Injected into dynamic suffix |
| `state["feedback"]` | `_build_search_dynamic_context` | Validator error on retry |
| `state["messages"]` | appended to input | Full conversation history |
| `state["loop_count"]` | error path only | Incremented +1 on LLM failure |

#### What it writes to AgentState

| Field | Value | Purpose |
|---|---|---|
| `messages` | `[AIMessage(tool_calls=[{search(...)}])]` or error text | Search query to execute |
| `feedback` | `None` | Clears validator feedback |
| `loop_count` | `state["loop_count"] + 1` | Only on LLM error path |

#### What the SEARCH tool produces (consumed by updater, then chat_worker)

When the `search()` tool executes, it returns a `SearchResponse` with `results: List[SearchResult]`. Each `SearchResult` has:
```python
SearchResult.document.metadata:
    name: str              # "Ốc Hương Xốt Trứng Muối"
    price: int             # 85000
    tags: str              # "cay, đặc sản, hải sản"
    description: str       # Full menu description
    category: str          # "Ốc & Sò"
    taste_profile: str     # "cay, mặn"
    type: str              # "menu" | "info" | "bestseller"
```

The `state_updater` writes `search_context = results` to AgentState. This is the bridge between RAG and conversation.

---

### 3. PAYMENT Dispatcher (`payment_dispatch_node.py:25`)

**Type:** Deterministic, NO LLM.
**No context assembled.** Pure Python function.

#### What it reads from AgentState

| Field | Used in | Purpose |
|---|---|---|
| `state["table_id"]` | `table_id` default | Injected into request_payment args |

#### What it writes to AgentState

| Field | Value | Purpose |
|---|---|---|
| `messages` | `[AIMessage(tool_calls=[{request_payment(table_id)}])]` | Hardcoded payment request |
| `feedback` | `None` | Always clears |

The PAYMENT dispatcher is the simplest agent. The router already decided PAYMENT intent — no further LLM decision is needed. The node always emits the same tool call: `request_payment(table_id=T1)`.

Note: `verify_payment` is not triggered by this node. It is called by the backend's mock verification flow, not by the agent on a customer turn.

---

### 4. CHAT Worker (`chat_worker_node.py:56`) — The Central Focus

**Type:** Pure Python function, NO LLM call, NO tool call.

This is the **only leaf worker** — it doesn't produce tool calls. Instead, it builds a typed `ChatResponseContext` that the rewriter reads. The LLM call happens later, in `response_node._llm_paraphrase_chat`.

#### Why a separate worker?

Originally the router's inline helper built `ChatResponseContext` directly. The CHAT worker was promoted to its own node to maintain graph symmetry: every intent (ORDER, SEARCH, PAYMENT, CHAT) has a dedicated worker node. The router's job stays simple: decide intent → route to the right worker.

#### Graph routing to CHAT worker

The CHAT worker is reached via 3 paths (`graph.py:51`):

```
1. Router classifies utterance as CHAT
   → router → _route_by_intent → "chat_worker"

2. ORDER/SEARCH worker produces NO tool calls (defense-in-depth)
   → order_worker/search_worker → _route_if_tool_call → "chat_worker"

3. No intents remaining (fallback)
   → DEFAULT_WORKER = "chat_worker"
```

#### What it reads from AgentState

```python
# chat_worker_node.py:81-94
messages = state.get("messages") or []      # Full conversation history
search_results = state.get("search_context") # RAG results from prior SEARCH turn
active_cart = state.get("active_cart") or Cart()
order_stage = state.get("order_stage", "IDLE")
user_message = last_user_text(state)         # Most recent HumanMessage.content
```

#### What it writes to AgentState

```python
# chat_worker_node.py:83-94
{
    "response_context": ChatResponseContext(
        kind="CHAT",
        intent="CHAT",
        user_message="có cay không em?",
        active_cart=Cart(items=[...], total_price=170000),
        order_stage="AWAITING_CONFIRMATION",
        chat_history=[HumanMessage(...), AIMessage(...), ...],  # shallow copy
        curated_memory=[                                         # search_context → CuratedDish
            CuratedDish(
                name="Ốc Hương Xốt Trứng Muối",
                price=85000,
                tags=["cay", "đặc sản", "hải sản"],
                taste_profile="cay, mặn",
                category="Ốc & Sò",
            ),
        ],
    ),
}
```

#### The `_to_curated_memory` transform (`chat_worker_node.py:31`)

This is the critical bridge between the RAG pipeline and the conversational agent:

```python
def _to_curated_memory(search_results, max_items=5) -> List[CuratedDish]:
    dishes = []
    for r in (search_results or []):
        meta = r.document.metadata
        if meta.get("type") != "menu":       # Skip info/bestseller/promo docs
            continue
        tags_str = meta.get("tags", "")
        tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        dishes.append(CuratedDish(
            name=meta.get("name", ""),
            price=int(price_val) if price_val else None,
            tags=tag_list,
            taste_profile=meta.get("taste_profile"),
            category=meta.get("category"),
        ))
    return dishes[:max_items]                 # Cap at 5 to avoid prompt bloat
```

What it strips: embedding vectors, `document.content` (raw text), search scores, and search-specific metadata. What it keeps: name, price, tags, taste_profile, category — the fields the chat LLM can use to answer follow-up questions.

#### The `curated_memory` → LLM projection (`response_node.py:223`)

The `ChatResponseContext` built by the chat_worker is later projected into a **text block** by `_format_chat_for_llm` in `response_node.py`:

```
Giỏ hàng hiện tại: Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần) (tổng 170.000₫)
Trạng thái đơn: AWAITING_CONFIRMATION
Món đã thảo luận (từ các lần tìm kiếm trước):
  - Ốc Hương Xốt Trứng Muối | 85.000₫/phần | cay, đặc sản, hải sản | cay, mặn
  - Ốc Hương Rang Muối | 75.000₫/phần | mặn, cay | mặn, cay
Lịch sử hội thoại:
  Khách: Ốc Hương Xốt Trứng Muối bao nhiêu tiền vậy em?
  Em: Dạ, món Ốc Hương Xốt Trứng Muối có giá 85.000₫ ạ.
  Khách: Có cay không em?
Khách vừa nói: "có cay không em?"
```

This text block is then passed as a `SystemMessage(content="CONTEXT:\n{text}")` to the rewriter LLM alongside the `CHAT_REWRITER_PROMPT` system prompt.

#### The CHAT Rewriter LLM prompt (`response_node.py:81`)

```
Bạn là phục vụ viên AI tại Ốc Quậy. Khách vừa nói gì đó. Nhìn CONTEXT bên dưới
rồi trả lời lịch sự bằng tiếng Việt.
KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT.
Nếu khách hỏi về một món cụ thể (có cay không? giá bao nhiêu? mô tả? vị ra sao?),
kiểm tra 'Món đã thảo luận' trong CONTEXT trước. Nếu có trong đó → trả lời từ đó.
Nếu không có → nói 'Dạ em chưa có thông tin về món này, anh/chị cho em tìm giúp nhé ạ?'
Nếu khách dùng đại từ tham chiếu ('cái đó', 'món đó', 'món lúc nãy') → dùng
lịch sử hội thoại để xác định món đang được nhắc tới, rồi tra trong
'Món đã thảo luận' hoặc giỏ hàng.
Nếu khách hỏi về giỏ hàng / đơn hàng → liệt kê món + giá từng món + tổng từ CONTEXT.
Nếu khách tán gẫu / hỏi ngoài phạm vi → trả lời ngắn rồi hỏi lại cần hỗ trợ gì.
Dùng 'Dạ', 'ạ', xưng 'em', gọi khách là 'anh/chị'. 1-3 câu.
```

#### Two templates shortcut the LLM (`response_node.py:420`)

Before the LLM is called, two pure-template checks run:
- Greeting detection (`_is_greeting`): "chào", "xin chào", "hello", "hi" → "Dạ, em chào anh/chị ạ."
- Thanks detection (`_is_thanks`): "cảm ơn", "thank you", "thanks" → "Dạ, không có gì ạ."

These skip the LLM entirely, saving latency and preventing the LLM from over-responding to simple courtesies.

#### The two knowledge sources for CHAT

The CHAT LLM receives **two distinct knowledge sources**:

| Source | Origin | Purpose | Example |
|--------|--------|---------|---------|
| **Cart** (`active_cart`) | ORDER tools via updater | What the customer has ordered (action memory) | "Ốc Hương ×2, total 170.000₫" |
| **Curated memory** (`curated_memory`) | SEARCH tool via updater → chat_worker conversion | What the system knows about discussed dishes (semantic memory) | "Ốc Hương Xốt Trứng Muối: 85K, cay, đặc sản" |

This mirrors human waiter memory: "I know what you ordered (cart) and what I told you about (menu memory)."

#### Memory lifecycle: when is `curated_memory` populated?

```
Turn N:   Customer = "Ốc Hương giá bao nhiêu?"
          Router → SEARCH
          search_worker → search("Ốc Hương")
          ToolNode executes → SearchResponse(results=[Ốc Hương Xốt Trứng Muối, ...])
          updater → search_context = [SearchResult, ...]    ← POPULATED
          state_outcome → SearchResponseContext → response_node → "Dạ, 85.000₫ ạ"
          search_context PERSISTS in AgentState

Turn N+1: Customer = "có cay không?"
          Router → CHAT
          chat_worker → reads search_context → builds curated_memory
          chat_worker writes response_context with curated_memory → state_outcome finalizes
          response_node._llm_paraphrase_chat → sees curated_memory → "Dạ, có cay ạ."

Turn N+2: Customer = "cho 2 phần đi"
          Router → ORDER
          order_worker → add_cart(...)
          updater → active_cart updated
          state_outcome → OrderResponseContext(kind="ORDER")
          _finalize sees kind="ORDER" → does NOT clear search_context

Turn N+3: Customer asks follow-up → curated_memory still available (not cleared on ORDER)
```

Clearing rules:
- **SEARCH turn**: `search_context` overwritten with fresh results
- **PAYMENT turn**: `search_context` → `None` (conversation ended, bill paid)
- **ORDER turn**: NOT cleared (follow-up questions about ordered dishes still possible)
- **CHAT turn**: NOT cleared (the whole point is to reference prior search results)

---

## Context Comparison Matrix

| Aspect | ORDER Worker | SEARCH Worker | PAYMENT Dispatch | CHAT Worker |
|--------|-------------|---------------|------------------|-------------|
| **LLM call?** | Yes | Yes | No | No (LLM later in rewriter) |
| **Tools bound?** | add/remove/clear/confirm | search | N/A | N/A |
| **Static system prompt** | `order_worker_agent.md` (50 lines) | `search_agent.md` (82 lines) | N/A | `CHAT_REWRITER_PROMPT` (applied in rewriter) |
| **Few-shot examples** | 9 shot-pairs (180 lines) | 9 shot-pairs (160 lines) | N/A | N/A |
| **Dynamic context** | Cart + stage + feedback | Feedback only (retry) | N/A | Cart + stage + curated_memory + history + utterance |
| **Reads cart?** | Yes (in dynamic context) | No | No | Yes |
| **Reads search_context?** | No | No | No | Yes (→ curated_memory) |
| **Reads order_stage?** | Yes | No | No | Yes |
| **Reads feedback?** | Yes (retry) | Yes (retry) | No | No |
| **Writes to state** | messages, feedback=None | messages, feedback=None | messages, feedback=None | response_context |
| **Output type** | `AIMessage(tool_calls=[...])` | `AIMessage(tool_calls=[...])` | `AIMessage(tool_calls=[...])` | `ChatResponseContext` |
| **Where LLM actually runs** | In the worker itself | In the worker itself | Never | In `response_node._llm_paraphrase_chat` |

---

## The Graph Flow: How Context Accumulates

```
START
  │
  ▼
router (hybrid_router_node)         ← classifies intent: ORDER | SEARCH | PAYMENT | CHAT
  │                                   writes: current_intents, routing_meta
  ▼
worker (order | search | payment | chat)
  │
  ├─ has tool_calls ──► validator (deterministic_validator_node)
  │                        │           writes: is_valid, feedback, last_tool,
  │                        │                   unavailable_items, ambiguous_items
  │                        ├─ valid ──► tools (ToolNode executes tool)
  │                        │              │
  │                        │              ▼
  │                        │           updater (update_state_node)
  │                        │              │  writes: active_cart, order_stage,
  │                        │              │          search_context, ui_action
  │                        │              │  drains: current_intents
  │                        │              ├─ more intents → back to worker
  │                        │              └─ done → state_outcome
  │                        │
  │                        └─ invalid ──► back to worker (retry with feedback)
  │
  ├─ no tool_calls ──► chat_worker (if ORDER intent misrouted)
  │                       │  writes: response_context (ChatResponseContext)
  │                       └─► state_outcome
  │
  └─ CHAT worker already ──► state_outcome

state_outcome (state_outcome_node)   ← builds ResponseContext from tool message,
  │                                     or finalizes ChatResponseContext from chat_worker
  │                                   clears per-turn fields: unavailable_items,
  │                                     ambiguous_items, feedback, last_tool
  │                                   clears search_context on PAYMENT only
  ▼
response_node (response_node)        ← reads response_context, dispatches to rewriter
  │                                     writes: messages (AIMessage), response_context=None
  ▼
END
```

---

## Design Principles (revisited with code references)

1. **Cart is action memory, `search_context` is semantic memory.** Both feed the CHAT worker as two distinct knowledge sources. The cart comes from `state["active_cart"]` (written by `update_state_node` from ORDER tool artifacts). `search_context` comes from `state["search_context"]` (written by `update_state_node` from SEARCH tool artifacts). See `chat_worker_node.py:81-94`.

2. **CHAT worker is read-only.** It builds a context for the response LLM but doesn't modify AgentState (beyond setting `response_context`). This keeps it predictable and testable. The LLM call itself happens in `response_node._llm_paraphrase_chat` (`response_node.py:257`).

3. **Memory clears on context shift, not turn count.** When the customer pays (PAYMENT turn), `_finalize` in `state_outcome_node.py:283` clears `search_context = None` because the conversation is over. ORDER turns do NOT clear `search_context` — follow-up questions about ordered dishes are still valid.

4. **No self-loop in CHAT.** If curated memory is insufficient, the LLM tells the customer ("Dạ em chưa có thông tin về món này..."). The customer rephrases. The router routes to the right worker next turn. This is more reliable than an agent loop that could loop silently.

5. **Two-phase architecture.** Workers decide what to do (tool calls or context building). The rewriter decides what to say. This means worker LLMs see specialized tool-call context, while the rewriter LLM sees a structured context block. See `graph.py` edges: all paths end at `state_outcome → response_node → END`.

6. **Static prefix + dynamic suffix pattern.** All LLM-calling nodes use the same prompt assembly strategy (`prompt_utils.py`): static system prompt + static few-shot + dynamic suffix (table_id, cart, stage, feedback) + conversation. The static parts are KV-cached by Ollama; the dynamic part is small (~200 tokens).

7. **Validator as contract enforcer (not LLM).** The `deterministic_validator_node` is pure Python. It validates tool calls against the menu (via `resolve_menu_name`), the cart (remove/clear checks), and stage (confirm requires AWAITING_CONFIRMATION). It writes `feedback` which feeds back into worker retry cycles. No LLM is used for validation — this saves latency and prevents hallucination in the validation step.

---

## Token Budget per Agent (approximate, per turn)

| Agent | Static (KV-cached) | Dynamic (per-turn) | Conversation (variable) | Total typical |
|-------|-------------------|---------------------|------------------------|--------------|
| ORDER worker | ~1400 tokens (system + few-shot) | ~200 tokens (cart + stage + feedback) | ~500-2000 tokens | ~2100-3600 |
| SEARCH worker | ~1800 tokens (system + few-shot) | ~50 tokens (table_id + feedback) | ~500-2000 tokens | ~2350-3850 |
| CHAT rewriter | ~250 tokens (CHAT_REWRITER_PROMPT) | ~600-1500 tokens (cart + curated_memory + history + utterance) | (included in dynamic) | ~850-1750 |
| PAYMENT dispatch | 0 | 0 | 0 | 0 |

---

## Future: Memory Accumulation (out of scope for v1.7)

Current design: `search_context` holds only the LAST SEARCH results. Future could accumulate results from multiple SEARCH turns into a sliding window:

```python
# Future: accumulate instead of overwrite
search_context: List[SearchResult] = []  # AdditiveOperator, capped at N items
```

This would let the CHAT worker reference dishes from turn 3 even after turn 5 and turn 7 searched different things. Requires a deduplication + FIFO eviction strategy. The `_to_curated_memory` capping at 5 items already anticipates this — merging accumulated results would need a similar cap and dedup logic (by dish name).
