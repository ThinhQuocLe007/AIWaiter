# Tiến độ triển khai — AI Waiter

> Nhật ký "đã làm gì / làm thế nào / còn gì". Đọc kèm [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
> (kiến trúc tổng thể) và lộ trình **Mốc A→D** ở mục 11 của tài liệu đó.
> Cập nhật: 2026-06-20 · Nhánh: `feat/payment-tool`.

---

## 1. Tổng quan trạng thái theo mốc

| Mốc | Nội dung | Trạng thái |
|---|---|---|
| A | 1 robot, Brain↔Body localhost WS | ⬜ chưa bắt đầu |
| **B** | **Server trung tâm (FastAPI+SQLite), nối `customer_ui` vào backend, Kiosk + Bảng ĐK cơ bản** | 🟡 **đang làm** — backend skeleton + `GET /menu` xong, UI robot đã nối menu |
| C | Dispatcher + nút bàn + thanh toán | ⬜ chưa bắt đầu |
| D | Multi-robot | ⬜ chưa bắt đầu |

Cụ thể trong Mốc B: **đã xong "Bước 0 + Bước 1"** = dựng khung server và cho UI robot lấy menu thật từ server.

---

## 2. Đã làm (và làm thế nào)

### 2.1 Backend Orchestrator — khung FastAPI + SQLite
**Vị trí:** [src/backend/](../src/backend/) (mới, chưa commit).

| File | Vai trò |
|---|---|
| [app/main.py](../src/backend/app/main.py) | App FastAPI; `lifespan` gọi `init_db()` + `seed_dishes()` lúc khởi động; gắn CORS middleware; include router menu; có `GET /health` |
| [app/config.py](../src/backend/app/config.py) | `Settings` (pydantic-settings, prefix `ORCH_`): đường dẫn `menu.json`, file SQLite `storage/db/orchestrator.db`, danh sách CORS origins |
| [app/db.py](../src/backend/app/db.py) | Lớp SQLite thuần (không ORM). Định nghĩa **toàn bộ schema mục 8**: `tables, dishes, orders, order_items, robots, tasks, payments`. `get_conn()` mở connection theo từng call, commit/rollback tự động; `init_db()` tạo schema idempotent |
| [app/menu.py](../src/backend/app/menu.py) | `load_menu()` đọc `assets/data/menu.json` (cache `lru_cache`); `seed_dishes()` nạp bảng `dishes` từ file đó nếu rỗng |
| [app/routers/menu.py](../src/backend/app/routers/menu.py) | `GET /menu` → trả raw menu y hệt `menu.json` để frontend tự shaping client-side |

**Quyết định thiết kế:**
- **SQLite thuần + sqlite3** (chưa SQLAlchemy) để Bước 0 nhỏ gọn; đổi ORM sau chỉ sửa `db.py`.
- **`menu.json` là nguồn chân lý duy nhất** cho cả UI lẫn bảng `dishes` → không lệch dữ liệu.
- Backend **standalone**, không import `ai_waiter_core` (Brain) → sau chạy máy riêng được.

**Chạy:** `make backend` → `uvicorn ... --port 8000`. Đã test: `GET /menu` trả **217 món, HTTP 200**.

### 2.2 Nối UI robot vào backend (thay import tĩnh bằng fetch)
- [stores/menu.ts](../src/frontends/customer_ui/src/stores/menu.ts) → `loadMenu()` gọi `fetchMenu()` (REST) thay vì import tĩnh; có `isLoading` + `loadError` để hiện nút "Thử lại" khi lỗi.
- [data/api.ts](../src/frontends/customer_ui/src/data/api.ts) → REST client mỏng, `GET /menu`.
- [data/menuAdapter.ts](../src/frontends/customer_ui/src/data/menuAdapter.ts) giữ nguyên việc shaping (category, group, best-seller) ở client.

### 2.3 Hạ tầng dev — bỏ CORS bằng Vite proxy + cố định port
**Vấn đề gặp:** chạy nhiều `make frontend` → Vite nhảy port 5174/5175 (ngoài CORS allowlist) → backend trả 200 nhưng thiếu header CORS → browser "Failed to fetch" dù server log 200 OK.

**Cách sửa (trong [vite.config.ts](../src/frontends/customer_ui/vite.config.ts)):**
- `server.proxy`: `/api` → `http://127.0.0.1:8000` (rewrite strip `/api`), `/ws` → `ws://127.0.0.1:8000`. Browser chỉ gọi chính origin Vite → **không còn CORS**, khớp production (FastAPI serve static cùng origin).
- `port: 5173` + `strictPort: true`: Vite báo lỗi nếu port bận thay vì nhảy lung tung.
- [.env](../src/frontends/customer_ui/.env): `VITE_API_URL=/api`, `VITE_WS_URL=/ws` (đường dẫn tương đối).

**Quy ước port** (mỗi frontend sau cũng theo): backend `8000` · customer_ui `5173` · Kiosk `5174` · Bảng ĐK `5175` · ROS bridge `9090`.

---

## 3. Còn lại — việc tiếp theo (theo thứ tự ưu tiên)

### 3.1 Hoàn tất Mốc B (gần nhất)
- [ ] **`POST /orders`** ở backend (tạo đơn + `order_items`, tính `total`, set bàn `CHO_BEP`).
- [ ] **`MenuScreen → confirmOrder()`** ở UI robot: POST đơn lên server thay vì chỉ chuyển màn.
- [ ] **`GET /tables` + `POST /seatings`** (nền cho Kiosk).
- [ ] **Kiosk web** (`/kiosk`, port 5174): xem bàn trống → chọn bàn + số người. Tái dùng component menu của `customer_ui`.
- [ ] **Bảng điều khiển** (`/panel`, port 5175) cơ bản: list đơn theo bàn + nút tick "món xong" (`PATCH /orders/{id}`).
- [ ] **WebSocket `/ws`** (1 endpoint, phân luồng theo `role`): đẩy "đơn mới" realtime xuống Bảng ĐK.

### 3.2 Mốc C — Dispatcher + nút bàn + thanh toán
- [ ] **Dispatcher**: hàng đợi `tasks`, chọn robot idle/gần/đủ pin; máy trạng thái bàn (mục 6).
- [ ] **`POST /tables/{id}/call`** + luồng `call` (robot tới hỏi: đặt thêm / thanh toán).
- [ ] **Thanh toán** (đúng tên nhánh `feat/payment-tool`): `GET /orders/{id}/bill`, `POST /payments/{order_id}/qr`, `POST /webhooks/payment`; nối `PaymentScreen` (bill thật + QR + chờ webhook). Dùng **sandbox VietQR/MoMo/ZaloPay** cho demo.
- [ ] **Nút bàn phần cứng** (ESP32/WiFi → gọi `/tables/{id}/call`); demo tạm bằng `curl`.

### 3.3 Mốc A & D — robot
- [ ] **Brain↔Body WS localhost** + **node bridge** `ai_hw_bridge` (đang `COLCON_IGNORE`): nhận task → tra `restaurant_positions.md` → đặt Nav2 goal → báo `arrived`/`task_done`.
- [ ] **`ws_client.py`** (Brain → Server) để robot thành WS client.
- [ ] **Agent sinh lệnh hành động** (rủi ro lớn nhất, mục 12): hiện agent chỉ trả text, chưa phát lệnh điều khiển robot.
- [ ] **Voice thật**: thay mock `stores/voice.ts` bằng STT + LLM endpoint + TTS.
- [ ] **Multi-robot**: instance thứ 2 trong sim, lane 1 chiều, cân nhắc Open-RMF/Zenoh.

---

## 4. Ý tưởng phát triển / cải thiện
- **Serve frontend tĩnh từ FastAPI** (prod): build `customer_ui`/Kiosk/Panel → FastAPI mount static → cùng origin, không cần Vite lúc chạy thật.
- **Schema dùng chung**: pydantic models cho message WS (mục 5) đặt ở `schemas/` để Brain/Server/Body dùng chung 1 contract.
- **`menu.json` → DB**: dài hạn cho phép sửa menu qua Bảng ĐK (CRUD `dishes`) thay vì sửa file tay.
- **Seed `tables`**: hiện schema có bảng `tables` nhưng chưa seed; nên seed bàn 1–6 khớp `restaurant_positions.md`.
- **Health/readiness cho demo 3 laptop**: trang `/panel` hiện trạng thái kết nối robot (heartbeat) để biết robot "sống".
