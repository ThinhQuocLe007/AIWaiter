import signal
import sys
import asyncio
import time

from dotenv import load_dotenv

from ai_waiter_core.agent.graph import AIWaiterGraph
from ai_waiter_core.perception import SileroVAD, PhoWhisperSTT
from ai_waiter_core.perception.queues import get_transcript, queue_stats, shutdown_all
from ai_waiter_core.output import StreamingPlayer, speak_streaming, warmup
from ai_waiter_core.utils import flush_traces, log_struct

load_dotenv()

TABLE_ID = "T1"
STATS_LOG_INTERVAL = 30.0


def main():
    log_struct("Starting AI Waiter Voice Pipeline")
    agent = AIWaiterGraph()
    session_id = None

    vad = SileroVAD()
    stt = PhoWhisperSTT()
    player = StreamingPlayer(vad=vad)

    def shutdown(sig, frame):
        print("\nShutting down...")
        shutdown_all()
        vad.stop()
        stt.stop()
        flush_traces()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    vad.start()
    stt.start()

    asyncio.run(warmup())

    print("=" * 50)
    print(f" AI Waiter ready — Table {TABLE_ID}")
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

            result = agent.chat(
                query=text,
                table_id=TABLE_ID,
                session_id=session_id,
            )

            if session_id is None:
                session_id = result["session_id"]

            stage = result.get("final_stage", "IDLE")
            response = result["response"]
            print(f"[WAITER]: {response}")

            asyncio.run(speak_streaming(response, stage, player))
            player.reset()

        except KeyboardInterrupt:
            shutdown(None, None)
        except Exception as e:
            print(f"Error: {e}")
            player.reset()


if __name__ == "__main__":
    main()
