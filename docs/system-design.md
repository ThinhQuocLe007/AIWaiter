# Kiến trúc hệ thống — AI Waiter (nhà hàng nhiều robot)

> Tài liệu này mô tả **toàn bộ kiến trúc** hệ thống nhà hàng robot phục vụ: các thành phần,
> các web app, cách chúng giao tiếp, cách giao task cho hệ thống và cho robot, mô hình dữ liệu,
> hiện trạng đã code, và **cách demo trên 3 laptop**. Dùng để cả nhóm đọc và bám theo khi triển khai.
>
> 📄 **Hai file dễ nhầm — đọc cái nào?**
> - **`system-design.md` (file này)** = *bản thiết kế sản phẩm/định hướng*: luồng nghiệp vụ,
>   mô hình triển khai (3 laptop, Netbird), lý do thiết kế, lộ trình. Đọc để hiểu **vì sao** hệ làm vậy.
> - **[`code-architecture.md`](code-architecture.md)** = *bản mô tả khớp với CODE hiện tại*:
>   backend + agent + data store đã code (đã có sơ đồ Mermaid, bảng endpoint, file map). Đọc để biết
>   **code đang chạy ra sao**. Khi 2 file lệch nhau, `code-architecture.md` là **nguồn đúng**.
>
> Phiên bản: thiết kế gốc nay đã được **cập nhật khớp code (2026-06-26, sau khi gộp ledger
> `orchestrator.db` + bỏ `restaurant.db`)**. UI khách + Kiosk + Panel + backend FastAPI **đã code**.
> **Thay đổi lớn (2026-06):** LLM/RAG/agent **tách khỏi Jetson** → dồn lên **1 server trung tâm**.
> Jetson trên robot chỉ còn STT/VAD/TTS + ROS 2/Nav2; **UI là trình duyệt kiosk trỏ về server**
> (`chromium --kiosk http://<SERVER_IP>:8000/`, **không Node, không build trên Jetson**). Hỗ trợ
> **server đặt từ xa** (offsite để cooling) qua **Netbird** (overlay mesh VPN).
>
> **Pipeline web (chốt 2026-06):** **SERVER build & serve CẢ 3 web** (customer_ui, kiosk, panel) cùng 1
> origin `:8000`. Mọi client (Jetson robot, kiosk tablet, panel bếp, laptop khách) **chỉ mở URL** tới
> server — không máy nào build/serve web cục bộ. *(xem §3, §4, §10)*

---

## 0. TL;DR (đọc nhanh)

- **Toàn bộ "não" nằm trên 1 server** (không còn LLM trên robot):
  - **Não hội thoại** = LLM + RAG menu + agent (LangGraph sinh lệnh hành động) — chạy *trên server*,
    **dùng chung cho mọi robot**.
  - **Não điều phối** = Dispatcher giữ trạng thái bàn/đơn/tiền và chia việc cho robot — cùng server đó.
- **Jetson trên robot = "thân xác"** (không suy nghĩ): STT + VAD + TTS (xử lý audio *cục bộ*) và ROS 2
  Humble + Nav2 (di chuyển). Màn hình đặt món (`customer_ui`) chỉ là **trình duyệt kiosk trỏ về server**
  (server serve, Jetson **không build, không Node**). Nghe-nói cục bộ, *suy nghĩ* gửi lên server.
- **1 server làm tất cả:** LLM + Dispatcher + **backend FastAPI duy nhất** phục vụ **cả 3 web** (UI robot,
  Kiosk cổng, Bảng điều khiển/quản lý) + **SQLite**. Chạy backend trên server = cả hệ online.
- **Stack chốt:** `FastAPI + SQLite` (server) · `WebSocket + REST` (giao tiếp) · `ROS 2 Humble + Nav2`
  (di chuyển robot) · `Netbird` (overlay mạng khi server đặt từ xa). **KHÔNG dùng MQTT**.
- **Mạng:** chạy tốt trên **LAN** khi server ở quán; nếu server đặt *chỗ khác* (cooling) thì các thiết bị
  (jetson, kiosk, panel, nút bàn) **join chung 1 Netbird** → coi như cùng LAN, **code/giao thức không đổi**.
- **Robot làm đúng 3 việc:** `ĐẾN_BÀN` (gọi món lần đầu) · `GIAO_MÓN` · `GỌI` (khách bấm nút → robot
  tới hỏi: *đặt thêm* hay *thanh toán*).
