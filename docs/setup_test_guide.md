# AI Waiter — Hướng dẫn cài đặt theo từng máy (Jetson · Server PC · Laptop)

> **Một file cài đặt duy nhất** cho cả fleet. Mỗi máy chỉ cài đúng **vai trò** nó đóng
> (pivot 2026-06: "não" = LLM/RAG/agent + backend dồn lên **SERVER**; Jetson robot chỉ giữ
> **voice** + customer_ui + ROS 2/Nav2). Bao trùm 4 bộ: **Web · Voice · LLM · Backend**.
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
| **Web** | (tùy chọn) serve web cùng origin API | **build PRODUCTION `customer_ui`** (menu UI của robot) | **kiosk** + **panel** chạy ở đây (`npm run dev` cũng được) |
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
| **Server (PC)** | x86_64 + GPU | Backend + LLM + RAG + build/serve Web | "não" — 1 máy cho cả fleet |
| **Jetson robot** | aarch64 (JetPack 6) | Voice + ROS 2/Nav2 (**real**) + production customer_ui | "thân xác" — mỗi robot 1 con |
| **Laptop (dev/demo)** | x86_64 | tùy vai đóng | xem mục 4 |

### 1.1 Điều kiện chung (mọi máy Python)

```bash
# uv — quản lý môi trường Python (cài 1 lần)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version            # >= 0.11

# Python 3.10 (khớp ROS 2 Humble). uv tự quản; .python-version đã ghim 3.10.
```

### 1.2 Điều kiện cho Web (máy nào **build** frontend)

```bash
# Node 22 qua nvm (.nvmrc đã ghim 22)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
. "$HOME/.nvm/nvm.sh"
nvm install            # đọc .nvmrc -> Node 22
node -v                # v22.x
```

> Máy **chỉ xem web** (kiosk tablet, panel laptop) **không cần Node** — chỉ cần **trình duyệt**
> trỏ tới `http://<SERVER_IP>:8000/...`. Server (hoặc máy dev) là nơi build & serve.

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
make backend            # uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000
```

---

### 2.B — JETSON robot (aarch64): Voice + ROS 2/Nav2 + customer_ui

> "Thân xác": nghe (VAD+STT) / nói (TTS) **cục bộ**, + Body (ROS 2/Nav2), + màn hình customer_ui.
> **Không** cài LLM/RAG.

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

**(5) Web trên robot — CHỈ `customer_ui` (menu UI), dạng PRODUCTION:**

Mỗi robot chỉ chạy **`customer_ui`** (menu đặt món) full-screen trên LCD — **KHÔNG** chạy `kiosk` hay
`panel` (hai app đó ở máy khác, mục 3.Web). Build **production** rồi mở bằng trình duyệt **toàn màn hình**
(cờ `chromium --kiosk` = *chế độ kiosk của trình duyệt*, không liên quan tới app tên "kiosk"). Frontend
nói chuyện với server qua REST/WS (`shared/ws.ts`, `shared/rest.ts`); URL lấy từ `.env`.

```bash
# 1) Node 22 (xem 1.2). Build production cần URL TUYỆT ĐỐI trỏ về SERVER (không qua proxy dev):
cd src/frontends/customer_ui
cp .env.example .env
#   sửa .env:
#     VITE_API_URL=http://<SERVER_IP>:8000
#     VITE_WS_URL=ws://<SERVER_IP>:8000
npm ci
npm run build                          # -> dist/ (tĩnh)

# 2) Serve bản tĩnh ngay trên Jetson:
npm run preview -- --host 0.0.0.0 --port 4173 &

# 3) Mở toàn màn hình trên LCD robot (chế độ kiosk của Chromium):
sudo apt-get install -y chromium-browser
chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:4173
```
> **Cách gọn hơn (nếu LAN ổn):** để **server build & serve** `customer_ui` (cùng origin, khỏi CORS) →
> Jetson chỉ cần `chromium-browser --kiosk http://<SERVER_IP>:8000/`, **không cần Node trên Jetson**.
> Chi tiết build/run frontend: [frontend-customer-ui-guide.md](frontend-customer-ui-guide.md) ·
> [frontend-customer-ui-run-vi.md](frontend-customer-ui-run-vi.md).

**(6) Robot-agent WS client — gửi STT lên server · nhận text về để TTS:**

Tiến trình Python nối Jetson ↔ server: gửi `stt_text` (đã STT cục bộ) lên, nhận `say` (server/LLM
trả lời) → đọc bằng **TTS**, relay `navigate` xuống Body. Luồng đầy đủ:

```
mic → VAD → STT → WS↑ SERVER (LLM/agent) → WS↓ Jetson → TTS đọc cho khách
```

