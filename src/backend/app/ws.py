"""WebSocket hub — one /ws endpoint, fan-out by client `role`.

Clients connect with ?role=<role> (e.g. /ws?role=panel). The server pushes events to all
sockets of a role; for now only the control panel subscribes, to get new orders in realtime
instead of polling. Brain/robot roles will reuse this same hub later.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Tracks live sockets per role and broadcasts JSON events to them."""

    def __init__(self) -> None:
        self._by_role: dict[str, set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, role: str) -> None:
        await ws.accept()
        self._by_role.setdefault(role, set()).add(ws)

    def disconnect(self, ws: WebSocket, role: str) -> None:
        self._by_role.get(role, set()).discard(ws)

    async def broadcast(self, role: str, message: dict) -> None:
        """Send a JSON message to every socket of `role`; drop ones that error out."""
        data = json.dumps(message, default=str, ensure_ascii=False)
        for ws in list(self._by_role.get(role, ())):
            try:
                await ws.send_text(data)
            except Exception:  # broken pipe / closing socket — forget it
                self.disconnect(ws, role)


manager = ConnectionManager()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, role: str = "panel") -> None:
    await manager.connect(websocket, role)
    log.info("ws connected role=%s", role)
    try:
        # We don't expect inbound messages yet; receive to detect disconnect & keep alive.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, role)
        log.info("ws disconnected role=%s", role)
