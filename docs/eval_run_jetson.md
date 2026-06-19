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
