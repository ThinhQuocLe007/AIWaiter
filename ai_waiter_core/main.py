"""AI Waiter — voice device (runs on the machine with the microphone: Jetson/laptop).

This is NOT an always-on loop anymore. It is a *command-driven* service: it preloads + warms the
mic/VAD/STT models, connects to the backend WS hub as ``role=voice-device&robot_id=<id>``, then idles
until a tablet pushes the "talk to AI" button. The device is **table-agnostic** — the dispatcher
binds it to a table when this robot arrives there, and each ``start_listening`` command carries the
``table_id`` the guest belongs to. On the command it captures ONE utterance (mic → VAD → Whisper) and
POSTs the text to the agent (``POST /chat`` tagged with that table). The agent runs the LLM and
mirrors the turn back to the tablet via the voice bridge, so the web UI shows the conversation — the
browser never touches the microphone (so no HTTPS requirement).

Why a resident service instead of the web spawning it: a browser page can't launch a process on the
device (sandbox), and the mic needs a secure context. Running here as a service that the web *signals*
gives the production feel ("open web → press talk → speak") without either limitation.

Run on the device (point AGENT_URL / ORCHESTRATOR_URL at the server over the network in .env):
    cd ai_waiter_core && uv run python main.py
"""

import asyncio
import json
import logging
import os
import signal
import sys

import httpx
import websockets
from dotenv import load_dotenv

from ai_waiter_core.config import settings
from ai_waiter_core.perception import SileroVAD, PhoWhisperSTT
from ai_waiter_core.perception.queues import get_transcript, shutdown_all
from ai_waiter_core.utils import flush_traces, log_struct

load_dotenv()
logger = logging.getLogger("ai_waiter_core.voice_device")

# This device's robot identity — the SAME id the robot's motion client uses (mock_robot.py --id).
# The mic is bound to a *table* dynamically by the server: when the dispatcher sends this robot to a
# table and it arrives, the backend routes that table's "talk to AI" button here. So this device is
# table-agnostic; each start_listening command tells it which table the guest belongs to.
ROBOT_ID = os.getenv("VOICE_ROBOT_ID", "robo-1")
# Local model latency can be a few seconds; give the agent call generous headroom.
CHAT_TIMEOUT = httpx.Timeout(60.0, connect=5.0)
# After the button: how long to wait for the guest to finish speaking, and then for STT to emit text.
UTTERANCE_TIMEOUT = 15.0
TRANSCRIPT_TIMEOUT = 12.0
WS_RETRY_MAX = 10.0  # cap on reconnect backoff


def _backend_ws_url() -> str:
    """ws://<backend>/ws?role=voice-device&robot_id=<id> derived from ORCHESTRATOR_URL."""
    base = settings.ORCHESTRATOR_URL.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    return f"{base}/ws?role=voice-device&robot_id={ROBOT_ID}"


def _capture_and_send(vad: SileroVAD, agent_client: httpx.Client, table_id: int) -> None:
    """Blocking: arm one utterance, wait for it, transcribe, POST to the agent for `table_id` (the
    table the server says this robot is serving). Runs off the WS loop via asyncio.to_thread so the
    socket stays responsive."""
    # Drop any stale transcript so we POST only what the guest says now.
    while get_transcript(timeout=0.0) is not None:
        pass

    vad.begin_listen()
    print("[LISTENING] mời anh/chị nói...")
    if not vad.wait_for_utterance(UTTERANCE_TIMEOUT):
        print("[TIMEOUT] không nghe thấy gì, quay lại chờ.")
        return

    transcript = get_transcript(timeout=TRANSCRIPT_TIMEOUT)
    if transcript is None or not transcript.text.strip():
        print("[EMPTY] không nhận ra lời nói.")
        return

    text = transcript.text
    print(f"[HEARD @ {transcript.timestamp:.1f}s | bàn {table_id}]: {text}")

    # Send to the server-side agent. No sticky session_id: the agent re-resolves the table's backend
    # session each turn (thread resets after payment). The server mirrors this turn to the tablet.
    try:
        # The agent's /chat keys tables as the "T<N>" string convention; we got an int from the
        # server's start_listening command, so format it back.
        resp = agent_client.post("/chat", json={"table_id": f"T{table_id}", "text": text})
        resp.raise_for_status()
        result = resp.json()
    except httpx.HTTPError as e:
        print(f"Agent request failed: {e}")
        return

    print(f"[WAITER]: {result.get('response', '')}")


async def voice_device_loop(vad: SileroVAD, agent_client: httpx.Client) -> None:
    """Connect to the backend WS hub and react to start_listening commands. Reconnects with backoff."""
    url = _backend_ws_url()
    retry = 0
    while True:
        try:
            async with websockets.connect(url) as ws:
                retry = 0
                logger.info("voice-device connected: %s", url)
                print(f"[READY] đã kết nối backend ({ROBOT_ID}) — chờ điều tới bàn + web bấm 'nói chuyện'.")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") == "start_listening":
                        # The server tags the command with the table this robot is currently serving.
                        table_id = msg.get("table_id")
                        if table_id is None:
                            print("[WARN] start_listening thiếu table_id, bỏ qua.")
                            continue
                        await asyncio.to_thread(_capture_and_send, vad, agent_client, table_id)
        except (OSError, websockets.WebSocketException) as e:
            delay = min(2 ** retry, WS_RETRY_MAX)
            retry += 1
            logger.warning("WS down (%s); reconnect in %.0fs", e, delay)
            print(f"[WS] mất kết nối backend, thử lại sau {delay:.0f}s...")
            await asyncio.sleep(delay)


def main():
    log_struct("Starting AI Waiter Voice Device")
    # One agent HTTP client kept open for the whole run (connection pool reuse).
    agent_client = httpx.Client(base_url=settings.AGENT_URL, timeout=CHAT_TIMEOUT)

    vad = SileroVAD()
    stt = PhoWhisperSTT()

    # Start the mic/VAD + STT threads (each loads its model), then force the slow first STT inference
    # now so the first real turn is fast. Mic stays open but gated — no capture until armed.
    vad.start()
    stt.start()
    stt.warmup()

    print("=" * 50)
    print(f" AI Waiter voice device — Robot {ROBOT_ID}")
    print(f" Agent (LLM)  @ {settings.AGENT_URL}")
    print(f" Backend (WS) @ {settings.ORCHESTRATOR_URL}")
    print(" Models warmed. Bàn được gán động khi robot tới bàn. Ctrl+C để dừng.")
    print("=" * 50)

    def shutdown(*_):
        print("\nShutting down...")
        shutdown_all()
        vad.stop()
        stt.stop()
        agent_client.close()
        flush_traces()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)

    try:
        asyncio.run(voice_device_loop(vad, agent_client))
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