- **Mất kết nối server = robot ngừng hội thoại** (chờ/về dock). **Không** giữ LLM dự phòng trên Jetson.
- **Demo:** 3 laptop — (1) server (LLM + backend) + Kiosk, (2) Gazebo xem TurtleBot4 chạy + UI robot +
  STT/TTS, (3) Bảng điều khiển (bếp + giám sát).

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
┌──────────── SERVER TRUNG TÂM (1 máy — ở quán HOẶC offsite + Netbird) ─────────────────────────┐
│                                                                                               │
│  ┌─ NÃO HỘI THOẠI ───────────────────┐   ┌─ NÃO ĐIỀU PHỐI (Orchestrator, FastAPI) ─────────┐ │
│  │  LLM (dùng chung mọi robot)        │   │  REST API + WebSocket hub                       │ │
│  │  RAG menu + embedding              │   │  ┌─ Table Manager   (trạng thái từng bàn)       │ │
│  │  Agent (LangGraph): hiểu ý khách   │   │  ┌─ Order Service   (đơn hàng + lịch sử)        │ │
│  │  → text trả lời + SINH LỆNH        │   │  ┌─ Dispatcher      (sự kiện → task → chọn robot)│ │
│  │    (mở /menu, thêm món, /payment,  │   │  ┌─ Fleet Manager   (robot: trạng thái/pin/vị trí)│
│  │     navigate…)                     │   │  └─ Payment Service (QR, webhook, chốt đã trả)   │ │
│  └────────────────────────────────────┘   └──────────────────────────────────────────────────┘│
│                          SQLite (bàn, đơn, lịch sử, thanh toán)  ·  serve 3 web frontend       │
└───▲────────────▲──────────────────▲───────────────────▲──────────────────▲───────────────────┘
    │ WS         │ WS/REST           │ WS/REST            │ HTTP              │ HTTP webhook
    │ (voice+task)│                  │                    │                   │
┌───┴───┐  ┌─────┴─────┐   ┌─────────┴─────────┐   ┌──────┴──────┐   ┌────────┴─────────┐
│ ROBOT │  │ Kiosk web │   │ Bảng điều khiển   │   │ Nút bàn     │   │ Cổng thanh toán  │
│ 1..N  │  │ (cổng)    │   │ (bếp + giám sát   │   │ (phần cứng) │   │ (VietQR/MoMo/    │
│ (Jetson)│ │           │   │  + quản lý)       │   │ 1 nút/bàn   │   │  ZaloPay)        │
└───┬───┘  └───────────┘   └───────────────────┘   └─────────────┘   └──────────────────┘
    │ localhost WebSocket  (robot-agent ↔ Body — bên trong mỗi robot, không đổi)
┌───┴──────────────────────────────────────────────────┐
│ JETSON (trên mỗi robot) — "THÂN XÁC", KHÔNG có LLM    │
│  ┌─ ROBOT-AGENT (env uv, Python 3.10) — thin client   │
│  │   VAD + STT (nghe) · TTS (nói) — xử lý audio cục bộ │
│  │   ws_client → server: gửi text STT, nhận text→TTS   │
│  │                       + nhận lệnh navigate → Body   │
│  │   ws_server → Body (localhost)                      │
│  │   + chromium --kiosk → http://<SERVER>:8000/        │
│  │     (server serve customer_ui; Jetson KHÔNG build)  │
│  └─ BODY  (ROS 2 Humble + Nav2)                        │
│      ai_hw_bridge: nhận navigate → đặt Nav2 goal        │
│      → robot di chuyển; báo arrived/pose               │
└───────────────────────────────────────────────────────┘
        ↑ robot né nhau bằng lidar/costmap của Nav2 (coi nhau là chướng ngại động)
```

### Vì sao thiết kế như vậy
- **Tách LLM lên server (mới):** Jetson Orin 8GB không phải gánh LLM nữa → giải phóng RAM cho STT/TTS +
  ROS 2/Nav2; 1 LLM (mạnh hơn) trên server **dùng chung mọi robot**, dễ nâng cấp/đổi model 1 chỗ. Audio
  vẫn xử lý **cục bộ** (VAD/STT/TTS) nên không phải stream tiếng qua mạng — chỉ gửi *text* lên server.
- **Robot-agent ↔ Body = WebSocket localhost:** giữ nguyên contract cũ (2 env Python tách biệt cùng máy:
  agent cần `torch/whisper` env uv, Body cần `rclpy` env ROS) → ống nội bộ không đổi.
- **Robot ↔ Server = WebSocket:** server *đẩy task + text trả lời + lệnh navigate xuống*, robot *gửi text
  STT + trạng thái lên* → kênh 2 chiều luôn mở. Trên LAN hoặc qua overlay Netbird đều như nhau.
- **Web clients ↔ Server = REST + WebSocket:** REST cho thao tác (tạo đơn, tick món xong), WebSocket cho
  realtime (Bảng điều khiển thấy đơn mới + robot di chuyển; customer_ui nhận lệnh chuyển màn từ server).
- **Robot ↔ Robot = Nav2/DDS:** không cần broker; Nav2 đã coi robot khác là chướng ngại động.
- **Không MQTT:** không có thiết bị ngoài-ROS cần pub/sub; thêm broker là thừa việc vận hành.
- **Mất server = mất hội thoại:** vì LLM chỉ ở server, khi rớt mạng robot không nói chuyện được → robot
  *timeout + về dock* (mục 12). Đây là đánh đổi đã chấp nhận để Jetson nhẹ.

### 2.1 Mạng — LAN tại quán hay server đặt từ xa (Netbird)

Server là **nguồn chân lý duy nhất**; mọi thiết bị (jetson robot, kiosk, panel, nút bàn) chỉ là client
trỏ về `SERVER_IP:8000`. Có 2 cách bố trí, **code/giao thức y hệt nhau** — chỉ khác cái IP đó là gì:

```
(A) Server Ở QUÁN — LAN thường              (B) Server ĐẶT XA (cooling) — Netbird overlay
┌──────── WiFi/LAN quán 192.168.1.0/24 ───┐   ┌──── Netbird mesh 100.x (VPN overlay) ──────┐
│ server 192.168.1.10                     │   │ server 100.0.0.1   (đặt ở phòng máy/cloud)  │
│ robot  192.168.1.11                     │   │ robot  100.0.0.2   (ở quán)                 │
│ kiosk  192.168.1.12                     │   │ kiosk  100.0.0.3   (ở quán)                 │
│ panel  192.168.1.13                     │   │ panel  100.0.0.4   (ở quán)                 │
└─────────────────────────────────────────┘   └─────────────────────────────────────────────┘
   client trỏ ws://192.168.1.10:8000           client trỏ ws://100.0.0.1:8000
