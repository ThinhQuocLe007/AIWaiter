## 4.2 Overall Software Architecture

> **Status:** draft
> **Cross-refs:** see §4.1 for requirements, §4.3–§4.8 for component details
> **Figures needed:** Fig 4.2 (three-tier block diagram), Fig 4.3 (voice ordering data flow sequence)

---

### 4.2.1 Three-Tier Topology

The system is organized into three physical tiers connected over a local WiFi network, with Netbird VPN providing a secure overlay for off-site server scenarios.

**Tier 1 — Central Server** (x86 PC with NVIDIA GPU). This machine runs all intelligence: the conversational agent (LangGraph StateGraph with Ollama LLM inference), the backend orchestrator (FastAPI REST API and WebSocket hub), the hybrid RAG retrieval system (FAISS + BM25 indices over 217 menu items), and two SQLite databases (business ledger and conversation memory). All components on this tier communicate via localhost HTTP. The GPU requirement is driven by the LLM: Qwen2.5 7B requires approximately 6–8 GB VRAM, pinned in memory with `keep_alive=-1` to eliminate cold-start latency between turns.

**Tier 2 — Robot** (Jetson Orin Nano 8GB). This machine handles all physical interaction: voice input/output (microphone capture, Silero VAD, faster-whisper STT, Piper/edge-tts TTS), ROS2 autonomous navigation (covered in Chapter 3), and sensor processing (RPLiDAR A2M8, Intel RealSense D435, MPU6050 IMU). The Jetson maintains two persistent WebSocket connections to the server — one as `role=voice-device` for receiving microphone gating commands, one as `role=robot` for receiving navigation tasks and reporting telemetry — sharing a single `robot_id` for routing.

**Tier 3 — Staff Devices** (browsers on laptops/tablets). Three single-page applications serve distinct roles: a customer-facing tablet on the table (menu browsing, voice conversation mirror, cart, payment), a kiosk at the entrance (guest check-in, table selection), and a management panel in the kitchen (order Kanban board, robot fleet dashboard, table overview, SLAM minimap). All three share a common frontend library for REST/WebSocket communication and TypeScript type definitions.

---

### 4.2.2 Block Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    TIER 1 — CENTRAL SERVER                        │
│                                                                  │
│  ┌─────────────────────────┐    ┌────────────────────────────┐  │
│  │   AGENT BRAIN (:8100)   │    │   ORCHESTRATOR (:8000)     │  │
│  │                         │    │                            │  │
│  │  LangGraph StateGraph   │◄──►│  FastAPI REST (10 routers) │  │
│  │  Hybrid Router (2-tier) │    │  WebSocket Hub (4 roles)   │  │
│  │  4 Domain Workers       │    │  Fleet Dispatcher          │  │
│  │  Deterministic Validator│    │  Voice Bridge              │  │
│  │  7 Tools + ToolNode     │    │  Session Manager           │  │
│  │  Response Node (SSE)    │    │                            │  │
│  └───────────┬─────────────┘    └──────────┬─────────────────┘  │
│              │                             │                     │
│  ┌───────────▼─────────────┐    ┌─────────▼───────────────────┐ │
│  │  checkpoints.db         │    │  orchestrator.db (8 tables) │ │
│  │  (conversation memory)  │    │  (business ledger)          │ │
│  └─────────────────────────┘    └─────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Ollama: Qwen2.5 7B Instruct (3 endpoints, same model)   │   │
│  │  Router T=0.0  │  Worker T=0.1  │  Response T=0.3        │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │  RAG: FAISS (768-dim) + BM25 (k1=1.2,b=0) + RRF (k=60) │   │
│  │  217 dishes × 12 categories from menu.json               │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────┬───────────────────┬───────────────────────┘
                       │ Netbird / WiFi    │ Netbird / WiFi
         ┌─────────────▼──────────┐  ┌─────▼────────────────────────┐
         │ TIER 2 — ROBOT         │  │ TIER 3 — STAFF DEVICES        │
         │ (Jetson Orin Nano)     │  │ (browsers)                    │
         │                        │  │                               │
         │ ┌────────────────────┐ │  │  Customer Tablet  :5173       │
         │ │ Voice Pipeline     │ │  │  ┌─ Vue 3 + PrimeVue         │
         │ │ Mic→VAD→Whisper→TTS│ │  │  │─ WS role=customer          │
         │ │ WS voice-device    │ │  │  │─ Menu, Cart, Voice Mirror  │
         │ └────────────────────┘ │  │  └────────────────────────────┤
         │                        │  │                               │
         │ ┌────────────────────┐ │  │  Kiosk  :5174                 │
         │ │ ROS2 Navigation    │ │  │  ┌─ Vue 3                    │
         │ │ RTAB-Map + Nav2    │ │  │  │─ REST only                 │
         │ │ EKF + ArUco        │ │  │  │─ Table grid, Check-in      │
         │ │ WS robot           │ │  │  └────────────────────────────┤
         │ └────────────────────┘ │  │                               │
         │                        │  │  Panel  :5175                 │
         │ Sensors:               │  │  ┌─ Vue 3                    │
         │ RPLiDAR A2M8, D435,    │  │  │─ WS role=panel             │
         │ MPU6050, Hall encoders │  │  │─ Kitchen Kanban, Fleet,    │
         │                        │  │  │  Table Overview, Minimap  │
         └────────────────────────┘  │  └────────────────────────────┤
                                     └──────────────────────────────┘
