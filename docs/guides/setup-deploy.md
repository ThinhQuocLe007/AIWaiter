# AI Waiter — Hướng dẫn cài đặt & test theo từng máy (Jetson · Server PC · Laptop)

> **Một file cài đặt + test duy nhất** cho cả fleet. Mỗi máy chỉ cài đúng **vai trò** nó đóng
> (pivot 2026-06: "não" = LLM/RAG/agent + backend dồn lên **SERVER**; Jetson robot chỉ giữ
> **voice** + ROS 2/Nav2). Bao trùm 4 bộ: **Web · Voice · LLM · Backend** + **quy trình test** (mục 7).
>
> ### ⭐ Pipeline deploy (chốt 2026-06): **SERVER lo HẾT web + backend**
> - **SERVER** build & serve **cả 3 web** (customer_ui, kiosk, panel) **cùng 1 origin** `http://<SERVER_IP>:8000/`
>   + chạy backend FastAPI + LLM + RAG + SQLite. Đây là **nguồn chân lý duy nhất**.
> - **Jetson robot** **KHÔNG cài Node, KHÔNG build web** — chỉ mở trình duyệt kiosk trỏ về server:
>   `chromium-browser --kiosk http://<SERVER_IP>:8000/`. Jetson chỉ còn lo **voice** (VAD/STT/TTS) + **Body** (ROS 2/Nav2).
> - **Laptop khác** (kiosk cổng, panel bếp, máy khách) **KHÔNG chạy backend/UI cục bộ** — chỉ mở
>   `http://<SERVER_IP>:8000/` (kiosk) hoặc `…/panel` là thao tác được ngay. Node **chỉ cần trên máy DEV frontend**.
>
> Đọc kèm: [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) (tổng thể) ·
> [Setup_&_Eval Guide.md](Setup_&_Eval%20Guide.md) (env + eval chi tiết) ·
> [jetson-ctranslate2-build.md](jetson-ctranslate2-build.md) (build STT trên Jetson).

---

## 0. TL;DR — máy nào cài bộ nào

| Bộ | **Server (PC, x86)** | **Jetson robot** | **Laptop (theo vai demo)** |
|---|---|---|---|
| **Backend** (FastAPI + SQLite) | ✅ chạy ở đây | ❌ | chỉ khi laptop đóng vai Server |
| **LLM** (Ollama/llama.cpp + agent + RAG) | ✅ chạy ở đây | ❌ (không còn LLM) | chỉ khi laptop đóng vai Server |
| **Voice** (VAD + STT + TTS) | ⬜ tùy chọn (để test) | ✅ chạy ở đây | chỉ khi laptop đóng vai Robot |
| **Web** | ✅ **build & serve CẢ 3 web** (customer_ui + kiosk + panel) cùng origin `:8000` | ❌ **không Node, không build** — chỉ `chromium-browser --kiosk http://<SERVER_IP>:8000/` | ❌ chỉ mở trình duyệt tới `http://<SERVER_IP>:8000/...` (Node chỉ khi DEV frontend) |
| **ROS 2 / Nav2** (Body) | ❌ | ✅ phần **real** (`src/real`, colcon) | phần **sim** Gazebo (`src/sim`, colcon) khi đóng vai Robot |

**Chọn extra CUDA theo máy** (trên x86 torch lấy đúng theo CUDA của máy):

| Máy x86 | CUDA | extra torch |
|---|---|---|
| **Server (PC mới)** — Blackwell, driver ≥580 | **13** | `--extra cu13` |
| **Máy dev (laptop)** — GPU đời cũ, driver CUDA 12 | **12** | `--extra cu12` |
| Jetson (aarch64) | 12.6 | *không cần* — torch GPU auto từ index jetson |

**Lệnh `uv sync` theo vai trò** (extras trong `pyproject.toml`):

```bash
# SERVER (PC mới, CUDA 13):        não + RAG + backend
uv sync --extra server --extra cu13

# JETSON robot (aarch64):          chỉ voice (torch GPU auto từ index jetson)
uv sync --extra voice              # + build ctranslate2 bằng tay (mục 2.B-3)

# MÁY DEV (laptop, CUDA 12) chạy cả brain LẪN voice:
uv sync --extra server --extra voice --extra cu12
```

> ⚠️ **Khác với hướng dẫn cũ:** `uv sync` **trơn (không `--extra`)** giờ chỉ cài *base nhỏ*
> (pydantic/numpy/dotenv/tqdm + torch trên Jetson). Phải truyền **extra của vai trò** thì mới
> có đủ package. Đây là chủ đích của việc tách brain↔voice.

---

## 1. Phân lớp máy & điều kiện chung

