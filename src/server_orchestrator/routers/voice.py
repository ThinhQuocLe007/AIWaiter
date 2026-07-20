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

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from ..config import settings
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
    # True only on turns where the agent actually changed the cart — the tablet mirrors `cart`
    # into its draft only then, so a draft the guest edited by hand survives unrelated turns.
    cart_touched: bool | None = None
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
    """The tablet's "Hủy"/"Dừng" button: kill the whole in-flight turn on the table's voice device.

    The device disarms its mic / drops the captured utterance, stops consuming the agent's reply
    stream, and cuts TTS playback mid-sentence. If the utterance already reached the agent, the
    LLM may still finish server-side — the tablet suppresses that reply on its side.
    """
    ok = await manager.send_to_voice_device(
        req.table_id, {"type": "cancel_listening", "table_id": req.table_id}
    )
    return {"status": "ok" if ok else "no_device"}


class MuteRequest(BaseModel):
    """The tablet's speaker toggle: silence (or re-enable) the robot's TTS voice for this table.

    Muting also cuts the sentence currently playing. The conversation itself keeps flowing —
    the guest still sees the agent's replies as text on the tablet.
    """

    table_id: int
    muted: bool


@router.post("/mute")
async def voice_mute(req: MuteRequest) -> dict:
    """Forward the mute state to the robot serving this table (its Jetson owns the speaker)."""
    ok = await manager.send_to_voice_device(
        req.table_id, {"type": "set_muted", "muted": req.muted, "table_id": req.table_id}
    )
    return {"status": "ok" if ok else "no_device"}


class CartSyncItem(BaseModel):
    name: str
    quantity: int
    note: str | None = None


class CartSyncRequest(BaseModel):
    """The tablet's cart draft, pushed after the guest edited it by hand (+/− on the screen)."""

    table_id: int
    items: list[CartSyncItem] = []


@router.post("/cart")
async def voice_cart_sync(req: CartSyncRequest) -> dict:
    """Forward the tablet's cart draft to the agent so both sides hold ONE cart.

    Mirroring used to run agent → tablet only, so a manual +/− never reached the agent: the next
    voice turn broadcast the agent's stale cart back over it, and confirm_order would have sent
    those stale quantities to the kitchen. The cart lives in the agent service (LangGraph
    checkpoints), not here — same plain-HTTP hop as /voice/new-chat, no src.agent_brain import.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.agent_url.rstrip('/')}/cart",
                json={
                    "table_id": f"T{req.table_id}",
                    "items": [i.model_dump() for i in req.items],
                },
            )
            resp.raise_for_status()
    except httpx.HTTPError:
        return {"status": "agent_unreachable"}
    return {"status": "ok"}


@router.post("/new-chat")
async def voice_new_chat(req: ListenRequest) -> dict:
    """The tablet's "cuộc trò chuyện mới" button: wipe the agent's memory for this table's visit.

    The conversation thread lives in the agent service (LangGraph checkpoints), not here — forward
    the reset over plain HTTP (the orchestrator↔agent boundary stays import-free). Also cancel
    whatever the robot is currently saying/capturing so the old conversation stops immediately.
    """
    device = await manager.send_to_voice_device(
        req.table_id, {"type": "cancel_listening", "table_id": req.table_id}
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.agent_url.rstrip('/')}/reset",
                json={"table_id": f"T{req.table_id}"},
            )
            resp.raise_for_status()
    except httpx.HTTPError:
        return {"status": "agent_unreachable", "device": False}
    # The memory reset is what "new chat" MEANS, so it's ok even with no robot at the table — but
    # report the device separately. Without it the robot keeps talking through the old turn while
    # the tablet claims a fresh conversation started, which reads as "the button does nothing".
    return {"status": "ok", "device": device}
