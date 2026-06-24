# Voice Perception Testing Guide (VAD + STT)

How to run and understand the first two stages of the voice perception pipeline
on a **native Linux laptop** (e.g. Ubuntu) with a working built-in microphone:

```
Mic → VAD (Silero, segments speech) → STT (Whisper, speech → text) → Brain
        §1–§6                          §8 (this guide)
```

- **VAD** = *Voice Activity Detection*: finds where an utterance starts and stops,
  then hands the audio to STT. It does **not** transcribe. (§1–§6)
- **STT** = *Speech-To-Text*: turns that audio into Vietnamese text. (§8)

Relevant code:
- `ai_waiter_core/ai_waiter_core/perception/vad_silero.py` — the VAD thread.
- `ai_waiter_core/ai_waiter_core/perception/stt_phowhisper.py` — the STT thread.
- `scripts/probe_vad.py` — standalone VAD probe (RAM + live mic).
- `scripts/probe_stt.py` — standalone STT probe (RAM + wav file → text).

---

## 1. Why test on a native laptop (not over SSH)

The probe records from the microphone of the machine **the process runs on**.
SSH does **not** forward microphone audio. If you SSH from laptop A into desktop
B and run the probe, it captures B's mic (often an empty jack = silence), no
matter what you say into A.

So: **clone the repo onto the laptop you are physically sitting at, and run it
there.** Then the built-in mic is local to the process and works.

---

## 2. Prerequisites

```bash
# System library PyAudio binds to (Debian/Ubuntu):
sudo apt update && sudo apt install -y portaudio19-dev

# Python deps (uses the project's uv environment):
uv sync
```

> **x86 (laptop / desktop):** plain `uv sync` / `uv run` is **not** enough — you
> must pick a CUDA profile, otherwise torch falls back to the CUDA 13 build and
> the GPU/STT break. Use `--extra cu12` (older driver / CUDA 12, e.g. RTX 3050 +
> driver 535) or `--extra cu13` (Blackwell + driver ≥580) on **every** command:
> `uv sync --extra cu12`, then `uv run --extra cu12 python scripts/...`. See §11
> for the full matrix and the `libcublas.so.12 is not found` fix. Jetson
> (aarch64) needs no extra — plain `uv sync`.

Quick check that a capture device exists and is not silent:

```bash
arecord -l                              # should list a capture card
arecord -d 20 -f S16_LE -r 16000 test.wav  # speak for 20s
aplay test.wav                          # play it back — you should hear yourself
```

If `aplay` plays back silence, the OS itself is not capturing — fix that
(unmute / pick the right input in your sound settings) before touching the code.

---

## 3. How to run the probe

### a) Synthetic run (no mic) — sanity check + RAM measurement

```bash
uv run python scripts/probe_vad.py
```

It feeds 200 synthetic chunks (first half noisy "speech-like", second half near
silence) through the real model and prints RSS memory and inference timing. Use
this to confirm the model loads and to measure footprint (useful for Jetson
sizing). No microphone required.

### b) Live mic run

```bash
uv run python scripts/probe_vad.py --mic
```

Speak into the mic. It prints `speech=True` / `speech=False` per ~32 ms chunk.
Press `Ctrl-C` to stop.

Expected healthy output:

```
[after model load ] RSS  ~560 MB
[after open mic    ] RSS  ~627 MB
Mic opened: device=None (<your mic name>), rate=16000Hz, channels=1 -> resampled to 16000Hz mono
[mic] listening... speak, Ctrl-C to stop
  speech=True      <- while you talk
  speech=False     <- while silent
```

If it always says `speech=False` even while talking, see Troubleshooting.

---

## 4. Environment knobs

All optional. Defaults reproduce the original behavior (system default device,
16 kHz).

| Variable | Default | Meaning |
|---|---|---|
| `VAD_THRESHOLD` | `0.5` | Speech probability cutoff. Lower = more sensitive. |
| `MIC_DEVICE_INDEX` | _(unset → system default)_ | Force a specific PortAudio device index. List indices with the snippet below. Use this to bypass a broken `default`/PipeWire route. |
| `MIC_SAMPLE_RATE` | _(unset → auto)_ | Force the native capture rate (e.g. `48000`). |

List device indices:

```bash
uv run python -c "import pyaudio; p=pyaudio.PyAudio(); [print(i, p.get_device_info_by_index(i)['name']) for i in range(p.get_device_count()) if p.get_device_info_by_index(i)['maxInputChannels']>0]"
```

