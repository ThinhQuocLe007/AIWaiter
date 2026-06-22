# Kiến trúc hệ thống — AI Waiter (nhà hàng nhiều robot)

> Tài liệu này mô tả **toàn bộ kiến trúc** hệ thống nhà hàng robot phục vụ: các thành phần,
> các web app, cách chúng giao tiếp, cách giao task cho hệ thống và cho robot, mô hình dữ liệu,
> hiện trạng đã code, và **cách demo trên 3 laptop**. Dùng để cả nhóm đọc và bám theo khi triển khai.
>
> Phiên bản: bản thiết kế (server chưa code; UI khách đã có khung). Cập nhật: 2026-06.

---

## 0. TL;DR (đọc nhanh)

- **2 loại "não":**
  - **Não hội thoại** = LLM chạy *local trên từng robot* (nói chuyện với khách, độ trễ thấp).
  - **Não điều phối** = *1 server trung tâm* giữ trạng thái bàn/đơn/tiền và chia việc cho robot.
- **Stack chốt:** `FastAPI + SQLite` (server) · `WebSocket + REST` (giao tiếp) · `ROS 2 Humble + Nav2`
  (di chuyển robot). **KHÔNG dùng MQTT** — mọi thứ đã nằm trong web stack + ROS.
- **Local-first:** chạy trong mạng LAN của quán, không phụ thuộc internet (trừ cổng thanh toán).
- **2 giao diện web** (Kiosk cổng + **Bảng điều khiển** gộp bếp & giám sát) + **1 UI màn hình robot**
  (đã có khung Vue) + **nút bấm phần cứng ở mỗi bàn**; tất cả do **cùng 1 backend** phục vụ.
- **Robot làm đúng 3 việc:** `ĐẾN_BÀN` (gọi món lần đầu) · `GIAO_MÓN` · `GỌI` (khách bấm nút → robot
  tới hỏi: *đặt thêm* hay *thanh toán*).
- **Demo:** 3 laptop — (1) server + Kiosk, (2) Gazebo xem TurtleBot4 chạy + UI robot,
  (3) Bảng điều khiển (bếp + giám sát).

---

## 1. Phạm vi nghiệp vụ (luồng thực tế của quán)

1. Khách tới quán, **tự thao tác trên kiosk web ở cổng**: xem bàn nào trống, chọn bàn + nhập số người.
2. **Nhân viên (người thật) dẫn khách** tới bàn. Khi tới nơi, **robot đã đợi sẵn ở bàn**.
3. Robot **bật menu trên màn hình** cho khách đặt món (có LLM/giọng nói hỗ trợ). Đặt xong **robot về dock**.
4. Bếp nấu xong → **đặt món lên robot** → robot **chở tới bàn** cho khách lấy.
5. Khi cần gì, khách **bấm nút trên bàn** → robot tới → **hỏi khách muốn gì**:
   - *Đặt thêm món:* mở menu trên màn hình → khách đặt tiếp → robot về.
   - *Thanh toán:* hiện lịch sử món + tổng tiền → khách confirm → **thanh toán QR** ngay trên robot.
6. **Dọn bàn do nhân viên (người thật)** làm. Bàn được set lại `TRỐNG`.

> Những phần **người thật làm** (dẫn bàn, dọn bàn) → hệ thống *không* cần perception/đếm người,
> *không* cần task dẫn/dọn cho robot. Đây là điểm giúp hệ đơn giản đi nhiều.

---

## 2. Tổng quan kiến trúc

