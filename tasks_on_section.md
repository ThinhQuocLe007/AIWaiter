# Known Issues — Search Worker Freeze on Multi-Intent Turns

## Problem: Search worker produces no tool call, kills remaining intents

**Discovered**: Turn 11 of the long conversation test (post-Phase 1-7 refactor).

**User query**: *"Gỏi Xoài Ốc Giác có ngon không? Anh tính gọi thêm 1 phần mà sợ cay quá"*

**Router output**: `[SEARCH, ORDER]` — correct dual-intent classification.

### Chain of failure

**1. Router correctly classifies as `[SEARCH, ORDER]`**

Two intents queued: first search the dish info, then process any order action.

**2. Search worker produces nothing**

The search worker runs first. Its LLM receives:
- System prompt (`search_agent.md`)
- 11 few-shot pairs (2 delegate, 9 search)
- ĐÃ BIẾT list (dishes in cart + prior search results, including Gỏi Xoài Ốc Giác)
- Last 2 turns of conversation history — both are order_worker cart echoes, zero search context
- The user's utterance containing mixed signals: dish name ("Gỏi Xoài Ốc Giác"), taste question ("có ngon không?", "sợ cay"), ordering language ("gọi thêm 1 phần")

The LLM has 2 tools: `delegate` and `search`. With conflicting signals (known dish vs. new question, order language vs. search intent), the 7B model can't decide and produces **no tool call** — despite `tool_choice="any"`.

**3. `_route_if_tool_call` routes to `response_node → END`**

```python
# graph.py — _route_if_tool_call defensive branch:
intents = state.get("current_intents") or []
if intents and intents[0] in ("ORDER", "ORDER_CONFIRM"):
    return "chat_worker"     # ← would fire if intent were ORDER, but it's SEARCH
# Falls through to:
logger.warning("Worker produced no tool_calls...")
return "response_node"       # ← routes to END, killing all remaining intents
```

The ORDER intent still sits in the queue but is never processed. The turn ends with a generic apology.

### Root cause: Asymmetry between workers

| Worker | Retry on no tool call? | What happens |
|--------|----------------------|--------------|
| order_worker | **Yes** (lines 83-92) | Retry with forced instruction: "MUST call add_cart/remove_cart/..." |
| search_worker | **No** | Falls through to `response_node → END` |

The order worker was designed with a retry loop because it frequently encounters ambiguous queries (ported from ORDER when it should be SEARCH). The search worker never got the same guard because originally it only had one tool (`search`) — the LLM couldn't choose wrong.

Now with `delegate` as a second tool, the search worker faces the same ambiguity problem but has no safety net.

### Proposed fix

Add retry logic to `search_worker_node.py`, symmetric with the order worker:

```python
# After first _search_model.invoke():
if not response.tool_calls:
    retry_prompt = SystemMessage(
        content=(
            "⚠ CRITICAL: Bạn PHẢI gọi một tool call (search hoặc delegate). "
            "KHÔNG được trả lời bằng text. Nếu không chắc chắn, hãy gọi "
            "search() với tên món ăn hoặc từ khóa chính. "
            "Chỉ trả về tool call NGAY BÂY GIỜ."
        )
    )
    response = _search_model.invoke([retry_prompt] + list(input_messages))
```

This mirrors the order worker's retry at `order_worker_node.py:83-92` exactly.

### Files affected

| File | Action |
|------|--------|
| `agent/nodes/search_worker_node.py` | Add retry loop when no tool call produced |

### Alternatives considered

**A) Route to next worker on no-tool-call instead of response_node.** Changes `_route_if_tool_call` to proceed to next intent. Downside: the SEARCH intent silently fails with no response, customer sees only the ORDER half.

**B) Remove delegate from search worker.** Reverts to single-tool `search()`, LLM can't freeze. Downside: loses protection against misrouted SEARCH intents (e.g., "xem lại order" → nonsensical RAG call).

**C) Add retry (proposed).** Keeps delegate, adds safety net. Same pattern already proven in order_worker.
