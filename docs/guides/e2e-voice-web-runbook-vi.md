# Runbook — test e2e Voice ↔ Agent ↔ Web + pin thật (chưa cần nav)

> Mục tiêu bản này: bật đủ để **khách nói chuyện với AI qua web** và **panel hiện pin thật của robot**,
> KHI CHƯA có navigation/localization. Nav thật (Nav2 + RTAB-Map + ArUco) do người khác merge từ
> `tarkbot_robot_ros2` sang `robot_ws/src/real/` sau — xem [jetson-nav-merge-vi.md](jetson-nav-merge-vi.md).
>
> Vận hành voice hằng ngày: [jetson-boot-runbook-vi.md](jetson-boot-runbook-vi.md).
> Kiến trúc tổng thể: [setup-deploy.md](setup-deploy.md).

## 0. Bản đồ 3 máy (fleet Netbird)

| Máy | Netbird IP | Chạy gì | Mở trình duyệt tới |
|---|---|---|---|
| **Server** (ducduy-pc) | `100.66.165.221` | `backend` (serve luôn **cả 3 web**) + `agent` | — |
| **Jetson** (robot) | `100.66.177.150` | `robot_node` + `ai_hw_bridge` + `make voice` + **trình duyệt kiosk** | `:8000/` (customer_ui) |
| **Laptop** (ubuntu) | `100.66.242.168` | *(chỉ trình duyệt)* | `:8000/panel` + `:8000/kiosk` |

**Nguyên tắc:** chỉ **server** có Node → server **build** cả 3 web (`make build`), rồi **backend tự serve**
chúng cùng origin `:8000`. Jetson/laptop chỉ **mở URL** — không Node, không dev server, không CORS.

> **Đổi so với bản trước (2026-07-20):** trước đây server chạy `make frontend` (3 vite dev server
> 5173/5174/5175) và client trỏ thẳng vào cổng dev. Đó là **chế độ dev**, không phải deploy: backend
> khi ấy chưa mount static nào cả. Nay `main.py` mount `dist/` của cả 3 app và alias toàn bộ router
> dưới `/api` (dev thì vite proxy cắt tiền tố này giùm, production không ai cắt hộ).
> `make frontend` vẫn còn — nhưng **chỉ để sửa giao diện có hot-reload**.

```
STM32 ─/bat_vol─► robot_node ─► ai_hw_bridge ─WS role=robot────► backend :8000 ─► panel (pin thật)
                                     │ task.assign→arrived (STUB motion)                │
make voice ─WS role=voice-device────►│◄──────────────────────────────── binding bàn ───┘
     │ nói ─► agent :8100 ─► trả lời ─► TTS + customer_ui (:8000/ trên màn robot)
```

---

## ⓪ Một lần duy nhất — trên JETSON

**Dep bridge:**
```bash
sudo apt-get install -y python3-websocket
```
`python3-websocket` = dep runtime của bridge (cho `ros2 run` dùng system python3).

**Trình duyệt kiosk.** Trên rig hiện tại `chromium-browser` chạy tốt → cứ dùng nó (bước ② T4).

Chỉ khi chromium là **bản snap** và snapd chết (`inactive/disabled`, `snap list` treo — hay gặp trên
Jetson) mới cần đường vòng: cài **Firefox bản deb** qua Mozilla PPA (né snap), cũng có `--kiosk`
chuẩn cho touchscreen:
```bash
sudo add-apt-repository -y ppa:mozillateam/ppa
printf 'Package: *\nPin: release o=LP-PPA-mozillateam\nPin-Priority: 1001\n' | sudo tee /etc/apt/preferences.d/mozilla-firefox
sudo apt-get update && sudo apt-get install -y firefox
firefox --version    # phải ra "...~mt1" (mozillateam), KHÔNG phải "1snap1"
```

---

## ① SERVER — ducduy-pc — bật TRƯỚC

```bash
cd ~/AIWaiter && source .venv/bin/activate

make build                   # CHỈ khi mới pull/sửa web — build tĩnh cả 3 app ra dist/
```

`make build` chạy **trước** `make backend`: backend mount `dist/` lúc khởi động, nên build xong
phải **restart backend** thì web mới đổi. Chưa build thì `:8000/` ra 404 (API vẫn sống bình thường).

Rồi mỗi lệnh một terminal (hoặc `tmux`):

```bash
ollama serve                 # T0 — LLM (terminal riêng)
ollama list                  # phải có model khớp ROUTER/WORKER/RESPONSE_MODEL trong .env

make backend                 # T1 — :8000 — REST + WS hub + serve cả 3 web
make agent                   # T2 — :8100 — CHỜ in "Agent ready." (lần đầu build embeddings, lâu)
```

Verify trước khi qua Jetson:
```bash
curl -s http://127.0.0.1:8000/health           # backend sống
curl -s http://127.0.0.1:8100/health           # agent sống
curl -sI http://127.0.0.1:8000/ | head -1      # 200 = đã serve customer_ui (404 = quên make build)
curl -s http://127.0.0.1:8000/api/menu | head -c 80   # alias /api sống (bundle production gọi qua đây)
```