3 lớp máy. Khi demo bằng 3 laptop (mục 4) thì **mỗi laptop đóng một vai** trong 3 lớp này.

| Lớp | Kiến trúc | Cài bộ gì | Chú thích |
|---|---|---|---|
| **Server (PC)** | x86_64 + GPU | Backend + LLM + RAG + **build & serve cả 3 web** | "não" — 1 máy cho cả fleet |
| **Jetson robot** | aarch64 (JetPack 6) | Voice + ROS 2/Nav2 (**real**); web = **chỉ chromium kiosk** trỏ về server | "thân xác" — mỗi robot 1 con, **không Node** |
| **Laptop (dev/demo)** | x86_64 | tùy vai đóng | xem mục 4 |

### 1.1 Điều kiện chung (mọi máy Python)

```bash
# uv — quản lý môi trường Python (cài 1 lần)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version            # >= 0.11

# Python 3.10 (khớp ROS 2 Humble). uv tự quản; .python-version đã ghim 3.10.
```

### 1.2 Điều kiện cho Web (CHỈ máy **build** frontend = SERVER, hoặc máy DEV)

Node **chỉ cần ở nơi BUILD web** = **SERVER** (build & serve cả 3 web), hoặc máy **dev frontend**
(`npm run dev`). **Jetson robot và các laptop chỉ-xem KHÔNG cần Node** — chúng chỉ mở trình duyệt
trỏ tới `http://<SERVER_IP>:8000/...`.

```bash
# Node 22 qua nvm (.nvmrc đã ghim 22) — chạy trên SERVER / máy dev frontend
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
. "$HOME/.nvm/nvm.sh"
nvm install            # đọc .nvmrc -> Node 22
node -v                # v22.x
```

> Máy **chỉ xem/thao tác web** (Jetson kiosk, kiosk tablet ở cổng, panel bếp, laptop khách)
> **không cần Node** — chỉ cần **trình duyệt** trỏ tới `http://<SERVER_IP>:8000/...`. **Server** là nơi
> duy nhất build & serve.

---

## 2. Cài theo từng máy

### 2.A — SERVER (PC, x86): Backend + LLM + RAG + Web

> "Não" của hệ: FastAPI + SQLite + LLM/agent + RAG, đồng thời **build & serve cả 3 web**.

**(1) Python env — vai `server`:**
```bash
cd <repo-root>
uv sync --extra server --extra cu13         # PC mới = CUDA 13 -> cu13  (laptop dev CUDA 12 -> cu12)
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

**(2) LLM runtime (Ollama) + model:** → xem **mục 3.LLM**.

**(3) Embedding + storage (DB/FAISS/BM25):**
```bash
cp .env.template .env                        # chỉnh DEVICE / EMBEDDING_DEVICE / *_MODEL nếu cần
uv run python scripts/setup.py               # dựng storage/: SQLite + FAISS + BM25 (+ centroids nếu thiếu)
```
> `storage/` bị git-ignore → **máy mới phải chạy `scripts/setup.py` một lần**. Chi tiết khi nào
> dùng `--force` / `--embeddings-only`: [Setup_&_Eval Guide.md §2](Setup_&_Eval%20Guide.md).

**(4) Web — build & serve cả 3 frontend:** → xem **mục 3.Web**.

**(5) Chạy backend (serve API + web + WS hub):**
```bash
make backend            # uvicorn src.server_orchestrator.main:app --host 0.0.0.0 --port 8000
```

---

### 2.B — JETSON robot (aarch64): Voice + ROS 2/Nav2 (web = chromium kiosk)

> "Thân xác": nghe (VAD+STT) / nói (TTS) **cục bộ**, + Body (ROS 2/Nav2). Màn hình chỉ là **trình duyệt
> kiosk** trỏ về server. **Không** cài LLM/RAG, **không** cài Node, **không** build web.

**(1) System libs cho audio** (pyaudio/sounddevice/soundfile cần native libs):
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev libsndfile1 libportaudio2
```

**(2) Python env — vai `voice`:**
```bash
cd <repo-root>
uv sync --extra voice                        # torch GPU tự lấy từ index jetson-ai-lab (cu126)
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"   # mong: 2.11.0 True
```
> Nếu lỗi `libcudss.so.0`: `sudo apt-get install -y libcudss0-cuda-12`.

**(3) STT (faster-whisper / CTranslate2) — build TAY trên Jetson:**

`pyproject.toml` cố tình **không** cài faster-whisper trên aarch64: wheel PyPI chỉ có Python binding,
**thiếu** C++ runtime `libctranslate2.so` → `import` sẽ lỗi. Phải build CTranslate2 từ nguồn (lần đầu
~30–40′). Hướng dẫn đầy đủ + recovery: **[jetson-ctranslate2-build.md](jetson-ctranslate2-build.md)**.

