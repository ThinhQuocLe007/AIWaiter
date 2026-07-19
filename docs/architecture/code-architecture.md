# AI Waiter — Architecture & Data Flow (code-level overview)

> Reviewer's guide to **how the system is wired and how data flows**, matching the code as of
> 2026-06-26 (after the ledger unification). For the broader product/design doc see
> [system-design.md](system-design.md); **this file is the current, code-accurate
> overview** of the backend + agent + data stores.

## TL;DR

- **One backend is the single writer.** `orchestrator.db` is the business ledger. The LLM agent,
  the kiosk, the kitchen panel and the customer tablet **all go through the FastAPI REST API** — no
  component writes the DB directly except the backend itself.
- **Session-centric ledger.** A *session* = one party's whole visit (seating → orders → one gộp
  bill → leave). Orders and the single payment hang off the session.
- **Three data stores, by data nature** (the key design decision):
  - `orchestrator.db` (SQLite) — durable business records (the ledger).
  - `checkpoints.db` (SQLite, LangGraph) — conversation memory, **keyed by session id**.
  - **RAM** (`fleet.py`) — live robot telemetry (pose/battery), high-frequency & ephemeral, kept
    out of the DB so heartbeats never contend with order/payment writes.
- **Agent ↔ backend = HTTP seam.** Tools (`confirm_order` / `request_payment` / `verify_payment`)
  call REST endpoints via `OrchestratorClient`.
- **Robots ↔ backend = WebSocket.** Task assignment + heartbeats over `/ws`.

---

## 1. Component map

```mermaid
flowchart TB
    subgraph ROBOTS["Robots (Jetson — body, one per table area)"]
        STT["STT / VAD / TTS + tablet UI"]
        NAV["ROS2 / Nav2 (motion)"]
    end

    subgraph SERVER["Central Server"]
        subgraph AGENT["LLM Agent (LangGraph, stateless, shared)"]
            GRAPH["graph.py — router → workers → tools"]
            CKPT[("checkpoints.db<br/>thread_id = session_id")]
        end
        subgraph BE["Backend — FastAPI (the ONLY writer)"]
            API["REST routers + WS hub"]
            DISP["dispatcher.py (tasks → robots)"]
            FLEET["fleet.py — live pose/battery (RAM)"]
            DB[("orchestrator.db<br/>tables · sessions · orders<br/>order_items · payments · tasks · robots · dishes")]
        end
    end

    KIOSK["Kiosk (check-in)"] -->|"REST"| API
    PANEL["Kitchen panel"] -->|"REST + WS(role=panel)"| API
    TABLET["customer_ui (tablet)"] -->|"REST"| API

    STT -->|"text + table_id"| GRAPH
    GRAPH <--> CKPT
    GRAPH -->|"HTTP seam: confirm_order / request_payment / verify_payment"| API
    GRAPH -.->|"resolve active session (GET /tables/id/session)"| API
    NAV <-->|"WS(role=robot): task.assign / heartbeat"| API

    API <--> DB
    DISP --> DB
    DISP <-->|"heartbeat"| FLEET
    API -->|"GET /robots overlays live"| FLEET

    style DB fill:#e0f0ff
    style CKPT fill:#ede7ff
    style FLEET fill:#fff0c0
    style API fill:#e8ffe8
```

**Who writes what:** only the backend writes `orchestrator.db`. The agent reaches it *through* the
backend (REST). Robot telemetry lands in RAM (`fleet.py`); the DB gets only an occasional snapshot.

---

## 2. Data model — `orchestrator.db`

Defined in [src/server_orchestrator/data/db.py](../src/server_orchestrator/data/db.py) (plain SQLite, no ORM).