```
┌──────────────────── SERVER TRUNG TÂM "Orchestrator" (FastAPI, 1 máy LAN) ───────────────────┐
│                                                                                              │
│   REST API + WebSocket hub                         SQLite  (bàn, đơn, lịch sử, thanh toán)   │
│   ┌─ Table Manager   (trạng thái từng bàn)                                                   │
│   ┌─ Order Service   (đơn hàng + lịch sử)                                                    │
│   ┌─ Dispatcher      (biến sự kiện nghiệp vụ → task → chọn robot rảnh gần nhất)              │
│   ┌─ Fleet Manager   (theo dõi robot: trạng thái, pin, vị trí)                               │
│   └─ Payment Service (tạo QR, nhận webhook, chốt đã trả)                                     │
│                                                                                              │
└───▲────────────▲──────────────────▲───────────────────▲──────────────────▲──────────────────┘
    │ WS         │ WS/REST           │ WS/REST            │ HTTP              │ HTTP webhook
    │            │                   │                    │                   │
┌───┴───┐  ┌─────┴─────┐   ┌─────────┴─────────┐   ┌──────┴──────┐   ┌────────┴─────────┐
│ ROBOT │  │ Kiosk web │   │ Bảng điều khiển   │   │ Nút bàn     │   │ Cổng thanh toán  │
│ 1..N  │  │ (cổng)    │   │ (bếp + giám sát)  │   │ (phần cứng) │   │ (VietQR/MoMo/    │
│       │  │           │   │ — 1 web duy nhất  │   │ 1 nút/bàn   │   │  ZaloPay)        │
└───┬───┘  └───────────┘   └───────────────────┘   └─────────────┘   └──────────────────┘
    │ localhost WebSocket  (Brain ↔ Body — bên trong mỗi robot, không đổi)
┌───┴──────────────────────────────────────────┐
│ JETSON (trên mỗi robot)                       │
│  ┌─ BRAIN (env uv, Python 3.10)               │
│  │   LLM gemma4 · RAG menu · STT/TTS           │
│  │   + UI khách (Vue) chạy trên màn hình robot │
│  │   ws_client → server  +  ws_server → Body   │
│  └─ BODY  (ROS 2 Humble + Nav2)                │
│      ai_brain_bridge.py: nhận task → đặt goal  │
│      Nav2 → robot di chuyển; báo ack/trạng thái│
└───────────────────────────────────────────────┘
        ↑ robot né nhau bằng lidar/costmap của Nav2 (coi nhau là chướng ngại động)
```

### Vì sao thiết kế như vậy
- **Tách Brain/Body** vì 2 môi trường Python *không import lẫn nhau được*: Brain cần
  `torch/whisper/langchain` (env uv), Body cần `rclpy` (env ROS/colcon). → nói chuyện qua đường ống.
- **Brain ↔ Body = WebSocket localhost:** cùng 1 máy (Jetson), 2 tiến trình → ống nội bộ.
- **Robot ↔ Server = WebSocket qua LAN:** server cần *đẩy task xuống* và *nhận trạng thái lên* bất cứ
  lúc nào → kênh 2 chiều luôn mở (REST hỏi-đáp không làm được việc đẩy ngược).
- **Web clients ↔ Server = REST + WebSocket:** REST cho thao tác (tạo đơn, tick món xong), WebSocket
  cho realtime (Bảng điều khiển thấy đơn mới + robot di chuyển cùng lúc).
- **Robot ↔ Robot = Nav2/DDS:** không cần broker; Nav2 đã coi robot khác là chướng ngại động.
- **Không MQTT:** không có thiết bị ngoài-ROS cần pub/sub; thêm broker là thừa việc vận hành.

---

## 3. Cần bao nhiêu web? (trả lời trực tiếp)

**Chỉ 2 web + 1 UI màn hình robot (+ nút bấm phần cứng ở bàn). Tất cả do CÙNG 1 backend (FastAPI)
phục vụ** — không phải nhiều server, chỉ là vài "ứng dụng frontend" cùng gọi 1 API.

| # | Giao diện | Chạy ở đâu | Ai dùng | Làm gì | Trạng thái |
|---|---|---|---|---|---|
| 1 | **Kiosk cổng** | Tablet ở cổng | Khách | Xem bàn trống → chọn bàn + số người | ⬜ chưa code |
| 2 | **Bảng điều khiển** (bếp + giám sát, **gộp 1**) | Laptop quầy/bếp | Nhân viên | Xem đơn mới theo từng bàn, tick "món xong", **đồng thời** theo dõi vị trí robot / pin / hàng đợi task | ⬜ chưa code |
| 3 | **UI màn hình robot** (`customer_ui`) | Màn hình LCD trên robot | Khách | Menu khi đặt món · bill + thanh toán · trợ lý giọng nói | 🟡 **đã có khung** |
| — | **Nút bàn** | Gắn trên mỗi bàn | Khách | **Phần cứng, không phải web** — bấm 1 nút → server tạo task gọi robot | ⬜ chưa code |

