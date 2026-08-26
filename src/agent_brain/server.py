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

from src._shared.types import normalise_table_id
from src.agent_brain.config import settings as agent_settings
from src.agent_brain.services.orchestrator_client import OrchestratorClient
from src.agent_brain.utils import logger as log
from src.agent_brain.warehouse.graph import build_graph
from src.agent_brain.warehouse.memory.checkpointer import get_checkpointer

load_dotenv()


# Loaded once at startup (the LLM/graph is expensive to build) and shared across requests.
_graph = None
_orchestrator = OrchestratorClient()


def _warmup() -> None:
    """Pre-load models so the FIRST real turn isn't slow (best-effort)."""
    try:
        log.info("Warming up RAG retriever (embedding model) ...")
        from src.agent_brain.warehouse.tools.live_tools import get_index

        get_index()
    except Exception as e:  # noqa: BLE001 — startup time; RAG may fail for any reason
        log.warning("Retriever warmup failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    log.info("Loading warehouse brain graph...")
    _graph = build_graph(get_checkpointer())
    log.info("Warehouse brain ready. Warming up models...")
    await asyncio.to_thread(_warmup)
    log.info("Warmup complete — models resident.")
    yield


app = FastAPI(title="Warehouse Brain Agent", version="0.1.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    # The edge voice device speaks "T1"-style table refs; the orchestrator keys tables by INT.
    table_id: str = "T1"
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
def reset_conversation(req: ChatRequest) -> dict:
    """""Cuộc trò chuyện mới": drop the table's conversation thread."""
    thread_id = req.table_id
    try:
        _graph.checkpointer.delete_thread(thread_id)
    except Exception as e:  # noqa: BLE001 — missing thread is fine
        log.warning("reset thread %s: %s", thread_id, e)
    return {"status": "ok", "thread_id": thread_id}


class CartSyncRequest(BaseModel):
    table_id: str = "T1"
    items: list = []


@app.post("/cart")
def sync_cart(req: CartSyncRequest) -> dict:
    """Warehouse has no cart — silent no-op kept so the orchestrator's /voice/cart keeps working."""
    return {"status": "ok", "thread_id": req.table_id}


def _split_sentences(text: str) -> list[str]:
    """Split a Vietnamese reply into speakable chunks for TTS streaming."""
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _run_turn(text: str, table_id: str) -> dict:
    """Run the warehouse graph for one utterance; returns the final state dict."""
    config = {"configurable": {"thread_id": table_id}}
    inputs = {"user_text": text, "session_id": table_id}
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


def _emit_voice_reply(table_int: int, reply: str, action, intent: str) -> None:
    """Mirror the turn's reply (and any navigation action) to the operator panel."""
    _orchestrator.post_voice_event(
        {
            "type": "voice.reply",
            "table_id": table_int,
            "text": reply,
            "action": action,
            "stage": intent,
        }
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Non-streaming variant kept for parity / debugging. The running system uses /chat/stream."""
    text = req.text.strip()
    table_id = req.table_id
    table_int = normalise_table_id(table_id)

    _orchestrator.post_voice_event(
        {"type": "voice.heard", "table_id": table_int, "text": text}
    )

    result = _run_turn(text, table_id)
    reply = result.get("reply", "")
    action = result.get("action")
    intent = result.get("intent") or "chat"
    session_id = table_id

    _emit_voice_reply(table_int, reply, action, intent)
    _dispatch_navigation_if_needed(action)

    return ChatResponse(response=reply, final_stage=intent, action=action, session_id=session_id)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Sentence-level SSE streaming variant of POST /chat (matches the AI Waiter edge contract).

    Emits ``progress`` → ``sentence``* → ``done`` events. ``sentence`` chunks feed the edge TTS;
    ``done`` carries the structured ``action`` (e.g. a navigate token) + ``stage`` + ``session_id``.
    """

    def generate():
        table_id = req.table_id
        table_int = normalise_table_id(table_id)
        text = req.text.strip()

        _orchestrator.post_voice_event(
            {"type": "voice.heard", "table_id": table_int, "text": text}
        )
        yield f"data: {json.dumps({'event': 'progress', 'text': 'processing'})}\n\n"
        _orchestrator.post_voice_event(
            {"type": "voice.progress", "table_id": table_int, "status": "đang xử lý..."}
        )

        try:
            result = _run_turn(text, table_id)
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
        session_id = table_id

        _emit_voice_reply(table_int, reply, action, intent)
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
