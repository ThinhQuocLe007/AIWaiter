"""WebSocket hub — one /ws endpoint, fan-out by client `role`.

Two kinds of clients share this hub:

* **Viewers** (e.g. `role=panel`, `role=customer`, `role=monitor`): anonymous, read-only. The server
  `broadcast()`s events to every socket of the role; inbound messages are ignored. The kitchen
  panel uses this to get new orders/tasks in realtime instead of polling; the customer tablet
  uses `role=customer` to mirror the voice conversation + follow the agent's UI actions (see
  `routers/voice.py`). `role=monitor` is the voice monitor — the demo screen: it gets the same
  voice events *plus* the device's own stage telemetry, which no other client cares about.
* **Robots** (`role=robot&robot_id=robo-1`): identified and two-way. The dispatcher must reach
  one *specific* robot (`send_to_robot`), and the robot reports back (`task_accepted`, `arrived`,
  `task_done`, `heartbeat`) which the dispatcher acts on. So robot sockets are tracked by id and
  their inbound frames are parsed and routed, not dropped.
* **Voice devices** (`role=voice-device&robot_id=robo-1`): the mic loop on an AGV's Jetson. Keyed
  by the *same* robot id as the robot socket — one physical AGV, two sockets (motion vs mic). The
  device is reached by *robot id* (the operator panel names the AGV it wants to talk), not by table.

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
            # Viewers (panel) send nothing we act on. Robots drive the dispatcher; voice devices
            # narrate their own pipeline for the monitor.
            if role == "robot" and robot_id:
                await _handle_robot_message(dispatcher, robot_id, raw)
            elif role == "voice-device" and robot_id:
                await _handle_voice_device_message(robot_id, raw)
    except WebSocketDisconnect:
        manager.disconnect(websocket, role, robot_id)
        log.info("ws disconnected role=%s robot_id=%s", role, robot_id)
        if role == "robot" and robot_id:
            await dispatcher.on_robot_disconnect(robot_id)
        if role == "voice-device" and robot_id:
            # The mic died mid-turn: clear the busy lamp so the monitor doesn't sit there showing
            # a turn that can never finish.
            manager.set_voice_busy(robot_id, False)


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
    elif mtype == "at_dock":
        await dispatcher.on_at_dock(robot_id)
    else:
        log.warning("unknown robot message type=%r from %s", mtype, robot_id)


async def _handle_voice_device_message(robot_id: str, raw: str) -> None:
    """Parse one inbound voice-device frame.

    Two kinds arrive, and both exist only so the monitor has something to show:

    * ``voice_turn {active}`` — a turn (listen → LLM → speak) started or finished, which is what
      GET /voice/devices reports as `busy`.
    * ``telemetry {stage, ...}`` — the mic narrating its own pipeline (armed → speech → STT → TTS).
      It is forwarded to ``role=monitor`` viewers and dropped on the floor when nobody is watching.
      Kept on this existing socket rather than a new HTTP endpoint so the device needs no second
      connection, and so a stage lands in order with the turn it belongs to.
    """
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("bad voice-device frame from %s: %r", robot_id, raw[:200])
        return
    mtype = msg.get("type")
    if mtype == "voice_turn":
        manager.set_voice_busy(robot_id, bool(msg.get("active")))
    elif mtype == "telemetry":
        # One stage is also worth remembering, not just relaying: `levels` is state (where the
        # speaker/mic sliders sit), while every other stage is an event that only means anything
        # at the instant it arrives. Cache it so a monitor opened later starts with real values.
        if msg.get("stage") == "levels":
            manager.set_voice_levels(
                robot_id,
                {k: msg.get(k) for k in ("speaker", "mic", "can_set")},
            )
        # Stamp the sender server-side: the monitor must not have to trust (or the device bother
        # sending) an id that the socket already establishes.
        await manager.broadcast("monitor", {**msg, "type": "voice.device", "robot_id": robot_id})
    else:
        log.warning("unknown voice-device message type=%r from %s", mtype, robot_id)