```mermaid
erDiagram
    TABLES ||--o{ SESSIONS : "many visits over time"
    SESSIONS ||--o{ ORDERS : "one session, many orders"
    ORDERS ||--o{ ORDER_ITEMS : ""
    SESSIONS ||--o| PAYMENTS : "ONE gộp payment / session"
    TABLES ||--o{ TASKS : "robot jobs"
    ROBOTS ||--o{ TASKS : "assigned to"

    TABLES {
        int id PK
        string status "TRONG / DANG_PHUC_VU / DA_THANH_TOAN"
        int current_order_id
        int party_size
    }
    SESSIONS {
        int id PK
        int table_id FK
        string status "ACTIVE / CLOSED"
        ts started_at
        ts ended_at
    }
    ORDERS {
        int id PK
        int session_id FK "owner (gộp bill)"
        int table_id "kept for fast kitchen/robot lookup"
        string status "CHO_BEP / DANG_LAM / XONG"
        real total
    }
    ORDER_ITEMS {
        int id PK
        int order_id FK
        int dish_id
        int qty
        real price
    }
    PAYMENTS {
        int id PK
        int session_id FK "paid per SESSION"
        real amount "= sum of session orders"
        string status "PENDING / PAID"
        string qr_url
    }
    ROBOTS {
        string id PK
        string status "idle / busy / offline"
        int current_task_id
        real battery "snapshot; live in RAM"
        real x "snapshot; live in RAM"
        real y "snapshot; live in RAM"
    }
    TASKS {
        int id PK
        string kind "go_to_table / deliver / call"
        int table_id
        int order_id
        string robot_id
        string status "PENDING / ASSIGNED / IN_PROGRESS / DONE"
    }
```

> Note on `robots`: `battery/x/y` columns are a **periodic snapshot** (cold-start fallback). The
> *live* values come from RAM (`fleet.py`) and are layered on top by `GET /robots`, the panel
> broadcast and the dispatcher's robot picker.

The other two stores are **not** in this DB: `checkpoints.db` (LangGraph) and the in-RAM fleet
state.

---

## 3. Session lifecycle (the core business flow)

```mermaid
sequenceDiagram
    actor Guest
    participant Kiosk
    participant Agent as LLM Agent
    participant API as Backend
    participant DB as orchestrator.db

    Kiosk->>API: POST /seatings {table_id, party_size}
    API->>DB: open session (ACTIVE), table → DANG_PHUC_VU
    Note over Agent: agent.chat resolves the table's<br/>ACTIVE session → thread_id

    Guest->>Agent: "cho 2 phở"
    Agent->>API: confirm_order → POST /orders {table_id, items}
    API->>DB: order #1 under session, total server-side
    Guest->>Agent: "thêm 1 chả giò"
    Agent->>API: confirm_order → POST /orders
    API->>DB: order #2 (SAME session)

    Guest->>Agent: "tính tiền"
    Agent->>API: request_payment → POST /payments {table_id}
    API->>DB: PENDING payment, amount = SUM(session orders)
    API-->>Agent: amount + qr_url

    Guest->>Agent: (scanned) "xong"
    Agent->>API: verify_payment → POST /payments/verify {table_id}
    API->>DB: payment PAID · session CLOSED · table DA_THANH_TOAN
    Note over Agent: next turn resolves NO active session<br/>→ fresh thread for the next guest
```

Endpoints: [tables.py](../src/server_orchestrator/routers/tables.py),
[orders.py](../src/server_orchestrator/routers/orders.py),
[payments.py](../src/server_orchestrator/routers/payments.py); session helpers in
[sessions.py](../src/server_orchestrator/services/sessions.py).

---

## 4. The agent seam (how the LLM writes data)

The agent never touches a DB. Tools call the backend via
[orchestrator_client.py](../src/agent_brain/services/orchestrator_client.py)
(`ORCHESTRATOR_URL`, table id normalised `"T1" → 1` via
[normalise_table_id](../src/_shared/types.py)).

