"""Text-only agent chat test — type → agent → streaming TTS, no mic/STT needed.

Usage:
    uv run python scripts/text_chat_test.py

Type a sentence, press Enter. The agent streams sentences via SSE,
each played through Piper TTS as soon as it arrives.
Type 'quit' to exit, 'reset' to clear session.
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from src.agent_brain.config import settings
from src.edge_voice.output.tts_engine import (
    StreamingPlayer,
    speak_sentence,
    warmup as tts_warmup,
)


def main():
    print("=" * 50)
    print(" AI Waiter — Text Chat Test (bypass mic/STT)")
    print(f" Agent: {settings.AGENT_URL}")
    print(" Type a sentence + Enter. 'quit' to exit, 'reset' to clear.")
    print("=" * 50)

    player = StreamingPlayer()
    tts_warmup()
    print("[TTS] Piper engine ready.\n")

    client = httpx.Client(base_url=settings.AGENT_URL, timeout=httpx.Timeout(60.0))
    table_id = "T1"

    try:
        while True:
            text = input(">> ").strip()
            if not text:
                continue
            if text.lower() == "quit":
                break
            if text.lower() == "reset":
                table_id = "T1"
                print("[RESET] New session.\n")
                continue

            player.reset()
            t0_total = time.time()
            first_sentence = True

            try:
                with client.stream(
                    "POST", "/chat/stream",
                    json={"table_id": table_id, "text": text}
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = json.loads(line[6:])
                        ev = data.get("event")

                        if ev == "progress":
                            pass
                        elif ev == "sentence":
                            sentence = data["text"]
                            dt = time.time() - t0_total
                            if first_sentence:
                                print(f"\n[{dt:.1f}s] {sentence}")
                                first_sentence = False
                            else:
                                print(f"[{dt:.1f}s] {sentence}")
                            if not player.is_stopped():
                                speak_sentence(sentence, player)
                        elif ev == "done":
                            dt = time.time() - t0_total
                            print(f"[{dt:.1f}s] done (stage={data.get('stage')})\n")
                            break
            except httpx.HTTPError as e:
                print(f"[ERROR] Agent: {e}\n")
    except KeyboardInterrupt:
        print("\n[EXIT]")
    finally:
        player.interrupt()
        client.close()


if __name__ == "__main__":
    main()