> **CẦN CÀI (tóm tắt 5 bước trong doc):**
> 1. Prereq: `build-essential cmake git` (cmake ≥3.18) + cuDNN (JetPack 6 có sẵn) + **swap** (build C++ ngốn RAM).
> 2. Build C++ lib CTranslate2 v4.6.0 (`-DWITH_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87`) → cài `/usr/local` → **`sudo ldconfig`**.
> 3. Build Python binding vào venv: `CTRANSLATE2_ROOT=/usr/local uv pip install . --no-build-isolation`.
> 4. `uv pip install faster-whisper --no-deps` rồi `uv pip install tokenizers huggingface-hub av onnxruntime`.
> 5. Verify từ `~` (KHÔNG đứng trong `~/CTranslate2/python`).
>
> **NÉ (bẫy đã dính thật):**
> - **Luôn `uv sync --inexact`** — `uv sync` trơn *xoá* ctranslate2/faster-whisper build tay (đúng theo lock).
> - Chạy app bằng `uv run --no-sync ...` **hoặc** venv đã `activate` — `uv run` ngầm sync → cũng xoá.
> - `faster-whisper` phải **`--no-deps`** — không thì nó kéo ctranslate2 PyPI **đè** bản build tay.
> - **`make -j2`** thôi (đừng `-j$(nproc)`) — 8GB RAM dễ OOM-kill lúc compile CUDA; bật swap trước.
> - **`sudo ldconfig`** bắt buộc sau khi copy `/usr/local` — thiếu thì loader không thấy `libctranslate2.so.4`.
> - Test `import ctranslate2` phải `cd ~` trước — đứng trong `~/CTranslate2/python` sẽ bị shadow.

> #### ✅ Sau (2)+(3)+(4), Jetson "vừa đủ" cho voice — không thừa, không thiếu
> | Cần cho | Có từ đâu |
> |---|---|
> | **torch** (GPU cu126) | `uv sync --extra voice` (base aarch64, auto index jetson) |
> | **VAD** (silero) | torch.hub lúc runtime + `scipy` — trong `--extra voice` |
> | **STT** (faster-whisper) | **build tay** mục (3) |
> | **huggingface-hub** (tải model whisper) | **build tay** mục (3) — Step 4 |
> | **TTS** (edge-tts + phát audio) | `sounddevice`/`soundfile` — trong `--extra voice` |
> | **Mic** | `pyaudio` (+ system portaudio) — trong `--extra voice` |
> | **ROS 2 / Nav2** | colcon/apt, env riêng — mục (4) |
>
> Tóm lại: `uv sync --extra voice` lo **torch + VAD + TTS + mic**; **STT + huggingface** tới từ build
> tay mục (3); **ROS 2** ở mục (4). **KHÔNG** cần `--extra server`, Jetson **không** có LLM/RAG.

**(4) Body — ROS 2 Humble + Nav2 (colcon env RIÊNG, không qua uv):**

`robot_ws/src/` chia theo **nơi triển khai** (xem `robot_ws/README.md`): `common/` (Nav2 + driver +
URDF — build mọi nơi) · `sim/` (Gazebo — **chỉ laptop**) · `real/ai_hw_bridge` (**robot thật, Jetson**).

```bash
# Trên JETSON (robot thật): build common (+ real), BỎ QUA sim Gazebo (nặng, không dùng trên robot).
# rclpy KHÔNG phải package PyPI — đi kèm ROS 2 Humble (apt).
cd robot_ws
colcon build --packages-ignore turtlebot4_ignition_bringup turtlebot4_python_tutorials
source install/setup.bash
```
> `real/ai_hw_bridge` hiện **rỗng** (`COLCON_IGNORE`) — node nhận `navigate` → đặt Nav2 goal **chưa viết**
> (SYSTEM_ARCHITECTURE §4, §11). Phần **sim Gazebo** chạy ở **laptop** (mục 2.C / 4), không phải Jetson.

**(5) Web trên robot — CHỈ chromium kiosk trỏ về SERVER (KHÔNG Node, KHÔNG build):**

Theo pipeline chốt 2026-06, **server build & serve `customer_ui`** (cùng origin với API → khỏi CORS).
Jetson **không cài Node, không `npm`, không `dist/`** — chỉ mở trình duyệt **toàn màn hình** trỏ thẳng
về server (cờ `chromium --kiosk` = *chế độ kiosk của trình duyệt*, không liên quan tới app tên "kiosk"):

```bash
# Chỉ cần trình duyệt — KHÔNG Node, KHÔNG npm:
sudo apt-get install -y chromium-browser
chromium-browser --kiosk --noerrdialogs --disable-infobars http://<SERVER_IP>:8000/
```

