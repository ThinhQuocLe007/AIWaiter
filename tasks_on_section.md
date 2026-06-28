# AI Waiter — Response Worker as a Schema-Driven Rewriter

> Implementation-focused plan. The architecture is the same as the previous revision; this version drops most of the rationale and focuses on **what to build and how to build it**.
>
> **LOCAL-ONLY NOTE:** Every commit below is local. Branch `backend-server-integration`. Never `git push`, never `gh`.

---

## 1. The proposed method, in one paragraph

Replace the current `response_node` (a single LLM call that mines scattered state) with a **typed rewriter**: each turn produces a single Pydantic `ResponseContext` (built by either `state_outcome` for tool paths or `chat_worker` for CHAT paths), and the new `response_node` is a thin dispatcher that maps that context to either a pure-Python template or a small LLM call. The LLM is reserved for the 4 cases that genuinely need paraphrasing (search results, off-menu-with-suggestion apology, free-form chat, edge cases); everything else is a template. The chat rewriter uses only 2 template triggers (`_is_greeting`, `_is_thanks`) — everything else (status questions, small talk, out of scope) goes to the LLM with the cart in context. No new tools, no router change, no worker prompt change.

---

## 2. File map (before / after)

### 2.1 New files

| File | LOC | Purpose |
|---|---|---|
| `src/agent_brain/schemas/response_context.py` | ~120 | The 5 context Pydantic classes + the `ResponseContext` union |
| `src/agent_brain/agent/nodes/chat_worker_node.py` | ~25 | Builds `ChatResponseContext` from state for the CHAT path |
| `src/agent_brain/agent/nodes/state_outcome_node.py` | ~120 | Builds a typed `ResponseContext` from `messages[-1]` + state for tool paths; finalizes the per-turn reset |
| `tests/test_state_outcome.py` | ~150 | Unit tests for `state_outcome_node` (all turn types) |
| `tests/test_chat_worker.py` | ~60 | Unit tests for `chat_worker_node` (cart / stage variations) |
| `tests/test_rewriter.py` | ~250 | Unit tests for `_rewrite_*` (12+ cases, including mock-LLM tests for the LLM branches) |

### 2.2 Modified files

| File | Change | LOC delta |
|---|---|---|
| `src/agent_brain/agent/state.py` | Add `response_context: Optional[ResponseContext]` to `AgentState` | +8 |
| `src/agent_brain/agent/nodes/__init__.py` | Export `chat_worker_node`, `state_outcome_node` | +2 |
| `src/agent_brain/agent/graph.py` | Register `chat_worker` + `state_outcome`; rewire edges (§4) | +25 |
| `src/agent_brain/agent/nodes/response_node.py` | Replace body with dispatcher + `_rewrite_*` functions; drop `_build_response_context`; keep `_build_ambiguity_response` as `_rewrite_order` branch | -30, +200 |
| `src/agent_brain/agent/nodes/deterministic_validator_node.py` | Populate `OffMenuItem.suggestion` (Phase 2) | +5 |
| `src/agent_brain/agent/nodes/update_state_node.py` | Drop reading of removed fields (Phase 5) | -10 |
| `src/agent_brain/utils/menu_utils.py` | Add `find_nearest_menu_name()` (Phase 2) | +20 |
| `src/agent_brain/agent/resources/system_prompts/waiter_agent.md` | Slim to ~25 lines + chat rewriter block (Phase 4) | -60, +30 |
| `src/agent_brain/schemas/__init__.py` | Re-export the 5 context types | +6 |

### 2.3 Net effect

- **+1 new graph node** (`chat_worker`), **+1 new graph node** (`state_outcome`) — but both are small pure-Python functions
- **+5 LOC to `AgentState`** (one field)
- **+200 LOC to `response_node.py`** (the rewriter dispatcher + template functions) but **-200 LOC of legacy code** (the old `_build_response_context` and the brittle 100-line prompt)
- **0 new tools, 0 router changes, 0 worker prompt changes**

---

## 3. The schemas (the contract)

New file: `src/agent_brain/schemas/response_context.py`. This is the **single most important file** — every other change hangs off these types.

```python
# src/agent_brain/schemas/response_context.py
from typing import Literal, Optional, List, Union
from pydantic import BaseModel, Field
from .order import Cart, OrderItem, OrderStage
from .search import SearchResult
from .routing import IntentType


class OffMenuItem(BaseModel):
    name: str                          # as the customer said it
    suggestion: Optional[str] = None   # closest menu name (Phase 2)


class AmbiguousItem(BaseModel):
    name: str
    candidates: List[str]


class OrderResponseContext(BaseModel):
    kind: Literal["ORDER"] = "ORDER"
    tool: Literal["sync_cart", "confirm_order"]
    outcome: Literal["success", "error"]
    cart: List[OrderItem] = Field(default_factory=list)
    total_vnd: str = "0"               # pre-formatted "170.000"
    off_menu: List[OffMenuItem] = Field(default_factory=list)
    ambiguous: List[AmbiguousItem] = Field(default_factory=list)
    order_id: Optional[int] = None
    stage: OrderStage = "IDLE"
    ui_action: Optional[str] = None
    error_message: Optional[str] = None


class SearchResponseContext(BaseModel):
    kind: Literal["SEARCH"] = "SEARCH"
    tool: Literal["search"]
    outcome: Literal["success", "error"]
    query: str
    results: List[SearchResult] = Field(default_factory=list)
    ui_action: Optional[str] = None
    error_message: Optional[str] = None


class PaymentResponseContext(BaseModel):
    kind: Literal["PAYMENT"] = "PAYMENT"
    tool: Literal["request_payment", "verify_payment"]
    outcome: Literal["success", "error"]
    amount_vnd: Optional[str] = None
    qr_url: Optional[str] = None
    table_id: str
    ui_action: Optional[str] = None
    error_message: Optional[str] = None


class ChatResponseContext(BaseModel):
    """Pure chat / status questions / small talk / out of scope.

    Carries `active_cart` and `order_stage` so the LLM in
    _llm_paraphrase_chat can answer cart-status questions
    ('what did I order?', 'how much so far?') without a
    read tool and without a hardcoded pattern list.
    """
    kind: Literal["CHAT"] = "CHAT"
    tool: None = None
    outcome: None = None
    intent: IntentType
    user_message: str
    active_cart: Cart = Field(default_factory=Cart)
    order_stage: OrderStage = "IDLE"
    ui_action: None = None
    error_message: None = None


class RetryResponseContext(BaseModel):
    kind: Literal["RETRY"] = "RETRY"
    tool: str
    feedback: str
    intent: IntentType
    ui_action: None = None
    error_message: None = None


ResponseContext = Union[
    OrderResponseContext,
    SearchResponseContext,
    PaymentResponseContext,
    ChatResponseContext,
    RetryResponseContext,
]
```

