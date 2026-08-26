"""Jetson half of the command link: fire one interpreted command at the laptop over UDP.

Two rules shape this file.

**It must never raise into the voice loop.** The mic thread is the one thing that must keep
running; a laptop that is switched off, unplugged or on the wrong subnet is a normal condition
during setup, and it must degrade to "the robot doesn't move" rather than "the voice pipeline
dies". Every socket error is logged once and swallowed.

**The first copy must leave immediately.** `protocol.REPEATS` copies spread over ~40 ms is what
makes UDP survivable, but blocking the caller for 40 ms on the stop path is exactly the latency
this design exists to avoid. So copy #1 is sent inline, and the remaining copies go out from a
short-lived daemon thread.
"""

from __future__ import annotations

import logging
import os
import select
import socket
import threading
import time
from itertools import count

from src.robot_link import protocol
from src.robot_link.protocol import Command

logger = logging.getLogger(__name__)

FALLBACK_HOST = "127.0.0.1"
FALLBACK_PORT = 45455


def _env_port() -> int:
    """Read ROBOT_UDP_PORT *now*, not at import time.

    `edge_voice/main.py` calls `load_dotenv()` after its import block, so anything this module
    resolved at import would predate `.env` and silently ignore a port set there.
    """
    try:
        return int(os.environ.get("ROBOT_UDP_PORT", "") or FALLBACK_PORT)
    except ValueError:
        logger.warning("ROBOT_UDP_PORT không phải số — dùng %d", FALLBACK_PORT)
        return FALLBACK_PORT


