# Guide điều tra 2 bug agent (cho Claude chạy trên SERVER)

> Soạn từ máy laptop (chỉ có source, không có index thật). Agent + index chạy trên server,
> nên một số thứ phải xác nhận tại server. Mục tiêu: định vị 2 bug thấy trong ảnh chụp:
> (1) khách nói "Tôi muốn đặt món ăn" → bot trả "Xin lỗi, em chưa rõ..."; (2) bot liệt kê
> "Sò Mai Nướng Mỡ Hành Trứng Cút – **giá 0đ**" trong khi 2 món nướng khác đúng giá.

## Bối cảnh kiến trúc (cần biết trước)
- Agent (LLM/LangGraph) chạy `:8100` (`src/agent_brain`), backend `:8000` (`src/server_orchestrator`).
- Luồng 1 lượt: `chat()` → graph: `router → worker (order/search/payment/chat) → [validator → tools → state_updater] → state_outcome → response_node → END`.
- `response_node` **chỉ** đọc `state["response_context"]` (do `state_outcome_node` dựng). Nếu context `None` → trả câu fallback cứng.

---

## BUG 1 — "Tôi muốn đặt món ăn" → "Xin lỗi, em chưa rõ..."
**Bug CODE (giống nhau trên mọi máy), độ tự tin cao. Đã định vị xong từ laptop:**

Nguyên nhân: trong `src/agent_brain/agent/graph.py` có 2 cạnh đi **thẳng** tới `response_node`,
**bỏ qua `state_outcome`** (nơi duy nhất dựng `response_context`):
1. `_route_if_tool_call` (graph.py ~L51-69): khi worker **không phát tool_call** → đi thẳng `response_node`.
2. `_route_after_validator` (graph.py ~L72-85): circuit breaker sau 3 retry → đi thẳng `response_node`.

Khi tới `response_node` mà `response_context is None` → `response_node.py:431-437` trả
`_FALLBACK_REPLY = "Xin lỗi, em chưa rõ..."`, **vứt luôn text mà worker đã sinh ra**.
(Comment ở L432 ghi "should be unreachable" — giả định này SAI vì 2 cạnh trên.)

Tại sao worker không phát tool_call: `order_worker_node.py:26-32` ghi rõ **`tool_choice="any"`
bị ChatOllama bỏ qua**. Với câu mơ hồ "muốn đặt món" (chưa có món cụ thể), LLM trả lời bằng
**text** (hỏi lại "anh/chị muốn gọi món gì?") thay vì gọi `sync_cart` → không có tool_call →
rơi vào cạnh số 1 → fallback.

### Cách xác nhận trên server
- Bật log DEBUG, tìm dòng warning `"Worker produced no tool_calls despite tool_choice='any'"`
  (graph.py:65). Nếu thấy → đúng đường này.
- Hoặc xem trace LangSmith: order_worker phát AIMessage có `content` (text) nhưng `tool_calls`
  rỗng → next node là `response_node` → `response_context=None`.

### Hướng sửa (chọn 1)
- (a) **Khuyến nghị:** đổi nhánh "no tool_call" và nhánh circuit-breaker để đi qua `state_outcome`
  trước, và cho `state_outcome` dựng `ChatResponseContext` từ text của worker.
- (b) Vá nhanh tại `response_node`: khi `ctx is None` nhưng message cuối là AIMessage có `content`
  → verbalize chính text đó thay vì fallback.
- (c) Cho `order_worker` khi không trích được món thì chủ động dựng context hỏi lại.

---

## BUG 2 — "Sò Mai Nướng Mỡ Hành Trứng Cút – giá 0đ" (2 món kia đúng giá)
**Nghi là bug DỮ LIỆU/INDEX trên server (index không nằm trong git nên phải kiểm tại server).**

Đã loại trừ phía code/data gốc (kiểm trên laptop):
- `assets/data/menu.json` có `"price": "39000"` cho món này (committed từ 2026-06-20, sạch,
  giống nhau ở HEAD lẫn working tree).
- `document_loader.py:38-45` parse `"39000"` → `39000.0` đúng; `menu_manager.get_price` cũng
  đúng với tên dạng NFC.
- Trong luồng **tư vấn/SEARCH**, giá hiển thị đến từ **document trong index**
  (`document_loader.py:55` metadata `price` + L58-67 `page_content` có dòng `Giá: ...`),
  **KHÔNG** qua `get_price` (get_price chỉ dùng ở `sync_cart`/`confirm_order`).
