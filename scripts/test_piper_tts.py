"""Quick test of Piper TTS with Vietnamese voice — standalone, no project deps needed.

Installs piper-tts, downloads the vi_VN voice model, synthesizes a test sentence,
and plays it through the default speakers.

Usage:
    uv run python scripts/test_piper_tts.py

On first run this downloads ~52 MB (ONNX model + config) to storage/tts/.
Subsequent runs use the cached files.
"""

import os
import sys
import time
import wave
import io
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "storage" / "tts"
VOICE = "vi_VN-vais1000-medium"
MODEL_URL_BASE = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    "/vi/vi_VN/vais1000/medium"
)


def download_model():
    onnx_path = MODEL_DIR / f"{VOICE}.onnx"
    json_path = MODEL_DIR / f"{VOICE}.onnx.json"

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for path, filename in [(onnx_path, f"{VOICE}.onnx"), (json_path, f"{VOICE}.onnx.json")]:
        if path.exists():
            print(f"  [cached] {path}")
            continue
        url = f"{MODEL_URL_BASE}/{filename}"
        print(f"  downloading {filename} ...")
        subprocess.run(
            ["curl", "-fSL", "-o", str(path), url],
            check=True,
            capture_output=False,
        )

    return onnx_path, json_path


def test_piper_python():
    """Test using the piper-tts Python package."""
    try:
        from piper_tts import PiperVoice
        import numpy as np
        import sounddevice as sd
    except ImportError:
        print("[SKIP] piper-tts not installed. Install with: uv add piper-tts")
        return False

    print("\n--- Piper Python API ---")
    print(f"Downloading/caching model to {MODEL_DIR} ...")
    onnx_path, json_path = download_model()

    print(f"Loading {VOICE} ...")
    t0 = time.time()
    voice = PiperVoice.load(str(onnx_path), config_path=str(json_path))
    print(f"  loaded in {time.time() - t0:.2f}s")

    sample_rate = voice.config.sample_rate
    print(f"  sample rate: {sample_rate} Hz")

    texts = [
        "Xin chào, tôi là người máy phục vụ bàn.",
        "Dạ, em chào anh chị ạ. Em có thể giúp gì cho anh chị ạ?",
        "Dạ, món ốc hương có giá một trăm năm mươi nghìn một phần ạ.",
    ]

    for i, text in enumerate(texts):
        print(f"\n[{i+1}/{len(texts)}] Synthesizing: '{text}'")
        t0 = time.time()

        chunks = []
        for chunk in voice.synthesize_stream_raw(text):
            chunks.append(chunk)
        pcm = b"".join(chunks)
        samples = np.frombuffer(pcm, dtype=np.int16)

        duration = len(samples) / sample_rate
        rtf = (time.time() - t0) / duration if duration > 0 else 0
        print(f"  {len(samples)} samples, {duration:.2f}s audio, RTF={rtf:.1f}x")

        if i == 0:
            print(f"  Playing through speakers ...")
            sd.play(samples, samplerate=sample_rate)
            sd.wait()

    print("\nPiper Python API works!")
    return True


def test_piper_binary():
    """Test using the piper command-line binary (fallback for platforms without pip wheel)."""
    import shutil

    piper_bin = shutil.which("piper")
    if piper_bin:
        print(f"\n--- Piper binary: {piper_bin} ---")
    else:
        piper_bin = shutil.which(f"./piper/piper")
        if not piper_bin:
            piper_local = MODEL_DIR / "piper" / "piper"
            if piper_local.exists():
                piper_bin = str(piper_local)

    if not piper_bin:
        print("[SKIP] piper binary not found in PATH or storage/tts/piper/")
        print("  Download from: https://github.com/rhasspy/piper/releases")
        return False

    print(f"\n--- Piper binary: {piper_bin} ---")
    onnx_path, json_path = download_model()

    text = "Xin chào, tôi là người máy phục vụ bàn."
    out_wav = MODEL_DIR / "test_output.wav"

    t0 = time.time()
    proc = subprocess.run(
        [piper_bin, "--model", str(onnx_path), "--output_file", str(out_wav)],
        input=text.encode("utf-8"),
        capture_output=True,
    )
    elapsed = time.time() - t0

    if proc.returncode != 0:
        print(f"  FAILED (exit {proc.returncode})")
        print(f"  stderr: {proc.stderr.decode()}")
        return False

    size = out_wav.stat().st_size
    print(f"  Output: {size} bytes in {elapsed:.2f}s -> {out_wav}")
    print(f"  Play with: aplay {out_wav}  # or: ffplay {out_wav}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print(" Piper TTS — Vietnamese Voice Test")
    print("=" * 60)

    ok_python = test_piper_python()

    if not ok_python:
        print("\nPython API failed — trying binary fallback...")
        ok_binary = test_piper_binary()
        if not ok_binary:
            print("\n❌ Piper TTS is NOT available on this machine.")
            print("   For x86:   uv add piper-tts")
            print("   For Jetson: build piper from source or use edge-tts fallback.")
            sys.exit(1)

    print("\n✅ Piper TTS is ready. You can now integrate it into tts_engine.py.")
