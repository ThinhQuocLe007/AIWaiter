import threading
import time
import logging
import os
from math import gcd

import numpy as np
import torch

from ai_waiter_core.perception.queues import AudioChunk, put_speech

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SIZE = 512
CHUNK_DURATION = CHUNK_SIZE / SAMPLE_RATE
SILENCE_TIMEOUT = 1.5
SILENCE_FRAMES_NEEDED = int(SILENCE_TIMEOUT / CHUNK_DURATION)


class SileroVAD(threading.Thread):
    def __init__(self, threshold: float = None):
        super().__init__(daemon=True)
        self.threshold = threshold or float(os.getenv("VAD_THRESHOLD", "0.5"))
        self._stop = threading.Event()
        self._current_utterance = []
        self._model = None
        self._stream = None
        self._p = None
        # mic capture / resampling state (set in _open_mic)
        self._native_rate = SAMPLE_RATE
        self._channels = 1
        self._frames_per_read = CHUNK_SIZE
        self._up = 1
        self._down = 1
        self._resample_poly = None  # callable when native_rate != SAMPLE_RATE
        self._resamp_buf = np.empty(0, dtype=np.float32)

    def _load_model(self):
        self._model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,  # avoid input() prompt -> EOFError when running non-interactive (service/Jetson)
        )
        logger.info(
            f"SileroVAD model loaded on cpu "
            f"(threshold={self.threshold}, timeout={SILENCE_TIMEOUT}s)"
        )

    def _device_index(self):
        """Capture device index, or None to use PortAudio's system default
        (the original behavior). Set MIC_DEVICE_INDEX to force a specific device
        -- e.g. a raw `hw:*` index to bypass a `default`/PipeWire route that is
        unreachable from an SSH shell or a systemd service (PortAudio -9999)."""
        env = os.getenv("MIC_DEVICE_INDEX")
        return int(env) if env not in (None, "") else None

    def _setup_resampler(self, rate: int):
        """Configure a polyphase resampler from `rate` -> SAMPLE_RATE (16k)."""
        self._native_rate = rate
        self._resamp_buf = np.empty(0, dtype=np.float32)
        if rate == SAMPLE_RATE:
            self._resample_poly = None
            self._up = self._down = 1
            return
        from scipy.signal import resample_poly  # scipy is a project dependency
        g = gcd(SAMPLE_RATE, rate)
        self._up = SAMPLE_RATE // g
        self._down = rate // g
        self._resample_poly = resample_poly

    def _open_mic(self):
        import pyaudio  # lazy: only needed to open the mic, not for model load/inference
        self._p = pyaudio.PyAudio()
        idx = self._device_index()
        try:
            info = (self._p.get_device_info_by_index(idx) if idx is not None
                    else self._p.get_default_input_device_info())
        except Exception:  # noqa: BLE001 - no default input device available
            info = None
        dev_default = int(info["defaultSampleRate"]) if info else SAMPLE_RATE

        env_rate = os.getenv("MIC_SAMPLE_RATE")
        if env_rate:
            candidate_rates = [int(env_rate)]
        else:
            # 16k first (no resample), then 48k (clean 3:1), then device native.
            # Many HDA cards (e.g. ALC897) reject 16k with -9997 and need 48k.
            candidate_rates = [SAMPLE_RATE, 48000, dev_default]

        last_err = None
        for rate in dict.fromkeys(candidate_rates):  # dedupe, keep order
            for ch in (1, 2):
                fpb = max(256, round(CHUNK_SIZE * rate / SAMPLE_RATE))
                try:
                    self._stream = self._p.open(
                        format=pyaudio.paInt16,
                        channels=ch,
                        rate=rate,
                        input=True,
                        input_device_index=idx,
                        frames_per_buffer=fpb,
                    )
                except Exception as e:  # noqa: BLE001 - probe each rate/channel combo
                    last_err = e
                    continue
                self._channels = ch
                self._frames_per_read = fpb
                self._setup_resampler(rate)
                name = info["name"] if info else "system default"
                logger.info(
                    f"Mic opened: device={idx} ({name}), rate={rate}Hz, "
                    f"channels={ch} -> resampled to {SAMPLE_RATE}Hz mono"
                )
                return
        raise RuntimeError(f"Could not open microphone (device={idx}): {last_err}")

    def read_chunk(self) -> bytes:
        """Return one CHUNK_SIZE-sample, 16kHz, mono, int16 chunk of audio.

        Reads at the mic's native rate/channels, downmixes to mono and resamples
        to 16kHz, buffering the remainder so any native rate (incl. fractional
        ratios like 44100->16000) yields exact 512-sample chunks.
        """
        while len(self._resamp_buf) < CHUNK_SIZE:
            raw = self._stream.read(self._frames_per_read, exception_on_overflow=False)
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            if self._channels == 2:
                samples = samples.reshape(-1, 2).mean(axis=1)
            if self._resample_poly is not None:
                samples = self._resample_poly(samples, self._up, self._down)
            self._resamp_buf = np.concatenate([self._resamp_buf, samples])
        out = self._resamp_buf[:CHUNK_SIZE]
        self._resamp_buf = self._resamp_buf[CHUNK_SIZE:]
        return np.clip(out, -32768, 32767).astype(np.int16).tobytes()

    def is_speech(self, audio_chunk: bytes) -> bool:
        samples = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        tensor = torch.from_numpy(samples)
        prob = self._model(tensor, SAMPLE_RATE).item()
        return prob >= self.threshold

    def is_speaking(self) -> bool:
        return len(self._current_utterance) > 3

    def run(self):
        self._load_model()
        self._open_mic()

        utterance = []
        self._current_utterance = utterance
        silence_frames = 0

        logger.info("SileroVAD started")

        while not self._stop.is_set():
            try:
                chunk = self.read_chunk()
            except Exception as e:
                logger.error(f"Mic read error: {e}")
                break

            if self.is_speech(chunk):
                utterance.append(chunk)
                silence_frames = 0
            elif utterance:
                silence_frames += 1
                if silence_frames >= SILENCE_FRAMES_NEEDED:
                    audio = b"".join(utterance)
                    timestamp = time.time()
                    duration = len(audio) / SAMPLE_RATE
                    put_speech(AudioChunk(samples=audio, timestamp=timestamp, duration_s=duration))
                    logger.info(f"Utterance flushed: {duration:.1f}s")
                    utterance.clear()
                    silence_frames = 0

        if self._stream:
            self._stream.close()
        if self._p:
            self._p.terminate()
        logger.info("SileroVAD stopped")

    def stop(self):
        self._stop.set()
