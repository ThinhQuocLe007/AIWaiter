# Chapter 5 Remediation Plan — Vòng 2

**Cập nhật:** 2026-07-27, sau khi kiểm chứng vòng 1.
**Trạng thái tổng:** code đã sửa xong và **đã verify bằng cách chạy thật**. Chương thì **chưa cập nhật một con số nào**. Các file `05-0*.md` sửa lần cuối 16:49-16:55, code sửa 17:38-18:13, nên toàn bộ prose đang mang số cũ.

**Việc còn lại chia làm bốn khối:**
- **Khối D**: viết lại prose theo số mới. Đây là khối lớn nhất và là đường găng.
- **Khối E**: sáu vấn đề mới phát hiện trong lúc verify.
- **Khối F**: lỗi phân loại mảnh (vụ Bia Sài Gòn). Đây là finding mới, nghiêm trọng.
- **Khối G**: các lần chạy còn thiếu để đủ protocol N = 5.

---

# PHẦN 0. Trạng thái vòng 1

Tất cả đã chạy lại và xác nhận vào 2026-07-27 18:20-18:32.

| ID | Nội dung | Code | Verify | Prose |
|----|----------|:----:|:------:|:-----:|
| A1 | Retrieval latency: percentile thật + warm-up | ✅ | ✅ p50 RRF ≥ FAISS | ❌ |
| A2+A3 | Tách 3 metric multi-intent | ✅ | ✅ runs=1 | ❌ |
| A4 | Token-align resolver | ✅ | ✅ 70/70, 25/25, **30/30** | ❌ |
| A5 | Sửa note CD-023 | ✅ | ✅ hết mâu thuẫn | ❌ disclosure chưa vào chương |
| A6 | Bỏ khung 14B | ❌ | | ❌ `05-01:24` vẫn ghi 14B |
| B1 | Mở rộng context set | ✅ | ✅ **p = 1.45e-4** | ❌ |
| B3 | Scorecard trung thực về 86.2% | ❌ | | ❌ |
| B4 | Bổ sung chi phí rewriter | ❌ | | ❌ |
| B5 | Siết luật boundary marker | ✅ | ✅ detection giữ 85.2% | ❌ |
| B6 | Thêm `--runs` cho 4 script | ✅ | ✅ đã chạy lại 1 lần mỗi cái | ❌ |
| B7 | bench_api n=100 | ✅ | ✅ | ❌ |
| B8 | Thống nhất six/seven | ❌ | | ❌ |
| C1 | Per-node latency | ✅ | ✅ bảng đầy đủ | ❌ |
| C2 | Cold start | ❌ | `cold_start_s` vẫn `None` | ❌ |
| C3 | Validator FP rate | ✅ | ⚠️ ra 0/0, mẫu số hỏng | ❌ |
| C4 | WebSocket propagation | ✅ | ⚠️ chưa chạy | ❌ |
| C5 | Bỏ cột GPU memory | ❌ | | ❌ |

Ba mục có kết quả vượt kỳ vọng và đáng nâng thành kết quả có tên trong chương: **A4** (28/30 lên 30/30), **B1** (p từ 0.057 xuống 1.45e-4), **C1** (tầng deterministic chỉ tốn 1.3% ngân sách một lượt).

**Vòng chạy 2026-07-27 19:20 đến 19:35** đã làm mới bốn experiment vốn stale vì chạy trên build trước 18:08. Kết quả ở §1.7 đến §1.10. Ba lần chạy bị Ollama chết giữa chừng trên máy 8 GB và đã chạy lại; mọi số cuối cùng đều có `connection errors = 0`. Vòng này sinh ra **một cảnh báo nghiêm trọng mới (mục H1)** và **một defect mới (mục E7)**.

---

# PHẦN 1. SỔ SỐ LIỆU

Đây là bảng tra cứu khi viết lại chương. Mọi con số dưới đây đã chạy lại ngày 2026-07-27, file kết quả ghi kèm.

## 1.1 Retrieval — `retrieval_full_20260727_182117.json`

**Bảng 5.6 mới.** Bốn cột chất lượng **không đổi** so với bản cũ, chỉ cột latency đổi.

| Mode | P@5 | R@5 | MRR | Hit Rate | p50 | p95 |
|------|:----:|:----:|:----:|:--------:|:----:|:----:|
| BM25 only | 0.367 | 0.719 | 0.720 | 0.875 | **0.5 ms** | **0.8 ms** |
| FAISS only | 0.315 | 0.523 | 0.663 | 0.792 | **6.9 ms** | **8.9 ms** |
| **RRF fusion** | **0.400** | **0.743** | **0.751** | **0.917** | **8.9 ms** | **10.9 ms** |

**Bảng 5.7 (per-difficulty, RRF): không đổi.** easy n=8: 0.425 / 0.865 / 1.000 / 1.000. medium n=9: 0.444 / 0.907 / 0.722 / 1.000. hard n=7: 0.314 / 0.391 / 0.505 / 0.714.

**Bảng 5.8 (gatekeeper): không đổi.** Both 20, lexical-only 3, semantic-only 0, rejected 1, admitted 23 = 95.8%.

## 1.2 Validator — `name_resolution_20260727_182104.json`, `ambiguity_20260727_182110.json`, `e2e_out_of_menu_report_20260727_182805.json`

| Phép đo | Cũ | **Mới** |
|---|---|---|
| Name resolution | 70/70 | **70/70** (không đổi) |
| Ambiguity | 25/25 | **25/25** (không đổi) |
| **Out-of-menu** | 28/30 = 93.3% | **30/30 = 100%** |
| Validator FP rate | không báo cáo | 0.000 nhưng **mẫu số = 0**, xem E1 |

## 1.3 Router — `mlp_router_eval_20260727_182213.json`, `..._182324.json`

**Context-dependent (mục B1), tập mới n = 123, 62 nhóm câu, 61 nhóm đổi nhãn theo stage:**

| | Cũ (n=70) | **Mới (n=123)** |
|---|---|---|
| Có context | 49/70 = 70.0% | **75/123 = 61.0%**, Wilson [52.1, 69.1] |
| Không context | 41/70 = 58.6% | **59/123 = 48.0%**, Wilson [39.3, 56.7] |
| Chênh lệch | +11.4 pp | **+13.0 pp** |
| McNemar | b=11, c=3, **p = 0.057** | b=17, c=1, **p = 1.45 × 10⁻⁴** |
| Nhóm vô dụng | 10/36 | **1/62** |

**Single-intent: 94.0% (140/149), không đổi.**

**Multi-intent detection: 23/27 = 85.2%, không đổi.** By boundary 21, by low confidence 5. Pseudo control 3, false alarm 2.

**Tỉ lệ nổ rewriter nhầm (mục B5):**

| Tập | Luật cũ | **Luật mới** |
|---|---|---|
| single_intent (149) | 16 = 10.7% | **10 = 6.7%** |
| context_dependent | 5/70 = 7.1% | **0/123 = 0%** |
| multi_intent_detection | 23/30 = 76.7% | **23/30 = 76.7%** |

Luật cũ và luật mới **bất đồng 0/30 case** trên tập detection. Nên 85.2% giữ nguyên cả về số lẫn thành phần, không phải trùng hợp.

## 1.4 Multi-intent — `multi_intent_20260727_183115.json` (⚠️ runs = 1, phải chạy lại N=5)

