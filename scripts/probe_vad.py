"""Probe VAD (silero) RAM in isolation — no mic required.

Reuses the real SileroVAD._load_model + is_speech (perception/vad_silero.py).
The silero model runs on CPU (see vad_silero.py). First run downloads it via torch.hub
(needs internet).

Run:
    uv run python scripts/probe_vad.py            # 200 synthetic chunks
    uv run python scripts/probe_vad.py --mic      # live mic (requires pyaudio)

On Jetson: run `tegrastats`/`jtop` in another terminal to read unified RAM.
"""
import argparse
import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "ai_waiter_core")
if os.path.isdir(SRC_DIR):
    sys.path.insert(0, SRC_DIR)

from dotenv import load_dotenv
load_dotenv()

import numpy as np


def rss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return -1.0


def report(tag: str, base: float):
    print(f"[{tag:18}] RSS {rss_mb():8.1f} MB (Δ {rss_mb()-base:+8.1f})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=200, help="number of 512-sample chunks to run (~6.4s)")
    ap.add_argument("--mic", action="store_true", help="test live mic (requires pyaudio)")
    args = ap.parse_args()

    base = rss_mb()
    report("startup", base)

    from ai_waiter_core.perception.vad_silero import SileroVAD, CHUNK_SIZE

    vad = SileroVAD()
    t0 = time.time()
    vad._load_model()
    print(f"[time] load model: {time.time()-t0:.1f}s")
    report("after model load", base)

    if args.mic:
        # live test: open mic, print is_speech prob until Ctrl-C
        vad._open_mic()
        report("after open mic", base)
        print("[mic] listening... speak, Ctrl-C to stop")
        try:
            while True:
                chunk = vad.read_chunk()
                print(f"  speech={vad.is_speech(chunk)}", end="\r")
        except KeyboardInterrupt:
            print("\n[mic] stopped")
        return

    # synthetic audio: first half strong noise (speech-like), second half near silence
    n_iter = args.chunks
    t0 = time.time()
    for i in range(n_iter):
        if i < n_iter // 2:
            chunk = (np.random.randn(CHUNK_SIZE) * 8000).astype(np.int16).tobytes()
        else:
            chunk = (np.random.randn(CHUNK_SIZE) * 50).astype(np.int16).tobytes()
        vad.is_speech(chunk)
    dt = time.time() - t0
    print(f"[time] {n_iter} chunks inference: {dt:.2f}s ({dt/n_iter*1000:.2f} ms/chunk)")
    report("after inference", base)


if __name__ == "__main__":
    main()
