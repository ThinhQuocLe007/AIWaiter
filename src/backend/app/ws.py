"""WebSocket hub — one /ws endpoint, fan-out by client `role`.

Two kinds of clients share this hub:

* **Viewers** (e.g. `role=panel`, `role=customer`): anonymous, read-only. The server
  `broadcast()`s events to every socket of the role; inbound messages are ignored. The kitchen
  panel uses this to get new orders/tasks in realtime instead of polling; the customer tablet
  uses `role=customer` to mirror the voice conversation + follow the agent's UI actions (see
  `routers/voice.py`).
* **Robots** (`role=robot&robot_id=robo-1`): identified and two-way. The dispatcher must reach
  one *specific* robot (`send_to_robot`), and the robot reports back (`task_accepted`, `arrived`,
  `task_done`, `heartbeat`) which the dispatcher acts on. So robot sockets are tracked by id and
  their inbound frames are parsed and routed, not dropped.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Tracks live sockets per role + per robot id, and sends JSON events to them."""

    def __init__(self) -> None:
        self._by_role: dict[str, set[WebSocket]] = {}
        # Robot sockets are also indexed by id so the dispatcher can target one robot.
        self._robots: dict[str, WebSocket] = {}
        # Voice-device sockets (the mic loop on a table's Jetson/laptop) are indexed by table id so
        # the "start listening" command from that table's tablet reaches the right microphone.
        self._voice_devices: dict[int, WebSocket] = {}

    async def connect(
        self,
        ws: WebSocket,
        role: str,
        robot_id: str | None = None,
        table_id: int | None = None,
    ) -> None:
        await ws.accept()
        self._by_role.setdefault(role, set()).add(ws)
        if robot_id:
            self._robots[robot_id] = ws
        if role == "voice-device" and table_id is not None:
            self._voice_devices[table_id] = ws

    def disconnect(
        self,
        ws: WebSocket,
        role: str,
        robot_id: str | None = None,
        table_id: int | None = None,
    ) -> None:
        self._by_role.get(role, set()).discard(ws)
        if robot_id and self._robots.get(robot_id) is ws:
            del self._robots[robot_id]
        if table_id is not None and self._voice_devices.get(table_id) is ws:
            del self._voice_devices[table_id]

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

    async def send_to_voice_device(self, table_id: int, message: dict) -> bool:
        """Tell one table's voice device to do something (e.g. start listening). Returns False if
        no device is connected for that table."""
        ws = self._voice_devices.get(table_id)
        if ws is None:
            return False
        try:
            await ws.send_text(json.dumps(message, default=str, ensure_ascii=False))
            return True
        except Exception:
            self._voice_devices.pop(table_id, None)
            return False

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


@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    role: str = "panel",
    robot_id: str | None = None,
    table_id: int | None = None,
) -> None:
    await manager.connect(websocket, role, robot_id, table_id)
    log.info("ws connected role=%s robot_id=%s table_id=%s", role, robot_id, table_id)

    # Lazy import to avoid a circular import (dispatcher imports `manager` from this module).
    from . import dispatcher

    if role == "robot" and robot_id:
        await dispatcher.on_robot_connect(robot_id)
    try:
        while True:
            raw = await websocket.receive_text()
            # Viewers (panel) + voice devices don't send anything we act on here; robots drive the
            # dispatcher. (The voice device only receives "start_listening" and POSTs to the agent.)
            if role == "robot" and robot_id:
                await _handle_robot_message(dispatcher, robot_id, raw)
    except WebSocketDisconnect:
        manager.disconnect(websocket, role, robot_id, table_id)
        log.info("ws disconnected role=%s robot_id=%s table_id=%s", role, robot_id, table_id)
        if role == "robot" and robot_id:
            await dispatcher.on_robot_disconnect(robot_id)


async def _handle_robot_message(dispatcher, robot_id: str, raw: str) -> None:
    """Parse one inbound robot frame and route it to the dispatcher by `type`."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("bad robot frame from %s: %r", robot_id, raw[:200])
        return
    mtype = msg.get("type")
    if mtype == "heartbeat":
        await dispatcher.on_heartbeat(robot_id, msg)
    elif mtype == "task_accepted":
        await dispatcher.on_accepted(robot_id, msg.get("task_id"))
    elif mtype == "arrived":
        await dispatcher.on_arrived(robot_id, msg.get("task_id"))
    elif mtype == "task_done":
        await dispatcher.on_done(robot_id, msg.get("task_id"))
    else:
        log.warning("unknown robot message type=%r from %s", mtype, robot_id)
