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
| **C** | **Dispatcher + nút bàn + thanh toán** | 🟦 **đang làm** — dispatcher (hàng đợi `tasks`, chọn robot gần/đủ pin, WS 2 chiều robot↔server, re-dispatch khi robot rớt) + nút bàn `/call` + thanh toán mock **đã xong & test E2E bằng mock robot**; còn robot thật (Mốc A) |
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

### 2.8 Bảng điều khiển *toàn quán* + máy trạng thái bàn + robot mock
Mở rộng Panel từ "chỉ KDS bếp" thành bảng giám sát cả quán (1 trang nhiều khu) cho quản lý.

**Máy trạng thái bàn (tách khỏi trạng thái bếp):**
- `tables.status`: `TRONG` → `DANG_PHUC_VU` (seating, kèm `seated_at`+`party_size`) → `DA_THANH_TOAN` → `TRONG`.
- **Đổi hành vi:** [orders.py](../src/backend/app/routers/orders.py) **không còn** ép bàn sang `CHO_BEP` khi đặt món — bàn giữ `DANG_PHUC_VU`, chỉ set `current_order_id`. Trạng thái bếp sống ở `orders.status` (`CHO_BEP→DANG_LAM→XONG`), không nhét lên bàn nữa.

**Backend:**
- [db.py](../src/backend/app/db.py): bảng `tables` += `party_size`, `seated_at`; thêm migration nhẹ trong `init_db()` (`PRAGMA table_info` + `ALTER TABLE ADD COLUMN`) để DB seed cũ tự lên cột mới (idempotent).
- [menu.py](../src/backend/app/menu.py): `seed_robots()` nạp **2 robot mock** (`robo-1` idle 92%, `robo-2` busy 64%) — dữ liệu thật tới ở Mốc A/D, cùng bảng `robots`.
- [schemas.py](../src/backend/app/schemas.py): `TableOut` += `party_size`/`seated_at`; thêm `RobotOut`, `TableStatusUpdate`.
- [tables.py](../src/backend/app/routers/tables.py): `POST /seatings` lưu `party_size`+`seated_at` & broadcast `table.updated`; **`GET /tables/{id}`** (cho tablet); **`PATCH /tables/{id}`** (đổi trạng thái; về `TRONG` thì clear order/khách/giờ ngồi) — đều broadcast `table.updated`.
- [robots.py](../src/backend/app/routers/robots.py) (mới): `GET /robots`.
- **WS** (role `panel`) thêm event `table.updated` (và `robot.updated` để dành) — `app/ws.py` không đổi, chỉ thêm chỗ gọi broadcast.

**Frontend dùng chung** ([shared/](../src/frontends/shared/)): `types.ts` += `party_size`/`seated_at` cho `Table`, thêm `Robot`, thêm biến thể `WsEvent` `table.updated`/`robot.updated`; `rest.ts` += `fetchTable`, `updateTableStatus`, `fetchRobots`.

**Panel** ([src/frontends/panel/](../src/frontends/panel/)): tách App.vue thành 3 component + 1 trang cuộn dọc:
- `components/TablesOverview.vue` — lưới **1 hàng 6 cột**, thẻ bàn: badge Trống/Đang ăn/Đã xong, số khách, **đồng hồ "đã ngồi"** (tick mỗi giây), số món + trạng thái bếp + tổng tiền của đơn hiện tại (cross-ref `tables`×`orders` qua `current_order_id`), nút **"Kết thúc bàn"** khi `DA_THANH_TOAN`.
- `components/RobotBoard.vue` — thẻ robot: bận/rảnh + pin (đỏ khi <25%) + **hoạt động** dạng chữ (`robots.activity`, vd "Đang ở dock", "Đang giao món · Bàn 4") thay cho toạ độ x/y. `seed_robots()` backfill `activity` cho fleet seed cũ; dispatcher sẽ set thật ở Mốc A/D.
- `components/KitchenBoard.vue` — KDS 3 cột (bê nguyên từ App.vue cũ).
- `format.ts` — `formatPrice`/`timeAgo`/`durationLabel` dùng chung. App.vue mở rộng WS xử lý `table.updated`/`robot.updated`, fetch thêm `robots`, ticker `now`.

