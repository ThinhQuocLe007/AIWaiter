"""AI Waiter — voice device (runs on the machine with the microphone: Jetson/laptop).

This is NOT an always-on loop anymore. It is a *command-driven* service: it preloads + warms the
mic/VAD/STT models, connects to the backend WS hub as ``role=voice-device&robot_id=<id>``, then idles
until the monitor pushes the "talk to AI" button. On the command it captures ONE utterance
(mic → VAD → Whisper) and POSTs the text to the agent (``POST /chat`` tagged with this robot's id,
which is also the agent's conversation-thread key). The agent runs the LLM and
mirrors the turn back to the monitor via the voice bridge, so the web UI shows the conversation — the
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
import time

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
from src.agent_brain.warehouse import control_phrases
from src.edge_voice import audio_levels
from src.edge_voice.log import log_struct, logger
from src.edge_voice.output.tts_engine import StreamingPlayer, speak_sentence, speak_streaming, warmup as tts_warmup
from src.edge_voice.perception import PhoWhisperSTT, SileroVAD
from src.edge_voice.perception.queues import get_transcript, shutdown_all
from src.robot_link.sender import CommandSender, build_sender

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# This device's robot identity — the SAME id the robot's motion client uses (mock_robot.py --id).
# It addresses this mic on the WS hub AND names the agent's conversation thread: one robot, one
# thread. Nothing else has to be carried in a command frame or matched up between services.
ROBOT_ID = os.getenv("VOICE_ROBOT_ID", "robo-1")
# UDP link to the laptop running Gazebo, built in main(). Module-level because the turn function
# runs in a worker thread and threading a sender through three call sites buys nothing. Stays None
# when ROBOT_UDP_HOST is unset — a voice-only run (bench test, web-monitor demo) needs no laptop.
_ROBOT: CommandSender | None = None
# Local model latency can be a few seconds; give the agent call generous headroom.
CHAT_TIMEOUT = httpx.Timeout(60.0, connect=5.0)
# After the button: how long to wait for the guest to finish speaking, and then for STT to emit text.
UTTERANCE_TIMEOUT = 15.0
TRANSCRIPT_TIMEOUT = 12.0
WS_RETRY_MAX = 10.0  # cap on reconnect backoff


class Telemetry:
    """Narrates this device's pipeline to the backend for the voice monitor web.

    Everything here is best-effort and silent on failure. The monitor is an observer; a demo screen
    failing to update must never be able to break, slow or abort a real spoken turn.

    Thread-affinity is the whole reason this is a class. The WS belongs to the asyncio loop, but the
    stages worth reporting happen inside ``_capture_and_send_streaming``, which runs in a worker
    thread (``asyncio.to_thread``) — touching the socket from there directly is undefined behaviour.
    So ``send()`` is callable from any thread and hops back onto the loop to do the write.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._ws = None

    def set_socket(self, ws) -> None:
        """Point at the live socket (or None while reconnecting). Called from the loop thread."""
        self._ws = ws

    def send(self, stage: str, /, **fields) -> None:
        """Report one pipeline stage. `stage` is positional-only so a payload field of the same
        name (the agent's DIALOGUE stage — a different thing entirely) cannot collide with it."""
        ws = self._ws
        if ws is None:
            return
        frame = json.dumps({"type": "telemetry", "stage": stage, "ts": time.time(), **fields})

        async def _write() -> None:
            try:
                await ws.send(frame)
            except Exception:  # socket died mid-turn — the reconnect path handles it
                pass

        try:
            asyncio.run_coroutine_threadsafe(_write(), self._loop)
        except RuntimeError:  # loop closing during shutdown
            pass


def _backend_ws_url() -> str:
    """ws://<backend>/ws?role=voice-device&robot_id=<id> derived from ORCHESTRATOR_URL."""
    base = settings.ORCHESTRATOR_URL.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    return f"{base}/ws?role=voice-device&robot_id={ROBOT_ID}"