```

- **Netbird** là overlay mesh VPN (WireGuard): cài agent trên *mỗi* thiết bị → tất cả vào **1 mạng ảo**,
  có IP `100.x` cố định, **gói tin mã hoá đầu-cuối**, đi xuyên NAT/khác mạng vật lý mà *không cần mở port
  công khai*. Server đặt ở đâu (phòng máy có điều hoà, hay cloud) cũng coi như "cùng LAN" với robot.
- **Đổi LAN → Netbird chỉ là đổi 1 biến `SERVER_HOST`** (env/config) ở mỗi client. WebSocket/REST/giao
  thức JSON **không đổi**. Nav2/DDS giữa robot vẫn chạy trong LAN vật lý của quán (không qua Netbird).
- **Lưu ý độ trễ:** vì LLM ở server, voice round-trip = (STT cục bộ) + RTT lên server + (LLM) + RTT về +
  (TTS cục bộ). Server **offsite qua internet** sẽ thêm vài chục–trăm ms RTT → ưu tiên đặt server *trong
  quán* hoặc *cùng vùng/cùng ISP* để giữ hội thoại mượt. Audio không stream qua mạng nên băng thông nhẹ.
- **Bảo mật:** Netbird thay cho việc mở port server ra internet — đỡ lộ FastAPI/LLM ra ngoài. Cổng thanh
  toán (webhook) vẫn cần đường HTTPS công khai riêng (mục 7.3), không đi qua Netbird.

---

## 3. Cần bao nhiêu web? (trả lời trực tiếp)

**Chỉ 2 web + 1 UI màn hình robot (+ nút bấm phần cứng ở bàn). Tất cả do CÙNG 1 backend (FastAPI)
phục vụ** — không phải nhiều server, chỉ là vài "ứng dụng frontend" cùng gọi 1 API.

| # | Giao diện | Chạy ở đâu | Ai dùng | Làm gì | Trạng thái |
|---|---|---|---|---|---|
| 1 | **Kiosk cổng** | Trình duyệt tablet ở cổng → `…:8000/kiosk` | Khách | Xem bàn trống → chọn bàn + số người | 🟢 **đã code** (`src/frontends/kiosk`) |
| 2 | **Bảng điều khiển** (bếp + giám sát + **quản lý**, **gộp 1**) | Trình duyệt laptop quầy/bếp → `…:8000/panel` | Nhân viên + quản lý | Đơn mới theo bàn, tick "món xong"; vị trí robot / pin / hàng đợi task; **+ quản lý nhà hàng** (menu, bàn, doanh thu, lịch sử đơn) | 🟢 **đã code** (`src/frontends/panel`) |
| 3 | **UI màn hình robot** (`customer_ui`) | Trình duyệt kiosk màn LCD robot → `…:8000/` | Khách | Menu khi đặt món · bill + thanh toán · trợ lý giọng nói | 🟢 **đã code** (`src/frontends/customer_ui`) |
| — | **Nút bàn** | Gắn trên mỗi bàn | Khách | **Phần cứng, không phải web** — bấm 1 nút → server tạo task gọi robot | ⬜ chưa code |

> **Bảng điều khiển gộp bếp + giám sát + quản lý:** 1 web duy nhất cho nhân viên/quản lý — vừa là Kitchen
> Display (đơn mới theo bàn, tick món xong), vừa là bảng giám sát (sơ đồ vị trí robot, pin, trạng thái
> bàn, hàng đợi task), vừa là **panel quản lý** (sửa menu/giá, cấu hình bàn, xem doanh thu/lịch sử đơn).
> Gộp lại cho dễ quản lý: nhân viên chỉ cần nhìn 1 màn hình. (Có thể tách tab "Quản lý" cho role admin.)
>
> Cả 3 web là tĩnh, **server build & serve cùng 1 origin `:8000`** — mọi client chỉ mở URL (`vite dev` chỉ
> dùng khi DEV frontend). UI robot (#3) chạy full-screen (chromium `--kiosk`) trên màn LCD robot, **không
> build cục bộ**; có thể dùng lại component menu/giỏ hàng của `customer_ui` cho Kiosk #1.

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
- `stores/voice.ts`: thay mock bằng **STT + TTS cục bộ trên Jetson** (robot-agent) + **LLM ở server**.
  (Audio nghe/nói xử lý ngay trên Jetson; chỉ *text* đi lên server cho LLM hiểu ý + sinh đáp.)
- `PaymentScreen`: nối **bill thật** từ server + **QR thanh toán** + chờ xác nhận webhook.
- Nhận lệnh từ **Server** (qua WS) để **tự chuyển màn** (vd: tới bàn → mở `/menu`; gọi tính tiền →
  `/payment`). Lệnh do **agent trên server** sinh ra, không còn từ Brain cục bộ.

---

## 4. Phân bổ code — Server (não) vs Jetson robot (thân xác)

Repo hiện tại (`ai_waiter_core`) đang là **1 khối Brain** chạy trên Jetson. Theo thiết kế mới, tách
đôi: module *suy nghĩ* dời **lên server**, module *audio + di chuyển* ở lại **Jetson**.

```
SERVER  (env uv, Python 3.10 — "NÃO": LLM + điều phối + backend)
├── ai_waiter_core/ai_waiter_core/
│   ├── agent/         (LangGraph agent: trò chuyện, gọi RAG, SINH LỆNH HÀNH ĐỘNG)   ← LÊN SERVER
│   ├── services/      (order_worker, payment_worker, RAG menu + embedding)          ← LÊN SERVER
│   ├── schemas/       (pydantic — dùng chung cho mọi WS message)                    ← shared
│   └── interfaces/
│       ├── ws_server.py   ← hub WS của server: nói chuyện với mọi robot + web client
│       └── (REST FastAPI: /menu, /orders, /seatings, /payments… — mục 9)
│   + Dispatcher / Table Manager / Fleet Manager / Payment Service / SQLite
└── src/frontends/                       ← server BUILD & SERVE cả 3 web (kiosk, panel, customer_ui)

