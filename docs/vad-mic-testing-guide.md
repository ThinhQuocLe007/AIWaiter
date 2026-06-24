# VAD Microphone Testing Guide

How to run and understand the Silero VAD (Voice Activity Detection) stage of the
voice perception pipeline. Written for testing on a **native Linux laptop**
(e.g. Ubuntu) with a working built-in microphone.

Relevant code:
- `ai_waiter_core/ai_waiter_core/perception/vad_silero.py` — the VAD thread.
- `scripts/probe_vad.py` — standalone probe (RAM + live mic) used here.

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

Quick check that a capture device exists and is not silent:

```bash
arecord -l                              # should list a capture card
arecord -d 3 -f S16_LE -r 16000 test.wav   # speak for 3s
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
