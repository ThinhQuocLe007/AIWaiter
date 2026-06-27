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
* **Voice devices** (`role=voice-device&robot_id=robo-1`): the mic loop on a robot's Jetson. Keyed
  by the *same* robot id as the robot socket — one physical robot, two sockets (motion vs mic). The
  device is reached by *table*, not id: the dispatcher binds `table → robot` when that robot arrives
  at the table (`bind_table_robot`), so "table 3 wants to talk" resolves to whichever robot is
  currently standing at table 3. This is the dynamic-dispatch model: a robot isn't tied to a table,
  it's tied to one *while serving it*.

The socket *registry* lives in ``connection_manager.py`` (the ``manager`` singleton). This
module owns the ``/ws`` endpoint and the robot-frame dispatcher routing.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .connection_manager import manager

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    role: str = "panel",
    robot_id: str | None = None,
) -> None:
    await manager.connect(websocket, role, robot_id)
    log.info("ws connected role=%s robot_id=%s", role, robot_id)

    # Lazy import to avoid a circular import (dispatcher imports `manager` from this module).
    from ..services import dispatcher

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
        manager.disconnect(websocket, role, robot_id)
        log.info("ws disconnected role=%s robot_id=%s", role, robot_id)
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
