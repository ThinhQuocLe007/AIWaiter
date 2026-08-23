# Màn hình giám sát voice — "Đường tín hiệu"

Trang web dựng riêng để **cho người khác xem bộ voice + agent chạy thật**: nói vào mic của robot,
màn hình hiện từng chặng sáng lên theo đúng thứ tự tín hiệu đi qua, kèm số mili-giây thật đo được
ở từng chặng.

Khác với 3 web nhà hàng (`customer_ui`, `kiosk`, `panel`) — vốn phục vụ khách và bếp — trang này
không phục vụ ai trong nhà hàng cả. Nó chỉ có một việc: **làm cho một pipeline vô hình nhìn thấy
được**, và chứng minh các con số là thật chứ không phải hoạt cảnh.

URL: `http://<SERVER_IP>:8000/monitor` (production) hoặc `http://localhost:5176` (`make monitor`).

---

## 1. Màn hình có gì

| Khu vực | Đọc cái gì ở đó |
|---------|-----------------|
| **Rack tín hiệu** (hàng trên) | 5 module `MIC → VAD → STT → AGENT → TTS`. Module đang chạy sáng hổ phách, dây nối vào nó có xung sáng chạy. Module đã xong đổi sang màu mint kèm số đo. Module lỗi chuyển đỏ đất. |
| **Hội thoại** | Đúng những gì robot **nghe** và **nói**. Lượt đang chạy nằm trên cùng và điền dần: nghe được trước, rồi từng câu trả lời hiện ra đúng lúc agent sinh ra nó. |
| **Sổ đo** | Mỗi lượt một thanh, chia đoạn theo chặng: *khách nói · Whisper · LLM tới câu đầu · robot nói*. Tất cả các thanh vẽ theo cùng một thang, nên nhìn là biết thời gian đi đâu và lượt nào chậm bất thường. |
| **Nhật ký sự kiện** | Từng frame một, ghi rõ do **THIẾT BỊ** (Jetson) hay **AGENT** (server) gửi. Đây là phần chứng minh số liệu có nguồn gốc. |

Nút điều khiển: **Bắt đầu nghe** · **Dừng** · **Hội thoại mới** (xoá trí nhớ hội thoại của bàn) ·
**Tắt loa** (robot vẫn trả lời, chỉ không phát tiếng).

---

## 2. Số liệu ở đâu ra

Hai nguồn độc lập, không nguồn nào thấy hết một lượt:

```
Jetson (edge_voice/main.py)                    Server (agent_brain/server.py)
  telemetry qua WS role=voice-device             POST /voice/event
       │                                              │
       │  listening / transcribing / heard            │  voice.heard
       │  thinking / speaking / done                  │  voice.sentence  ← từng câu, kèm at_ms
       │  timeout / empty / cancelled / error         │  voice.reply     ← kèm first_sentence, llm_total
       ▼                                              ▼
              orchestrator hub  ──broadcast role=monitor──▶  trang này gộp lại thành 1 lượt
```

* Jetson đo phần chỉ nó biết: khách nói bao lâu, Whisper mất bao lâu, câu nào đang phát ra loa.
* Agent đo phần chỉ nó biết: bao lâu tới câu đầu tiên, tổng thời gian LLM, giai đoạn hội thoại.
* Đồng hồ của agent bắt đầu **sau** khi STT xong, nên hai con số cộng lại chứ không chồng lên nhau.

`voice.sentence` là sự kiện **chỉ monitor mới nhận** — tablet khách vẫn nhận nguyên câu trả lời
hoàn chỉnh như cũ, không bị bắn từng mảnh.

---

## 3. Chạy demo

Cần 3 tiến trình. Đúng thứ tự này:

```bash
# 1. Trên SERVER (máy PC) — hub + web
make backend                 # http://0.0.0.0:8000

# 2. Trên SERVER — agent LLM
make agent                   # http://0.0.0.0:8100

# 3. Trên JETSON — mic + Whisper + TTS
make voice
```

Rồi mở `http://<SERVER_IP>:8000/monitor`.

