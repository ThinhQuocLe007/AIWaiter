# Tiến độ triển khai — AI Waiter

> Nhật ký "đã làm gì / làm thế nào / còn gì". Đọc kèm [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
> (kiến trúc tổng thể) và lộ trình **Mốc A→D** ở mục 11 của tài liệu đó.
> Cập nhật: 2026-06-20 · Nhánh: `feat/payment-tool`.

---

## 1. Tổng quan trạng thái theo mốc

| Mốc | Nội dung | Trạng thái |
|---|---|---|
| A | 1 robot, Brain↔Body localhost WS | ⬜ chưa bắt đầu |
| **B** | **Server trung tâm (FastAPI+SQLite), nối `customer_ui` vào backend, Kiosk + Bảng ĐK cơ bản** | ✅ **xong (cốt lõi)** — backend menu+orders+tables+WS, UI robot gửi đơn thật, **Bảng ĐK realtime**, **Kiosk check-in** (chọn bàn + số người). *(Tái dùng component menu trên Kiosk để dành — xem 2.7.)* |
| C | Dispatcher + nút bàn + thanh toán | ⬜ chưa bắt đầu |
| D | Multi-robot | ⬜ chưa bắt đầu |

Cụ thể trong Mốc B: **đã xong "Bước 0 → 4"** = dựng khung server, UI robot lấy menu thật, **đặt món thật**, **Bảng điều khiển bếp realtime** (đơn mới đẩy qua WebSocket, tick trạng thái món), và **Kiosk check-in** (chọn bàn trống + số người → `POST /seatings`). Phần *tái dùng component menu* trên Kiosk để dành (sẽ nâng npm workspaces khi cần) — **không chặn**, vì khách đặt món trên tablet tại bàn (`customer_ui`).

---

## 2. Đã làm (và làm thế nào)

### 2.1 Backend Orchestrator — khung FastAPI + SQLite
**Vị trí:** [src/backend/](../src/backend/) (mới, chưa commit).

| File | Vai trò |
|---|---|
| [app/main.py](../src/backend/app/main.py) | App FastAPI; `lifespan` gọi `init_db()` + `seed_tables()` + `seed_dishes()` lúc khởi động; gắn CORS middleware; include router menu/tables/orders/ws; có `GET /health` |
| [app/config.py](../src/backend/app/config.py) | `Settings` (pydantic-settings, prefix `ORCH_`): đường dẫn `menu.json`, file SQLite `storage/db/orchestrator.db`, danh sách CORS origins |
| [app/db.py](../src/backend/app/db.py) | Lớp SQLite thuần (không ORM). Định nghĩa **toàn bộ schema mục 8**: `tables, dishes, orders, order_items, robots, tasks, payments`. `get_conn()` mở connection theo từng call, commit/rollback tự động; `init_db()` tạo schema idempotent |
| [app/menu.py](../src/backend/app/menu.py) | `load_menu()` đọc `assets/data/menu.json` (cache `lru_cache`); `seed_dishes()` nạp bảng `dishes` từ file đó nếu rỗng |
| [app/routers/menu.py](../src/backend/app/routers/menu.py) | `GET /menu` → trả raw menu y hệt `menu.json` để frontend tự shaping client-side |
| [app/schemas.py](../src/backend/app/schemas.py) | Pydantic models (1 chỗ, contract dùng chung): `OrderCreate/OrderOut/OrderItem*`, `TableOut`, `SeatingCreate` |
| [app/routers/orders.py](../src/backend/app/routers/orders.py) | `POST /orders` (lưu đơn + items, **tính `total` server-side**, set bàn `CHO_BEP` + `current_order_id`), `GET /orders` (lọc `table_id`/`status`), `GET /orders/{id}`, `PATCH /orders/{id}` (đổi status). `POST`/`PATCH` là **async** và **broadcast WS** sau khi lưu |
| [app/routers/tables.py](../src/backend/app/routers/tables.py) | `GET /tables`, `POST /seatings` (ngồi bàn: `TRONG`→`DANG_PHUC_VU`, chặn bàn đã có khách 409) |
| [app/ws.py](../src/backend/app/ws.py) | **WebSocket hub** `/ws?role=<role>`: 1 endpoint, fan-out theo `role`. `ConnectionManager` (singleton `manager`) giữ set socket theo role + `broadcast(role, msg)`. Orders router gọi `manager.broadcast("panel", {...})` khi có đơn mới/đổi trạng thái |

**Seed bàn:** `seed_tables()` nạp bàn 1–6 (`menu.py`) khớp [restaurant_positions.md](../robot_ws/docs/restaurant_positions.md) (marker q1–q6), gọi trong `lifespan`.

**Sự kiện WS hiện có** (gửi tới `role=panel`): `{"type":"order.created","order":{...}}` và `{"type":"order.updated","order":{...}}` — payload `order` y hệt `OrderOut`.

**Quyết định thiết kế:**
- **SQLite thuần + sqlite3** (chưa SQLAlchemy) để Bước 0 nhỏ gọn; đổi ORM sau chỉ sửa `db.py`.
- **`menu.json` là nguồn chân lý duy nhất** cho cả UI lẫn bảng `dishes` → không lệch dữ liệu.
- Backend **standalone**, không import `ai_waiter_core` (Brain) → sau chạy máy riêng được.

**Chạy:** `make backend` → `uvicorn ... --port 8000`. Đã test: `GET /menu` trả **217 món, HTTP 200**.

### 2.2 Nối UI robot vào backend (thay import tĩnh bằng fetch)
- [stores/menu.ts](../src/frontends/customer_ui/src/stores/menu.ts) → `loadMenu()` gọi `fetchMenu()` (REST) thay vì import tĩnh; có `isLoading` + `loadError` để hiện nút "Thử lại" khi lỗi.
- [data/api.ts](../src/frontends/customer_ui/src/data/api.ts) → REST client mỏng, `GET /menu`.
- [data/menuAdapter.ts](../src/frontends/customer_ui/src/data/menuAdapter.ts) giữ nguyên việc shaping (category, group, best-seller) ở client.

### 2.3 UI robot gửi đơn thật (`confirmOrder` → `POST /orders`)
- [data/api.ts](../src/frontends/customer_ui/src/data/api.ts) → thêm `postJson` + `createOrder(tableId, items)`.
- [screens/MenuScreen.vue](../src/frontends/customer_ui/src/components/screens/MenuScreen.vue) → `confirmOrder()` giờ `async`: map giỏ hàng → POST, có `submitting`/`orderError`, lỗi thì hiện trong giỏ thay vì nhảy màn "thành công" giả. Bàn lấy từ `VITE_TABLE_ID` (mặc định 1).
- [cart/CartDrawer.vue](../src/frontends/customer_ui/src/components/cart/CartDrawer.vue) → nhận props `submitting`/`error`: nút đổi chữ "Đang gửi đơn…" + disable, hiện dòng lỗi.
- Giỏ **không** clear ngay sau POST → `ConfirmationScreen` còn snapshot được tổng tiền; giỏ tự clear khi quay về màn chính.

### 2.4 Hạ tầng dev — bỏ CORS bằng Vite proxy + cố định port
**Vấn đề gặp:** chạy nhiều `make frontend` → Vite nhảy port 5174/5175 (ngoài CORS allowlist) → backend trả 200 nhưng thiếu header CORS → browser "Failed to fetch" dù server log 200 OK.

**Cách sửa (trong [vite.config.ts](../src/frontends/customer_ui/vite.config.ts)):**
- `server.proxy`: `/api` → `http://127.0.0.1:8000` (rewrite strip `/api`), `/ws` → `ws://127.0.0.1:8000`. Browser chỉ gọi chính origin Vite → **không còn CORS**, khớp production (FastAPI serve static cùng origin).
- `port: 5173` + `strictPort: true`: Vite báo lỗi nếu port bận thay vì nhảy lung tung.
- [.env](../src/frontends/customer_ui/.env): `VITE_API_URL=/api`, `VITE_WS_URL=/ws` (đường dẫn tương đối).

**Quy ước port** (mỗi frontend sau cũng theo): backend `8000` · customer_ui `5173` · Kiosk `5174` · Bảng ĐK `5175` · ROS bridge `9090`.

### 2.5 Code dùng chung giữa các frontend — `shared/` (không monorepo)
**Vị trí:** [src/frontends/shared/](../src/frontends/shared/) — TS thuần, **không phụ thuộc thư viện** nào, nên Vite của từng app bundle thẳng được qua alias `@shared` (chưa cần npm workspaces).

| File | Vai trò |
|---|---|
| [shared/types.ts](../src/frontends/shared/types.ts) | `Order`, `OrderItem`, `Table`, `WsEvent` — mirror `schemas.py` của backend |
| [shared/rest.ts](../src/frontends/shared/rest.ts) | REST client: `fetchOrders/createOrder/updateOrderStatus`, `fetchTables/createSeating`. Base `VITE_API_URL` (mặc định `/api`) |
| [shared/ws.ts](../src/frontends/shared/ws.ts) | `connectEvents(role, onEvent, onStatus?)`: mở `/ws?role=...`, parse JSON, **tự reconnect backoff** (1→10s), báo trạng thái kết nối |

**Quyết định cấu trúc (production):** mỗi surface là **app Vite riêng** (cô lập bảo mật — panel bếp không lẫn vào bundle tablet khách; deploy độc lập; khớp quy ước port). Chia sẻ code theo tầng: *giờ* tách phần TS thuần ra `shared/` + alias; *khi tới Kiosk* (cần share **component Vue** có deps) thì mới nâng lên **npm workspaces** (`apps/*` + `packages/ui`).

> Lưu ý: customer_ui **chưa** migrate sang `shared/` (vẫn dùng `data/api.ts` riêng) để tránh churn — đây là việc dọn dẹp optional, không chặn gì.

### 2.6 Bảng điều khiển bếp (Panel) — app riêng, realtime
**Vị trí:** [src/frontends/panel/](../src/frontends/panel/) (app Vite + Vue mới, port **5175**). Deps tối thiểu (`vue` + vite); **không** dùng vue-tsc (build = `vite build`, esbuild lo TS).

- [src/App.vue](../src/frontends/panel/src/App.vue) — KDS 3 cột theo trạng thái: **Chờ bếp** (`CHO_BEP`) → **Đang làm** (`DANG_LAM`) → **Xong** (`XONG`). Card: tên bàn, thời gian, list `qty × món`, tổng tiền, nút đẩy trạng thái (`CHO_BEP`→`DANG_LAM`→`XONG`) gọi `updateOrderStatus` (`PATCH`).
- Realtime: `onMounted` → `fetchTables + fetchOrders` (load đầu), rồi `connectEvents('panel', …)` cập nhật tức thì (`order.created` thêm card, `order.updated` thay card). Có đèn báo "đã kết nối" + **poll lại mỗi 15s** để re-sync nếu lỡ event.
- [vite.config.ts](../src/frontends/panel/vite.config.ts): proxy `/api`+`/ws` sang `:8000`, alias `@`+`@shared`, `port 5175 strictPort`.

**Luồng trạng thái dùng chung (quy ước hiện tại):**
- **Order:** `CHO_BEP` → `DANG_LAM` → `XONG` (panel điều khiển). *(chưa có bước giao: `DANG_GIAO`/`DA_GIAO` — để dành Mốc C khi có robot.)*
- **Bàn (`tables.status`):** `TRONG` → `DANG_PHUC_VU` (seating) ; `POST /orders` đẩy bàn sang `CHO_BEP` + set `current_order_id`.

**Chạy:** `make panel` → Vite 5175. Đã test E2E (qua Vite proxy): tạo đơn → panel nhận `order.created` realtime; PATCH → `order.updated`. WS proxy hoạt động.

### 2.7 Kiosk check-in (Quầy đăng ký) — app riêng, port 5174
**Vị trí:** [src/frontends/kiosk/](../src/frontends/kiosk/) (app Vite + Vue mới). Dựng theo đúng khuôn `panel/`: deps tối thiểu (`vue` + vite, **không** vue-tsc), alias `@`+`@shared`, proxy `/api`+`/ws` sang `:8000`, `port 5174 strictPort`.

- [src/App.vue](../src/frontends/kiosk/src/App.vue) — máy trạng thái 1 màn: **lưới bàn** (`fetchTables`) → bấm bàn trống → **chọn số người** (stepper 1…`capacity`) → `createSeating` (`POST /seatings`) → **màn xác nhận** "bàn đã sẵn sàng" rồi tự về danh sách (cho khách kế tiếp).
  - Bàn `TRONG` mới bấm được; bàn khác (`DANG_PHUC_VU`/`CHO_BEP`…) hiển thị "Đang phục vụ", disable.
  - **Xử lý 409** (bàn vừa bị người khác lấy giữa lúc tải & submit): bắt lỗi → thông báo "mời chọn bàn khác" + refetch, không kẹt overlay.
  - **Poll `GET /tables` mỗi 8s** (không có WS event cho trạng thái bàn) để phản ánh bàn được giải phóng / lấp đầy.
- Dùng chung `@shared/rest` (`fetchTables`/`createSeating`) + `@shared/types` — không trùng client code.
- **Phạm vi bước 1:** chỉ **seating** (đúng gợi ý mục 3.1). Khách đặt món trên **tablet tại bàn** (`customer_ui`), nên Kiosk *không* cần nhúng menu lúc này; ghép menu vào Kiosk để dành tới khi nâng **npm workspaces**.

**Chạy:** `make kiosk` → Vite 5174. Đã test: `vite build` pass (13 modules, gồm `@shared`); API E2E qua backend: `POST /seatings` bàn trống → `201` (`TRONG`→`DANG_PHUC_VU`); seat lại / seat bàn đang phục vụ → `409` (khớp nhánh xử lý lỗi trong UI).

---

## 3. Còn lại — việc tiếp theo (theo thứ tự ưu tiên)

### 3.1 Mốc B — ✅ cốt lõi đã xong
- [x] **`POST /orders`** ở backend (tạo đơn + `order_items`, tính `total`, set bàn `CHO_BEP`).
- [x] **`MenuScreen → confirmOrder()`** ở UI robot: POST đơn lên server thay vì chỉ chuyển màn.
- [x] **`GET /tables` + `POST /seatings`** (nền cho Kiosk).
- [x] **Bảng điều khiển** (app `panel`, port 5175): KDS list đơn + nút đổi trạng thái (`PATCH /orders/{id}`) — xong (2.6).
- [x] **WebSocket `/ws`** (1 endpoint, fan-out theo `role`): đẩy `order.created`/`order.updated` realtime xuống Panel — xong (2.6, `app/ws.py`).
- [x] **Kiosk web** (app riêng `src/frontends/kiosk/`, port **5174**): xem bàn trống (`GET /tables`) → chọn bàn + số người (`POST /seatings`) → màn xác nhận — xong (2.7).
- [ ] *(còn lại, optional)* **Tái dùng component menu trên Kiosk**: menu components có deps (pinia…) → để dành tới khi **nâng npm workspaces** (`apps/*` + `packages/ui`). Hiện không cần vì khách đặt món trên tablet tại bàn (`customer_ui`).
- [ ] *(liên quan)* Sau khi seat xong, customer_ui cần biết `table_id` **động** (hiện lấy tĩnh từ `VITE_TABLE_ID` trong [ui.ts](../src/frontends/customer_ui/src/stores/ui.ts)) — xem mục 4.

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
- **`table_id` động cho customer_ui**: hiện tablet gán tĩnh qua `VITE_TABLE_ID` ([ui.ts](../src/frontends/customer_ui/src/stores/ui.ts) `tableId`). Khi có Kiosk seating, nên set `ui.tableId` lúc check-in (query param/route hoặc gọi API), thay vì cố định mỗi máy 1 bàn.
- **Migrate customer_ui sang `shared/`**: customer_ui còn `data/api.ts` riêng (trùng phần order types/client với `shared/`). Thêm alias `@shared` vào [vite.config.ts](../src/frontends/customer_ui/vite.config.ts) rồi dùng chung — dọn dẹp optional.
- **Nâng lên npm workspaces khi share component Vue**: lúc làm Kiosk cần tái dùng component menu (có deps) → chuyển `src/frontends/` thành workspace (`apps/customer_ui|kiosk|panel` + `packages/ui`). TS thuần thì `shared/` + alias là đủ (đã làm).
- **Serve frontend tĩnh từ FastAPI** (prod): build customer_ui/Kiosk/Panel → FastAPI mount static → cùng origin, không cần Vite lúc chạy thật.
- **`menu.json` → DB**: dài hạn cho phép sửa menu qua Bảng ĐK (CRUD `dishes`) thay vì sửa file tay.
- **WS cho customer_ui/robot**: hub `app/ws.py` đã fan-out theo `role`; mở thêm `role=robot`/`role=customer` khi cần (vd báo "đơn đã xong, robot đang giao" về tablet khách).
- **Health/readiness cho demo 3 laptop**: trang panel hiện trạng thái kết nối robot (heartbeat) để biết robot "sống".

---

## 5. Cách chạy nhanh (cho session mới)
> Lần đầu (hoặc sau khi pull): `make install` để cài deps cho cả 3 frontend (đã gồm `kiosk`) + backend.
> Mỗi lệnh `make` dưới đây chiếm 1 terminal (chạy foreground) — mở 4 cửa sổ, hoặc thêm `&`. Dừng tất cả: `make kill`.

```bash
make backend     # FastAPI :8000 (tự seed bàn 1–6 + 217 món lúc khởi động)
make frontend    # customer_ui :5173  (tablet khách — đặt món)
make kiosk       # Quầy đăng ký   :5174  (chọn bàn + số người → seating)
make panel       # Bảng ĐK bếp    :5175  (KDS realtime)
```
- DB: `storage/db/orchestrator.db` (SQLite, tự tạo). Xoá file này để seed lại từ đầu (mọi bàn về `TRONG`).
- **Test luồng đặt món** (panel): mở panel (5175) → ở customer_ui (5173) đặt món → đơn hiện realtime trên panel → bấm "Bắt đầu làm"/"Món xong" để đẩy trạng thái.
- **Test luồng Kiosk** (5174): mở kiosk → bấm 1 bàn **Trống** → chọn số người → "Vào bàn" → màn xác nhận; bàn vừa seat chuyển sang "Đang phục vụ" (poll 8s). Bàn đã có khách thì bị mờ/không bấm được.
- **Chưa commit:** toàn bộ `src/backend/`, `src/frontends/shared/`, `src/frontends/panel/`, **`src/frontends/kiosk/`** và sửa đổi trong `customer_ui` + `Makefile` đang ở working tree nhánh `feat/payment-tool`.
