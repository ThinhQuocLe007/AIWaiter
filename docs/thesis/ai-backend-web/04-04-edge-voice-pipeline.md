## 4.4 Edge Deployment & Voice Pipeline

> **Status:** draft
> **Cross-refs:** §4.2 for overall architecture, §4.3 for agent pipeline, §4.5.6 for voice bridge, §5.3.5 for voice evaluation
> **Source:** `src/edge_voice/main.py` (235 lines), `perception/vad_silero.py` (221 lines), `perception/stt_phowhisper.py` (79 lines), `output/tts_engine.py` (188 lines)
> **Figures needed:** Fig 4.4.1 (voice pipeline threading architecture: mic → VAD thread → speech_queue → STT thread → text_queue → main loop → TTS)

---

The system accepts spoken Vietnamese and replies in spoken Vietnamese. Voice capture and synthesis are deployed on the Jetson Orin Nano at the robot edge, with the LLM agent residing on the central server. This section describes the architecture of this deployment split and the voice processing pipeline that transforms microphone audio into agent text and agent text into speaker audio.

### 4.4.1 Edge/Server Split Rationale

The voice pipeline is split across two physical machines, driven by hardware constraints and latency budgets.

**Why voice I/O on the Jetson edge?** Speech input/output hardware (microphone, speaker) is physically on the robot, making the Jetson the natural compute point. Three considerations support this choice:

1. **GPU-light models run on Jetson.** The Silero VAD model (~2 MB) and faster-whisper medium (~1.5 GB on disk, ~3 GB VRAM with float16) fit within the Jetson Orin Nano's 8 GB unified memory. The TTS engine (Piper, ~200 MB for the Vietnamese voice model) is also GPU-light. These models use the Jetson's CUDA cores for inference acceleration on the `aarch64` architecture.

2. **Local STT avoids audio upload latency.** Raw 16 kHz mono PCM audio for a typical utterance (3–5 seconds) is ~96–160 KB. Uploading this over WiFi adds 50–100ms round-trip latency plus variable network jitter. Running STT locally eliminates this overhead: the audio never leaves the Jetson — only the text transcript (a few bytes) is sent to the server.

3. **STT survives temporary WiFi drops.** Voice capture (VAD + microphone) and transcription (faster-whisper) complete locally on the Jetson. The text transcript is a tiny payload that can be POSTed when WiFi recovers. If the server-side LLM is temporarily unreachable, the voice pipeline still captures and transcribes the utterance — the agent call can be retried.

**Why the LLM agent on the server?** The LLM (Qwen2.5 7B, ~6–8 GB VRAM in float16) requires server-grade GPU memory. Running it on the Jetson Orin Nano would require aggressive 4-bit quantization with significant quality degradation, particularly for Vietnamese (which is already underrepresented in training data). The HTTP text round-trip (Jetson → server → Jetson) adds ~2–4s total, but this is dominated by LLM inference (1–2s), not network transfer of text payloads (<50ms on local WiFi).

**Protocol.** The edge voice device connects to the orchestrator WebSocket as `role=voice-device&robot_id=<id>` (`main.py:64`). The tablet-to-voice flow traverses three components:

1. Customer presses "Talk to AI" on the tablet → `POST /voice/listen {table_id}` to the orchestrator.
2. The orchestrator's voice bridge resolves `table_id → robot_id` via the dynamic table-robot binding (§4.5.6) and sends `start_listening` to the Jetson's `voice-device` WebSocket (`routers/voice.py:66-69`).
3. The Jetson arms the microphone, captures one utterance, transcribes it, and POSTs the text to the agent `/chat` or `/chat/stream`.
4. The agent's response text is POSTed to `POST /voice/event` on the orchestrator, which fans it to the customer's tablet WebSocket (`role=customer`) for the voice mirror display.

The browser never touches the microphone — the tablet is a display and signal device, not an audio capture device. This eliminates the need for HTTPS (microphone access requires a secure context in browsers) and keeps the voice pipeline a native Python service.

### 4.4.2 Threaded Pipeline Architecture

The voice pipeline runs as a multi-threaded Python process with three concurrent threads that pass data through bounded queues. This architecture separates blocking I/O operations (microphone read, model inference, network HTTP) into independent threads so that no stage blocks another.

