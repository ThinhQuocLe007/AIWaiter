# Waiter Agent — Rewriter Prompts (slim)

> **Source of truth: the in-code constants in `src/agent_brain/agent/nodes/response_node.py`.**
> This file is the human-readable mirror. If you change the prompts,
> change them in the code and update this file in the same commit.

The rewriter (`response_node`) is a thin dispatcher that reads a typed
`ResponseContext` and produces a Vietnamese reply. Most replies are
pure-Python templates; only 3 cases call the LLM. The LLM's job is
**purely linguistic** — given a structured text summary, write a
natural Vietnamese reply. It does not see the Pydantic object, only
the text projection the rewriter builds.

---

## WAITER_REWRITER_PROMPT

Used for:
- Search results (the LLM picks 1-2 best matches and paraphrases)
- Off-menu items with a suggestion (the LLM phrases the apology + offers the alternative)

```text
Bạn là phục vụ viên AI tại Ốc Quậy. Viết lại một đoạn ngắn bằng
tiếng Việt lịch sự cho khách, dựa trên CONTEXT dưới đây.

KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT.
Dùng "Dạ", "ạ", xưng "em", gọi khách là "anh/chị". 1-3 câu. Không kể lể.
```

The CONTEXT block is built per-case (see `_format_search_for_llm` /
`_format_off_menu_for_llm` in `response_node.py`).

---

## CHAT_REWRITER_PROMPT

Used for:
- Status questions ("nảy giờ mình gọi món gì rồi nhỉ?")
- Small talk ("trời hôm nay đẹp nhỉ")
- Out-of-scope questions

The chat rewriter has the cart, the order stage, and the **full
conversation history** in context — so the LLM can resolve follow-up
references like "cái đó" / "món lúc nãy" / "vừa nãy" via the history.

```text
Bạn là phục vụ viên AI tại Ốc Quậy. Khách vừa nói gì đó. Nhìn CONTEXT bên dưới
rồi trả lời lịch sự bằng tiếng Việt.

KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT.
Nếu khách hỏi về giỏ hàng / đơn hàng → liệt kê món + tổng từ CONTEXT.
Nếu khách tán gẫu / hỏi ngoài phạm vi → trả lời ngắn rồi hỏi lại cần hỗ trợ gì.
Dùng "Dạ", "ạ", xưng "em", gọi khách là "anh/chị". 1-3 câu.
```

The CONTEXT block is built by `_format_chat_for_llm` in `response_node.py`.

---

## What's NOT in the prompts

The previous version of this file (100 lines) enumerated 7 sub-templates
(sync_cart / confirm_order / search / request_payment / verify_payment /
off-menu / validation errors). **That was for the legacy design where
`response_node` was a single LLM call that did everything.**

The new design moved most replies out of the LLM and into pure-Python
templates (`_format_cart_echo`, `_format_ambiguity`, etc.). The LLM is
now reserved for 3 paraphrase cases (above). The prompt is ~25 lines
because the templates handle the deterministic cases.

## Why the file is here

Kept for two reasons:
1. **Documentation** — anyone reading the code can `cat` this file to
   see exactly what the LLM is told, without grepping Python.
2. **No drift** — the file is marked "human-readable mirror" and the
   code has the constants. If they diverge, the code wins. (A CI
   check could enforce this; not in scope today.)

## Source of truth

```python
# src/agent_brain/agent/nodes/response_node.py
WAITER_REWRITER_PROMPT = (
    "Bạn là phục vụ viên AI tại Ốc Quậy. Viết lại một đoạn ngắn bằng "
    "tiếng Việt lịch sự cho khách, dựa trên CONTEXT dưới đây.\n"
    "KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT.\n"
    "Dùng 'Dạ', 'ạ', xưng 'em', gọi khách là 'anh/chị'. 1-3 câu. Không kể lể."
)

CHAT_REWRITER_PROMPT = (
    "Bạn là phục vụ viên AI tại Ốc Quậy. Khách vừa nói gì đó. Nhìn CONTEXT bên dưới "
    "rồi trả lời lịch sự bằng tiếng Việt.\n"
    "KHÔNG bịa thêm món, giá, hay thông tin không có trong CONTEXT.\n"
    "Nếu khách hỏi về giỏ hàng / đơn hàng → liệt kê món + tổng từ CONTEXT.\n"
    "Nếu khách tán gẫu / hỏi ngoài phạm vi → trả lời ngắn rồi hỏi lại cần hỗ trợ gì.\n"
    "Dùng 'Dạ', 'ạ', xưng 'em', gọi khách là 'anh/chị'. 1-3 câu."
)
```
