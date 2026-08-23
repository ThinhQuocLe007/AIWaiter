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
| **Rack tín hiệu** (hàng trên) | 5 module `MIC → VAD → STT → AGENT → TTS`. Module đang chạy sáng hổ phách, dây nối vào nó có xung sáng chạy. Module đã xong đổi sang xanh teal kèm số đo. |
| **Diễn biến** (cột trái) | Một dòng chảy duy nhất, lượt mới nhất trên cùng. Mỗi lượt gồm: khách nói gì, robot trả lời gì, số đo của lượt, và **ngay bên dưới là các frame thô** sinh ra lượt đó — ghi rõ do **THIẾT BỊ** (Jetson) hay **AGENT** (server) gửi. |
| **Cột điều khiển** (cột phải) | Mọi thứ ngón tay chạm vào khi demo: 4 nút lớn cỡ chạm (nút chính *Bắt đầu nghe* chiếm nguyên hàng), hai thanh trượt **Loa/Mic** chạy hết bề ngang cột, và khúc *Sổ đo* ở đáy. |
| **Sổ đo** (đáy cột điều khiển) | Mỗi lượt một thanh, chia đoạn theo chặng: *khách nói · chép lời · LLM tới câu đầu · robot nói*. Cùng một thang cho mọi thanh nên nhìn là biết lượt nào chậm. Cố ý chỉ là một khúc vài thanh, cuộn khi nhiều — nó đáng một cái liếc, không đáng một cột. |

*Diễn biến* trước đây là hai ô riêng (*Hội thoại* và *Nhật ký sự kiện*) nằm cạnh nhau. Gộp lại vì
đọc một lượt phải liếc hai chỗ rồi tự ghép theo dấu thời gian; giờ mỗi lượt tự mang bằng chứng
của nó. Chữ lời thoại ~1rem, frame ~0.7rem — chênh lệch cỡ chữ là thứ giữ cho đống frame không
nuốt mất hai câu mà người ta thật sự đến để đọc.

Nút điều khiển: **Bắt đầu nghe** · **Dừng** · **Hội thoại mới** (xoá trí nhớ hội thoại của bàn) ·
**Tắt loa** (robot vẫn trả lời, chỉ không phát tiếng). Chúng nằm dọc **cột phải** chứ không phải
một dải ngang trên đầu — trang này được bấm bằng ngón tay trên màn cảm ứng 7", nên nút cần chiều
cao thật (≥50px), và hai ô đọc nhường bề ngang để trả cho khoản đó.

**Trang không nêu tên model nào.** Chặng STT ghi *"chép lời thành chữ"*, số đo ghi *"chép lời"* —
không phải "Whisper"/"PhoWhisper". Người ngoài xem demo không có việc gì phải biết bên trong chạy
model gì; đây là lựa chọn có chủ ý, đừng "sửa lại cho rõ". Tên model vẫn nằm nguyên trong code,
trong log Jetson và trong tài liệu này.

Chữ toàn trang là **Be Vietnam Pro** (nhãn in hoa có tracking) + **JetBrains Mono** cho số. Trước
đây nhãn dùng Martian Mono — font đó **không có glyph tiếng Việt** (thiếu dải Latin Extended
Additional), nên "Diễn biến"/"THIẾT BỊ" bị ghép dấu từ font khác và nhìn gãy. Đừng đưa nó quay lại.

### Hai thanh trượt Loa / Mic

Kéo trực tiếp âm lượng loa và độ nhạy mic **của Jetson** ngay trên trang, không phải SSH vào gõ
`pactl`. Đây là điều khiển thật: nó chạy `pactl set-sink-volume` / `set-source-volume` trên máy
đó, nên `pactl` và thanh trượt luôn nói cùng một con số.

| | Khoảng | Vì sao |
|---|---|---|
| **Loa** | 0–100% | Quá 100% PulseAudio khuếch đại số — hội trường nghe ra tiếng rè, không phải to hơn |
| **Mic** | 0–150% | Mic USB rẻ trong hội chợ ồn thật sự cần phần dư này; mic quá nhạy cùng lắm mất một chữ |

Thanh trượt **mờ và không kéo được** khi Jetson chưa báo mức thật lên (chưa kết nối, hoặc máy đó
không có `pactl`). Giá trị hiển thị luôn là mức **đọc ngược lại từ pactl** sau khi đặt, không phải
con số vừa kéo — pactl có thể tự kẹp lại, và một thanh trượt khăng khăng giữ giá trị phần cứng đã
từ chối thì tệ hơn là để nó bật về.

Giao diện là **nền sáng** (giấy ấm), cố ý — hội chợ có đèn chiếu mạnh, nền tối bị loá và nhìn
từ xa không rõ chữ.

### Trang không được la làng

Khách VIP đứng xem cùng phòng, nên trang này **không bao giờ hiện lỗi đỏ cho những chuyện bình
thường**:

- Rớt WS → góc phải ghi *"Đang kết nối…"* màu xám, không phải *"Mất kết nối hub"* màu đỏ. Client
  tự nối lại trong vài giây, nên báo động đỏ gần như luôn sai vào lúc người ta đọc xong nó.
- Không ai nói, khách bấm Dừng, Whisper không nghe rõ → module chuyển **xám** kèm chữ bình thản
  (*"không có ai nói"*, *"đã dừng"*, *"không nghe rõ"*). Đây là pipeline chạy đúng trên đầu vào
  rỗng, không phải hỏng.
