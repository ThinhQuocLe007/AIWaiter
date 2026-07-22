## 4.5 Backend Orchestrator — FastAPI + SQLite + WebSocket

> **Status:** draft
> **Cross-refs:** §4.2 for architecture overview, §4.3.5 for agent-orchestrator integration, §4.6 for fleet management, §4.7 for web interfaces
> **Source:** `src/server_orchestrator/main.py` (61 lines), `data/db.py` (188 lines), `realtime/connection_manager.py` (135 lines), `realtime/ws.py` (81 lines), `routers/` (9 routers)
> **Figures needed:** Fig 4.5 (database ERD — 8 tables with foreign key relationships)

---

The backend orchestrator is the central nervous system of the AI Waiter system. It owns the persistent business ledger (SQLite), exposes a REST API for all CRUD operations, and maintains a WebSocket hub for real-time event fan-out to all connected clients. The orchestrator is a single FastAPI process running on port 8000 on the central server, started via `uvicorn src.server_orchestrator.main:app`.

### 4.5.1 Architectural Patterns

Three foundational patterns shape the orchestrator's design:

**Event-driven via WebSocket pub/sub.** The orchestrator is the central message hub. All business events — order created, table status changed, robot arrived, task assigned — are fanned out to all relevant WebSocket clients by role. REST is used for writes and initial state loads; WebSocket for all real-time updates. No client polls for data. This eliminates polling overhead (a kitchen with 3 panels polling at 1 Hz generates 180 requests per minute, most returning unchanged data) and ensures all UIs synchronize within <50ms of a state change on local WiFi.

**Single-writer SQLite.** One FastAPI process handles all database writes. There is no concurrent write contention at restaurant scale (dozens of orders per hour, not thousands per second). SQLite in WAL (Write-Ahead Logging) mode provides concurrent read access while one writer holds the lock. ACID transactions guarantee correctness for critical multi-step operations — a seating creates a session, updates the table, and dispatches a robot task atomically; failure at any step rolls back the entire transaction.

**Service layer separation.** Routers handle HTTP parsing and response formatting only. Business logic lives in `services/` — dispatcher (`dispatcher.py`, 469 lines), fleet telemetry (`fleet.py`), session management (`sessions.py`, 57 lines), and menu loading (`menu_loader.py`). This separation allows the agent brain to call service functions via `OrchestratorClient` without going through HTTP when running co-located on the same server, though in the current deployment the agent communicates over localhost HTTP for process isolation (§4.2.7).

### 4.5.2 REST API Design

The orchestrator exposes 20 endpoints across 10 routers, mounted at startup via `app.include_router()` (`main.py:47-56`). All request and response bodies are validated via Pydantic models; OpenAPI documentation is auto-generated.

| Router | Prefix | Endpoints | Purpose |
|--------|--------|-----------|---------|
| `menu` | `/menu` | `GET /menu` | Returns full menu with dishes, categories, best sellers, discounts |
| `tables` | `/tables` | `GET /tables`, `GET /tables/{id}`, `GET /tables/{id}/session`, `POST /seatings`, `PATCH /tables/{id}` | Table list, seating (kiosk check-in), session lookup, status management |
| `orders` | `/orders` | `POST /orders`, `PATCH /orders/{id}` | Order creation (agent confirm_order), status advancement (kitchen panel) |
| `payments` | `/payments` | `POST /payments`, `POST /payments/verify` | Payment request (agent request_payment), verification (backend mock) |
| `robots` | `/robots` | `GET /robots`, `GET /robots/{id}` | Robot list with live pose/battery overlay from RAM telemetry |
| `tasks` | `/tasks` | `GET /tasks`, `POST /tables/{id}/call` | Task list, call-robot button (guest summons robot) |
| `layout` | `/layout` | `GET /layout` | Returns SLAM map PNG and table waypoints for panel minimap |
| `admin` | `/admin` | `POST /admin/reset` | Wipes and re-seeds demo data |
| `voice` | `/voice` | `POST /voice/event`, `POST /voice/listen`, `POST /voice/cancel` | Agent-to-tablet voice mirroring, tablet-to-robot listen commands |
| `ws` | (WebSocket) | `WS /ws` | WebSocket hub for all real-time events |