Example:

```bash
MIC_DEVICE_INDEX=4 uv run python scripts/probe_vad.py --mic
```

---

## 5. How the code works

### Constants (`vad_silero.py` top)

- `SAMPLE_RATE = 16000` — Silero VAD **requires** 16 kHz mono input.
- `CHUNK_SIZE = 512` — model processes 512 samples (= 32 ms) at a time.
- `SILENCE_TIMEOUT = 1.5s` → `SILENCE_FRAMES_NEEDED` — how many consecutive
  silent chunks end an utterance.

### The thread lifecycle (`run()`)

```
run()
 ├─ _load_model()      # download/cache Silero from torch.hub, runs on CPU
 ├─ _open_mic()        # open the microphone (see below)
 └─ loop until stop():
      chunk = read_chunk()           # 512 samples, 16 kHz, mono int16
      if is_speech(chunk):           # model prob >= threshold
          utterance.append(chunk)    # accumulate spoken audio
      elif utterance:                # we were speaking, now silent
          silence_frames += 1
          if silence_frames >= SILENCE_FRAMES_NEEDED:
              put_speech(AudioChunk(...))   # flush utterance to speech_queue
              utterance.clear()
```

So VAD's job is: **detect where speech starts and stops, then hand each complete
utterance to the next stage (STT) via `speech_queue`** (see
`perception/queues.py`). It does not transcribe — it only segments audio.

### Opening the mic (`_open_mic()`) — the part that was fixed

The microphone hardware rarely supports 16 kHz natively (many HDA cards like
ALC897 reject it with PortAudio error `-9997`). So instead of forcing 16 kHz:

1. **Device** (`_device_index()`): use the system default device, unless
   `MIC_DEVICE_INDEX` is set.
2. **Rate**: try `16000` first (no resampling needed), then `48000` (a clean 3:1
   ratio to 16 kHz), then the device's native default. Try mono, then stereo.
   The first combination that opens wins.
3. **Resampler** (`_setup_resampler()`): if the opened rate is not 16 kHz, set up
   a polyphase resampler (`scipy.signal.resample_poly`) with the reduced ratio
   `16000 / native_rate`. If it *is* 16 kHz, the resampler is a no-op.

### Reading audio (`read_chunk()`)

Each call must return exactly one 512-sample, 16 kHz, mono `int16` chunk — even
though the mic may be delivering, say, 48 kHz stereo. It:

1. Reads raw frames at the native rate/channels.
2. Downmixes stereo → mono (averages the two channels).
3. Resamples native → 16 kHz (skipped when already 16 kHz).
4. Buffers leftover samples (`_resamp_buf`) so fractional ratios like
   44100→16000 still yield exact 512-sample chunks across calls.

**Key property:** if the mic opens directly at 16 kHz mono (the common case on a
USB mic / Jetson), `read_chunk()` returns the same bytes the original code did —
no resampling, no behavior change. The resampling path only activates when the
hardware forces a different rate.

### Speech detection (`is_speech()`)

Converts the `int16` bytes to a normalized float tensor (`/32768`), runs the
Silero model, and compares the returned probability against `threshold`.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `OSError -9999 Unanticipated host error` | Opening a `default`/PipeWire route that isn't reachable (SSH shell, systemd service, suspended source). | Run natively, or set `MIC_DEVICE_INDEX` to a raw `hw:*` device index. |
| `OSError -9997 Invalid sample rate` | Card doesn't support the requested rate (e.g. 16 kHz). | Already handled: code falls back to 48 kHz + resample. If you forced `MIC_SAMPLE_RATE`, pick a supported rate. |
| Always `speech=False` while talking | Mic captures silence (wrong input selected, muted, or empty jack); or you're on SSH and talking into the wrong machine. | Verify with the `arecord`/`aplay` test in §2. Run natively. |
| Red `ALSA lib pcm_*` lines at startup | Harmless ALSA probing noise from PortAudio scanning devices. | Ignore — if `Mic opened:` is logged afterward, capture succeeded. |
| Too sensitive / not sensitive enough | Threshold. | Tune `VAD_THRESHOLD` (e.g. `0.3` more sensitive, `0.7` stricter). |

---

## 7. Note for Jetson deployment