And in `src/agent_brain/agent/state.py`:

```python
class AgentState(TypedDict):
    # ... existing fields unchanged ...

    # The typed handoff from the implement stage to the response stage.
    # Set by chat_worker (CHAT path) or state_outcome (tool path).
    # Read and cleared by response_node. Nothing else touches it.
    response_context: Optional[ResponseContext]
```

---

## 4. The graph change

### 4.1 Today (graph.py:97-176)

```
router → worker → validator → tools → state_updater → response_node → END
                        ↑                                │
                        └──── retry (if invalid) ────────┘
```

### 4.2 Proposed

```
router ─┬─ ORDER     → order_worker    → validator → tools → state_updater → state_outcome ┐
        ├─ SEARCH    → search_worker   → validator → tools → state_updater → state_outcome │
        ├─ PAYMENT   → payment_worker  → validator → tools → state_updater → state_outcome ├─→ response_node → END
        └─ CHAT      → chat_worker     ───────────────────────────────────── state_outcome ┘
```

### 4.3 Exact graph.py edits

```python
# in src/agent_brain/agent/graph.py

# 1. Import the new nodes
from src.agent_brain.agent.nodes.chat_worker_node import chat_worker_node
from src.agent_brain.agent.nodes.state_outcome_node import state_outcome_node

# 2. In AIWaiterGraph._build_workflow, after the existing add_node calls:
workflow.add_node("chat_worker", chat_worker_node)
workflow.add_node("state_outcome", state_outcome_node)

# 3. Replace the response_node edge in _route_after_updater
#    (graph.py:85-94) — the conditional map now has fewer entries
#    because state_outcome always runs.
#    Old:
#       {"order_worker": ..., "search_worker": ..., "payment_worker": ...,
#        "response_node": ..., "end": END}
#    New:
#       {"state_outcome": "state_outcome", "end": END}
#    (workers route to state_outcome when there are more intents OR the
#     last message is a tool result; END only when there are no more
#     intents and the last message is NOT a tool result)

# 4. Add new edges
workflow.add_edge("chat_worker", "state_outcome")
workflow.add_edge("state_updater", "state_outcome")
workflow.add_edge("state_outcome", "response_node")
```

The `_route_by_intent` function (graph.py:43-45) needs to change CHAT's target:

```python
INTENT_TO_WORKER = {
    "ORDER": "order_worker",
    "ORDER_CONFIRM": "order_worker",
    "SEARCH": "search_worker",
    "PAYMENT": "payment_worker",
    "CHAT": "chat_worker",   # ← was "response_node"
}
```

That's the entire graph change. **4 lines of imports, 2 lines of add_node, 1 line of intent map, 3 lines of add_edge.**

---

## 5. The new nodes

### 5.1 `chat_worker_node` (10 LOC, pure)

```python
# src/agent_brain/agent/nodes/chat_worker_node.py
from typing import Dict, Any
from langchain_core.messages import HumanMessage
from src.agent_brain.agent.state import AgentState
from src.agent_brain.schemas import ChatResponseContext
from src.agent_brain.schemas.order import Cart


def _last_user_text(state: AgentState) -> str:
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def chat_worker_node(state: AgentState) -> Dict[str, Any]:
    """Build a ChatResponseContext for the CHAT path.

    Symmetric with the tool-calling workers (order/search/payment):
    every intent has a worker that produces a typed context for
    response_node to read.

    Pure function: no LLM call, no tool call.
    """
    return {
        "response_context": ChatResponseContext(
            kind="CHAT",
            intent="CHAT",
            user_message=_last_user_text(state),
            active_cart=state.get("active_cart") or Cart(),
            order_stage=state.get("order_stage", "IDLE"),
        ),
    }
```

### 5.2 `state_outcome_node` (50 LOC, pure)

