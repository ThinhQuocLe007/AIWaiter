import asyncio
import io
import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

logger = logging.getLogger(__name__)

# ── Engine selection ─────────────────────────────────────────────────────────
# Force the cloud engine (edge-tts) regardless of whether piper is installed:
#   TTS_BACKEND=cloud make voice
_FORCE_CLOUD = os.getenv("TTS_BACKEND", "").lower() in ("cloud", "edge", "edge-tts")

try:
    from piper import PiperVoice

    _HAS_PIPER = not _FORCE_CLOUD
except ImportError:
    _HAS_PIPER = False

_PIPER_VOICE: "PiperVoice | None" = None

# ── Model paths ──────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODEL_DIR = _REPO_ROOT / "storage" / "tts"
_PIPER_MODEL_NAME = "vi_VN-vais1000-medium"
_PIPER_ONNX = _MODEL_DIR / f"{_PIPER_MODEL_NAME}.onnx"
_PIPER_JSON = _MODEL_DIR / f"{_PIPER_MODEL_NAME}.onnx.json"
_PIPER_MODEL_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    "/vi/vi_VN/vais1000/medium"
)

# ── Fallback cloud TTS (edge-tts) ────────────────────────────────────────────
VOICE = "vi-VN-HoaiMyNeural"
SAMPLE_RATE = 22050  # matches Piper vais1000-medium; edge-tts output is resampled
CHUNK_SIZE = 4096

TTS_CONFIG = {
    "IDLE": {"rate": "+0%", "pitch": "+0Hz"},
    "DRAFTING": {"rate": "+10%", "pitch": "+0Hz"},
    "AWAITING_CONFIRMATION": {"rate": "-5%", "pitch": "+0Hz"},
    "CONFIRMED": {"rate": "+0%", "pitch": "+2Hz"},
}

SENTENCE_BOUNDARY = re.compile(
    r"(?<=[.!?])\s+|" r"(?<=ạ)\s+|(?<=nhé)\s+|(?<=nha)\s+"
)


def split_vietnamese_sentences(text: str) -> list:
    parts = SENTENCE_BOUNDARY.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


# ── Piper backend ────────────────────────────────────────────────────────────


def _download_piper_model():
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for filename in [f"{_PIPER_MODEL_NAME}.onnx", f"{_PIPER_MODEL_NAME}.onnx.json"]:
        path = _MODEL_DIR / filename
        if path.exists():
            logger.info("piper model cached: %s", path)
            continue
        url = f"{_PIPER_MODEL_URL}/{filename}"
        logger.info("downloading piper model: %s", url)
        subprocess.run(
            ["curl", "-fSL", "--max-time", "120", "-o", str(path), url],
            check=True,
        )


def _synthesize_piper(text: str) -> np.ndarray:
    global _PIPER_VOICE
    if _PIPER_VOICE is None:
        _PIPER_VOICE = PiperVoice.load(str(_PIPER_ONNX), config_path=str(_PIPER_JSON))
    chunks = []
    for chunk in _PIPER_VOICE.synthesize(text):
        if chunk.audio_int16_bytes:
            chunks.append(chunk.audio_int16_bytes)
    pcm = b"".join(chunks)
    return np.frombuffer(pcm, dtype=np.int16)


# ── edge-tts (cloud fallback) ────────────────────────────────────────────────


async def _synthesize_edge_tts(text: str, stage: str = "IDLE") -> np.ndarray:
    import edge_tts

    config = TTS_CONFIG.get(stage, TTS_CONFIG["IDLE"])
    communicate = edge_tts.Communicate(
        text, VOICE, rate=config["rate"], pitch=config["pitch"]
    )
    mp3_data = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_data.write(chunk["data"])
    mp3_data.seek(0)
    samples, _ = sf.read(mp3_data, dtype="float32")
    return (samples * 32767).astype(np.int16)


# ── Public API ───────────────────────────────────────────────────────────────


def synthesize(text: str, stage: str = "IDLE") -> np.ndarray:
    if _HAS_PIPER and _PIPER_VOICE is not None:
        return _synthesize_piper(text)
    return asyncio.run(_synthesize_edge_tts(text, stage))


# ── Streaming player ─────────────────────────────────────────────────────────


class StreamingPlayer:
    def __init__(self, vad=None):
        self._vad = vad
        self._stop = threading.Event()

    def play_sentence(self, audio: np.ndarray):
        if self._stop.is_set():
            return
        sd.play(audio, samplerate=SAMPLE_RATE, blocking=False)
        while sd.get_stream() is not None and sd.get_stream().active:
            if self._stop.is_set():
                sd.stop()
                break
            if self._vad and self._vad.is_speaking():
                sd.stop()
                break
            time.sleep(0.05)

    def interrupt(self):
        self._stop.set()
        try:
            sd.stop()
        except Exception:
            pass

    def is_stopped(self) -> bool:
        return self._stop.is_set()

    def reset(self):
        self._stop.clear()


# ── Speech functions ─────────────────────────────────────────────────────────


def speak_streaming(text: str, stage: str, player: StreamingPlayer):
    sentences = split_vietnamese_sentences(text)
    if not sentences:
        return

    audio = synthesize(sentences[0], stage)
    player.play_sentence(audio)

    if len(sentences) > 1 and not player.is_stopped():
        for sent in sentences[1:]:
            if player.is_stopped():
                break
            audio = synthesize(sent, stage)
            if not player.is_stopped():
                player.play_sentence(audio)


def speak_sentence(text: str, player: StreamingPlayer) -> None:
    """Play a single pre-split sentence through TTS immediately (streaming path)."""
    if not text.strip():
        return
    audio = synthesize(text)
    if not player.is_stopped():
        player.play_sentence(audio)


def warmup() -> None:
    if _HAS_PIPER:
        _download_piper_model()
        _synthesize_piper(".")
        logger.info("TTS warmup complete (piper)")
    else:
        asyncio.run(_synthesize_edge_tts(".", "IDLE"))
        logger.info("TTS warmup complete (edge-tts fallback)")
