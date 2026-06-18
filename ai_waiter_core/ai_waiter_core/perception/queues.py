"""Typed queue plumbing for the voice perception pipeline.

VAD and STT are threading.Thread subclasses that use blocking I/O
(mic read, model inference), not async coroutines. The queues here
use threading primitives — asyncio primitives would force wrapping
every blocking call in run_in_executor. Compute device (CPU/GPU)
is orthogonal to this choice.
"""
import logging
import queue
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

SPEECH_QUEUE_MAX = 10
TEXT_QUEUE_MAX = 10

_speech_drops: int = 0
_text_drops: int = 0


@dataclass(frozen=True, slots=True)
class AudioChunk:
    samples: bytes
    timestamp: float
    sample_rate: int = 16000
    duration_s: float = 0.0


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    timestamp: float
    audio_duration_s: Optional[float] = None


speech_queue: queue.Queue[AudioChunk] = queue.Queue(maxsize=SPEECH_QUEUE_MAX)
text_queue: queue.Queue[Transcript] = queue.Queue(maxsize=TEXT_QUEUE_MAX)


def put_speech(chunk: AudioChunk) -> None:
    global _speech_drops
    try:
        speech_queue.put_nowait(chunk)
    except queue.Full:
        _speech_drops += 1
        logger.warning(f"speech_queue full, dropped utterance ({_speech_drops} total)")


def put_transcript(t: Transcript) -> None:
    global _text_drops
    try:
        text_queue.put_nowait(t)
    except queue.Full:
        _text_drops += 1
        logger.warning(f"text_queue full, dropped transcript ({_text_drops} total)")


def get_transcript(timeout: float = 0.5) -> Optional[Transcript]:
    try:
        return text_queue.get(timeout=timeout)
    except queue.Empty:
        return None


def queue_stats() -> dict:
    return {
        "speech_qsize": speech_queue.qsize(),
        "text_qsize": text_queue.qsize(),
        "speech_drops": _speech_drops,
        "text_drops": _text_drops,
    }


def shutdown_all() -> None:
    while not speech_queue.empty():
        try:
            speech_queue.get_nowait()
        except queue.Empty:
            break
    while not text_queue.empty():
        try:
            text_queue.get_nowait()
        except queue.Empty:
            break
    logger.info("perception queues drained")