JETSON ROBOT  (mỗi robot)
├── robot-agent/                         (env uv, Python 3.10 — thin client, KHÔNG LLM)
│   ├── perception/    (VAD + STT)       ← Ở LẠI JETSON (nghe, cục bộ)
│   ├── output/        (TTS)             ← Ở LẠI JETSON (nói, cục bộ)
│   └── ws_client.py   → server (gửi text STT, nhận text→TTS + lệnh navigate)
│       + ws bridge → Body (localhost, contract cũ không đổi)
├── (KHÔNG có web)                       ← chromium --kiosk → http://<SERVER>:8000/ (server serve, không build)
└── robot_ws/                            (env colcon, ROS 2 Humble — BODY)
    ├── src/sim/turtlebot4_ignition_bringup/   (Gazebo: turtlebot4_ignition.launch.py, world restaurant.sdf)
    ├── src/common/turtlebot4_navigation/      (Nav2 — điều hướng tới waypoint)
    └── src/real/ai_hw_bridge/                 (CHỖ cho node bridge: rclpy + WS client → robot-agent)
                                                 hiện COLCON_IGNORE (trống) — CẦN VIẾT
```

- **Server (não)** giữ phần "suy nghĩ": nhận *text* từ STT của robot → hiểu/đáp (LLM + RAG menu) → trả
  về *text* cho robot đọc (TTS) + **sinh lệnh hành động** (chuyển màn UI, navigate). Đồng thời chạy
  Dispatcher/Order/Payment và serve 3 web. **1 LLM dùng chung mọi robot.**
- **Jetson robot-agent** giữ "tai + miệng": VAD bắt khi khách nói → STT ra text (cục bộ) → gửi server;
  nhận text trả lời → TTS đọc (cục bộ). **Không** chứa LLM/RAG/embedding → Jetson nhẹ hẳn.
- **Body** giữ "chân" robot: nhận lệnh `navigate` (server → robot-agent → Body) → đặt goal cho **Nav2**
  → robot di chuyển → báo `arrived`/`nav_failed`.
- **Tái cấu trúc cần làm:** `agent/` + `services/` (RAG, worker) **chuyển sang chạy ở server**; trên
  Jetson chỉ còn `perception/` + `output/` + ws_client gói thành **robot-agent**. `schemas/` giữ chung
  (cùng pydantic models cho WS) — đóng gói thành package dùng chung cả 2 phía.
- **Đã có trong repo:** các package **TurtleBot4 gốc** (sim `turtlebot4_ignition_bringup`, điều hướng
  `turtlebot4_navigation`) để xem **TurtleBot4 di chuyển** (xem mục 10). **Node bridge chưa viết** —
  chỗ trống `ai_hw_bridge` (đang `COLCON_IGNORE`). Toạ độ **dock + bàn 1–6** đã có sẵn ở
  `robot_ws/docs/restaurant_positions.md` → đây là nguồn waypoint cho Body.

---

## 5. Giao tiếp & giao thức (tất cả message là JSON)

| Cặp giao tiếp | Cơ chế | Lý do |
|---|---|---|
| Web clients ↔ Server | **REST** (thao tác) + **WebSocket** (realtime push) | Web cần cả hỏi-đáp lẫn nhận đẩy |
| Robot-agent ↔ Server | **WebSocket** (LAN / Netbird) | Server đẩy task + **text trả lời (TTS)** + navigate; robot gửi **text STT** + trạng thái |
| Robot-agent ↔ Body (trong robot) | **WebSocket** (localhost) | 2 env Python tách biệt cùng máy |
| Robot ↔ Robot | **ROS 2 / Nav2 (DDS)** | Né va chạm tự động; không cần broker |
| Server ↔ Cổng thanh toán | **HTTP webhook** | Cổng báo "đã nhận tiền" về server |

> **LLM ở server → thêm "kênh hội thoại":** ngoài task/ack/heartbeat như cũ, robot-agent còn gửi *text
> đã STT* lên server và nhận lại *text để TTS đọc*. **Chỉ truyền text, không truyền audio** → nhẹ mạng,
> chạy được cả qua Netbird. Khi server đứt kết nối, robot-agent ngừng hội thoại và để Body về dock.

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

**Hội thoại — Robot-agent → Server (text đã STT cục bộ):**
```jsonc
{ "type": "stt_text", "robot_id": "r1", "table_id": 3, "text": "cho tôi 2 phở bò" }
```
**Hội thoại — Server (LLM/agent) → Robot-agent:**
```jsonc
{ "type": "say",      "robot_id": "r1", "text": "Dạ, 2 phở bò ạ. Anh dùng thêm gì không?" }  // → TTS đọc
{ "type": "ui",       "robot_id": "r1", "action": "open_menu" }     // → đẩy customer_ui sang /menu
{ "type": "ui",       "robot_id": "r1", "action": "open_payment" } // → /payment (bill + QR)
{ "type": "navigate", "robot_id": "r1", "table_id": 3 }            // → relay xuống Body
{ "type": "return_dock", "robot_id": "r1" }
```
> Lệnh `ui` server có thể đẩy thẳng tới **customer_ui** (WS riêng của UI) hoặc qua robot-agent — chọn 1
> đường, miễn nhất quán. `navigate`/`return_dock` luôn đi qua robot-agent để relay xuống Body (dưới).

**Robot-agent → Body (localhost, trong robot — contract cũ không đổi):**
```jsonc
{ "type": "navigate", "table_id": 3 }     // tới waypoint bàn 3
{ "type": "return_dock" }                 // về dock
```
**Body → Robot-agent:**
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

### Máy trạng thái — bàn / phiên / đơn (Server giữ; khớp code)

> **Cập nhật (gộp ledger):** code **không** dùng máy trạng thái bàn 7 trạng thái như bản thiết kế cũ.
> Thực tế tách làm **3 lớp**, mỗi lớp có vòng đời riêng (xem [`code-architecture.md`](code-architecture.md) §2–§3):

**1. BÀN (`tables.status`) — chỉ 3 trạng thái:**
```
TRỐNG (TRONG) ─(kiosk POST /seatings)→ ĐANG_PHỤC_VỤ (DANG_PHUC_VU) ─(thanh toán xong)→ ĐÃ_THANH_TOÁN (DA_THANH_TOAN)
   ▲                                                                                          │
   └──────────────────────── (nhân viên dọn, PATCH /tables/{id} status=TRONG) ────────────────┘