> Không cần `VITE_TABLE_ID` — customer_ui default sẵn **bàn 1**.

---

## ② JETSON — robot — 4 terminal

```bash
# ── T1: base driver (STM32 → /bat_vol, /odom, /imu). KHÔNG gửi cmd_vel nên xe ĐỨNG YÊN.
cd ~/ptd_workspace/tarkbot_robot_ros2
source /opt/ros/humble/setup.sh && source install/setup.sh
ros2 run tarkbot_robot robot_node
```

```bash
# ── T2: bridge robot↔web (role=robot) — đẩy battery THẬT + nhận task (arrived fire ngay)
cd ~/ptd_workspace/AIWaiter/robot_ws
source /opt/ros/humble/setup.sh && source install/setup.sh
ros2 run ai_hw_bridge task_bridge --ros-args \
  -p server_host:=100.66.165.221:8000 -p robot_id:=robo-1
# → "WS connected → ws://100.66.165.221:8000/..." + "task_bridge ready"
```

```bash
# ── T3: voice device (STT/TTS ↔ agent)
cd ~/ptd_workspace/AIWaiter
make voice
# → CHỜ "[READY] đã kết nối backend (robo-1)"
```

```bash
# ── T4: customer_ui trên màn robot — trỏ vào :8000 (bản build), KHÔNG còn :5173
# Nếu gõ QUA SSH: phải trỏ sang màn hình vật lý :0 của robot (2 dòng export), else "no DISPLAY".
# Gõ trực tiếp trên terminal của desktop robot thì bỏ 2 dòng export.
export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority

chromium-browser --kiosk --noerrdialogs --disable-infobars http://100.66.165.221:8000/
# Nếu chromium trên máy này là bản snap và snap chết → dùng Firefox deb (bước ⓪):
#   firefox --kiosk http://100.66.165.221:8000/
# Thoát kiosk: Ctrl+W hoặc Alt+F4
```

> Base pin 3S Li-ion: `battery_full_v=12.6`, `battery_empty_v=10.5` đã là default đúng — khỏi truyền.
> Muốn override pack khác: thêm `-p battery_full_v:=... -p battery_empty_v:=...` vào lệnh T2.

---

## ③ LAPTOP — ubuntu — chỉ mở trình duyệt

- Panel (bếp, xem **pin robot**): `http://100.66.165.221:8000/panel`
- Kiosk (xếp bàn, tuỳ chọn): `http://100.66.165.221:8000/kiosk`

---

## ④ Chạy thử luồng

1. **Panel** (`:8000/panel`) → robot **`robo-1`** online, **pin thật ~47%** từ STM32.
   *(Chưa có chấm minimap vì chưa localization — ĐÚNG dự kiến; pin vẫn hiện ở robot board.)*
2. **Kiosk/panel** → **seat bàn 1** → **gọi robot tới bàn 1**.
   → bridge (T2): `task.assign` → `[STUB] deliver_to(Table 1)` → `arrived`
   → backend: **`voice bound to robo-1`**.
   **Bước này bắt buộc:** binding bàn→robot sinh ra ở đây, và *mọi* nút voice (nói chuyện, Hủy,
   tắt loa, cuộc trò chuyện mới) đều đi qua nó. Chưa gọi robot tới bàn thì cả 4 nút đều `no_device`.
3. **customer_ui trên màn robot** (`:8000/`) → bấm **"Nói chuyện với AI"**
   → voice (T3): `[LISTENING] mời anh/chị nói...`
4. Nói tiếng Việt → `[HEARD @ ... | bàn 1]: ...` → `[WAITER]: ...` + **loa đọc** + customer_ui hiện hội thoại.
5. **Thử 3 nút điều khiển** (đối chiếu log T3 — mỗi nút phải in một dòng):
   - **Hủy/Dừng** giữa lượt → `[CANCEL] khách bấm dừng` + loa tắt ngay giữa câu.
   - **Tắt loa** (icon loa) → `[MUTE] tắt loa trả lời`; hội thoại vẫn chạy dạng chữ.
   - **Cuộc trò chuyện mới** → `[CANCEL] ...` ở T3 + agent (T2) log `Conversation thread ... reset`.
   Sau mỗi nút, bấm **"Nói tiếp"** phải nghe lại được ngay — nếu im lặng, xem mục 6.
6. **Vuốt hàng Best Seller** bằng ngón tay (không chạm thanh cuộn, không bấm mũi tên) → strip phải
   trượt theo tay và có quán tính.

---

## ⑤ Bảng chờ (dán lên tường)

