## 4.3.6 Stage V — Response: Output Generation

> **Status:** draft
> **Cross-refs:** §4.3.5 for state outcome, §5.4.5 for response quality evaluation
> **Source:** `src/agent_brain/agent/nodes/response_node.py` (337 lines), `response_template.py`
> **Figures needed:** Table 4.1 (Response Generation Decision Table — template vs LLM dispatch matrix)

---

The final stage converts the typed `ResponseContext` into spoken Vietnamese. Every utterance follows a guaranteed path: the `state_outcome` always produces a `ResponseContext`, and the `response_node` always produces an `AIMessage` — the customer always hears something, regardless of whether the turn succeeded, failed validation, or triggered the circuit breaker.

### 4.3.6.1 Typed ResponseContext Dispatch

The `ResponseContext` is a discriminated union of five subtypes, each carrying structured data specific to the tool that executed:

| Subtype | Produced By | Carries |
|---------|-------------|---------|
| `OrderResponseContext` | `state_outcome` after cart tools | Cart state, total, off-menu items, ambiguous items, order ID, status |
| `SearchResponseContext` | `state_outcome` after search tool | Query text, ranked results with metadata (name, price, category) |
| `PaymentResponseContext` | `state_outcome` after payment tools | Amount in VND, QR URL, table ID, status |
| `ChatResponseContext` | `chat_worker` | User message, cart, order stage, conversation history, curated memory, delegate reason |
| `RetryResponseContext` | `state_outcome` on circuit breaker | Failed tool name, feedback string |

The `response_node` (`response_node.py:328`) reads `state["response_context"]`, dispatches to a type-specific rewriter function, and writes the resulting text as an `AIMessage` appended to `messages`.

### 4.3.6.2 Template-Based Responses (Deterministic)

Template responses are pre-written Vietnamese strings assembled with Python string formatting. They are used for deterministic outcomes — situations where the content is formula-driven and the phrasing should be predictable:

| Situation | Template Function | Example Output |
|-----------|------------------|----------------|
| Order confirmation | `_format_confirm_reply(order_id)` | "Dạ, đơn hàng #42 của anh/chị đã được gửi đến bếp ạ. Món sẽ được làm ngay!" |
| Cart echo | `_format_cart_echo(ctx)` | "Dạ, giỏ hàng của anh/chị có: Ốc Hương Xốt Trứng Muối ×2 — 340k, Lẩu Thái ×1 — 250k. Tổng 590k. Anh/chị xác nhận đặt món ạ?" |
| Ambiguity clarification | `_format_ambiguity(ctx)` | "Dạ, Ốc Hương có nhiều loại sốt: trứng muối, me, tỏi, bơ... anh/chị muốn loại nào ạ?" |
| Off-menu rejection | `_format_off_menu(ctx)` | "Dạ, món 'Cơm Tấm' không có trong thực đơn. Món gần giống nhất là Cơm Chiên (150k). Anh/chị muốn thử không ạ?" |
| Remove confirmation | `_format_remove_reply(ctx)` | "Dạ, em đã bỏ Ốc Hương khỏi giỏ hàng ạ." |
| Clear confirmation | `_format_clear_reply()` | "Dạ, em đã xóa giỏ hàng ạ." |
| Order error | `_format_order_error(ctx)` | "Dạ, em xin lỗi, có lỗi khi thêm món: [error message]. Anh/chị thử lại giúp em nhé ạ." |
| Payment prompt | Inline in `_rewrite_payment` | "Dạ, tổng hóa đơn của anh/chị là {amount}₫. Anh/chị vui lòng quét mã QR để thanh toán nhé." |
| Payment success | Inline in `_rewrite_payment` | "Dạ, em đã xác nhận thanh toán thành công. Cảm ơn anh/chị đã dùng bữa tại Ốc Quậy ạ!" |
| Greeting | `_format_greeting()` | "Dạ, em chào anh/chị ạ. Anh/chị muốn gọi món gì ạ?" |
| Thanks | `_format_thanks()` | "Dạ, không có gì ạ. Anh/chị cần gì thêm không ạ?" |
| Circuit breaker apology | `_rewrite_retry(ctx)` | "Dạ, em xin lỗi anh/chị, [feedback]. Anh/chị kiểm tra lại giúp em nhé ạ." |

**Design rationale for templates.** Template responses are:
- **Fast:** No LLM inference — assembly takes microseconds.
- **Correct:** Prices are computed deterministically from cart state, not hallucinated. Quantity math is Python arithmetic, not LLM generation.
- **Consistent:** The same situation produces the same phrasing every time, making the system's behavior predictable for the customer.
- **Natural Vietnamese:** Templates are hand-written by a Vietnamese speaker, not translated from English. They use natural waiter vocabulary ("Dạ," "ạ," "anh/chị," "quán mình") and appropriate politeness levels.

