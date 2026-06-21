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
   > Trên **Jetson**, bản cài bằng script `curl ... | sh` thường không nhận iGPU → CPU-only. Dùng bản
   > **prebuilt JetPack 6** chính thức (có CUDA cho Tegra) để chạy GPU — lệnh cài ở **6.4**.

2. **Embedding** mặc định `AITeamVN/Vietnamese_Embedding` (BGE-M3) — tải tự động lần đầu từ HuggingFace,
   dùng chung cho retrieval (FAISS) lẫn semantic router qua singleton. Device điều khiển bởi
   `EMBEDDING_DEVICE` (trống = theo `DEVICE`; `cuda` → fp16 ~1.1GB, `cpu` → fp32). Đổi model qua
   `EMBEDDING_MODEL` (xem 6.6). Centroid router build sẵn ở
   `ai_waiter_core/.../agent/resources/centroids/centroids.npz`.

3. **Python env**: `uv sync` (mục 1).

4. **`.env`** (tuỳ chọn): `cp .env.template .env`. Biến quan trọng:
   `DEVICE` (`cuda`/`cpu`), `EMBEDDING_DEVICE`, `EMBEDDING_MODEL`,
   `ROUTER_MODEL`/`WORKER_MODEL`/`RESPONSE_MODEL`, `LLM_NUM_CTX`, `HF_TOKEN`.

> Eval script tự thêm `./ai_waiter_core` vào `sys.path` → **không cần set `PYTHONPATH`**, chỉ chạy từ gốc repo.

### 2.1. Khởi tạo lần đầu sau khi clone (dựng `storage/`)

`storage/` bị **git-ignore toàn bộ** → các artifact sau **không** lên GitHub, máy mới (Jetson) sẽ thiếu ngay sau `git clone`:

- `storage/db/*.db` — SQLite (`restaurant` / `orchestrator` / `checkpoints`)
- `storage/vector/faiss_index/` — FAISS index (vector của menu)
- `storage/vector/bm25.pkl` — BM25 index

> Riêng `centroids.npz` **có** trong git (nằm ở `ai_waiter_core/.../agent/resources/centroids/`, không thuộc `storage/`) nên đi theo repo.

Vì vậy **mỗi lần clone mới phải dựng lại `storage/` một lần**:

```bash
git clone <repo> && cd AI_Waiver
uv sync                                     # mục 1 (torch theo kiến trúc)
cp .env.template .env                       # chỉnh DEVICE/EMBEDDING_DEVICE... (Jetson: xem 6.1)
ollama pull qwen3:4b-instruct-2507-q4_K_M   # mục 2
uv run python scripts/setup.py              # ← dựng storage/: DB + FAISS + BM25 (+ centroids nếu thiếu)
```

> ⚠️ `./setup.sh` / `make setup` **không** gọi `scripts/setup.py` — chúng chỉ cài node/uv + frontend.
> Phải chạy `scripts/setup.py` bằng tay, nếu không app sẽ thiếu FAISS/DB và lỗi khi khởi động.

### 2.2. Khi nào cần build lại

**3 lệnh, khác nhau ở chỗ build lại cái gì** (✓ = build lại / dựng, – = giữ nguyên, *skip nếu có* = chỉ build khi file chưa tồn tại):

| Lệnh | Restaurant DB | Checkpoints DB | FAISS + BM25 | Centroids |
|---|---|---|---|---|
| `setup.py` | tạo nếu chưa có | tạo nếu chưa có | *skip nếu có* | *skip nếu có* |
| `setup.py --embeddings-only` | – | – | ✓ luôn | ✓ luôn |
| `setup.py --force` | ✓ xoá + dựng lại | ✓ xoá + dựng lại | ✓ luôn | ✓ luôn |

**Dùng lệnh nào theo việc bạn vừa làm:**

| Thay đổi gì | Lệnh nên dùng |
|---|---|
| Clone mới / mất `storage/` | `uv run python scripts/setup.py` |
| Đổi **embedding model** (`EMBEDDING_MODEL`) | `uv run python scripts/setup.py --embeddings-only` → xem **6.6** |
| Đổi **menu data** (`menu.json`, `best_seller`, `discounts`…) | `uv run python scripts/setup.py --force` |
| Không chắc / muốn reset sạch | `uv run python scripts/setup.py --force` |

