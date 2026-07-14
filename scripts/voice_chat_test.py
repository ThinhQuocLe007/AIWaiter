"""One-shot voice chat test — mic → STT → agent → TTS, no tablet needed.

Usage:
    uv run python scripts/voice_chat_test.py

Press Enter, speak a sentence, wait for the agent's spoken reply.
Press Enter again for another turn. Ctrl+C to quit.
"""

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from src.agent_brain.config import settings
from src.edge_voice.perception import SileroVAD, PhoWhisperSTT
from src.edge_voice.perception.queues import get_transcript, shutdown_all
from src.edge_voice.output.tts_engine import (
    StreamingPlayer,
    speak_sentence,
    warmup as tts_warmup,
)


def main():
    print("=" * 50)
    print(" AI Waiter — Voice Chat Test (direct)")
    print(f" Agent: {settings.AGENT_URL}")
    print(" Press Enter to speak, Ctrl+C to quit.")
    print("=" * 50)

    vad = SileroVAD()
    stt = PhoWhisperSTT()
    vad.start()
    stt.start()
    stt.warmup()
    print("[STT] PhoWhisper warmed up.")

    player = StreamingPlayer(vad=vad)
    tts_warmup()
    print("[TTS] Engine warmed up.")

    client = httpx.Client(base_url=settings.AGENT_URL, timeout=httpx.Timeout(60.0))
    table_id = "T1"

    try:
        while True:
            input("\n>>> Press Enter to start listening (or Ctrl+C to quit) >>>")

            # Drop stale transcripts
            while get_transcript(timeout=0.0) is not None:
                pass

            vad.begin_listen()
            print("[LISTENING] 🎤 Mời anh/chị nói...", end="", flush=True)
            if not vad.wait_for_utterance(15.0):
                print("\n[TIMEOUT] Không nghe thấy gì.")
                continue

            transcript = get_transcript(timeout=12.0)
            if transcript is None or not transcript.text.strip():
                print("\n[EMPTY] Không nhận ra lời nói.")
                continue

            print(f"\n[HEARD] {transcript.text}")

            player.reset()
            try:
                with client.stream(
                    "POST", "/chat/stream",
                    json={"table_id": table_id, "text": transcript.text}
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = json.loads(line[6:])
                        ev = data.get("event")

                        if ev == "progress":
                            print(f"[AGENT] đang xử lý...")
                        elif ev == "sentence":
                            sentence = data["text"]
                            print(f"[WAITER] {sentence}")
                            if sentence and not player.is_stopped():
                                speak_sentence(sentence, player)
                        elif ev == "done":
                            print(f"[DONE] stage={data.get('stage')}")
                            break
            except httpx.HTTPError as e:
                print(f"[ERROR] Agent unreachable: {e}")
    except KeyboardInterrupt:
        print("\n[EXIT]")
    finally:
        player.interrupt()
        shutdown_all()
        vad.stop()
        stt.stop()
        client.close()


if __name__ == "__main__":
    main()