On the Jetson the microphone (typically USB) is wired directly to the device, so
it is local to the process — the SSH limitation above does not apply. If that
mic supports 16 kHz mono, `_open_mic()` opens it directly and the resampling path
never runs. `scipy` is only imported/used when a non-16 kHz rate is selected.

---

## 8. Testing the STT (speech-to-text) stage

VAD only **segments** audio. The next stage, **STT**, turns each utterance into
Vietnamese text. Test it with `scripts/probe_stt.py`, which reuses the real
`PhoWhisperSTT._load_model()` + `_transcribe()` so the measured RAM and output
match the runtime exactly.

### 8.1 What model actually runs (read this first)

Despite the file/class name `stt_phowhisper.py` / `PhoWhisperSTT`, the code
currently loads **OpenAI Whisper `small`** via `faster-whisper`, **not** an actual
PhoWhisper model:

```python
self._model = WhisperModel("small", device=device, compute_type=compute)
```

| Aspect | Value |
|---|---|
| Engine | `faster-whisper` (runs on ctranslate2) |
| Model | Whisper **`small`** (~460 MB, multilingual) |
| Language | forced `language="vi"` |
| Device | `settings.DEVICE` (from `.env`: `DEVICE=cuda`) |
| Compute type | `cuda` → `float16`; `cpu` → `int8` |

So if Vietnamese transcription quality is mediocre (esp. dish names / jargon),
that is expected for vanilla Whisper `small` — it is not a mic or file problem.
Swapping in a real PhoWhisper model is a separate change.

### 8.2 Prerequisites

Same env as VAD (`uv sync`). STT downloads the Whisper `small` weights from
Hugging Face on first run and caches them (`~/.cache/huggingface`), so the **first
run needs internet** and is slower; later runs are offline.

Confirm which device it will use:

```bash
# Should print: CUDA available: True  (if you have an NVIDIA GPU + matching torch)
uv run python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

`DEVICE=cuda` in `.env` + CUDA available → STT runs on the **GPU (float16)**.
Set `DEVICE=cpu` in `.env` to force CPU (`int8`) — slower but no GPU needed.

### 8.3 Synthetic run (no mic) — sanity check + RAM

```bash
uv run python scripts/probe_stt.py
```

Feeds 5 s of random noise through the real model. Expected: it **loads the model**
and prints timing + RAM, with an **empty** transcript (noise has no speech):

```
[cfg] DEVICE=cuda  -> compute=float16
[time] load model: 4.2s
[after model load ] RSS  ~900 MB | GPU alloc ... MB
[time] transcribe: 0.6s
[stt out] ''            <- empty is CORRECT here: pure noise, nothing to transcribe
```

Use this only to confirm the model loads and to read its memory footprint. To
actually see text, you need real speech (§8.4).

### 8.4 Real speech run — record a wav, get text

```bash
# 1. Record 20 seconds of Vietnamese speech, 16 kHz mono (the format STT expects)
arecord -d 20 -f S16_LE -r 16000 test.wav

# 2. (optional) play it back to confirm the mic captured you, not silence
aplay test.wav

# 3. Transcribe it
uv run python scripts/probe_stt.py --audio test.wav
```

The last line is the model's transcript:

```
[stt out] 'cho tôi một ly cà phê sữa và một phần cơm gà'
```

That string is what STT heard from your voice. Compare it to what you said to
judge the model's accuracy.

### 8.5 Notes & gotchas

| Point | Detail |
|---|---|
| **File must be 16 kHz** | `arecord -r 16000` already does this. If you record elsewhere at 44.1/48 kHz, the probe prints `[warn] ... result may be wrong` and the text will be garbled. Re-record at 16 kHz. |
| **Mono** | `-f S16_LE` mono is expected; if the wav is stereo the probe takes the first channel automatically. |
| **First run is slow** | Downloads Whisper `small` weights once, then caches. Time it on the *second* run for the real load speed. |
| **Empty output on real speech** | Usually the wav is actually silent (wrong input / muted / SSH'd into the wrong machine) — verify with `aplay` in step 2. STT also runs its own internal VAD filter, so very quiet audio yields `''`. |
| **GPU memory** | On the dev laptop the GPU has room. On the **Jetson Orin 8 GB unified memory**, STT shares GPU RAM with the Ollama LLM + embedding model — watch the `GPU alloc` line and `tegrastats`/`jtop` to confirm it fits the budget. |

### 8.6 Note for Jetson

`faster-whisper` uses ctranslate2, which manages CUDA memory **outside** torch, so
`torch.cuda.memory_allocated()` (the `GPU alloc` line) may read near 0 even on CUDA.
On the Jetson, trust **`tegrastats`** / **`jtop`** (unified RAM) for the real
figure, not the probe's GPU number. Run one of those in a second terminal while
the probe transcribes.

---

## 9. Real-time mic → text (Ubuntu laptop)

`probe_stt.py` (§8) only does **file → text**. To test the live experience —
**speak and watch text appear** — use `scripts/probe_stt_live.py`. It runs the
real `SileroVAD` + `PhoWhisperSTT` threads together (the same wiring as
`ai_waiter_core/main.py`) but **without** the agent / LLM / TTS, so it isolates
just the *mic → VAD → STT* path. No Ollama needed.

```bash
# NATIVE machine with a working local mic — NOT over SSH (see §1).
uv run python scripts/probe_stt_live.py
```

Speak Vietnamese; each finished utterance prints as:

```
[cfg] DEVICE=cuda  (STT compute: float16)
====================================================
 Live STT ready — speak Vietnamese into the mic
 Ctrl-C to stop
