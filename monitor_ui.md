# Hướng dẫn sử dụng màn hình Monitor (AI WAREHOUSE)

> Dành cho bạn bè muốn hiểu (và tự chạy) cái màn hình demo giọng nói của robot kho.
> Từ lúc cài đặt tới lúc biết từng thành phần trên giao diện làm gì.

---

## 1. Monitor là cái gì?

**Monitor** là một trang web đứng riêng, dùng làm **màn hình demo** cho cả căn phòng nhìn cùng lúc.
Nó không phải cái bảng điều khiển — nó chỉ có **một con robot, một sóng âm, một dòng trả lời**,
để ai không đọc được chữ (hoặc không thèm đọc) vẫn biết robot đang làm gì: đang nghe, đang nghĩ,
đang nói, hay vừa nhận lệnh xong.

Trang này nằm ở: `src/frontends/monitor/` (Vue 3 + Vite).

---

## 2. Cần những gì để chạy?

Monitor chỉ là "cái màn hình" — nó cần 3 anh khác chạy ngầm để có thứ mà hiển thị:

| Thành phần | Chạy ở đâu | Làm gì | Lệnh |
|---|---|---|---|
| **Backend (orchestrator)** | Máy server | Trạm trung chuyển WS, gửi map/telemetry, phục vụ file web | `make backend` |
| **Agent (LLM)** | Máy server | Cái "não" hiểu tiếng Việt, trả lời + ra lệnh cho robot | `make agent` |
| **Voice device** | Máy Jetson (có mic + loa) | Nghe tiếng người, nói lại bằng TTS | `make voice` |

> Monitor tự nó **không** có mic. Nó chỉ nhận sự kiện đẩy tới qua WebSocket từ backend.

**Phần mềm trên máy bạn:**
- **Node.js 22** (dùng nvm cho gọn: `nvm use 22`)
- **uv** (để chạy backend/agent): `export PATH="$HOME/.local/bin:$PATH"`
- Git

---

## 3. Chạy Monitor như thế nào?

Có 2 cách: **dev (xem nhanh lúc code)** và **production (demo thật)**.

### 3.1. Xem nhanh lúc phát triển (dev server)

Mở terminal tại thư mục gốc repo:

```bash
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"; nvm use 22
make monitor
```

Mở trình duyệt: **http://localhost:5176/monitor/**

(Monitor dùng base `/monitor/` và tự proxy `/api` + `/ws` sang backend `:8000`,
nên bạn chỉ cần backend chạy là được.)

### 3.2. Demo thật (production)

Monitor được build thành file tĩnh và **do backend phục vụ chung một cổng 8000** —
không cần trình duyệt cài Node. Làm trên **máy server**:

```bash
git pull
make build          # build cả 4 app (customer_ui, kiosk, panel, monitor) → thư mục dist/
make backend        # uv thiết đã --reload sẽ tự load bản dist mới
```

Sau đó **máy Jetson (hoặc bất kỳ máy nào)** chỉ việc mở URL:

```
http://<SERVER_IP>:8000/monitor
```

Trên Jetson thường dùng lệnh `make jetson` — nó tự mở trang `/monitor` ra trình duyệt kiosk
toàn màn hình. **Pull code trên Jetson KHÔNG đổi giao diện monitor**, vì monitor được build/serve
từ máy server. Muốn cập nhật giao diện là phải `make build` trên server.

> 💡 Lưu ý: `make voice` trên Jetson **hoàn toàn không liên quan** tới code monitor.
> Bạn sửa giao diện thoải mái, voice vẫn chạy bình thường.

---

## 4. Giao diện có những gì?

Từ trên xuống dưới:

```
┌───────────────────────────────────────────────┐
│  [🤖] AI WAREHOUSE        TRỢ LÝ KHO ROBOT   │ ← Header
│                          ● robo-1  (đang kết nối)│
│                                                 │
│              ╭───────────────────╮              │
│              │    CON ROBOT AGV   │              │ ← Robot (giữa)
│              │  listening/thinking│              │
│              ╰───────────────────╯              │
│                 ～～ sóng âm ～～                │ ← Voice wave
│                                                 │
│              📍  (icon lệnh bự, nếu có)          │ ← Action glyph
│                                                 │
│              ĐANG NGHE  —  Mời anh/chị ra lệnh…  │ ← State
│              “anh đưa tôi thùng bia”             │ ← Lời nghe được
│              Đây ạ, em đi lấy thùng bia Khu A.    │ ← Câu trả lời
│              [ Di chuyển đến Khu A · ô A01 ]     │ ← Chip hành động
│                                                 │
│  🔋 Pin 87%   đang nghỉ   Vị trí (0.0, 0.0)      │ ← Telemetry
│  [“lệnh 1”] [“lệnh 2”] [“lệnh 3”]  ← lịch sử    │ ← History
│  [🎤 Bắt đầu] [⏹ Dừng] [🔄 Mới]  Mic ▔▔ Loa ▔▔  │ ← Controls
└───────────────────────────────────────────────┘
```

### 4.1. Header (đầu trang)
- **Logo + thương hiệu**: `AI WAREHOUSE / TRỢ LÝ KHO ROBOT`.
- **Chấm trạng thái + tên robot**:
  - Chấm xanh = đã kết nối với backend và có robot.
  - "Đang kết nối…" = chưa tới được backend.
  - "Chưa có robot" = backend chạy nhưng chưa thấy thiết bị voice.
  - Nếu có nhiều robot, có một **dropdown** để chọn robot nào được chiếu lên màn này.

### 4.2. Con robot AGV (giữa màn hình)
Là một hình vẽ robot kho (AMR): thân bo tròn, mái vòm LIDAR, đèn beacon, màn hình mặt có 2 mắt,
đèn ngực, 2 bánh, và vành hào quang (halo) xung quanh.

Nó **đổi trạng thái theo từng giai đoạn** của một lượt nói (xem mục 4.3). Đặc biệt:
- Lúc **đang nói**, nó có **cái miệng động** (mấp máy) để người xem thấy rõ robot đang "nói".
- Có **vành hào quang sáng** màu theo giai đoạn, và **rửa ánh sáng** nhẹ toàn màn lúc đang nói.

### 4.3. Các giai đoạn (phase) — tim của màn hình
Toàn bộ quy trình nghe→hiểu→nói được gom thành **1 trong 7 trạng thái**, mỗi trạng thái có
**1 màu riêng** hiện ở halo, sóng âm và dòng trạng thái:

| Trạng thái | Dòng hiện ra | Ý nghĩa | Màu |
|---|---|---|---|
| `Sẵn sàng` | "Bấm Bắt đầu ra lệnh rồi nói với robot" | Chưa có lượt nào | xám |
| `Đang nghe` | "Mời anh/chị ra lệnh…" | Robot đang thu giọng nói | xanh trời |
| `Đang xử lý` | "Robot đang hiểu câu lệnh và tra cứu kho" | Đang nhận diện + hỏi não LLM | cam |
| `Đang trả lời` | "Robot đang nói câu trả lời" | Não xong, robot đang đọc to | xanh lá |
| `Đã xong` | "Robot đã nhận lệnh và bắt đầu thực hiện" | Lệnh được chấp nhận, bắt đầu làm | xanh lá |
| `Chưa nghe rõ` | "Không bắt được câu nói — bấm ra lệnh lại" | Mic không bắt được tiếng | xám |
| `Chưa trả lời được` | "Có trục trặc ở lượt này — thử lại" | Lỗi ở lượt này | đỏ |

→ Người xem **chỉ cần nhìn màu + sóng** là biết robot đang ở đâu trong câu chuyện, không cần đọc chữ.

### 4.4. Voice wave (sóng âm)
Sóng dao động ngay dưới con robot, **màu theo trạng thái** (mục 4.3).
Càng lúc đang nghe/nói sóng càng nhảy — tạo cảm giác máy "sống".

### 4.5. Action glyph (icon lệnh bự)
Khi robot được giao việc cụ thể, một **icon khổng lồ** hiện giữa màn để ai không đọc cũng biết
nó phải làm gì:
- 📍 **navigate** (ghim bản đồ) — đi tới một khu/ô.
- ⬆️/⬇️ **lift** (mũi tên nâng/hạ) — nâng/hạ càng nâng.
- 🛑 / ▶️ / ❌ **control** — dừng tại chỗ / chạy tiếp / hủy chuyến.

