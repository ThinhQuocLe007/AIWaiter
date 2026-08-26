"""Wire format for the voice → robot datagram, shared verbatim by both ends.

Stdlib only, on purpose: the Jetson imports it inside the voice loop and the laptop imports it
inside a ROS node, and neither should have to agree on a third-party version to agree on a
message.

One command is one datagram. There is no fragmentation and no stream state, so a lost packet
costs exactly one command and never desynchronises the link. Two mechanisms make that loss
tolerable:

  * the sender transmits each command `REPEATS` times a few milliseconds apart. Datagram loss on
    a wired LAN is bursty but short; three copies across ~40 ms almost always survive it, and the
    cost is 3 × ~300 bytes.
  * the receiver de-duplicates on (session, seq), so those repeats — and any duplication the
    network invents — collapse back into one command. `session` is regenerated per process, so a
    Jetson restart cannot have its fresh seq numbers swallowed as duplicates of the old run's.

Commands are idempotent by design (stop, resume, cancel, "go to A"), so even if de-duplication
failed the worst case is applying the same instruction twice.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field

WIRE_VERSION = 1

# Every command must fit one datagram well under the smallest MTU on the path, so the sentence is
# truncated rather than allowed to fragment. Real spoken commands are far shorter than this.
MAX_DATAGRAM = 1200
MAX_SENTENCE = 400

# How many copies of each datagram the sender puts on the wire, and the gap between them.
REPEATS = 3
REPEAT_GAP_S = 0.02

KIND_NAVIGATE = "navigate"
KIND_CONTROL = "control"
KIND_MOTION = "motion"
KIND_PING = "ping"
# The receiver echoes one of these per datagram it accepts. It carries no instruction — its whole
# job is to let the sender distinguish "the laptop is ignoring me" from "the laptop never heard
# me", which on a one-way link look identical and cost a demo five minutes of panic.
KIND_ACK = "ack"


@dataclass
class Command:
    """One spoken instruction, already interpreted, on its way to the robot.

    `action` is the agent's own `NavigateAction`/`ControlAction` dump — the same contract the web
    monitor renders — so the laptop never re-parses Vietnamese. `sentence` rides along anyway:
    it costs nothing, it is what the operator actually said, and it is the only thing worth
    printing in a log when a command turns out to have been interpreted wrongly.
    """

    kind: str
    action: dict | None = None
    sentence: str = ""
    reply: str = ""
    source: str = "agent"          # "fastpath" (matched on Jetson) | "agent" (LLM decided)
    robot_id: str = "robo-1"
    seq: int = 0
    session: str = ""
    ts: float = field(default_factory=time.time)
    v: int = WIRE_VERSION

    def encode(self) -> bytes:
        payload = asdict(self)
        payload["sentence"] = (self.sentence or "")[:MAX_SENTENCE]
        payload["reply"] = (self.reply or "")[:MAX_SENTENCE]
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_DATAGRAM:
            # Only free-text can push us over; drop it rather than lose the command itself.
            payload["sentence"] = payload["sentence"][:80]
            payload["reply"] = ""
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return raw


def decode(raw: bytes) -> Command | None:
    """Parse a datagram, or None if it is malformed or speaks a version we don't.

    Returning None rather than raising is deliberate: this runs on an open UDP socket, where a
    stray packet from anything else on the LAN is a normal event, not an error worth crashing a
    robot bridge over.
    """
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("v") != WIRE_VERSION:
        return None
    kind = payload.get("kind")
    if kind not in (KIND_NAVIGATE, KIND_CONTROL, KIND_MOTION, KIND_PING, KIND_ACK):
        return None
    known = Command.__dataclass_fields__.keys()
    return Command(**{k: val for k, val in payload.items() if k in known})


def ack_for(cmd: "Command") -> bytes:
    """A minimal datagram acknowledging `cmd`, echoing what identifies it."""
    return Command(kind=KIND_ACK, session=cmd.session, seq=cmd.seq, robot_id=cmd.robot_id).encode()


def new_session() -> str:
    """A short id identifying this sender process, so seq numbers are scoped to one run."""
    return uuid.uuid4().hex[:8]


class Deduper:
    """Remembers recently seen (session, seq) pairs so repeats are applied exactly once.

    A bounded deque, not a growing set: the link runs for hours and the only thing that must be
    remembered is the last few seconds of traffic.
    """

    def __init__(self, window: int = 512) -> None:
        self._seen: set[tuple[str, int]] = set()
        self._order: deque[tuple[str, int]] = deque(maxlen=window)

    def is_duplicate(self, cmd: Command) -> bool:
        key = (cmd.session, cmd.seq)
        if key in self._seen:
            return True
        if len(self._order) == self._order.maxlen:
            self._seen.discard(self._order[0])
        self._order.append(key)
        self._seen.add(key)
        return False