> #### ⚠️ Cái bẫy hay gặp nhất: centroids không khớp model
> `centroids.npz` **nằm trong git** (không thuộc `storage/`) nên **luôn đi theo repo** — máy mới clone về
> là đã có sẵn. Nhưng nó **gắn cứng với embedding model lúc build** (số chiều vector: BGE-M3 = 1024,
> PhoBERT/bkai = 768, e5-small = 384…).
>
> Hệ quả: nếu `.env` của bạn dùng model **khác** với model lúc file được commit, mà bạn chỉ chạy
> `setup.py` thường → nó thấy `centroids.npz` đã tồn tại nên **skip**, giữ nguyên centroids cũ sai chiều.
> Lúc chạy router sẽ lỗi `Incompatible dimension ... X.shape[1] == 768 while Y.shape[1] == 1024`,
> **mọi case rớt về SLM, accuracy 0%**. (FAISS thì an toàn hơn vì nằm trong `storage/` bị git-ignore,
> clone mới luôn build lại đúng model.)
>
> **Cách tránh:** mỗi khi đụng tới `EMBEDDING_MODEL`, **luôn** chạy `--embeddings-only` (hoặc `--force`),
> **đừng** chạy `setup.py` trơn. Chỉ khi máy mới dùng *đúng* model như lúc commit thì centroids trong git
> mới xài lại được.

> #### "Cứ `--force` cho dễ" có được không?
> **Được, và không bao giờ sai về chức năng** — `--force` là superset, luôn dựng lại FAISS + centroids
> đúng theo model hiện tại. Đổi lại 2 cái giá: (1) nó **xoá luôn `restaurant.db` + `checkpoints.db`** →
> mất order/session/hội thoại test (với máy dev/eval thường chẳng sao, nhiều khi còn muốn reset);
> (2) **chậm hơn** vì re-embed lại toàn bộ docs + utterances mỗi lần (trên CPU Jetson tốn vài phút).
> Nếu **chỉ đổi model** thì `--embeddings-only` nhanh hơn và giữ nguyên DB. Lười nhớ thì `--force` luôn cũng ổn.

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
DEVICE=cuda             # STT/VAD chạy GPU
EMBEDDING_DEVICE=cpu    # ĐẨY embedding khỏi iGPU → trả ~1.2GB RAM unified cho LLM (xem 6.4)
EMBEDDING_MODEL=        # trống = AITeamVN/Vietnamese_Embedding (2.2GB). Đổi model nhẹ hơn: xem 6.6
ROUTER_MODEL=qwen3:4b-instruct-2507-q4_K_M
WORKER_MODEL=qwen3:4b-instruct-2507-q4_K_M
RESPONSE_MODEL=qwen3:4b-instruct-2507-q4_K_M
LLM_NUM_CTX=6144        # context pin cho mọi lời gọi Ollama (hạ xuống 4096 nếu cần tiết kiệm thêm)
```
Ngân sách ước tính: LLM qwen3:4b q4 ~2.5GB (weights) + KV cache (theo `num_ctx`) + embedding ~1.2GB
+ torch/CUDA runtime + OS ≈ **sát 8GB** → cần các bước dưới. Vì là **unified memory**, embedding nằm
trên iGPU sẽ ăn vào đúng phần RAM mà Ollama cần để nạp LLM lên GPU → đặt `EMBEDDING_DEVICE=cpu`.

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
Environment="OLLAMA_KEEP_ALIVE=1m"         # idle 1 phút thì UNLOAD → trả RAM cho navigation/audio
```
```bash
sudo systemctl restart ollama
```

