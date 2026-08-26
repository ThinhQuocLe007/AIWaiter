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
        # Robots whose voice device is mid-conversation-turn (listening → LLM → speaking). Only
        # the monitor reads it, through GET /voice/devices; nothing in the dispatch path depends
        # on it, so a device that dies mid-turn costs a stale flag at worst — and `disconnect`
        # below clears even that.
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
            # The mic is gone, so no turn can still be running on it and its levels describe a
            # machine we can no longer reach. Drop both rather than let the monitor keep showing
            # a busy lamp and two steppers for a device that isn't there.
            self._voice_busy.discard(robot_id)
            self._voice_levels.pop(robot_id, None)

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

    # Alias giữ lại tên cũ. Bản nhà hàng có HAI đường tới mic: theo bàn (tablet — cần dispatcher
    # gắn robot vào bàn trước) và theo robot id (monitor — không có bàn nào cả). Kho bỏ hẳn khái
    # niệm bàn nên chỉ còn đường thứ hai; giữ tên `_by_id` để trang monitor khỏi phải sửa, và để
    # đọc code vẫn thấy rõ "địa chỉ ở đây là robot id, không phải bàn".
    async def send_to_voice_device_by_id(self, robot_id: str, message: dict) -> bool:
        return await self.send_to_voice_device(robot_id, message)

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
            with contextlib.suppress(Exception):  # already closing/closed — fine
                await ws.close()


manager = ConnectionManager()