```

---

### 4.2.3 Component Responsibility Map

| Component | Location | Port/Protocol | Talks to | Over |
|-----------|----------|---------------|----------|------|
| **Agent Brain** | Server | 8100 / HTTP | Orchestrator (REST), Ollama (localhost), Voice Device (receives POST /chat) | HTTP |
| **Orchestrator** | Server | 8000 / HTTP + WS | Agent (REST), All WebSocket clients, SQLite DBs | HTTP, WS |
| **Ollama** | Server | 11434 / HTTP | Agent Brain (ChatOllama) | localhost HTTP |
| **Voice Pipeline** | Robot (Jetson) | N/A (client only) | Orchestrator (WS voice-device), Agent (POST /chat) | WS + HTTP |
| **ROS2 Nav2** | Robot (Jetson) | N/A (client only) | Orchestrator (WS robot) | WS |
| **Customer Tablet** | Staff device | 5173 / HTTP (dev) | Orchestrator (WS customer + REST /api) | WS + HTTP |
| **Kiosk** | Staff device | 5174 / HTTP (dev) | Orchestrator (REST /api) | HTTP |
| **Panel** | Staff device | 5175 / HTTP (dev) | Orchestrator (WS panel + REST /api) | WS + HTTP |

---

### 4.2.4 Primary Data Flows

The system executes four main data flows, described here at the architecture level. Each flow's internal logic is detailed in the referenced sections.

**Flow (a) — Voice Ordering at Table** (see §4.3, §4.4)

This is the core customer interaction loop. Steps:

1. Guest presses "Talk to AI" on the tablet → `POST /voice/listen {table_id}` → Orchestrator resolves `table_id → robot_id` via the voice bridge → sends `start_listening` to the Jetson's `voice-device` WebSocket.
2. Jetson arms the microphone. Silero VAD detects speech boundaries and captures one utterance. faster-whisper (PhoWhisper weights, `language=vi`, `beam_size=5`) transcribes the audio to Vietnamese text.
3. The transcript is POSTed to Agent Brain `/chat` or `/chat/stream` with `table_id`.
4. Agent Brain immediately posts `voice.heard` to Orchestrator `POST /voice/event`, which fans the transcript to the tablet WebSocket so the customer sees what was heard.
5. The LangGraph agent processes the utterance through five stages: router classifies intent → worker decides on a tool call → tools execute → validator inspects results → state updates → response generated. If the action is `confirm_order`, the tool POSTs to Orchestrator `/orders`.
6. Agent Brain posts `voice.reply` (response text, UI action, cart state, order confirmation) to Orchestrator `POST /voice/event`, which fans to the tablet WebSocket.
7. The response text is streamed back to the Jetson for TTS playback (Piper or edge-tts, sentence by sentence, aligned with SSE).

**Flow (b) — Order to Kitchen Display** (see §4.5, §4.7)

When `confirm_order` creates an order via `POST /orders`, the Orchestrator:

1. Inserts the order and order items into `orchestrator.db` with status `CHO_BEP` (awaiting kitchen).
2. Emits `order.created` to all `role=panel` WebSocket connections.
3. The management panel's Kitchen Kanban board displays the new order in the "Chờ Bếp" column with per-item details and elapsed time.
4. Kitchen staff advances the order: Chờ Bếp → Đang Làm → Xong via `PATCH /orders/{id}`.
5. When status reaches `XONG`, the Orchestrator's dispatcher creates a `deliver` task and assigns it to the nearest idle robot via WebSocket `task.assign`.

**Flow (c) — Manager Monitoring** (see §4.6, §4.7)

The management panel maintains live situational awareness through WebSocket events:

- `robot.updated`: robot position (x, y) and battery level, refreshed at 5 Hz from RAM telemetry store. Drives the minimap animation and fleet board battery gauges.
- `table.updated`: table status changes (TRONG → DANG_PHUC_VU → DA_THANH_TOAN). Drives the table overview.
- `task.created` / `task.updated`: dispatcher task lifecycle. Drives the fleet board activity descriptions.
- REST endpoints (`GET /robots`, `GET /tables`, `GET /tasks`) provide initial state on panel load; WebSocket provides subsequent live updates.

**Flow (d) — Backend to Robot Navigation Goals** (see §4.6, Chapter 3)

The dispatcher translates business events into robot navigation tasks:

1. Business event occurs (guest seated → `go_to_table`; order ready → `deliver`; guest presses call button → `call`).
2. Dispatcher creates a PENDING task in `orchestrator.db`.
3. `try_assign()` picks the nearest idle robot (live WebSocket connection + battery ≥ 20% + Euclidean distance to table waypoint). Robot receives `task.assign` via WebSocket with target waypoint coordinates.
4. Robot's ROS2 Nav2 stack receives the goal, navigates autonomously (covered in Chapter 3), and reports progress: `task_accepted` → `arrived` → `task_done`.
5. On arrival, the dispatcher binds `table_id → robot_id` in the voice bridge, enabling subsequent voice commands from that table to route to the correct robot's microphone.

---

### 4.2.5 Communication Protocol Summary

| Communication Path | Protocol | Pattern | Purpose |
|-------------------|----------|---------|---------|
| Agent → Orchestrator | HTTP REST | Synchronous request/response | Order creation, payment, session queries |
| Agent → Orchestrator | HTTP REST | Fire-and-forget | Voice event mirroring (hears, replies) |
| Orchestrator → Web Clients | WebSocket | Server push (pub/sub) | Real-time state updates |
| Orchestrator → Robot | WebSocket | Bidirectional | Task assignment + telemetry |
| Robot → Agent | HTTP REST | Synchronous request/response | Voice utterance → agent processing |
| Robot → Orchestrator | WebSocket | Heartbeat | Telemetry (pose, battery) |
| Frontends → Orchestrator | HTTP REST | Request/response | CRUD operations, initial state loads |
| Frontends → Orchestrator | WebSocket | Server push (receive only) | Live updates, voice mirroring |
| Agent → Ollama | HTTP REST | Synchronous (localhost) | LLM inference |
| All → All | Netbird VPN | Encrypted overlay | Secure connectivity across network boundaries |

**Why WebSocket for real-time, not polling?** A restaurant has multiple state-changing events per minute (order created, table status changed, robot position updated at 5 Hz). Polling every client at 1 Hz would generate hundreds of requests per minute, most returning unchanged data. WebSocket push eliminates this overhead: clients receive events only when state changes, with <50ms propagation latency on local WiFi.

**Why separate Agent and Orchestrator processes?** The agent performs CPU/GPU-bound LLM inference (blocking operations taking 0.3–2.2s per turn). The orchestrator handles sub-millisecond database operations and real-time WebSocket fan-out. Running them as separate processes (ports 8100 and 8000) prevents LLM inference from blocking WebSocket event delivery. They communicate via localhost HTTP, which adds negligible overhead (~1ms) compared to LLM inference time.

**Why HTTP between Agent and Orchestrator, not in-process?** A shared Python process would couple the agent's LangGraph dependency tree to the orchestrator's FastAPI event loop. Separate processes allow independent scaling, debugging, and restart. The Orchestrator can continue serving web clients and dispatching robots even if the Agent is restarting.

---

### 4.2.6 Service Dependency Graph

```
Ollama (must be running first)
    │
    ▼
