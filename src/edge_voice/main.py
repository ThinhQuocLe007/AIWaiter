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
    uv run python src/edge_voice/main.py    # or: make voice
"""

import asyncio
import json
import os
import signal
import sys
import threading

# Make the repo root importable so `from src.agent_brain...` resolves when this file is
# invoked as `python src/edge_voice/main.py` (uvicorn's `:` form sets sys.path automatically,
# but a plain script run puts the *script's* directory on sys.path[0] which hides the `src/`
# package from absolute imports). `parents[2]` from this file = repo root.
from pathlib import Path

import httpx
import websockets
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.agent_brain.config import settings
from src.edge_voice.log import log_struct, logger
from src.edge_voice.output.tts_engine import StreamingPlayer, speak_sentence, speak_streaming, warmup as tts_warmup
from src.edge_voice.perception import PhoWhisperSTT, SileroVAD
from src.edge_voice.perception.queues import get_transcript, shutdown_all

load_dotenv()

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


def _capture_and_send(vad: SileroVAD, agent_client: httpx.Client, table_id: int,
                      player: StreamingPlayer, cancel: threading.Event) -> None:
    """Blocking: arm one utterance, wait for it, transcribe, POST to the agent for `table_id` (the
    table the server says this robot is serving). Runs off the WS loop in a worker thread so the
    socket stays responsive; `cancel` is set by a cancel_listening frame and aborts the turn at
    every stage boundary."""
    # Drop any stale transcript so we POST only what the guest says now.
    while get_transcript(timeout=0.0) is not None:
        pass

    vad.begin_listen()
    print("[LISTENING] mời anh/chị nói...")
    if not vad.wait_for_utterance(UTTERANCE_TIMEOUT):
        print("[TIMEOUT] không nghe thấy gì, quay lại chờ.")
        return
    if cancel.is_set():
        print("[CANCELLED] khách hủy khi đang nghe.")
        return

    transcript = get_transcript(timeout=TRANSCRIPT_TIMEOUT)
    if transcript is None or not transcript.text.strip():
        print("[EMPTY] không nhận ra lời nói.")
        return
    if cancel.is_set():
        print("[CANCELLED] khách hủy — không gửi cho agent.")
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

    response = result.get("response", "")
    stage = result.get("final_stage", "IDLE")

    print(f"[WAITER]: {response}")

    if response and not cancel.is_set() and not player.is_stopped():
        speak_streaming(response, stage, player)


def _capture_and_send_streaming(vad: SileroVAD, agent_client: httpx.Client, table_id: int,
                                 player: StreamingPlayer, cancel: threading.Event) -> None:
    """Streaming variant: consumes SSE from POST /chat/stream, plays sentences incrementally.

    `cancel` (set by the tablet's Hủy/Dừng button via a cancel_listening frame) aborts the turn
    wherever it is: an armed capture is dropped, an in-flight agent stream is closed (we stop
    consuming — the LLM may finish server-side but the tablet suppresses that reply), and TTS
    playback is cut by player.interrupt() done on the WS side.
    """
    while get_transcript(timeout=0.0) is not None:
        pass

    vad.begin_listen()
    print("[LISTENING] mời anh/chị nói...")
    if not vad.wait_for_utterance(UTTERANCE_TIMEOUT):
        print("[TIMEOUT] không nghe thấy gì, quay lại chờ.")
        return
    if cancel.is_set():  # cancel_listen() releases the wait above immediately
        print("[CANCELLED] khách hủy khi đang nghe.")
        return

    transcript = get_transcript(timeout=TRANSCRIPT_TIMEOUT)
    if transcript is None or not transcript.text.strip():
        print("[EMPTY] không nhận ra lời nói.")
        return
    if cancel.is_set():
        print("[CANCELLED] khách hủy — không gửi cho agent.")
        return

    text = transcript.text
    print(f"[HEARD @ {transcript.timestamp:.1f}s | bàn {table_id}]: {text}")

    try:
        with agent_client.stream("POST", "/chat/stream", json={
            "table_id": f"T{table_id}", "text": text
        }) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if cancel.is_set():
                    print("[CANCELLED] dừng nhận trả lời từ agent.")
                    break
                if not line or not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                ev = data.get("event")

                if ev == "progress":
                    print(f"[WAITER progress]: {data.get('text', '...')}")
                elif ev == "sentence":
                    sentence = data["text"]
                    print(f"[WAITER]: {sentence}")
                    if sentence and not cancel.is_set() and not player.is_stopped():
                        speak_sentence(sentence, player)
                elif ev == "done":
                    print(f"[WAITER done] stage={data.get('stage')}")
                    break
    except httpx.HTTPError as e:
        print(f"Agent stream request failed: {e}")


async def voice_device_loop(vad: SileroVAD, agent_client: httpx.Client, player: StreamingPlayer) -> None:
    """Connect to the backend WS hub and react to server commands. Reconnects with backoff.

    The turn itself (capture → STT → agent → TTS) runs as a BACKGROUND task, never awaited inline:
    the receive loop must stay free to process cancel_listening / set_muted arriving mid-turn —
    that's the whole point of the tablet's Dừng and tắt-loa buttons working in realtime.
    """
    url = _backend_ws_url()
    retry = 0
    turn_task: asyncio.Task | None = None
    cancel = threading.Event()  # per-turn abort flag, shared with the capture worker thread
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
                    mtype = msg.get("type")
                    if mtype == "start_listening":
                        # The server tags the command with the table this robot is currently serving.
                        table_id = msg.get("table_id")
                        if table_id is None:
                            print("[WARN] start_listening thiếu table_id, bỏ qua.")
                            continue
                        if turn_task is not None and not turn_task.done():
                            print("[BUSY] một lượt đang chạy — bỏ qua start_listening.")
                            continue
                        cancel.clear()
                        player.reset()  # clear a leftover interrupt; mute (if on) persists
                        turn_task = asyncio.create_task(asyncio.to_thread(
                            _capture_and_send_streaming, vad, agent_client, table_id, player, cancel
                        ))
                    elif mtype == "cancel_listening":
                        # Tablet's Hủy/Dừng: kill the whole in-flight turn — armed mic, agent
                        # stream consumption AND the sentence currently coming out of the speaker.
                        print("[CANCEL] khách bấm dừng — hủy lượt hiện tại.")
                        cancel.set()
                        vad.cancel_listen()
                        player.interrupt()
                    elif mtype == "set_muted":
                        muted = bool(msg.get("muted"))
                        player.set_muted(muted)
                        print(f"[MUTE] {'tắt' if muted else 'bật'} loa trả lời.")
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

    # Streaming TTS player (edge-tts → sounddevice). Warm the TTS engine so the
    # first customer turn doesn't pay the cold-start latency. VAD barge-in allows
    # the customer to interrupt the robot mid-speech by talking.
    player = StreamingPlayer(vad=vad)
    tts_warmup()
    speak_streaming("Xin chào", "IDLE", player)

    print("=" * 50)
    print(f" AI Waiter voice device — Robot {ROBOT_ID}")
    print(f" Agent (LLM)  @ {settings.AGENT_URL}")
    print(f" Backend (WS) @ {settings.ORCHESTRATOR_URL}")
    print(" Models warmed. Bàn được gán động khi robot tới bàn. Ctrl+C để dừng.")
    print("=" * 50)

    def shutdown(*_):
        print("\nShutting down...")
        player.interrupt()
        shutdown_all()
        vad.stop()
        stt.stop()
        agent_client.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)

    try:
        asyncio.run(voice_device_loop(vad, agent_client, player))
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