> - Server quyết định màn hình nào hiện (`/`, `/menu`, `/payment`) qua REST/WS — Jetson chỉ render.
>   Muốn ghim đúng bàn: thêm query param do server hỗ trợ (vd `…:8000/?table=3`) thay vì build riêng.
> - **Vì sao bỏ build trên Jetson:** trước đây mỗi robot phải cài Node + `npm run build` + `vite preview`
>   → nặng, mỗi máy 1 bản build dễ lệch. Gom về server: **1 nơi build, mọi robot/laptop chỉ mở URL**.
> - Chi tiết build/serve phía server: **mục 3.Web**.

**(6) Robot-agent WS client — gửi STT lên server · nhận text về để TTS:**

Tiến trình Python nối Jetson ↔ server: gửi `stt_text` (đã STT cục bộ) lên, nhận `say` (server/LLM
trả lời) → đọc bằng **TTS**, relay `navigate` xuống Body. Luồng đầy đủ:

```
mic → VAD → STT → WS↑ SERVER (LLM/agent) → WS↓ Jetson → TTS đọc cho khách
```

> ⚠️ **Hiện CHƯA có file `ws_client.py`** — các placeholder cũ trong `interfaces/` đều rỗng và đã được
> dọn. Đây là việc cần viết (SYSTEM_ARCHITECTURE §4 "robot-agent", §11 Mốc B). Tạm thời
> `src/edge_voice/main.py` là pipeline voice **all-in-one cũ** (VAD+STT+agent+TTS cùng máy) để test cục bộ.

---

### 2.C — LAPTOP: theo vai đóng

Laptop x86 cài **giống lớp máy mà nó đóng vai**:

| Vai laptop đóng | Cài như | Lệnh chính |
|---|---|---|
| **Server** (LLM + backend + **serve cả 3 web**) | mục **2.A** | `uv sync --extra server --extra cu13` + Ollama + setup.py + `make build` |
| **Robot SIM** (Gazebo + voice; web = chromium kiosk) | mục **2.B** (x86: **khỏi** build ctranslate2) + ROS 2 **sim** | `uv sync --extra voice --extra cu12` + `colcon build` (common+sim); web = mở `http://<SERVER_IP>:8000/` |
| **Bảng điều khiển** (panel) / **Kiosk** | **chỉ trình duyệt** | mở `http://<SERVER_IP>:8000/panel` hoặc `…/` (kiosk). *Chỉ khi DEV frontend* mới cần Node + `make panel`/`make kiosk` |

> - Laptop đóng vai Robot dùng **`sim`** (Gazebo, `src/sim`) — **khác** Jetson dùng **`real`** (`src/real`).
> - Laptop đóng vai Robot SIM **không build customer_ui cục bộ** — mở thẳng `http://<SERVER_IP>:8000/`
>   (giống Jetson). Server lo build & serve.
> - Trên **laptop x86** faster-whisper **cài thẳng từ PyPI** (không build tay như Jetson) — đã nằm trong
>   `--extra voice` với marker `x86_64`, nên `uv sync --extra voice --extra cu12` là đủ cho STT.

---

## 3. Cài theo từng BỘ (chi tiết)

### 3.Web — customer_ui · kiosk · panel (Vue 3 + Vite, Node 22)

3 frontend trong `src/frontends/`. Cổng dev cố định: customer_ui **5173**, kiosk **5174**, panel **5175**
(proxy `/api` → `:8000`, không CORS).

**Deploy thật (pipeline chốt 2026-06):** **SERVER build & serve CẢ 3 web cùng origin `:8000`** — backend
FastAPI mount static `dist/` của từng app:
- `…:8000/` → **customer_ui** (màn hình robot / tablet tại bàn).
- `…:8000/kiosk` → **Kiosk cổng** (chọn bàn + số người).
- `…:8000/panel` → **Bảng điều khiển** (bếp + giám sát).

Mọi client (Jetson robot, kiosk tablet, panel bếp, laptop khách) **chỉ mở URL** tới server — **không build,
không Node**. Server là nơi build duy nhất:

```bash
# TRÊN SERVER (cần Node 22, mục 1.2):
make install            # npm ci/install cho cả 3 frontend (+ uv sync gốc)
make build              # build tĩnh CẢ 3 -> dist/, backend (make backend) tự serve cùng origin :8000
```

> **Chỉ khi DEV frontend** (sửa giao diện, hot-reload) mới chạy dev server cục bộ — KHÔNG dùng cho deploy:
> ```bash
> make frontend           # dev hot-reload: menu 5173 · kiosk 5174 · panel 5175 (proxy /api → :8000)
> # hoặc 1 app lẻ: cd src/frontends/<customer_ui|kiosk|panel> && npm install && npm run dev
> ```