```mermaid
flowchart LR
    subgraph Agent
        T1["confirm_order"]
        T2["request_payment"]
        T3["verify_payment"]
        OC["OrchestratorClient (httpx)"]
        T1 & T2 & T3 --> OC
    end
    OC -->|"POST /orders"| E1["orders.py"]
    OC -->|"POST /payments"| E2["payments.py"]
    OC -->|"POST /payments/verify"| E3["payments.py"]
    OC -->|"GET /tables/{id}/session"| E4["tables.py"]
    E1 & E2 & E3 & E4 --> DB[("orchestrator.db")]
```

### Conversation memory = session (the checkpoint fix)

`thread_id = active session id` ([checkpointer.py](../src/agent_brain/agent/memory/checkpointer.py)).
`graph.chat` resolves the table's current session each turn
([graph.py](../src/agent_brain/agent/graph.py)):

- **Within a visit** → same session id → memory persists.
- **After payment** (session CLOSED) → no active session → next guest opens a **new** session →
  **new thread → clean context** (no bleed between guests). Fallback `table-{id}-nosession` only
  before any seating.

---

## 5. Robot dispatch + telemetry

Robots connect over `/ws?role=robot&robot_id=...` ([ws.py](../src/server_orchestrator/realtime/ws.py)); the
dispatcher ([dispatcher.py](../src/server_orchestrator/services/dispatcher.py)) turns business events into tasks.

```mermaid
sequenceDiagram
    participant API as Backend (router)
    participant Disp as dispatcher
    participant Fleet as fleet.py (RAM)
    participant DB as orchestrator.db
    participant Robot
    participant Panel

    Note over API,Disp: business event (seating / order XONG / call button)
    API->>Disp: create_task(kind, table_id)
    Disp->>DB: task PENDING
    Disp->>Disp: try_assign → pick nearest idle+online robot<br/>(uses LIVE pose from Fleet)
    Disp->>Robot: WS task.assign
    Robot-->>Disp: task_accepted / arrived / task_done
    Disp->>DB: advance task + table + robot status
    Disp->>Panel: WS robot.updated / task.updated / table.updated

    loop every ~0.2s while moving
        Robot-->>Disp: WS heartbeat {battery, x, y}
        Disp->>Fleet: update (RAM) — NO DB write
        Disp->>Panel: WS robot.updated (throttled)
    end
    Note over Disp,DB: snapshot pose/battery to DB only every ~15s (cold-start fallback)
```

**Why telemetry is in RAM:** a moving robot streams pose several times a second. Writing each beat
to SQLite would take a file-level write lock and contend with order/payment transactions on the
same DB. Keeping it in RAM (latest-value-wins, losing a tick is harmless) removes that contention;
`robots` rows stay for identity + assignment + a periodic snapshot.

---

## 6. Frontends

Three Vite/Vue apps under [src/frontends/](../src/frontends/): `customer_ui` (tablet menu/bill),
`kiosk` (check-in seating), `panel` (kitchen + fleet board). Each calls the backend via a
same-origin `/api` proxy to FastAPI:8000 (no CORS); the panel also opens `/ws?role=panel` for
realtime `order.created` / `table.updated` / `robot.updated` / `task.*` events.

### Voice mirror on the tablet (`customer_ui`)

The mic + STT + TTS live on the **Jetson** (USB conference mic in, Bluetooth speaker out); the
tablet has no mic. So `customer_ui` is a **mirror**, not a voice client: it opens
`/ws?role=customer` and renders the live conversation + follows the agent's UI actions. The flow:

```
Jetson: mic → VAD → Whisper → text ──POST /chat──► agent service (LLM, server.py)
                                                      │  ├─ POST /voice/event {voice.heard}
agent runs AIWaiterGraph, returns reply+action ──────┤  └─ POST /voice/event {voice.reply, action}
Jetson speaks the reply (TTS)                         ▼
                                       backend broadcast(role=customer) ──► customer_ui
                                       (user/AI bubbles; open_menu→/menu, open_payment→/payment)
```

