# Chạy hệ thống Voice + LLM + Web UI

> Hướng dẫn chạy luồng **voice → LLM → web UI** sau khi tách kiến trúc (2026-06):
> **bộ não (LLM) ở SERVER**, **thân xác (mic/STT/TTS) ở JETSON/laptop**. Web UI chỉ *mirror*
> hội thoại, không thu mic. Tài liệu kiến trúc: [code-architecture.md](code-architecture.md) §6.

## 1. Bức tranh tổng thể

```
JETSON / LAPTOP (thân xác)                 SERVER (bộ não, Netbird 100.x.x.x)
mic(USB) → VAD → Whisper → text                  Ollama (LLM)
                  │                                  │
                  └── POST /chat ──────────► agent service (:8100, make agent)
                                                  │  ├─ POST /voice/event {heard}
   loa(BT) ◄── TTS đọc reply ◄── reply ───────────┤  └─ POST /voice/event {reply, action}
                                                  ▼
                                          backend (:8000, make backend)
                                          broadcast role=customer
                                                  │
                                                  ▼
                                          customer_ui (:5173, make menu)
                                          ← mở trên browser laptop qua Netbird
```

**3 thứ chạy trên SERVER:** `make backend` + `make agent` + `make menu` (và **Ollama**).
**1 thứ chạy trên JETSON/laptop:** vòng lặp voice `ai_waiter_core/main.py`.

| Máy | Vai trò | Chạy | Extra cài |
|---|---|---|---|
| **SERVER** (x86, Blackwell/driver ≥580) | LLM + ledger + web | Ollama, `make backend`, `make agent`, `make menu` | `--extra server --extra cu13` |
| **LAPTOP** (x86, CUDA 12, có mic) | đóng vai Jetson | `main.py` (voice) | `--extra voice --extra cu12` |
| **JETSON** thật (aarch64, có mic) | thân xác | `main.py` (voice) | `--extra voice` (+ build tay ctranslate2) |

> CUDA & torch theo máy: **Server PC mới = CUDA 13 → `cu13`** (torch ≥2.12, PyPI); laptop GPU đời cũ
> = CUDA 12 → `cu12` (torch cu121). **Jetson = CUDA 12.6** (JetPack 6.2) → torch **2.11.0 cu126** lấy
> từ index `jetson-ai-lab` — **tự động** theo marker `aarch64` trong `pyproject.toml`
> (`[tool.uv.sources]`/`[[tool.uv.index]]`), nên Jetson **không** truyền `cu12/cu13` (đó là selector của
> x86). Tức Jetson vẫn cần torch khớp CUDA, chỉ là chọn tự động. Chi tiết: [setup-deploy.md](setup-deploy.md) §1.1.
>
> ⚠️ `make install` còn chạy `npm ci` cho 3 web → **trên Jetson (không có Node) sẽ lỗi**. Máy
> voice-only nên cài thẳng `uv sync --extra voice` thay vì `make install`. Và `make install` **không**
> lo: cài Ollama + `ollama pull`, tạo `.env`, build ctranslate2 (Jetson) — xem các mục bên dưới.

> LLM (`langgraph`/`langchain-ollama`) nằm trong extra **`server`** → máy voice **không** load LLM,
> chỉ Whisper + VAD + TTS. Đó là mục đích của việc tách.

---

## 2. SERVER — cài & chuẩn bị (làm 1 lần)

```bash
git pull                                              # lấy code mới
make install UV_EXTRAS="--extra server --extra cu13"  # Server PC mới = CUDA 13

# Ollama: phải chạy + pull đúng model trong .env
ollama serve &
ollama pull <model-ollama>        # khớp ROUTER_MODEL / WORKER_MODEL / RESPONSE_MODEL
```

`.env` (gốc repo, trên server) — model LLM + embedding muốn test:
```bash
ROUTER_MODEL=<model-ollama>
WORKER_MODEL=<model-ollama>
RESPONSE_MODEL=<model-ollama>
EMBEDDING_MODEL=<model-embedding>     # để trống = mặc định AITeamVN/Vietnamese_Embedding (~2.2GB)
# ORCHESTRATOR_URL mặc định http://localhost:8000 (agent gọi backend cùng máy) — không cần sửa
```

## 3. SERVER — chạy (3 terminal / tmux)

```bash
make backend     # T1: orchestrator + /voice bridge        :8000
make agent       # T2: rebuild embeddings (sạch) → LLM      :8100
make menu        # T3: customer_ui (web)                    :5173
```

### `make agent` làm gì?
Mỗi lần chạy nó **rebuild sạch embedding trước** rồi mới serve (để test model mới):
```
reindex: xoá storage/vector/ + centroids.npz  →  scripts/setup.py --force
         (rebuild FAISS + BM25 + centroids theo EMBEDDING_MODEL; wipe checkpoints.db)
agent:   uvicorn ai_waiter_core.server:app :8100
```
- ⚠️ `--force` **wipe cả `checkpoints.db`** (bộ nhớ hội thoại) nhưng **không** đụng `orchestrator.db`.
  Muốn reset ledger (đơn/lượt ngồi/thanh toán) có 3 cách, đều OK:
  - Bấm nút **"↺ Reset hệ thống"** trên **panel** (bếp) — gọi `POST /admin/reset`, xoá sạch *dữ liệu bên
    trong* DB (không xoá file), bàn về `TRONG`, reseed robot.
  - `make reset` (backend đang chạy) — y hệt nút trên panel (cùng endpoint).
  - `rm storage/db/orchestrator.db` — xoá hẳn file; backend tự seed lại khi khởi động.