> Nếu đang sửa code frontend thì chạy `make monitor` (cổng 5176, hot reload) thay vì mở qua :8000.
> Bản production phải `make build` lại thì :8000/monitor mới thấy thay đổi.

### Bấm nút không cần robot đứng ở bàn nào

Đây là điểm khác quan trọng so với luồng nhà hàng. Nút "nói chuyện" trên tablet đi theo đường
`bàn → robot`, mà binding đó chỉ sinh ra khi dispatcher **điều robot tới bàn**. Trong buổi demo
không có sàn nhà hàng, không có task, không có "tới nơi" — nên monitor gọi thẳng thiết bị theo
`robot_id`:

```
POST /voice/listen  {"robot_id": "robo-1", "table_id": 1}
                     ─────────────────────  ────────────
                     mic nào                 lượt này tính cho hội thoại của bàn nào
```

`table_id` vẫn cần vì agent lưu trí nhớ, giỏ hàng và giai đoạn hội thoại **theo bàn**. Mặc định là
bàn 1 — một bàn có thật, nên nếu thầy muốn xem tới cùng thì `confirm_order` vẫn chạy thật và đơn
vẫn hiện trên `panel` của bếp.

---

## 4. Gỡ rối

| Hiện tượng trên màn hình | Nghĩa là gì | Làm gì |
|---|---|---|
| Ô chọn thiết bị ghi *"chưa có mic nào"*, các nút mờ đi | Jetson chưa nối vào hub | Trên Jetson chạy `make voice`; kiểm tra `ORCHESTRATOR_URL` trong `.env` của Jetson trỏ đúng IP server |
| Góc phải ghi *"Mất kết nối hub"* | Trang không nối được WS | `make backend` đã chạy chưa; mở đúng cổng 8000 chưa |
| Bấm nghe, hiện *"Mic không nhận lệnh"* | Hub thấy trang nhưng không thấy mic đó | Jetson vừa rớt mạng — danh sách thiết bị tự làm mới mỗi 5 giây, đợi rồi chọn lại |
| MIC đỏ, *"không nghe thấy"* | Hết 15 giây chờ mà VAD không thấy tiếng nói | Kiểm tra đường âm thanh PulseAudio trên Jetson — xem [`jetson-demo-runbook-vi.md`](jetson-demo-runbook-vi.md) |
| STT đỏ, *"không dùng được"* | Whisper trả về rỗng, **hoặc** bộ lọc đã chặn một câu bịa | Bình thường khi có tiếng động lạ. Xem log Jetson để biết câu bị chặn là gì (`STT bỏ qua…`) |
| AGENT sáng mãi không tắt | LLM chưa trả lời xong hoặc agent chết | Xem terminal `make agent` |
| Nghe và chép được, nhưng AGENT không nhúc nhích | Jetson không gọi được server | Kiểm tra `AGENT_URL` trong `.env` của Jetson |

---

## 5. File liên quan

| File | Vai trò |
|------|---------|
| [`src/frontends/monitor/`](../../src/frontends/monitor/) | Trang web (Vue 3 + Vite, cổng dev 5176) |
| [`src/frontends/monitor/src/pipeline.ts`](../../src/frontends/monitor/src/pipeline.ts) | Mô hình một lượt: các chặng, bản ghi lượt, định dạng số |
| [`src/edge_voice/main.py`](../../src/edge_voice/main.py) | Lớp `Telemetry` + các mốc báo cáo trong một lượt |
| [`src/server_orchestrator/routers/voice.py`](../../src/server_orchestrator/routers/voice.py) | `/voice/listen|cancel|mute|new-chat` theo `robot_id`, `/voice/devices`, fan-out sang `role=monitor` |
| [`src/server_orchestrator/realtime/ws.py`](../../src/server_orchestrator/realtime/ws.py) | Nhận frame `telemetry` từ mic, phát lại thành `voice.device` |
| [`src/agent_brain/server.py`](../../src/agent_brain/server.py) | Bắn `voice.sentence` từng câu + số đo độ trễ trong `/chat/stream` |