> ⚠️ **`OLLAMA_KEEP_ALIVE` — chọn theo logic chia RAM, đừng để mặc định.** Trên kiosk này LLM **dùng
> chung 8GB unified** với robot navigation + xử lý âm thanh, nên muốn LLM **nhả RAM khi không chạy**:
>
> | Giá trị | Hành vi | Khi nào dùng |
> |---|---|---|
> | `1m` *(khuyên dùng)* | giữ model trong một lượt khách (burst vài câu), idle 1 phút thì unload | kiosk: vào–gọi món–rời đi |
> | `0` | unload **ngay** sau mỗi request | RAM cực căng, ưu tiên tối đa cho nav/audio; chịu cold-start mỗi lần gọi |
> | `-1` | thường trú **vĩnh viễn**, không bao giờ nhả | chỉ khi LLM là tiến trình chính, **không** share RAM |
>
> `-1` (giữ thường trú) **mâu thuẫn** với mục tiêu trên — nó ăn RAM liên tục kể cả lúc idle và thường là
> thủ phạm tràn swap thật sự (chứ không chỉ `NUM_PARALLEL`). Env var chỉ là *default*; có thể override
> từng lời gọi bằng tham số `keep_alive` trong payload `/api/generate` · `/api/chat` (vd `"keep_alive": 0`).
> Đổi lại: unload xong thì lần gọi kế tiếp phải **nạp lại model** (cold-start vài giây) — cân nhắc giữa độ
> trễ và RAM rảnh.

### 6.4. Ollama có **thật sự** chạy GPU không? (quan trọng)
```bash
ollama ps        # sau 1 request: xem cột PROCESSOR + CONTEXT + SIZE
```
- Cột **PROCESSOR** là câu trả lời dứt khoát:
  - `100% GPU` → tốt.
  - `83%/17% CPU/GPU` hoặc `100% CPU` → Ollama đang **rút layer về CPU** (chậm, CPU 1–2 core đỏ).
- Bản `ollama` cài bằng script `curl ... | sh` trên Jetson thường **không nhận iGPU Tegra** → CPU-only.
  Kiểm tra log: `journalctl -u ollama -n 80 --no-pager | grep -iE "gpu|cuda|cpu|offload|compatible"`.
  Thấy `no compatible GPUs were discovered` / `offloaded 0/N layers` → cài đè bản **prebuilt JetPack 6**
  chính thức của Ollama (đã build CUDA cho Tegra):
  ```bash
  curl -L https://github.com/ollama/ollama/releases/download/v0.30.6/ollama-linux-arm64-jetpack6.tar.zst -o ollama-jp6.tar.zst
  sudo tar --zstd -xf ollama-jp6.tar.zst -C /usr/local
  sudo systemctl restart ollama
  ```
  Sau restart, gửi 1 request rồi `ollama ps` → cột `PROCESSOR` phải là `100% GPU`.
- Nếu PROCESSOR đã có GPU nhưng vẫn spill CPU lúc chạy eval: **tranh chấp bộ nhớ unified**. Embedding
  trên GPU (`python3` giữ ~1.2GB GPU MEM) + desktop làm Ollama ước lượng thiếu VRAM → đẩy layer xuống CPU.
  Đặt `EMBEDDING_DEVICE=cpu` (6.1) để trả lại ~1.2GB → Ollama nạp trọn LLM lên iGPU.
- Cách nhìn trong `jtop` (tab 2GPU): tìm process **`llama-server`** — nếu `GPU MEM` chỉ vài trăm MB cho
  model 4GB và `CPU%` ~180% thì model **không** nằm trên GPU. (Các đỉnh GPU giật cục thường là của
  embedding/torch ở `python3`, không phải LLM.)

### 6.5. Các "cần gạt" RAM khác
```bash
tegrastats       # RAM/SWAP realtime
free -h
```
- Nếu `ollama ps` báo context > 6144 → pin `num_ctx` đang cắt thật.
- Đặt công suất tối đa: `sudo nvpmodel -m 0 && sudo jetson_clocks`.
- Chạy **lần lượt từng eval** (đừng song song) để tránh đỉnh bộ nhớ cộng dồn.
- Vẫn thiếu: chạy headless `sudo systemctl set-default multi-user.target` (tiết kiệm 1–2GB);
  hạ `LLM_NUM_CTX=4096`; hoặc đổi embedding nhỏ hơn (6.6).

### 6.6. Đổi / benchmark model embedding

> **Tất cả model embedding ở đây đều chạy trên CPU** (`EMBEDDING_DEVICE=cpu`, dtype `float32`) để
> nhường RAM iGPU cho LLM (xem 6.4). Vậy các con số benchmark phản ánh **latency trên CPU Jetson** —
> model càng nhiều param càng chậm. Không cần chỉnh device riêng cho từng model.

