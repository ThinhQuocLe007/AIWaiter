"""Warehouse brain — agent (LLM) HTTP service (replaces the AI Waiter agent).

Runs on the central server: the LLM lives here. The Jetson edge voice device
POSTs the recognised text to ``POST /chat/stream``; this service runs the
warehouse LangGraph agent (inventory Q&A + navigation token) and streams the
spoken reply back as SSE, and pushes a ``voice.reply`` event to the orchestrator
so the server stays in the loop.

This is the same contract the old AI Waiter ``agent_brain`` exposed
(``/chat/stream`` SSE, ``/reset``, ``/cart``, ``/health``), so the existing
``server_orchestrator`` and ``edge_voice`` keep working unchanged — only the
domain changed from restaurant ordering to warehouse inventory/location.

Run (on the server, alongside the orchestrator backend) — from the repo root:
    uv run uvicorn src.agent_brain.server:app --host 0.0.0.0 --port 8100
"""

import asyncio
import json
import re
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent_brain.config import settings as agent_settings
from src.agent_brain.services.orchestrator_client import OrchestratorClient
from src.agent_brain.utils import logger as log
from src.agent_brain.warehouse.graph import build_graph
from src.agent_brain.warehouse.memory.checkpointer import get_checkpointer

load_dotenv()


# Loaded once at startup (the LLM/graph is expensive to build) and shared across requests.
_graph = None
_orchestrator = OrchestratorClient()


def _check_router() -> None:
    """Fail startup if the intent router was never trained, instead of failing mid-conversation.

    The trained weights are a runtime artifact and are not in git, so a fresh clone has none until
    `make train-router` runs. Without this check the miss surfaces on the first utterance that
    reaches the classifier — and only *some* utterances do, because `route()` short-circuits
    control phrases, named places and section mentions first. The result is an agent that answers
    two questions, then throws a 500 on the third, which reads as an intermittent fault rather
    than a missing file. Better to refuse to start and say which command fixes it.
    """
    from src.agent_brain.warehouse.router.model import MLPRouter, RouterNotTrained

    try:
        MLPRouter.load()
    except RouterNotTrained as e:
        raise RuntimeError(
            f"{e}\n"
            "Chạy trên chính máy chạy `make agent`, sau khi .env đã đặt EMBED_MODEL."
        ) from e


def _warmup_llm() -> None:
    """Pin the Ollama model in VRAM for the life of the service.

    Ollama evicts after 5 min idle by default, so the first `chat`-intent question of a demo
    would stall ~10-30s reloading 12GB from disk. `keep_alive: -1` = never evict. This goes to
    Ollama's NATIVE /api/generate, not the OpenAI-compatible /v1 endpoint the client uses —
    /v1 has no keep_alive field. An empty prompt loads the model and returns immediately.
    """
    import httpx

    from src.agent_brain.warehouse.paths import settings as wh_settings

    root = wh_settings.llm_base_url.rstrip("/").removesuffix("/v1")
    log.info("Warming up LLM %s (keep_alive=-1) ...", wh_settings.llm_model)
    r = httpx.post(
        f"{root}/api/generate",
        json={"model": wh_settings.llm_model, "keep_alive": -1},
        timeout=180.0,  # cold load of a 14b off a slow disk
    )
    r.raise_for_status()


