"""Probe STT (faster-whisper) RAM in isolation — no mic required.

Reuses the real PhoWhisperSTT._load_model + _transcribe (perception/stt_phowhisper.py)
so the measured RAM reflects the actual runtime.

Run:
    uv run python scripts/probe_stt.py                 # synthetic 5s audio
    uv run python scripts/probe_stt.py --audio a.wav   # real wav file (16k mono)

On Jetson: run `tegrastats` or `jtop` in another terminal to read unified RAM.
RSS below is process RAM (CPU side); model on GPU shows via the GPU mem line (if CUDA).
Note: faster-whisper uses ctranslate2, which manages CUDA memory outside torch,
so torch GPU alloc may read 0 even on cuda — trust tegrastats for the real figure.
"""
import argparse
import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import numpy as np


def rss_mb() -> float:
    """Process RAM (RSS) in MB, read from /proc/self/status — no psutil needed."""
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return -1.0


def gpu_mb() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / 1024 / 1024
    except Exception:
        pass
    return -1.0


def report(tag: str, base_rss: float):
    g = gpu_mb()
    gpu_str = f" | GPU alloc {g:8.1f} MB" if g >= 0 else ""
    print(f"[{tag:18}] RSS {rss_mb():8.1f} MB (Δ {rss_mb()-base_rss:+8.1f}){gpu_str}")


def load_audio_bytes(path: str | None, seconds: float) -> bytes:
    """Return int16 PCM mono 16kHz as bytes (matches the real AudioChunk.samples)."""
    sr = 16000
    if path:
        from scipy.io import wavfile
        file_sr, data = wavfile.read(path)
        if data.ndim > 1:
            data = data[:, 0]
        if data.dtype != np.int16:
            data = (data.astype(np.float32) / np.abs(data).max() * 32767).astype(np.int16)
        if file_sr != sr:
            print(f"[warn] file {file_sr}Hz != 16000Hz — STT expects 16k, result may be wrong")
        return data.tobytes()
    # Synthetic audio: light noise (transcribes to empty but still loads the full model)
    n = int(sr * seconds)
    noise = (np.random.randn(n) * 800).astype(np.int16)
    return noise.tobytes()


def prefetch_model(model_size: str):
    """Download the faster-whisper repo *with a visible progress bar* before loading.

    WhisperModel(...) downloads silently on first run, so on a slow link (e.g. Jetson)
    you can't tell whether it's stuck or how far along it is. snapshot_download shows a
    per-file tqdm bar; once cached this returns instantly and the bars don't reappear.
    """
    from faster_whisper.utils import _MODELS
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import enable_progress_bars

    enable_progress_bars()  # in case HF_HUB_DISABLE_PROGRESS_BARS is set somewhere
    repo_id = _MODELS.get(model_size, model_size)
    print(f"[download] fetching {repo_id} (shows progress; cached after first run)…", flush=True)
    t0 = time.time()
    path = snapshot_download(repo_id)
    print(f"[download] ready in {time.time()-t0:.1f}s -> {path}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", help="16kHz mono wav file (default: synthetic audio)")
    ap.add_argument("--seconds", type=float, default=5.0, help="synthetic audio length")
    args = ap.parse_args()

    base = rss_mb()
    report("startup", base)

    from src.edge_voice.perception.stt_phowhisper import PhoWhisperSTT, MODEL_SIZE
    from src.agent_brain.config import settings
    print(f"[cfg] DEVICE={settings.DEVICE}  -> compute={'float16' if settings.DEVICE=='cuda' else 'int8'}")

    # Prefetch the exact model PhoWhisperSTT will load (MODEL_SIZE in stt_phowhisper.py),
    # so the progress bar always matches the real model — change it in one place only.
    print(f"[cfg] MODEL_SIZE={MODEL_SIZE}")
    prefetch_model(MODEL_SIZE)

    stt = PhoWhisperSTT()
    t0 = time.time()
    stt._load_model()
    print(f"[time] load model: {time.time()-t0:.1f}s")
    report("after model load", base)

    audio = load_audio_bytes(args.audio, args.seconds)
    t0 = time.time()
    text = stt._transcribe(audio)
    print(f"[time] transcribe: {time.time()-t0:.1f}s")
    report("after transcribe", base)
    print(f"[stt out] {text!r}")


if __name__ == "__main__":
    main()
