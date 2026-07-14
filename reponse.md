# Long Conversation Test — AI Waiter Responses

**Model:** qwen2.5:7b-instruct (all roles)
**Date:** 2026-07-14
**Result:** 10/12 turns had tool calls (83%), 0 crashes

---

## Conversation

> **Turn 1** — greeting + menu browse
```
[Human] Chào em, bàn mình có 2 người. Cho anh xem menu có gì hot hôm nay đi
[AI]    Dạ, anh/chị có thể thử Lẩu Thái với giá 255.000₫ hoặc Cá Chim Nướng Sa Tế
        với 249.000₫, đều là những món ăn rất được khách hàng yêu thích ạ.
```
Tool: search("món ngon, món hot"). Router classified correctly as SEARCH (SLM).

---

> **Turn 2** — recommendation search
```
[Human] Hải sản ở đây có món gì ngon? Anh với vợ thích ốc với tôm, em gợi ý vài món đi
[AI]    Dạ, anh/chị có thể thử món tôm sú xào sa tế ạ. Đây là một trong những món
        hải sản được nhiều thực khách yêu thích tại Ốc Quậy, đảm bảo sẽ vừa miệng anh/chị.
```
Tool: search("ốc, tôm, hải sản"). Correctly classified SEARCH (SLM). Good query rewrite from conversational input.

---

> **Turn 3** — follow-up question about found dish
```
[Human] Ốc Hương Xốt Trứng Muối ngon không em? Có cay không?
[AI]    Dạ, anh/chị muốn gọi Ốc Hương Xốt Trứng Muối ạ? Chúng có hai suất giá 85.000
        đồng mỗi suất ạ.
```
Tool: search("Ốc Hương Xốt Trứng Muối"). Classified SEARCH (SLM). Good direct dish name lookup, no rewrite needed. Response slightly misinterprets "ngon không/cay không" as an order intention but answers with available info.

---

> **Turn 4** — portion info query ⚠️ MISROUTED
```
[Human] Tôm Càng Xanh Nướng Phô Mai phần ăn bao nhiêu con vậy em?
[AI]    Dạ, anh/chị cho em hỏi bếp nhé. Em chưa có thông tin đó ạ.
```
⚠️ Router classified as ORDER (SEMANTIC, should be SEARCH). No tool call. The graph redirected to chat_worker, which correctly said it doesn't have that info rather than hallucinating. Acceptable fallback behavior.

---

> **Turn 5** — first item order
```
[Human] Cho anh 2 phần Ốc Hương Xốt Trứng Muối trước đi
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
        Tổng tạm tính 170.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?
```
Tool: add_cart([Ốc Hương Xốt Trứng Muối×2]). Router: ORDER (SEMANTIC, 0.64 confidence). Stage: AWAITING_CONFIRMATION. Perfect.

---

> **Turn 6** — multi-item add
```
[Human] Vợ anh thích ăn hàu, cho thêm 3 con Hàu Nướng Phô Mai và 1 chai Bia Tiger Bạc
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Ốc Hương Xốt Trứng Muối ×4 (85.000₫/phần)
          - Hàu Nướng Phô Mai ×3 (39.000₫/phần)
          - Bia Tiger Bạc ×1 (22.000₫/phần)
        Tổng tạm tính 479.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?
```
Tool: add_cart([Ốc Hương×2, Hàu Nướng×3, Bia Tiger×1]). ⚠️ LLM passed the full cart (including existing items) which caused Ốc Hương to double to ×4. The validator's additive protection didn't catch this because the LLM included existing items in the list. Not ideal but the cart echo is accurate.

---

> **Turn 7** — price query about item already in cart ⚠️ MISROUTED
```
[Human] À quên, cho anh hỏi Ốc Hương Xốt Trứng Muối bao nhiêu 1 phần vậy?
[AI]    Dạ, giá của món Ốc Hương Xốt Trứng Muối là 85.000₫/phần ạ. Anh/chị có cần
        thêm thông tin gì nữa không?
```
⚠️ Router classified as ORDER (SEMANTIC, should be SEARCH). No tool call — redirected to chat_worker. However, the chat LLM had the price in `curated_memory` from the earlier search and answered correctly. Acceptable fallback.

---

> **Turn 8** — substitution: remove + add
```
[Human] Thôi bỏ Bia Tiger Bạc đi, đổi qua 2 Bia Sài Gòn đi em. Bia Tiger nghe đắng quá
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Ốc Hương Xốt Trứng Muối ×4 (85.000₫/phần)
          - Hàu Nướng Phô Mai ×3 (39.000₫/phần)
          - Bia Sài Gòn ×2 (15.000₫/phần)
        Tổng tạm tính 487.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?
```
Tools: remove_cart(Bia Tiger Bạc) + add_cart([Bia Sài Gòn×2]). Two tool calls in one turn — the new CoT prompt correctly handled substitution as two calls. Cart correctly shows Bia Tiger removed and Bia Sài Gòn added. Total updated (479k → 487k). Perfect.

---

