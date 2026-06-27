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
  → `manager.bind_table_robot`), xóa khi robot rời/đứt kết nối (`on_robot_disconnect` /
  socket mic đóng → `unbind_robot`). Một robot phục vụ 1 bàn tại 1 thời điểm và ngược lại.
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
- `src/backend/app/dispatcher.py`: `on_arrived` → `bind_table_robot(table, robot)`;
  `on_robot_disconnect` → `unbind_robot(robot)`.
- `src/backend/app/routers/voice.py`: `start_listening` mang theo `table_id` để device tag `/chat`.

### Thiết bị có mic
- `ai_waiter_core/main.py`: `VOICE_TABLE_ID` → `VOICE_ROBOT_ID` (mặc định `robo-1`); đăng ký
  `role=voice-device&robot_id=<id>`; `_capture_and_send(..., table_id)` dùng `table_id` từ lệnh
  `start_listening` cho `POST /chat` (không còn bàn cố định trong env).

### (Từ đợt trước, vẫn giữ)
- `vad_silero.py` cổng push-to-talk single-shot; `stt_phowhisper.py` `warmup()` chống trễ câu đầu.
- `config/agent_config.py` `LLM_KEEP_ALIVE` + ép kiểu; `server.py` lifespan `_warmup()` warm LLM/RAG.
- TTS vẫn TẮT (`ENABLE_TTS=False`) — phản hồi dạng chữ trên web.

## Cách test end-to-end trên laptop (chưa có robot thật)

Vì bind là dispatcher-driven, cần một robot "tới bàn" để có binding. Dùng `scripts/mock_robot.py`:

```bash
# 1) backend :8000, agent :8100 đang chạy
# 2) mic device (cùng robot_id với mock robot)
cd ai_waiter_core
VOICE_ROBOT_ID=robo-1 \
AGENT_URL=http://<server>:8100 ORCHESTRATOR_URL=http://<server>:8000 \
uv run python main.py
# 3) robot giả: connect role=robot, nhận task, báo arrived → backend bind table→robo-1
uv run python scripts/mock_robot.py --id robo-1
# 4) tạo task điều robo-1 tới đúng bàn tablet (vd bàn 3) — qua kiosk/seat hoặc API tạo task
# 5) sau khi mock in "arrived", bấm "nói chuyện" trên tablet bàn 3 → nói tiếng Việt
```

- ⚠️ Lưu ý timing: `mock_robot.py` báo `arrived` rồi ~3s sau báo `done` và chạy về dock. Binding
  **không** bị xóa lúc `done` (chỉ xóa khi robot đứt kết nối hoặc được điều sang bàn khác), nên mic
  vẫn phục vụ bàn đó tới khi robot rời đi — đủ để test bấm nút.
- Kỳ vọng: terminal mic in `[HEARD ... | bàn 3]`, tablet bàn 3 hiện bong bóng user→reply.
- Nếu `no_device`: chưa có robot nào `arrived` ở bàn đó, hoặc `VOICE_ROBOT_ID` ≠ `--id` mock robot.

## Việc còn lại

1. **systemd service** cho `main.py` (auto-start, reconnect) thay cho chạy tay `uv run` — giải quyết
   "không phải SSH bật từng robot".
2. **Tinh chỉnh rule unbind khi robot rời bàn**: hiện chỉ unbind lúc disconnect / điều sang bàn khác.
   Khi lifecycle robot rõ hơn (robot đứng phục vụ bao lâu, lúc nào rời) có thể unbind chính xác hơn
   (vd theo trạng thái bàn về `TRONG`/thanh toán xong).
3. Robot thật (`ws_client.py`, Mốc A) nói cùng contract như `mock_robot.py` + chạy `main.py` chung
   robot_id.
4. TTS (phát loa trên robot) — chưa code.

## Trạng thái hiện tại
- ✅ Backend: bind bàn↔robot động, `/voice/listen` tra table→robot→mic. Compile OK.
- ✅ Device: `main.py` đăng ký theo `robot_id`, dùng `table_id` từ lệnh cho `/chat`.
- ✅ Web: không cần đổi (vẫn gửi `table_id`).
- ⬜ Chưa chạy thử end-to-end với `mock_robot.py` trên máy thật.
- ⬜ systemd service chưa viết.
