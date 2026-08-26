"""WebSocket connection manager — tracks live sockets per role + per robot id.

Extracted from ``realtime/ws.py`` so the manager class can be imported in
isolation (e.g. from routers) without pulling in the FastAPI router and
the message-handling helper. The ``ws.py`` module still owns the ``/ws``
endpoint and the robot-frame dispatcher routing; this file owns the
*registry* of live sockets only.
"""

import contextlib
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
        # Voice-device (mic) sockets, indexed by robot id — same id as the robot's motion socket.
        self._voice_devices: dict[str, WebSocket] = {}

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

    async def send_to_voice_device(self, robot_id: str, message: dict) -> bool:
        """Tell a robot's mic device to do something (e.g. start listening).

        Returns False if that robot's voice device isn't connected.
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

    def connected_robot_ids(self) -> set[str]:
        return set(self._robots)

    async def kick_robot(self, robot_id: str) -> None:
        """Force-close a (hung) robot's socket and drop it from the pool immediately."""
        ws = self._robots.pop(robot_id, None)
        if ws is not None:
            with contextlib.suppress(Exception):  # already closing/closed — fine
                await ws.close()


manager = ConnectionManager()