### 3.Voice — VAD + STT + TTS (bộ `--extra voice`)

| Thành phần | Package | Ghi chú cài |
|---|---|---|
| **VAD** | torch (silero qua `torch.hub`) + scipy | torch: base (Jetson) / cu12-13 (x86) |
| **STT** | faster-whisper (CTranslate2) | x86: PyPI · **Jetson: build tay** (2.B-3) |
| **Mic** | pyaudio | cần `portaudio19-dev` |
| **TTS** | edge-tts + sounddevice + soundfile | cần `libsndfile1`, `libportaudio2`; edge-tts là **cloud** (offline Piper = TODO) |

```bash
# Laptop dev x86 test voice (CUDA 12):
uv sync --extra voice --extra cu12            # PC mới CUDA 13 -> cu13
# Verify nhanh:
uv run python scripts/probe_vad.py            # mic + VAD
uv run python scripts/probe_stt.py --audio test.wav
```

### 3.LLM — Ollama/llama.cpp + agent + RAG (bộ `--extra server`, chạy ở SERVER)

**(1) Ollama + model** (cả router/worker/response dùng **1 model**, override qua `.env`):
```bash
ollama serve                                  # nếu chưa chạy như service
ollama pull gemma4:e2b-it-qat                 # model mặc định (baseline)
ollama list
```
> **Trên Jetson** (nếu vẫn chạy LLM ở Jetson theo phương án cũ): bản `curl|sh` thường **không nhận
> iGPU** → phải cài bản **prebuilt JetPack 6** + tinh chỉnh RAM. Hậu-pivot LLM ở **server** nên việc này
> chủ yếu là legacy — chi tiết GPU/RAM: [Setup_&_Eval Guide.md §6.3–6.4](Setup_&_Eval%20Guide.md).

**(2) Chọn cỡ model** (server không bị giới hạn 8GB như Jetson) → khuyến nghị & cách eval:
[jetson-orin-nano-llm-sizing-and-runtime.md](jetson-orin-nano-llm-sizing-and-runtime.md)
(Qwen2.5-3B / Gemma-3-4B Q4 là sweet spot; đo bằng `evals/scripts/*`).

**(3) Embedding** (tự tải từ HuggingFace lần đầu; dùng chung retrieval + router):
```dotenv
# .env
EMBEDDING_MODEL=                 # trống = AITeamVN/Vietnamese_Embedding (BGE-M3, 1024-dim, ~2.2GB)
EMBEDDING_DEVICE=                # trống = theo DEVICE; đặt cpu để nhường RAM GPU cho LLM
```
> Đổi embedding **phải rebuild**: `uv run python scripts/setup.py --embeddings-only`. Danh sách model
> + bẫy "centroids sai chiều": [Setup_&_Eval Guide.md §6.6](Setup_&_Eval%20Guide.md).

### 3.Backend — FastAPI + SQLite (bộ `--extra server`, chạy ở SERVER)

```bash
uv sync --extra server --extra cu13           # fastapi + uvicorn[standard] nằm trong extra server
uv run python scripts/setup.py                # dựng SQLite + FAISS + BM25 (mục 2.A-3)
make backend                                  # serve :8000 (REST + WS hub + serve web tĩnh)
# Reset dữ liệu demo (backend đang chạy):
make reset
```
SQLite ở `storage/db/` (restaurant / orchestrator / checkpoints). Mô hình dữ liệu: architecture §8.

---

## 4. Demo 3 laptop (LAN chung) — ai cài gì

Mạng LAN chung; Server IP cố định (vd `192.168.1.10`). Client trỏ về `SERVER_IP:8000`.
(Server đặt xa thì cài **Netbird**, đổi 1 biến `SERVER_HOST=100.x` — architecture §2.1, §10.1.)

| Laptop | Vai | Cài (mục) | Chạy |
|---|---|---|---|
| **L1** | Server + LLM + **serve cả 3 web** | 2.A | `make build` + `make backend` + Ollama; mở `/kiosk` |
| **L2** | Robot sim (Gazebo) + voice | 2.C-Robot + ROS 2 | `colcon` + Gazebo + bridge; web = mở `http://192.168.1.10:8000/` |
| **L3** | Bảng điều khiển | **chỉ browser** | mở `http://192.168.1.10:8000/panel` |

> Cả 3 web (customer_ui, kiosk, panel) đều do **L1 serve cùng origin `:8000`** — L2/L3 không build gì.

Kịch bản demo ~5′: SYSTEM_ARCHITECTURE §10.

