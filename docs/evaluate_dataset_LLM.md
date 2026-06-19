# AI Waiter — Eval Suite Guide

> Tài liệu này mô tả **bộ eval gồm 4 bài test** (4 "problem") cho phần "brain" của AI Waiter,
> và cách chạy trên **PC dev** lẫn **Jetson Orin**.
>
> Menu dùng để test là quán ốc/hải sản **"Ốc Quậy"** — `assets/data/menu.json` (98 món).

---

## 1. Bốn bộ eval

| # | Script | Đo cái gì | Dataset | Số case |
|---|---|---|---|---|
| 1 | `evals/scripts/eval_router.py` | Hybrid router (semantic centroid + SLM fallback) phân loại đúng intent | `evals/data/router/router_eval.json` | 45 cases |
| 2 | `evals/scripts/eval_retrieval.py` | RAG menu (BM25 + FAISS, fusion RRF) trả về món liên quan | `evals/data/retrieval/retrieval_eval.json` | 24 cases |
| 3 | `evals/scripts/eval_e2e.py` | Toàn bộ graph (router → worker → tools → response) qua hội thoại nhiều lượt | `evals/data/e2e/e2e_conversations_part1.json` + `part2.json` | 11 scenarios (6 + 5) |
| 4 | `evals/scripts/eval_out_of_menu.py` | Từ chối món **ngoài thực đơn** (Validator phát hiện + LLM không chốt đơn) | `evals/data/e2e/e2e_out_of_menu_test.json` | 4 scenarios |

Tất cả kết quả ghi vào `evals/results/` (mỗi lần chạy: 1 log `*.log` theo timestamp + 1 report JSON).
Thư mục này được tạo tự động khi chạy.

---

## 2. Cách từng eval hoạt động

### (1) `eval_router.py`
- Đọc `router_eval.json` (mỗi case có `input`, `expected_route`, `order_stage`).
- Có **warm-up run** trước để loại bias cold-start (load PyTorch + mở channel Ollama).
- Mỗi case: gọi trực tiếp `hybrid_router_node(state)`, so `current_intents` với `expected_route`.
  - `ORDER_CONFIRM` được chấp nhận khi expected là `ORDER` (cùng route tới `order_worker`).
- Output: **accuracy**, latency trung bình theo intent, và tỉ lệ quyết định bởi **SEMANTIC vs SLM**.
- Report: `evals/results/eval_router_slm_<timestamp>.json` + `.log`.

### (2) `eval_retrieval.py`
- Đọc `retrieval_eval.json` (mỗi case: `query`, `expected_relevant`, `difficulty`, `category`).
- Khởi tạo `IndexBuilder` → nếu chưa có index trong `storage/vector/` thì **tự build** FAISS + BM25 từ `assets/data/` (lần đầu chạy sẽ lâu).
- Chạy fusion mode **RRF**, lấy `k=5`.
- Tính **Precision@5, Recall@5, MRR, Hit Rate** (so theo tên món, không phân biệt hoa thường).
- Report: `evals/results/retrieval_report.json` + `retrieval_eval_<timestamp>.log`.

### (3) `eval_e2e.py`
- Đọc các file scenario trong `evals/data/e2e/`. Mỗi scenario = hội thoại nhiều lượt, mỗi lượt có khối `assert`.
- **Xoá `storage/db/checkpoints.db`** ở đầu run + warm-up agent một lần.
- Mỗi lượt chạy qua `app.stream(...)`, trích tool calls / tool outputs / response / state rồi kiểm assertion:
  - `tool_called`, `tool_must_NOT_call`, `tool_output_contains`,
    `response_contains`, `response_should_contain_one_of`,
    `confirmed_items_must_contain`, `confirmed_items_must_NOT_contain`.
- Output: **pass rate** theo scenario.
- Report: `evals/results/e2e_report.json` + `e2e_eval_<timestamp>.log`.
- **Mặc định chỉ chạy `part1`** — phải truyền `--datasets` để chạy thêm part2.

### (4) `eval_out_of_menu.py`  ← bộ thứ 4
- Đọc **cố định** `evals/data/e2e/e2e_out_of_menu_test.json` (4 scenario, **không** nhận `--datasets`).
- 4 "problem" phủ các tình huống:
  - `OOM-001` — 1 món sai + 1 món đúng → thêm món đúng, từ chối món sai, **không** `confirm_order`.
  - `OOM-002` — 1 món sai + nhiều món đúng → `sync_cart` các món đúng, nêu món thiếu, **không** chốt.
  - `OOM-003` — toàn bộ món sai → không thêm món nào, không chốt.
  - `OOM-004` — biến thể gần giống tên thật ("Bia Corona", "Lẩu Hải Sản") → test nhánh gợi ý của Validator.
- Dùng `app.invoke(...)` từng lượt, cùng bộ assertion như e2e.
- Report: `evals/results/e2e_out_of_menu_report.json` + `e2e_out_of_menu_eval_<timestamp>.log`.

---

## 3. Yêu cầu trước khi chạy (chung cho PC & Jetson)

1. **Ollama** đang chạy và đã pull model dùng cho router/worker/response:
   ```bash
   ollama serve            # nếu chưa chạy như service
   ollama pull qwen3:4b-instruct-2507-q4_K_M
   ollama list             # xác nhận model có mặt
   ```
   Model mặc định lấy từ `config/agent_config.py` (`ROUTER_MODEL`/`WORKER_MODEL`/`RESPONSE_MODEL`
   = `qwen3:4b-instruct-2507-q4_K_M`), có thể override qua `.env`.