```python
# src/agent_brain/agent/nodes/state_outcome_node.py
from typing import Dict, Any
from langchain_core.messages import ToolMessage
from src.agent_brain.agent.state import AgentState
from src.agent_brain.schemas import (
    ResponseContext, OrderResponseContext, SearchResponseContext,
    PaymentResponseContext, ChatResponseContext, RetryResponseContext,
)
from src.agent_brain.schemas.order import Cart
from src.agent_brain.schemas.search import SearchResult
from src.agent_brain.schemas.reflection import ItemCorrection


def _last_user_text(state: AgentState) -> str:
    for m in reversed(state["messages"]):
        from langchain_core.messages import HumanMessage
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def _build_from_tool_message(last: ToolMessage, state: AgentState) -> ResponseContext:
    """Map a tool result to a typed context based on the tool name."""
    ui = state.get("ui_action")
    tool_name = last.name
    artifact = getattr(last, "artifact", None)
    cart = state.get("active_cart")
    total_vnd = f"{int(cart.total_price):,}".replace(",", ".") if cart else "0"
    stage = state.get("order_stage", "IDLE")

    if tool_name == "sync_cart":
        return OrderResponseContext(
            tool="sync_cart",
            outcome="success" if artifact and getattr(artifact, "status", None) == "success" else "error",
            cart=cart.items if cart else [],
            total_vnd=total_vnd,
            off_menu=state.get("unavailable_items") or [],
            ambiguous=state.get("ambiguous_items") or [],
            stage=stage,
            ui_action=ui,
            error_message=getattr(artifact, "message", None) if artifact else None,
        )
    if tool_name == "confirm_order":
        return OrderResponseContext(
            tool="confirm_order",
            outcome="success" if artifact and getattr(artifact, "status", None) == "success" else "error",
            cart=cart.items if cart else [],
            total_vnd=total_vnd,
            order_id=getattr(artifact, "order_id", None) if artifact else None,
            stage="CONFIRMED",
            ui_action=ui,
            error_message=getattr(artifact, "message", None) if artifact else None,
        )
    if tool_name == "search":
        return SearchResponseContext(
            tool="search",
            outcome="success" if artifact and getattr(artifact, "status", None) == "success" else "error",
            query=last.content or "",
            results=getattr(artifact, "results", []) if artifact else [],
            ui_action=ui,
            error_message=getattr(artifact, "message", None) if artifact else None,
        )
    if tool_name == "request_payment":
        return PaymentResponseContext(
            tool="request_payment",
            outcome="success" if artifact and getattr(artifact, "status", None) == "success" else "error",
            amount_vnd=f"{int(artifact.amount):,}".replace(",", ".") if artifact and getattr(artifact, "amount", None) else None,
            qr_url=getattr(artifact, "qr_url", None) if artifact else None,
            table_id=state.get("table_id", "T1"),
            ui_action=ui,
            error_message=getattr(artifact, "message", None) if artifact else None,
        )
    if tool_name == "verify_payment":
        return PaymentResponseContext(
            tool="verify_payment",
            outcome="success" if artifact and getattr(artifact, "status", None) == "success" else "error",
            table_id=state.get("table_id", "T1"),
            ui_action=ui,
            error_message=getattr(artifact, "message", None) if artifact else None,
        )
    # Defensive fallback for unknown tools
    return ChatResponseContext(
        intent="CHAT",
        user_message=_last_user_text(state),
        active_cart=cart or Cart(),
        order_stage=stage,
    )


def _is_retry_state(state: AgentState) -> bool:
    return (state.get("is_valid") is False
            and bool(state.get("feedback"))
            and not isinstance(state["messages"][-1], ToolMessage))


def _build_retry_context(state: AgentState) -> RetryResponseContext:
    return RetryResponseContext(
        tool=state.get("last_tool", ""),
        feedback=state.get("feedback", ""),
        intent="ORDER",
    )


def state_outcome_node(state: AgentState) -> Dict[str, Any]:
    """Build a typed ResponseContext from the current turn's state.

    Pure function: no LLM call, no side effects. For the CHAT path
    chat_worker has already set response_context; this node just
    runs the per-turn reset.
    """
    existing = state.get("response_context")
    if existing is not None:
        return _finalize(existing)

    last = state["messages"][-1]
    if isinstance(last, ToolMessage):
        return _finalize(_build_from_tool_message(last, state))
    if _is_retry_state(state):
        return _finalize(_build_retry_context(state))

    # Defensive: should be unreachable for tool paths.
    return _finalize(ChatResponseContext(
        intent="CHAT",
        user_message=_last_user_text(state),
        active_cart=state.get("active_cart") or Cart(),
        order_stage=state.get("order_stage", "IDLE"),
    ))


def _finalize(ctx: ResponseContext) -> Dict[str, Any]:
    return {
        "response_context": ctx,
        "unavailable_items": None,
        "ambiguous_items": None,
        "feedback": None,
    }
```

The 5 helper functions are private to this file. Each is < 30 LOC. The public surface is just `state_outcome_node`.

---

## 6. The new `response_node` (the rewriter)

### 6.1 Top-level dispatcher

