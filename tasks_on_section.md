
# AI Waiter — Long Conversation Test Results

**Date**: 2026-07-18 23:13 (post-fixes)  
**Model**: qwen2.5:7b-instruct (router, worker, response)  
**Embedding**: bkai-foundation-models/vietnamese-bi-encoder  
**Backend**: DOWN (confirm/payment turns skipped)  
**Previous run**: 2026-07-18 22:40 (baseline)

---

## Fixes Applied Before This Run

| # | Fix | File | Status |
|---|-----|------|--------|
| 1 | Propagate `delegate_reason` + `curated_memory` in fallback ChatResponseContext | `state_outcome_node.py` | ✓ Applied |
| 2 | Flip validator: strip confirm_order, push ORDER_CONFIRM to intent queue | `deterministic_validator_node.py` | ✓ Applied |
| 3 | Wiped checkpoints DB before test run | `storage/db/checkpoints.db` | ✓ Applied |

---

## Scenario A — Couple Dinner (T1, 17 turns)

[Human] Chào em, bàn mình có 2 người. Cho anh xem menu có gì hot hôm nay đi
[AI Waiter] Dạ, anh/chị có muốn thử món cháo hải sản đặc sản của chúng em không? ✓ [1 search, 11.26s — cold start]

[Human] Hải sản ở đây có món gì ngon? Anh với vợ thích ốc với tôm, em gợi ý vài món đi
[AI Waiter] Dạ chị/chị ạ, em thấy Tôm Thẻ Cháy Tỏi rất ngon đấy, vừa giòn vừa thơm. ✓ [4.0s]

[Human] Ốc Hương Xốt Trứng Muối ngon không em? Có cay không? Mà bao nhiêu 1 phần?
[AI Waiter] Dạ chị/anh muốn thử ốc bulot xốt trứng muối ạ? Món này cũng rất ngon và đặc biệt... [CHINESE LEAK in response: "呢，这里我纠正了错误，并用正确的中文回复"]

[Human] Ừ nghe cũng được. Mà ngoài món đó ra Ốc Hương còn làm kiểu gì khác không em?
[AI Waiter] Dạ chị/anh, em xin推荐您尝试一下我们的蒜香蒸螺... [CHINESE LEAK — full Chinese paragraph]

[Human] Tôm Càng Xanh Nướng Phô Mai phần ăn bao nhiêu con? Có đủ 2 người ăn không?
[AI Waiter] Dạ chị/chị ơi, có món tôm càng xanh nướng phô mai với giá 120.000₫. ✓

[Human] Cho 2 phần Ốc Hương Xốt Trứng Muối với 1 Tôm Càng Xanh Nướng Phô Mai đi
[AI Waiter] Giỏ hàng: Ốc Hương ×2 (85k), Tôm Càng Xanh ×1 (120k) = 290.000₫. ✓ [CLEAN CART — no contamination from prior run]

[Human] À mà vợ anh thích hàu hơn tôm, bỏ Tôm Càng Xanh đi, cho anh 3 con Hàu Nướng Phô Mai thay
[AI Waiter] Giỏ hàng: Ốc Hương ×2, Hàu ×3 = 287.000₫. ✓ [correct substitution]

[Human] Với cho 1 Bia Tiger Bạc. Mà khoan, Tiger nghe đắng quá, có bia nào nhẹ hơn không em?
[AI Waiter] Giỏ hàng: Ốc Hương ×2, Hàu ×3, Bia Tiger ×1 = 309.000₫. [ORDER misroute, SEARCH lost, 18.75s]

[Human] Vậy lấy 2 Bia Sài Gòn đi. Cho anh hỏi thêm Ốc Móng Tay ở đây có những món gì?
[AI Waiter] Giỏ hàng: ... Bia Sài Gòn ×2 = 339.000₫. [add_cart only, SEARCH lost, 21.62s]

[Human] Cho thêm 1 dĩa Khoai Tây Lắc Phô Mai cho vợ. Có món chay nào nữa không em?
[AI Waiter] Giỏ hàng: ... Khoai Tây ×1 = 388.000₫. [add_cart only, SEARCH lost]

[Human] Gỏi Xoài Ốc Giác giá bao nhiêu? Rồi cho anh 1 phần luôn, lưu ý bớt cay nha
[AI Waiter] Dạ, Gỏi Xoài Ốc Giác (không cay) là 50.000₫/phần. Em đã thêm. [SEARCH misroute, item added anyway, 29.84s — SLOWEST]

[Human] Em ơi cho anh xem tổng đơn hiện tại đi
[AI Waiter] Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [PAYMENT misroute → request_payment]

