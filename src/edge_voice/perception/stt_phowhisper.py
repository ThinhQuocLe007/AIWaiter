import threading
import queue
import logging
import re

import numpy as np
from faster_whisper import WhisperModel

from src.agent_brain.config import settings
from src.edge_voice.perception.queues import speech_queue, put_transcript, Transcript

logger = logging.getLogger(__name__)

# Single source of truth for the faster-whisper model size.
# Change this to switch models (e.g. "small", "medium", "large-v3", "large-v3-turbo").
# probe_stt.py reads this so its download progress bar always matches the real model.
MODEL_SIZE = "medium"

# Whisper hallucinates YouTube boilerplate on short/noisy segments -- a 0.4s pallet drop comes back
# as "Hãy subscribe cho kênh Ghiền Mì Gõ...". Nothing downstream filters by duration, so that
# invented sentence would go straight to the agent and the robot would answer it out loud in front
# of the room. These phrases come from the video captions Whisper was trained on and never occur in
# a warehouse command, so dropping the whole utterance on a match is safe.
#
# Matched against the text lowercased with punctuation stripped (see _is_hallucination). Add new
# ones here as they show up in the logs -- they are logged, not silently swallowed.
_HALLUCINATION_PATTERNS = [
    re.compile(p) for p in (
        r"subscribe",
        r"đăng ký kênh",
        r"ghiền mì gõ",
        r"hẹn gặp lại (ở|trong) (video|clip)",
        r"(video|clip) (tiếp theo|sau)",
        r"(cảm ơn|cám ơn) (các bạn |mọi người )?đã (xem|theo dõi)",
        r"(nhấn|bấm|ấn) (like|chuông|đăng ký)",
        r"(chúc|mời) (các bạn|quý vị) xem (video|clip)",
        r"phụ đề (được (thực hiện|làm) bởi|bởi)",
    )
]

# Keep letters (incl. Vietnamese diacritics) and spaces; drop punctuation Whisper sprinkles in.
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def _is_hallucination(text: str) -> bool:
    """True if `text` is Whisper's video-caption boilerplate rather than a spoken command."""
    norm = _PUNCT.sub(" ", text.lower())
    norm = " ".join(norm.split())
    return any(pat.search(norm) for pat in _HALLUCINATION_PATTERNS)


class PhoWhisperSTT(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self._ready = threading.Event()  # set once the model is loaded in run()
        self._model = None

    def _load_model(self):
        device = settings.DEVICE
        compute = "float16" if device == "cuda" else "int8"
        self._model = WhisperModel(MODEL_SIZE, device=device, compute_type=compute)
        self._ready.set()
        logger.info(f"PhoWhisper loaded: {MODEL_SIZE}, device={device}, compute={compute}")

    def warmup(self, timeout: float = 120.0) -> None:
        """Force the first (slow) CTranslate2 inference at startup so the first real turn is fast.
        Waits for the model to finish loading in run(), then transcribes a short silent buffer."""
        if not self._ready.wait(timeout):
            logger.warning("STT warmup skipped: model not ready after %.0fs", timeout)
            return
        silent = np.zeros(8000, dtype=np.float32)  # 0.5s @ 16kHz
        list(self._model.transcribe(silent, language="vi", beam_size=1, vad_filter=False)[0])
        logger.info("PhoWhisper warmup done")

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
                if text and _is_hallucination(text):
                    # Log it: a dropped turn that vanished silently looks identical to a dead mic.
                    logger.info(f"STT bỏ qua (câu bịa của Whisper, {chunk.duration_s:.1f}s): {text}")
                    text = ""
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