**Các model đã khai báo sẵn** (profile tiền xử lý: prefix / word-seg / normalize) trong
`EMBEDDING_PROFILES` ([embeddings.py](../ai_waiter_core/ai_waiter_core/services/retriever/indices/embeddings.py)):

| EMBEDDING_MODEL | Backbone | Params | dim | ~size | Tiền xử lý | Ghi chú |
|---|---|---|---|---|---|---|
| `AITeamVN/Vietnamese_Embedding` *(mặc định)* | BGE-M3 (XLM-R large) | ~560M | 1024 | 2.2GB | — | tốt nhất TV, nặng nhất |
| `bkai-foundation-models/vietnamese-bi-encoder` | PhoBERT-base | ~135M | 768 | 0.5GB | word-seg + norm | chuyên TV, nhẹ |
| `dangvantuan/vietnamese-embedding` | PhoBERT-base | ~135M | 768 | 0.5GB | word-seg + norm | SBERT TV |
| `keepitreal/vietnamese-sbert` | PhoBERT-base | ~135M | 768 | 0.5GB | word-seg + norm | "sBERT-Vi" |
| `intfloat/multilingual-e5-small` | MiniLM-L12 | ~118M | 384 | 0.47GB | prefix `query:`/`passage:` + norm | nhẹ/nhanh nhất, đa ngữ |
| `intfloat/multilingual-e5-base` | XLM-R base | ~278M | 768 | 1.1GB | prefix + norm | đa ngữ mạnh hơn |
| `Alibaba-NLP/gte-multilingual-base` | mGTE | ~305M | 768 | 1.2GB | norm + trust_remote_code | chất lượng cao, ctx 8k |

> "~size" = dung lượng tải về (gồm tokenizer/config), không phải params × bytes. Thứ tự nhẹ→nặng:
> e5-small < (bkai ≈ dangvantuan ≈ keepitreal) < e5-base < gte < Vietnamese_Embedding.
>
> Không đưa vào list: `anti-ai/ViEmbedding-base` (PhoBERT-base-v2, 135M) — repo thiếu `config.json`/
> tokenizer/pooling, đóng gói cho thư viện riêng `rage`, **không nạp được** qua `SentenceTransformer`.
> Cần "dòng ViEmbedding/PhoBERT" thì dùng `dangvantuan/vietnamese-embedding` (tương đương, đóng gói chuẩn).

**Đổi model → rebuild → chạy lại** (mỗi bước ~đều trên CPU; lần đầu mỗi model sẽ tải từ HuggingFace):

```bash
# Cách A — sửa .env: EMBEDDING_MODEL=dangvantuan/vietnamese-embedding   rồi:
uv run python scripts/setup.py --embeddings-only   # rebuild CHỈ FAISS + centroids (không đụng SQLite DB)
uv run python evals/scripts/eval_retrieval.py      # Precision@5 / Recall@5 / MRR / Hit Rate
uv run python evals/scripts/eval_router.py         # accuracy router (dùng centroids mới)
uv run python evals/scripts/eval_e2e.py --datasets e2e_conversations_part1.json e2e_conversations_part2.json  # (tuỳ chọn) full pipeline

# Cách B — không sửa .env, override 1 lần bằng biến môi trường (nhớ set GIỐNG nhau cho cả rebuild lẫn eval):
EMBEDDING_MODEL=intfloat/multilingual-e5-small uv run python scripts/setup.py --embeddings-only
EMBEDDING_MODEL=intfloat/multilingual-e5-small uv run python evals/scripts/eval_retrieval.py
```

> **Bắt buộc rebuild khi đổi model** — vector model cũ không so được với model mới (khác chiều/khác phân
> bố). `--embeddings-only` chỉ dựng lại FAISS + centroids (BM25 là lexical, không phụ thuộc embedding;
> SQLite DB giữ nguyên). Nếu quên rebuild, retrieval/router sẽ sai âm thầm.

**Benchmark cả list một lượt** (mỗi model: rebuild → eval_retrieval → eval_router, log ra
`evals/results/bench_embedding/<model>.log`):
```bash
scripts/bench_embedding.sh                                   # toàn bộ list mặc định
scripts/bench_embedding.sh dangvantuan/vietnamese-embedding bkai-foundation-models/vietnamese-bi-encoder  # chỉ vài model
```

### 6.7. Chạy (giống PC)
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
