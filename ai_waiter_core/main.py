"""AI Waiter — voice device (runs on the machine with the microphone: Jetson/laptop).

This is NOT an always-on loop anymore. It is a *command-driven* service: it preloads + warms the
mic/VAD/STT models, connects to the backend WS hub as ``role=voice-device`` for its table, then idles
until the table's tablet (customer_ui) pushes the "talk to AI" button. On ``start_listening`` it
captures ONE utterance (mic → VAD → Whisper) and POSTs the recognised text to the agent (``POST
/chat``). The agent runs the LLM and mirrors the turn back to the tablet via the voice bridge, so the
web UI shows the conversation — the browser never touches the microphone (so no HTTPS requirement).

Why a resident service instead of the web spawning it: a browser page can't launch a process on the
device (sandbox), and the mic needs a secure context. Running here as a service that the web *signals*
gives the production feel ("open web → press talk → speak") without either limitation.

Run on the device (point AGENT_URL / ORCHESTRATOR_URL at the server over the network in .env):
    cd ai_waiter_core && uv run python main.py
"""

import asyncio
import json
import logging
import signal
import sys

import httpx
import websockets
from dotenv import load_dotenv

from ai_waiter_core.config import settings
from ai_waiter_core.perception import SileroVAD, PhoWhisperSTT
from ai_waiter_core.perception.queues import get_transcript, shutdown_all
from ai_waiter_core.services.orchestrator_client import _table_int
from ai_waiter_core.utils import flush_traces, log_struct

load_dotenv()
logger = logging.getLogger("ai_waiter_core.voice_device")

TABLE_ID = "T1"
# Local model latency can be a few seconds; give the agent call generous headroom.
CHAT_TIMEOUT = httpx.Timeout(60.0, connect=5.0)
# After the button: how long to wait for the guest to finish speaking, and then for STT to emit text.
UTTERANCE_TIMEOUT = 15.0
TRANSCRIPT_TIMEOUT = 12.0
WS_RETRY_MAX = 10.0  # cap on reconnect backoff


def _backend_ws_url() -> str:
    """ws://<backend>/ws?role=voice-device&table_id=<int> derived from ORCHESTRATOR_URL."""
    base = settings.ORCHESTRATOR_URL.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    return f"{base}/ws?role=voice-device&table_id={_table_int(TABLE_ID)}"


def _capture_and_send(vad: SileroVAD, agent_client: httpx.Client) -> None:
    """Blocking: arm one utterance, wait for it, transcribe, POST to the agent. Runs off the WS
    loop via asyncio.to_thread so the socket stays responsive."""
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
    print(f"[HEARD @ {transcript.timestamp:.1f}s]: {text}")

    # Send to the server-side agent. No sticky session_id: the agent re-resolves the table's backend
    # session each turn (thread resets after payment). The server mirrors this turn to the tablet.
    try:
        resp = agent_client.post("/chat", json={"table_id": TABLE_ID, "text": text})
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
                print(f"[READY] đã kết nối backend — chờ web bấm 'nói chuyện' (bàn {_table_int(TABLE_ID)}).")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") == "start_listening":
                        await asyncio.to_thread(_capture_and_send, vad, agent_client)
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
    print(f" AI Waiter voice device — Table {TABLE_ID}")
    print(f" Agent (LLM)  @ {settings.AGENT_URL}")
    print(f" Backend (WS) @ {settings.ORCHESTRATOR_URL}")
    print(" Models warmed. Bấm 'nói chuyện' trên web để nói. Ctrl+C để dừng.")
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