```python
# src/agent_brain/agent/nodes/response_node.py
import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_ollama import ChatOllama

from src.agent_brain.agent.state import AgentState
from src.agent_brain.config import settings
from src.agent_brain.schemas import (
    ResponseContext, OrderResponseContext, SearchResponseContext,
    PaymentResponseContext, ChatResponseContext, RetryResponseContext,
)
from src.agent_brain.utils import trace_latency

logger = logging.getLogger(__name__)

_response_llm = ChatOllama(
    model=settings.RESPONSE_MODEL,
    temperature=0.1,
    num_ctx=settings.LLM_NUM_CTX,
    keep_alive=settings.llm_keep_alive,
)

WAITER_REWRITER_PROMPT = (
    "Bạn là phục vụ viên AI tại Ốc Quậy. Viết lại một đoạn ngắn bằng "
    "tiếng Việt lịch sự cho khách, dựa trên CONTEXT dưới đây.\n"
    "KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT.\n"
    "Dùng 'Dạ', 'ạ', xưng 'em', gọi khách là 'anh/chị'. 1-3 câu."
)

CHAT_REWRITER_PROMPT = (
    "Bạn là phục vụ viên AI tại Ốc Quậy. Khách vừa nói gì đó. Nhìn "
    "CONTEXT bên dưới rồi trả lời lịch sự bằng tiếng Việt.\n"
    "KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT.\n"
    "Nếu khách hỏi về giỏ hàng / đơn hàng → liệt kê món + tổng từ CONTEXT.\n"
    "Nếu khách tán gẫu / hỏi ngoài phạm vi → trả lời ngắn rồi hỏi lại cần hỗ trợ gì.\n"
    "Dùng 'Dạ', 'ạ', xưng 'em', gọi khách là 'anh/chị'. 1-3 câu."
)

_FALLBACK_REPLY = "Xin lỗi, em chưa rõ, anh/chị nói lại giúp em nhé ạ."


@trace_latency("Response Node", run_type="chain")
def response_node(state: AgentState) -> Dict[str, Any]:
    ctx = state.get("response_context")
    if ctx is None:
        return {"messages": [AIMessage(content=_FALLBACK_REPLY)],
                "response_context": None}

    reply = _rewrite(ctx)
    return {
        "messages": [AIMessage(content=reply)],
        "response_context": None,   # never leak to next turn
    }


def _rewrite(ctx: ResponseContext) -> str:
    if isinstance(ctx, OrderResponseContext):    return _rewrite_order(ctx)
    if isinstance(ctx, SearchResponseContext):   return _rewrite_search(ctx)
    if isinstance(ctx, PaymentResponseContext):  return _rewrite_payment(ctx)
    if isinstance(ctx, ChatResponseContext):     return _rewrite_chat(ctx)
    if isinstance(ctx, RetryResponseContext):    return _rewrite_retry(ctx)
    return _FALLBACK_REPLY
```

### 6.2 `_rewrite_order` (templates + 1 LLM branch)

```python
def _vnd(amount) -> str:
    return f"{int(amount):,}".replace(",", ".") + "₫"


def _rewrite_order(ctx: OrderResponseContext) -> str:
    # 1. Ambiguous items take precedence (must ask the customer)
    if ctx.ambiguous:
        return _format_ambiguity(ctx)

    # 2. Off-menu w/ suggestion → LLM apologizes and offers the alternative
    if ctx.off_menu and any(o.suggestion for o in ctx.off_menu):
        return _llm_paraphrase_order(ctx, WAITER_REWRITER_PROMPT)

    # 3. Off-menu without suggestion → pure template
    if ctx.off_menu and all(not o.suggestion for o in ctx.off_menu):
        return _format_off_menu(ctx)

    # 4. Tool error → apologize
    if ctx.outcome == "error":
        return _format_order_error(ctx)

    # 5. confirm_order success
    if ctx.tool == "confirm_order" and ctx.outcome == "success":
        return (f"Dạ, em đã xác nhận đơn hàng #{ctx.order_id} ạ. "
                f"Món đang được chuẩn bị, anh/chị chờ một chút nhé.")

    # 6. sync_cart success — happy path
    return _format_cart_echo(ctx)


def _format_ambiguity(ctx: OrderResponseContext) -> str:
    parts = []
    for a in ctx.ambiguous:
        cands = "\n".join(f"  - {c}" for c in a.candidates)
        parts.append(f"Dạ, món **{a.name}** bên em có nhiều loại ạ, anh/chị muốn chọn loại nào ạ?\n{cands}")
    if ctx.active_cart_for_render.items:  # see note below
        cart_text = _format_cart_lines(ctx)
        parts.insert(0, f"Dạ, giỏ hàng hiện có:\n{cart_text}")
    return "\n\n".join(parts)


def _format_off_menu(ctx: OrderResponseContext) -> str:
    names = ", ".join(o.name for o in ctx.off_menu)
    return f"Dạ, món {names} hiện không có trong thực đơn ạ. Anh/chị muốn chọn món khác không ạ?"


def _format_order_error(ctx: OrderResponseContext) -> str:
    return f"Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. {ctx.error_message or 'Anh/chị thử lại giúp em nhé ạ.'}"


def _format_cart_lines(ctx: OrderResponseContext) -> str:
    lines = []
    for item in ctx.cart:
        line = f"  - {item.name} ×{item.quantity}"
        if item.special_requests:
            line += f" (Ghi chú: {item.special_requests})"
        lines.append(line)
    return "\n".join(lines)


def _format_cart_echo(ctx: OrderResponseContext) -> str:
    cart = _format_cart_lines(ctx)
    suffix = "\nAnh/chị xác nhận đặt hàng chưa ạ?" if ctx.stage == "AWAITING_CONFIRMATION" else ""
    return f"Dạ, giỏ hàng của anh/chị hiện có:\n{cart}\nTổng tạm tính {_vnd(ctx.total_vnd_numeric)}.{suffix}"
```

> Note: `ctx.active_cart_for_render` and `ctx.total_vnd_numeric` are tiny convenience accessors derived from `ctx.cart` / `ctx.total_vnd` (parse the string back to int). Add them as `@property` on `OrderResponseContext` in `schemas/response_context.py` if you want; or just keep the parsing inline.

### 6.3 `_rewrite_search` (LLM with compact text)

