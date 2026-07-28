## Appendix G. End-to-End Conversation Transcripts

Six conversations were run end to end against the deployed agent and are summarised in Table 5.9.
Three of them are reproduced inside §5.4.5, because the argument made there cannot be followed
without the text: the twelve-turn sitting, the adversarial off-menu conversation, and the opening
turn of the multi-intent conversation. The remaining three are reproduced here in full.

The transcripts are verbatim. Vietnamese replies appear as generated, with the customer's turns
marked `[Khách]` and the agent's `[AI]`. `[Tools]` lines give the tool calls the agent produced
after validation, and `[Stage]` lines give the order stage committed to state.

---

### G.1 Ordering, Confirming and Paying

The baseline interaction is a customer who names two dishes, confirms, and asks for the bill.

```
[Khách]     Cho mình 2 Ốc Hương Xốt Trứng Muối với 1 Lẩu Thái nha
[Tools]     add_cart(Ốc Hương Xốt Trứng Muối ×2, Lẩu Thái ×1)
[Stage]     AWAITING_CONFIRMATION, cart 425.000₫
[AI]        Dạ, giỏ hàng của anh/chị hiện có:
            - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
            - Lẩu Thái ×1 (255.000₫/phần)
            Tổng tạm tính 425.000. Anh/chị xác nhận đặt hàng chưa ạ?

[Khách]     Ok chốt đơn đi em
[Tools]     confirm_order(items=[Ốc Hương Xốt Trứng Muối ×2, Lẩu Thái ×1])
[Stage]     CONFIRMED
[AI]        Dạ, em đã xác nhận đơn hàng 14 ạ. Món đang được chuẩn bị,
            anh/chị chờ một chút nhé.

[Khách]     Tính tiền giùm mình
[Tools]     request_payment(table_id=T_qs_1)
[AI]        Dạ, tổng hóa đơn của anh/chị là 425.000₫ ạ.
            Anh/chị vui lòng quét mã QR để thanh toán nhé.
```

Three turns, three intents, three correct tool calls. The order stage advances IDLE to
AWAITING_CONFIRMATION to CONFIRMED, and the billed total of 425.000₫ equals the cart total. That
last equality is the check that graph state and the orchestrator's ledger agree, and it holds in
every conversation that reaches payment.

The customer never uses a menu-exact phrasing for the transaction itself. "Chốt đơn đi em" is
colloquial for closing an order and "tính tiền giùm mình" is an informal request to be billed.
Neither appears in any tool schema; both route correctly.

---

### G.2 Referring Back to a Search Result

A customer who does not know the menu asks for a recommendation and then orders by reference
rather than by name.

```
[Khách]     Có món gì cay cay ăn nhậu không em
[Tools]     search(query="món cay, đồ cay, ốc cay, tôm cay")
[AI]        Dạ, anh/chị có muốn thử Tôm Thẻ Xốt Thái Siêu Cay ạ?
            Món này rất cay và ngon, chắc chắn sẽ thích hợp với khẩu vị
            của anh/chị.

[Khách]     Vậy cho mình 1 phần món đó đi
[Tools]     add_cart(Tôm Thẻ Xốt Thái Siêu Cay ×1)
[Stage]     AWAITING_CONFIRMATION, cart 115.000₫

[Khách]     Chốt đơn luôn nha
[Tools]     confirm_order(items=[Tôm Thẻ Xốt Thái Siêu Cay ×1])
[Stage]     CONFIRMED
```

The second turn contains no dish name at all. "Món đó" means "that dish", and resolving it
requires the system to remember what it just recommended. The search results persist in
`search_context`, are carried into the worker's prompt as curated memory, and the resolved name
reaches `add_cart` in full. This is the bridge described in §4.6.4 operating end to end, and it is
the interaction pattern a real customer is most likely to produce, since people rarely repeat a
dish name they have just been told.

---

### G.3 An Ambiguous Dish Name

Eleven dishes on the reference menu begin with "Ốc Hương". A customer who says only that has not
specified an order. This is the end-to-end view of the ambiguity mechanism whose accuracy §5.4.2
reports, and it is the more informative view, because it includes the clarification the customer
actually hears and the follow-up turn that resolves it.

```
[Khách]     Cho mình 2 phần Ốc Hương
[Tools]     add_cart(items=[])
[Stage]     IDLE, cart unchanged
[AI]        Dạ, món Ốc Hương bên em có nhiều loại ạ, anh/chị muốn chọn
            loại nào ạ?
            - Ốc Hương Xốt Trứng Muối
            - Ốc Hương Xốt Phô Mai
            - Ốc Hương Xốt Me
            - Ốc Hương Xốt Muối Tắc
            - Ốc Hương Xốt Bơ Cay
            - Ốc Hương Xốt Bơ Tỏi Cay
            - Ốc Hương Xốt Thái Siêu Cay
            - Ốc Hương Xốt Sa Tế
            - Ốc Hương Rang Muối
            - Ốc Hương Cháy Tỏi
            - Ốc Hương Hấp Sả

[Khách]     Ốc Hương Xốt Bơ Cay ấy
[Tools]     add_cart(Ốc Hương Xốt Bơ Cay ×2)
[Stage]     AWAITING_CONFIRMATION, cart 170.000₫

[Khách]     Chốt đơn đi em
[Tools]     confirm_order(items=[Ốc Hương Xốt Bơ Cay ×2])
[Stage]     CONFIRMED
```

The validator recognises that the spoken name is a prefix of eleven menu entries, empties the item
list before the tool executes, and returns all eleven candidates for the agent to read back. The
order stage stays at IDLE because nothing entered the cart. The customer's reply on the next turn
is a bare dish name with the particle `ấy`, and the quantity of two is carried forward from the
original request rather than being asked for again.

What the system does not do is choose. Selecting the most popular variant, or the first
alphabetically, would produce a smoother conversation and occasionally the wrong dish on the bill.
The design treats an ambiguous reference as missing information rather than as information to be
guessed.