> **Bảng điều khiển gộp bếp + giám sát:** 1 web duy nhất cho nhân viên — vừa là Kitchen Display (đơn
> mới theo bàn, tick món xong), vừa là bảng giám sát (sơ đồ vị trí robot, pin, trạng thái bàn, hàng đợi
> task). Gộp lại cho dễ quản lý: nhân viên chỉ cần nhìn 1 màn hình.
>
> Tất cả web là tĩnh, build cho FastAPI serve (hoặc `vite dev` khi dev). UI robot (#3) chạy full-screen
> (kiosk mode) trên màn hình robot; có thể dùng lại component menu/giỏ hàng của `customer_ui` cho Kiosk #1.

### 3.1 Hiện trạng UI robot đã code (`src/frontends/customer_ui`)
Vue 3 + Vite + TypeScript + Pinia + Vue Router, thiết kế cố định **1024×600** (đúng LCD robot), tự
scale theo viewport khi chạy máy dev.

- **Màn hình:** `WelcomeScreen` → `MenuScreen` → `ConfirmationScreen`, và **`PaymentScreen`** (đã có).
- **Menu:** `CategoryTabs`, `FoodGrid`, `FoodCard`, `FoodDetailModal`, `CartButton`.
- **Giỏ hàng:** `CartDrawer`, `CartItem`, `CartSummary` (store `cart.ts`).
- **Trợ lý giọng nói:** `VoicePanel`, `SmartBannerCard` (store `voice.ts`, hiện là **mock timer**:
  idle→listening→thinking→speaking).
- **Dữ liệu menu:** `menuAdapter.ts` đọc **tĩnh** từ `assets/data/menu.json` (chung với backend Python).

**Còn thiếu (Phase 2 của UI — nối vào kiến trúc này):**
- `stores/menu.ts → loadMenu()`: fetch menu từ **FastAPI** thay vì import tĩnh.
- `MenuScreen → confirmOrder()`: **POST đơn** lên server (thay vì chỉ chuyển màn).
- `stores/voice.ts`: thay mock bằng **STT thật + LLM endpoint + TTS** (nối Brain).
- `PaymentScreen`: nối **bill thật** từ server + **QR thanh toán** + chờ xác nhận webhook.
- Nhận lệnh từ Brain/Server để **tự chuyển màn** (vd: tới bàn → mở `/menu`; gọi tính tiền → `/payment`).

---

## 4. Bên trong mỗi robot (Brain / Body)

```
AI_Waiter/                              (env uv, Python 3.10 — BRAIN)
├── ai_waiter_core/ai_waiter_core/
│   ├── agent/         (LangGraph agent: trò chuyện, gọi RAG, SINH LỆNH HÀNH ĐỘNG)
│   ├── services/      (order_worker, payment_worker, RAG menu)
│   ├── perception/    (STT)   ├── output/ (TTS)   ├── schemas/ (pydantic — dùng chung WS)
│   └── interfaces/
│       ├── ws_server.py   ← server WS phía Brain, nói chuyện với Body  (Phase 4)
│       └── ws_client.py   ← client WS nối lên Server trung tâm        (Phase 6)
├── src/frontends/customer_ui/          ← UI màn hình robot (Vue) — mục 3.1
└── robot_ws/                           (env colcon, ROS 2 Humble — BODY)
    ├── src/sim/turtlebot4_ignition_bringup/   (Gazebo: turtlebot4_ignition.launch.py, world restaurant.sdf)
    ├── src/common/turtlebot4_navigation/      (Nav2 — điều hướng tới waypoint)
    └── src/real/ai_hw_bridge/                 (CHỖ cho node bridge: rclpy + WS client → Brain)
                                                 hiện COLCON_IGNORE (trống) — CẦN VIẾT
```

- **Brain** giữ "miệng" + "mặt" robot: nghe (STT) → hiểu/đáp (LLM + RAG menu) → nói (TTS), hiển thị
  `customer_ui`, và **sinh lệnh hành động**. Đồng thời là **client của Server trung tâm**.
- **Body** giữ "chân" robot: nhận lệnh → đặt goal cho **Nav2** → robot di chuyển → báo
  `arrived`/`nav_failed`.
- **Đã có trong repo:** các package **TurtleBot4 gốc** (sim `turtlebot4_ignition_bringup`, điều hướng
  `turtlebot4_navigation`) để xem **TurtleBot4 di chuyển** (xem mục 10). **Node bridge chưa viết** —
  chỗ trống `ai_hw_bridge` (đang `COLCON_IGNORE`). Toạ độ **dock + bàn 1–6** đã có sẵn ở
  `robot_ws/docs/restaurant_positions.md` → đây là nguồn waypoint cho Body.

---

## 5. Giao tiếp & giao thức (tất cả message là JSON)

| Cặp giao tiếp | Cơ chế | Lý do |
|---|---|---|
| Web clients ↔ Server | **REST** (thao tác) + **WebSocket** (realtime push) | Web cần cả hỏi-đáp lẫn nhận đẩy |
| Robot (Brain) ↔ Server | **WebSocket** (LAN) | Server đẩy task xuống + robot báo trạng thái lên |
| Brain ↔ Body (trong robot) | **WebSocket** (localhost) | 2 env Python tách biệt cùng máy |
| Robot ↔ Robot | **ROS 2 / Nav2 (DDS)** | Né va chạm tự động; không cần broker |
| Server ↔ Cổng thanh toán | **HTTP webhook** | Cổng báo "đã nhận tiền" về server |

### Quy ước message
Mọi message **luôn có `robot_id`, `table_id`/`order_id`, `task_id`** khi liên quan — để multi-robot
không phải sửa contract về sau.

**Server → Robot (giao task):**
```jsonc
{ "type": "task", "task_id": "t-101", "kind": "go_to_table",  "table_id": 3 }              // gọi món lần đầu
{ "type": "task", "task_id": "t-102", "kind": "deliver",      "table_id": 3, "order_id": "o-55" }
{ "type": "task", "task_id": "t-103", "kind": "call",         "table_id": 3 }              // khách bấm nút bàn
{ "type": "cancel", "task_id": "t-101" }
```

**Robot → Server (trạng thái/ack):**
```jsonc
{ "type": "task_accepted", "task_id": "t-101", "robot_id": "r1" }
{ "type": "arrived",       "task_id": "t-101", "robot_id": "r1", "table_id": 3 }
{ "type": "task_done",     "task_id": "t-102", "robot_id": "r1" }
{ "type": "task_failed",   "task_id": "t-101", "robot_id": "r1", "reason": "nav_timeout" }
{ "type": "heartbeat",     "robot_id": "r1", "battery": 0.82, "x": 4.1, "y": 2.0, "state": "idle" }
```

**Brain → Body (trong robot):**
```jsonc
{ "type": "navigate", "table_id": 3 }     // tới waypoint bàn 3
{ "type": "return_dock" }                 // về dock
```
**Body → Brain:**
```jsonc
{ "type": "arrived", "table_id": 3 }
{ "type": "nav_failed", "reason": "..." }
{ "type": "pose", "x": 4.1, "y": 2.0, "state": "moving|idle" }
```

---

## 6. Cơ chế giao task — "task hệ thống" vs "task robot" (phần lõi)

Có **2 tầng task**, đừng nhầm:
- **Task hệ thống (nghiệp vụ):** "phục vụ bàn 3" — do **Server** tạo từ một *sự kiện nghiệp vụ*.
- **Task robot (vật lý):** "đi tới waypoint bàn 3, mở đúng màn hình" — do **Robot** dịch ra.

### Vòng đời 1 task
```
SỰ KIỆN NGHIỆP VỤ                 SERVER (Dispatcher)              ROBOT
─────────────────                ──────────────────              ─────
kiosk chọn bàn 3      ──►  tạo Task(go_to_table, t=3)
bếp tick "xong"       ──►  tạo Task(deliver, o=55)         PENDING
khách bấm NÚT bàn     ──►  tạo Task(call, t=3)                │
                                  │ Dispatcher chọn robot rảnh + gần nhất + đủ pin
                                  ▼
                            Task → ASSIGNED ───── gửi WS ───►  nhận task
                                                               task_accepted ──► IN_PROGRESS
                                                               đặt Nav2 goal → di chuyển
                                  ◄──────── arrived ───────────  tới bàn
                            cập nhật trạng thái bàn             làm hành động:
                                                                 - go_to_table → mở /menu, chờ đặt
                                                                 - deliver     → chờ khách lấy món
                                                                 - call        → HỎI khách (voice/màn hình):
                                                                     • đặt thêm → mở /menu
                                                                     • thanh toán → mở /payment (bill+QR)
                                  ◄──────── task_done ─────────  xong → về dock
                            Task → DONE, robot → idle
```

### Dispatcher chọn robot thế nào
Khi có task `PENDING`, chọn robot theo ưu tiên: (1) đang **idle**, (2) **gần** bàn đích nhất (theo
`x,y` heartbeat), (3) **đủ pin** (vd > 20%; thấp → về sạc). → Chọn tập trung nên **không bao giờ 2
robot cùng chạy 1 bàn**. Hết robot rảnh thì task chờ trong hàng đợi, có robot rảnh là gắp ngay.

### Máy trạng thái của BÀN (Server giữ)
```
TRỐNG ─(kiosk chọn)→ ĐÃ_ĐẶT ─(robot tới)→ ĐANG_GỌI_MÓN ─(đặt xong)→ CHỜ_BẾP
   ↑                                              ▲                       │
   │                              (bấm nút→đặt thêm)│             (bếp xong, giao)
(nhân viên dọn, set lại)                          │                      ▼
DỌN ←─(đã thanh toán)── ĐANG_THANH_TOÁN ←──────────┴──────────────── ĐANG_ĂN
                          ▲   (bấm nút → robot tới → chọn "thanh toán")
                          └── khách bấm NÚT khi ĐANG_ĂN, robot hỏi → rẽ nhánh:
                              đặt thêm (→ CHỜ_BẾP) hoặc thanh toán (→ ĐANG_THANH_TOÁN)
```

---

## 7. Luồng nghiệp vụ đầy đủ (end-to-end)

### 7.1 Đặt bàn → gọi món
```
Khách@Kiosk          Server                 Dispatcher        Robot         Bếp@Bảng ĐK
   │ chọn bàn 3, 2 người                       │               │                │
   │──REST POST /seatings──►│ bàn3=ĐÃ_ĐẶT      │               │                │
   │                        │──tạo task go_to_table(3)──►│      │                │
   │                        │                  │─WS task──────►│ tới bàn 3      │
   │                        │◄─────────── arrived ──────────────│ (đợi sẵn, mở /menu)
   │ (nhân viên dẫn khách tới)                                  │                │
   │ ───────────────── khách đặt món trên màn hình robot ──────►│                │
   │                        │◄──REST POST /orders (món)─────────│                │
   │                        │ bàn3=CHỜ_BẾP                      │ về dock        │
   │                        │──WS "đơn mới"───────────────────────────────────►│ hiện đơn
```

### 7.2 Bếp xong → giao món
```
Bếp@Bảng ĐK        Server              Dispatcher       Robot
  │ tick "xong"       │                   │              │
  │──REST PATCH /orders/55 done──►│ tạo task deliver(55)─►│
  │                   │                   │─WS task──────►│ (nhân viên đặt món lên robot)
  │                   │◄────────── arrived (bàn 3) ───────│ tới bàn, chờ khách lấy
  │                   │◄────────── task_done ─────────────│ → về dock; bàn3=ĐANG_ĂN
```

### 7.3 Khách bấm nút → robot tới hỏi (đặt thêm / thanh toán)
```
NÚT bàn 3          Server               Dispatcher    Robot                       Cổng TT
  │ bấm nút           │                   │            │                            │
  │──HTTP POST /tables/3/call──────►│ tạo task call(3)─►│                            │
  │                    │                  │─WS task────►│ tới bàn                    │
  │                    │◄────── arrived ─────────────────│ HỎI: "đặt thêm hay tính tiền?"
  │                    │                                 │                            │
  │   ── nhánh A: ĐẶT THÊM ──        │                  │ mở /menu → khách đặt        │
  │                    │◄──REST POST /orders (món)───────│ bàn3=CHỜ_BẾP → về dock     │
  │                    │                                 │                            │
  │   ── nhánh B: THANH TOÁN ──      │                  │ mở /payment                │
  │                    │◄──GET /orders/55/bill───────────│ hiện món + tổng tiền + QR  │
  │ confirm + quét QR ───────────────────────────────────────────────────────────────►│
  │                    │◄──────────── webhook "đã nhận tiền" ──────────────────────────│
  │                    │ order=ĐÃ_TRẢ, bàn3=DỌN          │ báo "thành công" → về dock │
  │                    │◄────── task_done ───────────────│                            │
```
> **An toàn:** robot **chỉ hiển thị** QR; tiền được **server xác nhận qua webhook**. Không để robot
> tự quyết "đã trả". Việc "đặt thêm hay thanh toán" do khách chọn trên màn hình robot (hoặc trả lời
> bằng giọng nói → Brain hiểu ý định).

---

## 8. Mô hình dữ liệu (SQLite)

```sql
tables(      id, name, capacity, status, current_order_id )
dishes(      id, name, price, category, available )            -- menu, nguồn cho RAG + menu.json
orders(      id, table_id, status, total, created_at )
order_items( id, order_id, dish_id, qty, note, status )
robots(      id, name, status, battery, x, y, current_task_id ) -- cập nhật từ heartbeat
tasks(       id, kind, table_id, order_id, robot_id, status, created_at, updated_at )
payments(    id, order_id, method, amount, status, txn_ref, paid_at )
```
- **Vì sao SQLite:** quán nhỏ → ít ghi đồng thời; *1 file, không server DB*, backup = copy file, vẫn có
  transaction cho thanh toán. Dùng SQLAlchemy/SQLModel → đổi sang PostgreSQL sau chỉ là đổi connection string.

---

## 9. Danh sách API & sự kiện WebSocket (bản nháp)

**REST (web clients):**
```
GET   /tables                      → danh sách bàn + trạng thái (kiosk, bảng điều khiển)
POST  /seatings        {table_id, party_size}   → nhận bàn (kiosk)
GET   /menu                        → danh sách món (UI robot: stores/menu.ts)
POST  /orders          {table_id, items[]}      → tạo đơn (UI robot: confirmOrder)
PATCH /orders/{id}     {status}    → bếp tick xong (bảng điều khiển)
GET   /orders/{id}/bill            → lấy bill (UI robot: PaymentScreen)
POST  /tables/{id}/call            → khách bấm NÚT bàn → robot tới hỏi (đặt thêm / thanh toán)
POST  /payments/{order_id}/qr      → tạo QR thanh toán
POST  /webhooks/payment            → cổng TT báo đã nhận tiền
```
> `/tables/{id}/call` là endpoint mà **nút phần cứng** gọi (qua firmware/ESP32 hoặc cầu nối). Generic:
> server tạo task `call`, không phân biệt trước là đặt thêm hay thanh toán — khách quyết khi robot tới.

**WebSocket (1 endpoint `/ws`, phân luồng theo `role`):**
```
role=robot      : server⇄robot (task, ack, heartbeat — mục 5)
role=panel      : server→Bảng điều khiển (đơn mới/cập nhật theo bàn + vị trí robot/pin/task — REALTIME, gộp 1 kênh)
```

---

## 10. DEMO TRÊN 3 LAPTOP (mạng LAN chung)

Mục tiêu: chạy thử **không cần robot thật**. Robot được thay bằng **TurtleBot4 mô phỏng trong Gazebo**.

> ⚠️ **Lưu ý quan trọng về Gazebo:** trong sim, **chỉ TurtleBot4 là phần thật của hệ thống** (để xem
> robot di chuyển bằng Nav2). World `restaurant.sdf` có vẽ model bàn/bếp/ArUco marker nhưng đó chỉ là
> **trang trí trực quan** — *không* phải logic của hệ. Hệ thống chỉ dùng **toạ độ waypoint** (dock +
> bàn 1–6) ghi ở `robot_ws/docs/restaurant_positions.md`; Body lái TurtleBot4 tới đúng toạ độ đó. Đổi
> sang world khác (depot/maze/warehouse) hay world trống cũng chạy được, miễn waypoint đúng.

Cả 3 laptop nối **cùng 1 WiFi/LAN**; Server có IP cố định, ví dụ `192.168.1.10`.

```
        WiFi / LAN của quán  (192.168.1.0/24)
   ┌───────────────┬─────────────────────────┬────────────────────┐
   │               │                         │                    │
┌──▼───────────┐ ┌─▼─────────────────────┐ ┌─▼──────────────────┐
│ LAPTOP 1     │ │ LAPTOP 2              │ │ LAPTOP 3           │
│ SERVER+KIOSK │ │ ROBOT (mô phỏng)      │ │ BẢNG ĐIỀU KHIỂN    │
│ 192.168.1.10 │ │ 192.168.1.11          │ │ (chỉ trình duyệt)  │
├──────────────┤ ├───────────────────────┤ ├────────────────────┤
│ FastAPI +    │ │ ROS 2 Humble + Nav2    │ │ Mở trình duyệt tới: │
│ SQLite       │ │ Gazebo: chạy TurtleBot4│ │ http://192.168.1.10 │
│              │ │  → THẤY ROBOT DI CHUYỂN│ │   /panel            │
│ Web (tab):   │ │ node bridge            │ │                    │
│ /kiosk       │ │  (WS client → 1.10)    │ │ 1 web gộp bếp+giám: │
│ (nút bàn giả │ │ Brain hoặc mock-brain  │ │  - đơn mới theo bàn │
│  lập = curl  │ │ customer_ui (Vue) =    │ │  - tick "món xong"  │
│  /tables/3/  │ │  màn hình robot        │ │  - vị trí robot/pin │
│  call)       │ │  → /menu, /payment     │ │  - hàng đợi task    │
└──────┬───────┘ └───────────┬─────────────┘ └─────────┬──────────┘
       │  WebSocket/REST      │ WebSocket (task/ack)     │ WebSocket
       └─────────────────────►│◄─────────────────────────┘
                       (tất cả trỏ về 192.168.1.10:8000)
```

### Laptop 1 — Server + Kiosk (sân khấu chính)
- Chạy FastAPI (cổng `8000`) + SQLite (`restaurant.db`).
- Mở tab **Kiosk** (`/kiosk`). **Nút bàn** chưa có phần cứng → giả lập bằng `curl -X POST
  http://192.168.1.10:8000/tables/3/call` (hoặc 1 nút bấm nhỏ trên trang dev).

### Laptop 2 — Robot mô phỏng ("thấy robot di chuyển")
- `ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py world:=restaurant` → Gazebo +
  RViz, **TurtleBot4 chạy bằng Nav2** (`turtlebot4_navigation`) giữa các toạ độ waypoint.
- **Node bridge** (cần viết, vd trong `ai_hw_bridge`): **WS client** tới
  `ws://192.168.1.10:8000/ws?role=robot`, nhận task → tra toạ độ bàn (`restaurant_positions.md`) → đặt
  Nav2 goal → robot chạy trong Gazebo → báo `arrived`/`task_done`.
- **`customer_ui` (Vue)** mở full-screen ở đây = màn hình robot; theo lệnh sẽ chuyển `/menu`, `/payment`.
- **2 chế độ:** *mock-brain* (bỏ LLM/mic, bridge tự dịch task→goal — đủ demo luồng + di chuyển) hoặc
  *full-brain* (LLM gemma4 + STT/TTS để demo cả đặt món bằng giọng nói).
- **Multi-robot:** mở 2 instance, đổi `robot_id`/namespace (`r1`, `r2`) → bảng điều khiển hiện 2 robot,
  Dispatcher tự chia task.

### Laptop 3 — Bảng điều khiển (bếp + giám sát, gộp 1)
- Chỉ **mở trình duyệt** tới `http://192.168.1.10:8000/panel`.
- Một màn hình duy nhất cho nhân viên: **đơn mới theo từng bàn** + nút **tick "món xong"** (vai trò bếp),
  **đồng thời** sơ đồ **vị trí robot / pin / trạng thái bàn / hàng đợi task** (vai trò giám sát).

### Kịch bản demo gợi ý (~5 phút)
1. **L1/Kiosk:** chọn "Bàn 3, 2 người" → **L3** thấy task `go_to_table` → **L2/Gazebo** robot chạy tới bàn 3.
2. **L2/customer_ui:** đặt 2 món → **L3** hiện đơn mới của bàn 3.
3. **L3:** tick "món xong" → **L2** robot chạy về bàn 3 giao món → **L3** bàn `ĐANG_ĂN`.
4. **L1:** "bấm nút bàn 3" (curl `/tables/3/call`) → **L2** robot tới bàn, `customer_ui` hỏi "đặt thêm /
   thanh toán" → chọn **thanh toán** → mở `/payment` (bill+QR) → giả lập webhook → **L3** bàn `DỌN`.
   (Hoặc chọn **đặt thêm** → quay lại bước 2.)
5. (Tùy chọn) Mở robot `r2` ở L2, tạo 2 yêu cầu cùng lúc → thấy Dispatcher chia cho 2 robot.

> **Cổng thanh toán khi demo:** dùng *sandbox* VietQR/MoMo/ZaloPay, hoặc 1 nút "giả lập đã trả" gọi
> thẳng `/webhooks/payment` để demo không cần tiền thật.

---

## 11. Lộ trình triển khai (làm theo mốc)

- **Mốc A — 1 robot, không server:** Brain↔Body qua localhost WS; robot tới bàn + nhận lệnh đặt/giao
  với 1 con. Chứng minh đường ống Brain/Body chạy.
- **Mốc B — dựng Server trung tâm:** FastAPI + SQLite; chuyển trạng thái bàn/đơn lên server; robot thành
  WS client; **nối `customer_ui` vào backend** (loadMenu, confirmOrder); làm Kiosk + **Bảng điều khiển** cơ bản.
- **Mốc C — Dispatcher + nút bàn + thanh toán:** hàng đợi task, chọn robot, hoàn thiện Bảng điều khiển
  (giám sát realtime), endpoint `/tables/{id}/call`, luồng `call` (đặt thêm / thanh toán QR + webhook,
  `PaymentScreen`).
- **Mốc D — multi-robot:** thêm robot thứ 2 trong sim; thiết kế **lane 1 chiều** giảm kẹt; cân nhắc
  **Open-RMF**/**Zenoh** nếu đông robot hoặc WiFi yếu.

---

## 12. Rủi ro & quyết định cần chốt

**Rủi ro lớn nhất — KHÔNG chỉ là "nối dây":**
Agent hiện *chỉ trả về text*, **chưa sinh lệnh điều khiển robot** (đi bàn nào, giao món). Phần việc thật
là **thêm logic để agent phát lệnh hành động** + map lệnh → task → Nav2 goal.

**Các rủi ro khác:**
- **Giao thông nhiều robot lane hẹp:** Nav2 né va chạm nhưng dễ *kẹt đối đầu* → thiết kế **lane 1 chiều**;
  đông thì Open-RMF.
- **Mất WiFi:** robot cần *timeout + tự về dock*; server *re-dispatch* task nếu robot rớt; dùng heartbeat
  phát hiện robot "chết".
- **Thanh toán:** qua transaction + webhook; server là nguồn chân lý, robot chỉ hiển thị.
- **Voice mock → thật:** `stores/voice.ts` mới là timer giả; nối STT/LLM/TTS thật còn nhiều việc.

**Cần chốt trước khi code:**
1. **LLM chạy đâu?** Local Jetson (đang chọn, gemma4) hay server ngoài? — *Khuyến nghị: local để robot
   nói với khách không phụ thuộc mạng.*
2. **Frontend server:** tự build (React/Vue) hay tool sẵn dashboard (PocketBase)? — *Khuyến nghị: FastAPI
   + SQLite cho đồng bộ Python; tái dùng component của `customer_ui` cho Kiosk.*
3. **Nút bàn (phần cứng):** loại nào gọi `/tables/{id}/call`? — vd **ESP32 + WiFi** (gửi HTTP), nút USB,
   hay nút không dây qua gateway. *Chốt loại phần cứng + cách map nút → `table_id`.*
4. **Cổng thanh toán:** VietQR / MoMo / ZaloPay — chọn nhà cung cấp có sandbox tốt cho demo.
