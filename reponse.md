# E2E Evaluation — Part 1 + Part 2 Results

**Model:** gemma4:e2b-it-qat (all roles)
**Date:** 2026-07-07
**Pass Rate:** 6/11 (54.55%)

---

## Passed (6/11)

### E2E-001 — Happy path single item

```
[Human] Cho mình 2 phần Ốc Hương xốt trứng muối
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
        Tổng tạm tính 170.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?

[Human] Đúng rồi, xác nhận đặt luôn
[AI]    Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [Errno 111] Connection refused
```
Tool calls: add_cart ✓, confirm_order ✓. Backend down → `Connection refused` expected.

### E2E-002 — Multi-item order

```
[Human] Cho 6 con Hàu Nướng Phô Mai và 3 chai Bia Tiger Bạc nha
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Hàu Nướng Phô Mai ×6 (39.000₫/phần)
          - Bia Tiger Bạc ×3 (22.000₫/phần)
        Tổng tạm tính 300.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?

[Human] Ok chốt đơn đi em
[AI]    Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [Errno 111] Connection refused
```
Tool calls: add_cart (2 items) ✓, confirm_order ✓.

### E2E-003 — Search then order

```
[Human] Lẩu Thái ở quán cay không em?
[AI]    Dạ, hiện tại em có món Lẩu Thái với giá 255.000đ ạ. Ngoài ra còn có
        Tré Trộn Thái với giá 95.000đ nữa ạ.

[Human] Vậy cho mình 1 phần Lẩu Thái
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Lẩu Thái ×1 (255.000₫/phần)
        Tổng tạm tính 255.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?

[Human] Ừ đặt nha
[AI]    Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [Errno 111] Connection refused
```
Tool calls: search ✓, add_cart ✓, confirm_order ✓. Full search→order→confirm flow works.

### E2E-006 — Add item then confirm

```
[Human] Cho mình 2 phần Ốc Hương
[AI]    Dạ, món **Ốc Hương** bên em có nhiều loại ạ, anh/chị muốn chọn loại nào ạ?
          - Ốc Hương Xốt Trứng Muối
          - Ốc Hương Xốt Phô Mai
          - Ốc Hương Xốt Me
          ... (11 variants)

[Human] Thêm 1 dĩa Khoai Tây Lắc Phô Mai nữa
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Khoai Tây Lắc Phô Mai ×1 (49.000₫/phần)
        Tổng tạm tính 49.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?

[Human] Ok đặt hết luôn nha
[AI]    Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [Errno 111] Connection refused
```
Tool calls: add_cart (ambiguous→asked for clarification) ✓, add_cart ✓, confirm_order ✓.

### E2E-009 — Modify quantity

```
[Human] Cho mình 2 con Hàu Nướng Phô Mai
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Hàu Nướng Phô Mai ×2 (39.000₫/phần)
        Tổng tạm tính 78.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?

[Human] Mà thôi cho mình 5 con luôn đi
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Hàu Nướng Phô Mai ×7 (39.000₫/phần)
        Tổng tạm tính 273.000₫.
        Anh/chị xác nhận đặt hàng chưa ạ?
        ⚠ 2 + 5 = 7 (merged instead of replaced)

[Human] Ừ chốt nha
[AI]    Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [Errno 111] Connection refused
```
**Issue:** Quantity is ADDED (2× → 5× = 7× total) instead of REPLACED. Customer said "thôi cho 5 con" which implies replacing the 2 with 5, not adding 5 more. The ORDER worker uses ADD semantics (always merges), which is wrong for this substitution pattern.

### E2E-011 — Remove one of two

```
[Human] Cho mình 2 phần Ốc Hương Xốt Trứng Muối và 2 chai Bia Sài Gòn
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
          - Bia Sài Gòn ×2 (15.000₫/phần)
        Tổng tạm tính 200.000₫.

[Human] Bỏ bia đi, không lấy bia nữa
[AI]    Dạ, em đã bỏ món khỏi giỏ hàng ạ.
        Dạ, giỏ hàng của anh/chị hiện có:
          - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
        Tổng tạm tính 170.000₫.

[Human] Ok đặt nha
[AI]    Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [Errno 111] Connection refused
```
Tool calls: add_cart ✓, remove_cart ✓, confirm_order (1 item, no Bia) ✓.

---

## Failed (5/11)

### E2E-004 — order_then_request_payment (FAIL)

```
[Human] Cho mình 1 tô Cháo Hàu
[AI]    Dạ em chưa có thông tin về món này, anh/chị cho em tìm giúp nhé ạ?

[Human] Xác nhận đặt luôn
[AI]    Dạ, anh/chị muốn xác nhận đặt 1 tô Cháo Hàu ạ. Hiện tại em vẫn đang tìm
        thông tin chi tiết về món này để hỗ trợ anh/chị nhé.

[Human] Cho mình tính tiền nha
[AI]    Dạ, hiện chưa có đơn hàng nào trong phiên này ạ.
```

**Root cause:** ORDER worker at turn 1 produced NO tool call for "Cháo Hàu" — `add_cart` was never called. Cart remained empty. All subsequent turns (confirm, payment) fail because there's no cart.

Gemma4 ORDER worker failure — same pattern as turn 7 in the long conversation test. The retry mechanism didn't save it here either.

**Latency:** Turn 2 took 27.88s — the ORDER_CONFIRM validator rejected (cart empty) and the retry loop ran.

---

### E2E-005 — search_only_no_order (FAIL)