def _capture_and_send_streaming(vad: SileroVAD, agent_client: httpx.Client,
                                 player: StreamingPlayer, cancel: threading.Event,
                                 tel: "Telemetry") -> None:
    """Streaming variant: consumes SSE from POST /chat/stream, plays sentences incrementally.

    `cancel` (set by the tablet's Hủy/Dừng button via a cancel_listening frame) aborts the turn
    wherever it is: an armed capture is dropped, an in-flight agent stream is closed (we stop
    consuming — the LLM may finish server-side but the tablet suppresses that reply), and TTS
    playback is cut by player.interrupt() done on the WS side.
    """
    while get_transcript(timeout=0.0) is not None:
        pass

    t_start = time.perf_counter()

    def ms_since(t: float) -> int:
        return int((time.perf_counter() - t) * 1000)

    vad.begin_listen()
    print("[LISTENING] mời anh/chị nói...")
    tel.send("listening")
    if not vad.wait_for_utterance(UTTERANCE_TIMEOUT):
        print("[TIMEOUT] không nghe thấy gì, quay lại chờ.")
        tel.send("timeout", waited_ms=ms_since(t_start))
        return
    if cancel.is_set():  # cancel_listen() releases the wait above immediately
        print("[CANCELLED] khách hủy khi đang nghe.")
        tel.send("cancelled", at="listening")
        return

    # Speech ended here; everything from now until the transcript arrives is Whisper's own time,
    # which is the number worth showing separately from "how long the guest talked".
    t_speech_end = time.perf_counter()
    tel.send("transcribing", speech_ms=ms_since(t_start))

    transcript = get_transcript(timeout=TRANSCRIPT_TIMEOUT)
    if transcript is None or not transcript.text.strip():
        print("[EMPTY] không nhận ra lời nói.")
        # An empty transcript is also what the hallucination filter produces when it drops a
        # bogus caption line (see perception/stt_phowhisper.py), so the monitor shows this as
        # "nghe nhưng không dùng được" rather than pretending nothing happened.
        tel.send("empty", stt_ms=ms_since(t_speech_end))
        return
    if cancel.is_set():
        print("[CANCELLED] khách hủy — không gửi cho agent.")
        tel.send("cancelled", at="transcribed")
        return

    text = transcript.text
    stt_ms = ms_since(t_speech_end)
    print(f"[HEARD @ {transcript.timestamp:.1f}s]: {text}")
    tel.send(
        "heard", text=text,
        stt_ms=stt_ms, audio_s=round(transcript.audio_duration_s or 0.0, 2),
    )

    # ── Fast path: run control ("dừng lại", "đi tiếp", "hủy") ────────────────
    # These skip the agent entirely. The round trip to the LLM — VPN to the PC server, LangGraph,
    # Ollama, back — is several seconds, and a robot that keeps driving for three seconds after
    # being told to stop has not stopped. Everything the command needs is already decided by the
    # time the transcript exists, so the datagram goes out here and the LLM never sees the turn.
    # The agent still has a `control` intent for phrasings this matcher misses; that path is
    # slower but at least ends in a stop instead of a chat reply.
    verb = control_phrases.match(text)
    if verb is not None:
        if _ROBOT is not None:
            _ROBOT.control(verb, sentence=text, reply=control_phrases.REPLY[verb])
        reply = control_phrases.REPLY[verb]
        print(f"[FASTPATH {verb.upper()} in {ms_since(t_speech_end)}ms]: {reply}")
        tel.send("speaking", text=reply, index=0, muted=player.is_muted())
        if not cancel.is_set() and not player.is_stopped():
            speak_sentence(reply, player)
        tel.send("done", dialog_stage="control",
                 agent_ms=0, turn_ms=ms_since(t_start), sentences=1)
        return

    t_agent = time.perf_counter()
    spoken = 0
    try:
        with agent_client.stream("POST", "/chat/stream", json={
            "robot_id": ROBOT_ID, "text": text
        }) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if cancel.is_set():
                    print("[CANCELLED] dừng nhận trả lời từ agent.")
                    tel.send("cancelled", at="agent")
                    break
                if not line or not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                ev = data.get("event")

                if ev == "progress":
                    print(f"[WAITER progress]: {data.get('text', '...')}")
                    tel.send("thinking")
                elif ev == "sentence":
                    sentence = data["text"]
                    print(f"[WAITER]: {sentence}")
                    if sentence and not cancel.is_set() and not player.is_stopped():
                        # Report BEFORE speaking: speak_sentence blocks until the audio has played,
                        # so reporting after it would show the caption only once the robot had
                        # already finished saying that line.
                        tel.send(
                            "speaking", text=sentence, index=spoken,
                            muted=player.is_muted(),
                        )
                        speak_sentence(sentence, player)
                        spoken += 1
                elif ev == "done":
                    print(f"[WAITER done] stage={data.get('stage')}")
                    # The `done` event is where the structured action lives (navigate token, or a
                    # control verb the fast path did not catch). Send it after the reply has been
                    # spoken so the robot never starts moving before it has answered.
                    if _ROBOT is not None and not cancel.is_set():
                        _ROBOT.send_action(data.get("action"), sentence=text)
                    tel.send(
                        "done", dialog_stage=data.get("stage"),
                        agent_ms=ms_since(t_agent), turn_ms=ms_since(t_start), sentences=spoken,
                    )
                    break
    except httpx.HTTPError as e:
        print(f"Agent stream request failed: {e}")
        tel.send("error", detail=str(e)[:200])


