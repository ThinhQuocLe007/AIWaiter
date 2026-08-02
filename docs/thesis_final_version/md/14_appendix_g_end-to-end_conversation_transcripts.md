# Appendix G. End-to-End Conversation Transcripts

The seven conversations reported in section 5.4.5, reproduced as they ran. The customer's turns are marked [Khách] and the agent's [AI Waiter]; [Tools] lists the tool calls the graph executed on that turn and [Stage] the order stage committed to state afterwards. Transcripts are verbatim, including the agent's own phrasing errors and its repeated sentences.

The findings section 5.4.5 draws from these transcripts are stated as properties of the architecture rather than as properties of a particular turn, so a re-run replaces the transcripts below without invalidating that section's prose.

The pass rate over those five runs is 82.9 % [71.4 %–100 %]; the transcripts below are one of them, the run in which all seven scenarios passed their assertions. The runner derives a run-unique thread identifier and clears both the checkpoint store and the transactional tables before starting, so no run inherits the previous one's cart

**G.1 Ordering, Confirming, Paying (QS-001)**

The baseline path. The router classifies all three turns correctly, the validator confirms both item names against the menu, and the order stage advances IDLE to AWAITING_CONFIRMATION to CONFIRMED. The billed total matches the cart exactly, which is the check that state and ledger agree.


| [Khách]     Cho mình 2 Ốc Hương Xốt Trứng Muối với 1 Lẩu Thái nha [Tools]     add_cart(Ốc Hương Xốt Trứng Muối ×2, Lẩu Thái ×1) [Stage]     AWAITING_CONFIRMATION   cart 425.000₫ [AI Waiter] Dạ, đơn của mình đang có: - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần) - Lẩu Thái ×1 (255.000₫/phần) Tổng tạm tính 425.000. Anh/chị xác nhận đặt hàng chưa ạ? [Khách]     Ok chốt đơn đi em [Tools]     confirm_order(items=[Ốc Hương Xốt Trứng Muối ×2, Lẩu Thái ×1])  → đơn #74 [Stage]     CONFIRMED   cart trống [AI Waiter] Dạ, em đã xác nhận đơn hàng 74 ạ. Món đang được chuẩn bị. Anh/chị có muốn gọi thêm món gì nữa không ạ? [Khách]     Tính tiền giùm mình [Tools]     request_payment(table_id=T_qs_1)  → 425.000 VND [Stage]     CONFIRMED [AI Waiter] Dạ, tổng hóa đơn của anh/chị là 425.000₫ ạ. Anh/chị vui lòng quét mã QR để thanh toán nhé. [Khách]     Tính tiền giùm mình [Tools]     request_payment(table_id=T_qs_1) [AI Waiter] Dạ, tổng hóa đơn của anh/chị là 425.000₫ ạ. Anh/chị vui lòng quét mã QR để thanh toán nhé. |
| --- |

**G.2 Referring Back to a Search Result (QS-002)**

The referential phrase "món đó" resolves against the prior search context, so add_cart receives the full menu name rather than the pronoun. The bridge from search_context through curated_memory to the cart functions correctly.


| [Khách]     Có món gì cay cay ăn nhậu không em [Tools]     search(query="món cay, đồ cay, ốc cay, tôm cay")   → 6 kết quả [Stage]     IDLE [AI Waiter] Dạ anh/chị ơi, bên em có vài món cay ngon nha! Món tôm thẻ xốt bơ tỏi cay và tôm thẻ rang muối cay đều rất hợp gu người thích ăn cay, thịt tôm ngọt đậm đà, cay nhẹ vừa phải. Anh/chị thử không? [Khách]     Vậy cho mình 1 phần món đó đi [Tools]     add_cart(Tôm Thẻ Xốt Bơ Tỏi Cay ×1) [Stage]     AWAITING_CONFIRMATION   cart 115.000₫ [AI Waiter] Dạ, đơn của mình đang có: - Tôm Thẻ Xốt Bơ Tỏi Cay ×1 (115.000₫/phần) Tổng tạm tính 115.000. Anh/chị xác nhận đặt hàng chưa ạ? [Khách]     Chốt đơn luôn nha [Tools]     confirm_order(items=[Tôm Thẻ Xốt Bơ Tỏi Cay ×1])  → đơn #75 [Stage]     CONFIRMED   cart trống [AI Waiter] Dạ, đơn 75 đã được gửi bếp rồi nha. Anh/chị muốn gọi thêm gì không ạ? |
| --- |