---

## 5. Verify nhanh (sau khi cài)

```bash
# Server
uv run python -c "import torch, fastapi, langgraph, faiss; print('server OK', torch.cuda.is_available())"
uv run python evals/scripts/eval_router.py          # brain hoạt động

# Jetson robot (sau khi build ctranslate2)
cd ~ && uv run --no-sync python -c "import ctranslate2; from faster_whisper import WhisperModel; print(ctranslate2.__version__, 'OK')"
uv run --no-sync python scripts/probe_stt.py --audio test.wav

# Web (trên SERVER — build + serve cùng origin)
make build && make backend                       # rồi mở:
#   http://<SERVER_IP>:8000/        (customer_ui)
#   http://<SERVER_IP>:8000/kiosk   (kiosk cổng)
#   http://<SERVER_IP>:8000/panel   (bảng điều khiển)
# Client (Jetson/laptop khác) chỉ cần mở các URL trên — không build gì.
```

---

## 6. Bẫy hay gặp

- **`uv sync` trơn cài thiếu** → quên `--extra <vai>`. Server: `--extra server --extra cu13`; robot: `--extra voice`.
- **Jetson mất ctranslate2 sau `uv sync`** → luôn `uv sync --inexact`; chạy app bằng `uv run --no-sync` hoặc venv đã activate. ([jetson-ctranslate2-build.md](jetson-ctranslate2-build.md) §Gotchas).
- **TTS không kêu** → thiếu `libsndfile1`/`libportaudio2`, hoặc chưa `--extra voice` (edge-tts/sounddevice/soundfile).
- **Router accuracy 0%** → đổi `EMBEDDING_MODEL` mà quên `scripts/setup.py --embeddings-only` (centroids sai chiều).
- **App lỗi thiếu FAISS/DB** → chưa chạy `scripts/setup.py` (storage/ bị git-ignore).
- **Ollama chạy CPU trên Jetson** → cài bản prebuilt JetPack 6 ([Setup_&_Eval Guide.md §6.4](Setup_&_Eval%20Guide.md)).

---

## 7. Quy trình TEST (voice · web · brain)

> Nơi duy nhất theo dõi đã test gì, trên máy nào, bằng cách nào. (Gộp từ 2 file cũ
> `testing-tracker.md` + `vad-mic-testing-guide.md` đã xoá.)
>
> Ký hiệu: ✅ xong · 🔄 đang làm · ⬜ chưa · ⏸ tạm hoãn.

### 7.0 Bảng trạng thái nhanh

| Mảng | Thành phần | Cách test | Laptop (dev) | Jetson Orin |
|---|---|---|---|---|
| **Voice** | Mic + VAD (cắt câu nói) | `scripts/probe_vad.py [--mic]` | ✅ | ⬜ |
| **Voice** | STT — file → text | `scripts/probe_stt.py --audio f.wav` | 🔄 | ⬜ |
| **Voice** | STT — **mic trực tiếp → text** | `scripts/probe_stt_live.py` | ⬜ | ⬜ (mic USB cắm thẳng) |
| **Voice** | TTS (text → speech) | _chưa có probe_ | ⬜ | ⬜ |
| **Web** | Đặt món (customer_ui) — **bản production** | §7.2 (`make build` + `make backend`) | ⬜ | ⬜ |
| **Web** | Backend API (orders/tables/payments) | §7.2.3 (curl) | ⬜ | ⬜ |
| **Brain** | Embedding / Retrieval (RAG) | `evals/scripts/eval_retrieval.py` | ⏸ sau | ⏸ sau |
| **Brain** | Router / Workers / E2E agent | `evals/scripts/eval_*.py` (cần Ollama) | ⏸ sau | ⏸ sau |

### 7.1 Test voice — 2 đích, 2 cách (mic phải CỤC BỘ)

> **SSH không forward được mic.** Tiến trình thu âm từ mic của **máy nó đang chạy**. Nếu SSH từ laptop
> vào Jetson rồi chạy probe → nó thu mic của *Jetson* (thường jack rỗng = im lặng), nói vào laptop vô ích.
> → **Test mic ở ngay máy bạn đang ngồi.** Trên Jetson: cắm **mic USB thẳng vào Jetson** thì mic mới cục bộ.

**Chuẩn bị (mọi máy test voice):**
```bash
sudo apt-get install -y portaudio19-dev            # lib PyAudio bind tới
uv sync --extra voice --extra cu12                 # laptop CUDA12 (PC mới: cu13; Jetson: chỉ --extra voice)
# Kiểm tra có thiết bị thu, không im lặng:
arecord -l                                         # phải liệt kê 1 card thu
arecord -d 20 -f S16_LE -r 16000 test.wav          # nói 20s, 16kHz mono
aplay test.wav                                     # nghe lại — phải nghe được giọng mình
```
> Nếu `aplay` phát ra im lặng → **OS không thu được** (unmute / chọn đúng input) — sửa trước khi đụng code.

