"""WebSocket connection manager — tracks live sockets per role + per robot id.

Extracted from ``realtime/ws.py`` so the manager class can be imported in
isolation (e.g. from routers) without pulling in the FastAPI router and
the message-handling helper. The ``ws.py`` module still owns the ``/ws``
endpoint and the robot-frame dispatcher routing; this file owns the
*registry* of live sockets only.
"""

import json
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks live sockets per role + per robot id, and sends JSON events to them."""

    def __init__(self) -> None:
        self._by_role: dict[str, set[WebSocket]] = {}
        # Robot sockets are also indexed by id so the dispatcher can target one robot.
        self._robots: dict[str, WebSocket] = {}
        # Voice-device (mic) sockets, indexed by robot id — the same id as the robot's motion socket.
        self._voice_devices: dict[str, WebSocket] = {}
        # Dynamic "which robot's mic serves which table" binding. The dispatcher sets it when a robot
        # arrives at a table; "table N wants to talk" resolves through here to the robot's mic. Empty
        # until a robot is actually standing at a table — that's why an unattended table has no mic.
        self._table_to_robot: dict[int, str] = {}
        # Robots whose voice device is in the middle of a conversation turn (listening → LLM →
        # speaking). The dispatcher holds a robot's `task.release` while this is set, so it can't
        # drive away mid-sentence — see dispatcher._release_robot.
        self._voice_busy: set[str] = set()
        # Last speaker/mic levels each device reported, e.g. {"speaker": 45, "mic": 100,
        # "can_set": True}. Cached only so a monitor page opened AFTER the device connected can
        # start its sliders at the real values — the device pushes a fresh frame on every change,
        # so nothing here is ever the authority on what the hardware is actually set to.
        self._voice_levels: dict[str, dict] = {}

    async def connect(
        self,
        ws: WebSocket,
        role: str,
        robot_id: str | None = None,
    ) -> None:
        await ws.accept()
        self._by_role.setdefault(role, set()).add(ws)
        # A robot opens two sockets sharing one id (role=robot for motion, role=voice-device for the
        # mic); key each into its own registry so the mic socket never clobbers the motion socket.
        if role == "robot" and robot_id:
            self._robots[robot_id] = ws
        if role == "voice-device" and robot_id:
            self._voice_devices[robot_id] = ws

    def disconnect(
        self,
        ws: WebSocket,
        role: str,
        robot_id: str | None = None,
    ) -> None:
        self._by_role.get(role, set()).discard(ws)
        if role == "robot" and robot_id and self._robots.get(robot_id) is ws:
            del self._robots[robot_id]
        if role == "voice-device" and robot_id and self._voice_devices.get(robot_id) is ws:
            del self._voice_devices[robot_id]
            # The mic is gone, so no turn can still be running on it. Clearing this here means a
            # crashed device can't leave a robot parked waiting for speech that will never end.
            self._voice_busy.discard(robot_id)
            self._voice_levels.pop(robot_id, None)
            # Don't unbind the table here: the table↔robot binding tracks the robot's *physical*
            # presence (its role=robot lifecycle), not the mic socket. A mic restart shouldn't force
            # a re-arrival — and while the mic is down send_to_voice_device already returns no_device.

    async def broadcast(self, role: str, message: dict) -> None:
        """Send a JSON message to every socket of `role`; drop ones that error out."""
        data = json.dumps(message, default=str, ensure_ascii=False)
        for ws in list(self._by_role.get(role, ())):
            try:
                await ws.send_text(data)
            except Exception:  # broken pipe / closing socket — forget it
                self.disconnect(ws, role)

    async def send_to_robot(self, robot_id: str, message: dict) -> bool:
        """Send a JSON message to one specific robot. Returns False if it isn't connected."""
        ws = self._robots.get(robot_id)
        if ws is None:
            return False
        try:
            await ws.send_text(json.dumps(message, default=str, ensure_ascii=False))
            return True
        except Exception:
            self._robots.pop(robot_id, None)
            return False

    def bind_table_robot(self, table_id: int, robot_id: str) -> None:
        """Record that `robot_id`'s mic now serves `table_id` (the robot just arrived there).

        A robot serves one table at a time and a table is served by one robot, so any stale mapping
        on either side is dropped first — e.g. the robot's previous table, or whoever was at this
        table before. Idempotent.
        """
        for t in [t for t, r in self._table_to_robot.items() if r == robot_id]:
            del self._table_to_robot[t]  # robot moved on from an earlier table
        self._table_to_robot[table_id] = robot_id

    def unbind_robot(self, robot_id: str) -> None:
        """Forget any table this robot was serving (it left, finished, or went offline)."""
        for t in [t for t, r in self._table_to_robot.items() if r == robot_id]:
            del self._table_to_robot[t]

    def table_robot(self, table_id: int) -> str | None:
        """Which robot is currently standing at / serving this table, if any."""
        return self._table_to_robot.get(table_id)

    async def send_to_voice_device(self, table_id: int, message: dict) -> bool:
        """Tell the robot currently serving `table_id` to do something (e.g. start listening).

        Resolves table → robot (bound by the dispatcher on arrival) → that robot's mic socket.
        Returns False if no robot is standing at the table or its mic device isn't connected.
        """
        robot_id = self._table_to_robot.get(table_id)
        if robot_id is None:
            return False
        return await self.send_to_voice_device_by_id(robot_id, message)

    async def send_to_voice_device_by_id(self, robot_id: str, message: dict) -> bool:
        """Same command, addressed to a mic by robot id instead of by table.

        The restaurant always goes through the table (that binding is what makes "table 3 wants to
        talk" meaningful). The voice monitor has no tables at all — it drives ONE device directly,
        so it needs the id path. Kept as the primitive both callers share rather than a second copy
        of the send, so a dead socket is reaped in exactly one place.
        """
        ws = self._voice_devices.get(robot_id)
        if ws is None:
            return False
        try:
            await ws.send_text(json.dumps(message, default=str, ensure_ascii=False))
            return True
        except Exception:
            self._voice_devices.pop(robot_id, None)
            return False

    def voice_device_ids(self) -> list[str]:
        """Ids of every mic currently connected — what the monitor lists as available devices."""
        return sorted(self._voice_devices)

    def set_voice_busy(self, robot_id: str, busy: bool) -> None:
        """Record whether this robot's voice device is mid-conversation-turn."""
        if busy:
            self._voice_busy.add(robot_id)
        else:
            self._voice_busy.discard(robot_id)

    def voice_busy(self, robot_id: str) -> bool:
        """Is this robot still listening / thinking / speaking? False if it has no mic device."""
        return robot_id in self._voice_busy

    def set_voice_levels(self, robot_id: str, levels: dict) -> None:
        """Remember the speaker/mic levels a device just reported."""
        self._voice_levels[robot_id] = levels

    def voice_levels(self, robot_id: str) -> dict:
        """Last known levels for this mic; empty until it has reported any."""
        return self._voice_levels.get(robot_id, {})

    def connected_robot_ids(self) -> set[str]:
        return set(self._robots)

    async def kick_robot(self, robot_id: str) -> None:
        """Force-close a (hung) robot's socket and drop it from the pool immediately."""
        ws = self._robots.pop(robot_id, None)
        if ws is not None:
            try:
                await ws.close()
            except Exception:  # already closing/closed — fine
                pass


manager = ConnectionManager()
