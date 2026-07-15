# Long Conversation Test — AI Waiter Responses (Post-Refactor v2)

**Model:** qwen2.5:7b-instruct (all roles)
**Date:** 2026-07-15
**Result:** 10/12 turns had tool calls (83%), 0 crashes

**Note:** Cart state from previous runs persisted via SQLite checkpointer. Quantities started non-zero at Turn 1. This does not affect correctness validation of the fixes.

---

## Conversation

> **Turn 1-3** — greeting + menu browse + dish inquiry
```
[Human] Chào em, bàn mình có 2 người. Cho anh xem menu có gì hot hôm nay đi
[AI]    Dạ, có thể thử Lẩu Thái hoặc Cá Chim Nướng Sa Tế...
```
Tools: search("món ngon, món mới"), search("ốc, tôm"), search("Ốc Hương Xốt Trứng Muối"). All correct.

> **Turn 4** — portion info query (misrouted)
```
[Human] Tôm Càng Xanh Nướng Phô Mai phần ăn bao nhiêu con vậy em?
[AI]    Dạ, anh/chị cho em hỏi bếp nhé. Em chưa có thông tin đó ạ.
```
Router: ORDER (SEMANTIC, should be SEARCH). No tool call → redirected to chat. Acceptable.

> **Turn 5** — first item order ✅ FIXED (WAS DELEGATE HIJACK)
```
[Human] Cho anh 2 phần Ốc Hương Xốt Trứng Muối trước đi
[AI]    Dạ, giỏ hàng của anh/chị hiện có: ... Ốc Hương Xốt Trứng Muối ×2 ...
```
Tool: add_cart([Ốc Hương×2]). ✅ **FIX CONFIRMED**: Previous run had add_cart dropped by delegate hijack. Now delegate is stripped — add_cart executed correctly. Ốc Hương ×2 added to cart.

**Log**: `Stripped 1 delegate call(s) — 1 CRUD call(s) remain`

> **Turn 6** — multi-item add ✅ NO DOUBLING
```
[Human] Vợ anh thích ăn hàu, cho thêm 3 con Hàu Nướng Phô Mai và 1 chai Bia Tiger Bạc
[AI]    Dạ, giỏ hàng: ... Hàu Nướng Phô Mai ×6, Bia Tiger Bạc ×1 ...
```
Tool: add_cart([Hàu Nướng×3, Bia Tiger×1]). ✅ LLM passed ONLY the new items. No existing items re-passed. Hàu merged correctly: existing ×3 + new ×3 = ×6.

> **Turn 7** — price query ✅ DELEGATE CATCHES MISROUTE
```
[Human] À quên, Ốc Hương Xốt Trứng Muối bao nhiêu 1 phần vậy?
[AI]    Dạ, 85.000 đồng mỗi phần ạ.
```
Tool: delegate(reason="khách hỏi về giá món ăn, không phải yêu cầu CRUD"). Router: ORDER (SEMANTIC — wrong). ✅ Delegate caught it, cart NOT mutated. Answered from curated_memory.

> **Turn 8** — substitution: remove + add
```
[Human] Thôi bỏ Bia Tiger Bạc đi, đổi qua 2 Bia Sài Gòn đi em.
[AI]    Dạ, giỏ hàng: ... Bia Sài Gòn ×4 ...
```
Tools: remove_cart(Bia Tiger) + add_cart([Bia Sài Gòn×2]). Bia Tiger removed, Bia Sài Gòn merged (×2 existing + ×2 new = ×4 due to add_cart merge semantics). No delegate interference.

> **Turn 9** — cart review ✅ FIXED (NO DOUBLING)
```
[Human] Cho anh xem lại order đang có những gì đi em
[AI]    Dạ, giỏ hàng của anh/chị hiện có: Hàu Nướng ×6, Bia Sài Gòn ×4, ...
```
Tool: delegate(reason="khách hỏi xem lại giỏ hàng, không có yêu cầu CRUD"). ✅ **FIX CONFIRMED**: Order worker called delegate. Cart NOT mutated. Correct echo. This was the Turn 9 bug (×4→×8 doubling) in the original run.

> **Turn 10** — valid item + off-menu item ✅ FIXED (WAS DELEGATE HIJACK)
```
[Human] Thêm 1 dĩa Khoai Tây Lắc Phô Mai cho vợ. Với cả có Dừa Tươi không em?
[AI]    Dạ, giỏ hàng: ... Khoai Tây Lắc Phô Mai ×1 ...
```
Tool: add_cart([Khoai Tây×1]). ✅ **FIX CONFIRMED**: Previous run had add_cart dropped. Now delegate stripped, add_cart executed. Khoai Tây added to cart. Validator restored cart items + deduplicated correctly.

**Validator log**:
```
additive turn but the LLM dropped the existing cart — restored 4 item(s)
stripped 4 existing item(s) from add_cart (context copy, not mentioned by customer)
```

> **Turn 11** — dish inquiry with conditional order ⚠️ NO TOOL CALL
```
[Human] Gỏi Xoài Ốc Giác có ngon không? Anh tính gọi thêm 1 phần mà sợ cay quá
[AI]    Xin lỗi, em chưa rõ, anh/chị nói lại giúp em nhé ạ.
```
Router: SEARCH+ORDER (SLM — dual intent). But search worker produced NO tool call despite `tool_choice="any"`. This is a separate issue — the search worker with the new ĐÃ BIẾT context + delegate tool may be confusing the dual-intent case. Defensive fallback to default response.

> **Turn 12** — add with special request
```
[Human] Thôi cho anh 1 phần Gỏi Xoài Ốc Giác luôn, ít cay nha em
[AI]    Dạ, giỏ hàng: ... Gỏi Xoài Ốc Giác ×2 (95.000₫/phần) (Ghi chú: ít cay) ...
```
Tool: add_cart([Gỏi Xoài Ốc Giác×1]). Special request "ít cay" correctly extracted. OK.

> **Turns 13-15** — Confirm & Payment (SKIPPED)
```
Backend service was not reachable (port 8000). Turns skipped.
```

---

## Fixes Confirmed

| Bug | Original | Post-Fix | Evidence |
|-----|----------|----------|----------|
| Turn 5: delegate hijack drops add_cart | Ốc Hương lost | Ốc Hương ×2 in cart | `Stripped 1 delegate call(s) — 1 CRUD call(s) remain` |
| Turn 6: LLM re-passes existing items (doubling) | Ốc Hương ×2→×4 | Hàu ×3→×6 correct merge | LLM passed only [Hàu×3, Bia×1], no Ốc Hương |
| Turn 9: Cart review doubles everything | ×4→×8 | Cart NOT mutated | delegate called, correct echo |
| Turn 10: delegate hijack drops add_cart | Khoai Tây lost | Khoai Tây ×1 in cart | add_cart executed, validator dedup worked |

## Remaining Issues

| Turn | Issue | Severity | Note |
|------|-------|----------|------|
| 4 | Portion query misrouted as ORDER | Low | Chat fallback handled correctly |
| 7 | Price query misrouted as ORDER | Low | Delegate caught it, no harm |
| 11 | Search worker produced no tool call | Medium | Dual intent (SEARCH+ORDER) confused the search worker with new delegate context. Needs investigation |
| 11 | Fallback response was unhelpful | Low | "Em chưa rõ" could be improved |
| All | SQLite checkpointer persists state across runs | Low | Test contamination — not a production bug but affects eval reproducibility |