```
┌─────────────────┐     speech_queue      ┌─────────────────┐     text_queue      ┌──────────────────┐
│   VAD Thread    │ ──────────────────►   │   STT Thread    │ ────────────────►   │   Main Thread    │
│                 │    AudioChunk         │                 │    Transcript      │                  │
│  Silero VAD     │                       │  faster-whisper │                    │  HTTP → Agent    │
│  Mic capture    │                       │  PhoWhisper     │                    │  TTS playback    │
│  16kHz resample │                       │  beam_size=5    │                    │  WS command loop │
└─────────────────┘                       └─────────────────┘                    └──────────────────┘
       ▲                                                                                 │
       │ gated (start_listening)                                                          ▼
       │                                                                         ┌──────────────────┐
  ┌────┴────────────┐                                                            │  StreamingPlayer │
  │  Microphone     │                                                            │  sounddevice     │
  │  (PyAudio)      │                                                            │  VAD barge-in    │
  └─────────────────┘                                                            └──────────────────┘
```

**Bounded queues.** Both inter-thread queues have a maximum capacity of 10 items (`queues.py:16-17`). If the STT thread falls behind (VAD produces utterances faster than STT can transcribe), the `speech_queue` fills and new utterances are dropped with a warning log. In practice, the single-utterance mode (one utterance per `start_listening`) means the queues never exceed 1 item — the bound is safety against pathological conditions.

**Thread-safe shutdown.** On SIGTERM or KeyboardInterrupt, all threads are stopped in order: VAD thread (closes microphone, terminates PyAudio), STT thread, and TTS player. Queues are drained to prevent stuck `put()` calls.

#### VAD Thread — Voice Activity Detection

The VAD thread (`vad_silero.py:21`) is a `threading.Thread` subclass that runs the Silero VAD model and microphone capture loop. It is the only thread that touches audio hardware.

**Model.** The Silero VAD model is loaded via `torch.hub.load("snakers4/silero-vad", "silero_vad")` at thread startup. Silero VAD is a lightweight neural network (~2 MB) that classifies 512-sample frames at 16 kHz as speech or silence. It is language-agnostic — it detects voice activity based on acoustic features, not linguistic content — which makes it effective for Vietnamese without language-specific adaptation.

**Microphone capture.** The microphone is opened via PyAudio at the highest compatible sample rate. The capture pipeline (`vad_silero.py:79-123`) tries rates in priority order: 16 kHz (native, no resampling), 48 kHz (clean 3:1 downsampling for HDA cards that reject 16 kHz), then the device's default rate. Audio is captured in native-format chunks, downmixed to mono (if stereo), and resampled to 16 kHz via `scipy.signal.resample_poly` polyphase filtering. Residual samples from fractional resampling ratios (e.g., 44.1 kHz → 16 kHz) are buffered between reads to ensure exact 512-sample chunk boundaries.

**Gated capture.** The microphone stays open but capture is gated — audio is only collected when `_listening` is set. This prevents continuous eavesdropping. The gate is armed by `begin_listen()` (called from the WebSocket command handler when `start_listening` arrives) and auto-disarmed when an utterance is flushed. Between utterances, the microphone is read but audio is discarded — the model stays warm but nothing is captured.

**Speech detection.** Each 512-sample chunk is classified by Silero VAD with a probability threshold of 0.50 (`vad_silero.py:24`). When speech is detected, the chunk is appended to the current utterance buffer. Silence frames are counted; after 1.5 seconds of continuous silence (`SILENCE_TIMEOUT = 1.5s` → `SILENCE_FRAMES_NEEDED = 47` frames at 512 samples / 16000 Hz = 32ms per frame), the utterance is considered complete. The complete audio buffer is placed on the `speech_queue` as an `AudioChunk` (raw int16 bytes, timestamp, duration), and the gate auto-disarms.

**Padding.** The gate's auto-disarm after 1.5s of silence provides implicit end-padding — the audio includes trailing silence that helps STT models detect utterance boundaries. Pre-padding (silence before the first speech frame) is inherent to the gated mode: audio only starts being collected when Silero detects speech, so there is no leading silence to pad.

**Cancel support.** `cancel_listen()` (`vad_silero.py:163-171`) immediately disarms the gate and unblocks the waiter. Any partially captured utterance is discarded. This is triggered by the tablet's "Hủy" button via `POST /voice/cancel`.

#### STT Thread — Speech-to-Text

The STT thread (`stt_phowhisper.py:19`) consumes `AudioChunk` objects from the `speech_queue` and produces `Transcript` objects on the `text_queue`.

**Model.** faster-whisper medium is loaded via the CTranslate2 backend (`stt_phowhisper.py:29`). faster-whisper is an optimized reimplementation of OpenAI's Whisper that uses CTranslate2 for efficient inference — on the Jetson's CUDA cores, it achieves ~800ms per utterance compared to 2–3s with the original Whisper implementation. The model uses float16 precision on CUDA and int8 on CPU (`stt_phowhisper.py:28`). PhoWhisper weights (Whisper fine-tuned on Vietnamese data) improve tonal accuracy for Vietnamese's six-tone system, though the standard faster-whisper medium model is used as the base (PhoWhisper weights are loaded as fine-tune checkpoints when available).