async def voice_device_loop(vad: SileroVAD, agent_client: httpx.Client, player: StreamingPlayer) -> None:
    """Connect to the backend WS hub and react to server commands. Reconnects with backoff.

    The turn itself (capture → STT → agent → TTS) runs as a BACKGROUND task, never awaited inline:
    the receive loop must stay free to process cancel_listening / set_muted arriving mid-turn —
    that's the whole point of the tablet's Dừng and tắt-loa buttons working in realtime.

    We also tell the backend when a turn starts and ends (`voice_turn`), which is what the monitor
    screen reports as "busy" for this mic — see realtime/ws.py.
    """
    url = _backend_ws_url()
    retry = 0
    ws = None  # the live socket; send_turn_state() below always uses the current one
    # Stage reporting for the voice monitor. Bound to THIS loop, and re-pointed at each new socket
    # below so a reconnect resumes reporting instead of going quiet for the rest of the run.
    tel = Telemetry(asyncio.get_running_loop())
    turn_task: asyncio.Task | None = None
    # Monotonic id of the turn currently owning the mic. A cancelled turn can keep unwinding for
    # seconds after a new one starts; only the current turn may report "finished", or that zombie
    # would clear the busy flag in the middle of the new conversation.
    turn_seq = 0

    async def send_turn_state(active: bool) -> None:
        if ws is None:
            return
        try:
            await ws.send(json.dumps({"type": "voice_turn", "active": active}))
        except Exception:  # link dropped — the server clears the flag on disconnect anyway
            pass

    async def report_levels() -> None:
        """Push the real mixer levels up so the monitor's sliders show the truth.

        Off the loop thread: pactl is a subprocess, and this runs on the same receive loop that
        has to stay free for a cancel arriving mid-turn. `can_set=False` (no pactl on this box)
        is what disables the sliders in the web rather than leaving them lying about control
        they don't have.
        """
        if not audio_levels.available():
            tel.send("levels", speaker=None, mic=None, can_set=False)
            return
        levels = await asyncio.to_thread(audio_levels.get_levels)
        tel.send("levels", can_set=True, **levels)

    # Abort flag of the CURRENT turn, handed to that turn's capture worker. A fresh Event per
    # turn, never a reused one: a cancelled worker can still be parked in a blocking call (the
    # agent stream, the STT queue wait) for seconds after we cancel it, and clearing a SHARED
    # flag for the next turn would un-cancel that zombie and let it speak over the new one.
    turn_cancel = threading.Event()
    while True:
        try:
            async with websockets.connect(url) as ws:
                retry = 0
                tel.set_socket(ws)
                logger.info("voice-device connected: %s", url)
                print(f"[READY] đã kết nối backend ({ROBOT_ID}) — chờ điều tới bàn + web bấm 'nói chuyện'.")
                # A turn that outlived the dropped socket: the server forgot we were talking when
                # the old one closed, so re-assert the hold on the new one.
                if turn_task is not None and not turn_task.done():
                    await send_turn_state(True)
                # Levels first, before any command: a monitor that opened while we were away
                # otherwise shows two sliders parked at zero until someone drags one.
                await report_levels()
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    mtype = msg.get("type")
                    if mtype == "start_listening":
                        # Busy only counts for a turn still doing real work. A CANCELLED turn is a
                        # zombie: it has been told to quit and is just unwinding a blocking read,
                        # which can take as long as the agent takes to answer. Treating it as busy
                        # is what made the device go deaf after Hủy / "cuộc trò chuyện mới" — every
                        # later start_listening was dropped here and the guest saw an agent that
                        # had simply stopped hearing them.
                        if turn_task is not None and not turn_task.done() and not turn_cancel.is_set():
                            print("[BUSY] một lượt đang chạy — bỏ qua start_listening.")
                            continue
                        turn_cancel = threading.Event()  # this turn's own flag; zombies keep theirs set
                        player.reset()  # clear a leftover interrupt; mute (if on) persists
                        turn_seq += 1
                        turn_task = asyncio.create_task(asyncio.to_thread(
                            _capture_and_send_streaming, vad, agent_client, player,
                            turn_cancel, tel,
                        ))
                        # Flag busy from the moment we start listening, not from the first spoken
                        # word: the whole turn — mic armed, LLM thinking, robot talking — is time
                        # this device cannot take another command.
                        await send_turn_state(True)

                        def _turn_finished(_task, seq=turn_seq):
                            # _capture_and_send_streaming returns only after its last sentence has
                            # finished playing (play_sentence blocks), so this is genuinely
                            # "the robot has stopped talking".
                            if seq == turn_seq:
                                asyncio.create_task(send_turn_state(False))

                        turn_task.add_done_callback(_turn_finished)
                    elif mtype == "cancel_listening":
                        # Tablet's Hủy/Dừng: kill the whole in-flight turn — armed mic, agent
                        # stream consumption AND the sentence currently coming out of the speaker.
                        print("[CANCEL] khách bấm dừng — hủy lượt hiện tại.")
                        tel.send("cancelled", at="command")
                        turn_cancel.set()
                        vad.cancel_listen()
                        player.interrupt()
                    elif mtype == "set_muted":
                        muted = bool(msg.get("muted"))
                        player.set_muted(muted)
                        print(f"[MUTE] {'tắt' if muted else 'bật'} loa trả lời.")
                        tel.send("muted", muted=muted)
                    elif mtype == "set_audio_level":
                        # The monitor's two sliders. This moves the machine's real PulseAudio
                        # levels, not a gain of our own — see audio_levels for why.
                        target = msg.get("target")
                        percent = msg.get("percent")
                        if target in ("speaker", "mic") and isinstance(percent, (int, float)):
                            actual = await asyncio.to_thread(audio_levels.set_level, target, int(percent))
                            print(f"[AUDIO] {target} → {actual}%")
                            await report_levels()
                        else:
                            print(f"[WARN] set_audio_level không hợp lệ: {msg!r}")
        except (OSError, websockets.WebSocketException) as e:
            tel.set_socket(None)  # stop writing into a dead socket while we back off
            delay = min(2 ** retry, WS_RETRY_MAX)
            retry += 1
            logger.warning("WS down (%s); reconnect in %.0fs", e, delay)
            print(f"[WS] mất kết nối backend, thử lại sau {delay:.0f}s...")
            await asyncio.sleep(delay)


def main():
    global _ROBOT
    log_struct("Starting AI Waiter Voice Device")
    # One agent HTTP client kept open for the whole run (connection pool reuse).
    agent_client = httpx.Client(base_url=settings.AGENT_URL, timeout=CHAT_TIMEOUT)
    _ROBOT = build_sender(ROBOT_ID)

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
    print(f" Robot (UDP)  @ {f'{_ROBOT.host}:{_ROBOT.port}' if _ROBOT.enabled else 'tắt — đặt ROBOT_UDP_HOST để bật'}")
    print(" Models warmed. Bàn được gán động khi robot tới bàn. Ctrl+C để dừng.")
    print("=" * 50)

    def shutdown(*_):
        print("\nShutting down...")
        player.interrupt()
        shutdown_all()
        vad.stop()
        stt.stop()
        agent_client.close()
        if _ROBOT is not None:
            _ROBOT.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)

    try:
        asyncio.run(voice_device_loop(vad, agent_client, player))
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