class CommandSender:
    """Sends `Command`s to the laptop running the Gazebo warehouse."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        robot_id: str = "robo-1",
        enabled: bool = True,
        send_action: bool = True,
    ) -> None:
        self.host = host or os.environ.get("ROBOT_UDP_HOST", "") or FALLBACK_HOST
        self.port = int(port or _env_port())
        self.robot_id = robot_id
        self.enabled = enabled
        # When False the datagram carries only the spoken sentence and the laptop reads it with
        # `robot_link.parse_text`. Sending the brain's action as well is strictly better — it is
        # the trained router's reading rather than a substring match — but the switch exists
        # because "just ship the sentence" is a legitimate way to run this, and because forcing
        # it is the only way to exercise the laptop's fallback path on purpose.
        self.send_action_field = send_action
        self.session = protocol.new_session()
        self._seq = count(1)
        self._sock: socket.socket | None = None
        self._warned = False
        self._unacked: dict[int, str] = {}
        self._lock = threading.Lock()
        self.last_ack_ts = 0.0
        if enabled:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Non-blocking: a full send buffer must not stall the voice loop either.
            self._sock.setblocking(False)
            threading.Thread(target=self._read_acks, daemon=True).start()
            logger.info("Robot link → udp://%s:%d (session %s)", self.host, self.port, self.session)
        else:
            logger.info("Robot link disabled (ROBOT_UDP_HOST chưa đặt) — chỉ nói, không điều khiển")

    # ── public API ────────────────────────────────────────────────────────────
    def navigate(self, action: dict, sentence: str = "", reply: str = "", source: str = "agent") -> None:
        """Send a navigate action the agent produced (already a `NavigateAction.model_dump()`)."""
        self._send(protocol.KIND_NAVIGATE, action=action, sentence=sentence, reply=reply, source=source)

    def control(self, verb: str, sentence: str = "", reply: str = "", source: str = "fastpath") -> None:
        """Send stop / resume / cancel. `source="fastpath"` means the LLM was bypassed."""
        self._send(
            protocol.KIND_CONTROL,
            action={"type": "control", "verb": verb},
            sentence=sentence,
            reply=reply,
            source=source,
        )

    def send_action(self, action: dict | None, sentence: str = "", reply: str = "") -> bool:
        """Route whatever action a turn produced. Returns True if anything was sent.

        The agent may answer with no action at all (most `answer` and `chat` turns), which is not
        an error — it just means this turn had nothing for the robot to do.
        """
        if not action:
            return False
        kind = action.get("type")
        if kind == "navigate":
            self.navigate(action, sentence, reply)
            return True
        if kind == "control":
            self.control(action.get("verb", ""), sentence, reply, source="agent")
            return True
        logger.warning("Robot link: bỏ qua action lạ %r", kind)
        return False

    @property
    def link_ok(self) -> bool:
        """Has the laptop acknowledged anything in the last 30 s?

        False before the first command of a run — silence is not evidence either way until we
        have actually sent something.
        """
        return self.last_ack_ts > 0.0 and (time.time() - self.last_ack_ts) < 30.0

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    # ── internals ─────────────────────────────────────────────────────────────
    def _send(self, kind: str, **fields) -> None:
        if not self.enabled or self._sock is None:
            return
        if not self.send_action_field:
            fields = {**fields, "action": None}
        cmd = Command(
            kind=kind,
            robot_id=self.robot_id,
            session=self.session,
            seq=next(self._seq),
            **fields,
        )
        raw = cmd.encode()
        with self._lock:
            self._unacked[cmd.seq] = cmd.sentence[:40]
        # Give all REPEATS copies time to land before deciding nobody is listening.
        threading.Timer(1.0, self._check_ack, args=(cmd.seq,)).start()
        self._sendto(raw)  # copy #1, inline — this is the one that matters
        threading.Thread(target=self._repeat, args=(raw,), daemon=True).start()
        logger.info("→ robot [%s/%s] seq=%d %s", kind, cmd.source, cmd.seq, cmd.sentence[:60])

    def _repeat(self, raw: bytes) -> None:
        for _ in range(protocol.REPEATS - 1):
            time.sleep(protocol.REPEAT_GAP_S)
            self._sendto(raw)

    def _read_acks(self) -> None:
        """Collect acks on the same socket the commands go out on."""
        while self._sock is not None:
            try:
                ready, _, _ = select.select([self._sock], [], [], 0.5)
                if not ready:
                    continue
                raw, _addr = self._sock.recvfrom(512)
            except (OSError, ValueError):
                return  # socket closed under us during shutdown
            ack = protocol.decode(raw)
            if ack is None or ack.kind != protocol.KIND_ACK or ack.session != self.session:
                continue
            with self._lock:
                self._unacked.pop(ack.seq, None)
            self.last_ack_ts = time.time()

    def _check_ack(self, seq: int) -> None:
        with self._lock:
            sentence = self._unacked.pop(seq, None)
        if sentence is None:
            return
        # The one failure mode worth shouting about: a wrong ROBOT_UDP_HOST behaves exactly like
        # a robot that heard the command and chose to ignore it.
        logger.warning("Robot KHÔNG phản hồi lệnh seq=%d (%r). Kiểm tra ROBOT_UDP_HOST=%s:%d "
                       "và `make robotlink` trên laptop.", seq, sentence, self.host, self.port)

    def _sendto(self, raw: bytes) -> None:
        try:
            self._sock.sendto(raw, (self.host, self.port))
            self._warned = False
        except OSError as e:
            # Log the first failure of a run, then stay quiet: an unreachable laptop would
            # otherwise fill the Jetson's console with one line per repeat, per command.
            if not self._warned:
                logger.warning("Robot link không gửi được tới %s:%d (%s)", self.host, self.port, e)
                self._warned = True


def build_sender(robot_id: str = "robo-1") -> CommandSender:
    """Sender configured from the environment; disabled when ROBOT_UDP_HOST is unset.

    Disabled-by-default is intentional. Voice-only runs (bench testing the STT, demoing the web
    monitor without Gazebo) are common, and they should not need a laptop listening on the LAN.
    """
    host = os.environ.get("ROBOT_UDP_HOST", "").strip()
    send_action = os.environ.get("ROBOT_LINK_SEND_ACTION", "1").strip() not in ("0", "false", "no")
    return CommandSender(host=host or None, robot_id=robot_id,
                         enabled=bool(host), send_action=send_action)