**Transcription parameters.** Transcription uses `language="vi"`, `beam_size=5`, and built-in VAD filtering (`vad_filter=True` with `min_silence_duration_ms=500`). The built-in VAD filter is a secondary safety net — Silero VAD already segments utterances, but faster-whisper's internal VAD can further trim leading/trailing silence and split very long utterances into segments. Beam size 5 balances accuracy against latency (higher beam sizes improve accuracy marginally but increase compute time linearly).

**Warmup.** At startup, the STT thread is warmed up by transcribing a 0.5-second silent buffer (`stt_phowhisper.py:33-41`). The first CTranslate2 inference is disproportionately slow (model compilation, GPU kernel JIT) — this warmup absorbs that cost before any customer utterance arrives.

**Error handling.** Transcription errors (model crash, CUDA OOM) are caught and logged; the STT thread continues running. If transcription produces no text (empty output, noise-only input), no `Transcript` is placed on the queue — the main loop handles the timeout.

#### Main Thread — Orchestration and TTS

The main thread (`main.py:157-186`) runs the `asyncio` event loop that manages the WebSocket connection to the orchestrator. This is the only async component — all voice processing (VAD, STT, TTS) is synchronous and runs in daemon threads.

**WebSocket lifecycle.** The device connects to the orchestrator at `ws://<backend>/ws?role=voice-device&robot_id=<id>` with exponential backoff reconnection (max 10s, `main.py:58`). It idles indefinitely, processing incoming messages. The only actionable message is `start_listening`, which carries a `table_id`. On receipt, the handler calls `asyncio.to_thread(_capture_and_send_streaming, vad, agent_client, table_id, player)` — this offloads the blocking voice capture to a thread pool, keeping the WebSocket responsive for subsequent commands (e.g., `cancel_listening`).

**Capture-and-send flow** (`main.py:111-154`):
1. Drain any stale transcript from the `text_queue` (ensures the captured text matches the current utterance, not a leftover).
2. Arm the VAD gate via `vad.begin_listen()`.
3. Block on `vad.wait_for_utterance(15.0)` — 15-second timeout for the customer to begin speaking.
4. Block on `get_transcript(12.0)` — 12-second timeout for STT to produce a result.
5. If no transcript or empty text, return to idle (no agent call).
6. POST the transcript to the agent `/chat/stream` with `table_id=f"T{table_id}"`.
7. Consume the SSE stream: for each `sentence` event, call `speak_sentence()` for immediate TTS playback. On `done` event, return to idle.

**Single-utterance mode.** The pipeline captures exactly one utterance per `start_listening` command, then auto-idles. This gives the customer explicit control over when the robot listens — they press "Talk to AI" for each turn. This design was chosen over continuous listening for two reasons: (a) it prevents false triggers from ambient restaurant noise (conversations at other tables, kitchen sounds) from being sent to the LLM; (b) it matches the turn-taking model of restaurant service — the waiter listens when the customer signals readiness, not continuously.

### 4.4.3 Barge-In Mechanism

Natural conversation involves interruption — a customer might correct an order or change their mind while the robot is speaking. The barge-in mechanism allows the customer to interrupt TTS playback by speaking.

**Sentence-level TTS.** The TTS playback is sentence-by-sentence, aligned with the agent's SSE output. The `StreamingPlayer` (`tts_engine.py:120-149`) plays each sentence via `sounddevice` as a blocking play with a tight polling loop (50ms sleep). During playback, two conditions are checked:

1. **Stop flag:** If `player.interrupt()` was called (from a `cancel_listening` command or shutdown), playback stops immediately.
2. **VAD speech detection:** If a VAD instance is provided to the player, `vad.is_speaking()` is polled each cycle. The VAD thread runs concurrently — even during playback, it continues reading the microphone. If it detects speech (more than 3 speech frames in the current utterance buffer), the player calls `sd.stop()` and exits the playback loop.

The customer's new speech triggers the VAD thread to begin capturing a new utterance. The main loop completes the current `_capture_and_send_streaming` call (which was interrupted — the TTS player stopped mid-sentence), then processes the new utterance normally. From the customer's perspective: the robot stops talking, listens, and responds to the new utterance.

**False barge-in prevention.** The VAD `is_speaking()` check requires at least 3 speech frames in the utterance buffer (`vad_silero.py:150-151`) before it reports speech. This prevents transient noises (plate clink, chair scrape) from triggering an interruption. Combined with the 1.5s silence timeout, only sustained human speech triggers barge-in.

