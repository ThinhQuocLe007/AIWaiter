# Tính năng: Web bấm "Nói chuyện với AI" → mic trên robot nghe (gán bàn động)

> Cập nhật 2026-06-27. Mục tiêu: khách mở web, bấm nút mic là nói được — không phải gõ tay
> `uv run main.py` mỗi lần, câu đầu không trễ vì nạp model, và **server tự biết voice từ bàn nào**
> dựa vào robot nào đang đứng ở bàn đó (không hardcode bàn cho từng thiết bị).

## Mô hình chốt: bind bàn↔robot động (dispatcher-driven)

Trước đây mỗi thiết bị mic gắn cứng 1 bàn qua env `VOICE_TABLE_ID`. Không hợp với robot di động:
robot được dispatcher điều tới bàn nào là tùy lúc. Giờ:

- **Mic đăng ký theo `robot_id`**, KHÔNG theo bàn: `role=voice-device&robot_id=robo-1` (cùng id với
  socket điều khiển `role=robot` của chính robot đó — 1 robot, 2 socket: motion + mic).
- **Server giữ map động `table → robot`.** Dispatcher set map này khi robot **tới bàn** (`on_arrived`
  → `manager.bind_table_robot`), xóa khi robot **rời bàn về dock** (`on_done` → `unbind_robot`),
  đứt kết nối, hoặc được điều sang bàn khác. Một robot phục vụ 1 bàn tại 1 thời điểm và ngược lại.
  Lưu ý: binding gắn với **sự hiện diện vật lý của robot** (vòng đời `role=robot`), KHÔNG theo socket
  mic — restart `main.py` không làm mất binding (mic xuống thì `send_to_voice_device` trả `no_device`
  cho tới khi mic lên lại).
- **Robot đứng phục vụ rồi mới rời khi khách xong.** Task `go_to_table`/`call`: robot tới bàn, **đứng
  lại** (khách nói chuyện được) cho tới khi khách **đặt món** (`POST /orders`) hoặc **thanh toán**
  (`/payments/verify`) → server gọi `dispatcher.release_robot_at_table` gửi `task.release` → robot
  báo `done` + về dock. Task `deliver` thì tự xong sau khi giao món.
- **Web bấm nút (bàn 3)** → `POST /voice/listen {table_id:3}` → server tra robot đang ở bàn 3 → gửi
  `start_listening{table_id:3}` tới mic robot đó → mic thu 1 lượt → `POST /chat {table_id:3,...}`.
  `table_id` do **server cấp theo từng lượt**, robot không cần tự biết mình ở bàn nào.

→ Server luôn biết "voice này từ bàn 3" vì chính nó chọn gửi lệnh tới robot đó với danh nghĩa bàn 3.

```
Dispatcher điều robot R → bàn 3,  R báo "arrived"
   backend:  bind_table_robot(3, "R")
Khách bấm "nói chuyện" trên tablet bàn 3
   POST /voice/listen {table_id:3}
   → table_to_robot[3]="R" → send tới _voice_devices["R"]: {start_listening, table_id:3}
   → mic robot R thu âm → POST /chat {table_id:3, text:...}
   → agent chạy LLM → mirror voice.heard/voice.reply về tablet bàn 3 (role=customer)
```

```
🎤 main.py (mic+VAD+STT) trên Jetson robot R       ┌──────── SERVER ────────┐
   role=voice-device, robot_id=R  ──WS──────────►  backend :8000 (ws hub)   │
        ▲  start_listening{table_id}              │   table_to_robot (bind)  │
   robo R cũng connect role=robot ──WS──arrived─► │   ▲ POST /voice/listen   │
        │  POST /chat{table_id} ─────────────────►  agent :8100 (LLM)        │
        └──────── voice.heard/reply ◄──── mirror về tablet bàn N ────────────┘
                                                   web :5173 (mirror, KHÔNG dùng mic)
```

- Web **không thu âm** (không `getUserMedia`) → **không cần HTTPS**. Mic luôn ở `main.py` trên robot.
- Web **không đổi**: vẫn gửi `table_id` từ `getStoredTableId()`. Mọi thay đổi nằm ở backend + device.

## Tại sao không "khởi động mic từ server" theo kiểu spawn process

Server **đã** điều khiển mic từ xa rồi — đó là `POST /voice/listen` → `start_listening`. Cái server
không làm được là *spawn tiến trình `main.py`* trên máy khác (browser/server sandbox). Giải pháp
production KHÔNG phải SSH bật tay từng robot, mà chạy `main.py` như **systemd service** (`Restart=
always`, auto-start lúc boot, có sẵn reconnect-backoff). Provision 1 lần (bake image / Ansible),
robot tự lên + tự kết nối lại. → việc còn lại: viết systemd unit (mục TODO).

## Đã làm gì (code) — đợt bind động

### Backend
- `src/backend/app/ws.py`:
  - `_voice_devices` đổi key từ `table_id` → `robot_id`. Gate `_robots` theo `role=="robot"` để
    socket mic (cùng id) không ghi đè socket motion.
  - Thêm map `_table_to_robot` + `bind_table_robot()` / `unbind_robot()` (mỗi robot 1 bàn, 2 chiều
    nhất quán).
  - `send_to_voice_device(table_id)` giờ tra `table → robot → socket`; `no_device` khi không có robot
    ở bàn hoặc mic của nó offline.
  - `ws_endpoint` bỏ query `table_id` (voice-device dùng `robot_id`).
- `src/backend/app/dispatcher.py`: `on_arrived` → `bind_table_robot` + đổi activity panel sang
  "Đang phục vụ · Bàn N"; `on_done`/`on_robot_disconnect` → `unbind_robot`; thêm
  `release_robot_at_table(table_id)` (gửi `task.release` tới robot đang ở bàn).