```

**2. PHIÊN (`sessions.status`) — 1 phiên = trọn 1 lượt khách (ngồi → nhiều đơn → 1 hoá đơn gộp → rời):**
```
(POST /seatings mở phiên) ACTIVE ──(thanh toán xác nhận)──► CLOSED
```
> Phiên là **đơn vị gom hoá đơn (gộp bill)** và cũng là **`thread_id` của bộ nhớ hội thoại** (xem §13).

**3. ĐƠN (`orders.status`) — tiến độ bếp, gắn vào phiên, KHÔNG nằm trên bàn:**
```
CHỜ_BẾP (CHO_BEP) ──► ĐANG_LÀM (DANG_LAM) ──► XONG (XONG → enqueue task deliver)
```
Khách bấm **nút bàn** lúc đang ăn → task `call` (không đổi trạng thái bàn): robot tới hỏi *đặt thêm*
(tạo đơn mới trong CÙNG phiên) hay *thanh toán* (mở payment cho phiên).

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
> bằng giọng nói → STT cục bộ gửi text lên **server, LLM/agent hiểu ý định**).

---

## 8. Mô hình dữ liệu (khớp code — `orchestrator.db`)

> **Cập nhật quan trọng:** DB chính nay tên **`orchestrator.db`** (đã bỏ `restaurant.db`), do **backend
> FastAPI là writer DUY NHẤT** ([src/backend/app/db.py](../src/backend/app/db.py), SQLite thuần, không ORM).
> Thêm bảng **`sessions`**; **`payments` gắn theo `session_id`** (gộp bill mỗi lượt khách), **không còn
> theo `order_id`**. Sơ đồ ER đầy đủ: [`code-architecture.md`](code-architecture.md) §2.

```sql
tables(      id, name, capacity, status, current_order_id, party_size, seated_at ) -- status: TRONG/DANG_PHUC_VU/DA_THANH_TOAN
sessions(    id, table_id, status, started_at, ended_at )       -- 1 lượt khách; status ACTIVE/CLOSED  ← MỚI
dishes(      id, name, price, category, available )             -- menu, nguồn cho RAG + menu.json
orders(      id, session_id, table_id, status, total, created_at ) -- session_id = chủ sở hữu (gộp bill); status CHO_BEP/DANG_LAM/XONG
order_items( id, order_id, dish_id, qty, note, price )
robots(      id, name, status, battery, x, y, current_task_id ) -- battery/x/y chỉ là SNAPSHOT; live ở RAM (fleet.py)
tasks(       id, kind, table_id, order_id, robot_id, status, created_at, updated_at ) -- kind: go_to_table/deliver/call
payments(    id, session_id, amount, status, qr_url, paid_at )  -- 1 payment GỘP / phiên; status PENDING/PAID  ← theo session_id
```
- **Vì sao SQLite:** quán nhỏ → ít ghi đồng thời; *1 file, không server DB*, backup = copy file, vẫn có
  transaction cho thanh toán. Đổi sang PostgreSQL sau chỉ là đổi connection.
- **3 kho dữ liệu theo bản chất (quyết định thiết kế):** (1) `orchestrator.db` — ledger nghiệp vụ bền vững;
  (2) `checkpoints.db` (LangGraph) — bộ nhớ hội thoại, key = session id (§13); (3) **RAM** (`fleet.py`) —
  telemetry robot (pose/pin) tần suất cao & tạm thời, để ngoài DB nên heartbeat không tranh lock ghi với đơn/tiền.

---

## 9. Danh sách API & sự kiện WebSocket (bản nháp)

**REST (web clients) — khớp code ([src/backend/app/routers/](../src/backend/app/routers/)):**
```
GET   /tables                      → danh sách bàn + trạng thái (kiosk, bảng điều khiển)
GET   /tables/{id}                 → 1 bàn
POST  /seatings        {table_id, party_size}   → nhận bàn → MỞ phiên ACTIVE (kiosk)
GET   /tables/{id}/session         → phiên ACTIVE + tổng tiền GỘP (agent resolve thread; panel hiện bill)
PATCH /tables/{id}     {status}    → đổi trạng thái bàn (vd dọn → TRONG)
GET   /menu                        → danh sách món (UI robot: stores/menu.ts)
POST  /orders          {table_id, items[]}      → tạo đơn DƯỚI phiên của bàn (total tính ở server)
GET   /orders                      → danh sách đơn (bảng điều khiển)
PATCH /orders/{id}     {status}    → bếp đổi trạng thái; XONG → enqueue task deliver
POST  /payments        {table_id}  → mở/refresh payment GỘP của phiên (PENDING + qr_url)
POST  /payments/verify {table_id}  → chốt theo bàn (agent): PAID + đóng phiên + bàn DA_THANH_TOAN
POST  /payments/{id}/verify        → chốt theo id (tablet)
POST  /tables/{id}/call            → khách bấm NÚT bàn → robot tới hỏi (đặt thêm / thanh toán)
GET   /tasks · GET /robots · GET /layout · GET /map/image.png · POST /admin/reset
```
> `/tables/{id}/call` là endpoint mà **nút phần cứng** gọi (qua firmware/ESP32 hoặc cầu nối). Generic:
> server tạo task `call`, không phân biệt trước là đặt thêm hay thanh toán — khách quyết khi robot tới.
> *Chưa code:* webhook cổng thanh toán thật (`/webhooks/payment`) — hiện `verify` chốt thủ công/giả lập;
> QR là VietQR dựng từ `amount` (`payments._vietqr_url`).

**WebSocket (1 endpoint `/ws`, phân luồng theo `role`):**
```
role=robot      : server⇄robot-agent (task, ack, heartbeat + HỘI THOẠI: stt_text↑, say/ui/navigate↓ — mục 5)
role=robot_ui   : server→customer_ui  (lệnh chuyển màn: open_menu / open_payment …)
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

