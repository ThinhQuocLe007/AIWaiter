import signal
import sys
import asyncio
import time

import httpx
from dotenv import load_dotenv

from ai_waiter_core.config import settings
from ai_waiter_core.perception import SileroVAD, PhoWhisperSTT
from ai_waiter_core.perception.queues import get_transcript, queue_stats, shutdown_all
from ai_waiter_core.output import StreamingPlayer, speak_streaming, warmup
from ai_waiter_core.utils import flush_traces, log_struct

load_dotenv()

TABLE_ID = "T1"
STATS_LOG_INTERVAL = 30.0
# TTS chưa code xong — tạm tắt để test STT + agent. Bật lại = True khi làm xong bộ TTS.
ENABLE_TTS = False
# The LLM runs on the server, not the Jetson: this loop only does mic→VAD→Whisper and TTS, then
# POSTs the recognised text to the agent service (ai_waiter_core/server.py) for processing. Local
# model latency can be a few seconds, so give the call generous headroom.
CHAT_TIMEOUT = httpx.Timeout(60.0, connect=5.0)


def main():
    log_struct("Starting AI Waiter Voice Pipeline")
    # The agent (LLM) lives on the server; we reach it over HTTP. One Client kept open for the
    # whole loop reuses the connection pool. Tools/orchestration happen server-side.
    agent_client = httpx.Client(base_url=settings.AGENT_URL, timeout=CHAT_TIMEOUT)

    vad = SileroVAD()
    stt = PhoWhisperSTT()
    player = StreamingPlayer(vad=vad)

    def shutdown(sig, frame):
        print("\nShutting down...")
        shutdown_all()
        vad.stop()
        stt.stop()
        agent_client.close()
        flush_traces()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    vad.start()
    stt.start()

    if ENABLE_TTS:
        asyncio.run(warmup())

    print("=" * 50)
    print(f" AI Waiter ready — Table {TABLE_ID}")
    print(f" Agent (LLM) @ {settings.AGENT_URL}")
    print(" Speak in Vietnamese to order...")
    print(" Press Ctrl+C to stop")
    print("=" * 50)

    last_stats_log = time.time()
    while True:
        try:
            transcript = get_transcript(timeout=0.5)
            if transcript is None:
                if time.time() - last_stats_log >= STATS_LOG_INTERVAL:
                    log_struct("queue_stats", **queue_stats())
                    last_stats_log = time.time()
                continue

            text = transcript.text
            timestamp = transcript.timestamp
            print(f"\n[HEARD @ {timestamp:.1f}s]: {text}")

            if not text.strip():
                continue

            # Send the recognised text to the server-side agent. No sticky session_id: the agent
            # re-resolves the table's current backend session each turn, so the thread resets
            # automatically after payment (see graph.chat / Phase 4). The server also mirrors this
            # turn to the table's tablet (customer_ui) over the voice bridge.
            try:
                resp = agent_client.post("/chat", json={"table_id": TABLE_ID, "text": text})
                resp.raise_for_status()
                result = resp.json()
            except httpx.HTTPError as e:
                print(f"Agent request failed: {e}")
                continue

            stage = result.get("final_stage", "IDLE")
            response = result["response"]
            print(f"[WAITER]: {response}")

            if ENABLE_TTS:
                asyncio.run(speak_streaming(response, stage, player))
                player.reset()

        except KeyboardInterrupt:
            shutdown(None, None)
        except Exception as e:
            print(f"Error: {e}")
            player.reset()


if __name__ == "__main__":
    main()
