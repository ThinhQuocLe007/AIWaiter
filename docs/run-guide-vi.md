# Hướng Dẫn Cài & Chạy — AI Waiter (RoboDish)

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

> Chọn `UV_EXTRAS` theo máy (xem [docs/setup-deploy.md](setup-deploy.md)):
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
> Chi tiết CUDA/role: [docs/setup-deploy.md](setup-deploy.md). Makefile dùng
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
