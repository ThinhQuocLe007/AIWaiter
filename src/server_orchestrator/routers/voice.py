"""Voice bridge — relays the brain's spoken turns + navigation actions to the operator panel.

The LLM brain runs as a *separate* service (``src.agent_brain``); the Jetson only
does mic → VAD → Whisper and TTS. After each voice turn the brain service POSTs
here so the backend — the one hub every web client already connects to — can fan
the turn out to the warehouse operator panel over the ``role=panel`` WebSocket.

This is the *delivery* half of the brain's action seam: the brain **decides** the
navigation action (a section token), this endpoint **delivers** it to the panel
and (via ``/navigation``) to the AGV. The backend stays ignorant of the brain (no
``src.agent_brain`` import), keeping the standalone-orchestrator boundary intact —
the bridge is plain JSON over HTTP.
"""

from typing import Literal

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import settings
from ..realtime.connection_manager import manager

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceEvent(BaseModel):
    """One thing to mirror onto the operator panel. `type` is the wire event the UI switches on:

    * ``voice.heard`` — what the operator/guest just said (user bubble + "thinking").
    * ``voice.reply`` — the brain's spoken reply, plus any navigation action to follow.
    * ``voice.progress`` — processing status update for monitor UI (e.g. "đang xử lý...").
    """

    type: str
    robot_id: str | None = None
    text: str | None = None
    action: dict | None = None
    stage: str | None = None
    status: str | None = None


@router.post("/event")
async def voice_event(ev: VoiceEvent) -> dict:
    """Fan a voice event out to every operator panel AND every voice monitor.

    `role=monitor` is a second *viewer*, not a second protocol — the same payload, mirrored. It
    matters because the monitor is usually the ONLY thing watching: the demo runs the voice
    pipeline on its own, with no panel open anywhere. Dropping it here is what makes the monitor
    sit at "Sẵn sàng" through a whole turn while the robot happily talks.
    """
    payload = ev.model_dump()
    await manager.broadcast("panel", payload)
    await manager.broadcast("monitor", payload)
    return {"status": "ok"}


class ListenRequest(BaseModel):
    """The panel's "talk to the AI" button: ask the AGV's Jetson (voice device) to capture one
    utterance. The mic lives on the robot's Jetson (a ``role=voice-device`` WS client), not the
    browser — so the button doesn't record audio, it just signals the device to start listening.
    """

    robot_id: str = "robo-1"


@router.post("/listen")
async def voice_listen(req: ListenRequest) -> dict:
    """Forward a "start listening" command to the AGV's voice device."""
    ok = await manager.send_to_voice_device(
        req.robot_id, {"type": "start_listening", "robot_id": req.robot_id}
    )
    return {"status": "ok" if ok else "no_device"}


@router.post("/cancel")
async def voice_cancel(req: ListenRequest) -> dict:
    """The panel's "Hủy"/"Dừng" button: kill the in-flight turn on the voice device."""
    ok = await manager.send_to_voice_device(
        req.robot_id, {"type": "cancel_listening", "robot_id": req.robot_id}
    )
    return {"status": "ok" if ok else "no_device"}


class MuteRequest(BaseModel):
    """The panel's speaker toggle: silence (or re-enable) the AGV's TTS voice."""

    robot_id: str = "robo-1"
    muted: bool


@router.post("/mute")
async def voice_mute(req: MuteRequest) -> dict:
    """Forward the mute state to the AGV's voice device (its Jetson owns the speaker)."""
    ok = await manager.send_to_voice_device(
        req.robot_id, {"type": "set_muted", "muted": req.muted, "robot_id": req.robot_id}
    )
    return {"status": "ok" if ok else "no_device"}


@router.post("/new-chat")
async def voice_new_chat(req: ListenRequest) -> dict:
    """The panel's "cuộc trò chuyện mới" button: wipe the brain's memory for this session.

    The conversation thread lives in the brain service (LangGraph checkpoints), not here — forward
    the reset over plain HTTP (the orchestrator↔brain boundary stays import-free).
    """
    device = await manager.send_to_voice_device(
        req.robot_id, {"type": "cancel_listening", "robot_id": req.robot_id}
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.agent_url.rstrip('/')}/reset",
                json={"robot_id": req.robot_id},
            )
            resp.raise_for_status()
    except httpx.HTTPError:
        return {"status": "agent_unreachable", "device": bool(device)}
    return {"status": "ok", "device": bool(device)}


# ── Màn monitor ────────────────────────────────────────────────────────────────────────────
# Hai endpoint dưới đây CHỈ màn `/monitor` dùng. Panel không cần: nó điều khiển AGV, còn monitor
# điều khiển thẳng một cái mic (chọn thiết bị + chỉnh mức loa/mic của chính máy Jetson đó).


class AudioLevelRequest(BaseModel):
    """Hai mức của monitor: robot nói to cỡ nào, và mic của nó nhạy cỡ nào.

    Khác /mute — /mute là cái chốt trên đường phát TTS của mình. Cái này dịch mức PulseAudio
    THẬT trên Jetson, tức là thứ quyết định cả phòng có nghe rõ robot không và Whisper có tín
    hiệu dùng được không. Chỉ thiết bị mới biết giá trị thật: nó tự chặn trần, đọc lại từ pactl
    rồi đẩy một frame telemetry `levels` về — nên câu trả lời ở đây chỉ là "lệnh đã gửi tới nơi",
    không bao giờ là "mức giờ đang là N".
    """

    robot_id: str = "robo-1"
    target: Literal["speaker", "mic"]
    percent: int = Field(ge=0, le=150)


@router.post("/audio-level")
async def voice_audio_level(req: AudioLevelRequest) -> dict:
    """Chuyển tiếp một thay đổi mức âm xuống Jetson của robot."""
    ok = await manager.send_to_voice_device(
        req.robot_id,
        {"type": "set_audio_level", "target": req.target, "percent": req.percent},
    )
    return {"status": "ok" if ok else "no_device"}


@router.get("/devices")
async def voice_devices() -> dict:
    """Mic nào đang online — ô chọn thiết bị của monitor đọc cái này lúc mở trang.

    Monitor gọi thiết bị theo id, nên thiếu endpoint này thì phải gõ id bằng tay (và sẽ thấy
    "no_device" mà không phân biệt được id sai với Jetson đang tắt). Kèm luôn cờ bận để giao diện
    làm mờ nút ra lệnh trên thiết bị đang giữa lượt.
    """
    return {
        "devices": [
            {
                "robot_id": rid,
                "busy": manager.voice_busy(rid),
                # Mức âm gần nhất mic báo về. Thiết bị đẩy lúc kết nối và sau mỗi lần đổi; lặp lại
                # ở đây chỉ để trang monitor mở sau không phải chờ tới lần đổi kế tiếp mới biết
                # hai cụm Mic/Loa đang ở đâu.
                **manager.voice_levels(rid),
            }
            for rid in manager.voice_device_ids()
        ],
    }
