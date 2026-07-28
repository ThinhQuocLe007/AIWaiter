#!/usr/bin/env python3
"""Cascade evaluation: what the recogniser costs the components downstream (thesis §5.4.5).

Every other AI experiment in Chapter 5 feeds the agent clean typed text. This one runs the
real audio path -- Silero VAD, then faster-whisper -- and then feeds the resulting transcript
to the same intent classifier the clean-text experiments use. The headline number is not the
word error rate but the *difference* it causes:

    cascade accuracy delta = accuracy(reference text) - accuracy(recognised text)

A system that routes at 88% on typed text and 70% on its own microphone is a system whose
reported accuracy describes a condition it never operates in. This script is what makes that
claim checkable either way.

This runs on the Jetson or on any machine with enough VRAM for Whisper-medium; it does not
need the LLM, the orchestrator, or the robot. It is designed to be run by someone other than
its author: it validates its inputs up front, fails loudly with an actionable message, and
writes a single self-contained JSON that the thesis tables are built from without re-running.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_cascade.py --audio-dir recordings/
    PYTHONPATH=. uv run python evals/scripts/eval_cascade.py --audio-dir recordings/ \\
        --noise assets/noise/restaurant.wav
    PYTHONPATH=. uv run python evals/scripts/eval_cascade.py --audio-dir recordings/ --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

MANIFEST = PROJECT_ROOT / "evals" / "data" / "cascade" / "manifest.json"
MENU = PROJECT_ROOT / "assets" / "data" / "menu.json"
RESULTS = PROJECT_ROOT / "evals" / "results"
SAVED = PROJECT_ROOT / "src" / "training_semantic_router" / "classifier" / "saved"


# --------------------------------------------------------------------------------------
# Text scoring
# --------------------------------------------------------------------------------------


def normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Diacritics are preserved.

    Vietnamese tone marks are meaning-bearing -- 'ốc' and 'óc' are different words -- so
    stripping them before scoring would hide exactly the class of error a generic multilingual
    recogniser is most likely to make on this menu.
    """
    text = unicodedata.normalize("NFC", text.lower())
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def edit_distance(a: list[str], b: list[str]) -> int:
    """Levenshtein distance over token lists (or characters, if given characters)."""
    if not a:
        return len(b)
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def wer(reference: str, hypothesis: str) -> tuple[int, int]:
    ref = normalise(reference).split()
    return edit_distance(ref, normalise(hypothesis).split()), len(ref)


def cer(reference: str, hypothesis: str) -> tuple[int, int]:
    ref = list(normalise(reference).replace(" ", ""))
    return edit_distance(ref, list(normalise(hypothesis).replace(" ", ""))), len(ref)


def dish_token_errors(reference: str, hypothesis: str, dishes: set[str]) -> tuple[int, int]:
    """Reference dish tokens missing from the hypothesis, and how many there were.

    Reported separately from overall WER because the two have different consequences: a
    mangled function word costs nothing downstream, whereas a mangled dish token is what the
    validator's name-resolution cascade fails on.
    """
    ref = [t for t in normalise(reference).split() if t in dishes]
    hyp = set(normalise(hypothesis).split())
    return sum(1 for t in ref if t not in hyp), len(ref)


# --------------------------------------------------------------------------------------
# Audio
# --------------------------------------------------------------------------------------


def mix_at_snr(speech, noise, snr_db: float):
    """Mix noise into speech at a target SNR, tiling or trimming the noise to length.

    Power is computed over the whole utterance rather than over detected speech regions; the
    resulting SNR is therefore a nominal level for reproducibility, not a perceptual claim.
    """
    import numpy as np

    if len(noise) < len(speech):
        noise = np.tile(noise, int(np.ceil(len(speech) / len(noise))))
    noise = noise[: len(speech)]

    speech_power = float(np.mean(speech.astype(np.float64) ** 2)) or 1e-12
    noise_power = float(np.mean(noise.astype(np.float64) ** 2)) or 1e-12
    scale = np.sqrt(speech_power / (noise_power * (10 ** (snr_db / 10))))
    mixed = speech + scale * noise
    peak = float(np.max(np.abs(mixed)))
    return (mixed / peak * 0.99 if peak > 1.0 else mixed).astype(np.float32)


def load_wav(path: Path, target_sr: int = 16000):
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != target_sr:
        ratio = target_sr / sr
        idx = np.arange(int(len(audio) * ratio)) / ratio
        audio = np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)
    return audio


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------


