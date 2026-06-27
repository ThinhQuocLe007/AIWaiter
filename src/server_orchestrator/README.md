# AI Waiter — Server Orchestrator (FastAPI)

The **orchestrator backend** — the central FastAPI app that owns the business
ledger (`orchestrator.db`), routes every web client (kiosk, panel, customer
tablet) and the robot WS hub, and is the **single writer** to the database. The
LLM brain (`src/agent_brain/`) and the edge voice device (`src/edge_voice/`)
talk to it over HTTP / WebSocket only — no direct DB access.

## Role split
- **Orchestrator (this package)** — the truth. Owns state, the dispatcher, the
  WS hub, every REST endpoint. Runs on the central server.
- **Brain** — see `../agent_brain/` → LLM, RAG, agent. Runs on the same server,
  talks to the orchestrator via `OrchestratorClient` (HTTP).
- **Edge voice** — see `../edge_voice/` → mic + speaker. Runs on the Jetson,
  talks to the orchestrator via WS.

## Layout

```
src/server_orchestrator/
├── main.py                        # FastAPI app, lifespan, CORS, mount routers
├── config.py                      # settings (env prefix ORCH_)
├── data/                          # persistence
│   ├── db.py                      # sqlite3 schema + connection
│   └── seed.py                    # TODO: seed extraction from main.py lifespan
├── realtime/                      # WebSocket hub
│   ├── connection_manager.py      # manager singleton (live sockets by role + robot_id)
│   └── ws.py                      # /ws endpoint + robot-frame dispatcher routing
├── routers/                       # REST endpoints (one file per resource)
│   ├── admin.py                   # POST /admin/reset
│   ├── layout.py                  # GET /layout + /map/image.png (SLAM map)
│   ├── menu.py                    # GET /menu
│   ├── orders.py                  # POST /orders, PATCH /orders/{id}
│   ├── payments.py                # POST /payments, /payments/verify
│   ├── robots.py                  # GET /robots (DB snapshot + live RAM overlay)
│   ├── tables.py                  # /seatings, /tables, /tables/{id}/session
│   ├── tasks.py                   # GET /tasks, POST /tables/{id}/call
│   └── voice.py                   # /voice/event, /voice/listen (the agent bridge)
├── schemas/                       # pydantic REST contracts
│   └── __init__.py                # re-exports all models (TableOut, OrderOut, ...)
└── services/                      # business logic
    ├── dispatcher.py              # task dispatch + heartbeat watchdog
    ├── fleet.py                   # live robot telemetry (RAM, latest-wins)
    ├── menu_loader.py             # load_menu() + seed_dishes/robots/tables
    └── sessions.py                # session helpers (open/close, gộp total)
```

## Install

```bash
# from the repo root
uv sync --extra server --extra cu13     # x86 server (use --extra cu12 on older GPU)
```

See [`../../docs/setup-deploy.md`](../../docs/setup-deploy.md) for the
per-machine guide (Server / Jetson / laptop).

## Run

```bash
# from the repo root
uv run uvicorn src.server_orchestrator.main:app --reload --host 0.0.0.0 --port 8000
# or: make backend
```

## Features
- **Single FastAPI app, single writer** — `orchestrator.db` is the only
  durable business ledger. The LLM brain reaches it over HTTP via
  `OrchestratorClient`; the voice device reaches it over WS.
- **Session-centric ledger** — a *session* = one party's whole visit
  (seating → orders → one gộp bill → leave). Orders and the single payment
  hang off the session.
- **Three data stores, by data nature**:
  - `orchestrator.db` (SQLite) — durable business records (the ledger).
  - `checkpoints.db` (SQLite, LangGraph) — conversation memory, keyed by
    session id.
  - **RAM** (`services/fleet.py`) — live robot telemetry (pose/battery),
    high-frequency & ephemeral, kept out of the DB so heartbeats never
    contend with order/payment writes.
- **Robot dispatch** — `services/dispatcher.py` turns business events
  (seating, order `XONG`, call button) into tasks; picks the nearest
  idle+online robot; tracks `task_accepted / arrived / task_done`;
  broadcasts to the kitchen panel over WS.
- **WebSocket hub** — `realtime/connection_manager.py` tracks live sockets
  by role (`panel` / `robot` / `customer` / `voice-device`); `realtime/ws.py`
  exposes `/ws` and routes robot frames to the dispatcher.
- **Voice bridge** — `routers/voice.py` relays each agent turn
  (`voice.heard` / `voice.reply` + UI action) to the customer tablet via
  the `role=customer` WS broadcast; `voice.listen` forwards the tablet's
  "talk to AI" button to the robot's voice device.
- **Live minimap data** — `routers/layout.py` serves the SLAM `.pgm` map
  (converted to PNG) plus the table waypoints the panel's minimap needs.
- **Admin reset** — `POST /admin/reset` (also `make reset`) wipes live
  demo data and re-seeds.
- **Mock seeders** — tables, robots, dishes seeded on first boot.