> ⚠️ **Hiện CHƯA có file `ws_client.py`** — các placeholder cũ trong `interfaces/` đều rỗng và đã được
> dọn. Đây là việc cần viết (SYSTEM_ARCHITECTURE §4 "robot-agent", §11 Mốc B). Tạm thời
> `ai_waiter_core/main.py` là pipeline voice **all-in-one cũ** (VAD+STT+agent+TTS cùng máy) để test cục bộ.

---

### 2.C — LAPTOP: theo vai đóng

Laptop x86 cài **giống lớp máy mà nó đóng vai**:

| Vai laptop đóng | Cài như | Lệnh chính |
|---|---|---|
| **Server** (LLM + backend; có thể kèm kiosk/panel dev) | mục **2.A** | `uv sync --extra server --extra cu13` + Ollama + setup.py |
| **Robot SIM** (Gazebo + voice + customer_ui) | mục **2.B** (x86: **khỏi** build ctranslate2) + ROS 2 **sim** | `uv sync --extra voice --extra cu12` + `colcon build` (common+sim) |
| **Bảng điều khiển** (panel) / **Kiosk** | trình duyệt, hoặc dev | `make panel` / `make kiosk` cục bộ, hoặc mở `http://<SERVER_IP>:8000` |

> - Laptop đóng vai Robot dùng **`sim`** (Gazebo, `src/sim`) — **khác** Jetson dùng **`real`** (`src/real`).
> - Trên **laptop x86** faster-whisper **cài thẳng từ PyPI** (không build tay như Jetson) — đã nằm trong
>   `--extra voice` với marker `x86_64`, nên `uv sync --extra voice --extra cu12` là đủ cho STT.

---

## 3. Cài theo từng BỘ (chi tiết)

### 3.Web — customer_ui · kiosk · panel (Vue 3 + Vite, Node 22)

3 frontend trong `src/frontends/`. Cổng dev cố định: customer_ui **5173**, kiosk **5174**, panel **5175**
(proxy `/api` → `:8000`, không CORS). Chi tiết: [frontend-customer-ui-guide.md](frontend-customer-ui-guide.md).

**Chạy ở đâu (deploy thật):** `customer_ui` → **mỗi Jetson robot** (production, mục 2.B-5) ·
`kiosk` → **tablet/laptop ở cổng** · `panel` → **laptop ở quầy/bếp**. Khi dev chạy `npm run dev` cả 3
trên 1 máy cũng được; hoặc để **server build & serve** cả 3 (cùng origin) nếu muốn gom 1 chỗ.

```bash
make install            # npm ci/install cho cả 3 frontend (+ uv sync gốc)
# Dev (hot-reload) — chạy cả 3:
make frontend           # menu 5173 · kiosk 5174 · panel 5175
# Prod — build tĩnh để backend serve:
make build              # -> src/frontends/customer_ui/dist/
```
> Cài 1 frontend lẻ: `cd src/frontends/<customer_ui|kiosk|panel> && npm install && npm run dev`.

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
| **L1** | Server + LLM + Kiosk | 2.A | `make backend` + Ollama; mở `/kiosk` |
| **L2** | Robot sim (Gazebo) + voice + customer_ui | 2.C-Robot + ROS 2 | `colcon` + Gazebo + bridge; mở customer_ui |
| **L3** | Bảng điều khiển | chỉ browser | mở `http://192.168.1.10:8000/panel` |

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

# Web
make frontend            # mở 5173/5174/5175
```

---

## 6. Bẫy hay gặp

- **`uv sync` trơn cài thiếu** → quên `--extra <vai>`. Server: `--extra server --extra cu13`; robot: `--extra voice`.
- **Jetson mất ctranslate2 sau `uv sync`** → luôn `uv sync --inexact`; chạy app bằng `uv run --no-sync` hoặc venv đã activate. ([jetson-ctranslate2-build.md](jetson-ctranslate2-build.md) §Gotchas).
- **TTS không kêu** → thiếu `libsndfile1`/`libportaudio2`, hoặc chưa `--extra voice` (edge-tts/sounddevice/soundfile).
- **Router accuracy 0%** → đổi `EMBEDDING_MODEL` mà quên `scripts/setup.py --embeddings-only` (centroids sai chiều).
- **App lỗi thiếu FAISS/DB** → chưa chạy `scripts/setup.py` (storage/ bị git-ignore).
- **Ollama chạy CPU trên Jetson** → cài bản prebuilt JetPack 6 ([Setup_&_Eval Guide.md §6.4](Setup_&_Eval%20Guide.md)).