**G.3 ****Two Intents in One Utterance(QS-003)**

Both turns are multi-intent and both decompose correctly. On the first, the boundary marker rồi triggers the rewriter, which splits the utterance into ORDER and PAYMENT fragments and executes both. On the second, ORDER_CONFIRM and PAYMENT both fire and the bill matches the confirmed order.

The first turn also shows the ordering constraint honestly. The payment fragment executes before the order is confirmed, so the payment tool finds no order to bill and returns an error, which the reply template renders as a statement that no order exists yet. The two intents run in the order spoken, not reordered to make sense, and the customer hears a cart summary followed by a refusal to bill.


| [Khách]     Cho 2 Hàu Nướng Phô Mai rồi tính tiền luôn nha em [Tools]     add_cart(Hàu Nướng Phô Mai ×2) request_payment(table_id=T_qs_3)   → lỗi: chưa có đơn để thanh toán [Stage]     AWAITING_CONFIRMATION   cart 78.000₫ [AI Waiter] Dạ, giỏ hàng của anh/chị hiện có: - Hàu Nướng Phô Mai ×2 (39.000₫/phần) Tổng tạm tính 78.000. Anh/chị xác nhận đặt hàng chưa ạ? Dạ, hiện chưa có đơn hàng nào trong phiên này ạ. [Khách]     Xác nhận đơn rồi bill luôn [Tools]     confirm_order(items=[Hàu Nướng Phô Mai ×2])  → đơn #76 request_payment(table_id=T_qs_3)             → 78.000 VND [Stage]     CONFIRMED   cart trống [AI Waiter] Dạ, đơn 76 đã được gửi bếp rồi nha. Anh/chị muốn gọi thêm gì không ạ? Dạ, tổng hóa đơn của anh/chị là 78.000₫ ạ. [Tools]     add_cart(Ốc Hương Xốt Bơ Cay ×2) [Stage]     AWAITING_CONFIRMATION   cart 170.000₫ [Khách]     Chốt đơn đi em [Tools]     confirm_order(items=[Ốc Hương Xốt Bơ Cay ×2]) [Stage]     CONFIRMED |
| --- |

**G.4 ****Changing Your Mind Mid-Order (QS-004)**

Both turns are multi-intent and both decompose correctly. On the first, the boundary marker rồi triggers the rewriter, which splits the utterance into ORDER and PAYMENT fragments and executes both. On the second, ORDER_CONFIRM and PAYMENT both fire and the bill matches the confirmed order.

The first turn also shows the ordering constraint honestly. The payment fragment executes before the order is confirmed, so the system reports that no order exists yet rather than inventing a total. The two intents run in the order spoken, not reordered to make sense, and the customer hears a cart summary followed by a refusal to bill.


| [Khách]     Cho mình 1 Mực Cháy Tỏi với 2 Bia Sài Gòn [Tools]     add_cart(Mực Cháy Tỏi ×1, Bia Sài Gòn ×2) [Stage]     AWAITING_CONFIRMATION   cart 165.000₫ [Khách]     Thôi bỏ Mực Cháy Tỏi đi, đổi qua Cháo Hàu 1 phần [Tools]     remove_cart("Mực Cháy Tỏi"), add_cart(Cháo Hàu ×1) [Stage]     AWAITING_CONFIRMATION   cart 125.000₫ [AI Waiter] Dạ, em đã bỏ món khỏi giỏ hàng ạ. Dạ, giỏ hàng của anh/chị hiện có: - Bia Sài Gòn ×2 (15.000₫/phần) - Cháo Hàu ×1 (95.000₫/phần) Tổng tạm tính 125.000. Anh/chị xác nhận đặt hàng chưa ạ? [the same cart summary is then repeated a second time] [Khách]     Thêm 1 Khoai Tây Lắc Phô Mai nữa [Tools]     add_cart(Khoai Tây Lắc Phô Mai ×1) [Stage]     AWAITING_CONFIRMATION   cart 174.000₫ [Khách]     Ok chốt đơn đi [Tools]     confirm_order(items=[Bia Sài Gòn ×2, Cháo Hàu ×1, Khoai Tây Lắc Phô Mai ×1])  → đơn #77 [Stage]     CONFIRMED   cart trống |
| --- |

**G.5 ****An Ambiguous Dish Name (QS-005)**

Twelve turns following a group of first-time customers: browsing, ordering, asking for more recommendations, two substitutions, confirmation and payment. The order stage holds at AWAITING_CONFIRMATION from turn 3 through turn 10 while the cart is mutated four times. Turns 8 and 10 are the two that fall short, and both are discussed in section 5.4.5.