- Chỉ **một** trường hợp còn màu đỏ: agent thật sự lỗi. Ngay cả khi đó trang chỉ ghi *"chưa trả
  lời được"* — traceback đi vào console của trình duyệt, không lên màn hình.

Chi tiết kỹ thuật vẫn còn, nằm trong **tooltip**: rê chuột lên đèn kết nối hoặc ô chọn thiết bị.
Khách không rê chuột; người vận hành thì có.

### Kích thước màn hình

Trang tự co theo màn:

| Màn | Cách bố trí |
|-----|-------------|
| **Màn rời 7" của Jetson (1024×600)** | Bố cục gọn: bỏ dòng phụ dưới tiêu đề và các chú thích nhỏ, module rack thấp lại, chữ trong *Diễn biến* nhỏ đi. Ngược lại **nút và thanh trượt giữ cỡ chạm đầy đủ** (nút ≥50px, núm trượt 26px) — đó là những thứ duy nhất phải bấm, mà màn 7" chính là màn được bấm. *Sổ đo* còn ~3 thanh. Toàn bộ vừa trong 600px, **cả trang không cuộn**, chỉ *Diễn biến* và *Sổ đo* cuộn bên trong. |
| **Màn desktop** | Bố cục đầy đủ, 2 cột. |
| **Màn hẹp mà cao** (tablet dựng đứng, < 1100px rộng) | Xếp chồng 1 cột; rack tự xuống 2 hàng khi dưới 900px. |

Điều kiện chuyển sang bố cục gọn là **chiều cao ≤ 700px**, không phải chiều rộng — đúng cái ràng
buộc thật của màn 7" (600px cao mới là chỗ chật, 1024px ngang thì đủ cho 5 module).

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
| Ô chọn thiết bị ghi *"chưa có mic"*, các nút mờ đi | Jetson chưa nối vào hub | Trên Jetson chạy `make voice`; kiểm tra `ORCHESTRATOR_URL` trong `.env` của Jetson trỏ đúng IP server |
| Góc phải ghi *"Đang kết nối…"* mãi không xanh | Trang không nối được WS | `make backend` đã chạy chưa; mở đúng cổng 8000 chưa |
| Bấm nghe, hiện *"Robot chưa sẵn sàng."* | Hub thấy trang nhưng không thấy mic đó | Jetson vừa rớt mạng — danh sách thiết bị tự làm mới mỗi 5 giây, đợi rồi chọn lại |
| MIC xám, *"không có ai nói"* | Hết 15 giây chờ mà VAD không thấy tiếng nói | Nếu lặp lại: kiểm tra đường âm thanh PulseAudio trên Jetson — xem [`jetson-demo-runbook-vi.md`](jetson-demo-runbook-vi.md). Thử kéo thanh **Mic** lên |
| STT xám, *"không nghe rõ"* | Whisper trả về rỗng, **hoặc** bộ lọc đã chặn một câu bịa | Bình thường khi có tiếng động lạ. Xem log Jetson để biết câu bị chặn là gì (`STT bỏ qua…`) |
| AGENT sáng mãi không tắt | LLM chưa trả lời xong hoặc agent chết | Xem terminal `make agent` |
| AGENT đỏ, *"chưa trả lời được"* | Gọi agent thất bại | Lỗi thật nằm ở console trình duyệt (F12) và ở terminal `make agent` |
| Nghe và chép được, nhưng AGENT không nhúc nhích | Jetson không gọi được server | Kiểm tra `AGENT_URL` trong `.env` của Jetson |
| Hai thanh Loa/Mic mờ, hiện `—` | Jetson chưa báo mức lên, hoặc máy đó không có `pactl` | Trên Jetson: `which pactl`. Nếu có mà vẫn mờ thì code `src/edge_voice/` trên Jetson là bản cũ — đồng bộ lại |

---

## 5. File liên quan

| File | Vai trò |
|------|---------|
| [`src/frontends/monitor/`](../../src/frontends/monitor/) | Trang web (Vue 3 + Vite, cổng dev 5176) |
| [`src/frontends/monitor/src/pipeline.ts`](../../src/frontends/monitor/src/pipeline.ts) | Mô hình một lượt: các chặng, bản ghi lượt, định dạng số |
| [`src/frontends/monitor/src/components/Timeline.vue`](../../src/frontends/monitor/src/components/Timeline.vue) | Ô *Diễn biến* — lời thoại và frame của cùng một lượt gộp làm một |
| [`src/edge_voice/main.py`](../../src/edge_voice/main.py) | Lớp `Telemetry` + các mốc báo cáo trong một lượt, và lệnh `set_audio_level` |
| [`src/edge_voice/audio_levels.py`](../../src/edge_voice/audio_levels.py) | Đọc/đặt mức loa + mic qua `pactl` (đường tương thích cả pactl 13 lẫn 15) |
| [`src/server_orchestrator/routers/voice.py`](../../src/server_orchestrator/routers/voice.py) | `/voice/listen|cancel|mute|new-chat|audio-level` theo `robot_id`, `/voice/devices`, fan-out sang `role=monitor` |
| [`src/server_orchestrator/realtime/ws.py`](../../src/server_orchestrator/realtime/ws.py) | Nhận frame `telemetry` từ mic, phát lại thành `voice.device` |
| [`src/agent_brain/server.py`](../../src/agent_brain/server.py) | Bắn `voice.sentence` từng câu + số đo độ trễ trong `/chat/stream` |