### 4.3.6.3 LLM-Based Responses

Three situations require LLM generation because the content is too variable for templates:

| Situation | System Prompt | Context | Output Style |
|-----------|--------------|---------|-------------|
| Search results | `response_rewriter.md` (waiter persona) | Ranked dish list with names, prices, categories | Conversational listing: "Dạ, quán mình có các món nước ấm: Lẩu Thái (250k) — cay, chua; Lẩu Hải Sản (300k) — ngọt, thanh. Anh/chị muốn thử món nào ạ?" |
| Off-menu with suggestions | `response_rewriter.md` | Off-menu items + nearest-match suggestions | Natural suggestion: "Dạ, món 'Cơm Tấm' không có, nhưng quán mình có Cơm Chiên (150k) và Cơm Rang (140k) cũng rất ngon ạ. Anh/chị muốn thử món nào?" |
| Free-form chat | `chat_rewriter.md` | Full conversation history, cart, curated memory, delegate reason | Open-ended conversational response grounded in restaurant context |

**LLM configuration.** The response LLM uses Qwen2.5 7B with `temperature=0.3` — higher than the router (0.0) and workers (0.1) because response generation benefits from varied phrasing. The same model instance is reused across all three LLM paths with different system prompts.

**Context format.** Before being sent to the LLM, structured data is serialized into a formatted text block (e.g., `_format_search_for_llm` produces "Khách tìm: 'món nước ấm'\nKết quả (3 món):\n- Lẩu Thái — 250.000₫/phần\n- Lẩu Hải Sản — 300.000₫/phần\n..."). The LLM receives this text as a `CONTEXT` system message and paraphrases it into conversational Vietnamese. This design means the LLM never hallucinates dish names or prices — it only reformats verified data into natural language.

### 4.3.6.4 Response Selection Heuristics

Within some context types, the `response_node` applies heuristics to select between template and LLM paths:

**Order responses** (`_rewrite_order`, `response_node.py:212-241`):
1. If `ambiguous` items exist → template (clarification request)
2. If `off_menu` items have suggestions → LLM (natural paraphrasing of alternatives)
3. If `off_menu` items have no suggestions → template (clean rejection)
4. If `status == "error"` → template (error message)
5. If `tool == "confirm_order"` and success → template (order confirmation)
6. If `tool == "remove_cart"` and success → template (removal confirmation)
7. If `tool == "clear_cart"` and success → template (clear confirmation)
8. Otherwise (add_cart success) → template (cart echo with per-item prices and total)

**Chat responses** (`_rewrite_chat`, `response_node.py:275-302`):
1. If delegate reason is "xem lại" (review cart) → template (cart echo)
2. If delegate reason is "không rõ" (unclear) → template (clarification request)
3. If message is a greeting → template (greeting)
4. If message is thanks → template (thanks acknowledgment)
5. Otherwise → LLM (free-form conversation)

This hybrid approach — templates for formula-driven outputs, LLM for variable content — maximizes speed and correctness while maintaining conversational flexibility where needed.

### 4.3.6.5 Streaming Architecture

The response generator supports Server-Sent Events (SSE) streaming, bridging the synchronous LangGraph graph to async FastAPI endpoints (`response_node.py:84-85`).

**Sentence splitting.** LLM-generated text is streamed token-by-token from Ollama and split into sentences at punctuation boundaries (`[.!?]\s`). Each complete sentence is emitted as an SSE event immediately, without waiting for the full response. This enables the TTS engine on the Jetson to begin playback of the first sentence while the LLM is still generating subsequent sentences.

**Stream context.** A module-level `_StreamContext` singleton (`response_node.py:56-81`) holds a `Queue` that is set before graph invocation and cleared after. The `_stream.emit()` method pushes `("sentence", text)` tuples onto the queue. An async generator on the FastAPI side consumes this queue and yields SSE events. When no queue is set (non-streaming `/chat` endpoint), `emit()` is a no-op — the same response node works for both streaming and blocking modes.

**Template streaming.** Template responses are emitted as a single sentence (the full template text). LLM responses are streamed sentence-by-sentence. The `was_streamed` flag (`response_node.py:77`) tracks whether any content was emitted — if the response node produces a reply but nothing was streamed (e.g., an empty context edge case), a fallback reply is emitted.

**SSE and TTS alignment.** The SSE sentence stream is delivered to the Jetson's voice pipeline, where the TTS engine plays sentences sequentially. Meanwhile, the customer's tablet receives the same SSE stream for the voice mirror display. The "done" event at the end of the SSE stream carries the full response text, UI action, and cart state — the tablet uses this to update its UI after the last sentence plays.