| Metric | Cũ (trộn lẫn) | **Mới (tách 3 tầng)** |
|---|---|---|
| routing_precision | không đo | **0.940** |
| execution_rate | không đo | **0.767** |
| **verbalisation_rate** | 0.725 | **0.800** |
| **fully_verbalised** | 0.576 | **0.760** |
| coverage_of_expected | 0.747 | 0.753 |
| verbalisation strict | 0.625 | 0.720 |
| fully_verbalised strict | 0.456 | 0.680 |

Phụ trợ: generic_error_reply 4 lượt, retry_apology 2 lượt, validator_rejected 5 lượt.

Theo số intent đã chạy trong lượt: 0 intent → 2 lượt (0.0%), 1 intent → 12 lượt (83.3%), 2 intent → 11 lượt (90.9%).

**Diễn giải bắt buộc đưa vào chương:** khâu yếu nhất **không phải** response layer (0.800) mà là **execution (0.767)**. Gần một phần tư intent được xếp hàng không hề sinh ra tool call nào.

## 1.5 Latency — `latency_20260727_183204.json` (n-runs 5, n = 60)

**Bảng 5.10 mới (theo lớp intent):**

| Intent | p50 | p95 | n |
|---|:---:|:---:|:--:|
| ORDER | 1.013 s | 1.691 s | 10 |
| ORDER_CONFIRM | 2.651 s | **6.126 s** | 5 |
| SEARCH | 1.786 s | 2.334 s | 15 |
| PAYMENT | 0.047 s | 2.414 s | 10 |
| CHAT | 0.879 s | 2.604 s | 10 |
| Multi-intent | 1.855 s | 2.035 s | 10 |
| **Toàn bộ** | **1.703 s** | **2.703 s** | 60 |

Toàn cục **cải thiện** so với 2.15 / 3.40 cũ, nhờ B5 bớt nổ rewriter. Nhưng ORDER_CONFIRM p95 = 6.126 s **vượt trần 5 s**, xem E2.

**Bảng mới (per-node), đây là kết quả mạnh nhất thu được ở vòng này:**

| Node | p50 | p95 | % ngân sách | n |
|---|:---:|:---:|:---:|:--:|
| order_worker | 1.052 s | 2.999 s | **43.8%** | 27 |
| response_node | 0.009 s | 1.171 s | **29.9%** | 60 |
| search_worker | 0.823 s | 1.269 s | 14.6% | 15 |
| classifier_router | 0.013 s | 0.828 s | 10.3% | 60 |
| tools | 0.023 s | 0.043 s | 1.1% | 44 |
| validator | 0.001 s | 0.003 s | 0.1% | 45 |
| state_outcome | 0.001 s | 0.002 s | 0.1% | 60 |
| state_updater | 0.001 s | 0.001 s | 0.0% | 49 |
| payment_dispatch | 0.001 s | 0.001 s | 0.0% | 13 |
| chat_worker | 0.001 s | 0.002 s | 0.0% | 10 |

**Hai điều rút ra, cả hai nên viết thành câu có trọng lượng:**

1. Toàn bộ tầng deterministic (validator, máy trạng thái, số học giỏ hàng, state management, tool execution) chiếm **khoảng 1.3%** ngân sách một lượt. 98.7% còn lại là gọi LLM. Đây là bằng chứng trực tiếp nhất trong cả chương cho luận điểm kiến trúc: **tầng an toàn gần như miễn phí**.
2. `classifier_router` p50 = 0.013 s nhưng p95 = 0.828 s. Đó chính là rewriter nổ, đo được từ một phép đo **hoàn toàn độc lập** với con số 0.98 s lấy từ file multi-intent. Hai nguồn khớp nhau, nên mục B4 có hai bằng chứng chứ không phải một.

## 1.6 API — `bench_api_20260727_183144.json` (n = 100 mỗi endpoint)

**Bảng 5.11 mới:**

| Endpoint | p50 | p95 | p99 |
|---|:---:|:---:|:---:|
| GET /menu | 1.0 | 1.5 | 1.6 |
| GET /tables | 1.0 | 1.4 | 1.6 |
| GET /tables/{id} | 0.9 | 1.3 | 1.6 |
| POST /seatings | 0.9 | 1.7 | 2.0 |
| GET /orders | 2.4 | 2.9 | 4.0 |
| POST /orders | 0.7 | 1.2 | **9.0** |
| GET /payments | 1.0 | 1.5 | 1.9 |
| GET /robots | 0.9 | 1.4 | 1.5 |
| GET /tasks | 1.0 | 1.4 | 1.7 |
| GET /layout | 0.7 | 1.0 | 1.2 |
| POST /voice/event | 0.7 | 1.0 | 1.3 |
| POST /voice/listen | 0.7 | 0.8 | 1.2 |

Câu "every endpoint responds within 4 ms at the 99th percentile" **không còn đúng**: `POST /orders` có p99 = 9.0 ms so với p50 0.7 ms, đuôi gấp 13 lần. Ở n = 10 cái đuôi này vô hình. Xem E5.

## 1.7 Six-arm router ablation — `router_arms_20260727_192028.json`

**Pool đổi từ 304 sang n = 360**, vì `context_dependent_eval.json` đã tăng từ 70 lên 123 case. Mọi con số trong bảng 5.2 cũ đều không dùng được nữa.

**Bảng 5.2 mới:**

| Arm | Hệ thống | Accuracy | 95% Wilson CI | p50 | p95 | b/c vs E | p |
|-----|----------|----------|--------------:|----:|----:|:---:|---:|
| A | Centroid (semantic only) | 251/360, 69.7% | 64.8–74.2% | 9 ms | 11 ms | 61/22 | 2.2 × 10⁻⁵ |
| B | SLM only (qwen2.5:3b) | 270/360, 75.0% | 70.3–79.2% | 186 ms | 199 ms | 37/17 | 0.0091 |
| C | Hybrid semantic → SLM (hệ cũ) | 246/360, 68.3% | 63.4–72.9% | 9 ms | 669 ms | 66/22 | 2.9 × 10⁻⁶ |
| D | MLP, bỏ context features | 274/360, 76.1% | 71.4–80.2% | 8 ms | 9 ms | 18/2 | 0.00040 |
| **E** | **MLP + context (đề xuất)** | **290/360, 80.6%** | **76.2–84.3%** | **8 ms** | **9 ms** | tham chiếu | |
| F | LLM zero-shot (qwen2.5:7b) | 272/360, 75.6% | 70.9–79.7% | 195 ms | 213 ms | 35/17 | 0.0175 |

**Per-class arm E (n = 360):**

| Lớp | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| ORDER | 0.757 | 0.883 | 0.815 | 120 |
| SEARCH | 0.803 | 0.792 | 0.797 | 72 |
| PAYMENT | 0.946 | 0.964 | 0.955 | 55 |
| CHAT | 0.796 | 0.655 | 0.718 | 113 |

Tỉ lệ latency giờ là **24 lần** (195 / 8), không phải 25 lần.

**Cảnh báo: xem mục H1 trước khi viết bất kỳ câu nào về arm F.**

## 1.8 Validator ablation — `validator_ablation_validator_on_20260727_192238.json` và `..._off_20260727_192947.json`

**Bảng 5.4 mới (n = 41 scenario mỗi nhánh, 1 run, connection errors = 0 ở cả hai):**

| Điều kiện | Pass rate | Off-menu items vào cart tools | Bad `confirm_order` |
|-----------|:---------:|:-----------------------------:|:-------------------:|
| Validator **ON** | 92.68% (38/41) | **0** | **0** |
| Validator **OFF** | 95.12% (39/41) | **32** | **7** |

