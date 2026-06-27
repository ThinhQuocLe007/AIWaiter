import re
import io
import queue
import threading
import logging
import asyncio
import numpy as np
import sounddevice as sd
import soundfile as sf
import edge_tts

logger = logging.getLogger(__name__)

VOICE = "vi-VN-HoaiMyNeural"
SAMPLE_RATE = 24000
CHUNK_SIZE = 4096

TTS_CONFIG = {
    "IDLE":                 {"rate": "+0%",  "pitch": "+0Hz"},
    "DRAFTING":             {"rate": "+10%", "pitch": "+0Hz"},
    "AWAITING_CONFIRMATION": {"rate": "-5%",  "pitch": "+0Hz"},
    "CONFIRMED":            {"rate": "+0%",  "pitch": "+2Hz"},
}

SENTENCE_BOUNDARY = re.compile(
    r"(?<=[.!?])\s+|"
    r"(?<=ạ)\s+|(?<=nhé)\s+|(?<=nha)\s+"
)


def split_vietnamese_sentences(text: str) -> list:
    parts = SENTENCE_BOUNDARY.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


async def synthesize(text: str, stage: str = "IDLE") -> np.ndarray:
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


class StreamingPlayer:
    def __init__(self, vad=None):
        self._vad = vad
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            callback=self._callback,
        )

    def _callback(self, outdata, frames, time_info, status):
        if self._stop.is_set():
            outdata.fill(0)
            raise sd.CallbackStop()
        try:
            chunk = self._queue.get_nowait()
            n = min(len(chunk), len(outdata))
            outdata[:n, 0] = chunk[:n]
            outdata[n:, 0] = 0
        except queue.Empty:
            outdata.fill(0)

    def play_sentence(self, audio: np.ndarray):
        self._stream.start()
        for i in range(0, len(audio), CHUNK_SIZE):
            if self._stop.is_set():
                break
            if self._vad and self._vad.is_speaking():
                self.interrupt()
                break
            self._queue.put(audio[i:i + CHUNK_SIZE])
        self._stream.stop()

    def interrupt(self):
        self._stop.set()
        while not self._queue.empty():
            self._queue.get_nowait()

    def is_stopped(self) -> bool:
        return self._stop.is_set()

    def reset(self):
        self._stop.clear()


async def speak_streaming(text: str, stage: str, player: StreamingPlayer):
    sentences = split_vietnamese_sentences(text)
    if not sentences:
        return

    config = TTS_CONFIG.get(stage, TTS_CONFIG["IDLE"])

    audio = await synthesize(sentences[0], stage)
    player.play_sentence(audio)

    if len(sentences) > 1 and not player.is_stopped():
        for sent in sentences[1:]:
            if player.is_stopped():
                break
            audio = await synthesize(sent, stage)
            if not player.is_stopped():
                player.play_sentence(audio)


async def warmup():
    await synthesize(".", "IDLE")
    logger.info("TTS warmup complete")