import threading
import time
import logging
import os

import numpy as np
import torch
import pyaudio

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

    def _load_model(self):
        self._model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
        )
        logger.info(
            f"SileroVAD model loaded on cpu "
            f"(threshold={self.threshold}, timeout={SILENCE_TIMEOUT}s)"
        )

    def _open_mic(self):
        self._p = pyaudio.PyAudio()
        self._stream = self._p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

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
                chunk = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
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