2. **Embedding model**: `AITeamVN/Vietnamese_Embedding` (tải tự động lần đầu từ HuggingFace).
   Dùng cho cả retrieval (FAISS) lẫn semantic router. Centroid router đã build sẵn ở
   `ai_waiter_core/ai_waiter_core/agent/resources/centroids/centroids.npz`.

3. **Python env** qua `uv` (pyproject + uv.lock đã pin sẵn, Python 3.10):
   ```bash
   uv sync                 # tạo .venv với đúng dependency
   ```

4. **`.env`** (tuỳ chọn) — copy từ template rồi sửa:
   ```bash
   cp .env.template .env
   ```
   Các biến quan trọng: `DEVICE` (`cuda`/`cpu`), `ROUTER_MODEL`/`WORKER_MODEL`/`RESPONSE_MODEL`, `HF_TOKEN`.

> Các eval script tự thêm `./ai_waiter_core` vào `sys.path`, nên **không cần set `PYTHONPATH`** —
> chỉ cần chạy từ thư mục gốc repo.

---

## 4. Chạy trên PC (dev)

Từ thư mục gốc repo (`/home/ducduy/AI_Waiver`), với Ollama đang chạy:

```bash
# 1. Router
uv run python evals/scripts/eval_router.py

# 2. Retrieval (lần đầu sẽ build FAISS+BM25 từ assets/data → hơi lâu)
uv run python evals/scripts/eval_retrieval.py

# 3. E2E — chạy CẢ part1 + part2 (mặc định chỉ part1)
uv run python evals/scripts/eval_e2e.py \
    --datasets e2e_conversations_part1.json e2e_conversations_part2.json

# 4. Out-of-menu (4 problem) — không cần --datasets
uv run python evals/scripts/eval_out_of_menu.py
```

Cờ hữu ích của `eval_e2e.py`:
- `--limit N` — chỉ chạy N scenario đầu (debug nhanh).
- `--datasets <file...>` — chọn dataset cụ thể, ví dụ chỉ part2: `--datasets e2e_conversations_part2.json`.

---

## 5. Chạy trên Jetson Orin (8GB unified memory)

Code chạy y hệt PC, khác biệt nằm ở **ngân sách bộ nhớ** và **device**. Jetson chia sẻ chung
8GB LPDDR5 cho cả CPU lẫn GPU.

### 5.1. Chuẩn bị
```bash
# uv cho aarch64
curl -LsSf https://astral.sh/uv/install.sh | sh

# Ollama (bản aarch64/Jetson) + model lượng tử hoá nhẹ
ollama pull qwen3:4b-instruct-2507-q4_K_M     # ~2.5GB resident (~3.5GB khi load ctx)

uv sync
cp .env.template .env
```

### 5.2. `.env` cho Jetson
```dotenv
DEVICE=cuda                                   # dùng GPU Jetson cho embedding (sentence-transformers)
ROUTER_MODEL=qwen3:4b-instruct-2507-q4_K_M
WORKER_MODEL=qwen3:4b-instruct-2507-q4_K_M
RESPONSE_MODEL=qwen3:4b-instruct-2507-q4_K_M
```
- **Một model Ollama duy nhất** cho cả router/worker/response → Ollama chỉ giữ ~3.5GB thay vì nạp nhiều model.
- Embedding `AITeamVN/Vietnamese_Embedding` được dùng chung qua singleton (≈2GB).
- Ngân sách ước tính: LLM ~3.5GB + embedding ~2GB + (STT ~1GB nếu có) + OS/ROS ~1.5GB ≈ **vừa khít 8GB nhưng sát**.

### 5.3. Chạy (giống PC)
```bash
uv run python evals/scripts/eval_router.py
uv run python evals/scripts/eval_retrieval.py
uv run python evals/scripts/eval_e2e.py --datasets e2e_conversations_part1.json e2e_conversations_part2.json
uv run python evals/scripts/eval_out_of_menu.py
```

### 5.4. Nếu thiếu RAM / OOM trên Jetson — các "cần gạt" để giảm bộ nhớ
- Giảm context của ChatOllama: `num_ctx` 4096 → 2048.
- STT (nếu chạy chung): ép `compute_type=int8`.
- Hạ model: fallback `qwen2.5:3b` (nhẹ hơn nhưng kém hơn).
- Đặt Jetson ở chế độ công suất tối đa: `sudo nvpmodel -m 0 && sudo jetson_clocks`.
- Chạy **lần lượt từng eval** (đừng song song) để tránh đỉnh bộ nhớ cộng dồn.

---

## 6. Đọc kết quả

| File trong `evals/results/` | Nội dung |
|---|---|
| `eval_router_slm_<ts>.json` / `.log` | accuracy, latency/intent, SEMANTIC vs SLM split |
| `retrieval_report.json` / `retrieval_eval_<ts>.log` | Precision@5, Recall@5, MRR, Hit Rate (mode RRF) |
| `e2e_report.json` / `e2e_eval_<ts>.log` | pass rate + chi tiết từng lượt (tool calls, state, assertion) |
| `e2e_out_of_menu_report.json` / `e2e_out_of_menu_eval_<ts>.log` | pass rate 4 scenario từ chối món ngoài menu |

Log liệt kê từng case PASS/FAIL kèm lý do (intent dự đoán, tool gọi sai, response thiếu từ khoá…),
dùng để soi chỗ hệ thống thực sự fail.