### 4.4.4 TTS Strategy

The TTS engine (`tts_engine.py`) supports two backends with automatic fallback:

**Primary: Piper TTS (local).** Piper is an offline neural TTS engine that runs entirely on the Jetson with no network dependency. The Vietnamese voice model (`vi_VN-vais1000-medium`, ~200 MB) is downloaded from HuggingFace at first startup and cached to `storage/tts/`. Piper synthesizes text to raw PCM int16 audio via `PiperVoice.synthesize()`, which streams audio chunks incrementally. Latency is ~500ms per sentence on the Jetson.

Piper is the preferred backend because it satisfies NFR1 (self-hosted, no cloud dependency). However, Piper requires compilation of its C++ ONNX runtime bindings, which may not be available on all platforms (particularly x86 dev machines).

**Fallback: edge-tts (Microsoft Azure cloud).** When Piper is unavailable (`_HAS_PIPER = False`), the system falls back to edge-tts, which calls Microsoft Azure's Vietnamese Neural TTS voices (`vi-VN-HoaiMyNeural`). edge-tts streams MP3 audio chunks from the Azure endpoint, which are decoded via `soundfile` and played through the same `StreamingPlayer`. This requires internet connectivity but provides high-quality Vietnamese speech with natural prosody.

**Selection logic** (`tts_engine.py:111-114`):
1. If `_HAS_PIPER` is `True` (Piper library importable) and `_PIPER_VOICE` is loaded (model downloaded and loaded), use Piper.
2. Otherwise, fall back to edge-tts via `asyncio.run(_synthesize_edge_tts(...))`.

On Jetson (aarch64), Piper is the primary path. On x86 dev machines, Piper is typically unavailable (build dependencies), and edge-tts serves as the development TTS backend.

**Stage-aware prosody.** The TTS engine adjusts speech rate and pitch based on the agent's current `order_stage` (`tts_engine.py:42-47`):

| Stage | Rate | Pitch | Rationale |
|-------|------|-------|-----------|
| `IDLE` | +0% | +0Hz | Default neutral speech |
| `DRAFTING` | +10% | +0Hz | Slightly faster pacing during active ordering |
| `AWAITING_CONFIRMATION` | −5% | +0Hz | Slightly slower, emphasizing the confirmation request |
| `CONFIRMED` | +0% | +2Hz | Slightly brighter tone for order confirmation |

**Vietnamese sentence splitting.** Before synthesis, the response text is split into sentences via a Vietnamese-aware regex (`tts_engine.py:49-51`):

```python
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|(?<=ạ)\s+|(?<=nhé)\s+|(?<=nha)\s+")
```

Standard punctuation (`.`, `!`, `?`) is supplemented with Vietnamese sentence-final particles: "ạ" (politeness marker), "nhé" (suggestion/agreement), "nha" (casual agreement). Splitting at these boundaries produces natural sentence chunks for TTS playback rather than arbitrary character-count splits.

**TTS warmup.** At startup, the TTS engine synthesizes a single character (".") to warm up the model and the audio output device (`main.py:207`). This absorbs first-synthesis latency (model compilation, GPU kernel JIT, audio device initialization) before any customer interaction.

### 4.4.5 Latency Budget

The voice turn latency — from the customer finishing speech to the robot beginning its reply — is budgeted across stages:

| Stage | Location | Duration | Notes |
|-------|----------|----------|-------|
| VAD silence detection + utterance flush | Jetson | ~1.5s | Fixed: 1.5s silence timeout before flush |
| STT (faster-whisper medium) | Jetson | ~0.8s | Variable by utterance length; 3–5s typical utterance |
| HTTP round-trip (text → agent → text) | Network | ~0.05s | Local WiFi, text payloads only |
| Agent inference (MLP classifier routing) | Server | ~0.052s | Embedding (~50ms) + MLP forward (0.17ms) |
| Agent inference (LLM worker + response) | Server | ~1.5–2.5s | LLM inference dominates |
| TTS first sentence | Jetson | ~0.5s | Piper or edge-tts |
| **Total (total voice turn)** | — | **~3–5s** | Within the 5s NFR2 target |

The dominant latency source is the 1.5s VAD silence timeout — this is a fixed parameter chosen to balance responsiveness (shorter timeout = faster response but risk of cutting off the customer) against completeness. The STT and TTS latencies are model-dependent and could be reduced by using smaller models (faster-whisper small instead of medium, Piper low quality instead of medium), trading accuracy for speed.
