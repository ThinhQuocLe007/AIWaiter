# AI Waiter — Brain (LLM + RAG + Tools)

The LLM **brain** of the AI Waiter. Runs on the **central server**, NOT on the robot
(post-pivot 2026-06: "não" dồn lên server; Jetson chỉ còn voice + ROS 2/Nav2).
Hosts the LangGraph agent graph, hybrid RAG retrieval, tools, conversation memory,
and the agent HTTP service.

## Role split
- **Brain (this package)** — LLM, RAG, agent → runs on server, sees every guest.
- **Edge voice** — see `../edge_voice/` → runs on Jetson, mic + speaker only.
- **Orchestrator** — see `../server_orchestrator/` → FastAPI backend, the only writer
  to `orchestrator.db`. The brain reaches it over HTTP via `OrchestratorClient`.

## Layout
```
src/agent_brain/
├── server.py                    # FastAPI agent service (POST /chat, port 8100)
├── config/                      # settings (env, hardware, DB, agent)
├── schemas/                     # pydantic models (state, search, order, payment, routing, ...)
├── agent/
│   ├── graph.py                 # AIWaiterGraph (orchestration)
│   ├── state.py                 # AgentState TypedDict
│   ├── actions.py               # UI actions (open_menu, open_payment, ...)
│   ├── memory/checkpointer.py   # SQLite checkpointer (thread_id = session_id)
│   ├── nodes/                   # 10 LangGraph nodes (routers, workers, validators, critic, response, update)
│   ├── tools/                   # 5 LangChain tools (search, sync_cart, confirm_order, request_payment, verify_payment)
│   └── resources/               # static assets (centroids, few_shots, skills, system_prompts)
├── services/
│   ├── orchestrator_client.py   # agent → backend REST client
│   └── retriever/               # hybrid retrieval (BM25 + FAISS + RRF fusion)
└── utils/                       # logger, tracing, prompt/menu utils, search debug
```

## Install

```bash
# from the repo root
uv sync --extra server --extra cu13     # x86 server (use --extra cu12 on older GPU)
```

See [`../../docs/setup-deploy.md`](../../docs/setup-deploy.md) for the per-machine
guide (Server / Jetson / laptop).

## Run

```bash
# LLM HTTP service (port 8100) — alongside the orchestrator backend (port 8000)
uv run uvicorn src.agent_brain.server:app --host 0.0.0.0 --port 8100
# or simply: make agent    (rebuilds the index first, then starts the service)
```

## Features
- **LangGraph agent** — hybrid router (semantic centroid + SLM fallback) → workers
  → deterministic validator → critic → response.
- **Hybrid RAG** — BM25 + FAISS vector + reciprocal rank fusion. The fingerprint
  check fails fast on embedding-model/dim swap.
- **Function calling** — `search` · `sync_cart` · `confirm_order` ·
  `request_payment` · `verify_payment` (each posts to the orchestrator).
- **Session memory** — `thread_id = active session_id`; after payment the next guest
  opens a new session → clean context.
- **UI actions** — `open_menu` / `open_payment` are emitted alongside the reply
  and mirrored to the tablet by the voice bridge (`/voice/event` on the orchestrator).
- **Vietnamese prompts + few-shots** — `agent/resources/{system_prompts,few_shots}/`
  loaded at boot; skills (hospitality / menu grounding / no-service) layered on top.
- **LLM warmup** — every model is pinged at service start so the first real turn
  isn't slow.