Cả 3 laptop nối **cùng 1 WiFi/LAN**; Server có IP cố định, ví dụ `192.168.1.10`. (Nếu muốn thử kịch bản
**server đặt xa**: cài Netbird trên cả 3, dùng IP `100.x` thay cho `192.168.1.x` — xem 10.1.)

```
        WiFi / LAN của quán  (192.168.1.0/24)
   ┌───────────────┬─────────────────────────┬────────────────────┐
   │               │                         │                    │
┌──▼───────────┐ ┌─▼─────────────────────┐ ┌─▼──────────────────┐
│ LAPTOP 1     │ │ LAPTOP 2              │ │ LAPTOP 3           │
│ SERVER+KIOSK │ │ ROBOT (mô phỏng)      │ │ BẢNG ĐIỀU KHIỂN    │
│ +LLM/Não     │ │ 192.168.1.11          │ │ (chỉ trình duyệt)  │
│ 192.168.1.10 │ │                       │ │                    │
├──────────────┤ ├───────────────────────┤ ├────────────────────┤
│ FastAPI +    │ │ ROS 2 Humble + Nav2    │ │ Mở trình duyệt tới: │
│ SQLite + LLM │ │ Gazebo: chạy TurtleBot4│ │ http://192.168.1.10 │
│ + Dispatcher │ │  → THẤY ROBOT DI CHUYỂN│ │   /panel            │
│ Web (tab):   │ │ node bridge            │ │                    │
│ /kiosk       │ │  (WS client → 1.10)    │ │ 1 web gộp bếp+giám: │
│ (nút bàn giả │ │ robot-agent (STT/TTS)  │ │  - đơn mới theo bàn │
│  lập = curl  │ │ chromium --kiosk →     │ │  - tick "món xong"  │
│  /tables/3/  │ │  http://1.10:8000/     │ │  - vị trí robot/pin │
│  call)       │ │  (server serve UI)     │ │  - hàng đợi task    │
└──────┬───────┘ └───────────┬─────────────┘ └─────────┬──────────┘
       │  WebSocket/REST      │ WS (task/ack + voice)    │ WebSocket
       └─────────────────────►│◄─────────────────────────┘
                       (tất cả trỏ về 192.168.1.10:8000)
```

