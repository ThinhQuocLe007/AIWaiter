# Runbook demo — tắt Jetson, mở lại, chạy được

> Dành riêng cho **con Jetson Orin Nano ở `/home/orin/AI_voice/AIWaiter`** (cài lại 2026-08-22).
> Bản thao tác cho ngày demo. Kiến trúc & luồng voice: [run-voice-vi.md](run-voice-vi.md).
> Thứ tự server + binding bàn đầy đủ: [jetson-boot-runbook-vi.md](jetson-boot-runbook-vi.md).
>
> ⚠️ `jetson-boot-runbook-vi.md` viết cho máy cũ (`~/ptd_workspace/AIWaiter`). Đường dẫn ở đó
> **sai với máy này**. Dùng file này cho phần Jetson.

---

## ✅ PHẦN 0 — Chuẩn bị trước demo (ĐÃ XONG 2026-08-22)

> **Trạng thái: máy đã sẵn sàng.** `jetson_healthcheck.sh` ra **18 OK, 0 LỖI**. Giữ phần này để
> biết phải làm gì nếu cài lại máy — còn ngày demo thì nhảy thẳng xuống [Phần 1](#phần-1--sau-khi-bật-jetson-lên).

**Ba model tải về lúc chạy lần đầu.** Nếu để tới lúc demo mới tải mà wifi hội trường yếu hoặc
chặn GitHub thì hỏng ngay trước mặt khách.

| Model | Tải từ | Đã có chưa (2026-08-22) |
|---|---|---|
| Whisper `medium` (1.5GB) | HuggingFace | ✅ đã cache |
| Silero VAD | **GitHub** (`torch.hub`) | ✅ đã cache — `~/.cache/torch/hub` |
| Piper TTS `vi_VN-vais1000-medium` | HuggingFace | ✅ đã cache — `storage/tts/`, 60MB |

Silero tải qua `torch.hub.load("snakers4/silero-vad")` — tức là **cần vào được github.com**,
không chỉ HuggingFace. Nhiều mạng hội trường/công ty chặn cái này.

### Cách nạp cache: chạy thật một lần

```bash
make voice
```

Chờ tới khi nghe loa phát **"Xin chào"** và in `[READY]`, rồi `Ctrl+C`. Lúc đó cả 3 model đã nằm
trên đĩa và **những lần sau không cần internet để load model nữa**.

Muốn nạp cache mà không cần mic/loa (nhanh hơn, không mở thiết bị âm thanh):

```bash
.venv/bin/python -c "from src.edge_voice.output import tts_engine as t; t._download_piper_model(); from src.edge_voice.perception.vad_silero import SileroVAD; SileroVAD()._load_model()"
```

> Phải nạp Silero **qua `SileroVAD._load_model()`**, đừng gọi `torch.hub.load("snakers4/silero-vad")`
> trần: hubconf của silero `import torchaudio` ở module level, mà máy này cố tình không cài
> torchaudio (wheel aarch64 build cho CUDA 13, xung với torch 2.11 cu126) → `ModuleNotFoundError`.
> `_load_model()` cắm stub torchaudio trước khi load nên đi qua được.

Xác nhận đã cache đủ:

```bash
bash /home/orin/AI_voice/AIWaiter/scripts/jetson_healthcheck.sh
```

Ba dòng trong mục "Model cache" phải đều `[OK]`.

### Còn 2 việc nữa trước demo

**Mic + loa USB** — ✅ đã cắm, đã test. Thiết bị là **một cục Jieli USB Composite Device
(`card 0`)**, vừa là mic vừa là loa (kiểu speakerphone). Test lại khi cần:

```bash
arecord -l && arecord -D plughw:0,0 -d 5 -f S16_LE -r 16000 -c 1 /tmp/t.wav && aplay /tmp/t.wav
```

Đổi `0` cho khớp số card mà `arecord -l` in ra. Nghe lại được tiếng mình = tầng phần cứng xong.

⚠️ **Cắm được thôi CHƯA đủ** — còn phải trỏ default sink/source của PulseAudio vào nó, xem
[§ 0.1](#01-đường-âm-thanh--cái-bẫy-câm-lặng) ngay dưới. Đây là cái bẫy khó chịu nhất của cả setup.

**Tạo `.env`** — ✅ đã tạo. IP Netbird của server (peer `ducduy-pc-165-221`) là **`100.66.165.221`**:

```bash
cd /home/orin/AI_voice/AIWaiter && printf 'AGENT_URL=http://100.66.165.221:8100\nORCHESTRATOR_URL=http://100.66.165.221:8000\nVOICE_ROBOT_ID=robo-1\n' > .env && cat .env
```

Server chạy máy khác thì đổi IP — `netbird status -d` rồi tìm peer của server. Jetson này là
`orin-desktop` = `100.66.136.17`.

> `VOICE_ROBOT_ID` **phải trùng** id của robot motion (`make mockrobot ID=...`). Sai cái này là
> lỗi hay gặp nhất: mic kết nối bình thường, không log lỗi gì, nhưng bấm nút trên tablet trả
> `no_device`. Không cần `DEVICE=cuda` — mặc định đã là `cuda`.

### 0.1 Đường âm thanh — cái bẫy câm lặng

**Triệu chứng nếu sai:** mọi thứ chạy hoàn hảo. Log sạch, `[READY]` in ra, STT nhận đúng chữ,
TTS synthesize xong, `paplay` trả về 0. Mà **không ai nghe thấy gì**. Không có một dòng lỗi nào
để mà tra.

**Vì sao:** PortAudio *không* enumerate được card USB khi PulseAudio đang giữ nó, nên hàm tự-dò
mic theo tên (`"usb" in dev.name`) trong [`vad_silero.py`](../../src/edge_voice/perception/vad_silero.py)
trượt, rơi về `device=None` → ALSA `default` → pulse. TTS cũng đi qua pulse. Nghĩa là
**default sink/source của PulseAudio CHÍNH LÀ đường âm thanh thật của cả hệ voice**, chứ không
phải cái card USB bạn vừa cắm.

Mà mặc định của board thì trỏ đi chỗ khác. Máy này có 3 sink, chỉ **một** cái thật sự kêu:

| Sink | Là gì | Kêu không? |
|---|---|---|
| `alsa_output.usb-Jieli_...analog-stereo` | loa của cục USB | ✅ **cái này** |
| `alsa_output.platform-sound.analog-stereo` | jack 3.5mm trên board | ❌ không cắm gì — **và đây là mặc định của board** |
| `alsa_output.platform-3510000.hda.hdmi-stereo` | HDMI | ❌ màn hình không có loa; sink vẫn hiện vì cổng có tín hiệu |

Trỏ đúng (đã set sẵn 2026-08-22, và pulse lưu lại ở `~/.config/pulse/*-default-sink|source` nên
**sống qua reboot**):

```bash
pactl set-default-sink   $(pactl list short sinks   | grep -i usb | cut -f2 | head -1)
pactl set-default-source $(pactl list short sources | grep -i alsa_input.*usb | cut -f2 | head -1)
pactl set-sink-volume @DEFAULT_SINK@ 45%
```

Healthcheck kiểm 4 dòng này (`loa: default sink = USB`, `mic: default source = USB`, âm lượng,
mute) nên không cần nhớ — cứ chạy nó.

**Chỉnh âm lượng:**

```bash
pactl set-sink-volume @DEFAULT_SINK@ 45%    # đặt cứng 45% — mức đang dùng, vừa tai
pactl set-sink-volume @DEFAULT_SINK@ -5%    # giảm 1 nấc, gõ lại nhiều lần
pactl get-sink-volume @DEFAULT_SINK@        # xem đang bao nhiêu
```

Hoặc GUI: Settings → Sound → Output = *USB Composite Device Analog Stereo*. Hoặc `alsamixer -c 0`.

> Cục USB Jieli mặc định về **30%** khi cắm lần đầu, và loa của nó khá to — 85% là gào.
> 45% là mức đã test thấy vừa.

**Test nhanh cả TTS lẫn loa trong 1 lệnh** (không cần server, không cần mic):

```bash
.venv/bin/python -c "
from src.edge_voice.output.tts_engine import warmup, synthesize, StreamingPlayer
warmup(); StreamingPlayer().play_sentence(synthesize('Xin chào, đây là bài kiểm tra loa.'))" 2>/dev/null
```

> **Phải gọi `warmup()` trước `synthesize()`.** `synthesize()` chỉ dùng Piper khi voice đã load
> (`_PIPER_VOICE is not None`); chưa warmup thì nó **lặng lẽ rơi về edge-tts (cloud)** — vẫn ra
> tiếng nếu có mạng, nên rất dễ tưởng offline đã OK trong khi thật ra đang gọi Internet.
> `make voice` tự warmup ở bước 3 nên đường chạy thật không dính lỗi này.

---

## PHẦN 1 — Sau khi bật Jetson lên

### 1.1 Health check (30 giây) — làm đầu tiên, luôn luôn

```bash
bash /home/orin/AI_voice/AIWaiter/scripts/jetson_healthcheck.sh
```

Ra `Sẵn sàng demo.` thì nhảy thẳng xuống 1.3. Có dòng `[LỖI]` thì tra ở [Phần 3](#phần-3--gỡ-rối).

### 1.2 Những thứ KHÔNG tự sống lại sau reboot

Hầu hết mọi thứ đều persist (xem bảng [Phần 4](#phần-4--cái-gì-sống-sót-qua-reboot)). Chỉ 1 thứ
phải chạy lại mỗi lần boot nếu muốn tốc độ tối đa:

```bash
sudo jetson_clocks
```

Nó khoá CPU/GPU ở xung tối đa. Không có service systemd nào chạy giùm, nên **reboot là mất**.
Không chạy cũng không sao — chỉ là latency nhỉnh hơn chút.

> **Power mode thì KHÔNG cần đụng.** Máy đang ở `pmode:0002` = **MAXN_SUPER**, chế độ mạnh nhất
> của board này, và nó persist qua reboot. Kiểm tra: `cat /var/lib/nvpmodel/status`
>
> ⚠️ **Đừng chạy `sudo nvpmodel -m 0`.** Trên Orin Nano Super, mode 0 là **15W** — *chậm hơn*
> MAXN_SUPER. Các hướng dẫn Jetson đời cũ hay ghi "mode 0 = full power", điều đó **sai với board này**:
>
> | ID | Tên | |
> |---|---|---|
> | 0 | 15W | |
> | 1 | 25W | mặc định trong `/etc/nvpmodel.conf` |
> | 2 | **MAXN_SUPER** | ← đang dùng, mạnh nhất |
> | 3 | 7W | |

### 1.3 Chạy voice device

```bash
cd /home/orin/AI_voice/AIWaiter && make voice
```

**Không cần `source .venv/bin/activate`, không cần `~/nocondaenv.sh`.** `make voice` gọi thẳng
`.venv/bin/python`, mà Python xác định env theo vị trí file thực thi (`pyvenv.cfg` nằm cạnh nó),
không theo biến môi trường — nên nó tự trúng đúng venv.

Boot mất ~30–60s, đi qua 5 bước. Biết thứ tự này để đọc log lúc treo:

| # | Nạp gì | Dấu hiệu |
|---|---|---|
| 1 | Mic + Silero VAD | log `Mic opened: device=None (default)` là **bình thường** — đi qua pulse, xem [§ 0.1](#01-đường-âm-thanh--cái-bẫy-câm-lặng) |
| 2 | Whisper `medium` (float16, CUDA) | warmup bằng 0.5s im lặng |
| 3 | Piper TTS (offline) | |
| 4 | Phát "Xin chào" | **nghe được tiếng = tầng loa OK** |
| 5 | Nối WS backend | in `[READY]` |

Thành công:

```
==================================================
 AI Waiter voice device — Robot robo-1
 Agent (LLM)  @ http://100.66.165.221:8100
 Backend (WS) @ http://100.66.165.221:8000
==================================================
[READY] đã kết nối backend (robo-1) — chờ điều tới bàn + web bấm 'nói chuyện'.
```

`[READY]` = mic sẵn sàng, **nhưng chưa nói được** — còn thiếu binding bàn (Phần 2).

---

## PHẦN 2 — Thứ tự bật cả hệ thống

Jetson **không tự nói được một mình**. Mic mở sẵn nhưng bị khoá cho tới khi nhận lệnh
`start_listening` từ server.

**Bật server trước, Jetson sau.** (Jetson bật trước cũng không chết — WS tự retry, chỉ in
`[WS] mất kết nối` cho tới khi backend lên.)

| # | Máy | Lệnh | Chờ tới khi |
|---|---|---|---|
| 1 | server | `ollama serve` | `ollama list` ra model |
| 2 | server | `make backend` | `:8000` lên |
| 3 | server | `make agent` | in `Agent ready.` |
| 4 | server | `make menu` | `:5173` lên |
| 5 | **jetson** | `bash scripts/jetson_healthcheck.sh` | `Sẵn sàng demo.` |
| 6 | **jetson** | `make voice` | in `[READY]` |
| 7 | server | `make mockrobot ID=robo-1` | robot online trên panel |
| 8 | tablet | seat bàn + gọi robot | backend log `voice bound to robo-1` |
| 9 | tablet | bấm "nói chuyện" | jetson in `[LISTENING]` |

Seat bàn nhanh bằng curl:

```bash
curl -X POST http://100.66.165.221:8000/seatings -H 'Content-Type: application/json' -d '{"table_id":1,"party_size":2}'
```

Một lần bấm nút = **một lượt nói**. Gate tự đóng sau khi flush, muốn nói tiếp thì bấm lại.

---

## PHẦN 3 — Gỡ rối

### Theo dòng `[LỖI]` của health check

| Dòng lỗi | Sửa |
|---|---|
| `loader KHÔNG thấy libctranslate2` | `sudo ldconfig` |
| `ld.so.conf ctranslate2 MẤT` | `echo "/home/orin/AI_voice/ct2-runtime/lib" \| sudo tee /etc/ld.so.conf.d/ctranslate2.conf && sudo ldconfig` |
| `loader KHÔNG thấy libcudss` | `echo "/usr/lib/aarch64-linux-gnu/libcudss/12" \| sudo tee /etc/ld.so.conf.d/libcudss-12.conf && sudo ldconfig` |
| `lib ctranslate2 MẤT` | Nặng — build lại, xem [jetson-ctranslate2-build.md](jetson-ctranslate2-build.md) (~9 phút với `-j6`) |
| `ctranslate2 hỏng` mà lib còn | Ai đó chạy `uv sync` trần. Xem [§ Cứu sau khi bị uv sync](#cứu-sau-khi-bị-uv-sync-trần) |
| `Silero VAD / Piper CHƯA tải` | Cần internet — chạy `make voice` một lần |
| `KHÔNG thấy mic USB` | Rút cắm lại, `dmesg \| tail` |

### Theo triệu chứng lúc chạy

| Triệu chứng | Nguyên nhân |
|---|---|
| Bấm nút → `no_device` | Chưa có binding (robot chưa tới bàn), hoặc `VOICE_ROBOT_ID` ≠ id robot motion |
| `[WS] mất kết nối backend` lặp | Backend chưa chạy / `ORCHESTRATOR_URL` sai IP / Netbird chưa mở 8000 |
| `[LISTENING]` rồi nói mà `[TIMEOUT]` | Mic sai device → `make probe`; hoặc hạ `VAD_THRESHOLD=0.3` |
| `Agent request failed` | Agent `:8100` chưa chạy, hoặc `AGENT_URL` sai |
| **TTS chạy xong mà không nghe gì**, log sạch | Default sink trỏ nhầm (`platform-sound` = jack trống, hoặc HDMI không loa). Xem [§ 0.1](#01-đường-âm-thanh--cái-bẫy-câm-lặng) |
| Nghe quá to / quá nhỏ | `pactl set-sink-volume @DEFAULT_SINK@ 45%` |
| Đống `ALSA lib ... Unknown PCM` | **Bình thường** — PortAudio quét thiết bị. Thêm `2>/dev/null` |
| Log `Mic opened: device=None (default)` | **Bình thường** — pulse đang giữ card USB nên PortAudio không dò được theo tên; đi qua `default` là đúng, miễn default source = mic USB |
| `onnxruntime ... GPU device discovery failed` | **Bình thường** trên Jetson — Piper chạy CPU, không ảnh hưởng |
| STT ra "Hãy subscribe cho kênh..." | Whisper bịa trên đoạn < 1s. Không phải lỗi mic. **Đã lọc từ 2026-08-22** — xem [§ 3.1](#31-bộ-lọc-câu-bịa-của-whisper) |
| `ImportError: libctranslate2.so.4` | `sudo ldconfig` |
| `ImportError: libcudss.so.0` | Xem bảng trên |
| `GLIBCXX_3.4.34 not found` | Đang chạy trong shell có conda. Mở terminal mới, **đừng** `conda activate` |

### 3.1 Bộ lọc câu bịa của Whisper

Whisper `medium` được train trên phụ đề YouTube, nên gặp đoạn ngắn/ồn (tiếng đóng cửa, ghế kéo)
nó bịa ra boilerplate video. Thu thật trên máy này ngày 2026-08-22, một tiếng động **0.4 giây** ra:

```
STT: Hãy subscribe cho kênh Ghiền Mì Gõ Để không bỏ lỡ những video hấp dẫn
STT: Hẹn gặp lại trong video tiếp theo!
```

Trước đây pipeline **không lọc gì cả** — câu bịa đó đi thẳng tới agent và robot sẽ đọc câu trả lời
cho nó giữa lúc đang đứng trước khách. Nay [`stt_phowhisper.py`](../../src/edge_voice/perception/stt_phowhisper.py)
có `_is_hallucination()`: khớp danh sách mẫu (subscribe / đăng ký kênh / ghiền mì gõ / hẹn gặp lại
trong video / cảm ơn đã xem / phụ đề bởi...) thì **vứt cả utterance**.

Đã cân nhắc chặn theo độ dài (`< 0.7s`) nhưng **không làm**: khách trả lời "dạ", "ừ", "có" đều
ngắn hơn thế, mất mấy câu đó còn tệ hơn.

Câu bị vứt **vẫn ghi log** — vứt im lặng thì trông y hệt mic chết:

```
INFO ...stt_phowhisper: STT bỏ qua (câu bịa của Whisper, 0.4s): Hẹn gặp lại trong video tiếp theo!
```

Thấy mẫu bịa mới trong log thì thêm vào `_HALLUCINATION_PATTERNS`. Test lại bộ lọc:

```bash
.venv/bin/python -c "
from src.edge_voice.perception.stt_phowhisper import _is_hallucination as h
print(h('Hãy subscribe cho kênh Ghiền Mì Gõ'), h('cho tôi một ly cà phê sữa'))"   # True False
```

### Cứu sau khi bị `uv sync` trần

`ctranslate2` + `faster-whisper` ở đây **build tay**, không nằm trong `uv.lock`. Một lệnh
`uv sync` hoặc `uv run` trần sẽ gỡ sạch chúng. Thư viện C++ vẫn còn, chỉ mất phần Python —
sửa mất ~2 phút, **không** phải build lại CUDA:

```bash
source ~/nocondaenv.sh && cd /home/orin/AI_voice/AIWaiter && source .venv/bin/activate && cd /home/orin/AI_voice/CTranslate2/python && uv pip install -r install_requirements.txt && CTRANSLATE2_ROOT=/home/orin/AI_voice/ct2-runtime uv pip install . --no-build-isolation && uv pip install faster-whisper --no-deps && uv pip install tokenizers huggingface-hub av
```

**Phòng bệnh:** cần cài thêm package thì luôn dùng `--inexact` (nó cài/cập nhật nhưng **không gỡ**
cái ngoài lock):

```bash
cd /home/orin/AI_voice/AIWaiter && uv sync --inexact --extra voice
```

---

## PHẦN 4 — Cái gì sống sót qua reboot

| Thành phần | Ở đâu | Sống? |
|---|---|---|
| `libctranslate2.so.4.6.0` | `/home/orin/AI_voice/ct2-runtime/lib` | ✅ |
| Đường tìm lib ctranslate2 | `/etc/ld.so.conf.d/ctranslate2.conf` | ✅ |
| `libcudss.so.0` + đường tìm | `/usr/lib/.../libcudss/12` + `ld.so.conf.d` | ✅ |
| `ctranslate2` 4.6.0, `faster-whisper` 1.2.1 | `.venv` | ✅ |
| `torch` 2.11.0 cu126 | `.venv` | ✅ |
| Whisper `medium` 1.5GB | `~/.cache/huggingface` | ✅ |
| Silero VAD | `~/.cache/torch/hub` | ✅ *(sau khi tải lần đầu)* |
| Piper TTS | `storage/tts/` | ✅ *(sau khi tải lần đầu)* |
| swap 16G | `/swapfile` + `/etc/fstab` | ✅ |
| zram (đã tắt) | `nvzramconfig` disabled | ✅ vẫn tắt |
| Power mode MAXN_SUPER | `/var/lib/nvpmodel/status` | ✅ |
| default sink/source = USB | `~/.config/pulse/*-default-sink` / `-default-source` | ✅ |
| Âm lượng loa 45% | `~/.config/pulse/*-device-volumes.tdb` | ✅ |
| **`jetson_clocks`** | — | ❌ **phải chạy lại mỗi lần boot** |
| Source CTranslate2 (để rebuild) | `/home/orin/AI_voice/CTranslate2` | ✅ |

---

## PHẦN 5 — 3 quy tắc để không hỏng giữa demo

**1. Không bao giờ `uv sync` trần, không `uv run` trần.**
Dùng `make voice`, `make probe`, `.venv/bin/python ...`, hoặc `uv sync --inexact --extra voice`.

**2. Máy này có conda (miniconda3) chiếm PATH.**
Nó ship `libstdc++` mới hơn hệ thống (`GLIBCXX_3.4.34` vs `3.4.30`) — chạy voice trong shell đã
`conda activate` có thể gãy khi load thư viện. `make voice` không bị ảnh hưởng (gọi thẳng
`.venv/bin/python`), nhưng nếu gõ `python ...` tay thì mở terminal sạch:

```bash
source ~/nocondaenv.sh
```

**3. VL-JEPA và voice chạy ở 2 terminal riêng.**
Một shell = một env. Đừng activate conda và `.venv` cùng lúc. Máy có 7.4GB RAM dùng chung
CPU+GPU; Whisper `medium` ăn ~1.5GB. Chạy song song thì mở `jtop` canh chừng, và nếu thiếu RAM
thì hạ Whisper xuống `small` ở [`stt_phowhisper.py`](../../src/edge_voice/perception/stt_phowhisper.py) dòng `MODEL_SIZE`.

---

---

## PHẦN 6 — Bản ghi môi trường (chốt 2026-08-22)

Trạng thái đã kiểm chứng bằng cách chạy thật, không phải chép từ tài liệu. Dùng để so sánh khi
sau này có gì đó "tự nhiên hỏng".

### Phần cứng & OS

| | |
|---|---|
| Board | Jetson Orin Nano Super (`orin-desktop`) |
| L4T | R36.4.7 (JetPack 6.x), kernel oot |
| OS | Ubuntu 22.04.5 LTS |
| RAM | 7.4GB unified (CPU+GPU dùng chung) + swap 16G ở `/swapfile` |
| Đĩa | NVMe 456G, còn trống 361G |
| Power mode | `pmode:0002` = MAXN_SUPER (persist qua reboot) |
| Repo | `/home/orin/AI_voice/AIWaiter` |

### Python / CUDA

| | |
|---|---|
| Python | 3.10.12 (`.venv` ở repo root) |
| CUDA | 12.6 (nvcc V12.6.68) |
| torch | 2.11.0, `cuda_available=True` |
| ctranslate2 | 4.6.0 (**build tay**, không có trong `uv.lock`) |
| faster-whisper | 1.2.1 (cài `--no-deps`) |
| torchaudio | **cố ý KHÔNG cài** — xem [§ 0](#phần-0--chuẩn-bị-trước-demo-đã-xong-2026-08-22) |

### Âm thanh

| | |
|---|---|
| Thiết bị | Jieli USB Composite Device (`4c4a:4155`), **card 0**, vừa mic vừa loa |
| Default sink | `alsa_output.usb-Jieli_...analog-stereo` @ **45%**, không mute |
| Default source | `alsa_input.usb-Jieli_...mono-fallback` |
| Sink KHÔNG dùng | `platform-sound` (jack trống), `hdmi-stereo` (màn hình không loa) |
| Mic thu thử | RMS 1755, peak 12941 — có tín hiệu thật |

### Mạng (Netbird)

| Peer | IP | Vai trò |
|---|---|---|
| `orin-desktop` | `100.66.136.17` | **Jetson này** |
| `ducduy-pc-165-221` | `100.66.165.221` | **Server** — backend :8000 + agent :8100 + ollama |
| `ducduy-ubuntu` | `100.66.85.145` | máy khác, *không phải* server |
| `phonght` / `thinh-ubuntu` / `ducduy-window` | — | peer khác trong fleet |

> ⚠️ Peer nào cũng có thể đang Connected, **đừng suy ra server từ trạng thái kết nối**. Server là
> `ducduy-pc` theo [e2e-voice-web-runbook-vi.md § 0](e2e-voice-web-runbook-vi.md). Trỏ nhầm IP thì
> voice vẫn boot bình thường và chỉ in `[WS] mất kết nối` — rất giống lỗi "server chưa bật".

### Đã kiểm chứng bằng cách chạy thật

| Kiểm | Kết quả |
|---|---|
| `jetson_healthcheck.sh` | **18 OK, 0 LỖI** |
| STT thật (`make probe`) | nhận đúng giọng nói tiếng Việt vào mic |
| Piper TTS → loa USB | phát được, offline, không cần mạng |
| `make voice` | boot đủ 5 bước, in `Models warmed`, retry WS đúng backoff |
| Lọc câu bịa Whisper | 18/18 ca đúng (8 câu bịa + 10 câu thật) |

### Thay đổi trong repo ngày 2026-08-22

| File | Gì |
|---|---|
| `scripts/jetson_healthcheck.sh` | **mới** — 18 mục kiểm, có 4 mục audio |
| `docs/guides/jetson-demo-runbook-vi.md` | **mới** — file này |
| `src/edge_voice/perception/stt_phowhisper.py` | thêm `_is_hallucination()` lọc boilerplate YouTube |
| `docs/INDEX.md` | thêm mô tả runbook |
| `.env` | **không commit** (trong `.gitignore`) — mỗi máy tự tạo |

---

## Dán lên tường — ngày demo

```
TRƯỚC 1 NGÀY (có internet):   ✅ ĐÃ XONG HẾT 2026-08-22 — 18 OK, 0 LỖI
  make voice                → chờ "Xin chào" + [READY] → Ctrl+C     (nạp cache 3 model)
  bash scripts/jetson_healthcheck.sh   → phải "Sẵn sàng demo."
  cắm mic USB, test arecord
  pactl set-default-sink/source → cục USB     (thiếu bước này = CÂM, không báo lỗi)
  tạo .env (AGENT_URL / ORCHESTRATOR_URL / VOICE_ROBOT_ID)

NGÀY DEMO — sau khi bật Jetson:
  1. bash scripts/jetson_healthcheck.sh
  2. sudo jetson_clocks
  3. (server bật xong 4 thứ)
  4. make voice              → chờ [READY]
  5. make mockrobot ID=robo-1  (ở server)
  6. seat bàn + gọi robot    → backend log "voice bound to robo-1"
  7. tablet bấm "nói chuyện" → [LISTENING]

ÂM LƯỢNG:  pactl set-sink-volume @DEFAULT_SINK@ 45%
TẮT: Ctrl+C (jetson) + make kill (server)
```
