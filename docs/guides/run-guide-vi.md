# Hướng Dẫn Cài & Chạy — AI Waiter (RoboDish)

> 📌 **ĐÂY LÀ FILE CHẠY CHÍNH. Không nhớ đọc file nào thì đọc file này.**
> - Chỉ muốn bật web + backend nhanh → **[TL;DR](#tldr-máy-đã-cài-node-22--uv)** ngay bên dưới.
> - Chạy **hệ thống HOÀN CHỈNH** (web + robot Gazebo + voice, mô hình PC-server + laptop-sim) →
>   **[Mục 8](#8-full-pipeline-web--robot-sim-gazebo--voice--chạy-thật-không-mock)**.
> - Cài theo từng máy (CUDA 12/13, Jetson, Netbird) → [setup-deploy.md](setup-deploy.md).
> - Chi tiết riêng luồng voice/LLM → [run-voice-vi.md](run-voice-vi.md) (đã gộp bản rút gọn ở Mục 8).

Hướng dẫn cho người **mới clone repo về**: cài đặt và bật được toàn bộ hệ thống.
Dự án gồm **3 web frontend** + **1 backend**:

| Thành phần | Thư mục | Cổng | Vai trò |
|---|---|---|---|
| **menu** (customer_ui) | `src/frontends/customer_ui` | 5173 | Màn hình đặt món cho khách |
| **kiosk** | `src/frontends/kiosk` | 5174 | Màn hình check-in / chọn bàn |
| **panel** | `src/frontends/panel` | 5175 | Màn hình bếp (kitchen panel) |
| **backend** | `src/backend` | 8000 | FastAPI: API + WebSocket |

> **Quan trọng:** mỗi web là một project npm **riêng**, có `node_modules` riêng.
> Phải cài cho **cả ba**, nếu không web nào thiếu sẽ báo `vite: not found`.

---

## TL;DR (máy đã cài Node 22 + uv)

```bash
git clone <repo-url> && cd AI_Waiter
# cài 3 web + backend. Backend cần extra theo máy (CUDA 12/13, server/voice):
make install UV_EXTRAS="--extra server --extra voice --extra cu12"   # laptop dev CUDA 12
make backend     # terminal 1: bật backend (cổng 8000)
make frontend    # terminal 2: bật cả 3 web (5173, 5174, 5175)
```

> Chọn `UV_EXTRAS` theo máy (xem [setup-deploy.md](setup-deploy.md)):
> server CUDA 13 → `--extra server --extra cu13`; laptop CUDA 12 → `--extra server --extra voice --extra cu12`; Jetson → `--extra voice`.

Mở trình duyệt: **http://localhost:5173** (menu) · **:5174** (kiosk) · **:5175** (panel).

---

## 1. Yêu cầu trước khi chạy

| Cần | Kiểm tra | Ghi chú |
|---|---|---|
| **Node.js 22** | `node -v` → `v22.x` | Phiên bản pin trong `.nvmrc` |
| **npm** | `npm -v` | Đi kèm Node |
| **uv** (Python) | `uv --version` | Quản lý môi trường backend |
| **make** | `make -v` | Có sẵn trên Linux/macOS |

- Máy **chưa có Node/uv** → xem [Mục 2a](#2a-máy-mới-chưa-có-nodeuv).
- Máy **đã có sẵn** → nhảy thẳng [Mục 2b](#2b-máy-đã-có-node--uv).

---

## 2. Cài đặt lần đầu (chỉ làm 1 lần)

### 2a. Máy mới (chưa có Node/uv)

Chỉ chạy được trên **Linux (Ubuntu)**. Từ thư mục gốc dự án:

```bash
make setup        # cài nvm + Node 22 + uv (và deps của customer_ui)
source ~/.bashrc  # nạp lại shell để dùng được node/npm/uv
make install      # ⚠️ BẮT BUỘC: cài nốt deps cho kiosk + panel + backend
```

> `make setup` **chỉ** cài deps cho `customer_ui`. Phải chạy thêm `make install`
> thì kiosk và panel mới có `node_modules` — nếu bỏ qua, `make frontend` sẽ chỉ
> lên 1 web, hai web kia báo `vite: not found`.

Trên **macOS/Windows**: cài Node 22 ([nvm](https://github.com/nvm-sh/nvm) hoặc
[nodejs.org](https://nodejs.org)) và [uv](https://docs.astral.sh/uv/) thủ công,
rồi làm tiếp [Mục 2b](#2b-máy-đã-có-node--uv).

### 2b. Máy đã có Node + uv

Từ thư mục gốc dự án:

```bash
make install UV_EXTRAS="--extra server --extra voice --extra cu12"
```

Lệnh này sẽ:
- `npm ci` trong `customer_ui`
- `npm install` trong `kiosk`
- `npm install` trong `panel`
- `uv sync --inexact <UV_EXTRAS>` cho backend (Python)

> ⚠️ **Backend BẮT BUỘC truyền `UV_EXTRAS`.** `fastapi`/`uvicorn` nằm trong
> `--extra server`, không có ở base — chạy `make install` trơn sẽ **không có
> uvicorn** và `make backend` sẽ lỗi `Failed to spawn: uvicorn`. Chọn extra theo máy:
>
> | Máy | UV_EXTRAS |
> |---|---|
> | Server (PC mới, CUDA 13) | `--extra server --extra cu13` |
> | Laptop dev (CUDA 12, cả brain + voice) | `--extra server --extra voice --extra cu12` |
> | Jetson robot (aarch64) | `--extra voice` |
>
> Chi tiết CUDA/role: [setup-deploy.md](setup-deploy.md). Makefile dùng
> `--inexact` nên chạy lại `make install` **không** xoá extra đã cài.

### Cấu hình `.env` (tuỳ chọn)

Chỉ `customer_ui` có file mẫu. Bản mặc định đã chạy được, sửa khi cần:

```bash
cp src/frontends/customer_ui/.env.example src/frontends/customer_ui/.env
```

---

## 3. Chạy hệ thống (chế độ dev)

Cần **2 terminal** (backend và frontend chạy song song):

```bash
# Terminal 1 — backend
make backend          # FastAPI tại http://localhost:8000  (--reload)

# Terminal 2 — cả 3 web cùng lúc
make frontend         # 5173 menu · 5174 kiosk · 5175 panel  (Ctrl-C dừng cả 3)
```

Frontend gọi backend qua proxy của Vite (`/api`, `/ws` → cổng 8000) nên **cùng
origin, không dính CORS**.

**Bật từng web riêng** (nếu chỉ cần 1 cái):

```bash
make menu     # chỉ customer_ui (5173)
make kiosk    # chỉ kiosk       (5174)
make panel    # chỉ panel       (5175)
```

**Dừng:** `Ctrl + C` trong terminal, hoặc dọn sạch mọi server:

```bash
make kill     # tắt hết cổng 8000, 5173, 5174, 5175
```

---

## 4. Sau khi `git pull` code mới

```bash
make install      # cài lại deps nếu package.json đổi
# hoặc gọn hơn:
make update       # = git pull + make install
```

---

## 5. Bản production (tuỳ chọn)

```bash
make build        # build customer_ui → src/frontends/customer_ui/dist/
make serve        # chạy thử bản build tại http://localhost:4173
```

---

## 6. Dữ liệu menu

Toàn bộ món ăn nằm ở **`assets/data/menu.json`** (thư mục gốc dự án). Sửa và lưu
file → web tự cập nhật, không cần khởi động lại. Mỗi món có dạng:

```json
{
  "name": "Ốc Hương",
  "price": "85000",
  "diet_type": "mặn",
  "category": "Ốc & Sò",
  "tags": "ốc, hải sản, best seller"
}
```

- `price`: **chuỗi**, đơn vị VND, không dấu chấm (vd `"85000"`).
- `tags`: ngăn cách bằng **dấu phẩy** trong 1 chuỗi.
- `category`: web tự gom thành các tab.

---

## 7. Lỗi thường gặp

| Triệu chứng | Nguyên nhân & cách xử lý |
|---|---|
| `vite: not found` (1–2 web không lên) | Web đó **chưa cài deps**. Chạy `make install` ở thư mục gốc. |
| `Failed to spawn: uvicorn` (khi `make backend`) | Backend cài thiếu extra `server`. Chạy `make install UV_EXTRAS="--extra server --extra voice --extra cu12"` (đúng CUDA của máy). |
| `node: command not found` | Chưa cài Node → `make setup` rồi `source ~/.bashrc`. |
| `Cannot read file '.../tsconfig.json'` | Thiếu `tsconfig.json` của web đó (xem `kiosk/tsconfig.json` làm mẫu). |
| `Port 5173 is in use` (hoặc 5174/5175/8000) | Server đang chạy ở terminal khác → `make kill`. |
| Web mở được nhưng **trắng / thiếu món** | `menu.json` sai cú pháp JSON (thiếu dấu phẩy/ngoặc). |
| Frontend gọi API lỗi 404 / không phản hồi | Backend chưa chạy → mở terminal khác `make backend`. |

---

## 8. Full pipeline: web + robot sim (Gazebo) + voice — chạy thật, KHÔNG mock

> **Đây là mục "chạy hệ thống hoàn chỉnh".** Robot Gazebo giờ là **robot thật của dispatcher**
> (không còn `mock_robot`): node `ai_sim_bridge/task_bridge` nối WS về backend, nhận `task.assign`
> → tự lái TurtleBot4 bằng **Nav2 + ArUco** (dùng lại `food_delivery.py`) → `arrived`/`task_done`,
> đồng thời stream pose (map frame) + **pin cố định 100%** để minimap panel bám robot realtime.

### 8.0 Ai chạy gì (mô hình thật: PC làm server, laptop chạy sim)

| Máy | Vai trò | Lệnh chạy |
|---|---|---|
| **PC** (server) | Backend + agent LLM + 3 web + Ollama | `make backend` · `make agent` · `make frontend` (Ollama bật sẵn) |
| **Laptop** (sim) | Gazebo/Nav2 + cầu nối robot + **mic/loa (voice)** | `ros2 launch …` · `make simbridge` · `make voice` |
| **Máy khác / màn robot** | Chỉ mở trình duyệt (qua Netbird) | `http://<PC>:5173` (menu) · `…:5174` (kiosk) · `…:5175` (panel) |

> **Netbird:** mọi client trỏ về **IP netbird của PC** (vd `100.x.x.x`). Chạy chung 1 máy để demo
> thì thay `<PC>` = `127.0.0.1`. Vite (`make frontend`) đã bind `0.0.0.0` + tự proxy `/api`,`/ws`
> về `:8000` **trên PC**, nên laptop khác mở `http://<PC>:5173` là gọi API/WS được, không dính CORS.

### 8.1 Bên PC (server — "bộ não")

```bash
# (lần đầu, hoặc sau khi pull) cài web + backend theo CUDA của PC:
make install UV_EXTRAS="--extra server --extra cu13"   # PC mới CUDA 13; CUDA 12 → --extra server --extra voice --extra cu12
ollama pull qwen2.5:7b-instruct                        # model agent dùng (chỉ lần đầu)

make backend      # terminal 1 — API + WebSocket (:8000)
make agent        # terminal 2 — agent LLM (:8100); tự reindex RAG lúc khởi động
make frontend     # terminal 3 — 3 web (5173/5174/5175), bind 0.0.0.0
```

### 8.2 Bên laptop (sim + voice — "thân xác")

```bash
# (lần đầu, hoặc sau khi pull) — laptop CUDA 12, cần extra voice cho STT/TTS:
make install UV_EXTRAS="--extra voice --extra cu12"
cd robot_ws && colcon build && cd ..                   # build ROS ws (task_bridge là node MỚI)

# .env ở gốc repo — trỏ voice về PC + đặt id robot (PHẢI trùng id robot sim):
#   ORCHESTRATOR_URL=http://<PC_netbird_ip>:8000
#   AGENT_URL=http://<PC_netbird_ip>:8100
#   VOICE_ROBOT_ID=robo-1
#   DEVICE=cuda

# Terminal 1 — Gazebo + Nav2 + localization (map nhà hàng) + RViz
cd robot_ws && . /opt/ros/humble/setup.sh && . install/setup.sh && cd ..
ros2 launch turtlebot4_ignition_bringup turtlebot4_ignition.launch.py \
  nav2:=true slam:=false localization:=true rviz:=true

# Terminal 2 — cầu nối robot sim ↔ dispatcher (thay pose_bridge + mock_robot)
make simbridge SERVER_HOST=100.66.165.221:8000 ID=robo-1

# Terminal 3 — voice device (mic + loa ngay trên laptop này)
make voice
```

> **`make voice` lần đầu tải model** (faster-whisper `medium` ~1.5GB + Piper voice tiếng Việt).
> Chờ tải + warmup xong nó in `[READY] … chờ điều tới bàn + web bấm 'nói chuyện'` rồi mới dùng được.

### 8.3 Voice hoạt động thế nào (đọc kỹ chỗ này)

Voice là **theo lệnh**, KHÔNG phải nghe suốt. Robot **tới bàn** (task_bridge báo `arrived`) →
dispatcher gắn `bàn → robo-1` → lúc này nút **"Nói với trợ lý"** trên customer_ui của bàn đó mới
định tuyến về **mic laptop**. Bấm nút → nói 1 câu → STT (laptop) → agent (PC, biết "Bàn N · M khách")
→ **loa laptop đọc trả lời** + hội thoại mirror lên tablet. `task_bridge` (di chuyển) và `voice`
(mic) **cùng dùng `robo-1`** — 1 robot mở 2 socket, backend tách riêng nên không đụng nhau.

**Muốn nói thẳng để test nhanh, không cần robot/tablet:** dùng bản test trực tiếp trên laptop —
```bash
uv run python scripts/voice_chat_test.py    # Enter → nói → nghe agent trả lời (bàn T1) → Enter nói tiếp
```

### 8.4 Kịch bản demo đầy đủ (~5 phút)

1. **Kiosk** (`<PC>:5174`): chọn bàn trống + số người → phiên mở (nhớ bàn + số khách) →
   dispatcher tạo `go_to_table` → **robot trong Gazebo chạy từ dock tới bàn**.
2. Robot tới nơi → **customer_ui tự mở màn chọn món** (mở `<PC>:5173`, chọn đúng "Bàn N").
   Khách đặt tay, hoặc bấm **"Nói với trợ lý"** rồi nói vào mic laptop → agent tư vấn/ghi món
   (nghe trả lời trên loa laptop). Đặt xong → robot tự về dock.
3. **Panel** (`<PC>:5175`): đơn hiện realtime; minimap + bảng robot bám pose/pin/hoạt động robot
   sim. Bếp tick `XONG` → robot chạy giao món.
4. Bấm **"Gọi robot"** trên panel (hoặc `POST /tables/{id}/call`) → robot tới; tablet mở màn
   "đặt thêm / thanh toán" → thanh toán xong robot về dock, bàn `ĐÃ THANH TOÁN`.

> **Lưu ý:** `task_bridge` thay `pose_bridge` (đã gồm heartbeat pose) — đừng chạy cả hai cùng `robot_id`.
> Sửa code bridge xong: `cd robot_ws && colcon build --packages-select ai_sim_bridge`.
> Muốn test luồng web/robot **không cần Gazebo**: dùng lại `make mockrobot ID=robo-1` (chỉ để debug).

---

## Tóm tắt 1 phút

```bash
# Lần đầu (máy đã có Node 22 + uv) — laptop CUDA 12:
make install UV_EXTRAS="--extra server --extra voice --extra cu12"

# Mỗi lần muốn chạy
make backend     # terminal 1
make frontend    # terminal 2  → 5173 / 5174 / 5175

# Dừng tất cả
make kill
```

Xem mọi lệnh: `make help`.