**Customer UI** ([customer_ui](../src/frontends/customer_ui/)): màn đầu **theo trạng thái bàn** (sửa "menu web đang sai"):
- `components/screens/ServiceChoiceScreen.vue` (mới) — 2 nút: **Gọi món thêm** → `/menu`; **Thanh toán** → `/payment` (fetch tổng đơn hiện tại để dựng QR đúng số tiền).
- [router/index.ts](../src/frontends/customer_ui/src/router/index.ts): route `/service` + guard `beforeEach`: vào `'/'` → `GET /tables/{VITE_TABLE_ID}`; nếu bàn `DANG_PHUC_VU` **và có** `current_order_id` (đang ăn) → chuyển `/service`, ngược lại giữ **Chào mừng**. Guard chạy mọi lần về `'/'` nên sau khi đặt thêm cũng tự về đúng màn.
- [data/api.ts](../src/frontends/customer_ui/src/data/api.ts): += `fetchTable`, `fetchOrder`.
- **Đổi bàn ngay trên menu** (demo nhiều bàn bằng 1 tablet): badge "Bàn N" ở top-bar thành dropdown chọn Bàn 1…6 → `ui.setTableId`. Lưu `localStorage` (`tableSession.ts`, dùng chung với router guard) nên giữ qua reload. Đơn `POST /orders` đi theo bàn đang chọn.

**Đã test:** `vite build` panel (21 modules) + customer_ui (259 modules, esbuild) pass. Backend E2E (curl): migration cột mới OK trên DB seed cũ; `GET /robots` (2 robot); `POST /seatings` lưu `party_size`+`seated_at`; `POST /orders` giữ bàn `DANG_PHUC_VU`+`current_order_id` (không nhảy `CHO_BEP`); `PATCH /tables/{id}` `DA_THANH_TOAN`→`TRONG` clear sạch khách/giờ/đơn.

**Reset dữ liệu demo** (chạy lại từ đầu không cần restart/xoá file): `POST /admin/reset` ([admin.py](../src/backend/app/routers/admin.py)) xoá orders/seatings/payments/tasks, reset id AUTOINCREMENT, trả mọi bàn về `TRONG`, khôi phục robot mock; broadcast `{"type":"reset"}` → panel tự `load()` lại tức thì (kiosk phản ánh ở lần poll bàn kế). Gọi được bằng 3 cách: **nút "↺ Reset hệ thống"** ở header panel (có xác nhận; `resetSystem()` trong `@shared/rest`), **`make reset`** (curl tới backend đang chạy), hoặc offline `rm storage/db/orchestrator.db` → seed lại lúc khởi động.

**Đồng hồ digital** (giờ:phút, giờ thực máy, 24h, `tabular-nums`): thêm vào header cả 3 UI — panel (cạnh đèn kết nối/nút reset, gộp vào ticker 1s sẵn có), kiosk (pill ghim góc trên-phải), customer_ui (top-bar MenuScreen). Timer dọn khi unmount.

**Logo kiosk:** đồng bộ với menu — kiosk nạp `@tabler/icons-webfont` (như customer_ui) và dùng icon `ti-tools-kitchen-2`+`ti-robot` thay cho emoji `🍽️🤖` trong [kiosk/App.vue](../src/frontends/kiosk/src/App.vue).

> *Lưu ý:* `customer_ui` chưa có `tsconfig.json` nên `npm run build` (chạy `vue-tsc`) lỗi `TS5083` — **lỗi sẵn có, không do thay đổi này**; `vite build` (esbuild) vẫn build sạch. Type-check là việc dọn dẹp riêng.

### 2.9 Dispatcher — điều phối task cho robot (Mốc C)
Server thành "quản lý ca": sự kiện nghiệp vụ → tạo `task` → chọn robot → đẩy qua WS → robot báo về → đổi trạng thái bàn. **2 tầng task** (mục 6 kiến trúc): task hệ thống ("phục vụ bàn 3") ở server; task vật lý (waypoint+Nav2) do robot tự dịch — server **không** đụng Nav2.

