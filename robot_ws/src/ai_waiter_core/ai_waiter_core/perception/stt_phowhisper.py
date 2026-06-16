import threading
import queue
import logging

import numpy as np
from faster_whisper import WhisperModel

from ai_waiter_core.config import settings
from ai_waiter_core.perception.queues import speech_queue, put_transcript, Transcript

logger = logging.getLogger(__name__)


class PhoWhisperSTT(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self._model = None

    def _load_model(self):
        device = settings.DEVICE
        compute = "float16" if device == "cuda" else "int8"
        self._model = WhisperModel("small", device=device, compute_type=compute)
        logger.info(f"PhoWhisper loaded: small, device={device}, compute={compute}")

    def _transcribe(self, audio_bytes: bytes) -> str:
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(
            samples,
            language="vi",
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        return " ".join(seg.text.strip() for seg in segments if seg.text.strip())

    def run(self):
        self._load_model()
        logger.info("PhoWhisperSTT started")

        while not self._stop.is_set():
            try:
                chunk = speech_queue.get(timeout=0.5)
                text = self._transcribe(chunk.samples)
                if text:
                    put_transcript(
                        Transcript(
                            text=text,
                            timestamp=chunk.timestamp,
                            audio_duration_s=chunk.duration_s,
                        )
                    )
                    logger.info(f"STT: {text}")
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"STT error: {e}")

        logger.info("PhoWhisperSTT stopped")

    def stop(self):
        self._stop.set()
