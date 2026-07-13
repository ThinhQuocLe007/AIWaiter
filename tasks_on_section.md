# Long Conversation Test — qwen2.5:7b + All Fixes + Forced Tool Call

Model: `qwen2.5:7b` | Embedding: `bkai-foundation-models/vietnamese-bi-encoder`
Report: `evals/results/long_conv_20260713_205635.json`

Fixes applied:
- `MIN_SIM_THRESHOLD = 0.55` — semantic router blocks weak fast-tracks
- `order_worker_agent.md` — rule #0: MUST call tool, never reply in text
- `_extract_modifier()` — strips parenthesized modifiers from dish names in validator
- `CHAT_REWRITER_PROMPT` — explicit "don't fabricate" for unanswerable questions
- `_force_tool_call_via_ollama()` — falls back to raw Ollama API with `tool_choice: "required"`

---

## Summary

| Metric | gemma4 | qwen2.5 (all fixes) | qwen2.5 (+ forced tool) |
|---|---|---|---|
| Avg latency | 7.42s | 3.30s | 5.44s |
| Cart accuracy | wrong | wrong (missing base item) | **correct (461.000₫)** |
| Turns with tools | 14/15 | 13/15 | **13/15** |
| Intent matches | 5/15 | 13/15 | **13/15** |
| Turn 5 tool call | no | no | **yes ✓** |
| confirm_order | 404 | Order #1 | **Order #1 ✓** |
| Modifier extraction | dropped | ✓ | ✓ |

---

## Conversation Transcript

[Human] Chào em, bàn mình có 2 người. Cho anh xem menu có gì hot hôm nay đi
[AI Waiter] Dạ, anh/chị có thể thử cá chim nướng sa tế - món best seller của nhà hàng ạ. Hoặc nếu thích ốc, em đề xuất ốc len xào dừa.

[Human] Hải sản ở đây có món gì ngon? Anh với vợ thích ốc với tôm, em gợi ý vài món đi
[AI Waiter] Dạ, anh/chị có muốn thử món ốc hương hấp hay tôm sú xào sao? Em sẽ tư vấn thêm nếu cần ạ.

[Human] Ốc Hương Xốt Trứng Muối ngon không em? Có cay không?
[AI Waiter] Dạ, có 3 lựa chọn Ốc Hương Xốt Trứng Muối: Ốc Hương 85.000₫, Ốc Mỡ 95.000₫, Ốc Cà Na 75.000₫. Em có thể đặt món cho anh/chị được không?

[Human] Tôm Càng Xanh Nướng Phô Mai phần ăn bao nhiêu con vậy em?
[AI Waiter] Dạ, anh/chị muốn gọi Tôm Càng Xanh Nướng Phô Mai với giá 120.000₫ nhé? Em có thể đặt món này ngay cho anh/chị ạ.

[Human] Cho anh 2 phần Ốc Hương Xốt Trứng Muối trước đi
[AI Waiter] Dạ, giỏ hàng của anh/chị hiện có:
  - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
Tổng tạm tính 170.000₫. Anh/chị xác nhận đặt hàng chưa ạ?

[Human] Vợ anh thích ăn hàu, cho thêm 3 con Hàu Nướng Phô Mai và 1 chai Bia Tiger Bạc
[AI Waiter] Dạ, giỏ hàng của anh/chị hiện có:
  - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
  - Hàu Nướng Phô Mai ×3 (39.000₫/phần)
  - Bia Tiger Bạc ×1 (22.000₫/phần)
Tổng tạm tính 309.000₫. Anh/chị xác nhận đặt hàng chưa ạ?

[Human] À quên, cho anh hỏi Ốc Hương Xốt Trứng Muối bao nhiêu 1 phần vậy?
[AI Waiter] Dạ, Ốc Hương Xốt Trứng Muối là 85.000₫/phần ạ. Anh/chị có muốn gọi thêm món gì không?

[Human] Thôi bỏ Bia Tiger Bạc đi, đổi qua 2 Bia Sài Gòn đi em. Bia Tiger nghe đắng quá
[AI Waiter] Dạ, giỏ hàng của anh/chị hiện có:
  - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
  - Hàu Nướng Phô Mai ×3 (39.000₫/phần)
  - Bia Sài Gòn ×2 (15.000₫/phần)
Tổng tạm tính 317.000₫. Anh/chị xác nhận đặt hàng chưa ạ?

[Human] Cho anh xem lại order đang có những gì đi em
[AI Waiter] Dạ, giỏ hàng của anh/chị hiện có:
  - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
  - Hàu Nướng Phô Mai ×3 (39.000₫/phần)
  - Bia Sài Gòn ×2 (15.000₫/phần)