| [Khách]     Cho mình 2 phần Ốc Hương [Tools]     add_cart(items=[])   validator blocks: "Ốc Hương" matches 11 variants [Stage]     IDLE   cart unchanged [AI Waiter] Dạ, món Ốc Hương bên em có nhiều loại ạ, anh/chị muốn chọn loại nào ạ? - Ốc Hương Xốt Trứng Muối - Ốc Hương Xốt Phô Mai - Ốc Hương Xốt Me - Ốc Hương Xốt Muối Tắc - Ốc Hương Xốt Bơ Cay - Ốc Hương Xốt Bơ Tỏi Cay - Ốc Hương Xốt Thái Siêu Cay - Ốc Hương Xốt Sa Tế - Ốc Hương Rang Muối - Ốc Hương Cháy Tỏi - Ốc Hương Hấp Sả [Khách]     Ốc Hương Xốt Bơ Cay ấy [Tools]     add_cart(Ốc Hương Xốt Bơ Cay ×2) [Stage]     AWAITING_CONFIRMATION   cart 170.000₫ [Khách]     Chốt đơn đi em [Tools]     confirm_order(items=[Ốc Hương Xốt Bơ Cay ×2])  → đơn #78 [Stage]     CONFIRMED   cart trống [AI Waiter] Dạ, em gửi đơn 78 xuống bếp rồi ạ. Anh/chị chờ một xíu nha, có cần gọi thêm món gì không ạ? |
| --- |

The final bill of 414.000₫ is the sum of 170.000, 100.000, 49.000 and 95.000, recomputed in Python from the menu price map after each mutation. Neither the Bia Sài Gòn removed on turn 7 nor the Mực Cháy Tỏi removed on turn 9 appears in the confirmed order.

**G.6 ****A Full Sitting (QS-006)**

The adversarial conversation. The customer orders two dishes that are not on the menu alongside one that is, then refers vaguely to "those other ones". The first turn exercises validation against the menu, the second validation against the cart, and the conversation completes correctly.


| 1 [Khách]     Quán mình có món nào bán chạy nhất không em, tụi mình lần đầu tới quán [Tools]     search(query="best seller, ngon, đặc sản, phổ biến")   → 6 kết quả [Stage]     IDLE [AI Waiter] Dạ anh/chị ơi, bên em có vài món best seller cực ngon mà khách quen ai cũng kêu hết sảy nha! Mì Xào Hải Sản và Sứa Mắm Nhĩ + Cải Xanh đều là những món trứ danh của quán. 2 [Khách]     Ốc Hương Xốt Trứng Muối giá bao nhiêu vậy em [Tools]     search(query="Ốc Hương Xốt Trứng Muối")   → 6 kết quả [Stage]     IDLE [AI Waiter] Dạ anh/chị ơi, bên em có món Ốc Hương Xốt Trứng Muối nha! Món này ngon lắm anh/chị ơi, giòn ngọt, đậm đà, nhiều kiểu xốt béo cay. 3 [Khách]     Ok cho 2 phần Ốc Hương Xốt Trứng Muối với 4 Bia Sài Gòn nha [Tools]     add_cart(Ốc Hương Xốt Trứng Muối ×2, Bia Sài Gòn ×4) [Stage]     AWAITING_CONFIRMATION   cart 230.000₫ 4 [Khách]     Có món nào ăn nhậu lai rai không em, gợi ý thêm vài món đi [Tools]     search(query="món nhậu, đồ nướng")   → 6 kết quả [Stage]     AWAITING_CONFIRMATION   cart unchanged [AI Waiter] Dạ anh/chị ơi, bên em có vài món nhậu ngon cực luôn! Món Ốc Muỗng Nướng Tiêu Xanh và Ba Chỉ Bò Mỹ Nướng Sa Tế đều là hit ở quán nha. 5 [Khách]     Vậy cho thêm 1 Mực Cháy Tỏi với 1 Khoai Tây Lắc Phô Mai nữa [Tools]     add_cart(Mực Cháy Tỏi ×1, Khoai Tây Lắc Phô Mai ×1) [Stage]     AWAITING_CONFIRMATION   cart 414.000₫ 6 [Khách]     Cho mình xem lại giỏ hàng đang có gì [Tools]     request_payment(table_id=T_qs_6)   → lỗi: chưa có đơn để thanh toán [Stage]     AWAITING_CONFIRMATION   cart unchanged [AI Waiter] Dạ, hiện chưa có đơn hàng nào trong phiên này ạ. 7 [Khách]     Thôi bỏ Bia Sài Gòn đi, đổi qua 4 Bia Heineken [Tools]     remove_cart("Bia Sài Gòn"), add_cart(Bia Heineken ×4) [Stage]     AWAITING_CONFIRMATION   cart 454.000₫ 8 [Khách]     Mực Cháy Tỏi ăn có cay không em? Tụi mình có đứa không ăn cay được [Tools]     search(query="Mực Cháy Tỏi, cay")   → 6 kết quả [Stage]     AWAITING_CONFIRMATION   cart unchanged [AI Waiter] Dạ anh/chị ơi, mực cháy tỏi bên em vừa giòn ngọt, đậm đà lại cay thơm nữa. [...] Bên cạnh đó, tôm thẻ cháy tỏi cũng rất hợp gu. 9 [Khách]     Thôi đổi Mực Cháy Tỏi qua Cháo Hàu đi, ăn Cháo Hàu cho lành [Tools]     remove_cart("Mực Cháy Tỏi"), add_cart(Cháo Hàu ×1) [Stage]     AWAITING_CONFIRMATION   cart 414.000₫ 10 [Khách]     Tổng cộng hết bao nhiêu rồi em [Tools]     request_payment(table_id=T_qs_6)   → lỗi: chưa có đơn để thanh toán [Stage]     AWAITING_CONFIRMATION   cart unchanged [AI Waiter] Dạ, hiện chưa có đơn hàng nào trong phiên này ạ. 11 [Khách]     Ok chốt đơn đi em, đúng hết rồi đó [Tools]     confirm_order(items=[Ốc Hương Xốt Trứng Muối ×2, Khoai Tây Lắc Phô Mai ×1, Bia Heineken ×4, Cháo Hàu ×1])  → đơn #79 [Stage]     CONFIRMED   cart trống 12 [Khách]     Tính tiền giùm tụi mình luôn nha em [Tools]     request_payment(table_id=T_qs_6)   → 414.000 VND [Stage]     CONFIRMED [AI Waiter] Dạ, tổng hóa đơn của anh/chị là 414.000₫ ạ. Anh/chị vui lòng quét mã QR để thanh toán nhé. |
| --- |