Agent Brain (:8100) ───depends on───► Ollama (LLM inference)
    │                                  Orchestrator (:8000) (order/payment/session APIs)
    │
    ▼
Orchestrator (:8000) ───depends on───► SQLite (orchestrator.db)
    │                                  Agent (voice event mirroring)
    │
    ├──► Voice Pipeline (Jetson) ───depends on───► Orchestrator (WS commands)
    │                                              Agent (POST /chat)
    │
    ├──► ROS2 Nav2 (Jetson) ───depends on───► Orchestrator (WS tasks)
    │
    └──► Web Frontends (:5173-5175) ───depends on───► Orchestrator (REST + WS)
```

Startup order enforced by `make backend` → `make agent` → `make voice` → `make frontend`. Ollama must be running before the Agent starts (warmup ping at agent startup verifies this). The Orchestrator is independent of the Agent for core functionality (menu browsing, manual ordering, table management) and degrades gracefully if the Agent is unavailable.

---

### 4.2.7 Key Architectural Decisions

Four foundational decisions shape the entire architecture. Each is stated here with rationale; the implementation consequences appear throughout §4.3–§4.8.

**Decision 1: SQLite, not PostgreSQL.** SQLite is a single-file embedded database requiring zero administration — no server process, no configuration, no user management. At restaurant scale (dozens of orders per hour, not thousands per second), SQLite's single-writer concurrency model is not a bottleneck. ACID transactions guarantee correctness for multi-step operations (seat → create session → dispatch robot). The database file can be backed up by copying a single file. This decision trades horizontal scalability (which a restaurant does not need) for operational simplicity (which a restaurant deployment requires).

**Decision 2: RAM telemetry, not database writes at sensor frequency.** Robot heartbeats arrive at 4+ Hz per robot (pose and battery). Writing each heartbeat to SQLite would create write contention and unnecessary I/O. Instead, the latest pose and battery are stored in a thread-safe Python dictionary (`fleet.py`), updated lock-free. A periodic snapshot writes to the database every 15 seconds for cold-start recovery. This decision was validated in testing: SQLite write latency under concurrent access would bottleneck the dispatcher's nearest-robot scoring loop.

**Decision 3: Synchronous LangGraph execution wrapped in async SSE.** LangGraph's `SqliteSaver` checkpointer is synchronous (it uses `sqlite3`, which is not async-safe). But FastAPI's event loop should not be blocked by multi-second LLM inference. The solution: the LangGraph graph executes synchronously inside a `ThreadPoolExecutor`, producing a typed response context. An async generator wraps this result and yields Server-Sent Events to the HTTP client. This avoids blocking the event loop while maintaining compatibility with LangGraph's synchronous checkpointer.

**Decision 4: Self-hosted Ollama, not cloud API.** Cloud LLM APIs (OpenAI, Anthropic, Google) require internet connectivity per turn, incur per-token API costs, and transmit customer voice data off-premises. Ollama runs Qwen2.5 7B locally on the server's GPU with `keep_alive=-1` (model stays in VRAM). This provides: (a) no internet dependency — the restaurant WiFi can fail and voice ordering still works; (b) zero marginal cost per utterance; (c) data stays on-premises; (d) bounded latency with no external network variability. The trade-off is upfront hardware cost (a server with GPU) and model quality (7B parameters vs. cloud models with 70B+ parameters), which is acceptable for a task-oriented dialogue system with a limited domain.
