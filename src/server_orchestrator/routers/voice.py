"""Voice bridge — relays the agent's spoken turns + UI actions to the customer tablet.

The LLM agent runs as a *separate* service (`src.agent_brain`, "the LLM on the server"); the
Jetson only does mic → VAD → Whisper and TTS. After each voice turn the agent service POSTs
here so the backend — the one hub every web client already connects to — can fan the turn
out to the table's `customer_ui` over the `role=customer` WebSocket.

This is the *delivery* half of the agent's action seam
(`src/agent_brain/agent/actions.py`): the agent **decides** the UI action (open menu / bill),
this endpoint **delivers** it. The backend stays ignorant of the agent (no `src.agent_brain`
import), keeping the standalone-orchestrator boundary intact — the bridge is plain JSON over HTTP.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from ..realtime.connection_manager import manager

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceEvent(BaseModel):
    """One thing to mirror onto the table's tablet. `type` is the wire event the UI switches on:

    * ``voice.heard`` — what the guest just said (user bubble + "thinking").
    * ``voice.reply`` — the agent's spoken reply, plus any UI action to follow.
    * ``voice.progress`` — processing status update for monitor UI (e.g. "đang xử lý...").
    """

    type: str
    table_id: int
    text: str | None = None
    action: dict | None = None
    stage: str | None = None
    cart: list | None = None
    confirmed: bool | None = None
    status: str | None = None


@router.post("/event")
async def voice_event(ev: VoiceEvent) -> dict:
    """Fan a voice event out to every customer tablet; each filters by its own table_id."""
    await manager.broadcast("customer", ev.model_dump())
    return {"status": "ok"}


class ListenRequest(BaseModel):
    """The tablet's "talk to the AI" button: ask the robot serving this table to capture one utterance.

    The mic lives on the robot's Jetson (a `role=voice-device` WS client), not the browser — so the
    button doesn't record audio, it just signals the device to start listening. The table→robot
    binding is dynamic (the dispatcher sets it when the robot arrives), so this resolves to whichever
    robot is currently at the table. The device then does mic → VAD → STT → POST /chat, and the agent
    mirrors the turn back here via /event.
    """

    table_id: int


@router.post("/listen")
async def voice_listen(req: ListenRequest) -> dict:
    """Forward a "start listening" command to the robot serving this table. The command carries the
    table_id so the (table-agnostic) device tags its /chat turn with the right table. Returns
    no_device (tablet shows the assistant offline) when no robot is at the table or its mic is down.
    """
    ok = await manager.send_to_voice_device(
        req.table_id, {"type": "start_listening", "table_id": req.table_id}
    )
    return {"status": "ok" if ok else "no_device"}


@router.post("/cancel")
async def voice_cancel(req: ListenRequest) -> dict:
    """The tablet's "Hủy" button: abort the in-flight capture on the table's voice device.

    The device disarms its mic / drops the captured utterance so nothing is sent to the LLM.
    If the utterance already reached the agent, the tablet suppresses the reply on its side —
    this endpoint only stops what hasn't been sent yet.
    """
    ok = await manager.send_to_voice_device(
        req.table_id, {"type": "cancel_listening", "table_id": req.table_id}
    )
    return {"status": "ok" if ok else "no_device"}