> **Turn 9** — cart review ⚠️ QUANTITY BUG
```
[Human] Cho anh xem lại order đang có những gì đi em
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Ốc Hương Xốt Trứng Muối ×8 (85.000₫/phần)
          - Hàu Nướng Phô Mai ×6 (39.000₫/phần)
          - Bia Sài Gòn ×4 (15.000₫/phần)
        Tổng tạm tính 974.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?
```
⚠️ Router classified as ORDER (should be SEARCH). The ORDER worker called add_cart with the full existing cart — doubling all quantities (×4→×8, ×3→×6, ×2→×4). The validator's additive protection failed because "xem lại" contains none of the additive or destructive markers. **This is a bug** — "xem lại" (review) should trigger a SEARCH or CHAT, not an ORDER. The Entity Tracker (Section 6.1) would help here by routing cart review questions to a cart-read path, not an order-modify path.

---

> **Turn 10** — valid item + off-menu item ⚠️ QUANTITY BUG CONTINUES
```
[Human] Thêm 1 dĩa Khoai Tây Lắc Phô Mai cho vợ. Với cả có Dừa Tươi không em? Cho anh 1 trái
[AI]    Dạ, món Dừa Tươi hiện không có trong thực đơn ạ. Anh/chị muốn chọn món khác không ạ?
```
Tools: add_cart([existing items + Khoai Tây]). ⚠️ The doubling bug from turn 9 propagates — cart now has ×16 Ốc Hương, ×12 Hàu, ×8 Bia. "Dừa Tươi" correctly detected as off-menu by validator. Response correctly rejects the off-menu item but doesn't echo the cart (the response was truncated, likely by output limit).

---

> **Turn 11** — dish inquiry with conditional order intent
```
[Human] Gỏi Xoài Ốc Giác có ngon không? Anh tính gọi thêm 1 phần mà sợ cay quá
[AI]    Dạ, Gỏi Xoài Ốc Giác rất ngon ạ. Món này chua ngọt, giòn dai và đậm đà.
        Nếu anh thích ăn ít cay hơn, em khuyên anh nên chọn phần không cay hoặc ít cay nhé.
        Anh/chị muốn thêm vào giỏ hàng không ạ?
```
Tool: search("Gỏi Xoài Ốc Giác, độ cay"). Router: SEARCH+ORDER (SLM — correctly identified the conditional dual intent). The SEARCH ran first and returned results. The ORDER was then dispatched but produced no tool call (the model didn't think "sợ cay quá" was a definitive order). Chat worker handled the rest. Good behavior.

---

> **Turn 12** — add with special request
```
[Human] Thôi cho anh 1 phần Gỏi Xoài Ốc Giác luôn, ít cay nha em
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Ốc Hương Xốt Trứng Muối ×16 (85.000₫/phần)
          - Hàu Nướng Phô Mai ×12 (39.000₫/phần)
          - Bia Sài Gòn ×8 (15.000₫/phần)
          - Khoai Tây Lắc Phô Mai ×1 (49.000₫/phần)
          - Gỏi Xoài Ốc Giác ×1 (95.000₫/phần) (Ghi chú: không cay, ít cay)
        Tổng tạm tính 2.092.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?
```
Tool: add_cart([Gỏi Xoài Ốc Giác×1]). Router: ORDER (SEMANTIC, 0.59 confidence). Validator correctly stripped the "ít cay" modifier from the name and set it as special_requests. Quantities are still inflated from the turn 9 bug but the modifier extraction is correct.

---

> **Turns 13-15** — Confirm & Payment (SKIPPED)
```
Backend service was not reachable (port 8000). Confirm/payment turns skipped.
```

---

## Issues Found

| Turn | Issue | Severity | Root Cause |
|------|-------|----------|------------|
| **4** | "Tôm Càng Xanh...bao nhiêu con" misrouted as ORDER | Low | Semantic router confused dish name query with order; chat_worker handled fallback correctly |
| **6** | Ốc Hương doubled (×2→×4) on additive turn | Medium | LLM passed full cart in add_cart call instead of only new items; validator didn't catch because LLM included existing items |
| **7** | "Ốc Hương Xốt Trứng Muối bao nhiêu" misrouted as ORDER | Low | Semantic router classified price query as ORDER; chat_worker had the price in curated_memory and answered correctly |
| **9** | Cart review doubles all quantities (×4→×8) | **High** | "Xem lại order" classified as ORDER instead of SEARCH/CHAT. LLM called add_cart with full cart, doubling everything. Validator additive protection has no marker for "xem lại" |
| **10** | Quantities propagate from turn 9 bug | **High** | Same root cause — inflated cart from turn 9 |

## What Needs Fixing

1. **Entity Tracker (Section 6.1)** — Would prevent "xem lại order" from being treated as an ORDER action. A cart review should route to a read-only path, not an order-modify path.

2. **Validator additive detection** — Need to add "xem", "xem lại", "kiểm tra", "order" to a new category of "read-only" markers that prevent add_cart calls entirely.

3. **Router: dish info → SEARCH** — "Tôm Càng Xanh...bao nhiêu con" and "Ốc Hương...bao nhiêu 1 phần" should be classified as SEARCH, not ORDER. These are info queries despite containing food names. Possibly add more SEARCH examples in the router few-shots.