====================================================
[HEARD @  3.4s | 1.6s audio]: cho tôi một ly cà phê sữa
[HEARD @  9.1s | 2.0s audio]: thêm một phần cơm gà nữa
```

How it flows: **VAD opens the mic and detects where each sentence starts/stops**
→ hands the audio to **STT** → STT transcribes → the line prints. There is a short
pause (`SILENCE_TIMEOUT = 1.5s`, see §5) after you stop talking before the text
appears — that is the VAD deciding the utterance ended, not a hang.

Same tuning knobs as the VAD probe (§4):

```bash
VAD_THRESHOLD=0.4 MIC_DEVICE_INDEX=4 uv run python scripts/probe_stt_live.py
```

If nothing ever prints: first confirm the mic with the VAD probe
(`uv run python scripts/probe_vad.py --mic` — does it show `speech=True` when you
talk?). If VAD sees speech but no text appears, the problem is STT, not the mic.

---

## 10. Jetson voice testing (SSH workflow: record → scp → transcribe)

The Jetson is reached over SSH, and **SSH does not forward microphone audio**
(§1). So the live mic flow (§9) cannot be driven from your laptop into the Jetson.
Instead, **record on the laptop, copy the file over, transcribe on the Jetson** —
this still validates the Jetson's STT model + memory footprint on the real target.

```bash
# 1. ON THE LAPTOP — record 20s of Vietnamese, 16 kHz mono
arecord -d 20 -f S16_LE -r 16000 test.wav
aplay test.wav                          # confirm it captured you, not silence

# 2. COPY to the Jetson (adjust user@host and path)
scp test.wav jetson@<jetson-ip>:~/AI_Waiver/