#### 7.1.1 Laptop — mic trực tiếp, real-time

Bạn ngồi tại laptop nên mic tích hợp là cục bộ → nói và xem text hiện ra.

**a) VAD (cắt câu) — `probe_vad.py`:**
```bash
uv run python scripts/probe_vad.py            # synthetic (không mic): load model + đo RAM
uv run python scripts/probe_vad.py --mic      # mic: in speech=True khi nói / False khi im, Ctrl-C dừng
```

**b) STT từ file — `probe_stt.py`:**
```bash
arecord -d 20 -f S16_LE -r 16000 test.wav     # thu 20s tiếng Việt, 16kHz mono
uv run python scripts/probe_stt.py --audio test.wav   # dòng cuối [stt out] '…' = bản dịch
```

**c) ⭐ STT mic TRỰC TIẾP — `probe_stt_live.py` (nói → thấy text ngay):**

`probe_stt.py` chỉ làm *file → text*. Để test trải nghiệm thật — **nói và xem text hiện** — dùng
`probe_stt_live.py`. Nó chạy `SileroVAD` + `PhoWhisperSTT` thật (cùng wiring với
`src/edge_voice/main.py`) nhưng **bỏ** agent/LLM/TTS, nên cô lập đúng đường *mic → VAD → STT*.
**Không cần Ollama.**

```bash
# Máy NATIVE có mic cục bộ chạy được — KHÔNG qua SSH (xem đầu §7.1).
uv run python scripts/probe_stt_live.py
```

Nói tiếng Việt; mỗi câu hoàn chỉnh in ra:
```
[cfg] DEVICE=cuda  (STT compute: float16)
====================================================
 Live STT ready — speak Vietnamese into the mic
 Ctrl-C to stop
====================================================
[HEARD @  3.4s | 1.6s audio]: cho tôi một ly cà phê sữa
[HEARD @  9.1s | 2.0s audio]: thêm một phần cơm gà nữa
```

Luồng: **VAD mở mic + phát hiện câu bắt đầu/kết thúc** → đưa audio cho **STT** → STT dịch → in dòng.
Có độ trễ ngắn (`SILENCE_TIMEOUT = 1.5s`) sau khi ngừng nói trước khi text hiện — đó là VAD chốt câu, không phải treo.

Cùng các knob như VAD probe:
```bash
VAD_THRESHOLD=0.4 MIC_DEVICE_INDEX=4 uv run python scripts/probe_stt_live.py
```
> Nếu không bao giờ in gì: trước hết xác nhận mic bằng `probe_vad.py --mic` (có `speech=True` khi nói?).
> Nếu VAD thấy speech nhưng không ra text → lỗi ở STT, không phải mic.

#### 7.1.2 Jetson — thu → scp → transcribe (chỉ SSH được)

SSH không stream được mic laptop vào Jetson. Thu cục bộ, copy file, transcribe trên Jetson:
```bash
# trên LAPTOP
arecord -d 20 -f S16_LE -r 16000 test.wav
aplay test.wav                                       # xác nhận thu được giọng, không im
scp test.wav jetson@<jetson-ip>:~/AI_Waiver/
# trên JETSON (ssh)
uv run --no-sync python scripts/probe_stt.py --audio test.wav   # xem tegrastats/jtop cho RAM unified
```
Cách này xác nhận **model STT + dung lượng RAM unified** trên đích thật, **nhưng KHÔNG** đo độ trễ mic
on-device. Muốn đo: **cắm mic USB vào Jetson** (mic cục bộ → SSH không còn cản) rồi chạy
`probe_stt_live.py` (§7.1.1) ngay trong shell SSH.

> **Model STT thực tế đang chạy:** dù tên class là `PhoWhisperSTT`, code hiện load **Whisper `small`** qua
> `faster-whisper` (ctranslate2), ép `language="vi"`, `DEVICE=cuda`→float16 / `cpu`→int8. Chất lượng tiếng
> Việt (nhất là tên món) ở mức Whisper `small` là bình thường — không phải lỗi mic/file. Đổi sang PhoWhisper thật là việc riêng.