- Vì **chỉ đúng 1 món sai = 0**, 2 món khác đúng → không phải lỗi code chung, mà **document
  của riêng món này trong index mang price 0** → **index cũ/stale** (build từ menu.json cũ,
  khi món này chưa có giá / chưa tồn tại).

### Cách xác nhận trên server (chạy ở repo agent trên server)
```bash
# 1) Index có tồn tại & cũ hơn menu.json không
find storage/vector -type f -exec stat -c '%y  %n' {} \;
stat -c '%y  %n' assets/data/menu.json
python -c "from src.agent_brain.config import settings; print('BM25_PATH=', settings.BM25_PATH)"   # rồi stat path đó

# 2) Soi thẳng document đã index cho món này
uv run python - <<'PY'
from src.agent_brain.services.retriever.builder import IndexBuilder
from src.agent_brain.services.retriever.hybrid_retriever import RetrieverManager
b = IndexBuilder(); b.load_database()
r = RetrieverManager(vector_engine=b.vector_engine, bm25_engine=b.bm25_engine)
for res in r.search(query="Sò Mai Nướng Mỡ Hành Trứng Cút", k=3):
    d = res.document
    print("price(meta)=", d.metadata.get("price"), "| name=", d.metadata.get("name"))
    print(d.page_content[:200])
    print("---")
PY
```
Nếu `price(meta)` hoặc dòng `Giá:` ra **0** trong khi menu.json là 39000 → **xác nhận index stale**.

### Cách sửa
```bash
make reindex      # hoặc: make agent (nó chạy reindex trước khi serve)
```
⚠️ Nếu trên server đang khởi động agent bằng dòng `uvicorn ... agent_brain.server` trực tiếp
(để bỏ qua reindex cho nhanh) thì index **không bao giờ được làm mới** → đúng triệu chứng này.

### Cần loại trừ thêm
```bash
grep -rn "BEST_SELLER\|best_seller" src/agent_brain --include=*.py
```
Món này gắn tag *best seller*; kiểm tra có đường xử lý best-seller riêng nào hardcode/để price 0
không (chưa kiểm từ laptop).

---

## Bug phụ liên quan (ảnh hưởng luồng ĐẶT MÓN, không phải tư vấn)
`menu_manager.get_price` (`src/agent_brain/utils/menu_manager.py`) match tên **cứng** (chỉ
`lower()+strip()`), nên trả **0đ** khi:
1. Tên ở dạng **Unicode NFD** (STT/voice hay sinh ra; "ố" 1 ký tự ≠ "ô"+dấu) — đã reproduce:
   NFC→39000, NFD→0.
2. LLM **diễn đạt lại tên** lệch menu 1 chữ.

Đề xuất fix: chuẩn hóa `unicodedata.normalize("NFC", ...)` + gộp whitespace + lower, dùng chung
cho lúc build map và lúc tra; thêm `logger.warning` khi miss (đừng trả 0 âm thầm).
→ KHÔNG sửa bug 2 (tư vấn), nhưng chặn lỗi 0đ khi khách **đặt** đúng món qua voice.

---

## Lỗi phụ trong ảnh: bong bóng "đã subscribe kênh Ghiền Mì Gõ / Ốc Quậy"
Đây là **hallucination của PhoWhisper STT** trên audio im lặng/nhiễu (model train trên data
YouTube nên hay sinh câu outro kiểu này). Không phải lỗi agent. Cách giảm: siết ngưỡng VAD,
bỏ qua transcript rỗng/ngắn vô nghĩa trước khi POST `/chat`.

---

## Tóm tắt
| Bug | Loại | Vị trí | Hành động |
|---|---|---|---|
| 1. "em chưa rõ" | Code (graph) | `graph.py` cạnh worker/validator→response_node bỏ qua state_outcome; `response_node.py:431` | Route qua state_outcome **hoặc** verbalize text của worker khi ctx None |
| 2. giá 0đ (tư vấn) | Data/Index | index stale vs `menu.json` | `make reindex`; xác nhận bằng script soi document; loại trừ BEST_SELLER |
| phụ. 0đ khi đặt voice | Code | `menu_manager.get_price` match cứng | Chuẩn hóa NFC + log miss |
| phụ. greeting lạ | STT | PhoWhisper hallucination | Siết VAD, bỏ transcript rỗng |