- Lần đầu sẽ tải model embedding về (vài trăm MB–2GB) → hơi lâu, bình thường.
- **Restart agent KHÔNG rebuild** (sau khi đã build): chạy thẳng, đừng `make agent`:
  ```bash
  cd ai_waiter_core && uv run --project .. uvicorn ai_waiter_core.server:app --host 0.0.0.0 --port 8100
  ```
- Khởi động xong in `Agent ready.`

---

## 4. LAPTOP (CUDA 12, có mic) — đóng vai Jetson

```bash
git pull
make install UV_EXTRAS="--extra voice --extra cu12"
```

`.env` (gốc repo, trên laptop) — trỏ agent về SERVER qua Netbird:
```bash
AGENT_URL=http://100.x.x.x:8100      # ← IP Netbird của SERVER
ROUTER_MODEL=<model-ollama>          # (không bắt buộc trên laptop, nhưng để khớp cho gọn)
WORKER_MODEL=<model-ollama>
RESPONSE_MODEL=<model-ollama>
```

Chạy vòng lặp voice:
```bash
cd ai_waiter_core && uv run python main.py
```
In ra:
```
AI Waiter ready — Table T1
Agent (LLM) @ http://100.x.x.x:8100
Speak in Vietnamese to order...
```

> **TTS dùng `edge-tts` (cloud)** → laptop cần internet để phát tiếng ra loa.

---

## 5. JETSON thật (aarch64, có mic) — khác laptop ở đâu

```bash
# (a) system libs cho audio (mic/loa)
sudo apt-get install -y portaudio19-dev libsndfile1 libportaudio2

# (b) Python env — cài THẲNG, KHÔNG dùng make install (Jetson không Node → npm ci lỗi).
#     KHÔNG cu12/cu13 (đó là selector x86). torch 2.11.0 cu126 (CUDA 12.6) tự kéo từ index
#     jetson-ai-lab — khai báo sẵn trong pyproject.toml ([tool.uv.sources]/[[tool.uv.index]]).
uv sync --extra voice
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"   # mong: 2.11.0 True
# Nếu lỗi libcudss.so.0:  sudo apt-get install -y libcudss0-cuda-12
```
- Phải **build tay `ctranslate2`/`faster-whisper`** (wheel PyPI thiếu C++ runtime trên aarch64):
  xem [jetson-ctranslate2-build.md](jetson-ctranslate2-build.md). Sau đó luôn `uv sync --inexact` /
  `uv run --no-sync` để không bị xoá bản build tay.
- **Không cài LLM/RAG/embedding** ở đây → `.env` Jetson **chỉ cần `AGENT_URL`** (trỏ về server). Không
  cần `EMBEDDING_DEVICE`, không cần `*_MODEL` (mấy cái đó của agent trên server).
  > (Comment "Jetson set EMBEDDING_DEVICE=cpu" trong `.env.template` là của thời pre-pivot, giờ đã stale.)
- Phần còn lại (`main.py`, `AGENT_URL`) y hệt mục 4.

---

## 6. Mở web & nói thử

1. Browser trên laptop → **`http://100.x.x.x:5173`** (frontend ở server, qua Netbird).
   Vite tự proxy `/api` + `/ws` về backend `:8000` ở server → không dính CORS.
2. Bàn mặc định web = **bàn 1**, voice loop = **T1** → khớp sẵn.
3. Nói tiếng Việt vào mic → Whisper (máy voice) → `/chat` (LLM server) → **loa đọc trả lời**
   đồng thời **panel AI trên web bật lên**, hiện hội thoại, tự nhảy `/menu` hoặc `/payment` theo ý định.

> **Muốn đặt món / thanh toán thật** thì bàn 1 phải được *seat* trước:
> `make kiosk` (:5174) chọn bàn, hoặc nhanh:
> ```bash
> curl -X POST http://100.x.x.x:8000/seatings -H 'Content-Type: application/json' \
>      -d '{"table_id":1,"party_size":2}'
> ```
> Chỉ "hỏi gợi ý món" thì không cần seat.

---

## 7. Gỡ rối nhanh

| Triệu chứng | Xử lý |
|---|---|
| `Failed to spawn: uvicorn` khi `make backend`/`make agent` | Thiếu extra `server`. Cài lại: `make install UV_EXTRAS="--extra server --extra cu13"` (server CUDA 13) |
| `main.py` báo `Agent request failed` | Agent service `:8100` chưa chạy, hoặc `AGENT_URL` sai IP Netbird, hoặc Netbird chưa mở port 8100 |
| Agent log: lỗi gọi Ollama / model not found | Chưa `ollama serve` hoặc chưa `ollama pull <model>` đúng tên trong `.env` |
| Browser vào `:5173` báo *"host not allowed"* | Thêm `allowedHosts: true` vào khối `server` trong `customer_ui/vite.config.ts` |
| Web không hiện hội thoại khi nói | Kiểm tra bàn web = bàn 1 (khớp `TABLE_ID=T1`); xem Network tab có WS `/ws?role=customer` connected không |
| Voice không nghe / không ra tiếng | mic USB chưa nhận (laptop), hoặc TTS `edge-tts` thiếu internet |
| FAISS index lỗi đọc | Chạy `make reindex` (hoặc `make agent`) để build lại |

## 8. Cổng dùng

| Cổng | Dịch vụ | Máy |
|---|---|---|
| 8000 | backend (REST + /voice + WS) | server |
| 8100 | agent service (LLM, `/chat`) | server |
| 5173 | customer_ui (web) | server |
| 5174 | kiosk (seat bàn) | server (tuỳ chọn) |
| 5175 | panel (bếp) | server (tuỳ chọn) |
