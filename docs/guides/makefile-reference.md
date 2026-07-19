# Makefile — tra cứu các lệnh & tham số

> Giải thích từng `make <target>` trong [Makefile](../Makefile): làm gì, chạy trên máy nào, và các
> biến (`UV_EXTRAS`, `ID`, `ARGS`) truyền vào ra sao. Bối cảnh deploy: **server lo não + web**,
> **Jetson/laptop lo voice** ([setup-deploy.md](setup-deploy.md), [run-voice-vi.md](run-voice-vi.md)).

## Biến truyền vào (override khi gọi `make`)

| Biến | Mặc định | Dùng cho | Ví dụ |
|---|---|---|---|
| `UV_EXTRAS` | *(rỗng)* | `make install` — chọn **vai trò** Python (extras trong `pyproject.toml`) | `make install UV_EXTRAS="--extra server --extra cu13"` |
| `ID` | `robo-1` | `make mockrobot` — id robot giả | `make mockrobot ID=robo-2` |
| `ARGS` | *(rỗng)* | `make mockrobot` — cờ thêm cho mock robot | `make mockrobot ARGS="--x 2.3 --y 0.5"` |

> ⚠️ `uv sync` **trơn** (không `--extra`) chỉ cài *base nhỏ*. Backend/voice **bắt buộc** truyền
> `UV_EXTRAS` đúng vai, nếu không sẽ thiếu `uvicorn`/`torch`/… → `Failed to spawn: uvicorn`.

### Giá trị `UV_EXTRAS` theo máy

| Máy | `UV_EXTRAS` |
|---|---|
| **Server** (x86, CUDA 13) — não + RAG + backend + web | `--extra server --extra cu13` |
| Laptop GPU đời cũ (CUDA 12) làm **cả** não lẫn voice | `--extra server --extra voice --extra cu12` |
| Laptop đóng vai **robot** (voice, CUDA 12, có mic) | `--extra voice --extra cu12` |
| **Jetson** thật (aarch64, CUDA 12.6, voice) | `--extra voice` — **không** cu12/cu13 (đó là selector x86); torch **2.11.0 cu126** tự kéo từ index `jetson-ai-lab` (khai báo trong `pyproject.toml`). **Dùng `uv sync --extra voice` thẳng**, không `make install` (Jetson không có Node). |

---

## Các target

### Cài đặt / cập nhật

| Target | Làm gì | Máy |
|---|---|---|
| `make setup` | Cài môi trường lần đầu (nvm + Node 22 + uv) qua `setup.sh`. **Chỉ** cài deps cho `customer_ui` — vẫn phải chạy `make install` sau đó. | máy DEV / server (có Node) |
| `make install` | `npm ci`/`install` cho **3 web** (customer_ui, kiosk, panel) + `uv sync --inexact $(UV_EXTRAS)` cho Python. `--inexact` = giữ extras đã cài, không prune. | server / dev. **KHÔNG dùng trên Jetson** (không có Node → `npm ci` lỗi; cài `uv sync --extra voice` thẳng). |
| `make update` | `git pull` rồi `make install`. | server / dev |
| `make clean` | Xoá `node_modules` của 3 web + `.venv`. Cài lại bằng `make install`. | bất kỳ |

### Web (frontend)

| Target | Làm gì | Cổng |
|---|---|---|
| `make menu` | Dev server `customer_ui` (màn đặt món của khách). | 5173 |
| `make kiosk` | Dev server kiosk (check-in, seat bàn → `POST /seatings`). | 5174 |
| `make panel` | Dev server panel bếp (đơn + fleet + nút **Reset hệ thống**). | 5175 |
| `make frontend` | Chạy **cả 3** web cùng lúc; Ctrl-C tắt hết. | 5173-5175 |
| `make build` | Build production `customer_ui` → `dist/`. | — |
| `make serve` | Serve bản production (`vite preview`). | 4173 |

### Backend / Agent (Python)

| Target | Làm gì | Cổng | Máy |
|---|---|---|---|
| `make backend` | Uvicorn orchestrator (REST + `/voice` bridge + WS hub), `--reload`. | 8000 | server |
| `make reindex` | **Xoá sạch** `storage/vector/` (FAISS + BM25) + `centroids.npz`, rồi `scripts/setup.py --force` build lại FAISS + BM25 + centroids theo `EMBEDDING_MODEL` trong `.env`. **`--force` wipe luôn `checkpoints.db`** (bộ nhớ hội thoại); **không** đụng `orchestrator.db`. | — | server |
| `make agent` | Chạy `reindex` trước (rebuild embeddings sạch), rồi uvicorn **agent service** (LLM, `POST /chat`). Chạy từ repo root. | 8100 | server |

> Restart agent **không** rebuild (sau khi đã build xong): chạy thẳng, đừng `make agent`:
> ```bash
> uv run uvicorn src.agent_brain.server:app --host 0.0.0.0 --port 8100
> ```

### Tiện ích demo

| Target | Làm gì | Máy |
|---|---|---|
| `make mockrobot` | Robot giả nối WS để test dispatcher. `ID=` đổi id, `ARGS=` thêm cờ (`--x --y`). | bất kỳ |
| `make reset` | `POST /admin/reset` (backend phải đang chạy): xoá *dữ liệu* đơn/lượt ngồi/thanh toán/task, bàn về `TRONG`, reseed robot. **Không xoá file `.db`** — giống bấm nút "↺ Reset hệ thống" trên panel. | bất kỳ (gọi tới server) |
| `make kill` | Dừng dev server đang chạy (cổng 8000, 5173-5175). | máy đang chạy |

---

## Lưu ý quan trọng

- **`make agent` ≠ toàn bộ setup.** Nó lo FAISS + agent, nhưng **không** cài Ollama / `ollama pull`
  model / tạo `.env`. Làm các bước đó trước (xem [run-voice-vi.md](run-voice-vi.md) §2).
- **Xoá DB:**
  - `checkpoints.db` (memory hội thoại) → `make reindex`/`make agent` (qua `--force`).
  - `orchestrator.db` (ledger) → nút **Reset hệ thống** trên panel / `make reset` (xoá dữ liệu), hoặc
    `rm storage/db/orchestrator.db` (xoá hẳn file, backend seed lại khi khởi động).
- **Vòng lặp voice** — `make voice` (chạy từ repo root; khởi động `src/edge_voice/main.py`):
  ```bash
  make voice    # = .venv/bin/python src/edge_voice/main.py — cố ý KHÔNG qua `uv run`
  make probe    # chỉ mic -> VAD -> Whisper, in text ra màn hình (không cần server)
  ```
  Hai target này là target **duy nhất** chạy được trên Jetson: chúng gọi thẳng interpreter
  trong `.venv`, không sync env, nên không gỡ mất `ctranslate2`/`faster-whisper` build tay.
  Các target còn lại (`backend`, `agent`, `install`…) vẫn dùng `uv run` → chỉ dành cho server.