```python
def _rewrite_search(ctx: SearchResponseContext) -> str:
    if ctx.outcome == "error":
        return "Dạ, em chưa tìm thấy món phù hợp ạ. Anh/chị thử từ khóa khác nhé ạ."
    if not ctx.results:
        return "Dạ, em chưa tìm thấy món phù hợp ạ. Anh/chị muốn em gợi ý món khác không ạ?"

    # LLM-driven: project results to a compact text, ask LLM to paraphrase
    return _llm_paraphrase_search(ctx)


def _llm_paraphrase_search(ctx: SearchResponseContext) -> str:
    lines = [f"- {r.document.metadata.get('name', 'Unknown')} — "
             f"{_vnd(r.document.metadata.get('price', 0))}"
             for r in ctx.results]
    context_text = (
        f"Khách tìm: '{ctx.query}'\n"
        f"Kết quả ({len(ctx.results)} món):\n" + "\n".join(lines)
    )
    response = _response_llm.invoke([
        SystemMessage(content=WAITER_REWRITER_PROMPT),
        SystemMessage(content=f"CONTEXT:\n{context_text}"),
    ])
    return response.content
```

### 6.4 `_rewrite_payment` (templates)

```python
def _rewrite_payment(ctx: PaymentResponseContext) -> str:
    if ctx.tool == "request_payment":
        if ctx.outcome == "error" or not ctx.amount_vnd:
            return "Dạ, hiện chưa có đơn hàng nào trong phiên này ạ."
        return (f"Dạ, tổng hóa đơn của anh/chị là {ctx.amount_vnd}₫ ạ. "
                f"Anh/chị vui lòng quét mã QR để thanh toán nhé.")
    # verify_payment
    if ctx.outcome == "success":
        return "Dạ, em đã xác nhận thanh toán thành công. Cảm ơn anh/chị đã dùng bữa tại Ốc Quậy ạ!"
    return f"Dạ, chưa xác nhận được thanh toán. {ctx.error_message or 'Anh/chị thử lại giúp em nhé ạ.'}"
```

### 6.5 `_rewrite_chat` (12 LOC, LLM-driven for non-trivial)

```python
def _is_greeting(msg: str) -> bool:
    m = msg.lower().strip()
    return (m in {"chào", "chào bạn", "chào em", "xin chào", "hello", "hi"}
            or m.startswith(("chào", "xin chào", "hello", "hi")))


def _is_thanks(msg: str) -> bool:
    m = msg.lower().strip()
    return any(t in m for t in ("cảm ơn", "cám ơn", "thank", "tks", "thanks"))


def _normalize(msg: str) -> str:
    return (msg or "").lower().strip()


def _rewrite_chat(ctx: ChatResponseContext) -> str:
    msg = _normalize(ctx.user_message)

    if _is_greeting(msg):
        return "Dạ, em chào anh/chị ạ. Em có thể giúp gì cho anh/chị ạ?"

    if _is_thanks(msg):
        return "Dạ, không có gì ạ. Anh/chị cần em hỗ trợ gì thêm không ạ?"

    # Status questions, small talk, out of scope — LLM with the cart
    # in context produces the right reply.
    return _llm_paraphrase_chat(ctx)


def _llm_paraphrase_chat(ctx: ChatResponseContext) -> str:
    cart = ctx.active_cart
    cart_text = "trống"
    if cart and cart.items:
        cart_lines = [f"{i.name} ×{i.quantity}" for i in cart.items]
        cart_text = ", ".join(cart_lines) + f" (tổng {_vnd(cart.total_price)})"
    context_text = (
        f"Giỏ hàng hiện tại: {cart_text}\n"
        f"Trạng thái đơn: {ctx.order_stage}\n"
        f"Khách vừa nói: \"{ctx.user_message}\""
    )
    response = _response_llm.invoke([
        SystemMessage(content=CHAT_REWRITER_PROMPT),
        SystemMessage(content=f"CONTEXT:\n{context_text}"),
    ])
    return response.content
```

### 6.6 `_rewrite_retry` (template)

```python
def _rewrite_retry(ctx: RetryResponseContext) -> str:
    return f"Dạ, em xin lỗi anh/chị, {ctx.feedback} Anh/chị kiểm tra lại giúp em nhé ạ."
```

---

## 7. Phase 2 (món gần giống) details

In `src/agent_brain/utils/menu_utils.py`:

```python
def find_nearest_menu_name(name: str) -> Optional[str]:
    """Token-Jaccard nearest match. Returns the menu name with the
    highest token overlap (if > 0.3), else None."""
    if not name or not MENU_NAMES:
        return None
    target = set(_normalize(name).split())
    best, best_score = None, 0.0
    for menu_name in MENU_NAMES:
        menu_tokens = set(_normalize(menu_name).split())
        if not menu_tokens:
            continue
        overlap = len(target & menu_tokens) / len(target | menu_tokens)
        if overlap > best_score:
            best, best_score = menu_name, overlap
    return best if best_score > 0.3 else None
```

In `src/agent_brain/agent/nodes/deterministic_validator_node.py`, in the existing `else: unavailable_items.append(...)` branch (line ~91):

```python
# Before
unavailable_items.append({"name": name, "suggestion": None})

# After
unavailable_items.append({
    "name": name,
    "suggestion": find_nearest_menu_name(name),  # may be None
})
```

---

## 8. The slim `waiter_agent.md` (Phase 4)

```markdown
# Role
Bạn là phục vụ viên AI tại Ốc Quậy. Nhiệm vụ: viết lại đoạn ngắn bằng
tiếng Việt lịch sự cho khách dựa trên CONTEXT hệ thống cung cấp.

KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT.
Dùng "Dạ", "ạ", xưng "em", gọi khách là "anh/chị". 1-3 câu. Không kể lể.

# Chat rewriter (when context is ChatResponseContext)
- Nếu khách hỏi về giỏ hàng / đơn hàng → liệt kê món + tổng từ CONTEXT
- Nếu khách tán gẫu / hỏi ngoài phạm vi → trả lời ngắn rồi hỏi lại
```

