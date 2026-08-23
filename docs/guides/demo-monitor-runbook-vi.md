# Runbook demo voice + agent — PC, Jetson, màn rời

Buổi demo này **chỉ có voice và agent**, robot không di chuyển. Người xem nhìn vào màn hình
"Đường tín hiệu" (`/monitor`) thấy từng chặng sáng lên khi mình nói.

Ai chạy cái gì:

```
   PC (server)                          JETSON (thiết bị voice)
   ┌──────────────────────────┐         ┌──────────────────────────┐
   │ make backend   :8000     │◀──WS────│ mic → VAD → Whisper      │
   │   hub + web /monitor     │         │ loa ← TTS                │
   │ make agent     :8100     │◀──HTTP──│ (make jetson STACK=0)    │
   │   LangGraph + LLM        │         └───────────┬──────────────┘
   └──────────────────────────┘                     │ HDMI
              ▲                                     ▼
              │ trình duyệt                 ┌──────────────────┐
              └─────────────────────────────│ MÀN RỜI          │
                cùng một trang /monitor     │ /monitor kiosk   │
                                            └──────────────────┘
```

Màn rời của Jetson **chỉ hiển thị**. Nút bấm nên để trên máy PC — xem [mục 3](#3-màn-rời-và-ai-bấm-nút).

---

## 0. Làm một lần, trước ngày demo

### 0.1 PC — cài đủ thư viện server

Venv trên PC hiện thiếu `fastapi`/`uvicorn`, `make backend` sẽ không chạy. Cài trước:

```bash
cd ~/AIWaiter
make install UV_EXTRAS="--extra server --extra cu13"   # cu12 nếu máy chạy CUDA 12
.venv/bin/python -c "import fastapi, uvicorn; print('server deps OK')"
```

### 0.2 PC — build web (bắt buộc, nếu không sẽ không có `/monitor`)

```bash
make build          # build cả 4 web: customer_ui, kiosk, panel, monitor
```

> Chạy lại `make build` sau **mỗi lần** sửa code frontend. Bản `:8000/monitor` là bản đã build,
> không tự cập nhật.

### 0.3 Jetson — đồng bộ code voice mới

Máy Jetson phải có bản [`src/edge_voice/main.py`](../../src/edge_voice/main.py) mới nhất (lớp
`Telemetry`). Thiếu nó thì rack trên màn hình đứng im, chỉ mỗi ô AGENT sáng.

```bash
# trên Jetson
cd /home/orin/AI_voice/AIWaiter
git pull            # KHÔNG chạy `uv sync` trần — xem jetson-boot-runbook-vi.md mục 0a
grep -c "class Telemetry" src/edge_voice/main.py    # phải ra 1
```

### 0.4 Kiểm tra IP hai máy nhìn thấy nhau

Hai máy nói chuyện qua Netbird, IP cố định:

| Máy | Tên Netbird | IP |
|-----|-------------|-----|
| PC (server: hub + agent + web) | `ducduy-pc` | **100.66.165.221** |
| Jetson (mic + loa + màn rời) | `orin-desktop` | **100.66.136.17** |

Từ PC vào Jetson khỏi phải chuyển bàn phím: `ssh orin@100.66.136.17`.

File `.env` **trên Jetson** phải trỏ về PC:

```bash
AGENT_URL=http://100.66.165.221:8100
ORCHESTRATOR_URL=http://100.66.165.221:8000
VOICE_ROBOT_ID=robo-1
```

Thử hai chiều, cả hai đều phải trả lời ngay chứ không treo:

```bash
# trên Jetson — thấy được server chưa
curl -s http://100.66.165.221:8000/voice/devices

# trên PC — thấy được Jetson chưa
ping -c2 100.66.136.17
```

---

## 1. Ngày demo — bật PC trước

Ba terminal trên PC, đúng thứ tự này:

```bash
# T1 — hub + web (giữ terminal này chạy)
cd ~/AIWaiter && make backend
#   chờ dòng: Application startup complete.

# T2 — agent LLM (lần đầu lâu, nó rebuild embeddings trước)
cd ~/AIWaiter && make agent
#   chờ nó nghe ở :8100

# T3 — kiểm tra nhanh, rồi đóng terminal này cũng được
curl -s http://localhost:8000/voice/devices     # {"devices":[],"default_table_id":1}
curl -s http://localhost:8100/health            # agent còn sống
```

`devices` đang rỗng là **đúng** — Jetson chưa bật.

Mở trình duyệt trên PC: `http://localhost:8000/monitor`. Góc phải phải hiện **Hub realtime**
màu mint. Nếu hiện "Mất kết nối hub" thì `make backend` chưa lên.

---

## 2. Bật Jetson

### 2.1 Boot và health check — luôn làm đầu tiên

Cắm điện, cắm **mic USB**, **loa USB**, **màn rời qua HDMI**, bật nguồn, rồi **đăng nhập vào
desktop** trên màn rời.

Phải đăng nhập desktop thật vì trình duyệt kiosk cần phiên đồ hoạ `:0` đang sống. Nhưng sau khi
đã đăng nhập rồi thì gõ lệnh qua SSH từ PC vẫn được — [`scripts/jetson_run.sh`](../../scripts/jetson_run.sh)
tự set `DISPLAY=:0` và `XAUTHORITY` nên trình duyệt vẫn hiện ra đúng màn rời.

```bash
cd /home/orin/AI_voice/AIWaiter
bash scripts/jetson_healthcheck.sh
```

Phải ra `══ n OK, 0 LỖI ══`. Có dòng `[LỖI]` thì sửa theo hướng dẫn ngay trên dòng đó —
chi tiết ở [`jetson-demo-runbook-vi.md`](jetson-demo-runbook-vi.md) mục 3.

> Cái bẫy hay gặp nhất là **đường âm thanh**: mất điện xong PulseAudio quay về sink mặc định của
> board (jack analog trống hoặc HDMI không loa). Chạy không lỗi, log sạch, mà câm như hến.
> Health check bắt được ca này ở hai dòng `default sink` / `default source`.

### 2.2 Một lệnh chạy cả buổi

```bash
make jetson STACK=0 URL=http://100.66.165.221:8000/monitor
```

Lệnh này làm 2 việc:

| Phần | Nội dung |
|------|----------|
| `voice` | mic → VAD → Whisper → gọi agent → TTS ra loa |
| `web` | chờ backend trả lời rồi mở trình duyệt **kiosk toàn màn hình** trên màn rời, vào thẳng `/monitor` |

`STACK=0` bỏ qua ROS (RTAB-Map + Nav2). Buổi này robot đứng yên, mà stack đó nặng — và nếu nó
chết thì kéo luôn voice chết theo.

Đợi tới khi thấy:

```
[voice] ==================================================
[voice]  AI Waiter voice device — Robot robo-1
[voice]  Models warmed. ...
[web] mở firefox --kiosk http://100.66.165.221:8000/monitor
```

Robot nói "Xin chào" ra loa = TTS sống. Lúc này trên `/monitor` ở PC, ô chọn thiết bị chuyển từ
"chưa có mic nào" thành `robo-1`, các nút sáng lên.

Ctrl-C **một lần** trong terminal này là tắt sạch cả voice lẫn trình duyệt.

---

## 3. Màn rời và ai bấm nút

Cả hai màn hình mở **cùng một trang** và cùng nhận realtime từ hub — mở bao nhiêu bản cũng được.
Chia vai như sau:

- **Màn rời của Jetson**: kiosk toàn màn hình, để thầy nhìn. Không cần chuột.
- **Màn PC**: bạn bấm **Bắt đầu nghe** từ đây, rồi nói vào mic của Jetson.

Làm vậy vì trong chế độ kiosk không có thanh địa chỉ và thường không có chuột cắm ở Jetson.
Nếu Jetson có chuột/màn cảm ứng thì bấm ngay trên đó cũng được, không khác gì.

Muốn màn rời hiển thị trang khác thì đổi `URL=`, ví dụ `URL=http://100.66.165.221:8000/panel`.

### Màn 7" 1024×600

Trang `/monitor` có bố cục riêng cho màn này: cả rack vừa trong 600px, **không cuộn trang**, chỉ
ô *Hội thoại* và *Nhật ký sự kiện* cuộn bên trong. Điều kiện kích hoạt là chiều cao khung hiển
thị **≤ 700px**, nên hai thứ này phải đúng, nếu không nó rơi về bố cục desktop và tràn khỏi màn:

- **Zoom trình duyệt phải là 100%** (`Ctrl+0`). Zoom 125% biến 600px vật lý thành 480px CSS thì
  vẫn gọn, nhưng zoom 80% thành 750px CSS là mất bố cục gọn.
- **Phải toàn màn hình** (kiosk hoặc `F11`). Thanh tiêu đề + tab của cửa sổ thường ăn mất khoảng
  100px chiều cao, làm nội dung bị cắt ở đáy.

Kiểm tra nhanh: nhìn thấy dòng phụ *"Tiếng nói vào ở đầu này…"* dưới tiêu đề nghĩa là **đang ở bố
cục desktop** — bố cục 7" giấu dòng đó đi.

---

## 4. Kịch bản nói thử (60 giây)

1. Bấm **Bắt đầu nghe** → ô `MIC` sáng hổ phách, ghi "đang thu".
2. Nói: *"cho tôi một tô phở bò tái nạm"*.
3. Nhìn theo tín hiệu chạy: `VAD` chốt độ dài câu → `STT` hiện số ms của Whisper và câu chép được
   → `AGENT` sáng "đang nghĩ" → từng câu trả lời hiện dần ở khung Hội thoại → `TTS` đọc ra loa.
4. Bấm lần nữa, nói *"thêm một trà đá"* — lượt thứ hai ngắn hơn, **Sổ đo** giờ có 2 thanh để
   so sánh: nhìn là thấy thời gian nằm ở chặng nào.
5. Muốn cho thấy nó chạy thật tới cùng: nói *"chốt đơn cho tôi"* → đơn hiện thật trên
   `http://100.66.165.221:8000/panel` (bảng bếp). Nhớ `make reset` sau buổi demo.

Giải thích ngắn nếu thầy hỏi số liệu ở đâu ra: Jetson đo phần của nó (khách nói bao lâu, Whisper
bao lâu), server đo phần của nó (bao lâu tới câu đầu, tổng LLM); đồng hồ của agent bắt đầu **sau**
khi STT xong nên hai số cộng lại chứ không chồng nhau. Chi tiết:
[`voice-monitor-vi.md`](voice-monitor-vi.md).

---

## 5. Gỡ rối tại chỗ

| Triệu chứng | Nguyên nhân thường gặp | Xử lý |
|---|---|---|
| Trang ghi "Mất kết nối hub" | `make backend` chưa chạy / sai IP | Bật lại T1, kiểm tra mở `:8000` |
| Ô thiết bị mãi là "chưa có mic nào" | Jetson chưa nối được hub | Trên Jetson: `curl http://100.66.165.221:8000/voice/devices`. Treo = mạng Netbird; ra JSON = `make jetson` chưa chạy |
| Bấm nghe, hiện "Mic không nhận lệnh" | Jetson vừa rớt kết nối | Danh sách tự làm mới mỗi 5 giây — đợi rồi chọn lại thiết bị |
| `MIC` đỏ "không nghe thấy" | Sai default source, hoặc nói quá nhỏ/xa | Chạy lại health check, xem 2 dòng mic/loa |
| Nghe được nhưng không có tiếng trả lời | Loa mute hoặc sai default sink | `pactl set-sink-mute @DEFAULT_SINK@ 0` và `pactl set-sink-volume @DEFAULT_SINK@ 45%` |
| `STT` đỏ "không dùng được" | Whisper ra rỗng, **hoặc** bộ lọc chặn câu bịa | Bình thường khi có tiếng động lạ. Xem log `[voice] STT bỏ qua…` |
| `AGENT` sáng mãi | LLM chưa xong hoặc agent chết | Xem terminal `make agent` |
| Rack đứng im, chỉ `AGENT` sáng | Jetson chạy code cũ, chưa có telemetry | Làm lại [mục 0.3](#03-jetson--đồng-bộ-code-voice-mới) |
| Màn rời không mở trình duyệt | Chưa đăng nhập desktop nên chưa có phiên `:0` | Đăng nhập trên màn rời rồi chạy lại; hoặc mở tay Firefox vào URL đó rồi F11 |

---

## 6. Tắt

```bash
# Jetson: Ctrl-C một lần trong terminal `make jetson`
# PC:
make reset      # xoá đơn demo, trả bàn về trống (backend phải còn chạy)
make kill       # tắt backend + agent + các dev server
```

---

## Dán lên tường

```
PC:      make backend        (T1)
         make agent          (T2)
         mở localhost:8000/monitor

JETSON:  bash scripts/jetson_healthcheck.sh      → phải 0 LỖI
         make jetson STACK=0 URL=http://100.66.165.221:8000/monitor

NÓI:     bấm "Bắt đầu nghe" trên PC → nói vào mic Jetson
```
