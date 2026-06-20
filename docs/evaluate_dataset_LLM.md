# AI Waiter — Setup & Eval Guide (Dev x86 + Jetson Orin)

> Tài liệu gộp: **(A)** cách dựng môi trường Python (uv/torch) trên Dev x86 & Jetson,
> **(B)** bộ eval gồm **4 bài test** cho phần "brain" của AI Waiter, và cách chạy + đọc kết quả.
>
> Menu dùng để test: quán ốc/hải sản **"Ốc Quậy"** — `assets/data/menu.json` (217 món).

---

## 1. Môi trường Python (uv + torch theo kiến trúc)

Project dùng [uv](https://docs.astral.sh/uv/) quản lý môi trường Python (LLM, RAG, embeddings).
**torch chạy 2 loại máy với CUDA khác nhau**, `pyproject.toml` đã cấu hình lấy torch/torchvision
theo từng kiến trúc — bạn **không cần chỉnh gì**, chỉ `uv sync`.

| Máy | Kiến trúc | GPU | torch | Nguồn | CUDA |
|---|---|---|---|---|---|
| Dev | x86_64 | RTX 5060 Ti (Blackwell, sm_120) | `2.12.x` | PyPI | cu13 (13.0) |
| Deploy | aarch64 | Jetson Orin | `2.11.0` | index jetson-ai-lab | cu126 (12.6) |

### 1.1. Dev x86_64 (RTX 5060 Ti)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # lần đầu nếu chưa có uv
uv sync
uv run python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
# Mong đợi: 2.12.1+cu130 13.0 True   (driver phải hỗ trợ CUDA 13 cho Blackwell sm_120)
```

### 1.2. Jetson Orin (aarch64, JetPack 6 / CUDA 12.6)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git pull
uv sync     # uv tự kéo torch 2.11.0 cu126 (GPU) từ index jetson-ai-lab
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# Mong đợi: 2.11.0 True
```
Nếu lỗi `libcudss.so.0: cannot open shared object file`:
```bash
sudo apt-get install -y libcudss0-cuda-12
```

### 1.3. Lưu ý torch / pyproject
- **KHÔNG** `uv pip install torch ...` thủ công trên Jetson — `uv sync` đã lo; cài tay sẽ bị đồng bộ lại.
- **KHÔNG** cần `--no-sync` / `--inexact` / `--no-install-package torch`.
- torch 2 máy **khác version là cố ý** (cu13 cho Blackwell vs cu126 cho Jetson), không phải lỗi.
- Cách hoạt động (tham khảo `pyproject.toml`): cần (1) torch/torchvision khai báo **trực tiếp** trong
  `dependencies`, (2) URL index có đuôi `/+simple/`, (3) khai báo `environments` cho cả 2 kiến trúc;
  `[tool.uv.sources]` chỉ trỏ aarch64 sang index `jetson-cu126`.

---

## 2. Yêu cầu runtime (chung PC & Jetson)

1. **Ollama** đang chạy + đã pull model:
   ```bash
   ollama serve                                   # nếu chưa chạy như service
   ollama pull qwen3:4b-instruct-2507-q4_K_M
   ollama list
   ```
   Cả router/worker/response dùng **một model duy nhất** (`config/agent_config.py`), override qua `.env`.

2. **Embedding** `AITeamVN/Vietnamese_Embedding` (BGE-M3) — tải tự động lần đầu từ HuggingFace, dùng
   chung cho retrieval (FAISS) lẫn semantic router qua singleton; đã load **fp16** (~1.1GB). Centroid
   router build sẵn ở `ai_waiter_core/.../agent/resources/centroids/centroids.npz`.

3. **Python env**: `uv sync` (mục 1).

4. **`.env`** (tuỳ chọn): `cp .env.template .env`. Biến quan trọng:
   `DEVICE` (`cuda`/`cpu`), `ROUTER_MODEL`/`WORKER_MODEL`/`RESPONSE_MODEL`, `LLM_NUM_CTX`, `HF_TOKEN`.

> Eval script tự thêm `./ai_waiter_core` vào `sys.path` → **không cần set `PYTHONPATH`**, chỉ chạy từ gốc repo.

---

## 3. Bốn bộ eval

| # | Script | Đo cái gì | Dataset | Số case |
|---|---|---|---|---|
| 1 | `evals/scripts/eval_router.py` | Hybrid router (semantic centroid + SLM fallback) phân loại intent | `evals/data/router/router_eval.json` | 45 cases |
| 2 | `evals/scripts/eval_retrieval.py` | RAG menu (BM25 + FAISS, fusion RRF) trả món liên quan | `evals/data/retrieval/retrieval_eval.json` | 24 cases |
| 3 | `evals/scripts/eval_e2e.py` | Toàn graph (router → worker → tools → response) qua hội thoại nhiều lượt | `e2e_conversations_part1.json` + `part2.json` | 11 scenarios (6 + 5) |
| 4 | `evals/scripts/eval_out_of_menu.py` | Từ chối món **ngoài thực đơn** / xử món **mơ hồ** | `e2e_out_of_menu_test.json` | 4 scenarios |

Kết quả ghi vào `evals/results/` (mỗi run: 1 log `*.log` theo timestamp + 1 report JSON; thư mục tự tạo).

---

## 4. Cách từng eval hoạt động

### (1) `eval_router.py`
- Đọc `router_eval.json` (`input`, `expected_route`, `order_stage`). Có **warm-up** loại bias cold-start.
- Mỗi case gọi `hybrid_router_node(state)`, so `current_intents` với `expected_route`
  (`ORDER_CONFIRM` chấp nhận khi expected là `ORDER` — cùng route tới `order_worker`).
- Output: **accuracy**, latency/intent, tỉ lệ quyết định bởi **SEMANTIC vs SLM**.

### (2) `eval_retrieval.py`
- Đọc `retrieval_eval.json` (`query`, `expected_relevant`, `difficulty`, `category`).
- `IndexBuilder` tự build FAISS + BM25 từ `assets/data/` nếu chưa có trong `storage/vector/` (lần đầu lâu).
- Fusion **RRF**, `k=5` → **Precision@5, Recall@5, MRR, Hit Rate** (so theo tên món, không phân biệt hoa thường).

### (3) `eval_e2e.py`
- Đọc scenario trong `evals/data/e2e/`. Mỗi scenario = hội thoại nhiều lượt, mỗi lượt có khối `assert`.
- Đầu run **xoá `storage/db/checkpoints.db`** + **reset các bảng giao dịch trong `storage/db/restaurant.db`**
  (sessions/orders/order_items/payments) để cô lập test (tránh đơn dồn qua các run), rồi warm-up agent.
- Mỗi lượt chạy `app.stream(...)`, trích tool calls / outputs / response / state rồi kiểm assertion:
  `tool_called`, `tool_must_NOT_call`, `tool_output_contains`, `response_contains`,
  `response_should_contain_one_of`, `confirmed_items_must_contain`, `confirmed_items_must_NOT_contain`.
- Output: **pass rate** theo scenario. **Mặc định chỉ chạy `part1`** — phải truyền `--datasets` để thêm part2.

### (4) `eval_out_of_menu.py`
- Đọc **cố định** `e2e_out_of_menu_test.json` (4 scenario, **không** nhận `--datasets`):
  - `OOM-001` — 1 món sai + 1 món đúng → thêm món đúng, từ chối món sai, **không** `confirm_order`.
  - `OOM-002` — 1 món sai + nhiều món đúng (có cả món **mơ hồ** kiểu "Ốc Hương") → `sync_cart` món đúng,
    nêu món thiếu, **hỏi lại** loại nào cho món mơ hồ, **không** chốt.
  - `OOM-003` — toàn bộ món sai → không thêm món nào, không chốt.
  - `OOM-004` — biến thể gần giống tên thật ("Bia Corona", "Lẩu Hải Sản") → test nhánh gợi ý của Validator.
- Dùng `app.invoke(...)` từng lượt, cùng bộ assertion như e2e.

---

## 5. Chạy trên PC (dev)

Từ gốc repo (`/home/ducduy/AI_Waiver`), Ollama đang chạy:
```bash
uv run python evals/scripts/eval_router.py
uv run python evals/scripts/eval_retrieval.py     # lần đầu build FAISS+BM25 → hơi lâu
uv run python evals/scripts/eval_e2e.py \
    --datasets e2e_conversations_part1.json e2e_conversations_part2.json
uv run python evals/scripts/eval_out_of_menu.py
```
Cờ `eval_e2e.py`: `--limit N` (chỉ N scenario đầu), `--datasets <file...>` (chọn dataset cụ thể).

Tạo file review Q&A dễ đọc từ các report:
```bash
uv run python evals/scripts/build_review.py        # -> evals/results/e2e_review.md
```

---

## 6. Chạy trên Jetson Orin (8GB unified) — kèm tối ưu RAM

Code chạy y hệt PC; khác ở **ngân sách bộ nhớ**: Jetson chia chung 8GB LPDDR5 cho CPU + GPU,
nếu không tinh chỉnh dễ tràn swap.

### 6.1. `.env` cho Jetson
```dotenv
DEVICE=cuda
ROUTER_MODEL=qwen3:4b-instruct-2507-q4_K_M
WORKER_MODEL=qwen3:4b-instruct-2507-q4_K_M
RESPONSE_MODEL=qwen3:4b-instruct-2507-q4_K_M
LLM_NUM_CTX=6144        # context pin cho mọi lời gọi Ollama (hạ xuống 4096 nếu cần tiết kiệm thêm)
```
Ngân sách ước tính: LLM qwen3:4b q4 ~2.5GB (weights) + KV cache (theo `num_ctx`) + embedding fp16 ~1.1GB
+ torch/CUDA runtime + OS ≈ **sát 8GB** → cần các bước dưới.

### 6.2. `num_ctx` đã pin sẵn trong code
Mọi ChatOllama dùng `settings.LLM_NUM_CTX` (mặc định **6144**). qwen3:4b hỗ trợ tới 262144 token; để
Ollama tự quyết thì KV cache có thể rất lớn. Một giá trị **đồng nhất** cũng tránh Ollama nạp lại model
giữa các node.

### 6.3. Cấu hình Ollama service (env override) — lever lớn nhất
```bash
sudo systemctl edit ollama
```
```ini
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"        # kiosk tuần tự → KHÔNG nhân KV cache (nghi can chính gây tràn swap)
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"    # KV cache 8-bit → giảm ~nửa (cần FLASH_ATTENTION=1)
Environment="OLLAMA_KEEP_ALIVE=-1"         # giữ model thường trú, tránh reload
```
```bash
sudo systemctl restart ollama
```

### 6.4. Kiểm chứng + các "cần gạt" thêm
```bash
ollama ps        # sau 1 request: xem CONTEXT + SIZE model chiếm thực tế
tegrastats       # RAM/SWAP realtime
free -h
```
- Nếu `ollama ps` báo context > 6144 → pin `num_ctx` đang cắt thật.
- Đặt công suất tối đa: `sudo nvpmodel -m 0 && sudo jetson_clocks`.
- Chạy **lần lượt từng eval** (đừng song song) để tránh đỉnh bộ nhớ cộng dồn.
- Vẫn thiếu: chạy headless `sudo systemctl set-default multi-user.target` (tiết kiệm 1–2GB);
  hạ `LLM_NUM_CTX=4096`; hoặc đổi embedding nhỏ hơn (chạy lại `eval_retrieval` để cân chất lượng).

### 6.5. Chạy (giống PC)
```bash
uv run python evals/scripts/eval_router.py
uv run python evals/scripts/eval_retrieval.py
uv run python evals/scripts/eval_e2e.py --datasets e2e_conversations_part1.json e2e_conversations_part2.json
uv run python evals/scripts/eval_out_of_menu.py
```

---

## 7. Đọc kết quả

| File trong `evals/results/` | Nội dung |
|---|---|
| `eval_router_slm_<ts>.json` / `.log` | accuracy, latency/intent, SEMANTIC vs SLM split |
| `retrieval_report.json` / `retrieval_eval_<ts>.log` | Precision@5, Recall@5, MRR, Hit Rate (mode RRF) |
| `e2e_report.json` / `e2e_eval_<ts>.log` | pass rate + chi tiết từng lượt (tool calls, state, assertion) |
| `e2e_out_of_menu_report.json` / `e2e_out_of_menu_eval_<ts>.log` | pass rate 4 scenario ngoài menu / mơ hồ |
| `e2e_review.md` | Q&A dễ đọc (input khách + tool + câu AI + assertion), sinh bởi `build_review.py` |

Log liệt kê từng case PASS/FAIL kèm lý do (intent dự đoán, tool gọi sai, response thiếu từ khoá…),
dùng để soi chỗ hệ thống thực sự fail.