The 2 LLM branches (`_llm_paraphrase_search`, `_llm_paraphrase_chat`) read the prompt at module level (already shown in §6). The prompt file is the human-readable mirror; the in-code constant is what the code actually uses. Keep them in sync.

---

## 9. The phased plan

Each phase is **one local commit**, ends with a green checkpoint. Run `make agent` (or the standalone smoke `tests/scripts/run_conversation_demo.py`) after each phase to verify the graph still loads and runs.

### Phase 0 — Pre-flight (~5 min)

```bash
make kill                                          # stop all dev servers
git status                                         # clean tree
git commit --allow-empty -m "chore: snapshot pre-response-refactor"
```

✅ Clean tree + snapshot commit.

---

### Phase 1 — Add schema + state slot + chat_worker + state_outcome (no behavior change)

**Files**: 3 new, 3 modified. ~250 LOC net.

- [ ] **1.1** Create `src/agent_brain/schemas/response_context.py` with the 5 context classes + the `ResponseContext` union (copy §3)
- [ ] **1.2** Update `src/agent_brain/schemas/__init__.py` to re-export the 6 new names
- [ ] **1.3** Add `response_context: Optional[ResponseContext]` to `AgentState` in `src/agent_brain/agent/state.py`
- [ ] **1.4** Create `src/agent_brain/agent/nodes/state_outcome_node.py` (copy §5.2)
- [ ] **1.5** Create `src/agent_brain/agent/nodes/chat_worker_node.py` (copy §5.1)
- [ ] **1.6** Update `src/agent_brain/agent/nodes/__init__.py` to export `state_outcome_node` and `chat_worker_node`
- [ ] **1.7** In `src/agent_brain/agent/graph.py`: register both new nodes, add the 3 new edges, change CHAT's intent target (copy §4.3). **DO NOT** remove the existing response_node logic yet — the legacy path still runs in parallel.
- [ ] **1.8** Add `tests/test_state_outcome.py` (one test per turn type, see §10)
- [ ] **1.9** Add `tests/test_chat_worker.py` (3-4 tests, see §10)
- [ ] **1.10** `git commit -m "feat(agent_brain): add response_context schema + state_outcome + chat_worker (phase 1)"`

**Smoke test**:
```bash
uv run python -c "from src.agent_brain.agent.graph import AIWaiterGraph; g = AIWaiterGraph(); print('graph ok')"
uv run python tests/scripts/run_conversation_demo.py
```

✅ Graph loads, smoke runs all 8 turns. The new context is inspectable via `app.get_state()` for debugging.

---

### Phase 2 — Wire `món gần giống` suggestions (~30 min)

**Files**: 1 modified, 1 new. ~25 LOC.

- [ ] **2.1** Add `find_nearest_menu_name()` to `src/agent_brain/utils/menu_utils.py` (copy §7)
- [ ] **2.2** In `src/agent_brain/agent/nodes/deterministic_validator_node.py`, populate `OffMenuItem.suggestion` (copy §7)
- [ ] **2.3** Add `tests/test_menu_suggestions.py` (5-6 tests for known inputs)
- [ ] **2.4** `git commit -m "feat(agent_brain): wire món gần giống suggestions in validator (phase 2)"`

**Smoke test**:
```bash
uv run python evals/scripts/eval_out_of_menu.py   # the suggestion shows up in the response
```

✅ Off-menu items carry a suggestion when one exists.

---

### Phase 3 — Port the deterministic cases (~1-2 hours)

**Files**: 1 modified (response_node.py). ~250 LOC added, ~50 LOC removed.

- [ ] **3.1** Replace the body of `response_node.py` with the dispatcher (§6.1) + `_rewrite_order` (§6.2) + `_rewrite_payment` (§6.4) + `_rewrite_retry` (§6.6) + `_rewrite_chat` (§6.5, with `_is_greeting` / `_is_thanks` and the LLM call commented out for now — Phase 4 adds it)
- [ ] **3.2** Keep the legacy `_build_response_context` and the old `response_node` body commented at the bottom of the file as a "reference" — we'll delete it in Phase 5
- [ ] **3.3** In `_rewrite_order`, port the existing `_build_ambiguity_response` (response_node.py:92-121) into `_format_ambiguity`
- [ ] **3.4** Add `_vnd()` helper (§6.2) and a `@property` on `OrderResponseContext` to parse `total_vnd` back to int for re-rendering if needed
- [ ] **3.5** Add `tests/test_rewriter.py` with the 8-10 templated cases (see §10)
- [ ] **3.6** `git commit -m "refactor(agent_brain): port deterministic cases to response_context rewriter (phase 3)"`

**Smoke test**:
```bash
uv run python evals/scripts/eval_e2e.py
uv run python evals/scripts/eval_out_of_menu.py
```

✅ All templated cases produce the right reply. The 2 chat templates (greeting, thanks) work. Cart echoes / confirmations / payments come from `_rewrite_*` instead of `_build_response_context`.

---

### Phase 4 — Port the LLM-driven cases (~1-2 hours)

**Files**: 1 modified (response_node.py + waiter_agent.md). ~30 LOC delta.