| # | Máy | Lệnh | Chờ tới khi |
|---|---|---|---|
| 1 | server | `make build` *(chỉ khi mới pull/sửa web)* | build xong cả 3 `dist/` |
| 2 | server | `ollama serve` | `ollama list` ra model |
| 3 | server | `make backend` | `/health` OK + `curl -sI :8000/` ra 200 |
| 4 | server | `make agent` | `Agent ready.` |
| 5 | jetson | `ros2 run tarkbot_robot robot_node` | `/bat_vol` publish |
| 6 | jetson | `ros2 run ai_hw_bridge task_bridge` | `WS connected` + panel hiện pin |
| 7 | jetson | `make voice` | `[READY]` |
| 8 | jetson | `chromium-browser --kiosk :8000/` | web hiện trên màn robot |
| 9 | web | seat + gọi robot | backend `voice bound to robo-1` |
| 10 | web | bấm "nói chuyện" | jetson `[LISTENING]` |
| 11 | web | Hủy · tắt loa · cuộc trò chuyện mới | jetson `[CANCEL]` / `[MUTE]`, rồi "Nói tiếp" nghe lại được |

Tắt: server `make kill` · Jetson `Ctrl-C` từng terminal.

---

## 6. Gỡ rối theo triệu chứng

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Bấm "nói chuyện" trả `no_device` | Chưa gọi robot tới bàn (thiếu binding), hoặc `robot_id` bridge ≠ `VOICE_ROBOT_ID` (`.env`) ≠ `robo-1` |
| Hủy / tắt loa / cuộc trò chuyện mới **không ăn gì** | Cùng nguyên nhân `no_device` như trên — 4 nút voice dùng chung binding bàn→robot. Web giờ nói thẳng ("Chưa kết nối được robot…") thay vì im lặng; đối chiếu T3 phải có `[CANCEL]`/`[MUTE]` |
| Bấm "Nói tiếp" sau khi Hủy/new chat thì **câm luôn** | Bug đã sửa 2026-07-20: cờ cancel dùng chung + guard busy khiến lượt đã hủy (còn kẹt trong lời gọi chặn) nuốt mọi `start_listening` sau đó. Dấu hiệu: T3 in `[BUSY] một lượt đang chạy`. Chưa `git pull` trên Jetson thì vẫn dính |
| Best Seller không vuốt được bằng tay (chỉ mũi tên/thanh cuộn chạy) | Bug đã sửa 2026-07-20 (`touch-action: pan-y` trên `.strip`). Cần **`make build` lại trên server** + reload trình duyệt robot — sửa CSS không tự tới máy khách |
| Bridge/voice lặp `[WS] mất kết nối` | Server chưa lên — tự retry, bật server xong tự nối |
| Panel không hiện robot / pin | `robot_node` (T1) chưa chạy → `/bat_vol` trống → bridge không có pin để gửi |
| Pin hiện sai % | Sai pack pin — chỉnh `battery_full_v`/`battery_empty_v` ở lệnh T2 (mặc định 3S 12.6/10.5) |
| `ModuleNotFoundError: websocket` | Chưa `sudo apt install python3-websocket` (bước ⓪) |
| Robot không có chấm minimap | ĐÚNG — chưa có localization (nav merge sau). Pin vẫn hiện bình thường |
| Web `:8000/` ra **404** | Chưa `make build` trên server (backend chỉ mount `dist/` khi có) — hoặc build xong quên **restart `make backend`** |
| Web mở được nhưng **trang trắng / menu trống** | Bundle gọi API qua `/api` mà không tới được: kiểm tra `curl -s :8000/api/menu`. Riêng `:8000/kiosk` + `:8000/panel` trắng thì thường do build bằng code cũ chưa có `base:` — pull rồi `make build` lại |
| Sửa web xong mà máy khách vẫn thấy bản cũ | Deploy giờ là **bản build tĩnh**, không hot-reload: phải `make build` + restart backend + reload trình duyệt (Ctrl-Shift-R) |
| `chromium-browser` chết (`snapd-snap.socket`, `gnome-46-2404`) | Bản chromium đó là snap mà snapd chết — dùng **Firefox deb** (bước ⓪). Test nhanh thì mở `:8000/` trên browser laptop, nút "nói chuyện" bấm từ máy nào cũng được |
| `firefox`: `Error: no DISPLAY` | Đang gõ qua SSH, thiếu display. `export DISPLAY=:0` + `export XAUTHORITY=/run/user/1000/gdm/Xauthority` rồi chạy lại (màn robot phải đang có desktop — mặc định autologin GNOME) |

---

## 7. Phần này KHÁC gì bản có nav đầy đủ

| Thành phần | Bản này (test voice/web) | Bản đầy đủ (nav merge sau) |
|---|---|---|
| Robot client `role=robot` | `ai_hw_bridge` — battery thật, **motion STUB** (`arrived` fire ngay) | `ai_hw_bridge` — nav owner thay STUB bằng Nav2 + ArUco |
| Vị trí robot (x,y) | Trống (chưa localization) | Từ TF `map→base_link` (RTAB-Map + EKF) |
| Chấm minimap | Không có | Có, chạy theo robot |
| Robot có chạy tới bàn | Không (đứng yên) | Có |

`ai_hw_bridge` (`robot_ws/src/real/`) hiện đóng vai **thay `make mockrobot`**: gửi pin thật + tạo binding
để test được vòng voice/web mà chưa cần nav. Khi nav merge xong, chỉ cần điền waypoint + thay 2 hàm
STUB `deliver_to`/`return_to_dock` trong `hw_delivery.py` bằng Nav2 thật.