**Backend:**
- [app/dispatcher.py](../src/backend/app/dispatcher.py) (mới): `create_task(kind,table,order)` lưu `tasks` PENDING rồi `try_assign()`. **Chọn robot**: lọc `online`(có WS)+`idle`+`battery≥20`, rồi **gần bàn đích nhất** (Euclid theo `x,y` heartbeat vs waypoint `TABLE_POS` lấy từ [restaurant_positions.md](../robot_ws/docs/restaurant_positions.md) marker q1–q6). Hết robot rảnh → task nằm chờ. Callback từ robot: `on_accepted`→IN_PROGRESS, `on_arrived`→đổi trạng thái **bàn** (`go_to_table`→`DANG_GOI_MON`, `deliver`→`DANG_AN`), `on_done`→task DONE + robot idle + `try_assign()` gắp việc kế. `on_robot_disconnect`→**requeue** task đang dở (re-dispatch sang robot khác). `on_heartbeat`→cập nhật pin/vị trí.
- [app/ws.py](../src/backend/app/ws.py) (sửa): hub thêm danh tính robot — `/ws?role=robot&robot_id=…`. Thêm sổ `_robots` (tra socket theo id) + `send_to_robot()` (gửi **đích danh 1 robot**, không broadcast). Vòng nhận tin **parse JSON & route** theo `type` (`heartbeat`/`task_accepted`/`arrived`/`task_done`) thay vì vứt; disconnect→`on_robot_disconnect`. Role `panel` giữ nguyên (một chiều). Import trễ `dispatcher` để tránh circular.
- [app/routers/tasks.py](../src/backend/app/routers/tasks.py) (mới): `GET /tasks` (xem hàng đợi, lọc `status`), `POST /tables/{id}/call` (nút bàn → task `call`).
- Nối sự kiện đã có: [tables.py](../src/backend/app/routers/tables.py) `POST /seatings`→`go_to_table`; [orders.py](../src/backend/app/routers/orders.py) `PATCH /orders/{id}` status=`XONG`→`deliver`. [schemas.py](../src/backend/app/schemas.py) += `TaskOut`.

**WS contract:** server→robot `{"type":"task.assign","task_id","kind","table_id","order_id"}`; robot→server `task_accepted`/`arrived`/`task_done` (kèm `task_id`) + `heartbeat` (`battery,x,y`). Event mới gửi `panel`: `task.created`/`task.updated`/`robot.updated`.

**Heartbeat-timeout watchdog** (phát hiện robot "treo"): bắt ca mà disconnect **không** bắt được — robot kẹt/đơ nhưng socket TCP vẫn mở (không có `WebSocketDisconnect`). `dispatcher._last_seen` ghi mốc heartbeat gần nhất; `watchdog_loop()` (chạy nền từ `lifespan`, quét mỗi `ORCH_WATCHDOG_INTERVAL_S=5s`) thấy robot im quá `ORCH_HEARTBEAT_TIMEOUT_S` (**mặc định 30s, chỉnh qua env**) → coi là treo → `on_robot_disconnect` (requeue + offline) + `manager.kick_robot` (đóng socket zombie). **Ngưỡng tính theo bội số khoảng heartbeat, KHÔNG theo tốc độ robot** (robot đi chậm vẫn đập nhịp đều); để rộng 30s phòng Jetson tải nặng ship heartbeat trễ. Idempotent: sau khi set `current_task_id=NULL`, lần disconnect thứ 2 (do kick) là no-op.

**Mock robot** ([scripts/mock_robot.py](../scripts/mock_robot.py), `make mockrobot ID=robo-1`): client WS giả lập đúng contract trên (heartbeat định kỳ; nhận `task.assign` → accept→drive(4s)→arrive→act(3s)→done). Cờ test: `--hang-on-task` (nhận task rồi đóng băng, giữ socket mở — test watchdog), `--hang-after N`. Thay cho robot Jetson thật (Mốc A) — sau chỉ đổi sang `ws_client.py`, contract giữ nguyên.

**Đã test E2E** (backend + 1–2 mock robot, qua curl): seat bàn 3→task `go_to_table`→robot accept/arrive(bàn `DANG_GOI_MON`)/done(robot idle); order `XONG`→`deliver`(bàn `DANG_AN`); nút `/call`→task `call`. **2 robot**: 2 task đồng thời chia theo robot gần nhất (bàn 1→robo-1, bàn 6→robo-2). **Re-dispatch (disconnect)**: kill robot giữa lúc chở task → task requeue PENDING → robot còn lại gắp & hoàn tất. **Re-dispatch (treo)**: robo-1 nhận task rồi `--hang-on-task` đóng băng → watchdog (timeout 6s khi test) đánh offline + kick → task requeue → robo-2 hoàn tất.