def _warmup() -> None:
    """Pre-load models so the FIRST real turn isn't slow (best-effort)."""
    try:
        log.info("Warming up RAG retriever (embedding model) ...")
        from src.agent_brain.warehouse.tools.live_tools import get_index

        get_index()
    except Exception as e:  # noqa: BLE001 — startup time; RAG may fail for any reason
        log.warning("Retriever warmup failed: %s", e)
    try:
        _warmup_llm()
    except Exception as e:  # noqa: BLE001 — Ollama down/model not pulled: deterministic paths still work
        log.warning("LLM warmup failed (chat intent sẽ chậm lượt đầu): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    _check_router()
    log.info("Loading warehouse brain graph...")
    _graph = build_graph(get_checkpointer())
    log.info("Warehouse brain ready. Warming up models...")
    await asyncio.to_thread(_warmup)
    log.info("Warmup complete — models resident.")
    yield


app = FastAPI(title="Warehouse Brain Agent", version="0.1.0", lifespan=lifespan)


class SessionRequest(BaseModel):
    # One robot = one conversation thread. There are no tables in a warehouse; the robot id the
    # device already knows is the only key, so nothing has to invent or carry a second one.
    robot_id: str = "robo-1"


class ChatRequest(SessionRequest):
    text: str


class ChatResponse(BaseModel):
    response: str
    final_stage: str
    action: dict | None = None
    session_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent_loaded": _graph is not None}


@app.post("/reset")
def reset_conversation(req: SessionRequest) -> dict:
    """""Cuộc trò chuyện mới": drop this robot's conversation thread."""
    thread_id = req.robot_id
    try:
        _graph.checkpointer.delete_thread(thread_id)
    except Exception as e:  # noqa: BLE001 — missing thread is fine
        log.warning("reset thread %s: %s", thread_id, e)
    return {"status": "ok", "thread_id": thread_id}


class CartSyncRequest(SessionRequest):
    items: list = []


@app.post("/cart")
def sync_cart(req: CartSyncRequest) -> dict:
    """Warehouse has no cart — silent no-op kept so the orchestrator's /voice/cart keeps working."""
    return {"status": "ok", "thread_id": req.robot_id}


def _split_sentences(text: str) -> list[str]:
    """Split a Vietnamese reply into speakable chunks for TTS streaming."""
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _run_turn(text: str, robot_id: str) -> dict:
    """Run the warehouse graph for one utterance; returns the final state dict."""
    config = {"configurable": {"thread_id": robot_id}}
    inputs = {"user_text": text, "session_id": robot_id}
    result = _graph.invoke(inputs, config)
    return result


def _dispatch_navigation_if_needed(action: dict | None) -> None:
    """If the brain produced a navigate action, ask the orchestrator to send the AGV there."""
    if not action or action.get("type") != "navigate":
        return
    position = action.get("position") or {}
    token = position.get("token")
    if token:
        log.info("forwarding navigate token %r to orchestrator", token)
        _orchestrator.dispatch_navigation(token, position.get("section"))


def _emit_voice_reply(robot_id: str, reply: str, action, intent: str) -> None:
    """Mirror the turn's reply (and any navigation action) to the operator panel."""
    _orchestrator.post_voice_event(
        {
            "type": "voice.reply",
            "robot_id": robot_id,
            "text": reply,
            "action": action,
            "stage": intent,
        }
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Non-streaming variant kept for parity / debugging. The running system uses /chat/stream."""
    text = req.text.strip()
    robot_id = req.robot_id

    _orchestrator.post_voice_event(
        {"type": "voice.heard", "robot_id": robot_id, "text": text}
    )

    result = _run_turn(text, robot_id)
    reply = result.get("reply", "")
    action = result.get("action")
    intent = result.get("intent") or "chat"
    session_id = robot_id

    _emit_voice_reply(robot_id, reply, action, intent)
    _dispatch_navigation_if_needed(action)

    return ChatResponse(response=reply, final_stage=intent, action=action, session_id=session_id)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Sentence-level SSE streaming variant of POST /chat (matches the AI Waiter edge contract).

    Emits ``progress`` → ``sentence``* → ``done`` events. ``sentence`` chunks feed the edge TTS;
    ``done`` carries the structured ``action`` (e.g. a navigate token) + ``stage`` + ``session_id``.
    """

    def generate():
        robot_id = req.robot_id
        text = req.text.strip()

        _orchestrator.post_voice_event(
            {"type": "voice.heard", "robot_id": robot_id, "text": text}
        )
        yield f"data: {json.dumps({'event': 'progress', 'text': 'processing'})}\n\n"
        _orchestrator.post_voice_event(
            {"type": "voice.progress", "robot_id": robot_id, "status": "đang xử lý..."}
        )

        try:
            result = _run_turn(text, robot_id)
        except Exception as e:  # noqa: BLE001 — never break the voice loop on a bad turn
            log.exception("warehouse turn failed: %s", e)
            result = {
                "reply": "Xin lỗi, tôi gặp lỗi khi xử lý yêu cầu.",
                "intent": "chat",
                "action": None,
            }

        reply = result.get("reply", "")
        action = result.get("action")
        intent = result.get("intent") or "chat"
        session_id = robot_id

        _emit_voice_reply(robot_id, reply, action, intent)
        _dispatch_navigation_if_needed(action)

        for sentence in _split_sentences(reply):
            yield f"data: {json.dumps({'event': 'sentence', 'text': sentence})}\n\n"

        done_data = json.dumps(
            {"event": "done", "action": action, "stage": intent, "session_id": session_id}
        )
        yield f"data: {done_data}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _port() -> int:
    try:
        return int(urlparse(agent_settings.AGENT_URL).port)
    except Exception:  # noqa: BLE001
        return 8100


def main() -> None:
    import uvicorn

    uvicorn.run("src.agent_brain.server:app", host="0.0.0.0", port=_port())


if __name__ == "__main__":
    main()