- `src/backend/app/routers/voice.py`: `start_listening` mang theo `table_id` để device tag `/chat`.
- `src/backend/app/routers/orders.py`: đặt món xong → `release_robot_at_table`.
- `src/backend/app/routers/payments.py`: thanh toán xong (cả 2 endpoint verify) → `release_robot_at_table`.
- `scripts/mock_robot.py`: `go_to_table`/`call` → arrived rồi **chờ `task.release`** mới `done` (thay
  vì tự xong sau 3s); `deliver` vẫn auto. Heartbeat giữ nguyên vị trí bàn khi đang phục vụ.

### Thiết bị có mic
- `ai_waiter_core/main.py`: `VOICE_TABLE_ID` → `VOICE_ROBOT_ID` (mặc định `robo-1`); đăng ký
  `role=voice-device&robot_id=<id>`; `_capture_and_send(..., table_id)` dùng `table_id` từ lệnh
  `start_listening` cho `POST /chat`, gửi dạng `"T<n>"` (agent yêu cầu chuỗi — fix lỗi 422).

### (Từ đợt trước, vẫn giữ)
- `vad_silero.py` cổng push-to-talk single-shot; `stt_phowhisper.py` `warmup()` chống trễ câu đầu.
- `config/agent_config.py` `LLM_KEEP_ALIVE` + ép kiểu; `server.py` lifespan `_warmup()` warm LLM/RAG.
- TTS vẫn TẮT (`ENABLE_TTS=False`) — phản hồi dạng chữ trên web.

## Cách chạy / test end-to-end (chưa có robot thật)

**Bố trí:** server chạy backend `:8000` + agent `:8100` + 3 web `:5173-5175` (`make backend`,
`make agent`, `make frontend`). Laptop đóng vai con robot `robo-1` = **2 tiến trình** (thân xác +
mic). IP netbird server ví dụ `100.66.165.221`.

> ⚠️ Backend chạy trên **server** (checkout git riêng): mọi thay đổi `src/backend/...` phải commit +
> push từ laptop rồi `git pull` ở server thì luồng release mới hoạt động.

**Terminal 1 — robot giả `robo-1` (thân xác, biết đi):**
```bash
make mockrobot ID=robo-1 ARGS="--host 100.66.165.221 --port 8000"
```
→ panel `:5175` hiện `robo-1` ở dock, pin 100%, "Đang ở dock".

**Terminal 2 — mic của `robo-1` (`main.py`, cùng `robot_id`):**
```bash
cd ai_waiter_core
VOICE_ROBOT_ID=robo-1 \
AGENT_URL=http://100.66.165.221:8100 \
ORCHESTRATOR_URL=http://100.66.165.221:8000 \
uv run python main.py
```
→ chờ `PhoWhisper warmup done` → `[READY] đã kết nối backend (robo-1)...`. Kiểm tra banner in đúng
IP (không thừa dấu chấm).

**Kích hoạt + nói chuyện (ví dụ bàn 4):**
1. **Seat bàn 4** — kiosk `:5174` check-in bàn 4, hoặc curl:
   ```bash
   curl -X POST http://100.66.165.221:8000/seatings \
        -H 'Content-Type: application/json' -d '{"table_id":4,"party_size":2}'
   ```
   → T1: `→ arrived (bàn 4)` → `→ đang phục vụ bàn 4, chờ khách...`. Panel: robot ở bàn 4,
   "Đang phục vụ · Bàn 4". Backend bind `bàn 4 → robo-1`.
2. **Trỏ tablet sang bàn 4:** customer_ui `:5173` chọn Bàn 4 (hoặc Console:
   `localStorage.setItem('robodish.tableId','4')` rồi F5).
3. **Bấm "Nói chuyện với AI"** → nói tiếng Việt → T2 in `[HEARD ... | bàn 4]` rồi `[WAITER]: ...`,
   web hiện bong bóng user→reply. Robot **vẫn đứng ở bàn 4**.
4. **Đặt món** (hoặc thanh toán) trên customer_ui → server gửi `task.release` → T1:
   `<- task.release` → `→ khách xong, rời bàn 4` → `→ done` → về dock. Panel: robot về dock.

**Nếu `no_device`:** chưa có robot `arrived` ở bàn đó (làm lại bước 1), bàn tablet lệch bàn seat, hoặc
`VOICE_ROBOT_ID` (T2) ≠ `--id` mock robot (T1).

**Reset data kẹt** (bàn không `TRONG` để seat): chạy ở server `make reset`.

## Việc còn lại

1. **systemd service** cho `main.py` (auto-start, reconnect) thay cho chạy tay `uv run` — giải quyết
   "không phải SSH bật từng robot".
2. Robot thật (`ws_client.py`, Mốc A) nói cùng contract như `mock_robot.py` (xử lý `task.assign` +
   `task.release`) và chạy `main.py` chung `robot_id`.
3. TTS (phát loa trên robot) — chưa code.

## Trạng thái hiện tại
- ✅ Backend: bind bàn↔robot động; robot đứng phục vụ, rời khi đặt món/thanh toán
  (`release_robot_at_table`). Compile OK.
- ✅ Device: `main.py` đăng ký theo `robot_id`, dùng `table_id` từ lệnh, gửi `"T<n>"` cho `/chat`.
- ✅ Mock robot: serve-and-wait theo `task.release`.
- ✅ Web: không cần đổi (vẫn gửi `table_id`).
- ✅ Chạy thử: nghe + nhận dạng + định tuyến đúng bàn (đã thấy `[HEARD ... | bàn 4]`). Fix 422.
- ⬜ Chưa verify trọn vòng release (đặt món → robot về dock) trên server có code mới.
- ⬜ Backend mới cần `git pull` ở server. systemd service chưa viết.