So với bản cũ (0 vs 31, và 1 vs 8): claim an toàn **mạnh hơn**, và nhánh ON giờ **sạch hoàn toàn** ở cột bad confirm.

**Đảo chiều mới phải giải thích, không được giấu:** nhánh OFF **pass nhiều hơn** nhánh ON (39/41 so với 38/41). Bản cũ hai nhánh bằng nhau. Đây thực ra củng cố luận điểm: pass rate đo việc chọn tool và luồng hội thoại, không đo tính đúng của **đối số**. Bỏ validator thì agent trôi chảy hơn, pass thêm một scenario, đổi lại 32 món không tồn tại vào giỏ và 7 đơn xác nhận chứa món nhà bếp không nấu được. Câu đáng viết: validator có thể **làm mất một scenario pass** mà vẫn là thứ duy nhất chặn dữ liệu sai vào sổ.

**Danh sách món lọt khi tắt validator** (dùng làm ví dụ minh hoạ trong chương, đều là món có thật ngoài đời nhưng không có ở quán ốc này): Pizza Hải Sản, Sushi Cá Hồi, Bia Corona, Bún Bò Huế, Sườn Nướng BBQ, Rượu Vang Đỏ, Kem Dừa, Cua Rang Me, Tôm Hùm Baby, Trà Sữa Trân Châu, Cà Phê Sữa Đá, Gỏi Cá Trích, Chè Thái, Bánh Flan.

## 1.9 Qualitative E2E — `e2e_qualitative_20260727_192353.json`

**5/7 pass**, cùng tỉ lệ cũ nhưng **QS-007 đổi nội dung hẳn**.

| ID | Kịch bản | Kết quả |
|---|---|---|
| QS-001 | two_dishes_confirm_pay | PASS |
| QS-002 | browse_then_select | PASS |
| QS-003 | order_and_pay_same_turn | PASS |
| QS-004 | change_mind_mid_order | PASS |
| QS-005 | ambiguous_dish_clarification | PASS |
| QS-006 | group_dinner_full_service | FAIL, đúng 1 assertion ở turn 2 |
| QS-007 | off_menu_handling | FAIL, đúng 1 assertion ở turn 2 |

**QS-007 lần chạy mới, transcript để thay vào §5.4.5:**

```
[1] Cho mình 1 tô Phở Bò Tái, 2 Ốc Hương Xốt Me với 1 dĩa Cơm Tấm Sườn
    add_cart(Ốc Hương Xốt Me ×2)
    stage AWAITING_CONFIRMATION   cart 170.000₫
    AI: "Dạ, món Phở Bò Tái, Cơm Tấm Sườn hiện không có trong thực đơn ạ."

[2] Vậy thôi cho mình Ốc Hương Xốt Me đi, mấy món kia bỏ
    remove_cart(Phở Bò Tái), remove_cart(Cơm Tấm Sườn),
    remove_cart(Lẩu Thái), add_cart(Ốc Hương Xốt Me ×1)
    stage AWAITING_CONFIRMATION   is_valid=False   cart VẪN 170.000₫
    AI: ba lần "có lỗi khi xử lý đơn"

[3] Chốt đơn đi
    confirm_order  ->  stage CONFIRMED, đơn 76, cart 170.000₫
```

**So với bản trong chương:**

| | Chương đang viết | Lần chạy mới |
|---|---|---|
| Turn 2, số tool call | 6 (4 remove + add + remove) | **4** (3 remove + 1 add) |
| Giỏ sau turn 2 | **rỗng** | **giữ nguyên 170.000₫** |
| Turn 3 | `clear_cart`, is_valid=False | **`confirm_order` thành công** |

Câu *"The cart goes from correct to empty, and the customer receives three stacked apologies"*: vế sau vẫn đúng, **vế trước không còn đúng**. Luận điểm kiến trúc vẫn sống vì `remove_cart("Lẩu Thái")` là món có thật trong menu mà khách chưa từng gọi và validator vẫn cho qua, nhưng **hậu quả nhẹ hơn hẳn**, nên phải hạ giọng đoạn văn cho đúng mức.

Đây cũng là bằng chứng sống cho lý do §5.2.3 đòi N = 5: cùng một input, một lần chạy làm rỗng giỏ, lần khác không.

**QS-006** vẫn fail đúng một assertion ở turn 2 (`delegate` thay vì `search` cho câu hỏi giá). Chương đã nhận định đây là **assertion quá chặt chứ không phải lỗi hệ thống**. Đề nghị nới assertion để chấp nhận cả hai đường, khi đó QS-006 pass và tỉ lệ thành **6/7**.

## 1.10 Delegate — `delegate_baseline_20260727_193448.json`

**3.33% (3/90 lượt)**, connection errors = 0. Trùng con số cũ, nên §5.4.2 phần delegate **không phải sửa số**, chỉ cần đổi tên file kết quả nếu có trích.

Quan sát phụ có giá trị cho §5.4.3: log của lần chạy này có nhiều dòng
```
SEARCH worker produced no tool_calls on first attempt — retrying with forced instruction
ORDER worker produced no tool call despite tool_choice='any'
```
Đây chính là cơ chế đứng sau `execution_rate = 0.767` ở §1.4, quan sát được từ một experiment hoàn toàn khác. Hai nguồn độc lập cùng chỉ vào một chỗ.

---

# PHẦN 1B. KHỐI H — CẢNH BÁO VỀ CLAIM ĐẦU BẢNG

## H1. Đừng claim "MLP tốt hơn LLM 7B" trên pool gộp

**Mức nguy hiểm: rất cao.** Đây là claim đầu bảng của luận văn.

Nhìn bảng 5.2 mới thì E vs F đã từ **p = 0.200 "không phân biệt được"** thành **p = 0.0175 "tốt hơn có ý nghĩa thống kê"**. Rất hấp dẫn. Nhưng tách pool ra kiểm thì nó không đứng vững:

```
subset             n      E            F        b/c      p
router            39   38  97.4%   36  92.3%    3/1    0.6250
single           118  110  93.2%  106  89.8%    7/3    0.3438
semantic          71   62  87.3%   66  93.0%    3/7    0.3438
context           20   15  75.0%   12  60.0%    4/1    0.3750
context_dep      112   65  58.0%   52  46.4%   18/5    0.0106   <-- tập MỚI viết hôm nay
ALL              360  290  80.6%  272  75.6%   35/17   0.0175

Bỏ context_dep mới ra:  n=248  E 90.7%  F 88.7%  b/c=17/12  p = 0.4583
```

**Toàn bộ lợi thế của E so với F đến từ 112 case `context_dep` viết trong ngày 2026-07-27.** Trên 248 case còn lại, hai arm không phân biệt được (p = 0.46). Trên tập `semantic`, LLM còn nhỉnh hơn (93.0% so với 87.3%).

Đây đúng là rủi ro số 2 đã ghi ở mục B1: viết case mới sau khi biết model sai ở đâu là một dạng thiên lệch. Lúc đó nó chỉ ảnh hưởng một ablation nội bộ, giờ nó ảnh hưởng claim đầu bảng.

**Cách viết được đề nghị**, vừa trung thực hơn vừa đúng trọng tâm đóng góp hơn:

