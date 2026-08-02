#!/usr/bin/env python3
"""Voice pipeline latency: what VAD, STT and TTS cost on the machine that runs them (thesis §5.4.7).

Every agent experiment in Chapter 5 starts from a transcript. This one measures the three
components that stand between a speaking customer and that transcript, and between the reply
text and the sound the customer hears:

    VAD  Silero, per 512-sample frame, CPU
    STT  faster-whisper (PhoWhisper medium), one whole utterance, GPU where available
    TTS  Piper, one agent reply, CPU

No new dataset is created. STT and VAD run on the cascade recordings (evals/data/cascade/
recordings), so the latency figures and the recognition-accuracy figures of eval_cascade.py
describe the same audio. TTS runs on the agent replies recorded by the end-to-end evaluation,
so the sentences measured are sentences the system has actually spoken.

THE DEVICE MATTERS AND IS RECORDED. An x86 laptop is not a Jetson Orin Nano: the discrete GPU
has several times the memory bandwidth and the CPU several times the clock. Numbers taken on a
development machine are a lower bound on what the robot does, not a substitute for it. The
`device` block written into the result JSON identifies which machine produced the file, and
`is_tegra` is the flag that separates a real edge measurement from a laptop one.

Usage:
    PYTHONPATH=. uv run python evals/scripts/bench_voice.py --check
    PYTHONPATH=. uv run python evals/scripts/bench_voice.py
    PYTHONPATH=. uv run python evals/scripts/bench_voice.py --components stt --repeats 5
    PYTHONPATH=. uv run python evals/scripts/bench_voice.py --device cpu --limit 10
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

RECORDINGS = PROJECT_ROOT / "evals" / "data" / "cascade" / "recordings"
MANIFEST = PROJECT_ROOT / "evals" / "data" / "cascade" / "manifest.json"
REPLIES = PROJECT_ROOT / "evals" / "results" / "e2e_qualitative_20260731_180507.json"
RESULTS = PROJECT_ROOT / "evals" / "results"

VAD_FRAME_SAMPLES = 512          # matches perception/vad_silero.py CHUNK_SIZE
VAD_SAMPLE_RATE = 16000
TTS_SAMPLE_RATE = 22050          # matches output/tts_engine.py SAMPLE_RATE


# --------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------


def summarise(samples: list[float]) -> dict[str, Any]:
    """p50/p95 plus the raw samples, so a reader can recompute any percentile."""
    if not samples:
        return {"n": 0}
    ordered = sorted(samples)
    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 4),
        "p50": round(statistics.median(ordered), 4),
        # nearest-rank p95: with n < 20 an interpolated percentile invents a value that was
        # never observed, and these runs are deliberately small.
        "p95": round(ordered[min(len(ordered) - 1, int(round(0.95 * len(ordered))) - 1)], 4),
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
        "samples": [round(s, 4) for s in ordered],
    }


# --------------------------------------------------------------------------------------
# Device identification
# --------------------------------------------------------------------------------------


def tegra_power_state() -> dict[str, Any]:
    """Power mode and clock state, without which a Jetson figure cannot be interpreted.

    An Orin Nano runs at 7 W, 15 W or 25 W, and the same model is several times slower at the
    bottom of that range than at the top. `nvpmodel -q` names the active mode; the CPU governor
    and the gap between current and maximum frequency say whether jetson_clocks has pinned the
    clocks or left them to scale. A latency figure reported without both is not reproducible.
    """
    state: dict[str, Any] = {}

    try:
        out = subprocess.run(["nvpmodel", "-q"], capture_output=True, text=True, timeout=15)
        if out.returncode == 0:
            lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
            state["nvpmodel_raw"] = lines
            for i, line in enumerate(lines):
                if line.lower().startswith("nv power mode"):
                    tail = line.split(":", 1)[1].strip() if ":" in line else ""
                    state["power_mode"] = tail or (lines[i + 1] if i + 1 < len(lines) else None)
                elif line.isdigit() and "power_mode_id" not in state:
                    state["power_mode_id"] = int(line)
    except (OSError, subprocess.SubprocessError):
        state["nvpmodel"] = "unavailable"

    cpufreq = Path("/sys/devices/system/cpu/cpu0/cpufreq")
    try:
        cur = int((cpufreq / "scaling_cur_freq").read_text().strip())
        mx = int((cpufreq / "cpuinfo_max_freq").read_text().strip())
        state["cpu_governor"] = (cpufreq / "scaling_governor").read_text().strip()
        state["cpu_freq_mhz"] = round(cur / 1000)
        state["cpu_max_freq_mhz"] = round(mx / 1000)
        state["cpu_clocks_pinned"] = cur >= mx * 0.98
    except (OSError, ValueError):
        pass

    for gpu_freq in Path("/sys/class/devfreq").glob("*/cur_freq"):
        try:
            state["gpu_freq_mhz"] = round(int(gpu_freq.read_text().strip()) / 1_000_000)
            state["gpu_devfreq"] = gpu_freq.parent.name
            break
        except (OSError, ValueError):
            continue

    return state


def describe_device() -> dict[str, Any]:
    info: dict[str, Any] = {
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "is_tegra": Path("/etc/nv_tegra_release").exists(),
        "cpu_model": None,
        "cpu_count": None,
        "ram_gb": None,
        "gpu_name": None,
    }

    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith(("model name", "Model")):
                info["cpu_model"] = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass

    try:
        import os

        info["cpu_count"] = os.cpu_count()
    except Exception:
        pass

    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                info["ram_gb"] = round(int(line.split()[1]) / 1024 / 1024, 1)
                break
    except OSError:
        pass

    try:
        import torch

        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(0)
    except Exception:
        pass

    if info["is_tegra"]:
        info["tegra"] = tegra_power_state()

    return info


# --------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------


def load_utterances(limit: int | None) -> list[dict[str, Any]]:
    """One recording per manifest utterance, decoded the way the STT runtime decodes it.

    faster_whisper.audio.decode_audio goes through PyAV, which probes the actual codec. The
    cascade WAVs carry an MP3 payload under a WAV header (see synthesize_cascade_voices.py), so
    a plain soundfile read returns noise of the wrong length. Everything here goes through
    decode_audio for that reason.
    """
    from faster_whisper.audio import decode_audio

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = manifest["items"][:limit] if limit else manifest["items"]

    out = []
    for item in items:
        path = RECORDINGS / item["files"][0]
        if not path.is_file():
            continue
        audio = decode_audio(str(path), sampling_rate=VAD_SAMPLE_RATE)
        out.append({
            "id": item["id"],
            "file": path.name,
            "text": item["text"],
            "audio": audio,
            "duration_s": round(len(audio) / VAD_SAMPLE_RATE, 3),
        })
    return out


def load_replies(limit: int | None) -> list[str]:
    """Distinct agent replies from the end-to-end run: the sentences the system really says."""
    blob = REPLIES.read_text(encoding="utf-8")
    raw = re.findall(r'"response"\s*:\s*"((?:[^"\\]|\\.)*)"', blob)
    seen, replies = set(), []
    for r in raw:
        text = json.loads(f'"{r}"').strip()
        if text and text not in seen:
            seen.add(text)
            replies.append(text)
    replies.sort(key=len)
    return replies[:limit] if limit else replies


# --------------------------------------------------------------------------------------
# Benchmarks
# --------------------------------------------------------------------------------------


def bench_stt(utterances: list[dict], device: str, repeats: int) -> dict[str, Any]:
    """Transcription cost per utterance, through the deployed call exactly.

    perception/stt_phowhisper.py hands the model a float32 array and reads the segments with
    beam_size=5 and vad_filter=True. Both are reproduced here: a smaller beam or no VAD filter
    would measure a configuration the robot does not run.
    """
    from faster_whisper import WhisperModel

    from src.edge_voice.perception.stt_phowhisper import MODEL_SIZE

    compute = "float16" if device == "cuda" else "int8"
    print(f"  loading faster-whisper {MODEL_SIZE} ({device}, {compute}) ...", flush=True)
    t0 = time.perf_counter()
    model = WhisperModel(MODEL_SIZE, device=device, compute_type=compute)
    load_s = time.perf_counter() - t0
    print(f"  loaded in {load_s:.1f}s", flush=True)

    def transcribe(audio) -> str:
        segments, _ = model.transcribe(
            audio, language="vi", beam_size=5, vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        # faster-whisper is lazy: the work happens while the generator is consumed, so the
        # timer must close after this line, not after the call above.
        return " ".join(seg.text.strip() for seg in segments if seg.text.strip())

    import numpy as np

    print("  warmup ...", flush=True)
    transcribe(np.zeros(VAD_SAMPLE_RATE // 2, dtype=np.float32))

    latencies, rtfs, rows = [], [], []
    for i, utt in enumerate(utterances, 1):
        per_item = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            text = transcribe(utt["audio"])
            per_item.append(time.perf_counter() - t0)
        latencies.extend(per_item)
        rtfs.extend(l / utt["duration_s"] for l in per_item)
        rows.append({
            "id": utt["id"],
            "file": utt["file"],
            "audio_s": utt["duration_s"],
            "p50_s": round(statistics.median(per_item), 4),
            "rtf_p50": round(statistics.median(per_item) / utt["duration_s"], 4),
            "hypothesis": text,
        })
        print(f"  [{i}/{len(utterances)}] {utt['id']} "
              f"{utt['duration_s']:.2f}s audio -> {statistics.median(per_item):.3f}s", flush=True)

    return {
        "model": MODEL_SIZE,
        "device": device,
        "compute_type": compute,
        "beam_size": 5,
        "vad_filter": True,
        "model_load_s": round(load_s, 2),
        "repeats": repeats,
        "n_utterances": len(utterances),
        "audio_duration_s": summarise([u["duration_s"] for u in utterances]),
        "latency_s": summarise(latencies),
        "real_time_factor": summarise(rtfs),
        "per_utterance": rows,
    }


def bench_tts(replies: list[str], repeats: int) -> dict[str, Any]:
    """Synthesis cost per reply, and per first sentence.

    The deployed player speaks sentence by sentence (output/tts_engine.py speak_streaming), so
    what a customer waits for is the first sentence, not the whole reply. Both are measured:
    first_sentence_s is the figure that belongs in the end-to-end budget.
    """
    from src.edge_voice.output.tts_engine import _synthesize_piper, split_vietnamese_sentences

    print("  warmup ...", flush=True)
    _synthesize_piper("Dạ em nghe anh chị.")

    full, first, rtfs, rows = [], [], [], []
    for i, reply in enumerate(replies, 1):
        sentences = split_vietnamese_sentences(reply)
        head = sentences[0] if sentences else reply

        per_full, per_first, audio_s = [], [], 0.0
        for _ in range(repeats):
            t0 = time.perf_counter()
            audio = _synthesize_piper(reply)
            per_full.append(time.perf_counter() - t0)
            audio_s = len(audio) / TTS_SAMPLE_RATE

            t0 = time.perf_counter()
            _synthesize_piper(head)
            per_first.append(time.perf_counter() - t0)

        full.extend(per_full)
        first.extend(per_first)
        rtfs.extend(l / audio_s for l in per_full if audio_s > 0)
        rows.append({
            "chars": len(reply),
            "sentences": len(sentences),
            "audio_s": round(audio_s, 3),
            "full_p50_s": round(statistics.median(per_full), 4),
            "first_sentence_p50_s": round(statistics.median(per_first), 4),
            "text": reply[:80],
        })
        print(f"  [{i}/{len(replies)}] {len(reply):>4} chars -> "
              f"full {statistics.median(per_full):.3f}s, "
              f"first sentence {statistics.median(per_first):.3f}s", flush=True)

    return {
        "engine": "piper",
        "voice": "vi_VN-vais1000-medium",
        "device": "cpu",
        "sample_rate": TTS_SAMPLE_RATE,
        "repeats": repeats,
        "n_replies": len(replies),
        "reply_chars": summarise([float(len(r)) for r in replies]),
        "full_reply_s": summarise(full),
        "first_sentence_s": summarise(first),
        "real_time_factor": summarise(rtfs),
        "per_reply": rows,
    }


def bench_vad(utterances: list[dict], max_frames: int) -> dict[str, Any]:
    """Per-frame detection cost, on the same audio the STT benchmark transcribes.

    The comparison that matters is against CHUNK_DURATION (512/16000 = 32 ms): a detector
    slower than the frame it consumes cannot keep up with a live microphone.
    """
    import numpy as np

    from src.edge_voice.perception.vad_silero import SileroVAD

    print("  loading silero ...", flush=True)
    t0 = time.perf_counter()
    vad = SileroVAD()
    vad._load_model()
    load_s = time.perf_counter() - t0
    print(f"  loaded in {load_s:.1f}s", flush=True)

    frames: list[bytes] = []
    for utt in utterances:
        pcm = (np.clip(utt["audio"], -1.0, 1.0) * 32767).astype(np.int16)
        for start in range(0, len(pcm) - VAD_FRAME_SAMPLES, VAD_FRAME_SAMPLES):
            frames.append(pcm[start:start + VAD_FRAME_SAMPLES].tobytes())
            if len(frames) >= max_frames:
                break
        if len(frames) >= max_frames:
            break

    for f in frames[:20]:                      # warmup
        vad.is_speech(f)

    latencies = []
    for f in frames:
        t0 = time.perf_counter()
        vad.is_speech(f)
        latencies.append(time.perf_counter() - t0)
    print(f"  {len(frames)} frames, p50 {statistics.median(latencies)*1000:.2f} ms", flush=True)

    frame_duration = VAD_FRAME_SAMPLES / VAD_SAMPLE_RATE
    return {
        "model": "silero_vad",
        "device": "cpu",
        "model_load_s": round(load_s, 2),
        "frame_samples": VAD_FRAME_SAMPLES,
        "frame_duration_s": round(frame_duration, 4),
        "silence_window_s": 1.5,               # SILENCE_TIMEOUT in perception/vad_silero.py
        "n_frames": len(frames),
        "per_frame_s": summarise(latencies),
        "real_time_factor": summarise([l / frame_duration for l in latencies]),
    }


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------


def preflight(components: set[str]) -> list[str]:
    """Check inputs before any model loads, so a missing file fails in a second."""
    problems = []
    if {"stt", "vad"} & components:
        if not RECORDINGS.is_dir():
            problems.append(f"recordings not found: {RECORDINGS}")
        elif not any(RECORDINGS.glob("*.wav")):
            problems.append(f"no WAV files in {RECORDINGS}")
        if not MANIFEST.is_file():
            problems.append(f"manifest not found: {MANIFEST}")
    if "tts" in components:
        if not REPLIES.is_file():
            problems.append(f"agent replies not found: {REPLIES}")
        onnx = PROJECT_ROOT / "storage" / "tts" / "vi_VN-vais1000-medium.onnx"
        if not onnx.is_file():
            problems.append(f"piper voice not downloaded: {onnx}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--components", default="vad,stt,tts",
                    help="comma-separated subset of vad,stt,tts (default: all)")
    ap.add_argument("--device", default="cuda", choices=("cuda", "cpu"),
                    help="device for STT; VAD and TTS are CPU-only by design")
    ap.add_argument("--repeats", type=int, default=3, help="runs per item (default: 3)")
    ap.add_argument("--limit", type=int, help="use only the first N utterances/replies")
    ap.add_argument("--vad-frames", type=int, default=2000, help="frames to time (default: 2000)")
    ap.add_argument("--check", action="store_true", help="validate inputs and exit")
    args = ap.parse_args()

    components = {c.strip().lower() for c in args.components.split(",") if c.strip()}
    unknown = components - {"vad", "stt", "tts"}
    if unknown:
        print(f"unknown component(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    problems = preflight(components)
    if problems:
        for p in problems:
            print(f"  ! {p}", file=sys.stderr)
        return 1
    if args.check:
        print("preflight OK")
        return 0

    device = describe_device()
    print("Device:")
    print(f"  {device['cpu_model']} x{device['cpu_count']}, {device['ram_gb']} GB RAM")
    print(f"  GPU: {device['gpu_name'] or 'none'}")
    print(f"  tegra: {device['is_tegra']}  arch: {device['machine']}")
    if device["is_tegra"]:
        t = device.get("tegra", {})
        print(f"  power mode: {t.get('power_mode', 'unknown')} (id {t.get('power_mode_id', '?')})")
        print(f"  cpu governor: {t.get('cpu_governor', '?')}, "
              f"{t.get('cpu_freq_mhz', '?')} / {t.get('cpu_max_freq_mhz', '?')} MHz, "
              f"pinned: {t.get('cpu_clocks_pinned', '?')}")
    else:
        print("  NOTE: not a Jetson. These figures are a lower bound on edge latency.")
    print()

    result: dict[str, Any] = {
        "generated": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "device": device,
        "inputs": {
            "stt_vad_audio": str(RECORDINGS.relative_to(PROJECT_ROOT)),
            "tts_replies": str(REPLIES.relative_to(PROJECT_ROOT)),
        },
    }

    utterances = []
    if {"stt", "vad"} & components:
        print("Loading audio ...")
        utterances = load_utterances(args.limit)
        print(f"  {len(utterances)} utterances, "
              f"{sum(u['duration_s'] for u in utterances):.1f}s total\n")

    if "vad" in components:
        print("VAD (silero, cpu):")
        result["vad"] = bench_vad(utterances, args.vad_frames)
        print()

    if "stt" in components:
        print(f"STT (faster-whisper, {args.device}):")
        result["stt"] = bench_stt(utterances, args.device, args.repeats)
        print()

    if "tts" in components:
        print("TTS (piper, cpu):")
        replies = load_replies(args.limit)
        print(f"  {len(replies)} distinct agent replies")
        result["tts"] = bench_tts(replies, args.repeats)
        print()

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"voice_latency_{result['generated']}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print(f"{'Component':<34}{'p50 (s)':>12}{'p95 (s)':>12}{'n':>8}")
    print("-" * 72)
    if "vad" in result:
        v = result["vad"]["per_frame_s"]
        print(f"{'VAD per 32 ms frame':<34}{v['p50']:>12.4f}{v['p95']:>12.4f}{v['n']:>8}")
    if "stt" in result:
        s = result["stt"]["latency_s"]
        print(f"{'STT per utterance':<34}{s['p50']:>12.4f}{s['p95']:>12.4f}{s['n']:>8}")
        r = result["stt"]["real_time_factor"]
        print(f"{'  real-time factor':<34}{r['p50']:>12.4f}{r['p95']:>12.4f}{r['n']:>8}")
    if "tts" in result:
        f = result["tts"]["first_sentence_s"]
        print(f"{'TTS first sentence':<34}{f['p50']:>12.4f}{f['p95']:>12.4f}{f['n']:>8}")
        w = result["tts"]["full_reply_s"]
        print(f"{'TTS full reply':<34}{w['p50']:>12.4f}{w['p95']:>12.4f}{w['n']:>8}")
    print("=" * 72)
    print(f"written: {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
