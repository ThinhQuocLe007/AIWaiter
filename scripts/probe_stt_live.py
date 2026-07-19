#!/usr/bin/env python3
"""
probe_stt_live.py — real-time microphone -> VAD -> STT, prints Vietnamese text live.

Unlike probe_stt.py (which transcribes a single wav file), this opens the
microphone and runs the REAL perception threads — SileroVAD + PhoWhisperSTT, the
same ones used by the production pipeline in src/edge_voice/main.py — but WITHOUT
the agent / LLM / TTS. Use it to validate "speak -> see text" end to end.

Speak into the mic; each finished utterance prints as:

    [HEARD @ 12.3s | 1.8s audio]: cho tôi một ly cà phê sữa

Flow: VAD opens the mic, detects where each utterance starts/stops, hands the
audio to STT via speech_queue; STT transcribes and puts text on text_queue, which
this loop drains and prints.

IMPORTANT: the mic must be physically attached to the machine that RUNS this script.
SSH itself is fine — it forwards the printed text, not audio. So with a USB mic plugged
into the Jetson you can ssh in from a laptop, run this, speak at the Jetson, and watch
the transcript scroll by in the laptop's terminal. What does NOT work is speaking into
the *laptop's* mic while the script runs on the Jetson: it would capture the Jetson's
own (possibly empty) input, not yours.

If the Jetson has no mic of its own, record on the laptop and use probe_stt.py --audio.

Run:
    uv run python scripts/probe_stt_live.py     # Ctrl-C to stop

Tuning knobs (same as the VAD probe), e.g.:
    VAD_THRESHOLD=0.4 MIC_DEVICE_INDEX=4 uv run python scripts/probe_stt_live.py
"""
import logging
import os
import sys
import signal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from src.edge_voice.perception import SileroVAD, PhoWhisperSTT
from src.edge_voice.perception.queues import get_transcript, shutdown_all
from src.agent_brain.config import settings


def main():
    # Surface the perception layer's info logs -- which mic got picked, which rate it opened
    # at, and each "Utterance flushed" -- otherwise the root logger's WARNING default hides
    # them and a silent mic looks identical to a broken STT.
    #
    # stream=stdout on purpose: PortAudio/ALSA dump their device-scan noise straight to
    # stderr from C, so `python probe_stt_live.py 2>/dev/null` is the normal way to run this.
    # Logging to the default stderr would get swallowed by that same redirect.
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)s %(name)s: %(message)s")

    print(f"[cfg] DEVICE={settings.DEVICE}  (STT compute: "
          f"{'float16' if settings.DEVICE == 'cuda' else 'int8'})")

    vad = SileroVAD()
    stt = PhoWhisperSTT()

    def shutdown(sig, frame):
        print("\nStopping...")
        shutdown_all()
        vad.stop()
        stt.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Each thread loads its own model on start: VAD opens the mic + segments
    # speech; STT consumes utterances and emits transcripts.
    vad.start()
    stt.start()

    print("=" * 56)
    print(" Live STT ready — speak Vietnamese into the mic")
    print(" (first run is slower: models load on the first words)")
    print(" Ctrl-C to stop")
    print("=" * 56)

    while True:
        t = get_transcript(timeout=0.5)
        if t is None or not t.text.strip():
            continue
        dur = f" | {t.audio_duration_s:.1f}s audio" if t.audio_duration_s else ""
        print(f"[HEARD @ {t.timestamp:.1f}s{dur}]: {t.text}")


if __name__ == "__main__":
    main()