**Seating flow** (`POST /seatings`, `routers/tables.py:41-66`). This is the most complex single endpoint — it performs a multi-step transaction that begins a party's visit:

1. Verify the table exists and is `TRONG` (empty). Return 409 Conflict if occupied (race-condition protection for concurrent kiosk check-ins).
2. Update table status to `DANG_PHUC_VU`, set `party_size`, record `seated_at` timestamp.
3. Create an `ACTIVE` session row in the sessions table — this session ID will be the party's financial grouping and the agent's `thread_id` for conversation memory (§4.3.1.4).
4. Broadcast `table.updated` to all panel and customer WebSocket clients.
5. Create a `go_to_table` task, which triggers the dispatcher to find the nearest idle robot and send it to the table.

The entire operation runs in a single SQLite transaction with auto-commit on success and rollback on exception.

**CORS.** The orchestrator configures CORS middleware for the three Vite dev ports (5173, 5174, 5175) plus the production build port (`settings.cors_origins`). In production behind a reverse proxy, the frontend is served from the same origin, eliminating CORS entirely.

### 4.5.3 Database Schema

The orchestrator uses raw SQL via Python's `sqlite3` module — no ORM. This keeps the database layer simple (single file, no migrations framework, no connection pool) at the cost of manual schema management. SQLite rows use `sqlite3.Row` factory (`db.py:133`) for dict-like access; Pydantic models in `schemas/` enforce type constraints at the application boundary.

**Eight business tables** (`db.py:33-128`):

| Table | Primary Key | Key Columns | Purpose |
|-------|------------|-------------|---------|
| `tables` | `id` (INTEGER) | `name`, `capacity`, `status`, `party_size`, `seated_at` | Physical restaurant tables |
| `sessions` | `id` (AUTOINCREMENT) | `table_id` (FK), `status`, `party_size`, `started_at`, `ended_at` | One party's visit: seating → payment → leave |
| `dishes` | `id` (AUTOINCREMENT) | `name`, `price`, `category`, `available` | Menu items (populated from `menu.json` at seed) |
| `orders` | `id` (AUTOINCREMENT) | `session_id` (FK), `table_id` (FK), `status`, `total`, `created_at` | Confirmed orders with cumulative total |
| `order_items` | `id` (AUTOINCREMENT) | `order_id` (FK), `dish_id` (FK), `name`, `qty`, `price`, `note`, `status` | Line items within an order |
| `robots` | `id` (TEXT) | `name`, `status`, `battery`, `x`, `y`, `current_task_id`, `activity` | Robot identity and persistent state (pose/battery are periodic snapshots) |
| `tasks` | `id` (AUTOINCREMENT) | `kind`, `table_id`, `order_id`, `robot_id`, `status` | Dispatch unit: one robot serving one table for one purpose |
| `payments` | `id` (AUTOINCREMENT) | `session_id` (FK), `method`, `amount`, `status`, `txn_ref`, `qr_url`, `paid_at` | Per-session payment records (gộp billing) |

**Status enums.** String-based status values (`"TRONG"`, `"DANG_PHUC_VU"`, `"CHO_BEP"`, `"PENDING"`) are defined as Python enums in `src/_shared/types.py` and enforced by Pydantic validation at the REST boundary. SQLite stores these as raw TEXT with no CHECK constraints — type safety is maintained at the application layer, not the database.

**Schema evolution.** The database schema is versioned implicitly through the code. `init_db()` (`db.py:181-188`) runs at startup and applies:

1. `CREATE TABLE IF NOT EXISTS` for all tables — safe to run against an existing database.
2. `_migrate_payments_to_session()` — detects legacy per-order payment tables and drops them if present, before recreating with the per-session schema.
3. `_apply_migrations()` — checks `PRAGMA table_info` for each table and adds missing columns via `ALTER TABLE ADD COLUMN`. Each migration is idempotent: if the column already exists, the ALTER is skipped. Currently tracked migrations: `party_size` and `seated_at` on `tables`, `activity` on `robots`, `session_id` on `orders`, `qr_url` on `payments`.

This approach is appropriate for a single-deployment restaurant system, where schema changes are rare and backward-compatible. For a multi-tenant SaaS system, a proper migration framework (Alembic) would be necessary.