Icon cũng đổi màu theo trạng thái và có hiệu ứng "bật lên" (pop) khi xuất hiện.

### 4.6. Success burst (vòng bùng nổ)
Khoảnh khắc lệnh được chấp nhận (`Đã xong`), một **vòng sáng bùng ra một lần** từ giữa màn.
Kiểu "xong việc" — người xem *cảm* được hơn là đọc được.

### 4.7. Phần trả lời (answer)
- **“lời nghe được”** (italic): robot nghe bạn nói ra sao (để bạn sửa nếu nghe sai).
- **câu trả lời**: câu robot đọc to, chữ to, đậm, dễ đọc từ xa.
- **chip hành động**: tóm tắt lệnh dạng chữ, ví dụ
  `Di chuyển đến Khu A · ô A01 · hộp xanh dương` hoặc `Dừng tại chỗ`.

Cả khối này giữ nguyên cho tới lượt nói tiếp theo, để khách kịp đọc.

### 4.8. Telemetry (thông số robot)
Một dòng nhỏ: **🔋 Pin xx%**, **trạng thái** (đang nghỉ/đang chạy…),
**Vị trí (x, y)** lấy từ pose thật của robot. Giúp người xem tin đây là máy thật, không phải hình vẽ.

### 4.9. Command history (lịch sử lệnh)
Dải ngang các lượt vừa rồi (mới nhất bên phải), mỗi mục: lời nghe được + câu trả lời + chip.
Tiện khi demo muốn "xem lại nãy nó bảo gì" mà không cuộn chat.

### 4.10. Controls (điều khiển, dưới cùng)
- **🎤 Bắt đầu ra lệnh**: mở một lượt nghe (hiện "Đang nghe" ngay). Bấm xong thì nói.
- **⏹ Dừng**: cắt lượt hiện tại.
- **🔄 Hội thoại mới**: xóa hội thoại, về trạng thái sẵn sàng.
- **Mic / Loa**: hai cụm `− / số % / +` để chỉnh mức âm thanh **từng 10%** (bấm nút dễ hơn kéo thanh trượt).

---

## 5. Nó hoạt động ra sao (không cần hiểu sâu)

```
Mic Jetson ──► make voice ──► backend (WS hub) ──► monitor (trang web)
                  ▲                                   │
                  │                                   ▼
            LLM agent ◄──── "/chat/stream" ──  câu trả lời + lệnh có cấu trúc
```

- Mỗi sự kiện (nghe được, đang nghĩ, đang nói, xong, lỗi…) được backend **đẩy realtime** qua
  WebSocket tới monitor → màn hình đổi trạng thái tức thì, không cần refresh.
- Có 2 nguồn sự kiện:
  - **voice.device** (từ Jetson): nghe/nói/xong thực tế.
  - **voice.\*** (từ agent): câu trả lời + lệnh structured (nuôi Action glyph & chip).

---

## 6. Mẹo & lỗi thường gặp

- **Màn hình đứng yên ghi "Đang kết nối…"** → backend chưa chạy, hoặc sai IP. Kiểm tra `make backend`
  đang chạy trên server và Jetson mở đúng `http://<SERVER_IP>:8000/monitor`.
- **Hiện "Chưa có robot"** → backend sống nhưng chưa có `make voice` kết nối. Bật voice trên Jetson.
- **Đổi giao diện mà Jetson không thấy** → bạn quên `make build` trên server. Monitor được serve từ
  `dist/` của server, không phải từ code trên Jetson.
- **Chỉnh mic/loa không được** → số hiện `—` nghĩa là chưa có thông số từ device (voice chưa gửi
  `levels`). Đợi voice chạy ổn định rồi chỉnh.
- **Xem nhanh lúc code** → `make monitor` (port 5176) là đủ, không need build.

---

## 7. Tóm tắt lệnh hay dùng

```bash
# Server (phục vụ web + trung chuyển)
make backend          # cổng 8000
make agent            # cổng 8100 (não)
make build            # build lại dist/ sau mỗi lần sửa giao diện

# Dev xem nhanh giao diện monitor
make monitor          # http://localhost:5176/monitor/

# Jetson
make voice            # chạy thiết bị giọng nói
make jetson           # voice + mở màn /monitor kiosk toàn màn hình
```

Chúc vui với con robot! 🤖