### 2.10 Panel — view hàng đợi nhiệm vụ + nút "Gọi robot" trên mỗi bàn
Ráp nốt UI cho dispatcher (backend đã phát event từ 2.9, chỉ thiếu màn hình) + thay thao tác `curl` gọi robot bằng nút bấm ngay trên Panel cho dễ demo.

**Frontend dùng chung** ([shared/](../src/frontends/shared/)): `types.ts` += interface `Task` (mirror `TaskOut`) + 2 biến thể `WsEvent` `task.created`/`task.updated`; `rest.ts` += `fetchTasks(status?)` (`GET /tasks`) và `callRobot(tableId)` (`POST /tables/{id}/call`).

**Panel** ([src/frontends/panel/](../src/frontends/panel/)):
- `components/TasksBoard.vue` (mới) — **hàng đợi dispatcher realtime**: lưới thẻ nhiệm vụ *đang hoạt động* (lọc bỏ `DONE`, sắp **cũ nhất trước** = đúng thứ tự server phục vụ). Mỗi thẻ: icon+nhãn loại (`go_to_table`→"Đón khách", `deliver`→"Giao món", `call`→"Gọi phục vụ"), "Bàn N", robot được giao (hoặc "chờ phân robot"), badge trạng thái (`PENDING`/`ASSIGNED`/`IN_PROGRESS`), `#id` + thời gian. Cuối khối: dòng đếm "N nhiệm vụ đã hoàn tất".
- `components/TablesOverview.vue` — thêm nút **"🔔 Gọi robot"** trên **mọi** thẻ bàn (gói trong `.t-actions` cùng nút "Kết thúc bàn"); emit `call` → App gọi `callRobot`. Có cờ `callBusy` (Set table id) → disable + đổi chữ "Đang gọi…" lúc request bay. *(Demo bấm thẳng trên Panel thay vì `curl`; nút phần cứng ESP32 để dành.)*
- `App.vue` — state `tasks` + `callBusy`; `load()` fetch thêm `fetchTasks()`; `onEvent` xử lý `task.created`/`task.updated` (upsert); handler `callTable(id)` (optimistic upsert task trả về, WS echo idempotent). Thêm zone "Hàng đợi nhiệm vụ" (đếm active ở `zone-sub`).
- `styles.css` += style cho `.t-call`/`.t-actions` + `.tasks-grid`/`.task-card` (viền trái theo trạng thái: `PENDING` vàng, `ASSIGNED` terracotta, `IN_PROGRESS` gold).

**Đã test:** `vite build` panel pass (23 modules). **E2E** (backend :8011 + mock robot `robo-1`): `POST /tables/3/call` → task `PENDING`; robot connect → tự gắp → `IN_PROGRESS` (robot busy "Đang tới bàn 3 (gọi phục vụ)") → `DONE` → robot về `idle`/dock. `GET /tasks` phản ánh đúng từng bước.

> *Còn lại của Mốc C:* nút bàn **phần cứng** thật (ESP32/WiFi → `/tables/{id}/call`) — hiện demo bằng **nút trên Panel** (đủ cho demo) hoặc `curl`.

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
- [x] **Dispatcher** ([app/dispatcher.py](../src/backend/app/dispatcher.py)): hàng đợi `tasks`, chọn robot idle/gần/đủ pin; đẩy task qua WS 2 chiều; máy trạng thái bàn (mục 6) — xem **2.9**.
- [x] **`POST /tables/{id}/call`** + luồng `call` ([app/routers/tasks.py](../src/backend/app/routers/tasks.py)): bấm nút → task `call` → robot tới (demo bằng `curl`).
- [x] **Thanh toán (mock)** — *chỉ giả lập **khâu chuyển tiền thật**; backend vẫn cập nhật trạng thái thật.* Luồng: `ServiceChoiceScreen` (nút **Thanh toán** → lấy tổng đơn hiện tại) → `PaymentScreen` hiện **ảnh QR VietQR** (`img.vietqr.io`, mock số tiền + STK) + nút **"Đã thanh toán xong"** → gọi **`POST /payments/{order_id}`** ([payments.py](../src/backend/app/routers/payments.py)): ghi 1 dòng `payments` `PAID` (tính `amount` server-side từ `orders.total`, idempotent nếu bấm 2 lần) + đẩy bàn sang **`DA_THANH_TOAN`** + **broadcast `table.updated`** → panel hiện bàn "đã thanh toán" với nút **"Kết thúc bàn"** (`PATCH /tables/{id}` `→ TRONG`, đã có) để **trống lại** cho khách kế. Tablet clear giỏ & về màn chính (timeout idle 30s chỉ về màn chính, **không** tính là đã trả). **Không** dùng webhook/sandbox PSP — để dành nếu sau cần đối soát thật (thêm `/qr` + `/webhooks/payment`). *Đã test (TestClient): seat→order→pay `201` (bàn `DANG_PHUC_VU`→`DA_THANH_TOAN`), double-tap tái dùng payment id, `Kết thúc bàn`→`TRONG`, pay order lạ `404`.*
- [x] **Panel view hàng đợi nhiệm vụ + nút "Gọi robot" mỗi bàn** — xem **2.10** (đóng nốt UI cho dispatcher; nút trên Panel thay `curl`).
- [ ] **Nút bàn phần cứng** (ESP32/WiFi → gọi `/tables/{id}/call`); demo tạm bằng **nút trên Panel** / `curl`.