[Human] Bỏ Bia Tiger Bạc đi — à mà anh đã bỏ rồi hả? Thôi xem lại đơn đi
[AI Waiter] Dạ, em đã bỏ món khỏi giỏ hàng ạ. Giỏ hàng: Ốc Hương ×2, Hàu ×3, Bia Sài Gòn ×2, Khoai Tây ×1 = 366.000₫. ✓

[Human] Lấy thêm 1 Sò Điệp Nướng Phô Mai với 2 Cháo Hàu đi. Giờ chốt đơn nha em
[AI Waiter] Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. Lỗi xử lý đơn hàng: Connection refused. [confirm_order ran but backend DOWN — **FLOW IS CORRECT NOW**. Cart tools executed, then ORDER_CONFIRM re-invoked, confirm called. Expected error since backend is down. 11.18s]

[Human] Ok xác nhận — [SKIPPED]
[Human] Tính tiền — [SKIPPED]
[Human] Chuyển khoản xong — [SKIPPED]

**Summary**: 14 turns, 14 tools, 0 crashes, avg 8.59s/turn. **CLEAN CART — session corruption FIXED.** Chinese leaks worsened (A3, A4 now have full Chinese paragraphs).

---

## Scenario B — Big Group (T2, 12 turns)

[Human] Xin chào, tụi mình 6 người. Tư vấn vài món cho bàn đông người đi em
[AI Waiter] Dạ, anh/chị có thể cân nhắc thử Lẩu Cá Tầm Măng Chua ạ. ✓

[Human] Tụi mình có 2 người ăn chay. Có món chay nào không em?
[AI Waiter] Dạ có thể thử đậu hũ sốt nấm chay? ✓

[Human] Có lẩu nào cho 6 người không? Tầm giá dưới 1 triệu
[AI Waiter] Dạ có lẩu cá tầm măng chua hoặc lẩu Thái cay nồng. ✓

[Human] Nhóm mặn gọi trước. Cho 2 Lẩu Thái, 2 Ốc Hương Xốt Trứng Muối, 3 Tôm Thẻ Nướng Muối Ớt
[AI Waiter] Giỏ hàng: Lẩu Thái ×2, Ốc Hương ×2, Tôm Thẻ ×3 = 965.000₫. ✓

[Human] Nhóm chay: 2 Mì Xào Rau với 2 Bánh Mì Bơ Tỏi
[AI Waiter] Giỏ hàng: + Mì Xào Rau ×2, Bánh Mì Bơ Tỏi ×2 = 1.125.000₫. ✓

[Human] Cả bàn 6 Bia Sài Gòn với 3 Nước Suối nữa
[AI Waiter] Giỏ hàng: + Bia Sài Gòn ×6, Nước Suối ×3 = 1.245.000₫. ✓

[Human] Đổi 2 Bia Sài Gòn qua 2 Bia Heineken đi. Với cho hỏi Bánh Mì Bơ Tỏi có hành không? Có đứa dị ứng hành
[AI Waiter] Giỏ hàng: -Bia Sài Gòn, +Bia Heineken = 1.205.000₫. ✓

[Human] À tụi mình thêm 1 Lẩu Khổ Qua Cá Thác Lác, nghe nói món đó cũng ngon mà đỡ cay hơn Lẩu Thái
[AI Waiter] Giỏ hàng: +Lẩu Khổ Qua ×1 = 1.460.000₫. ✓