**Separate databases.** The orchestrator's `orchestrator.db` is distinct from the agent's `checkpoints.db`. The former stores business ledger data (tables, orders, payments, tasks); the latter stores LangGraph conversation state (message history, cart, order stage). The separation ensures that conversation memory — which grows linearly with customer interactions — never interferes with business ledger performance, and that a bad checkpoint write cannot corrupt order data.

### 4.5.4 WebSocket Hub

A single `/ws` endpoint serves all real-time communication, with client role determined by query parameter (`ws.py:36-61`):

| Role | Query | Direction | Purpose |
|------|-------|-----------|---------|
| `panel` | `role=panel` | Server → client only | Kitchen Kanban, fleet board, table overview, minimap |
| `customer` | `role=customer` | Server → client only (filtered by `table_id` in event payload) | Tablet: voice mirror, cart sync, UI actions, table status |
| `robot` | `role=robot&robot_id=<id>` | Bidirectional | Task assignment (server → robot), heartbeat/status (robot → server) |
| `voice-device` | `role=voice-device&robot_id=<id>` | Server → client only | `start_listening` / `cancel_listening` commands to Jetson |

**Connection management** (`connection_manager.py:18-134`). The `ConnectionManager` singleton tracks live WebSocket connections across four registries:

- `_by_role`: `dict[str, set[WebSocket]]` — role-grouped anonymous sockets for broadcast (panel, customer).
- `_robots`: `dict[str, WebSocket]` — indexed by `robot_id` for targeted task delivery.
- `_voice_devices`: `dict[str, WebSocket]` — indexed by `robot_id` for microphone gating commands.
- `_table_to_robot`: `dict[int, str]` — dynamic table→robot voice binding, set by the dispatcher when a robot arrives at a table.

A robot opens **two WebSocket connections** sharing one `robot_id`: `role=robot` for motion tasks and telemetry, and `role=voice-device` for microphone commands. Both are cleaned up independently on disconnect.

**Event catalog.** The orchestrator emits eight event types:

| Event | Emitters | Consumers | Payload |
|-------|----------|-----------|---------|
| `order.created` | `POST /orders` | Panel (KitchenBoard) | Full order with items |
| `order.updated` | `PATCH /orders/{id}` | Panel (order status) | Updated order fields |
| `table.updated` | `POST /seatings`, `PATCH /tables/{id}`, payment verify | Panel, Customer | Full table state |
| `robot.updated` | Heartbeat processing (throttled to 5 Hz) | Panel (fleet board, minimap) | Robot status, pose, battery, activity |
| `task.created` | `create_task()` | Panel (task queue) | New task metadata |
| `task.updated` | `on_accepted()`, `on_done()`, `_requeue_task()` | Panel | Task status change |
| `voice.heard` | `POST /voice/event` (type=voice.heard) | Customer (tablet) | User transcript |
| `voice.reply` | `POST /voice/event` (type=voice.reply) | Customer (tablet) | Agent response, UI action, cart |
| `reset` | `POST /admin/reset` | All | Full state wipe signal |

**Broadcast filtering.** Consumer-side filtering is done by the client based on event payload fields. Events carry the relevant identifiers (`table_id`, `robot_id`, `order_id`) in their payload, and each client filters locally. For example, the customer tablet receives all `customer`-role broadcasts but only renders events where `table_id` matches its own table. This is simpler than server-side per-table socket tracking at restaurant scale (6 tables, not 6,000).

### 4.5.5 Session Lifecycle

A session represents one party's entire visit: seating → ordering → payment → leave. Sessions are the unit of financial grouping (gộp bill: one payment for all orders) and conversation isolation (the agent's `thread_id` equals the session ID).

**Lifecycle states:**

```
[Kiosk Check-in] → ACTIVE → (multiple orders) → [Payment] → CLOSED
```

**1. Seating** (`POST /seatings`). A kiosk operator selects a free table and enters party size. The endpoint:
- Marks `tables.status = DANG_PHUC_VU`, records `party_size` and `seated_at`.
- Creates an `ACTIVE` session row (`sessions.py:20-27`).
- Dispatches a `go_to_table` task to the nearest idle robot.
- Returns the updated table and session.