> Trên các phát ngôn thông thường, bộ phân loại ngang với một LLM 7B (p = 0.46) ở tốc độ nhanh hơn 24 lần. Trên các phát ngôn mà trạng thái hội thoại quyết định nhãn, nó tốt hơn LLM có ý nghĩa thống kê (p = 0.011). Đó chính xác là loại phát ngôn mà các đặc trưng ngữ cảnh được thêm vào để xử lý.

Câu này miễn nhiễm với câu hỏi "pool gồm những gì, ai viết, viết lúc nào". Nếu claim trên pool gộp, người phản biện chỉ cần hỏi một câu là claim sụp.

**Hai kết quả giữ nguyên giá trị bất kể chọn đường nào**, và đây mới là đóng góp cốt lõi:
- **D vs E: p = 0.00040** (context features có tác dụng)
- **E thắng cả A, B, C**, đều p < 0.01

**Việc phải làm:** trong §5.4.1 và bảng 5.2, báo cáo bảng phân rã theo subset ở trên, không chỉ dòng ALL. Trong §5.6.4 thêm một mục Threats nói rõ tập `context_dep` được mở rộng sau khi đã quan sát lỗi của model, và vì thế phép so sánh E vs F được báo cáo tách theo subset thay vì gộp.

---

# PHẦN 2. KHỐI D — VIẾT LẠI PROSE

Đây là đường găng. Chia theo file, theo thứ tự nên làm.

## D1. `05-04-ai-agent-experiments.md` §5.4.4 Knowledge Retrieval

- **Bảng 5.6** (dòng 437-441): thay cột `p50 latency` bằng hai cột `p50` và `p95`, số lấy từ §1.1 trên.
- **Dòng 454-457**: xoá cả đoạn. Đoạn cũ giải thích 422 ms bằng chuyện "embedding computed once and reused", đó là hợp lý hoá một artefact. Viết lại theo hướng: lane lexical trả lời trong khoảng nửa mili giây, việc mã hoá truy vấn cho lane ngữ nghĩa cộng thêm khoảng 8 ms, và tổng 8.9 ms là không đáng kể so với ngân sách một lượt 1.7 giây. **Không được nhắc lại con số 422 ms ở bất kỳ đâu.**
- Bảng 5.7 và 5.8 giữ nguyên.

## D2. `05-04` §5.4.2 Action Validation and Safety

- **Dòng 306-317** (Out-of-Menu Robustness): 28/30 thành **30/30**. Viết lại đoạn mô tả hai ca fail, vì chúng không còn nữa.
- **Thêm một đoạn mới** kể lại defect đã tìm và đã sửa. Nội dung: tầng khớp substring vốn so sánh ở mức ký tự nên `gà rán` khớp vào `Chân Gà Rang Muối Hồng Kông`, khách gọi gà rán thì nhận chân gà, và không tầng nào bắt được vì tên món đó có thật trong menu. Sửa bằng cách yêu cầu khớp trọn token. Giữ nguyên 70/70 name resolution và 25/25 ambiguity, đưa out-of-menu lên 30/30. **Đây là điểm cộng, không phải điểm trừ**: nó chứng minh quy trình đánh giá phát hiện được lỗi thật chứ không chỉ xác nhận cái đã biết.
- **Dòng 252-263**: câu "neither mechanism guesses" giờ mới đúng. Bổ sung một câu nói rõ tầng substring yêu cầu khớp trọn token và vì sao.

## D3. `05-04` §5.4.1 Intent Classification and Routing

- **Dòng 103-137** (Context-Dependent Accuracy): thay toàn bộ số theo §1.3. Điểm quan trọng: accuracy tuyệt đối **giảm** (70.0% xuống 61.0%) trong khi effect size **tăng** và p đạt significance. Phải giải thích thẳng: tập mới bỏ đi các nhóm không kiểm được gì và thêm case khó hơn, nên con số tuyệt đối thấp hơn nhưng phép đo sắc hơn. Nếu không giải thích, người đọc sẽ tưởng hệ thống tệ đi.
- **Dòng 123-130** ("Two limitations"): viết lại. Cả hai giới hạn cũ đều đã xử lý: cỡ mẫu đã đủ lực thống kê, và việc re-partition đã thực hiện. Giữ lại phần mô tả re-partition như một quyết định thiết kế.
- **Thêm disclosure A5** ngay sau đoạn báo cáo accuracy: ba nhãn CD-023, CD-053, CD-055 được sửa sau khi prediction đã thấy được, prediction không đổi giữa hai lần chạy, con số tăng từ 65.7% lên 70.0% ở tập cũ. Ba câu là đủ.
- **Dòng 147-162** (Multi-Intent Detection): bổ sung luật boundary marker mới (marker phải nằm giữa hai mệnh đề, mỗi bên ít nhất 2 token) và ablation luật cũ vs luật mới theo §1.3.
- **Bảng 5.2** hàng D: cột `b/c vs E` và `p` phải cập nhật theo tập context mới. **Cần chạy lại `eval_router_arms.py` trước** (xem G3), vì pool 304 case có chứa context set cũ.

## D4. `05-04` §5.4.3 Multi-Intent Execution and Verbalisation

**Đây là phần viết lại nhiều nhất trong cả chương.**

- **Dòng 344-418**: viết lại gần như toàn bộ. Kết quả không còn là một con số 57.6% mà là ba con số ở ba tầng: routing_precision 0.940, execution_rate 0.767, verbalisation_rate 0.800.
- **Bảng 5.5** ("Residual verbalisation losses by pattern"): thay hẳn. Bảng cũ phân rã theo **cặp intent**, bảng mới phải phân rã theo **tầng gây lỗi**.
- **Dòng 406-412** ("It is worth recording what the cause is not..."): xoá. Đoạn này đang bảo vệ một chẩn đoán mà dữ liệu bác bỏ.
- **Dòng 415**: câu "the system executes more than it says" phải sửa. Dữ liệu nói ngược lại: hệ thống **nói ra 80% những gì nó chạy**, còn cái nó không làm được là **chạy** những gì đã xếp hàng.
- **Thêm đoạn mới về phương pháp**: giải thích vì sao phải tách ba metric. Mẫu số cũ là `routed` (những gì router xếp hàng) chứ không phải `executed`, nên một con số đang trộn lỗi của ba tầng kiến trúc. Đây là một đóng góp về phương pháp đo, đáng viết ra chứ không nên giấu.

## D5. `05-04` §5.4.6 Agent Latency and Cost

- **Bảng 5.10** (dòng 858-868): thay số theo §1.5.
- **Dòng 870**: "Median turn latency is 2.15 s and the 95th percentile is 3.40 s" thành 1.703 s và 2.703 s. **Thêm câu về ORDER_CONFIRM p95 = 6.126 s vượt trần**, xem E2.
- **Dòng 877-879**: xoá câu "A per-node breakdown ... was not instrumented and is noted as a gap in §5.6.4". Thay bằng **bảng per-node mới** và hai kết luận ở §1.5.
- **Thêm đoạn chi phí rewriter (mục B4)**: đường fast path 0.013 s, đường rewriter 0.828 s ở p95, nổ trên 6.7% câu đơn ý sau khi siết luật (10.7% trước khi siết). Chi phí routing amortised do đó vào khoảng 60 ms chứ không phải 9 ms.
- **Dòng 883-885**: sửa câu "it is spent on every turn". Nói rõ 9 ms là chi phí của **tầng phân loại**, còn chi phí routing đầu-cuối bao gồm cả rewriter khi nó nổ. Ghi chú thêm rằng so sánh 9 ms vs 229 ms vẫn hợp lệ ở tư cách component ablation, vì arm F cũng chỉ sinh một nhãn và cũng cần rewriter cho câu đa ý.

