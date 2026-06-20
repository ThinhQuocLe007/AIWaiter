# Setup môi trường Python (uv) — Dev x86 & Jetson

Project dùng [uv](https://docs.astral.sh/uv/) để quản lý môi trường Python (phần "brain": LLM, RAG, embeddings).

Điểm cần lưu ý: **torch chạy trên 2 loại máy với CUDA khác nhau**, nên `pyproject.toml`
đã cấu hình lấy torch/torchvision theo từng kiến trúc máy. Bạn **không cần** chỉnh gì,
chỉ chạy `uv sync` là đúng.

| Máy | Kiến trúc | GPU | torch | Nguồn | CUDA |
|---|---|---|---|---|---|
| Dev | x86_64 | RTX 5060 Ti (Blackwell, sm_120) | `2.12.x` | PyPI | cu13 (13.0) |
| Deploy | aarch64 | Jetson Orin | `2.11.0` | index jetson-ai-lab | cu126 (12.6) |

uv tự chọn đúng nhánh dựa trên `platform_machine` của máy đang chạy.

---

## 1. Máy DEV (x86_64, RTX 5060 Ti)

```bash
# Lần đầu: cài uv nếu chưa có
curl -LsSf https://astral.sh/uv/install.sh | sh

# Cài/đồng bộ môi trường
uv sync

# Kiểm tra torch + GPU
uv run python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

Kết quả mong đợi:

```
2.12.1+cu130 13.0 True
```

> Yêu cầu: driver NVIDIA hỗ trợ **CUDA 13** trên máy dev (Blackwell sm_120 cần cu13).

---

## 2. Máy JETSON (aarch64, Jetson Orin — CUDA 12.6 / JetPack 6)

### 2.1. Cài đặt

```bash
# Lần đầu: cài uv nếu chưa có
curl -LsSf https://astral.sh/uv/install.sh | sh

# Đồng bộ — uv tự kéo torch 2.11.0 cu126 (GPU) từ index jetson-ai-lab
git pull
uv sync

# Kiểm tra torch + GPU
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Kết quả mong đợi:

```
2.11.0 True
```

### 2.2. Nếu gặp lỗi `libcudss.so.0: cannot open shared object file`

torch cu126 cần lib hệ thống `libcudss`. Cài qua apt:

```bash
sudo apt-get install -y libcudss0-cuda-12
```

Rồi chạy lại bước kiểm tra ở trên.

---

## 3. Tối ưu RAM cho Ollama (Jetson Orin 8GB unified)

Trên Jetson Orin 8GB, GPU và CPU **dùng chung** 8GB. Nếu không tinh chỉnh, hệ thống dễ
tràn sang swap (đo được ~+3GB). Hai phần cần làm:

### 3.1. `num_ctx` đã được pin sẵn trong code

Mọi lời gọi LLM dùng `settings.LLM_NUM_CTX` (mặc định **6144**) — xem `agent_config.py`.
qwen3:4b hỗ trợ tới 262144 token; nếu để Ollama tự quyết, KV cache có thể rất lớn.
Một giá trị `num_ctx` **đồng nhất** cho mọi node cũng tránh Ollama nạp lại model giữa các node.

Chỉnh khi cần (vd muốn nhỏ hơn để tiết kiệm thêm RAM):

```bash
# trong .env
LLM_NUM_CTX=4096
```

### 3.2. Cấu hình Ollama service (env override)

```bash
sudo systemctl edit ollama
```

Dán vào:

```ini
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"        # kiosk phục vụ tuần tự → KHÔNG nhân KV cache (nghi can chính gây tràn swap)
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"    # KV cache 8-bit → giảm ~nửa, chất lượng gần như nguyên (cần FLASH_ATTENTION=1)
Environment="OLLAMA_KEEP_ALIVE=-1"         # giữ model thường trú, tránh reload
```

```bash
sudo systemctl restart ollama
```

### 3.3. Kiểm chứng

```bash
# sau khi gửi 1 request cho agent:
ollama ps        # xem CONTEXT + SIZE model đang chiếm thực tế
tegrastats       # theo dõi RAM/SWAP realtime
free -h
```

- Nếu `ollama ps` báo context > 6144 → việc pin `num_ctx` đang cắt thật.
- Nếu vẫn thiếu RAM: chạy headless `sudo systemctl set-default multi-user.target` (tiết kiệm 1–2GB),
  hoặc cân nhắc embedding nhỏ hơn (chạy lại `eval_retrieval` để cân chất lượng).

> Embedding (`AITeamVN/Vietnamese_Embedding`, BGE-M3) đã được load **fp16** sẵn (~1.1GB thay vì ~2.2GB) — xem `embeddings.py`.

---

## Lưu ý quan trọng

- **KHÔNG** chạy `uv pip install torch ...` thủ công trên Jetson nữa — `uv sync` đã lo việc đó.
  Cài tay sẽ bị `uv sync` lần sau đồng bộ lại.
- **KHÔNG** cần các cờ `--no-sync` / `--inexact` / `--no-install-package torch` nữa.
  Cấu hình trong `pyproject.toml` đã xử lý, cứ `uv sync` / `uv run` bình thường.
- torch trên 2 máy **khác version là cố ý** (cu13 cho Blackwell vs cu126 cho Jetson),
  không phải lỗi.

## Cách hoạt động (tham khảo, trong `pyproject.toml`)

```toml
[tool.uv]
# Ép uv resolve cho CẢ x86 lẫn aarch64 khi tạo lock (dù lock từ máy x86).
environments = [
    "sys_platform == 'linux' and platform_machine == 'x86_64'",
    "sys_platform == 'linux' and platform_machine == 'aarch64'",
]

[tool.uv.sources]
# Chỉ aarch64 (Jetson) mới lấy torch từ index NVIDIA jetson-ai-lab.
torch = [{ index = "jetson-cu126", marker = "platform_machine == 'aarch64'" }]
torchvision = [{ index = "jetson-cu126", marker = "platform_machine == 'aarch64'" }]

[[tool.uv.index]]
name = "jetson-cu126"
url = "https://pypi.jetson-ai-lab.io/jp6/cu126/+simple/"  # devpi cần hậu tố /+simple/
explicit = true
```

> 3 điều kiện để cấu hình này hoạt động: (1) torch/torchvision phải khai báo **trực tiếp**
> trong `dependencies` (không để transitive qua sentence-transformers), (2) URL index phải có
> đuôi `/+simple/`, (3) phải khai báo `environments` cho cả 2 kiến trúc.
