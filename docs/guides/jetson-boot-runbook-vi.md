# Runbook — bật Jetson lên tới lúc nói được

> Thứ tự chạy đầy đủ, từ lúc cắm điện Jetson tới lúc khách bấm "nói chuyện" trên tablet và
> robot trả lời. Bản **thao tác**; phần giải thích kiến trúc voice ở
> [run-voice-vi.md](run-voice-vi.md), toàn hệ thống ở [run-guide-vi.md](run-guide-vi.md).

## 0a. Quy ước: activate env, KHÔNG dùng `uv run`

Mọi lệnh Python dưới đây chạy sau khi activate env:

```bash
cd ~/ptd_workspace/AIWaiter
source .venv/bin/activate            # prompt đổi thành (ai-waiter)
```

Lý do không dùng `uv run`: nó **sync env trước mỗi lần chạy**, và trên Jetson `uv sync` trần sẽ
gỡ mất bản `ctranslate2`/`faster-whisper` build tay ([jetson-ctranslate2-build.md](jetson-ctranslate2-build.md))
— đang chạy ngon tự nhiên hỏng sau một lệnh vô hại.

⚠️ **Kéo theo: đừng dùng `make` trên Jetson.** `make voice` = `uv run python src/edge_voice/main.py`
([Makefile:119](../../Makefile#L119)), tức là dính đúng vấn đề trên. Trong repo này `make` là dành cho
máy server. Runbook này luôn ghi lệnh `python` trực tiếp cho phần Jetson.

## 0. Điều quan trọng nhất: Jetson KHÔNG tự nói được một mình

Từ bản `backend-server-integration`, voice device là **service chờ lệnh**, không phải vòng lặp
always-on. Mic mở sẵn nhưng **bị khoá** (gate) cho tới khi nhận lệnh `start_listening` từ server
([main.py:78](../../src/edge_voice/main.py#L78) → [vad_silero.py:245](../../src/edge_voice/perception/vad_silero.py#L245)).

Nên chuỗi phụ thuộc là:

```
Ollama  →  backend :8000  →  agent :8100  →  [Jetson: make voice]  →  robot motion  →  dispatcher điều tới bàn
                                                                                              │
                                                              tablet bấm "nói chuyện" ◄────────┘ (có binding mới bấm được)
```

**Bật server trước, Jetson sau.** Jetson bật trước cũng không chết (WS tự retry với backoff tới
10s — [main.py:227-232](../../src/edge_voice/main.py#L227-L232)), chỉ là in `[WS] mất kết nối` cho tới khi
backend lên.

---

## 1. SERVER — bật trước (4 thứ)

```bash
cd ~/AIWaiter && source .venv/bin/activate   # (tên env trên server; `make` cũng dùng được ở đây)

# T0: LLM
ollama serve &
ollama list                 # phải có model khớp ROUTER/WORKER/RESPONSE_MODEL trong .env

# T1: orchestrator (REST + WS hub + /voice bridge)
make backend                # :8000

# T2: agent LLM  (rebuild embeddings rồi mới serve — lần đầu lâu)
make agent                  # :8100 — chờ in "Agent ready."

# T3: web
make menu                   # :5173 customer_ui (tablet mở cái này)
make panel                  # :5175 bếp (tuỳ chọn)
make kiosk                  # :5174 seat bàn (tuỳ chọn)
```

> Restart agent mà **không** muốn rebuild index (đã build rồi) — chạy thẳng uvicorn, đừng `make agent`:
> `uvicorn src.agent_brain.server:app --host 0.0.0.0 --port 8100`

Kiểm tra nhanh trước khi qua Jetson:
```bash
curl -s http://127.0.0.1:8000/health     # backend sống
curl -s http://127.0.0.1:8100/health     # agent sống
```

---

## 2. JETSON — sau khi boot

### 2.1 Test mic (10 giây)

Cắm USB là Linux tự nhận, không cần cấu hình gì. Thu thử rồi nghe lại:

```bash
arecord -l                                                   # xem card số mấy (VD: card 2)
arecord -D plughw:2,0 -d 10 -f S16_LE -r 16000 -c 1 test.wav # thu 10s
aplay test.wav                                               # nghe lại
```
Nghe được = xong tầng phần cứng. Không thấy card → rút cắm lại USB, `dmesg | tail`.

> Số card (`2`) **đổi được** sau reboot / đổi cổng USB. Không sao — code không pin số, nó tự dò
> thiết bị có chữ "usb" trong tên ([vad_silero.py:109-117](../../src/edge_voice/perception/vad_silero.py#L109-L117)).
> Chỉ sửa số trong lệnh `arecord` trên cho khớp là được.
>
> Lưu ý: `plughw:` là plugin **tự convert** của ALSA (nó resample 48k→16k giùm), nên `-r 16000`
> luôn chạy. PortAudio trong code mở sát phần cứng hơn → mic USB từ chối 16k, code tự tụt về 48k
> rồi resample bằng scipy. Nên `arecord` OK **chưa chắc** app OK — vẫn nên chạy probe ở 2.3.

### 2.2 Kiểm tra env (1 lần sau mỗi lần cài lại / đổi IP)

`.env` ở gốc repo trên Jetson **chỉ cần 3 dòng**:

```bash
AGENT_URL=http://100.x.x.x:8100          # IP Netbird của SERVER — Jetson POST /chat vào đây
ORCHESTRATOR_URL=http://100.x.x.x:8000   # backend — Jetson mở WS role=voice-device vào đây
VOICE_ROBOT_ID=robo-1                    # ⚠ PHẢI trùng id của robot motion (mock_robot --id)
DEVICE=cuda
```

> `VOICE_ROBOT_ID` sai là lỗi hay gặp nhất: mic connect thành công, log không báo gì,
> nhưng bấm nút trên tablet trả về `no_device` — vì server resolve
> `table → robot_id → mic socket` ([connection_manager.py:103-114](../../src/server_orchestrator/realtime/connection_manager.py#L103-L114))
> và mic đang đăng ký dưới một id khác với robot đang đứng ở bàn.
>
> Không cần `*_MODEL` / `EMBEDDING_*` trên Jetson — LLM chạy ở server.

Verify torch còn sống sau reboot:
```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# mong đợi: 2.11.0 True
python -c "import ctranslate2, faster_whisper; print('ct2 ok')"   # bản build tay còn nguyên
```
> Khi buộc phải cài thêm package trên Jetson: `uv sync --inexact` (giữ lại bản build tay).
> **Không bao giờ** `uv sync` trần.

### 2.3 (Tuỳ chọn) Probe mic trước khi chạy thật

Đáng làm sau mỗi lần reboot hoặc đổi cổng USB — 30 giây, loại trừ được cả tầng audio:

```bash
python scripts/probe_vad.py 2>/dev/null        # chỉ VAD: thấy speech/silence
python scripts/probe_stt_live.py 2>/dev/null   # VAD + Whisper: nói → in text
```
Probe tự arm gate liên tục nên không cần server chạy.

`2>/dev/null` chỉ vứt đống `ALSA lib ... Unknown PCM` (PortAudio quét thiết bị — ồn nhưng **không
phải lỗi**). Log của app đi ra stdout nên không mất gì. Sau khi in vài dòng `INFO ... loaded` thì
màn hình **im lặng là đúng** — chỉ khi bạn nói mới có `Utterance flushed` + `[HEARD]`.

### 2.4 Chạy voice device

```bash
python src/edge_voice/main.py       # KHÔNG dùng `make voice` — xem mục 0a
```

Boot xong (~30–60s, load VAD + Whisper medium + warm TTS, có phát "Xin chào"):
```
==================================================
 AI Waiter voice device — Robot robo-1
 Agent (LLM)  @ http://100.x.x.x:8100
 Backend (WS) @ http://100.x.x.x:8000
 Models warmed. Bàn được gán động khi robot tới bàn. Ctrl+C để dừng.
==================================================
[READY] đã kết nối backend (robo-1) — chờ điều tới bàn + web bấm 'nói chuyện'.
```

Thấy `[READY]` = mic sẵn sàng. **Chưa nói được** — còn thiếu binding bàn.

---

## 3. Robot motion + binding bàn (bước hay bị quên)

Mic chỉ nhận lệnh khi server biết **robot nào đang đứng ở bàn nào**. Binding được set khi
dispatcher nhận `arrived` ([dispatcher.py:355](../../src/server_orchestrator/services/dispatcher.py#L355)),
và bị **gỡ** khi robot xong việc / về nhà / mất kết nối.

```bash
# Robot giả (test không cần Gazebo) — id PHẢI trùng VOICE_ROBOT_ID
make mockrobot ID=robo-1

# Hoặc robot sim thật trong Gazebo:
make simbridge ID=robo-1 SERVER_HOST=100.x.x.x:8000
```

Tạo binding: seat bàn rồi gọi robot tới.
```bash
curl -X POST http://100.x.x.x:8000/seatings -H 'Content-Type: application/json' \
     -d '{"table_id":1,"party_size":2}'
```
Rồi bấm nút gọi phục vụ trên tablet (hoặc panel) → robot chạy tới bàn 1 → backend log:
```
task N arrived (table 1) — voice bound to robo-1
```

---

## 4. Nói thử

1. Tablet mở `http://100.x.x.x:5173`, chọn **bàn 1**.
2. Bấm **"Nói chuyện với AI"**.
3. Jetson in `[LISTENING] mời anh/chị nói...` → nói tiếng Việt → `[HEARD @ ... | bàn 1]: ...`
   → `[WAITER]: ...` + loa đọc, tablet hiện hội thoại.

Một lần bấm = **một lượt nói**. Gate tự đóng sau khi flush utterance, muốn nói tiếp thì bấm lại.
Nút **Hủy/Dừng** cắt cả mic đang thu lẫn câu đang phát; nút **loa** mute TTS.

---

## 5. Tóm tắt thứ tự (dán lên tường)

| # | Máy | Lệnh | Chờ tới khi |
|---|---|---|---|
| 1 | server | `ollama serve` | `ollama list` ra model |
| 2 | server | `make backend` | :8000 lên |
| 3 | server | `make agent` | in `Agent ready.` |
| 4 | server | `make menu` | :5173 lên |
| 5 | jetson | `source .venv/bin/activate` + test `arecord` | nghe lại được `test.wav` |
| 6 | jetson | `python src/edge_voice/main.py` | in `[READY] đã kết nối backend` |
| 7 | server/sim | `make mockrobot ID=robo-1` | robot online trên panel |
| 8 | tablet | seat bàn + gọi robot | backend log `voice bound to robo-1` |
| 9 | tablet | bấm "nói chuyện" | jetson in `[LISTENING]` |

Tắt hết: `make kill` (server) + `Ctrl-C` (jetson).

---

## 6. Gỡ rối theo triệu chứng

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Nút "nói chuyện" trả `no_device` | Chưa có binding (robot chưa tới bàn), hoặc `VOICE_ROBOT_ID` ≠ id robot motion |
| Jetson `[WS] mất kết nối backend` lặp lại | Backend chưa chạy, `ORCHESTRATOR_URL` sai IP, hoặc Netbird chưa mở 8000 |
| `[READY]` rồi nhưng bấm nút không thấy `[LISTENING]` | Lệnh không tới được device → xem mục `no_device` ở trên |
| `[LISTENING]` rồi nói mà `[TIMEOUT]` | Mic sai device → chạy `probe_stt_live.py`; hạ `VAD_THRESHOLD=0.3` |
| `Could not open microphone` | USB mic chưa nhận (`arecord -l`), hoặc pin cứng `MIC_DEVICE_INDEX` sai sau reboot — **bỏ** biến này đi, code tự dò USB theo tên |
| `Agent request failed` | Agent :8100 chưa chạy hoặc `AGENT_URL` sai |
| STT ra "Hãy subscribe cho kênh..." | Whisper hallucinate trên đoạn quá ngắn — xem mục 7 |
| `OSError: libcudart.so.13` | torchaudio sai CUDA — code đã tự stub, nếu vẫn lỗi thì xem [run-voice-vi.md §5](run-voice-vi.md) |
| Đống log `ALSA lib ... Unknown PCM` | **Bình thường**, PortAudio quét thiết bị. Chạy với `2>/dev/null` |

## 7. Whisper hallucination trên utterance ngắn

Đoạn < ~1s thường ra câu rác học từ dữ liệu YouTube ("Hãy subscribe cho kênh Ghiền Mì Gõ...",
"Cảm ơn các bạn đã theo dõi"). Đây là hành vi đã biết của Whisper, không phải lỗi mic.

Hiện `SILENCE_TIMEOUT=1.5s` cắt utterance, nhưng **không có sàn độ dài** — một tiếng động 0.1s
vẫn được flush thẳng vào STT. Nếu thấy phiền khi demo, thêm ngưỡng bỏ qua utterance quá ngắn ở
chỗ flush ([vad_silero.py:256-266](../../src/edge_voice/perception/vad_silero.py#L256-L266)).
Trong luồng thật ít lộ hơn vì mic chỉ mở đúng một lượt sau khi khách bấm nút.