## D6. `05-05-backend-web-experiments.md` §5.5.1

- **Bảng 5.11** (dòng 22-35): thay số theo §1.6, ghi rõ n = 100.
- **Dòng 37**: câu "Every endpoint responds within 4 ms at the 99th percentile" **không còn đúng**. Sửa và thêm một câu về đuôi của `POST /orders`.

## D7. `05-06-results-summary.md`

- **Bảng 5.14 hàng 1** (objective 1): thêm cả ba con số 94.0% / 86.2% / 61.0% kèm chú thích mỗi con số đo trên tập nào và vì sao không so sánh được với nhau (mục B3).
- **Bảng 5.14 hàng 3** (objective 3): giữ verdict "met" nhưng **bắt buộc thêm câu về phạm vi**: đảm bảo là về tư cách thành viên của menu, không phải về việc món vào giỏ đúng là món khách gọi. Nhắc tới defect resolver đã sửa như bằng chứng cho việc phân biệt hai điều đó.
- **Bảng 5.14 hàng 5** (latency): 2.15/3.40 thành 1.703/2.703.
- **Bảng 5.14 hàng 7** (multi-intent): 57.6% thành ba con số mới.
- **Bảng 5.15 hàng validator**: cập nhật, 30/30.
- **Bảng 5.15 hàng "Response generation"**: hàng này sai, phải tách thành ba hàng theo ba tầng.
- **Dòng 71-72**: **xoá câu "The weakest link is therefore the response and rewriting layer."** Kết luận mới: khâu yếu nhất là **execution** (0.767), và nguyên nhân gốc phần lớn nằm ở việc phân loại mảnh sau khi rewriter cắt câu (khối F).
- **§5.6.4 Threats to Validity**:
  - xoá mục "Underpowered comparisons" (dòng 120-125), p giờ là 1.45e-4
  - xoá mục về per-node latency chưa đo (dòng 136-138)
  - mục "Single runs" thu hẹp lại sau khi chạy G1-G3
  - mục "Model configuration" xoá nếu quyết A6
- **B8**: thống nhất mẫu số six/seven. Dòng 24 ghi "four of six", dòng 82 ghi "four of six", nhưng chỗ khác nói "seven". Chọn một cách nói và giữ nhất quán.

## D8. `05-02-evaluation-design.md`

- **§5.2.1 bảng dataset**: context-dependent từ 70 lên **123 case, 62 nhóm**.
- **§5.2.2** (dòng 96-99): định nghĩa "Multi-intent verbalisation rate" phải nói rõ mẫu số là intent **đã chạy**, và phải giới thiệu hai metric mới là routing precision và execution rate.
- **§5.2.2**: bổ sung định nghĩa validator false-positive rate cho khớp với cái thật sự báo cáo (sau khi sửa E1).
- **§5.2.3** (dòng 118-127): cập nhật danh sách experiment đạt/không đạt N=5 sau khi chạy G1-G3.
- **§5.2.4 bảng inventory**: bổ sung flag `--runs` vào các lệnh.
- **§5.2.4 dòng 173-174**: **bỏ câu** *"The result file backing each table is cited in the text so that a reader can trace any number to the run that produced it."* Chương không trích dẫn file kết quả ở bất kỳ đâu (đếm được: 0 lần trong `05-04`, `05-05`, `05-06`), nên câu này mô tả một việc không xảy ra. Quyết định đã chốt: `collected-results.md` là **sổ nội bộ**, không lên luận văn, và chương không trích file. Bảng inventory ngay phía trên cộng với dòng nói mọi script ghi ra file timestamped trong `evals/results/` đã đủ cho tính tái lập.

## D9. `05-01-system-under-test.md`

Chỉ làm nếu quyết A6: bỏ đoạn 14B ở dòng 24-37, khai thẳng 7B kèm lý do.

---

# PHẦN 3. KHỐI E — VẤN ĐỀ MỚI PHÁT HIỆN KHI VERIFY

## E1. `validator_FP = 0/0`, mẫu số bằng không

**Bằng chứng:** log out-of-menu in ra `validator_FP=0/0`, và report ghi `validator_false_positive_rate: 0.000`.

**Vấn đề:** mẫu số bằng 0 không phải bằng chứng cho tỉ lệ 0%. Nó có nghĩa là **không đếm được item hợp lệ nào được đề xuất**, tức là biến `valid_items_proposed` không bao giờ tăng.

**Cách sửa:** trong `evals/scripts/eval_out_of_menu.py` quanh dòng 270-290, `valid_proposed` phải đếm mọi item nằm trong `scenario["valid_items"]` mà LLM có đề xuất trong tool call, kể cả khi nó đi lọt. Hiện tại nhiều khả năng chỉ đếm ở nhánh bị chặn. Kiểm bằng cách in ra `valid_items_proposed` cho scenario OOM-030 (negative control toàn món hợp lệ): nó phải bằng 3, không phải 0.

**Mức nguy hiểm: cao.** §5.2.2 định nghĩa metric này rất kỹ, kể cả lý do vì sao phải đọc cặp đôi với catch rate. Báo cáo 0.000 từ mẫu số 0 còn tệ hơn không báo cáo.

## E2. ORDER_CONFIRM p95 = 6.126 s, vượt trần 5 giây

**Bằng chứng:** `latency_20260727_183204.json`, ORDER_CONFIRM p50 2.651 s, p95 **6.126 s**, n = 5. Lần đo trước là 4.89 s.

**Vấn đề:** §5.4.6 hiện viết "both inside the five-second voice interaction budget". Toàn cục (2.703 s) vẫn trong ngân sách, chỉ lớp ORDER_CONFIRM vượt.

**Cách sửa:** hai bước.
1. Chạy lại với n-runs lớn hơn cho riêng lớp này. n = 5 nên đây có thể là một draw. Nhưng cả hai lần đo đều cho p95 gần hoặc quá 5 s, nên nhiều khả năng là thật.
2. Nếu vẫn vượt: **không được viết "both inside the budget" nữa**. Viết thẳng rằng lượt xác nhận đơn là lượt nặng nhất, p95 vượt trần, và nguyên nhân là `confirm_order` phải ghi database cộng đẩy kitchen display bên cạnh lời gọi LLM. Objective 5 ở §1.3 nói "within five seconds **at the median**", nên objective vẫn đạt. Nhưng phải nói rõ chỗ vượt.

**Mức nguy hiểm: cao.** Đây là claim dễ bị hỏi và hiện chương đang phát biểu mạnh hơn dữ liệu.

## E3. `eval_mlp_router.py:52` có bản sao riêng của luật boundary marker

**Vấn đề:** `_BOUNDARY_RE` và `_has_boundary_markers` trong script eval là bản sao y hệt của bản trong `classifier_router_node.py`. Hiện giống nhau, nên kết quả đúng. Nhưng hai bản sẽ trôi khỏi nhau, và khi đó eval sẽ đo một luật không phải luật đang chạy.

**Cách sửa:** xoá bản sao, import từ node:
```python
from src.agent_brain.agent.nodes.classifier_router_node import _has_boundary_markers
```

**Mức nguy hiểm: thấp bây giờ, cao về sau.** Đúng loại lỗi đã xảy ra ở A3 (script đo một thứ khác với cái nó tưởng nó đo).

## E4. Log detection đếm sai