#### 7.1.3 Troubleshooting voice

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `OSError -9999 Unanticipated host error` | Mở route `default`/PipeWire không tới được (SSH/service). | Chạy native, hoặc đặt `MIC_DEVICE_INDEX` tới `hw:*` thật. |
| `OSError -9997 Invalid sample rate` | Card không hỗ trợ rate yêu cầu (vd 16kHz). | Đã tự fallback 48kHz + resample. Nếu ép `MIC_SAMPLE_RATE` thì chọn rate được hỗ trợ. |
| Luôn `speech=False` khi đang nói | Mic thu im lặng (sai input/mute/jack rỗng), hoặc SSH nói nhầm máy. | Kiểm tra bằng `arecord`/`aplay` (đầu §7.1). Chạy native. |
| Dòng đỏ `ALSA lib pcm_*` lúc khởi động | Tiếng ồn ALSA khi PortAudio quét thiết bị. | Bỏ qua — nếu sau đó có `Mic opened:` là thu OK. |
| `STT error: libcublas.so.12 not found` / torch chạy CPU | Sai profile CUDA trên x86 (kéo nhầm torch cu13). | Dùng đúng `--extra cu12`/`--extra cu13` (xem bảng CUDA mục 0 + §6). |
| Quá nhạy / kém nhạy | Ngưỡng VAD. | Chỉnh `VAD_THRESHOLD` (0.3 nhạy hơn, 0.7 chặt hơn). |

> **Knob môi trường:** `VAD_THRESHOLD` (mặc định 0.5) · `MIC_DEVICE_INDEX` (ép index PortAudio) ·
> `MIC_SAMPLE_RATE` (ép rate native). Liệt kê index thiết bị thu:
> ```bash
> uv run python -c "import pyaudio; p=pyaudio.PyAudio(); [print(i, p.get_device_info_by_index(i)['name']) for i in range(p.get_device_count()) if p.get_device_info_by_index(i)['maxInputChannels']>0]"
> ```
>
> **Lưu ý Jetson:** `faster-whisper`/ctranslate2 quản CUDA memory **ngoài** torch → dòng `GPU alloc` có thể
> ~0 dù chạy CUDA. Tin **`tegrastats`/`jtop`** (RAM unified 8GB, dùng chung với LLM+embedding) cho con số thật.

### 7.2 Test web (đặt món) — chế độ PRODUCTION (server serve)

Phạm vi: **customer_ui** (tablet đặt món) + **backend**, ở **bản production** do **SERVER build & serve
cùng origin** — đúng pipeline deploy (mục 3.Web), không phải dev server `make frontend`.

#### 7.2.1 Build + serve
```bash
make backend          # terminal 1 — FastAPI :8000 (seed bàn 1–6 + menu) + serve static cả 3 web
make build            # build cả 3 frontend -> dist/ (server mount cùng origin)
```
Mở **http://<SERVER_IP>:8000/** (customer_ui) · `…/kiosk` · `…/panel`. Vì cùng origin với API nên
**không cần proxy, không CORS** — khác hẳn dev (`make frontend`, proxy `/api`→:8000).

#### 7.2.2 Luồng kiểm tra tay (bản production)
- [ ] Trang load, menu fetch (217 món) — không trắng màn / lỗi fetch.
- [ ] DevTools → Network: `/menu` trả **200**.
- [ ] Thêm món vào giỏ → tổng tiền đúng.
- [ ] Xác nhận đơn → nút "Đang gửi đơn…" rồi báo thành công.
- [ ] (đối chiếu) đơn hiện trên Panel (`…/panel`) hoặc `GET /orders`.
- [ ] Màn Service: bàn đang phục vụ + có đơn mở → "Gọi món thêm" / "Thanh toán" đều chạy.
- [ ] Payment: màn QR đúng số tiền → "Đã thanh toán xong" → bàn chuyển `DA_THANH_TOAN`.

#### 7.2.3 Smoke test API (độc lập UI)
```bash
curl -s localhost:8000/health
curl -s localhost:8000/menu | head -c 200
curl -s localhost:8000/tables
curl -s -X POST localhost:8000/seatings -H 'content-type: application/json' -d '{"table_id":1,"party_size":2}'
curl -s -X POST localhost:8000/orders   -H 'content-type: application/json' -d '{"table_id":1,"items":[{"dish_id":1,"qty":1}]}'
curl -s -X POST localhost:8000/payments/1
```
Reset dữ liệu demo giữa các lần: `make reset` (backend đang chạy) hoặc xoá `storage/db/orchestrator.db` rồi restart.

### 7.3 Tạm hoãn — embedding / brain

Chưa test bây giờ (theo yêu cầu). Khi nối lại:
- Dựng FAISS + centroids: `uv run python scripts/setup.py`.
- Chất lượng retrieval: `uv run python evals/scripts/eval_retrieval.py`.
- So embedding model: `scripts/bench_embedding.sh`.
- Router / E2E: `evals/scripts/eval_router.py`, `eval_e2e.py` (cần Ollama).