### 3.3 Mốc A & D — robot
- [ ] **Brain↔Body WS localhost** + **node bridge** `ai_hw_bridge` (đang `COLCON_IGNORE`): nhận task → tra `restaurant_positions.md` → đặt Nav2 goal → báo `arrived`/`task_done`.
- [ ] **`ws_client.py`** (Brain → Server) để robot thành WS client.
- [~] **Agent sinh lệnh hành động** (rủi ro lớn nhất, mục 12) — **nửa "quyết định" đã xong**: agent giờ sinh **lệnh UI** (`open_menu`/`open_payment`) bên cạnh text, suy ra **xác định** từ tool vừa chạy thành công (`sync_cart`/`search`→`open_menu`, `request_payment`→`open_payment`; `confirm_order` trung tính). Code ở [agent/actions.py](../ai_waiter_core/ai_waiter_core/agent/actions.py) (logic + seam `emit_action`), set trong [update_state_node.py](../ai_waiter_core/ai_waiter_core/agent/nodes/update_state_node.py), surface qua `chat()` → `result["action"]`. Đã test ở mức node (tool→action). **Còn lại = "nửa giao": cầu nối Brain→tablet (`emit_action` chưa cắm transport)** + lệnh `navigate`/`return_dock` (cần robot). *State `ui_action` reset mỗi lượt nên không rò sang lượt sau.*
- [ ] **Voice thật**: thay mock `stores/voice.ts` bằng STT + LLM endpoint + TTS.
- [ ] **Multi-robot**: instance thứ 2 trong sim, lane 1 chiều, cân nhắc Open-RMF/Zenoh.

---

## 4. Ý tưởng phát triển / cải thiện
- **`table_id` động cho customer_ui**: hiện tablet gán tĩnh qua `VITE_TABLE_ID` ([ui.ts](../src/frontends/customer_ui/src/stores/ui.ts) `tableId`). Khi có Kiosk seating, nên set `ui.tableId` lúc check-in (query param/route hoặc gọi API), thay vì cố định mỗi máy 1 bàn.
- **Migrate customer_ui sang `shared/`**: customer_ui còn `data/api.ts` riêng (trùng phần order types/client với `shared/`). Thêm alias `@shared` vào [vite.config.ts](../src/frontends/customer_ui/vite.config.ts) rồi dùng chung — dọn dẹp optional.
- **Nâng lên npm workspaces khi share component Vue**: lúc làm Kiosk cần tái dùng component menu (có deps) → chuyển `src/frontends/` thành workspace (`apps/customer_ui|kiosk|panel` + `packages/ui`). TS thuần thì `shared/` + alias là đủ (đã làm).
- **Serve frontend tĩnh từ FastAPI** (prod) — **đã CHỐT làm pipeline deploy (2026-06):** SERVER build
  customer_ui/Kiosk/Panel → FastAPI mount static cùng origin `:8000`; Jetson + laptop khác chỉ mở URL
  (`chromium --kiosk http://<SERVER_IP>:8000/`), **không Node/không build cục bộ**. Chi tiết:
  [setup_test_guide.md §3.Web](setup_test_guide.md) + [SYSTEM_ARCHITECTURE.md §3](SYSTEM_ARCHITECTURE.md).
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