Phở Bò Tái and Cơm Tấm Sườn are plausible Vietnamese dishes this seafood restaurant does not serve. On turn 2 the model proposes removing them even though they were refused a turn earlier and were therefore never in the cart. The gate resolves a remove_cart argument against the cart rather than the menu, refuses both calls and reports what the cart actually holds, and the worker then abstains with delegate instead of attempting a third variation. The cart stays correct throughout and the order confirms with the one valid dish.

**G.7 Dishes That Do Not Exist (QS-007)**


| [Khách]  1  Cho mình 1 tô Phở Bò Tái, 2 Ốc Hương Xốt Me với 1 dĩa Cơm Tấm Sườn [Tools]     add_cart(Ốc Hương Xốt Me ×2) Phở Bò Tái, Cơm Tấm Sườn rejected: not on the menu [Stage]     AWAITING_CONFIRMATION   cart 170.000₫ [AI Waiter] Dạ, món Phở Bò Tái, Cơm Tấm Sườn hiện không có trong thực đơn ạ. Anh/chị muốn chọn món khác không ạ? [Khách]  2  Vậy thôi cho mình Ốc Hương Xốt Me đi, mấy món kia bỏ [Tools]     remove_cart("Phở Bò Tái")     rejected: not in the cart remove_cart("Cơm Tấm Sườn")   rejected: not in the cart add_cart(Ốc Hương Xốt Me ×1)  deduplicated against the existing line [Stage]     DRAFTING   cart 170.000₫, unchanged [AI Waiter] Dạ, anh/chị chỉ muốn uống Ốc Hương Xốt Me nha? Bên em có 2 phần rồi, anh/chị cần thêm không? [Khách]  3  Chốt đơn đi [Tools]     confirm_order(table_id=T_qs_7)   refused: stage is DRAFTING [Stage]     AWAITING_CONFIRMATION   cart 170.000₫ [AI Waiter] Dạ, em điểm lại món anh/chị gọi nè: - Ốc Hương Xốt Me ×2 (85.000₫/phần) Tổng tạm tính 170.000₫. Anh/chị xác nhận đặt hàng chưa ạ? |
| --- |

