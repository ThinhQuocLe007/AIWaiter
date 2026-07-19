# Chuẩn bị merge navigation + localization vào e2e thật

> Trạng thái tại 2026-07-19: tầng voice trên Jetson (VAD → STT → agent → TTS) đã xong và chạy
> độc lập được. Tầng **motion** (Nav2 + AMCL trên robot thật) chưa có. Doc này ghi đúng những gì
> còn thiếu để ghép hai tầng lại thành e2e giống bên sim.
>
> Vận hành hằng ngày xem [jetson-boot-runbook-vi.md](jetson-boot-runbook-vi.md).
> Kiến trúc voice xem [run-voice-vi.md](run-voice-vi.md).

**File này là bản bàn giao.** Nav xong thì đưa lại nguyên file để làm tiếp — §5 ghi việc còn
lại đủ chi tiết để bắt tay vào code ngay, §6 ghi những thứ cần biết về robot thật.

## 0. Trạng thái

| Phần | Trạng thái |
|---|---|
| Mic + Silero VAD + gate push-to-talk | ✅ chạy |
| Whisper STT (`medium`, faster-whisper) | ✅ chạy |
| Piper TTS offline + edge-tts fallback | ✅ chạy |
| Barge-in (khách nói chen → cắt TTS) | ✅ chạy ([tts_engine.py:141](../../src/edge_voice/output/tts_engine.py#L141)) |
| WS client `role=voice-device` + reconnect backoff | ✅ chạy |
| Cancel / mute từ tablet | ✅ chạy |
| `edge_voice` độc lập khỏi extra `server` | ✅ xong 2026-07-19 |
| Bug `duration` sai 2× khi flush utterance | ✅ sửa 2026-07-19 |
| **Bridge robot `role=robot` (nav)** | ⬜ **chặn e2e** — §2, §3 |
| Sàn độ dài utterance (chống Whisper bịa) | ⬜ §5.1 — *không phụ thuộc nav* |
| Autostart khi boot (systemd) | ⬜ §5.2 |

`src/edge_voice/` không còn `TODO`/stub nào — ba ô trống ở trên là toàn bộ phần chưa code
trên Jetson.

## 1. Hai tầng ghép với nhau ở đâu

Voice và motion là **hai process rời**, không import lẫn nhau. Chúng gặp nhau ở backend, qua hai
WS role khác nhau:

```
                         ┌──────────── SERVER ────────────┐
   Jetson                │  backend :8000  ·  agent :8100 │
   ├─ make voice  ───────┼─► /ws?role=voice-device&robot_id=robo-1
   └─ node nav (ROS2) ───┼─► /ws?role=robot&robot_id=robo-1
                         └────────────────────────────────┘
```

**Ràng buộc duy nhất giữa hai bên là `robot_id` phải trùng nhau.** Backend resolve
`bàn → robot_id → socket mic` ([connection_manager.py:103-114](../../src/server_orchestrator/realtime/connection_manager.py#L103-L114)),
nên `VOICE_ROBOT_ID` trong `.env` phải bằng `robot_id` mà node nav đăng ký. Sai là mic connect
thành công, log không báo gì, nhưng bấm nút trên tablet trả `no_device`.

Hệ quả tốt: code nav của bạn merge vào **không đụng một dòng nào** của `src/edge_voice/`.

## 2. Contract mà node nav phải nói

Copy nguyên từ bản sim đã chạy được — [`ai_sim_bridge/task_bridge.py`](../../robot_ws/src/sim/ai_sim_bridge/ai_sim_bridge/task_bridge.py).
Bản mock (không ROS) ở [`scripts/mock_robot.py`](../../scripts/mock_robot.py) nói cùng contract.

```
server → robot : task.assign {task_id, kind, table_id}   ·  task.release {table_id}
robot → server : task_accepted / arrived / task_done {task_id}  ·  at_dock
                 heartbeat {robot_id, battery, x, y}     (map frame)
```

Vòng đời task — **chỗ dễ làm sai nhất là `go_to_table`**:

| kind | Luồng |
|---|---|
| `go_to_table`, `call` | accept → chạy tới bàn → `arrived` → **đứng chờ tại bàn** (khách đang nói chuyện với robot) → chỉ khi server gửi `task.release` mới `task_done` → về dock → `at_dock` |
| `deliver` | accept → chạy tới bàn → `arrived` → dừng ~5s cho khách lấy đồ → `task_done` → về dock → `at_dock` |

`task.release` được backend phát khi khách đặt món (`POST /orders`) hoặc thanh toán
(`/payments/verify`). **`arrived` chính là thứ tạo binding bàn cho mic** — dispatcher set binding
khi nhận `arrived` ([dispatcher.py:355](../../src/server_orchestrator/services/dispatcher.py#L355)).
Nav không gửi `arrived` = nút "nói chuyện" trên tablet vĩnh viễn `no_device`.

Heartbeat phải chạy **suốt đời process** (cả lúc idle lẫn lúc đang phục vụ), vì panel minimap vẽ
chấm robot từ đó. Toạ độ trong **map frame**, cùng frame với `restaurant.pgm`.

## 3. Việc cần làm — checklist

### 3.1 Toạ độ bàn đang hardcode ở 3 nơi

Đây là món nợ dễ cắn nhất khi đổi từ map sim sang map nhà hàng thật. Cùng một bộ số, chép tay 3 chỗ:

| File | Biến | Dùng để |
|---|---|---|
| [`food_delivery.py:47`](../../robot_ws/src/sim/turtlebot4_python_tutorials/turtlebot4_python_tutorials/food_delivery.py#L47) | `DESTINATIONS` | Waypoint + góc tiếp cận Nav2 thật sự chạy tới |
| [`dispatcher.py:51`](../../src/server_orchestrator/services/dispatcher.py#L51) | `TABLE_POS` | Chấm điểm "robot rảnh nào gần bàn nhất" |
| [`mock_robot.py:40`](../../scripts/mock_robot.py#L40) | `TABLE_POS` | Robot giả đi tới đâu |

Thêm `TABLE_MARKER_POS` + `DOCK_POS` trong `dispatcher.py:65` (vị trí icon bàn trên minimap) và
file map `restaurant.pgm` / `restaurant.yaml` mà [`layout.py:28`](../../src/server_orchestrator/routers/layout.py#L28) đọc.

**Khi có map thật phải sửa hết ngần đó chỗ, nếu không:** robot chạy đúng nhưng dispatcher chọn sai
robot gần nhất, và minimap vẽ bàn lệch chỗ.

### 3.2 Node nav chạy trong venv hay ngoài?

Đã đo thực tế trên máy dev (x86 + ROS2 Humble), **cả hai đều được**:

```bash
source /opt/ros/humble/setup.bash
.venv/bin/python -c "import rclpy, tf2_ros; from geometry_msgs.msg import Twist; ..."
# → rclpy + tf2 + publish message CHẠY được trong .venv, numpy 2.2.6 không xung đột
```

Chạy được vì `pyproject.toml` pin `requires-python = ">=3.10,<3.11"` đúng bằng python của ROS
Humble — pin đó không phải ngẫu nhiên. Source ROS xong thì `PYTHONPATH` chèn thêm 2 đường dẫn ROS
vào `sys.path` của venv, nhưng không che mất `numpy`/`torch` của venv (ROS không ship numpy riêng).

Chiều ngược lại cũng an toàn: import cả `src.edge_voice.main` khi đã source ROS vẫn OK.

> ⚠️ Mới chỉ đo trên **x86**. Trên Jetson aarch64 phải chạy lại đúng 2 lệnh trên để xác nhận,
> vì torch ở đó là 2.11.0 từ index jetson-ai-lab chứ không phải 2.5.1 cu121.

Khuyến nghị: cứ giữ **2 process riêng** (`make voice` và node nav) dù chung venv được — một bên
crash không kéo bên kia chết, và log tách bạch lúc demo.

### 3.3 Thứ tự làm

1. **SLAM map nhà hàng thật** → `restaurant.pgm` + `.yaml`, đo waypoint từng bàn + dock.
2. **Cập nhật 3 chỗ toạ độ** ở §3.1 (cân nhắc gộp về một nguồn duy nhất luôn thể).
3. **Viết node nav thật**: copy `ai_sim_bridge/task_bridge.py`, giữ nguyên phần WS/heartbeat/vòng
   đời task, thay `deliver_to()` / `return_to_dock()` bằng Nav2 + AMCL của robot thật.
4. **Test riêng motion**: chưa cần voice. Chạy node nav + backend, seat bàn, gọi robot → xem panel
   có `task N arrived (table 1)` và chấm minimap chạy đúng không.
5. **Ghép voice**: `make voice` trên Jetson với `VOICE_ROBOT_ID` = `robot_id` của node nav → bấm
   "nói chuyện" trên tablet.

Bước 4 tách khỏi 5 là cố ý: mỗi lần chỉ debug một tầng.

## 4. Chạy được ngay hôm nay (chưa có nav)

Muốn test full luồng voice trước khi nav xong thì cần một client `role=robot` giả để tạo binding:

```bash
make mockrobot ID=robo-1        # chạy ở server cũng được, id phải trùng VOICE_ROBOT_ID
```

Rồi làm tiếp từ mục 3 của [jetson-boot-runbook-vi.md](jetson-boot-runbook-vi.md). Đây đúng là
đường đang dùng cho demo sim, chỉ khác mic nằm trên Jetson thật thay vì laptop.

---

## 5. Việc còn lại phía voice — bàn giao

Hai mục dưới **không phụ thuộc nav**, có thể làm bất cứ lúc nào. Ghi đủ chi tiết để bắt tay vào
code mà không phải dò lại từ đầu.

### 5.1 Sàn độ dài utterance — chống Whisper bịa

**Triệu chứng.** Whisper `medium` gặp đoạn âm thanh quá ngắn (< ~1s) thì bịa ra câu học từ dữ
liệu YouTube: *"Hãy subscribe cho kênh Ghiền Mì Gõ"*, *"Cảm ơn các bạn đã theo dõi"*. Không phải
lỗi mic — là hành vi đã biết của Whisper. Robot đọc câu đó ra loa giữa lúc demo.

**Nguyên nhân.** [`vad_silero.py`](../../src/edge_voice/perception/vad_silero.py) cắt utterance khi
im lặng đủ `SILENCE_TIMEOUT = 1.5s`, nhưng **không có sàn dưới**: một tiếng động 0.1s (kéo ghế,
gõ bàn) vẫn được flush thẳng vào STT.

**Chỗ sửa.** Ngay trước `put_speech(...)` trong `run()` — chỗ đã tính sẵn `duration`:

```python
duration = len(audio) / BYTES_PER_SAMPLE / SAMPLE_RATE
# thêm: quá ngắn -> vứt, coi như chưa nghe thấy gì
```

**Lưu ý quan trọng khi làm:** `duration` từng bị tính sai gấp đôi (chia byte cho `SAMPLE_RATE` mà
quên int16 = 2 byte/mẫu) — **đã sửa 2026-07-19**. Nếu bạn thấy code chỗ này khác đi thì kiểm tra
lại trước khi chọn ngưỡng, ngưỡng 0.4s trên số phồng 2× thực chất chỉ lọc được 0.2s.

**Quyết định cần chốt khi làm:**
- Ngưỡng bao nhiêu? Đề xuất `MIN_UTTERANCE_S` đọc từ env, mặc định `0.4`, để chỉnh tại chỗ theo
  độ ồn thật của quán mà không phải sửa code + build lại.
- Vứt im lặng, hay vẫn báo cho khách? Utterance bị vứt thì `wait_for_utterance()` không fire →
  khách bấm nút mà không thấy gì xảy ra. Cân nhắc: gate **không** tự đóng khi vứt, tiếp tục nghe
  cho hết `UTTERANCE_TIMEOUT` (15s) rồi mới `[TIMEOUT]`. Cách này khách chỉ thấy "robot chờ lâu
  hơn một nhịp" thay vì "robot nói nhảm".

**Cách test không cần nhà hàng:** `make probe` rồi gõ nhẹ lên bàn / hắng giọng — trước khi sửa sẽ
thấy câu bịa, sau khi sửa phải im.

### 5.2 Autostart khi boot (systemd)

Repo hiện **không có file `.service` nào**. "Bật Jetson lên" đang có nghĩa là SSH vào gõ tay, và
đóng SSH là process chết theo.

Cần 2 unit (unit nav chỉ viết được sau khi có §3.3 bước 3):

| Unit | Chạy gì | Ghi chú |
|---|---|---|
| `ai-waiter-voice.service` | `.venv/bin/python src/edge_voice/main.py` | `Restart=always`. **Không** cần `After=` backend — voice tự retry WS với backoff tới 10s, bật trước lúc server chưa lên vẫn đúng |
| `ai-waiter-nav.service` | node ROS2 nav | Cần source `/opt/ros/humble` + workspace overlay trong `ExecStart` |

Hai cái độc lập nhau, không cần `After=` lẫn nhau.

**Bẫy đã biết:** `WorkingDirectory=` phải là repo root, vì `make voice` và `.env` đều dựa vào
đường dẫn tương đối từ đó. Và unit phải chạy dưới đúng user có quyền audio (nhóm `audio`), không
phải `root` — chạy root thì PortAudio nhìn thấy danh sách thiết bị khác.

---

## 6. Nav xong rồi — cần biết gì để làm tiếp

Đưa lại file này kèm mấy thông tin sau, càng cụ thể càng đỡ phải hỏi lại:

1. **Node nav tên gì, nằm ở đâu** — package ROS2 tên gì, `ros2 run <pkg> <exec>` ra sao, có
   launch file không.
2. **Dùng Nav2 chuẩn hay tự viết controller?** Nếu Nav2 thì bridge copy được gần như nguyên xi từ
   [`task_bridge.py`](../../robot_ws/src/sim/ai_sim_bridge/ai_sim_bridge/task_bridge.py); nếu tự
   viết thì cần biết API gọi "đi tới toạ độ (x, y, yaw)" và cách biết đã tới nơi.
3. **Localization ra pose ở frame nào** — bridge cần `map → base_link` để bơm heartbeat. AMCL
   chuẩn thì đúng luôn; nếu dùng frame khác phải khai qua param `map_frame`/`base_frame`.
4. **File map thật** — `.pgm` + `.yaml`, và toạ độ approach từng bàn + dock (kèm góc yaw).
   Xem §3.1 để biết phải chép vào những đâu.
5. **Có ArUco marker ở bàn không?** Bản sim dùng ArUco để căn chính xác chặng cuối
   (`deliver_to()`). Không có thì bỏ, chỉ Nav2 tới waypoint là xong.
6. **Robot có báo pin thật không?** Sim fix cứng 100%. Có pin thật thì heartbeat gửi số thật,
   panel hiện đúng.
7. **Kết quả 2 lệnh kiểm tra ở §3.2 chạy trên Jetson aarch64** — mới chỉ đo trên x86.