def preflight(manifest: dict, audio_dir: Path, noise: Path | None) -> list[str]:
    """Check every input before loading a model, so a missing file fails in a second.

    The alternative -- discovering a typo in the audio path after Whisper has warmed up on the
    Jetson -- wastes minutes per attempt for whoever is running this, who may not be the
    person who wrote it.
    """
    problems: list[str] = []
    if not audio_dir.is_dir():
        return [f"audio directory not found: {audio_dir}"]

    missing = [f for item in manifest["items"] for f in item["files"]
               if not (audio_dir / f).is_file()]
    if missing:
        problems.append(
            f"{len(missing)} of {manifest['total_recordings']} recordings missing, e.g. "
            f"{', '.join(missing[:4])}"
        )
    if noise is not None and not noise.is_file():
        problems.append(f"noise file not found: {noise}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio-dir", required=True, type=Path, help="directory holding the recorded WAVs")
    ap.add_argument("--noise", type=Path, help="restaurant-noise WAV; without it only 'clean' is scored")
    ap.add_argument("--snr", nargs="+", type=float, default=[20, 10, 0], help="SNR levels in dB")
    ap.add_argument("--model", default="medium", help="faster-whisper model size (default: medium)")
    ap.add_argument("--device", default="cuda", choices=("cuda", "cpu"))
    ap.add_argument("--check", action="store_true", help="validate inputs and exit without loading models")
    ap.add_argument("--json", type=Path, help="output path (default: timestamped in evals/results)")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = preflight(manifest, args.audio_dir, args.noise)
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        print(
            "\nRecord the manifest first. Each item needs one clean WAV per speaker, 16 kHz "
            "mono, named exactly as in manifest.json ('files'). See evals/HANDOFF.md.",
            file=sys.stderr,
        )
        return 1

    conditions = ["clean"] + ([f"{int(s)}db" for s in args.snr] if args.noise else [])
    print(f"  manifest: {manifest['total_utterances']} utterances x {manifest['speakers']} speakers")
    print(f"  conditions: {', '.join(conditions)}")
    print(f"  eval items: {manifest['total_recordings'] * len(conditions)}")
    if args.check:
        print("  inputs OK (--check: no models loaded, nothing written)")
        return 0

    import numpy as np
    from faster_whisper import WhisperModel

    from src.training_semantic_router.classifier.predict import classify

    dishes = {t for i in json.loads(MENU.read_text(encoding="utf-8"))
              for t in re.findall(r"\w+", i["name"].lower())}
    noise_audio = load_wav(args.noise) if args.noise else None

    print(f"  loading faster-whisper '{args.model}' on {args.device} ...")
    stt = WhisperModel(args.model, device=args.device,
                       compute_type="float16" if args.device == "cuda" else "int8")

    rows: list[dict[str, Any]] = []
    for item in manifest["items"]:
        # Multi-intent references have no single gold label, so they contribute to WER but are
        # excluded from the routing delta rather than scored against an arbitrary first intent.
        single_intent = "+" not in item["intent"]
        for fname in item["files"]:
            clean = load_wav(args.audio_dir / fname)
            for cond in conditions:
                audio = clean if cond == "clean" else mix_at_snr(
                    clean, noise_audio, float(cond.replace("db", "")))
                segments, _ = stt.transcribe(audio, language="vi", beam_size=5)
                hypothesis = " ".join(s.text for s in segments).strip()

                w_err, w_n = wer(item["text"], hypothesis)
                c_err, c_n = cer(item["text"], hypothesis)
                d_err, d_n = dish_token_errors(item["text"], hypothesis, dishes)

                row = {
                    "id": item["id"], "file": fname, "condition": cond,
                    "reference": item["text"], "hypothesis": hypothesis,
                    "wer_errors": w_err, "wer_tokens": w_n,
                    "cer_errors": c_err, "cer_chars": c_n,
                    "dish_errors": d_err, "dish_tokens": d_n,
                    "intent_gold": item["intent"], "single_intent": single_intent,
                }
                if single_intent:
                    state = {"order_stage": item["order_stage"]} if item["order_stage"] else None
                    ref_pred = classify(item["text"], state=state, model_path=SAVED / "model.pt",
                                        label_path=SAVED / "label_encoder.json",
                                        scaler_path=SAVED / "scaler.npz")["intent"]
                    asr_pred = classify(hypothesis, state=state, model_path=SAVED / "model.pt",
                                        label_path=SAVED / "label_encoder.json",
                                        scaler_path=SAVED / "scaler.npz")["intent"]
                    row |= {
                        "intent_from_reference": ref_pred,
                        "intent_from_asr": asr_pred,
                        "reference_correct": ref_pred == item["intent"],
                        "asr_correct": asr_pred == item["intent"],
                    }
                rows.append(row)
        print(f"  {item['id']} done", end="\r", flush=True)

    # ---- aggregate per condition ----------------------------------------------------
    print("\n")
    summary = {}
    table = []
    for cond in conditions:
        sub = [r for r in rows if r["condition"] == cond]
        routed = [r for r in sub if r["single_intent"]]
        w = sum(r["wer_errors"] for r in sub) / max(1, sum(r["wer_tokens"] for r in sub))
        c = sum(r["cer_errors"] for r in sub) / max(1, sum(r["cer_chars"] for r in sub))
        d_tot = sum(r["dish_tokens"] for r in sub)
        d = sum(r["dish_errors"] for r in sub) / d_tot if d_tot else 0.0
        ref_acc = sum(r["reference_correct"] for r in routed) / max(1, len(routed))
        asr_acc = sum(r["asr_correct"] for r in routed) / max(1, len(routed))
        summary[cond] = {
            "n_recordings": len(sub), "n_routed": len(routed),
            "wer": round(w, 4), "cer": round(c, 4), "dish_substitution_rate": round(d, 4),
            "accuracy_reference_text": round(ref_acc, 4),
            "accuracy_asr_text": round(asr_acc, 4),
            "cascade_delta": round(ref_acc - asr_acc, 4),
        }
        table.append([cond, len(sub), f"{w:.1%}", f"{c:.1%}", f"{d:.1%}",
                      f"{ref_acc:.1%}", f"{asr_acc:.1%}", f"{ref_acc - asr_acc:+.1%}"])

    from evals.lib.stats import markdown_table

    print(markdown_table(
        ["Condition", "n", "WER", "CER", "Dish sub.", "Acc (ref)", "Acc (ASR)", "Delta"], table))
    print(
        "\n  'Delta' is the routing accuracy lost to recognition. It, not WER, is the number"
        "\n  §5.4.5 reports: WER describes the recogniser, delta describes the system."
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.json or RESULTS / f"cascade_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated": stamp, "stt_model": args.model, "device": args.device,
        "conditions": conditions, "speakers": manifest["speakers"],
        "summary": summary, "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