[Human] Xem lại full đơn cả bàn đi em
[AI Waiter] Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [ORDER misroute → delegate, delegate_reason fix NOT WORKING yet — see Analysis #2]

[Human] Bỏ bớt 1 Lẩu Thái, thay bằng 2 Soup Tomyum Thố Nhỏ. Rồi chốt luôn
[AI Waiter] Dạ, xin lỗi anh/chị. Lỗi xử lý đơn hàng: Connection refused. [remove_cart + add_cart executed, confirm_order called after re-invoke — **FLOW IS CORRECT**. Backend down error expected. Cart updated: 1.140.000₫. 10.49s]

[Human] Ok xác nhận — [SKIPPED]
[Human] Tính tiền — [SKIPPED]

**Summary**: 10 turns, 10 tools, 0 crashes, avg 3.96s/turn. **B10 confirm_order loop FIXED.** B9 delegate still broken.

---

## Scenario C — Picky Customer (T3, 14 turns)

[Human] Dô, nay quán vắng quá vậy? Có gì ăn không em?
[AI Waiter] Dạ, anh/chị có thể thử cháo hải sản tươi ngon nữa ạ, bổ dưỡng lại dễ **呢？** [CHINESE LEAK] ✓

[Human] Cho anh xem món nào lạ miệng, đặc biệt một chút. Mấy món thường anh ăn chán rồi
[AI Waiter] Dạ có thể thử Răng Mực Xốt Thái Siêu Cay ạ. ✓

[Human] Mấy món cũng thường thôi. Ủa mà quán có món Cá Mặt Quỷ không em? Có báo viết khen lắm
[AI Waiter] Dạ có muốn thử cá tầm nướng sa tế không? Rất ngon, ăn kèm rau thơm **脆皮鱼怎么样？不过，既然您不介意尝试其他选项，那我推荐您可以试试烤石斑鱼，味道鲜美，搭配特制酱料更佳。** [SEVERE CHINESE LEAK — complete paragraph]

[Human] Ủa kỳ, Cá Mặt Quỷ không có hả? Vậy cá gì lạ lạ ở đây cho anh coi
[AI Waiter] Dạ em có thể thử món hến xúc bánh tráng ạ. ✓ [no Chinese — good]

[Human] Cá Chim Nướng Sa Tế bao nhiêu? Mà có cay lắm không? Nghe sa tế là thấy cay rồi
[AI Waiter] Dạ chị/chị có muốn thử cá tầm nướng sa tế nữa không? [wrong dish again — RAG quality issue]

[Human] Thôi được, cho anh 1 Sò Điệp Nướng Phô Mai, 1 Ốc Hương Xốt Trứng Muối. Mà khoan, giá sao vậy?
[AI Waiter] Giỏ hàng: Sò Điệp ×1, Ốc Hương ×1 = 170.000₫. [ORDER misroute, 18.05s slow]

[Human] Cho thêm 1 Bào Ngư Nướng Bơ Tỏi đi. À mà Tôm Hùm ở đây có không em?
[AI Waiter] Giỏ hàng: +Bào Ngư ×1 = 285.000₫. [SEMANTIC fast-track ORDER kills SEARCH for Tôm Hùm]

[Human] Ủa Tôm Hùm cũng không có luôn hả? Vậy hải sản cao cấp nhất ở đây là món gì?
[AI Waiter] Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [search returned 11 results, response is error — same bug as delegate path]

[Human] Thôi kệ, lấy thêm 2 Hàu Nướng Phô Mai với 1 Gỏi Hải Sản đi. Đồ ăn có tươi không đó?
[AI Waiter] Giỏ hàng: +Hàu ×2, Gỏi Hải Sản ×1 = 488.000₫. [17.23s slow — SEARCH worker failed no-tool-call]

[Human] Sò Điệp Nướng Phô Mai với Sò Điệp Nướng Mỡ Hành món nào ngon hơn?
[AI Waiter] Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [ORDER misroute → delegate, delegate fix not working]

[Human] Lấy thêm 1 Sò Điệp Nướng Mỡ Hành đi. Rồi bỏ món Gỏi Hải Sản, đổi qua Gỏi Xoài Ốc Giác cho gọn
[AI Waiter] Giỏ hàng: 6 món = 543.000₫. ✓ [perfect substitution chain]

[Human] Xem lại đơn coi, thấy hơi ít, lấy thêm gì ta...
[AI Waiter] Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [ORDER misroute → delegate, 6.52s]

[Human] Ok chốt đơn — [SKIPPED]
[Human] Tính tiền — [SKIPPED]

**Summary**: 12 turns, 12 tools, 0 crashes, avg 5.78s/turn. Chinese leaks worsened (C3 now full paragraph). Delegate still broken.

---

## Scenario D — Solo Quick Lunch (T4, 8 turns)

[Human] 1 mình, ăn trưa nhanh, dưới 100k
[AI Waiter] Dạ, anh/chị muốn em tư vấn món nào để ăn trưa nhanh? [ORDER misroute → delegate, now produces a natural response instead of "lỗi" — **DELEGATE FIX PARTIALLY WORKING** for this reason!]

[Human] Mì Xào Rau với Mì Xào Hải Sản khác gì nhau? Món nào no hơn?
[AI Waiter] Dạ, anh/chị có thể thử Mì Xào Bò 95.000₫ nhé. ✓

[Human] Lấy 1 Mì Xào Hải Sản, cho thêm ớt nha. Với 1 Bia Sài Gòn
[AI Waiter] Giỏ hàng: Mì Xào Hải Sản ×1 (nhiều ớt), Bia Sài Gòn ×1 = 110.000₫. ✓ [1.29s — fastest]

[Human] Cho thêm 1 trứng ốp la vô mì được không? Có tính thêm tiền hông?
[AI Waiter] Giỏ hàng: Mì Xào ×1, Bia ×1 = 110.000₫. [add_cart([]) — off-menu handled, cart unchanged] ✓

[Human] Mà quán nhận thẻ tín dụng không em?
[AI Waiter] Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [PAYMENT misroute → request_payment]

[Human] À có món tráng miệng gì không? Chè hay rau câu gì đó
[AI Waiter] Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [search returned 12 results, response is error]

[Human] Thôi kệ. Xác nhận đơn — [SKIPPED]
[Human] Tính tiền — [SKIPPED]

**Summary**: 6 turns, 6 tools, 0 crashes, avg 2.88s/turn. D1 delegate partially working (better response). D5/D6 still broken.

---

## Problems & Analysis

### 1. FIXED ✓ — Session State Corruption

A1 now correctly returns 1 search tool call (was 11). Cart at A6 starts clean with only the items ordered (290.000₫). All SEARCH turns A1-A5 return proper search responses instead of "lỗi".

**Root cause**: LangGraph checkpoints DB retained stale state from prior runs. Wiping `storage/db/checkpoints.db` before the test run fixed it.

### 2. FIXED ✓ — Confirm Order Loop Failure

**A14** and **B10** now work correctly. The validator strips `confirm_order` from mixed turns, pushes `ORDER_CONFIRM` to the intent queue with sub-query "Xác nhận đơn hàng". Cart tools execute first, then the worker is re-invoked with ORDER_CONFIRM → produces `confirm_order` with the updated cart.

Both turns correctly call `confirm_order` at the end. The "Connection refused" error is expected (backend is down). The flow is:

```
Turn:           intents = [ORDER]
Worker:         [remove_cart, add_cart, confirm_order]
Validator:      strip confirm_order → push ORDER_CONFIRM
Tools:          remove + add execute
State_updater:  pop ORDER → [ORDER_CONFIRM]
Worker(re-inv): query="Xác nhận đơn hàng" → confirm_order
Tools:          confirm_order → backend
```

Loop count = 0 for both turns (no retries needed).

### 3. PARTIALLY FIXED — Delegate Response

**D1** now produces a natural response ("Dạ, anh/chị muốn em tư vấn món nào...") instead of "lỗi khi xử lý đơn". The `_rewrite_chat` LLM path handles `delegate_reason="đang thảo luận về đơn hàng"` correctly.

**B9, C10, C12** still produce "lỗi khi xử lý đơn" despite having matching patterns in `_rewrite_chat` (B9 delegate_reason contains "xem lại" → should trigger cart echo). The cause is that `_pick_tool_message` in `state_outcome_node` selects old `ToolMessage`s from previous turns instead of falling through to the ChatResponseContext fallback. When an old add_cart ToolMessage is picked, `_build_from_tool_message` creates an `OrderResponseContext` instead of `ChatResponseContext`, so delegate_reason is never read.

**Fix needed**: `_pick_tool_message` should only consider ToolMessages from the CURRENT turn, not from all history.

### 4. WORSENED — Chinese Language Leaks

Chinese leaks expanded dramatically:
- **A3**: Full Chinese paragraph mixed with Vietnamese ("呢，这里我纠正了错误...")
- **A4**: Complete Chinese sentence ("推荐您尝试一下我们的蒜香蒸螺...")
- **C3**: Extended Chinese paragraph ("脆皮鱼怎么样？不过，既然您不介意...")

Previously these were single characters (呢？) at response end. Now the LLM is generating full Chinese paragraphs mid-response. The response rewriter's Vietnamese-only instruction is being ignored.

### 5. UNCHANGED — Router Misclassification: 10/42 = 23.8%

| Turn | Text | Expected | Actual | Pattern |
|------|------|----------|--------|---------|
| A8 | "cho Bia Tiger... có bia nào nhẹ hơn?" | SEARCH | ORDER | SEMANTIC fast-track kills SEARCH |
| A11 | "Gỏi Xoài giá bao nhiêu? Cho 1 phần" | ORDER | SEARCH | SEARCH wins |
| A12 | "cho anh xem tổng đơn hiện tại đi" | SEARCH | PAYMENT | "xem đơn" → payment |
| B9 | "Xem lại full đơn cả bàn" | SEARCH | ORDER | Cart review misroute |
| C6 | "cho 1 Sò Điệp... giá sao?" | SEARCH | ORDER | Dual-intent |
| C10 | "Sò A với Sò B món nào ngon hơn?" | SEARCH | ORDER | Comparison → ORDER |
| C12 | "Xem lại đơn coi... lấy thêm gì" | SEARCH | ORDER | Cart review + browse |
| D1 | "1 mình, ăn trưa nhanh, dưới 100k" | SEARCH | ORDER | Budget greeting → ORDER |
| D4 | "Cho thêm trứng ốp la vô mì" | SEARCH | ORDER | Off-menu → ORDER |
| D5 | "quán nhận thẻ tín dụng không?" | SEARCH | PAYMENT | "thẻ" → payment |

### 6. UNCHANGED — Multi-Intent Sub-Query Loss

A8, A9, A10, C7 all lose their SEARCH sub-queries because the SEMANTIC router fast-tracks to a single ORDER intent. C9 correctly detected ORDER+SEARCH but the SEARCH worker produced no tool calls for the quality question "đồ ăn có tươi không?".

### 7. Latency Analysis

| Rank | Turn | Latency | Cause |
|------|------|---------|-------|
| 1 | A11 | 29.84s | Gỏi Xoài price + order, slow SEARCH worker |
| 2 | A9 | 21.62s | Dual-intent, search hanging |
| 3 | A8 | 18.75s | Dual-intent, search hanging |
| 4 | C6 | 18.05s | Order + price check |
| 5 | C9 | 17.23s | Order + quality question |
| 6 | A1 | 11.26s | Cold start |
| 7 | A14 | 11.18s | confirm_order execute (backend timeout) |
| 8 | B10 | 10.49s | remove+add+confirm execute (backend timeout) |

### 8. "Lỗi khi xử lý đơn" Overuse

Still appears for:
- A12: PAYMENT misroute → request_payment → "lỗi"
- A14, B10: confirm_order → backend DOWN → "Connection refused" (expected)
- B9, C10, C12: delegate → still showing "lỗi" (pick_tool_message bug)
- C8, D6: search results exist but response is "lỗi" (same pick_tool_message issue)
- D5: request_payment → backend DOWN → "lỗi"

---

## Metrics Summary

| Scenario | Turns | Tools | Crashes | Avg Latency | Mismatches | Δ vs Prev |
|----------|-------|-------|---------|-------------|------------|-----------|
| A — Couple | 14/17 | 14 | 0 | 8.59s | 3 (21.4%) | -0.08s, cart fixed |
| B — Big Group | 10/12 | 10 | 0 | 3.96s | 1 (10.0%) | -0.12s, B10 fixed |
| C — Picky | 12/14 | 12 | 0 | 5.78s | 3 (25.0%) | -0.39s |
| D — Solo | 6/8 | 6 | 0 | 2.88s | 3 (50.0%) | -0.07s, D1 improved |
| **TOTAL** | **42/51** | **42** | **0** | **5.87s** | **10 (23.8%)** | -0.18s |

- Backend-dependent turns skipped: 9/51 (17.6%)  
- Intent mismatch rate: 10/42 = 23.8% (unchanged)  
- Zero crashes  
- Scenario A session corruption: **FIXED**  
- Confirm order loop: **FIXED**  
- Delegate error response: **PARTIALLY FIXED**  
- Chinese leaks: **WORSENED**

---

## Priority Action Items (Updated)

| # | Issue | Status | Priority |
|---|-------|--------|----------|
| 1 | Clear checkpoints DB before test run | ✅ FIXED | — |
| 2 | Fix confirm_order + add_cart in same turn | ✅ FIXED | — |
| 3 | Fix delegate error response — _pick_tool_message picks old ToolMessages, preventing ChatResponseContext fallback | 🔧 In Progress | HIGH |
| 4 | Fix Chinese leaks — worsened; response rewriter ignoring Vietnamese-only instruction | ⚠️ REGRESSION | HIGH |
| 5 | Fix router misclassification (10/42) — SEMANTIC fast-track kills multi-intent; SLM misses dual-intent | 📋 Pending (deploy → fine-tune) | MEDIUM |
| 6 | Fix "lỗi" response for working SEARCH — same _pick_tool_message root cause as #3 | 🔗 Same as #3 | MEDIUM |
| 7 | SEARCH worker produces no tool_calls for non-menu queries ("có tươi không?") | 📋 Pending (LLM quality) | LOW |
| 8 | "xem đơn" routing — needs dedicated path | 📋 Pending (router improvement) | LOW |
| 9 | "thẻ tín dụng" routing — payment method question triggers request_payment | 📋 Pending | LOW |
