# Hướng Dẫn Chạy Web — RoboDish Customer UI

File này hướng dẫn cách **cài đặt và bật web** giao diện đặt món (kiosk). Dành cho người mới, làm theo từng bước là chạy được.

> **TL;DR (nếu máy đã cài sẵn):**
> ```bash
> cd src/frontends/customer_ui
> npm run dev
> ```
> Mở trình duyệt: **http://localhost:5173**

---

## 1. Cần có gì trước khi chạy?

| Yêu cầu | Kiểm tra | Ghi chú |
|---|---|---|
| **Node.js 22** | `node -v` → `v22.x` | Bắt buộc. Phiên bản pin trong `.nvmrc` |
| **npm** | `npm -v` | Đi kèm Node, không cần cài riêng |

> Nếu `node -v` báo *not found* → máy chưa có Node. Xem [Phụ lục: Cài Node lần đầu](#phụ-lục-cài-node-lần-đầu-máy-mới).

---

## 2. Cài đặt lần đầu (chỉ làm 1 lần)

Từ thư mục gốc dự án (`AI_Waiter/`):

```bash
cd src/frontends/customer_ui   # vào thư mục web
cp .env.example .env           # tạo file cấu hình (nếu chưa có)
npm ci                         # cài đúng phiên bản thư viện trong package-lock.json
```

- `npm ci` tải toàn bộ thư viện vào thư mục `node_modules/` (tốn vài phút lần đầu).
- File `.env` chứa các đường dẫn backend/websocket. Bản mặc định đã chạy được; sửa khi cần.

---

## 3. Bật web (chế độ phát triển)

```bash
cd src/frontends/customer_ui
npm run dev
```

Thấy dòng này là **thành công**:
```
  ➜  Local:   http://localhost:5173/
```

Mở trình duyệt vào **http://localhost:5173** → web hiện ra.

- Web tự **reload** mỗi khi bạn sửa code hoặc sửa `menu.json` (hot-reload).
- **Dừng web:** bấm `Ctrl + C` trong terminal đang chạy.

---

## 4. Cách nhanh hơn bằng Makefile

Đứng ở **thư mục gốc dự án** (`AI_Waiter/`), không cần `cd`:

```bash
make frontend    # bật web dev → http://localhost:5173
make install     # cài lại thư viện sau khi pull code mới
make build       # đóng gói bản production → dist/
make serve       # chạy thử bản production (http://localhost:4173)
make help        # xem tất cả lệnh
```

---

## 5. Thêm / sửa dữ liệu menu

Toàn bộ món ăn nằm ở file: **`assets/data/menu.json`** (ở thư mục gốc dự án).

Mỗi món có dạng:
```json
{
  "name": "Ốc Hương",
  "description": "Mô tả món...",
  "price": "85000",
  "diet_type": "mặn",
  "category": "Ốc & Sò",
  "ingredients": "Ốc hương, tỏi, bơ...",
  "taste_profile": "Giòn ngọt, đậm đà",
  "tags": "ốc, hải sản, best seller"
}
```

Quy tắc:
- `price`: để **dạng chuỗi**, đơn vị VND, không dấu chấm (vd `"85000"`).
- `tags`: ngăn cách bằng **dấu phẩy** trong 1 chuỗi.
- `category`: tên danh mục. Web tự gom món theo `category` thành các tab.

Sửa xong **lưu file** → web tự cập nhật ngay (không cần khởi động lại).

> **Thêm danh mục mới?** Cứ điền `category` mới vào món là tab tự hiện (icon mặc định 🍽️).
> Muốn icon/thứ tự đẹp hơn → thêm 1 dòng vào `CATEGORY_META` trong
> [`src/data/menuAdapter.ts`](src/data/menuAdapter.ts).

---

## 6. Lỗi thường gặp

| Triệu chứng | Nguyên nhân & cách xử lý |
|---|---|
| `node: command not found` | Chưa cài Node → xem [Phụ lục](#phụ-lục-cài-node-lần-đầu-máy-mới) |
| `vite: not found` / lỗi thiếu module | Chưa chạy `npm ci`. Chạy lại trong `src/frontends/customer_ui` |
| `Port 5173 is in use` | Web đang chạy ở terminal khác. Tắt nó (`Ctrl+C`) hoặc đổi cổng: `npm run dev -- --port 5174` |
| Web mở được nhưng **trắng/thiếu món** | Kiểm tra `menu.json` có đúng cú pháp JSON không (thiếu dấu phẩy, ngoặc...) |
| Sửa menu mà web không đổi | Tải lại trang (F5). Nếu vẫn không, tắt và `npm run dev` lại |

---

## Phụ lục: Cài Node lần đầu (máy mới)

Nếu máy **chưa có Node.js**, dùng script cài tự động ở thư mục gốc:

```bash
make setup        # cài nvm + Node 22 + uv, rồi tự npm ci
source ~/.bashrc  # nạp lại shell để dùng được node/npm
make frontend     # bật web
```

> `make setup` chỉ chạy trên Linux (Ubuntu). Trên macOS/Windows: cài Node 22 thủ công
> (qua [nvm](https://github.com/nvm-sh/nvm) hoặc trang chủ nodejs.org), rồi làm tiếp từ [Mục 2](#2-cài-đặt-lần-đầu-chỉ-làm-1-lần).

---

## Tóm tắt 1 phút

```bash
# Lần đầu
cd src/frontends/customer_ui && cp .env.example .env && npm ci

# Mỗi lần muốn bật web
npm run dev            # → http://localhost:5173
# (hoặc từ gốc dự án:  make frontend)

# Dừng web: Ctrl + C
```