### Laptop 1 — Server + LLM + serve cả 3 web (sân khấu chính)
- Chạy FastAPI (cổng `8000`) + SQLite (`orchestrator.db`) + **LLM/agent + RAG menu** + Dispatcher,
  đồng thời **build & serve cả 3 web** (`make build`) — Laptop 2/3 chỉ mở URL, không build gì.
- Mở tab **Kiosk** (`…:8000/kiosk`). **Nút bàn** chưa có phần cứng → giả lập bằng `curl -X POST
  http://192.168.1.10:8000/tables/3/call` (hoặc 1 nút bấm nhỏ trên trang dev).
- (Demo nhẹ: nếu laptop yếu, đặt LLM ở 1 model nhỏ/endpoint riêng — vẫn là "trên server", không trên robot.)

### Laptop 2 — Robot mô phỏng ("thấy robot di chuyển")
- `ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py world:=restaurant` → Gazebo +
  RViz, **TurtleBot4 chạy bằng Nav2** (`turtlebot4_navigation`) giữa các toạ độ waypoint.
- **Node bridge** (cần viết, vd trong `ai_hw_bridge`): **WS client** tới
  `ws://192.168.1.10:8000/ws?role=robot`, nhận task/navigate → tra toạ độ bàn (`restaurant_positions.md`)
  → đặt Nav2 goal → robot chạy trong Gazebo → báo `arrived`/`task_done`.
- **Màn hình robot** = `chromium --kiosk http://192.168.1.10:8000/` (server serve `customer_ui`, **Laptop 2
  không build/Node**); theo lệnh server sẽ chuyển `/menu`, `/payment`.
- **2 chế độ:** *mock-voice* (bỏ mic, bridge tự dịch task→goal — đủ demo luồng + di chuyển) hoặc
  *full-voice* (robot-agent STT/TTS cục bộ + **LLM ở Laptop 1** để demo đặt món bằng giọng nói).
- **Multi-robot:** mở 2 instance, đổi `robot_id`/namespace (`r1`, `r2`) → bảng điều khiển hiện 2 robot,
  Dispatcher tự chia task. (Cả 2 robot **dùng chung 1 LLM** ở Laptop 1.)

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

### 10.1 Biến thể demo — server đặt xa (Netbird)
Khi muốn chứng minh "server không cần ở quán":
1. Cài Netbird trên cả 3 laptop (hoặc server + jetson thật), join cùng 1 network → mỗi máy có IP `100.x`.
2. Đặt **Laptop 1 (server)** ở mạng khác (vd nhà/cloud), Laptop 2/3 ở "quán".
3. Đổi **1 biến** `SERVER_HOST=100.0.0.1` ở các client (robot-agent, customer_ui, panel). **Không sửa code.**
4. Chạy lại kịch bản trên — mọi thứ y hệt, chỉ khác đường truyền đi qua overlay Netbird.
> Kiểm tra độ trễ voice: nếu RTT lên server cao, hội thoại sẽ "khựng" — đó là lý do nên đặt server *gần*
> (cùng vùng/ISP). Nav2/DDS giữa robot vẫn ở LAN quán, không phụ thuộc Netbird.

---

## 11. Lộ trình triển khai (làm theo mốc)

- **Mốc A — 1 robot, không server:** robot-agent↔Body qua localhost WS; robot tới bàn + nhận lệnh đặt/giao
  với 1 con. Chứng minh đường ống robot-agent/Body chạy. (Giai đoạn này có thể tạm mock "não" để test đường ống.)
- **Mốc B — dựng Server trung tâm (não + backend):** 🟢 **phần lớn ĐÃ XONG** — FastAPI + SQLite
  (`orchestrator.db`), agent + tools gọi REST, bộ nhớ hội thoại theo phiên (§13); **3 web đã code**
  (customer_ui, kiosk, panel). *Còn lại:* nối STT/TTS thật trên Jetson thay voice mock.
- **Mốc C — Dispatcher + nút bàn + thanh toán:** 🟡 **đang chạy** — dispatcher chọn robot + watchdog,
  endpoint `/tables/{id}/call`, `/payments` + `/payments/verify` (QR VietQR). *Còn lại:* webhook cổng
  thanh toán thật (hiện verify thủ công/giả lập).