- [ ] **4.1** Uncomment / implement `_llm_paraphrase_search` (§6.3)
- [ ] **4.2** Uncomment / implement `_llm_paraphrase_chat` (§6.5) — this is the line that makes "nảy giờ mình gọi món gì rồi nhỉ?" work
- [ ] **4.3** Uncomment / implement `_llm_paraphrase_order` for the off-menu w/ suggestion case (§6.2)
- [ ] **4.4** Slim `waiter_agent.md` to the ~25-line version (§8). The in-code `_response_llm` + `WAITER_REWRITER_PROMPT` is what the code actually uses; the file is the human-readable mirror.
- [ ] **4.5** Update `tests/test_rewriter.py` to mock the LLM call and assert the prompt sent to the LLM contains the cart + user_message (for chat) or the search results (for search)
- [ ] **4.6** `git commit -m "refactor(agent_brain): port LLM cases to response_context rewriter (phase 4)"`

**Smoke test**:
```bash
uv run python tests/scripts/run_conversation_demo.py
# Manually verify the "Bạn có những món gì?" reply is paraphrased
# (not a 100% template dump)
```

✅ All 4 LLM cases work. The legacy `_build_response_context` is no longer called (but still in the file for reference).

---

### Phase 5 — Clean up (~30 min)

**Files**: 4 modified. ~50 LOC removed.