**Bằng chứng:** log in `Missed detections (4 cases — needs boundary marker in utterance)` rồi liệt kê 5 đến 6 dòng. Ngoài ra `false_alarms = 2` và `correct_single = 3` trên 3 pseudo control, cộng lại quá 3.

**Vấn đề:** JSON đúng (23/27 = 85.2%), chỉ log sai. Nhưng nếu ai đó đọc log để viết chương thì sẽ chép nhầm.

**Cách sửa:** sửa cách dựng list `missed` quanh dòng 262 của `eval_mlp_router.py`, và kiểm lại quan hệ giữa `false_alarms` với `correct_single`.

## E5. `POST /orders` p99 = 9.0 ms so với p50 = 0.7 ms

**Vấn đề:** không phải lỗi, mà là một quan sát mới chỉ nhìn thấy được nhờ n = 100. Đuôi gấp 13 lần trong khi mọi endpoint khác có đuôi dưới 3 lần.

**Cách sửa:** một câu trong §5.5.1. Nguyên nhân nhiều khả năng là SQLite khoá ghi. Đây là ví dụ tốt cho lập luận "vì sao percentile chứ không phải mean", nên dùng luôn.

## E6. LangSmith hết quota, mọi eval spam lỗi 429

**Bằng chứng:** mỗi lần chạy eval đều kết thúc bằng một khối lỗi `LangSmithRateLimitError: Monthly unique traces usage limit exceeded`.

**Cách sửa:** đặt `LANGSMITH_TRACING=false` khi chạy eval, hoặc thêm hẳn vào đầu các script eval. Nó không làm sai số nhưng làm chậm và làm log khó đọc.

## E7. `eval_delegate.py` ghi report dù có connection error

**Bằng chứng, quan sát trực tiếp trong vòng chạy 19:26:**
```
[19:26:45]  Run 1: delegate_rate=1.11%  calls=1/90 turns
Report saved to .../delegate_baseline_20260726_192645.json
```
Log của lần chạy đó có 8 lần `ConnectError: Connection refused`. Ollama chết giữa chừng rồi sống lại, order worker và search worker fail hàng loạt, nhiều lượt không có tool call nào, nên delegate rate tụt xuống 1.11%. Chạy lại sạch cho **3.33%**.

**Vấn đề:** `eval_validator_ablation.py` có kiểm và in `Connection errors: 0`, nhưng `eval_delegate.py` **không có lưới đó** nên nó ghi report bình thường. Một con số 1.11% trông hoàn toàn hợp lý mà vô giá trị. Đúng cái bẫy `collected-results.md:36-43` đã cảnh báo: một run chết không tự khai trong summary.

**Cách sửa:** thêm bộ đếm connection error và **từ chối ghi report** khi khác 0, vào `eval_delegate.py`, `eval_qualitative.py` và `eval_multi_intent.py`. Copy pattern từ `eval_validator_ablation.py`.

**Mức nguy hiểm: cao.** Đây là loại lỗi sinh ra số sai mà không ai phát hiện.

**Ghi chú về môi trường:** ba lần crash trong vòng này đều là `model runner has unexpectedly stopped` trên máy 8 GB, đúng sự cố đã ghi ở `collected-results.md:36-43`. **Là giới hạn của máy dev, không phải của hệ thống**, không được đưa vào chương như một limitation. Cách chạy an toàn: chạy từng script một, kiểm `nvidia-smi` trước, và luôn đọc dòng connection error trước khi tin vào số.

---

# PHẦN 4. KHỐI F — LỖI PHÂN LOẠI MẢNH (vụ Bia Sài Gòn)

**Đây là finding mới quan trọng nhất của vòng 2.**

## F0. Chẩn đoán đã xác nhận

Rewriter cắt câu **đúng**. Classifier gán nhãn mảnh **sai**:
```
Cho 1 Lẩu Thái      -> ORDER  0.981  ✓
2 Bia Sài Gòn       -> SEARCH 0.815  ✗   <-- món này biến mất khỏi giỏ
Chốt đơn nhé        -> ORDER  1.000  ✓
```

Quét toàn bộ 219 món dưới dạng mảnh trần `N + tên món`:

| Dạng mảnh | Sai | Ghi chú |
|---|:---:|---|
| `2 Bia Sài Gòn` (đầu ra rewriter hiện tại) | **20/219 = 9.1%** | |
| `cho 2 Bia Sài Gòn` | 11/219 = 5.0% | |
| `2 Bia Sài Gòn nữa` | 3/219 = 1.4% | |
| `thêm 2 Bia Sài Gòn` | **2/219 = 0.9%** | tốt nhất |

**Hai phát hiện phụ, cả hai đều quan trọng:**

**F0a. 11 trong 20 ca sai rơi vào PAYMENT**, có ca confidence 0.884:
```
1 Cá Chim Nướng Sa Tế   -> PAYMENT 0.884
1 Chân Gà Nướng         -> PAYMENT 0.796
3 Răng Mực Cháy Tỏi     -> PAYMENT 0.786
```
Chương đang viết ở §5.4.1: *"The dangerous cell is empty: no utterance of any class was predicted as PAYMENT."* Câu đó đúng trên tập câu **nguyên vẹn**, nhưng trên phân phối mảnh mà rewriter thật sự sinh ra thì **PAYMENT là lỗi phổ biến nhất**. Đây là chỗ dễ bị hỏi nhất còn lại trong chương, và phải xử lý dù chọn giải pháp nào.

**F0b. Mảnh không hề bị kiểm ngưỡng tin cậy.** `classifier_router_node.py:139-148` phân loại từng mảnh rồi lấy thẳng `frag_result["intent"]`, không kiểm `>= 0.7`. Ngưỡng 0.7 chỉ áp cho câu gốc. **14 trong 20 ca sai có confidence < 0.7**, tức là tín hiệu để bắt đã có sẵn mà không ai đọc.

## F1. Sửa prompt rewriter để mảnh mang động từ

**Công:** một lần sửa prompt. **Hiệu quả đo được:** 9.1% xuống 0.9%.

**File:** prompt của rewriter trong `src/agent_brain/agent/resources/system_prompts/`.

Yêu cầu rewriter sinh ra mảnh **tự đứng được**, tức mảnh nối tiếp phải mang lại động từ của mệnh đề đầu:
```
Cũ:  "Cho 1 Lẩu Thái" | "2 Bia Sài Gòn" | "Chốt đơn nhé"
Mới: "Cho 1 Lẩu Thái" | "Cho 2 Bia Sài Gòn" | "Chốt đơn nhé"
```
Lập luận để bảo vệ trong chương: nhiệm vụ của rewriter là sinh ra **câu đơn ý**, mà một cụm danh từ không có động từ thì không phải một câu.

**Rủi ro:** phụ thuộc LLM tuân thủ, nên phải chạy N=5 để chắc.

## F2. Áp ngưỡng tin cậy cho mảnh

**Công:** khoảng 8 dòng, deterministic. **Hiệu quả:** bắt 14/20 ca sai.

**File:** `src/agent_brain/agent/nodes/classifier_router_node.py:139-148`.

Khi confidence của mảnh dưới ngưỡng, kế thừa intent của mảnh trước đó (hoặc của câu gốc nếu là mảnh đầu):
```python
prev_intent = None
for fragment in fragments:
    frag_result = _safe_classify(fragment, classifier_state, embedding_cache)
    frag_intent, frag_conf = frag_result["intent"], frag_result["confidence"]
    if frag_conf < CLASSIFIER_THRESHOLD and prev_intent is not None:
        logger.info("[Classifier Router] Fragment '%s' low confidence (%.3f) "
                    "-> inheriting %s from previous fragment", fragment, frag_conf, prev_intent)
        frag_intent = prev_intent
    prev_intent = frag_intent
    ...
```

