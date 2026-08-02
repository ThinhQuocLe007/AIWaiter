#!/usr/bin/env python3
"""Synthesize cascade evaluation audio using edge-tts voices. Pure network I/O, no GPU.

Usage:
    PYTHONPATH=. uv run python scripts/synthesize_cascade_voices.py
    PYTHONPATH=. uv run python scripts/synthesize_cascade_voices.py --outdir /tmp/recordings --parallel 8

Output: 120 WAV files (60 utterances x 2 voices), 16kHz mono.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
from pathlib import Path

import edge_tts
import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

MANIFEST = PROJECT_ROOT / "evals" / "data" / "cascade" / "manifest.json"

VOICES = {
    2: "vi-VN-HoaiMyNeural",
    3: "vi-VN-NamMinhNeural",
}


async def synthesize_one(text: str, out: Path, voice: str) -> None:
    for attempt in range(1, 4):
        try:
            communicate = edge_tts.Communicate(text, voice, rate="+0%")
            pcm = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    pcm.write(chunk["data"])
            audio = np.frombuffer(pcm.getvalue(), dtype=np.int16).astype(np.float32) / 32768.0
            sf.write(str(out), audio, 16000, subtype="PCM_16")
            return
        except Exception:
            if attempt < 3:
                await asyncio.sleep(attempt)
            else:
                raise


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", type=Path, help="output directory")
    ap.add_argument("--parallel", type=int, default=8, help="concurrent network requests")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    outdir = args.outdir or (PROJECT_ROOT / "evals" / "data" / "cascade" / "recordings")
    outdir.mkdir(parents=True, exist_ok=True)

    tasks = []
    for item in manifest["items"]:
        for spk, voice in VOICES.items():
            fname = item["files"][spk - 1]
            out = outdir / fname
            if out.exists():
                continue
            tasks.append((fname, synthesize_one(item["text"], out, voice)))

    total = len(tasks)
    if total == 0:
        print(f"All {len(manifest['items']) * len(VOICES)} files already exist in {outdir}")
        return 0

    print(f"Synthesizing {total} files with {args.parallel} parallel workers...")
    sem = asyncio.Semaphore(args.parallel)
    done = 0
    failed = []

    async def worker(fname: str, coro):
        nonlocal done
        async with sem:
            try:
                await coro
            except Exception as e:
                failed.append((fname, str(e)))
            done += 1
            if done % 10 == 0 or done == total:
                print(f"  [{done}/{total}]", flush=True)

    await asyncio.gather(*(worker(f, c) for f, c in tasks))

    print(f"\n{total - len(failed)}/{total} succeeded in {outdir}")
    if failed:
        print(f"{len(failed)} failures:")
        for name, err in failed:
            print(f"  {name}: {err}")
    return len(failed)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