The agent never reaches the tablet directly: it POSTs to the backend bridge
([routers/voice.py](../src/server_orchestrator/routers/voice.py)), keeping the backend's
"does-not-import-agent_brain" boundary intact. This is the *delivery* half of the agent's
action seam ([actions.py](../src/agent_brain/agent/actions.py) decides; the agent
service delivers). Tablets filter events by their own `table_id`.

---

## 7. File map (where to look)

| Concern | File |
|---|---|
| App entry, lifespan, routers | [src/server_orchestrator/main.py](../src/server_orchestrator/main.py) |
| DB schema + migrations | [src/server_orchestrator/data/db.py](../src/server_orchestrator/data/db.py) |
| Session helpers | [src/server_orchestrator/services/sessions.py](../src/server_orchestrator/services/sessions.py) |
| Live robot telemetry (RAM) | [src/server_orchestrator/services/fleet.py](../src/server_orchestrator/services/fleet.py) |
| Task dispatch + heartbeat + watchdog | [src/server_orchestrator/services/dispatcher.py](../src/server_orchestrator/services/dispatcher.py) |
| WebSocket hub (router + registry) | [src/server_orchestrator/realtime/ws.py](../src/server_orchestrator/realtime/ws.py) + [connection_manager.py](../src/server_orchestrator/realtime/connection_manager.py) |
| REST contracts (pydantic) | [src/server_orchestrator/schemas/__init__.py](../src/server_orchestrator/schemas/__init__.py) |
| Endpoints | [src/server_orchestrator/routers/](../src/server_orchestrator/routers/) (admin, layout, menu, orders, payments, robots, tables, tasks, voice) |
| Cross-role paths + types | [src/_shared/paths.py](../src/_shared/paths.py) + [types.py](../src/_shared/types.py) |
| Agent graph + chat() | [src/agent_brain/agent/graph.py](../src/agent_brain/agent/graph.py) |
| Thread = session | [src/agent_brain/agent/memory/checkpointer.py](../src/agent_brain/agent/memory/checkpointer.py) |
| Agent tools | [src/agent_brain/agent/tools/](../src/agent_brain/agent/tools/) |
| Agent → backend HTTP seam | [src/agent_brain/services/orchestrator_client.py](../src/agent_brain/services/orchestrator_client.py) |
| Agent resources (centroids, few-shots, prompts, skills) | [src/agent_brain/agent/resources/](../src/agent_brain/agent/resources/) |
| Voice loop on Jetson (mic → VAD → Whisper → POST /chat → TTS) | [src/edge_voice/main.py](../src/edge_voice/main.py) |
| VAD + STT + cross-thread queues | [src/edge_voice/perception/](../src/edge_voice/perception/) |
| TTS | [src/edge_voice/output/tts_engine.py](../src/edge_voice/output/tts_engine.py) |
| Agent HTTP service (LLM on the server; POST /chat) | [src/agent_brain/server.py](../src/agent_brain/server.py) |
| Voice bridge → customer tablet (role=customer WS) | [src/server_orchestrator/routers/voice.py](../src/server_orchestrator/routers/voice.py) |

## 8. Key endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/seatings` | Seat a party → opens an ACTIVE session |
| GET | `/tables/{id}/session` | Active session + gộp total (agent resolves thread, panel shows bill) |
| POST | `/orders` | Create order under the table's session |
| PATCH | `/orders/{id}` | Kitchen status; `XONG` → enqueues a deliver task |
| POST | `/payments` | Open/refresh the gộp payment (PENDING + QR) |
| POST | `/payments/verify` | Settle by table (agent): PAID + close session + free table |
| POST | `/payments/{id}/verify` | Settle by id (tablet) |
| GET | `/robots` | Fleet status (DB snapshot + live RAM overlay) |
| POST | `/voice/event` | Voice bridge: agent service → tablet (`voice.heard` / `voice.reply` + UI action) |
| WS | `/ws?role=panel\|robot\|customer` | Realtime events / robot link / voice mirror to tablet |