- **Mốc D — multi-robot + remote:** thêm robot thứ 2 trong sim (dùng chung 1 LLM); **Netbird cho server
  offsite**; thiết kế **lane 1 chiều** giảm kẹt; cân nhắc **Open-RMF**/**Zenoh** nếu đông robot hoặc WiFi yếu.

---

## 12. Rủi ro & quyết định cần chốt

**Rủi ro lớn nhất — KHÔNG chỉ là "nối dây":**
Agent hiện *chỉ trả về text*, **chưa sinh lệnh điều khiển robot** (đi bàn nào, giao món). Phần việc thật
là **thêm logic để agent phát lệnh hành động** + map lệnh → task → Nav2 goal.

**Các rủi ro khác:**
- **Giao thông nhiều robot lane hẹp:** Nav2 né va chạm nhưng dễ *kẹt đối đầu* → thiết kế **lane 1 chiều**;
  đông thì Open-RMF.
- **Mất WiFi/Netbird → mất não:** vì LLM ở server, robot **mất kết nối là mất hội thoại** (đã chấp nhận,
  không fallback). Robot cần *timeout + tự về dock*; server *re-dispatch* task nếu robot rớt; heartbeat
  phát hiện robot "chết". Server offsite làm rủi ro này lớn hơn LAN → cân nhắc đường mạng dự phòng.
- **Độ trễ voice qua mạng:** LLM ở server thêm RTT vào vòng nghe→nói; server càng xa càng "khựng" → ưu
  tiên đặt server gần (mục 2.1).
- **Thanh toán:** qua transaction + webhook; server là nguồn chân lý, robot chỉ hiển thị.
- **Voice mock → thật:** `stores/voice.ts` mới là timer giả; nối STT/TTS cục bộ + LLM server còn nhiều việc.

**Đã chốt (2026-06):**
1. **LLM chạy đâu? → SERVER.** LLM + RAG + agent dồn lên 1 server, dùng chung mọi robot. Jetson chỉ giữ
   STT/VAD/TTS + customer_ui + ROS2/Nav2. **Không** giữ LLM dự phòng trên Jetson. *Đánh đổi:* mất server
   thì robot ngừng hội thoại — chấp nhận để Jetson nhẹ + dễ nâng cấp model 1 chỗ.
2. **Mạng remote → Netbird.** Server có thể đặt offsite (cooling); các thiết bị join chung Netbird overlay,
   đổi 1 biến `SERVER_HOST`, code không đổi (mục 2.1).

**Cần chốt trước khi code:**
1. **Frontend server:** tự build (React/Vue) hay tool sẵn dashboard (PocketBase)? — *Khuyến nghị: FastAPI
   + SQLite cho đồng bộ Python; tái dùng component của `customer_ui` cho Kiosk.*
2. **Nút bàn (phần cứng):** loại nào gọi `/tables/{id}/call`? — vd **ESP32 + WiFi** (gửi HTTP), nút USB,
   hay nút không dây qua gateway. *Chốt loại phần cứng + cách map nút → `table_id`.*
3. **Cổng thanh toán:** VietQR / MoMo / ZaloPay — chọn nhà cung cấp có sandbox tốt cho demo.
4. **Model LLM trên server:** chọn model nào (kích thước/tốc độ) + chạy bằng gì (Ollama/vLLM/llama.cpp) +
   cấu hình máy server (GPU?). *Vì giờ không bị giới hạn 8GB Jetson → có thể dùng model lớn hơn.*
5. **Đẩy lệnh `ui` cho customer_ui:** đi thẳng (role=robot_ui) hay qua robot-agent? *Chốt 1 đường.*

---

## 13. Bộ nhớ hội thoại = phiên (đã code — `thread_id = session_id`)

> Phần này **không có trong bản thiết kế gốc**, bổ sung cho khớp code. Chi tiết:
> [`code-architecture.md`](code-architecture.md) §4.

Agent **không bao giờ chạm DB** — tools (`confirm_order` / `request_payment` / `verify_payment`) gọi REST
qua [`orchestrator_client.py`](../ai_waiter_core/ai_waiter_core/services/orchestrator_client.py)
(`ORCHESTRATOR_URL`, chuẩn hoá `"T1" → 1`). Bộ nhớ hội thoại của LangGraph nằm ở **`checkpoints.db`**,
**key theo phiên** ([checkpointer.py](../ai_waiter_core/ai_waiter_core/agent/memory/checkpointer.py)):

- `thread_id = id phiên ACTIVE`; mỗi lượt chat agent resolve phiên hiện tại của bàn
  ([graph.py](../ai_waiter_core/ai_waiter_core/agent/graph.py)).
- **Trong 1 lượt khách** → cùng session id → nhớ ngữ cảnh xuyên suốt.
- **Sau thanh toán** (phiên CLOSED) → không còn phiên ACTIVE → khách kế tiếp mở **phiên mới** →
  **thread mới → ngữ cảnh sạch** (không lẫn giữa các lượt khách). Fallback `table-{id}-nosession`
  chỉ dùng trước khi có seating.
