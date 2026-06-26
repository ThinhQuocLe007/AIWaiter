"""Voice bridge — relays the agent's spoken turns + UI actions to the customer tablet.

The LLM agent runs as a *separate* service (`ai_waiter_core`, "the LLM on the server"); the Jetson
only does mic → VAD → Whisper and TTS. After each voice turn the agent service POSTs here so the
backend — the one hub every web client already connects to — can fan the turn out to the table's
`customer_ui` over the `role=customer` WebSocket.

This is the *delivery* half of the agent's action seam
(`ai_waiter_core/.../agent/actions.py`): the agent **decides** the UI action (open menu / bill),
this endpoint **delivers** it. The backend stays ignorant of the agent (no `ai_waiter_core`
import), keeping the standalone-orchestrator boundary intact — the bridge is plain JSON over HTTP.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from ..ws import manager

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceEvent(BaseModel):
    """One thing to mirror onto the table's tablet. `type` is the wire event the UI switches on:

    * ``voice.heard`` — what the guest just said (user bubble + "thinking").
    * ``voice.reply`` — the agent's spoken reply, plus any UI action to follow.
    """

    type: str
    table_id: int
    text: str | None = None
    # {"type": "ui", "action": "open_menu" | "open_payment"} or None when nothing should move.
    action: dict | None = None
    stage: str | None = None


@router.post("/event")
async def voice_event(ev: VoiceEvent) -> dict:
    """Fan a voice event out to every customer tablet; each filters by its own table_id."""
    await manager.broadcast("customer", ev.model_dump())
    return {"status": "ok"}


class ListenRequest(BaseModel):
    """The tablet's "talk to the AI" button: ask this table's voice device to capture one utterance.

    The mic lives on the table's Jetson/laptop (a `role=voice-device` WS client), not the browser —
    so the button doesn't record audio, it just signals the device to start listening. The device
    then does mic → VAD → STT → POST /chat, and the agent mirrors the turn back here via /event.
    """

    table_id: int


@router.post("/listen")
async def voice_listen(req: ListenRequest) -> dict:
    """Forward a "start listening" command to the table's voice device. Returns no_device (and the
    tablet shows the assistant is offline) when no microphone is connected for that table."""
    ok = await manager.send_to_voice_device(req.table_id, {"type": "start_listening"})
    return {"status": "ok" if ok else "no_device"}
