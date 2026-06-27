"""AI Waiter — agent (LLM) HTTP service.

Runs on the central server: **the LLM lives here**. The Jetson does only mic → VAD → Whisper and
TTS (see ``src/edge_voice/main.py``); it POSTs the recognised text to ``POST /chat`` and this
service runs the LangGraph agent, returning the spoken reply (+ stage) for the Jetson to speak.

It also mirrors each turn to the table's ``customer_ui`` through the orchestrator's voice bridge
(``POST /voice/event``) so the web UI shows the live conversation and follows the agent's UI
actions (open the menu / the bill). The agent already *decides* those actions
(``agent/actions.py``); this service is where the *delivery* to the tablet is wired.

Run (on the server, alongside the orchestrator backend) — from the repo root, or just ``make agent``:
    uv run uvicorn src.agent_brain.server:app --host 0.0.0.0 --port 8100
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from src._shared.types import normalise_table_id
from src.agent_brain.agent.graph import AIWaiterGraph
from src.agent_brain.config import settings
from src.agent_brain.services.orchestrator_client import OrchestratorClient

load_dotenv()
log = logging.getLogger(__name__)

# Loaded once at startup (the LLM/graph is expensive to build) and shared across requests.
_agent: AIWaiterGraph | None = None
_orchestrator = OrchestratorClient()


def _warmup() -> None:
    """Pre-load every model into memory so the FIRST real turn isn't slow.

    Ollama loads a model into RAM/VRAM lazily — only on the first request — and (without keep_alive)
    evicts it after 5 idle minutes. The embedding model and faster-whisper are likewise lazy. We pin
    keep_alive=-1 on the ChatOllama clients (see agent/nodes/*), and here fire one tiny inference
    through each distinct LLM + the RAG retriever so everything is resident before a guest speaks.
    Best-effort: a warmup failure (e.g. Ollama not up yet) must not stop the service from starting.
    """
    from langchain_ollama import ChatOllama

    model_ids = {settings.ROUTER_MODEL, settings.WORKER_MODEL, settings.RESPONSE_MODEL}
    for model_id in model_ids:
        try:
            log.info("Warming up LLM %s ...", model_id)
            ChatOllama(
                model=model_id,
                num_ctx=settings.LLM_NUM_CTX,
                keep_alive=settings.llm_keep_alive,
            ).invoke("ok")
        except Exception as e:  # Ollama down / model not pulled — log and carry on.
            log.warning("LLM warmup failed for %s: %s", model_id, e)

    try:
        log.info("Warming up RAG retriever (embedding model) ...")
        from src.agent_brain.agent.tools.search_tool import search

        search.invoke({"query": "khởi động"})
    except Exception as e:
        log.warning("Retriever warmup failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    log.info("Loading AI Waiter agent graph...")
    _agent = AIWaiterGraph()
    log.info("Agent ready. Warming up models...")
    await asyncio.to_thread(_warmup)
    log.info("Warmup complete — models resident.")
    yield


app = FastAPI(title="AI Waiter Agent", version="0.1.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    # The agent layer speaks "T1"-style table refs (graph.chat / main.py / the LLM prompts); only
    # the backend keys tables by INT. We keep the agent convention here and convert to the INT id
    # at the tablet seam via normalise_table_id — matching orchestrator_client.
    table_id: str = "T1"
    text: str


class ChatResponse(BaseModel):
    response: str
    final_stage: str
    action: dict | None = None
    session_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent_loaded": _agent is not None}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Process one recognised utterance: run the agent, mirror it to the tablet, return the reply.

    Sync on purpose — ``AIWaiterGraph.chat`` is a blocking LangGraph invoke; FastAPI runs this in a
    threadpool so concurrent tables don't block the event loop.
    """
    text = req.text.strip()
    table_id = req.table_id
    table_int = normalise_table_id(table_id)  # backend/tablet key tables by INT

    # Show the guest's words on the tablet right away (user bubble + "thinking") — before the LLM,
    # which on a local model can take a couple of seconds.
    _orchestrator.post_voice_event(
        {"type": "voice.heard", "table_id": table_int, "text": text}
    )

    result = _agent.chat(query=text, table_id=table_id)
    response = result["response"]
    action = result.get("action")
    stage = result.get("final_stage", "IDLE")

    # Mirror the spoken reply + any UI action (open menu / bill) to the tablet.
    _orchestrator.post_voice_event(
        {"type": "voice.reply", "table_id": table_int, "text": response, "action": action, "stage": stage}
    )

    return ChatResponse(
        response=response,
        final_stage=stage,
        action=action,
        session_id=result.get("session_id"),
    )