- [ ] **5.1** Delete the commented-out legacy `response_node` body and the old `_build_response_context` from `response_node.py`
- [ ] **5.2** Remove `unavailable_items` and `ambiguous_items` from `AgentState` in `src/agent_brain/agent/state.py`
- [ ] **5.3** Remove the `feedback` field from `AgentState`
- [ ] **5.4** Update `state_updater` (`src/agent_brain/agent/nodes/update_state_node.py`) to drop reads of the removed fields (they're no longer in state)
- [ ] **5.5** Run all evals, assert pass rate is unchanged or better
- [ ] **5.6** `git commit -m "chore(agent_brain): drop dead state fields after response rewriter (phase 5)"`

✅ `AgentState` is minimal. The graph runs end-to-end with the new architecture.

---

## 10. Tests to write

### 10.1 `tests/test_state_outcome.py` (~150 LOC, 8 tests)

| Test | What it asserts |
|---|---|
| `test_sync_cart_success_builds_order_context` | `messages[-1]` is a `ToolMessage(name="sync_cart")` with success artifact → `OrderResponseContext(tool="sync_cart", outcome="success", cart=[...])` |
| `test_confirm_order_success_includes_order_id` | `ToolMessage(name="confirm_order")` with `order_id=42` → `OrderResponseContext(tool="confirm_order", order_id=42, stage="CONFIRMED")` |
| `test_search_with_results` | `ToolMessage(name="search")` with 3 results → `SearchResponseContext(query=..., results=[3 items])` |
| `test_request_payment_success` | `ToolMessage(name="request_payment")` with amount + qr_url → `PaymentResponseContext(amount_vnd=..., qr_url=...)` |
| `test_verify_payment_success` | `ToolMessage(name="verify_payment")` → `PaymentResponseContext(tool="verify_payment", outcome="success")` |
| `test_off_menu_items_carry_suggestion` | `unavailable_items=[{"name": "Bia Corona", "suggestion": "Bia Sài Gòn"}]` in state → `OrderResponseContext.off_menu` has the suggestion |
| `test_ambiguous_items_preserved` | `ambiguous_items=[{"name": "Ốc Hương", "candidates": [...]}]` in state → `OrderResponseContext.ambiguous` has the items |
| `test_per_turn_fields_cleared` | The returned dict sets `unavailable_items=None`, `ambiguous_items=None`, `feedback=None` |
| `test_chat_path_is_no_op` | If `state["response_context"]` is already set (chat_worker ran), `state_outcome` just finalizes without rebuilding |

### 10.2 `tests/test_chat_worker.py` (~60 LOC, 4 tests)

| Test | What it asserts |
|---|---|
| `test_empty_cart_chat_context` | `state["active_cart"]=None` → `ChatResponseContext(active_cart=Cart())` (default empty) |
| `test_cart_with_items` | `state["active_cart"]=Cart(items=[2 items], total=340000)` → context carries it |
| `test_stage_propagation` | `state["order_stage"]="AWAITING_CONFIRMATION"` → context carries it |
| `test_user_message_extracted` | `messages[-1]=HumanMessage("chào bạn")` → `context.user_message="chào bạn"` |

### 10.3 `tests/test_rewriter.py` (~250 LOC, 14+ tests)

**Templated cases (no LLM):**

| Test | Input | Asserts |
|---|---|---|
| `test_rewrite_order_sync_cart_happy` | `OrderResponseContext(tool="sync_cart", outcome="success", cart=[Ốc Hương×2, Bia×3], total_vnd="340.000")` | Reply lists items + "Tổng tạm tính 340.000₫" + "xác nhận đặt hàng chưa" |
| `test_rewrite_order_sync_cart_empty_cart` | `OrderResponseContext(cart=[], total_vnd="0")` | Reply says "giỏ hàng trống" |
| `test_rewrite_order_confirm_success` | `OrderResponseContext(tool="confirm_order", outcome="success", order_id=42)` | Reply says "đã xác nhận đơn hàng #42" |
| `test_rewrite_order_off_menu_no_suggestion` | `OrderResponseContext(off_menu=[OffMenuItem("Bia Corona")])` | Reply says "không có trong thực đơn" |
| `test_rewrite_order_ambiguous` | `OrderResponseContext(ambiguous=[AmbiguousItem("Ốc Hương", candidates=[...])])` | Reply lists candidates + asks "anh/chị muốn chọn loại nào" |
| `test_rewrite_search_no_results` | `SearchResponseContext(results=[])` | Reply says "chưa tìm thấy món phù hợp" |
| `test_rewrite_payment_request_success` | `PaymentResponseContext(tool="request_payment", amount_vnd="450.000", qr_url="...")` | Reply mentions "450.000₫" + "quét mã QR" |
| `test_rewrite_payment_verify_success` | `PaymentResponseContext(tool="verify_payment", outcome="success")` | Reply says "thanh toán thành công" |
| `test_rewrite_chat_greeting` | `ChatResponseContext(user_message="chào bạn")` | Reply is the greeting template (no LLM call) |
| `test_rewrite_chat_thanks` | `ChatResponseContext(user_message="cảm ơn nhiều")` | Reply is the thanks template (no LLM call) |
| `test_rewrite_retry` | `RetryResponseContext(feedback="tên món sai")` | Reply is the polite retry template |

**LLM-driven cases (mock the LLM):**

| Test | Input | Asserts |
|---|---|---|
| `test_rewrite_chat_status_question_calls_llm_with_cart` | `ChatResponseContext(active_cart=Cart([2 items]), user_message="nảy giờ mình gọi món gì rồi?")` | LLM is called; the prompt sent to LLM contains the cart items, the total, the order_stage, and the user message |
| `test_rewrite_search_with_results_calls_llm` | `SearchResponseContext(query="món chay", results=[3 SearchResults])` | LLM is called; the prompt contains the query and the results |
| `test_rewrite_order_off_menu_with_suggestion_calls_llm` | `OrderResponseContext(off_menu=[OffMenuItem("Bia Corona", suggestion="Bia Sài Gòn")])` | LLM is called; the prompt mentions the suggestion |

The LLM mocking pattern: replace `src.agent_brain.agent.nodes.response_node._response_llm` with a `unittest.mock.Mock` that returns a `MagicMock(content="...")`. Assert on `mock.invoke.call_args` to verify the prompt is well-shaped.

---

## 11. Risks / things to double-check

These are the things that **could go wrong** during implementation. Check them at each phase's checkpoint.

1. **State leakage**: `state_outcome` must set `unavailable_items=None` etc. on the dict it returns, OR the `state_updater` already nulls them. Check `update_state_node.py` to see if it already nulls them on every turn; if not, the `state_outcome` `_finalize` is the only safety net. **Test this** in Phase 1.

2. **The LLM in `_llm_paraphrase_chat` may not produce a "what did I order" reply for the edge case where `active_cart` is empty but the user asks "nảy giờ mình gọi món gì rồi nhỉ?"** — the LLM should say "anh/chị chưa gọi món nào ạ". This is a prompt-engineering question. Test it manually in Phase 4; tighten the prompt if needed.

3. **The `total_vnd` field is a string** (e.g. `"170.000"`) but the legacy `active_cart.total_price` is a float. Converting between them in the templates is a source of bugs. Pick one direction: store the float on the context and format in the template (cleaner), or store the pre-formatted string and parse when needed. I chose string; `_vnd()` formats, `_format_cart_echo` consumes. Add a `@property` for `total_vnd_numeric` if needed.

4. **`update_state_node` currently reads `unavailable_items` from state to determine `ui_action`**. If we remove the field in Phase 5, that read breaks. Check the `update_state_node.py` logic before Phase 5 and migrate the read to read from the new `ResponseContext` (which is the source of truth after Phase 1).

5. **The `chat_worker` is a 10-LOC node, but it's still a graph node** — it has to be exported, registered, and wired in `graph.py`. The edge change is trivial but easy to forget. Check `graph.py` carefully in Phase 1.7.

6. **The `validator` mutates `state["unavailable_items"]` and `state["ambiguous_items"]` in place.** These writes happen DURING the validator node, BEFORE `state_outcome` runs. By the time `state_outcome` reads them, they're populated correctly. But: if a turn has a retry loop (validator → worker → validator), the second validator run may overwrite the first. Make sure the validator is idempotent (overwrites, not appends) — or check the current logic to see if it already is.

7. **The `_llm_paraphrase_*` functions call `_response_llm` which is loaded at module import.** If the LLM isn't warmed up yet, the first chat turn could be slow. The current `server.py` has a `_warmup` that pings all models at startup — verify it still works after the refactor.

---

## 12. Out of scope

- Switching to a larger LLM.
- Adding new tools.
- Changing the router, workers' prompts, or validator logic (except the `OffMenuItem.suggestion` change in Phase 2).
- Few-shots for the rewriter.
- Response-quality scoring in the eval suite.
- The orchestrator backend, edge voice device, frontends, ROS 2 workspace, hybrid RAG retriever.
- `git push` to remote.

---

## 13. What we explicitly rejected (and why)

| Option | Rejected because |
|---|---|
| Add `get_cart` / `get_session_status` tools | Forces router to be more precise; worker prompt must distinguish "ask" from "act"; requires retraining router centroids. Same outcome achievable by carrying state in the context (Option A). |
| Self-looping workers (worker = mini-agent = tool + verbalize) | Conflates implement and response stages. Multi-intent turns produce multiple customer replies. +1 LLM call per worker. Evals need a rewrite. |
| Hardcoded `_STATUS_PATTERNS` tuple (15 Vietnamese substrings) | Brittle, false-positive on similar text ("tôi không muốn gọi món nữa" matches "gọi món"), false-negative on novel phrasings, maintenance burden. The LLM with the cart in context handles status questions naturally. |
| All replies are deterministic templates (no LLM in response_node) | Search paraphrase, off-menu apology, and free-form chat genuinely benefit from LLM naturalness. The ~70/30 split is the right call. |
| Per-tool static prompt files (5+ files) | More files to maintain, drift risk. The single slim `waiter_agent.md` + in-code prompt constants work. |
| Router's inline helper building `ChatResponseContext` | Breaks the "every intent has a worker" symmetry. Replaced by `chat_worker` node. |