**2. Ordering.** Multiple orders can be created within a session. Each `POST /orders` links to the session via `session_id`. The session total — computed as `SELECT COALESCE(SUM(total), 0) FROM orders WHERE session_id = ?` (`sessions.py:51-57`) — grows cumulatively as orders are added. The agent's LangGraph checkpointer uses `thread_id = session_id`, so conversation memory persists across all orders within the visit.

**3. Payment.** When the customer requests the bill via voice (`request_payment` tool), a `payments` row is created with `status = PENDING`, the session total is computed, and a VietQR URL is generated. When payment is verified (`POST /payments/verify`):
- The session is marked `CLOSED` with `ended_at` timestamp (`sessions.py:42-48`).
- The table is marked `DA_THANH_TOAN`.
- Pending robot tasks for the table are cancelled (`cancel_table_tasks`).
- The robot is released (sent home) via `task.release`.

**4. Table end.** Staff can manually end a table via `PATCH /tables/{id} {status: TRONG}` (`routers/tables.py:80-109`). This clears party state, cancels pending tasks, and broadcasts the change. The next seating at this table creates a new session with a new ID — the agent's checkpointer sees a new `thread_id` and provides a fresh conversation context.

**Session ID as the integration seam.** The session ID is the critical identifier that links three subsystems:
- **Database:** Groups orders and payments (financial ledger).
- **Agent:** Key for LangGraph conversation memory (`thread_id = session_id`, §4.3.1.4).
- **Orchestrator:** Target for agent tool calls (`table_id` routes to the correct session).

When payment closes a session, all three subsystems reset simultaneously — the ledger is closed, the conversation memory is archived, and the table is freed.

### 4.5.6 Voice Bridge

The voice bridge (`routers/voice.py`) connects the three voice-related components: the agent (produces text responses), the tablet (displays conversation), and the Jetson voice device (captures speech).

**Agent → Tablet mirroring** (`POST /voice/event`, `voice.py:40-44`). After each customer turn, the agent POSTs voice events to the orchestrator:

- `type: "voice.heard"` — the customer's transcribed utterance. Fan-out to the tablet: displays the user bubble and a "thinking..." indicator.
- `type: "voice.reply"` — the agent's spoken response text, plus optional `action` (UI command: `open_menu`, `open_payment`), `cart` (serialized cart state for tablet sync), `stage` (current order stage), and `confirmed` (whether an order was just confirmed).

The orchestrator broadcasts these to all `role=customer` WebSocket connections. Each tablet filters by `table_id` in the payload — only the correct table sees its conversation.

**Tablet → Voice Device signaling** (`POST /voice/listen`, `voice.py:60-69`). When a customer presses "Talk to AI" on the tablet:

1. The tablet POSTs `{table_id}` to `/voice/listen`.
2. The orchestrator's `send_to_voice_device` resolves `table_id → robot_id` via the dynamic binding (`connection_manager.py:103-120`).
3. If a binding exists (a robot is at the table with its mic connected), a `start_listening` message is sent to that robot's `voice-device` WebSocket.
4. If no binding exists (no robot at table, or mic disconnected), the endpoint returns `{status: "no_device"}` — the tablet shows an "assistant offline" indicator.

**Dynamic table-robot binding** (`connection_manager.py:83-101`). The binding is set by the dispatcher when a robot arrives at a table (`on_arrived`, `dispatcher.py:333`). It is cleared when:
- The robot completes its task and leaves (`on_done`, `dispatcher.py:339`).
- The robot disconnects (WebSocket close, `dispatcher.py:250`).
- The table is ended or payment is verified (`cancel_table_tasks` / session close).
- A new robot arrives at the same table (old binding replaced).

This dynamic binding means a robot is not tied to a specific table — it serves whichever table it is dispatched to. When the robot leaves, the table's "Talk to AI" button returns to the "no device" state until the next robot arrives.

**Cancel support** (`POST /voice/cancel`, `voice.py:72-83`). The tablet's "Hủy" button aborts an in-flight voice capture. The orchestrator sends `cancel_listening` to the table's bound voice device, which disarms the microphone and discards any partially captured utterance.