**Ưu điểm lớn nhất:** không phụ thuộc LLM, nên nó là **lưới an toàn deterministic** khi F1 hụt. Hai cái bổ sung cho nhau, nên làm cả hai.

**Rủi ro:** thấp. Nhưng phải chạy lại multi-intent detection để chắc không đổi 85.2%.

## F3. Thêm mảnh trần vào corpus huấn luyện

**Công:** nửa ngày cộng train lại. **KHÔNG NÊN LÀM MỘT MÌNH.**

Dạy model rằng cụm danh từ trần là ORDER sẽ làm hỏng các truy vấn SEARCH thật, vì `Bia Sài Gòn` đứng riêng thường đúng là SEARCH ("quán có Bia Sài Gòn không?"). Chỉ nên làm nếu kèm theo F4 để model có tín hiệu phân biệt.

## F4. Thêm `prev_fragment_intent` làm feature thứ 11

**Công:** một ngày cộng train lại cộng chạy lại toàn bộ §5.4.1. **Đây là cái duy nhất đáng viết thành contribution.**

Chương đang lập luận: *"conversation state belongs inside the feature vector rather than in a rule layer around it"*, và mục B1 vừa chứng minh luận điểm đó ở mức p = 1.45e-4. **Vị trí của mảnh trong câu và intent của mảnh trước chính là một loại trạng thái như vậy.** F4 mở rộng đúng luận điểm đã được chứng minh, thay vì vá bằng rule (F2 là rule).

Nếu làm F4 thì F2 trở thành baseline để so sánh, và mình có thêm một ablation: rule-based inheritance vs feature-based inheritance. Đó là một kết quả đẹp.

**Rủi ro:** train lại nghĩa là chạy lại toàn bộ §5.4.1 (single, context, multi, holdout, six-arm ablation). Chỉ làm nếu còn thời gian.

## Khuyến nghị

**Làm F1 + F2 ngay.** Rẻ, bổ sung cho nhau, và F2 không phụ thuộc LLM.

**F4 chỉ nếu còn thời gian**, nhưng nếu làm thì nó là contribution thật chứ không phải bản vá.

**Dù chọn gì cũng phải xử lý F0a** trong chương: câu "the dangerous cell is empty" cần một câu bổ sung nói rõ nó đúng trên câu nguyên vẹn, còn trên mảnh do rewriter sinh ra thì PAYMENT là lỗi phổ biến nhất, và đây là lý do có F1/F2.

---

# PHẦN 5. KHỐI G — CÁC LẦN CHẠY CÒN THIẾU

Bốn script đã có flag `--runs` nhưng **chưa chạy ở N = 5**. Không có những lần chạy này thì §5.2.3 và §5.6.4 vẫn phải khai là single run.

| ID | Lệnh | Ước tính | Chặn việc gì |
|---|---|---|---|
| **G1** | `eval_multi_intent.py --runs 5` | ~15 phút | D4 không viết được, số ở §1.4 mới là 1 draw |
| **G2** | `eval_validator_ablation.py --runs 5` (cả hai nhánh ON/OFF) | ~30 phút | §5.4.2 bảng 5.4 |
| **G3** | `eval_delegate.py --runs 5` | ~20 phút | §5.4.2 delegate rate |
| **G4** | `eval_qualitative.py --runs 5` | ~30 phút | §5.4.5, và con số 4/6 hay 5/7 |
| **G5** | `eval_router_arms.py --runs 1` | ~20 phút | **Bảng 5.2 phải chạy lại** vì pool 304 case chứa context set cũ, giờ context set đã đổi thành 123 case |
| **G6** | `eval_latency.py --cold-start` | 5 phút | C2, `cold_start_s` vẫn `None` |
| **G7** | `bench_ws.py` | 5 phút | C4, script đã viết lại nhưng chưa chạy |
| **G8** | `eval_out_of_menu.py --runs 5` sau khi sửa E1 | ~30 phút | validator FP rate thật |

**Điều kiện chạy:**
```bash
# orchestrator phải bật cho các eval E2E
uv run uvicorn src.server_orchestrator.main:app --host 127.0.0.1 --port 8000

# tắt tracing để khỏi spam 429
export LANGSMITH_TRACING=false
```

**Sau mỗi lần chạy N=5, bắt buộc kiểm log tìm connection error trước khi tin vào mean.** Bài học đã ghi ở `collected-results.md:36-43`: một run chết vì Ollama mất kết nối sẽ kéo mean xuống một giá trị trông có vẻ hợp lý mà không báo lỗi trong summary.

**Lưu ý G5:** pool six-arm gồm `single_intent_eval.json` (149) cộng `context_dependent_eval.json` (giờ là 123 thay vì 70) cộng các file khác. Pool sẽ không còn là 304 case nữa. Bảng 5.2 phải cập nhật cả cỡ mẫu lẫn mọi con số accuracy và p.

---

# PHẦN 6. CÁC MỤC CÒN TREO TỪ VÒNG 1

## A6. Quyết định về 14B

`05-01:24` vẫn ghi *"The language model is Qwen2.5 14B Instruct"*, trong khi `.env` khai 7B ở cả ba vai trò, `ollama list` không có 14B, và GPU là 8 GB.

**Khuyến nghị vẫn như cũ: bỏ khung 14B.** Và giờ có thêm một lý do mạnh: sau vòng này, latency toàn cục đã cải thiện xuống p50 1.703 s, và per-node cho thấy 98.7% ngân sách là LLM. Đổi sang model to hơn sẽ đẩy thẳng vào con số đó, và ORDER_CONFIRM p95 vốn đã 6.126 s. Giữ 14B nghĩa là phải chấp nhận rằng claim latency sẽ vỡ.

**Nếu bỏ:** sửa `05-01` dòng 24-37, `05-04` dòng 12-15 và 199-201, `05-06` §5.6.4 mục "Model configuration", và xoá banner PROVISIONAL trong `collected-results.md` dòng 6-21.

## B2. Hard queries R@5 0.391

Không đổi sau vòng 1 (đúng như dự đoán, vì đây là khoảng trống từ vựng trong corpus chứ không phải lỗi retriever).

**Khuyến nghị vẫn như cũ: không làm ở giai đoạn này.** Chỉ khai báo giới hạn ở §6.2. Ưu tiên khối D và F cao hơn nhiều.

## C5. Bỏ cột GPU memory

`collected-results.md:895-920` đã kết luận đúng: `peak_gpu_mb` ghi tổng chiếm dụng thiết bị tại thời điểm mỗi arm chạy, nên nó tích luỹ theo thứ tự arm chứ không phải footprint của arm đó. Bỏ cột khỏi bảng ablation, và lập luận deployability dựa vào số tham số của MLP cùng việc nó dùng chung embedding model đã nạp sẵn cho retrieval.

## C5b. Còn trống, không phải việc viết lách

§5.3 navigation (cần robot), ASR/voice pipeline (chưa đo bao giờ), session isolation với leakage count, fleet failure path. Ba cái sau rẻ hơn §5.3 nếu muốn lấp.

---

# PHẦN 7. THỨ TỰ THI HÀNH