Tổng tạm tính là 317.000₫ ạ. Anh/chị có muốn thay đổi gì nữa không?

[Human] Thêm 1 dĩa Khoai Tây Lắc Phô Mai cho vợ. Với cả có Dừa Tươi không em? Cho anh 1 trái
[AI Waiter] Dạ, món Dừa Tươi hiện không có trong thực đơn ạ. Anh/chị muốn chọn món khác không ạ?

[Human] Gỏi Xoài Ốc Giác có ngon không? Anh tính gọi thêm 1 phần mà sợ cay quá
[AI Waiter] Dạ, Gỏi Xoài Ốc Giác là một món khá mát và không cay nên anh/chị có thể yên tâm thử. Cho anh/chị thêm 1 phần Gỏi Xoài Ốc Giác nhé. Em sẽ cập nhật giỏ hàng ngay.

[Human] Thôi cho anh 1 phần Gỏi Xoài Ốc Giác luôn, ít cay nha em
[AI Waiter] Dạ, giỏ hàng của anh/chị hiện có:
  - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
  - Hàu Nướng Phô Mai ×3 (39.000₫/phần)
  - Bia Sài Gòn ×2 (15.000₫/phần)
  - Khoai Tây Lắc Phô Mai ×1 (49.000₫/phần)
  - Gỏi Xoài Ốc Giác ×1 (95.000₫/phần) (Ghi chú: ít cay)
Tổng tạm tính 461.000₫. Anh/chị xác nhận đặt hàng chưa ạ?

[Human] Xem lại đơn lần cuối rồi chốt luôn em ơi
[AI Waiter] Dạ, em đã xác nhận đơn hàng #1 ạ. Món đang được chuẩn bị, anh/chị chờ một chút nhé.

[Human] Tính tiền cho anh, quẹt thẻ được không em?
[AI Waiter] Dạ, tổng hóa đơn của anh/chị là 461.000₫ ạ. Anh/chị vui lòng quét mã QR để thanh toán nhé.

[Human] Anh chuyển khoản xong rồi đó, kiểm tra giúp anh
[AI Waiter] Dạ, tổng hóa đơn của anh/chị là 461.000₫ ạ. Anh/chị vui lòng quét mã QR để thanh toán nhé.

---

## Solutions Applied

### S1. MIN_SIM_THRESHOLD — semantic router blocks weak matches

File: `semantic_router_node.py`. Added `MIN_SIM_THRESHOLD = 0.55`. If the top centroid cosine similarity is below 0.55, skip SEMANTIC fast-track entirely and fall back to SLM. Cleans up Turns 4, 7, 10, 14 misroutes.

### S2. Modifier extraction — strips (parenthesized) modifiers from dish names

File: `deterministic_validator_node.py`. Added `_extract_modifier()` with patterns for `(modifier)`, `, modifier`, `- modifier`. When `resolve_menu_name()` fails, strips the modifier, retries the clean name, and sets `special_requests` from the extracted text.

Result: `"Gỏi Xoài Ốc Giác (ít cay)"` → `name="Gỏi Xoài Ốc Giác", special_requests="ít cay"`.

### S3. Forced tool_choice="required" via raw Ollama API

File: `order_worker_node.py`. ChatOllama ignores `tool_choice="any"` (confirmed by langchain_ollama docs). Added `_force_tool_call_via_ollama()` as a third-level fallback:
1. Try ChatOllama with `tool_choice="any"` (soft)
2. Retry with forced system prompt (medium)
3. Fall back to raw `POST /api/chat` with `tool_choice: "required"` (hard)

This forces qwen2.5:7b to call `add_cart` when it would otherwise respond in text. Cost: ~5s extra latency on the first ORDER turn (Turn 5 went from 5.16s to 11.28s, Turn 11 went to 28s due to multi-intent + retries).

## Remaining Problems

### P1. Turn 11 — high latency from forced tool fallback in multi-intent

**Latency**: 28.05s (vs 10.76s previously). The ORDER worker path in multi-intent `['SEARCH', 'ORDER']` triggers the full retry + raw API fallback chain. The forced `tool_choice="required"` call is slow because it requires a separate HTTP round-trip converting LangChain messages to Ollama format.

### P2. Turn 4 — search rewriter treats question as order

**Response**: "anh/chị muốn gọi Tôm Càng Xanh Nướng Phô Mai với giá 120.000₫ nhé?" The search rewriter phrases the single search result as a purchase suggestion instead of answering "bao nhiêu con?".

### P3. Turn 15 — verify_payment not called (demo design limitation)

Hardcoded `request_payment` in `payment_dispatch_node`. Not a bug — voice-based verify_payment was never implemented for the demo flow.