```
[Human] Quán mình có những món lẩu nào vậy?
[AI]    Dạ em xin phép tìm giúp anh/chị danh sách các món lẩu ạ.
        ⚠ No search() tool call was made. AI gave a placeholder response.

[Human] Thế Ốc Hương giá bao nhiêu một phần?
[AI]    Dạ, em xin thông báo hiện tại bên em có 3 món là Ốc Hương Xốt Trứng Muối,
        Ốc Mỡ Xốt Trứng Muối và Ốc Cà Na Xốt Trứng Muối ạ. Anh/chị muốn gọi món nào ạ?
```

**Root cause:** SEARCH worker at turn 1 produced NO tool call. The ASSERT required `search` to be called, but `tool_calls: []`. Turn 2 worked correctly.

Gemma4 SEARCH worker failure — the model produced text instead of a search() tool call. The retry didn't activate here (retry is only in ORDER worker at the moment).

---

### E2E-007 — user_refuses_then_reorders (FAIL)

```
[Human] Cho mình 1 phần Mực Chiên Xù
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Mực Chiên Xù ×1 (135.000₫/phần)
        Tổng tạm tính 135.000₫.

[Human] Thôi không lấy Mực nữa, đổi thành Cháo Hàu đi
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Mực Chiên Xù ×1 (135.000₫/phần)
          - Cháo Hàu ×1 (95.000₫/phần)
        Tổng tạm tính 230.000₫.
        ⚠ Mực Chiên Xù still in cart despite remove_cart returning success!

[Human] Ok đặt thôi
[AI]    Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [Errno 111] Connection refused
        ⚠ confirm_order contained BOTH Mực + Cháo. Should only contain Cháo.
```

**Root cause:** `remove_cart` + `add_cart` in the same turn: the `update_state_node` processes both ToolMessages sequentially. `remove_cart` sets cart without Mực, then `add_cart` merges with the CART THAT WAS SET BY remove_cart. But the final state shows both items.

The `_handle_remove_cart_result` removes by name, and `_handle_add_cart_result` merges with the existing cart. But the tool output says "Đã bỏ món" (success). So either:
1. `update_state_node` processes `add_cart` BEFORE `remove_cart` (wrong order in `tool_messages` extraction)
2. Or `_handle_remove_cart_result` has a bug

The ASSERT confirmed items contained forbidden 'Mực' — the cart still had both items at confirm.

---

### E2E-008 — full_flow_order_pay_verify (FAIL)

```
[Human] Cho mình 1 phần Tôm Càng Xanh Nướng Phô Mai và 2 chai Bia Sài Gòn
[AI]    Dạ, giỏ hàng của anh/chị hiện có:
          - Tôm Càng Xanh Nướng Phô Mai ×1 (120.000₫/phần)
          - Bia Sài Gòn ×2 (15.000₫/phần)
        Tổng tạm tính 150.000₫.

[Human] Đúng rồi xác nhận luôn
[AI]    Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. [Errno 111] Connection refused

[Human] Cho mình xin mã QR thanh toán
[AI]    Dạ, hiện chưa có đơn hàng nào trong phiên này ạ.
        ⚠ Backend down → confirm_order failed → no order in DB → request_payment returns empty

[Human] Mình chuyển khoản xong rồi nha
[AI]    Dạ, hiện chưa có đơn hàng nào trong phiên này ạ.
        ⚠ Expected verify_payment, got request_payment. Payment dispatcher always emits request_payment.
```

**Root cause:** Two issues:
1. Backend down → confirm_order fails → payment tools can't find an order → always return "chưa có đơn hàng"
2. Payment dispatcher always calls `request_payment` — never `verify_payment`. The "chuyển khoản xong" utterance should trigger `verify_payment`, but the dispatcher hardcodes `request_payment`.

---

### E2E-010 — chitchat_then_order (FAIL)

```
[Human] Chào em, quán hôm nay đông ghê ha
[AI]    Dạ, em chào anh/chị ạ. Em có thể giúp gì cho anh/chị ạ?

[Human] Thôi cho anh 1 phần Lẩu Thái đi
[AI]    Dạ em đã nhận được yêu cầu của anh/chị về 1 phần Lẩu Thái ạ. Em sẽ kiểm tra
        thông tin chi tiết cho anh/chị nhé!
        ⚠ No add_cart tool call. Cart still empty.

[Human] Xác nhận đi em
[AI]    Dạ, em đã xác nhận lại yêu cầu của anh/chị là 1 phần Lẩu Thái ạ. Anh/chị cần
        em hỗ trợ thêm gì nữa không ạ?
        ⚠ confirm_order with 0 items. Cart was never populated.
```

**Root cause:** ORDER worker at turn 2 produced NO tool call — `add_cart` never called. Gemma4 ORDER worker failure after a CHAT turn. The retry also failed. Latency on turn 3 spiked to 57.56s (validator rejection + retry loop).

---

## Failure Analysis

| Scenario | Tool | Root Cause |
|----------|------|-----------|
| E2E-004 | add_cart not called | Gemma4 ORDER worker fails after CHAT context |
| E2E-005 | search not called | Gemma4 SEARCH worker produces text instead of tool call |
| E2E-007 | remove_cart ineffective | update_state_node may process add_cart before remove_cart |
| E2E-008 | verify_payment not called | Payment dispatcher hardcodes request_payment |
| E2E-010 | add_cart not called | Gemma4 ORDER worker fails after CHAT context |

### Pattern

- **3/5 failures** are Gemma4 worker LLM refusing to produce tool calls (E2E-004, E2E-005, E2E-010). The ORDER retry helps but is not sufficient.
- **1 failure** is a state update ordering bug (E2E-007)
- **1 failure** is a missing verify_payment dispatch (E2E-008)
- All 5 pass scenarios involve ORDER with clean context (no CHAT turn in history) or simple SEARCH→ORDER flows