| Đợt | Việc | Ước tính | Vì sao thứ tự này |
|:---:|---|:---:|---|
| **6** | G1, G6, G7 | 30 phút | Rẻ nhất, và G1 chặn D4 là phần viết lớn nhất |
| **7** | E1 rồi G8; E3, E4, E6 | nửa ngày | Sửa metric hỏng trước khi chạy lấy số cuối |
| **8** | F1 + F2, rồi chạy lại G1 và multi-detection | nửa ngày | Phải xong trước D3 và D4 vì nó đổi số |
| **9** | G2, G3, G4, G5 | 2 giờ chạy | G5 bắt buộc vì context set đã đổi |
| **10** | **Khối D toàn bộ** | 2 đến 3 ngày | Đường găng. Chỉ làm khi mọi số đã chốt |
| **11** | A6, C5, E2 kết luận | nửa ngày | Quyết định + dọn |
| **12** | §5.6.5 "What this chapter establishes" | nửa ngày | Chỉ viết được sau khi D7 xong |

**Nguyên tắc quan trọng:** đừng viết prose trước khi chốt số. Vòng 1 đã mắc đúng lỗi này (prose sửa 16:55, code sửa 18:13), và kết quả là toàn bộ chương giờ mang số cũ. **Chạy hết đợt 6 đến 9 rồi mới bắt đầu đợt 10.**

---

# CHECKLIST VÒNG 2

## Đợt 6: chạy nhanh
- [ ] G1: `eval_multi_intent.py --runs 5`, kiểm connection error trong log
- [ ] G6: `eval_latency.py --cold-start`, lấy `cold_start_s`
- [ ] G7: `bench_ws.py`, xác nhận có bắt được event

## Đợt 7: sửa metric hỏng
- [ ] E1: sửa `valid_items_proposed` trong `eval_out_of_menu.py`, kiểm OOM-030 ra 3 chứ không phải 0
- [ ] G8: `eval_out_of_menu.py --runs 5` sau khi sửa E1
- [ ] E3: xoá bản sao `_has_boundary_markers` trong `eval_mlp_router.py`, import từ node
- [ ] E4: sửa cách đếm `missed` và quan hệ `false_alarms` / `correct_single`
- [ ] E6: `LANGSMITH_TRACING=false` vào các script eval

## Đợt 8: khối F
- [ ] F1: sửa prompt rewriter để mảnh nối tiếp mang động từ
- [ ] F2: thêm kế thừa intent khi confidence mảnh dưới ngưỡng
- [ ] Chạy lại `eval_mlp_router.py --datasets multi`, xác nhận detection vẫn >= 85.2%
- [ ] Chạy lại `eval_multi_intent.py --runs 5`, xác nhận `execution_rate` tăng từ 0.767
- [ ] Kiểm lại MI-005: giỏ phải có **cả** Lẩu Thái **và** Bia Sài Gòn

## Đợt 9: chạy lại các experiment stale — ĐÃ XONG 2026-07-27
- [x] G2: `eval_validator_ablation.py` cả hai nhánh, conn err = 0 → §1.8
- [x] G3: `eval_delegate.py` → 3.33%, conn err = 0 → §1.10
- [x] G4: `eval_qualitative.py` → 5/7 → §1.9
- [x] G5: `eval_router_arms.py` → pool n = 360 → §1.7
- [ ] E7: thêm guard connection error cho `eval_delegate`, `eval_qualitative`, `eval_multi_intent`
- [ ] **H1: quyết cách phát biểu E vs F.** Đề nghị: báo cáo tách theo subset, không claim trên pool gộp
- [ ] H1: thêm mục Threats về việc `context_dep` mở rộng sau khi quan sát lỗi model

## Đợt 10: khối D, viết lại chương
- [ ] D1: §5.4.4 bảng 5.6 và đoạn latency
- [ ] D2: §5.4.2 out-of-menu 30/30 và đoạn kể defect đã sửa
- [ ] D3: §5.4.1 context-dependent, disclosure A5, luật boundary mới, bảng 5.2 (n = 360, §1.7) **và bảng phân rã subset của H1**
- [ ] D2b: §5.4.2 bảng 5.4 validator ablation theo §1.8, kèm đoạn giải thích đảo chiều pass rate
- [ ] D4b: §5.4.5 thay transcript QS-007 theo §1.9, hạ giọng câu "cart goes from correct to empty"
- [ ] D4: §5.4.3 viết lại toàn bộ theo ba metric
- [ ] D5: §5.4.6 bảng 5.10, bảng per-node, đoạn rewriter cost
- [ ] D6: §5.5.1 bảng 5.11 n=100 và đuôi POST /orders
- [ ] D7: §5.6 bảng 5.14, bảng 5.15, xoá "weakest link is response layer", dọn §5.6.4, thống nhất six/seven
- [ ] D8: §5.2 dataset 123 case, định nghĩa 3 metric, protocol N=5
- [ ] D9: §5.1 nếu quyết A6

## Đợt 11: quyết định và dọn
- [ ] A6: quyết bỏ hay giữ 14B, sửa theo
- [ ] E2: kết luận về ORDER_CONFIRM p95 vượt trần, sửa câu ở §5.4.6
- [ ] C5: bỏ cột GPU memory
- [ ] B2: khai báo giới hạn corpus ở §6.2
- [ ] F0a: thêm câu về PAYMENT trên phân phối mảnh vào §5.4.1

## Đợt 12: đóng chương
- [ ] Viết §5.6.5 "What this chapter establishes"
- [ ] Rà lại `collected-results.md` cho khớp với chương
- [ ] Rà chéo: mọi con số trong chương phải truy được về một file trong `evals/results/`

---

# GHI CHÚ VỀ §5.6 VÀ CHƯƠNG 6

Giữ nguyên khuyến nghị vòng 1: **không thêm discussion và future work vào §5.6**. Outline đã có 6.1 Conclusion, 6.2 Limitations, 6.3 Future Works, và luận văn đang ở 280 đến 300 trang so với chuẩn 80 đến 150.

Ranh giới:
- **§5.6.4 Threats to Validity** = giới hạn của **phép đo**
- **§6.2 Limitations** = giới hạn của **hệ thống**

**§5.6.5 "What this chapter establishes"**, ba đoạn, một trang. Sau vòng 2 thì nội dung đã rõ hơn nhiều và có thể phác luôn:

1. Kiến trúc containment được chứng minh ở phạm vi **tư cách thành viên của menu**, không phải phạm vi **đúng ý khách**. Bằng chứng cho vế đầu: 30/30 out-of-menu, 70/70 name resolution, 0 món ngoài menu vào giỏ khi validator bật so với 31 khi tắt. Bằng chứng cho ranh giới của vế sau: defect resolver đã sửa, và vụ tham chiếu vô định ở QS-007.
2. Tầng deterministic **không hỏng ở bất kỳ thí nghiệm nào**, và tốn **khoảng 1.3% ngân sách một lượt**. An toàn gần như miễn phí. Đây là câu mạnh nhất mà chương có thể nói.
3. Mọi failure dồn vào phía LLM, và sau khi tách metric thì nó dồn cụ thể vào **execution** (0.767) chứ không phải verbalisation (0.800). Nguyên nhân gốc phần lớn là việc phân loại mảnh sau khi rewriter cắt câu, tức là chỗ mà phân phối đầu vào của classifier lệch khỏi phân phối nó được huấn luyện.

Điểm 3 chỉ viết được sau khi xong khối F, vì F1/F2 sẽ đổi con số.