# 3. ON THE JETSON (over SSH) — transcribe + measure RAM
ssh jetson@<jetson-ip>
cd ~/AI_Waiver
uv run python scripts/probe_stt.py --audio test.wav
```

Read the `[stt out]` line for accuracy, and watch unified RAM on the Jetson with
`tegrastats` (or `jtop`) in a second SSH session while step 3 runs.

### What this covers vs. what it does NOT

| Validated by this flow | NOT validated (needs a mic wired to the Jetson) |
|---|---|
| STT model loads on the Jetson (arch/driver/CUDA OK) | Live mic capture on the Jetson itself |
| Transcription accuracy on real Vietnamese audio | VAD segmentation timing from a live stream |
| **Unified-memory footprint** on the 8 GB target | End-to-end latency *speak → text* on device |

To close those gaps later: plug a **USB mic directly into the Jetson** (then it is
local to the process — the SSH limitation no longer applies, §7) and run
`scripts/probe_stt_live.py` (§9) **in the SSH shell**. The audio is captured by
the Jetson's own USB mic, not forwarded over SSH, so it works. That is the only
way to measure true on-device *speak → text* latency before wiring TTS + agent.

---

## 11. GPU / torch setup per machine (CUDA 12 vs 13)

### The symptom

```
STT error: Library libcublas.so.12 is not found or cannot be loaded
```
…and/or torch silently runs on CPU:
```
UserWarning: CUDA initialization: The NVIDIA driver on your system is too old
torch 2.12.1+cu130 | built for CUDA 13.0 | cuda available: False
```

### Why it happens

The fleet spans **three machine classes that cannot share one torch build**:

| Machine | arch | GPU / driver | CUDA | torch build |
|---|---|---|---|---|
| Jetson Orin (JetPack 6.2) | aarch64 | Tegra (JetPack) | 12.6 | `2.11.0` cu126 (jetson-ai-lab index) |
| Desktop LLM host (Blackwell sm_120) | x86_64 | driver ≥580 | **13.0** | `≥2.12` cu130 (PyPI) |
| Laptop / older GPU (e.g. RTX 3050) | x86_64 | driver 535 → CUDA 12.2 | **12.x** | `2.5.1` cu121 |

Two gotchas combine into the error:

1. **`torch ≥ 2.12` has _no_ CUDA 12 build** — from 2.6 onward PyTorch ships only
   cu124/126/128/130. So a CUDA-12 machine **cannot** use torch ≥2.12 at all.
2. **`platform_machine` can't tell the two x86 boxes apart** — Blackwell and the
   laptop are both `x86_64 linux`, yet need cu130 vs cu121. A marker alone can't
   branch on the GPU/driver.

So when the laptop resolved the default x86 dependency (`torch ≥2.12`), it pulled
`torch 2.12.1+cu130`. Driver 535 (CUDA 12.2) is too old for CUDA 13 → torch
disables the GPU, and `ctranslate2` (faster-whisper's engine, built for **CUDA
12**) can't find `libcublas.so.12`. STT dies.

> **Driver number ≠ CUDA number.** `nvidia-smi`'s "CUDA Version: 12.2" is the
> _highest_ CUDA the **driver** supports, not what's installed in the venv. And you
> do **not** need a specific driver version: any CUDA **12.x** torch wheel runs on
> any driver ≥525 thanks to CUDA-12 minor-version forward-compat. Keep driver 535
> on the laptop — only **CUDA 13** (Blackwell) needs a new driver (≥580).

### The fix: explicit install profiles (uv extras)

[`pyproject.toml`](../pyproject.toml) defines two conflicting extras so each x86
machine opts into its own CUDA build; aarch64 (Jetson) stays automatic via marker:

```toml
[project.optional-dependencies]
cu13 = [ "torch>=2.12 ; platform_machine=='x86_64'", ... ]   # Blackwell, CUDA 13 (PyPI)
cu12 = [ "torch==2.5.1 ; platform_machine=='x86_64'", ... ]  # CUDA 12 (download.pytorch.org/whl/cu121)

[tool.uv]
conflicts = [[{ extra = "cu12" }, { extra = "cu13" }]]
```

Install per machine:

```bash
# Laptop / older GPU + CUDA 12 driver (this is the RTX 3050 + driver 535 fix):
uv sync --extra cu12

# Desktop Blackwell host:
uv sync --extra cu13

# Jetson (aarch64) — no extra needed:
uv sync
```

### ⚠️ `uv run` re-syncs — always pass the extra on x86

`uv run` auto-syncs to the project default **before** running. On x86 a bare
`uv run python ...` will _silently reinstall the cu13 build_ and undo your
`--extra cu12`. So pass the extra on **every** invocation:

```bash
uv run --extra cu12 python scripts/probe_stt_live.py      # laptop
uv run --extra cu13 python scripts/probe_stt_live.py      # Blackwell
```

To stop the churn on a fixed deployment machine, sync once then disable auto-sync:

```bash
uv sync --extra cu12
export UV_NO_SYNC=1            # add to ~/.bashrc; `uv run` now uses the cu12 env as-is
uv run python scripts/probe_stt_live.py
```

### Verify the GPU is actually used

```bash
uv run --extra cu12 python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO GPU')"
# expect: 2.5.1+cu121 True NVIDIA GeForce RTX 3050 Ti Laptop GPU
```

On the laptop the cu12 profile also pulls `nvidia-cublas-cu12` + `nvidia-cudnn-cu12`
(cuDNN 9), which is exactly what `ctranslate2` needs — so `libcublas.so.12` is
resolved and STT runs on `float16` GPU.

> **Note for the Blackwell (cu13) host:** `ctranslate2` 4.x is still CUDA-12 only,
> so faster-whisper there will _also_ look for `libcublas.so.12` despite torch
> being cu13. Either keep STT on the Jetson/edge (where the mic lives), or add
> `nvidia-cublas-cu12 nvidia-cudnn-cu12` to that box, or run STT on CPU there.
