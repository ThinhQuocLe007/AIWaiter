## 2.6 Restaurant Operations & Fleet Management

> *A restaurant operator needs a customer tablet for ordering, a kitchen display for cooking, a manager dashboard for oversight, and a robot fleet for delivery — all seeing the same real-time state. An AI agent must drive this state through API calls, triggering robot navigation, kitchen display updates, and session lifecycle transitions. This section surveys existing approaches for fleet management and restaurant operations, and identifies the gap: no lightweight, self-contained system integrates all roles under a single AI-driven real-time state.*
>
> **Cross-refs:** §2.1 (overview — restaurant software limitation), §4.1 (backend requirements), §4.7 (orchestrator — proposed method), §5.5 (system integration tests)
> **Citations:** [2.6.1]–[2.6.25]; final numbering assigned when all Ch.2 references are merged.

---

### 2.6.1 Multi-Robot Task Assignment

In a restaurant with multiple robots and multiple tables, the system must answer a recurring question: when an order is ready for delivery, which robot should carry it? The answer depends on robot availability, proximity to the kitchen, battery level, and current task queue.

**Assignment strategies.** Three families of assignment algorithms have been studied in multi-robot systems [2.6.1]:

- **Nearest-idle.** The simplest strategy: when a task arrives, filter the pool of idle robots, compute each robot's Euclidean distance from its current position to the task's target location, and assign the task to the closest robot [2.6.2]. Strengths: minimal computation, no coordination overhead, works well for short trips (3–5 meters kitchen-to-table) in small environments where the difference between the nearest and second-nearest robot's travel time is negligible. Dominant approach in commercial restaurant robot deployments where tasks are assigned by a human operator through a tablet interface.

- **Auction-based and market-based.** Robots bid on tasks based on their current state — distance to target, battery level, queue length, estimated completion time. The auctioneer (centralized or decentralized) awards the task to the lowest bidder [2.6.3]. More complex than nearest-idle but enables dynamic load balancing across a heterogeneous fleet. Prior work on auction-based task assignment exists predominantly for warehouse AGV fleets (Amazon Kiva, Cainiao) where trip distances are 50–200 meters and the assignment choice meaningfully affects throughput [2.6.4].

- **Battery-aware filtering.** Before proximity scoring, robots with battery below a threshold — typically 20% — are excluded from the candidate pool. This prevents assigning a critical delivery to a robot that may shut down mid-trip. Prior work on energy-aware task assignment establishes the filtering approach as a standard safety constraint [2.6.5].

**Fleet management frameworks.** For multi-robot coordination at larger scales, ROS2 OpenRMF (Robotics Middleware Framework) provides a full-featured infrastructure: traffic scheduling with zone-based conflict avoidance, multi-floor elevator coordination, door control integration, and task queuing with priority support [2.6.6]. OpenRMF is designed for warehouse-scale and hospital-scale deployments — dozens of robots operating across multiple floors with complex traffic patterns.

Commercial fleet platforms — Bear Robotics' Bear Universe, Pudu's PuduCloud, Keenon's Cloud Platform — provide cloud-based fleet management for their respective robot ecosystems [2.6.7]. Each platform is manufacturer-locked: Bear Universe manages only Servi robots; PuduCloud manages only Bellabot and Kettybot. The platforms are closed — no third-party API exists for an external AI agent to create tasks, monitor robot status, or receive task completion events. They are designed for human operators managing robot fleets through a tablet dashboard, not for programmatic agent-driven dispatch.

**→ Gap.** Warehouse-scale frameworks are too heavy for restaurant scale. Commercial platforms are closed. Neither model serves the specific need of a restaurant AI system: a lightweight dispatcher embedded within the same backend process that manages orders, tables, and sessions, where tasks are created programmatically by the AI agent's business logic rather than by a human operator selecting destinations on a screen. The dispatch algorithm itself — nearest-idle with battery filtering — is not novel. What is novel, and unaddressed by prior work, is the integration of that algorithm into a backend where the task source is a conversational agent producing tool calls that cascade into task dispatches, with the entire task lifecycle synchronized with restaurant business events.

---

### 2.6.2 Dynamic Robot-Table Voice Binding

In a multi-robot, multi-table restaurant, robots are table-agnostic — any robot can serve any table. However, voice interaction is physically localized: the microphone and speaker are mounted on a specific robot. When a customer at table 3 presses the "Talk to AI" button on their tablet, the system must know which robot is currently at or en route to table 3, and must route the voice capture command to that specific robot's edge voice pipeline. When the agent produces a spoken response, the TTS output must play through that same robot's speaker. This binding between a table and a robot's voice hardware must be dynamic — established when the robot arrives, released when it departs [2.6.8].

**Prior approaches:**

- **Static binding.** Each table is permanently assigned a dedicated robot that never serves other tables. This is the simplest approach and is used in some commercial deployments where one robot per floor section operates on a fixed route. It eliminates the binding problem entirely — the tablet for table 3 always talks to robot 3. It also eliminates fleet flexibility: if robot 3 is charging, table 3 has no voice service.

- **Broadcast-to-all.** Every robot in the fleet hears every voice capture command and plays every TTS response. The robot physically nearest to the table is the one the customer hears clearly; the others produce quiet, distant speech. This creates two problems: (a) privacy — a customer's order at table 3 is heard by the microphone at table 5 if a robot is nearby, and (b) acoustic confusion — the customer hears a response from a robot across the aisle while their own robot remains silent.

- **Dynamic binding.** The binding between table and robot is established when the robot physically arrives at the table and is released when it departs. Voice capture commands from the tablet at the bound table are forwarded to the bound robot's voice device. TTS responses from the agent are routed to the bound robot's speaker. This is the standard pattern in multi-robot human-interaction systems [2.6.9].

**The binding lifecycle.** A binding must survive several state changes: the robot arrives at table 3 (binding established), the customer places an order (binding active during conversation), the robot departs to deliver another order (binding released), a second robot arrives at table 3 for the next interaction (new binding established with the same table, different robot). If a robot disconnects mid-session — WiFi drop, battery depletion, hardware fault — the binding must be released automatically, the pending tasks must be requeued, and when a replacement robot arrives, a new binding must be established without any manual intervention [2.6.10].

**→ Gap.** Dynamic binding is a known pattern in multi-robot interaction. No prior restaurant system has implemented table→robot→voice-device binding where (a) the binding is established by the dispatcher as a side effect of task state (robot reaches IN_PROGRESS at a table → bind), (b) the binding routes both voice capture commands (tablet → backend → robot microphone) and voice reply playback (agent → backend → robot speaker), (c) the binding is released automatically on task completion or robot disconnection, and (d) a replacement robot inherits the binding without customer-visible interruption. This gap motivates the voice bridge and dynamic binding mechanism in §4.7.

---

### 2.6.3 Telemetry, Liveness, and Fault Recovery

Coordinating multiple robots requires knowing where each robot is, whether it is operational, and what to do when it stops responding.

**Telemetry architecture.** Two patterns exist for storing real-time robot state [2.6.11]:

- **RAM-only latest-value store.** Each robot's current pose and battery percentage are stored in a thread-safe in-memory dictionary, overwritten on each update (typically at 4+ Hz via WebSocket heartbeats). Reads are lock-free and sub-microsecond — the dispatcher can score robot proximity without database I/O. The trade-off: state is lost on server restart. A cold-start recovery mechanism must reconstruct state from the last known position.

- **Database write-per-heartbeat.** Each heartbeat writes the robot's pose and battery to a database row. State persists across restarts — after a crash, the server restarts with the last known position of each robot. The trade-off: writing at 4+ Hz per robot (12–20 writes/second for a 3–5 robot fleet) creates write contention on a single-writer database.

The hybrid approach — RAM for real-time dispatch, periodic database snapshot (every 15 seconds) for cold-start recovery — is a known architectural pattern in robotics telemetry systems [2.6.12]. It provides lock-free real-time reads for the dispatcher and approximate state recovery for restart scenarios without the write-amplification cost of per-heartbeat SQL writes.

**Liveness monitoring.** A robot that maintains an open WebSocket connection but has a hung or crashed control process can appear connected while producing no telemetry updates and responding to no commands. WebSocket connection liveness alone is insufficient — the application layer must independently verify that the robot is actively communicating [2.6.13]. The standard defense is a heartbeat watchdog: each robot sends periodic heartbeat messages containing its current state at a fixed frequency. A separate monitoring thread tracks the time since the last heartbeat from each robot. If the elapsed time exceeds a configurable threshold — typically 30 seconds — the robot is declared offline regardless of its TCP connection state. The watchdog closes the zombie WebSocket, marks the robot offline in the database and RAM, and triggers task recovery [2.6.14].

**Task recovery on failure.** When a robot is declared offline, its in-flight tasks cannot be completed. The standard recovery procedure: (a) all tasks currently assigned to the offline robot are requeued to PENDING status, (b) the robot's voice binding to any table is released, (c) its WebSocket connection is closed, and (d) on the next dispatcher cycle, the requeued tasks are eligible for reassignment to other available robots [2.6.15]. Prior work on fault-tolerant task reassignment in multi-robot systems establishes this requeue-and-reassign pattern.

**→ Gap.** Telemetry, liveness monitoring, and fault recovery are individually well-understood patterns. No prior restaurant system composes them into a single lightweight dispatcher that simultaneously handles: (a) RAM-based real-time pose scoring for nearest-idle dispatch with periodic database snapshot for cold-start recovery, (b) heartbeat watchdog with configurable timeout and automatic zombie connection cleanup, (c) task requeue and voice binding release on robot failure, and (d) business-event-driven task creation — where the task source is not a human dispatcher but the AI agent's tool calls. The individual patterns are known; their composition into a restaurant-specific dispatcher driven by an AI agent is the gap.

---

### 2.6.4 Real-Time Restaurant State Synchronization

Restaurant operations involve multiple roles that need different views of the same underlying state. The kitchen needs to see orders as they are confirmed. The customer tablet needs to see cart updates, agent responses, and payment status. The manager dashboard needs to see table occupancy, robot positions, and order throughput. The robot needs navigation goals and task status. All roles must see state changes in real time — a kitchen display that learns about a new order on its next 10-second poll cycle adds an average 5 seconds of latency before cooking begins, which compounds across every order in the queue [2.6.16].

**The evolution of restaurant software.** Restaurant management systems have evolved through several generations, each addressing one role:

- **Point-of-sale (POS) systems.** The core transactional system — orders, payments, receipts [2.6.17]. Designed for a single terminal operated by a cashier or waiter. State is local to the POS device; other roles (kitchen, manager) have no real-time access to order status.

- **Kitchen display systems (KDS).** A dedicated screen in the kitchen showing order tickets. Typically operates on a polling model — the KDS polls the POS or order database every 5–10 seconds for new orders [2.6.18]. Acceptable for a human cook who glances at the screen periodically. Unacceptable for a system where the order's creation, status advancement, and completion must trigger downstream events (robot dispatch, customer notification) with sub-second latency.

- **QR-code ordering applications.** Proliferated during COVID-19: customers scan a QR code at their table, browse the menu on their phone, and place orders without a human waiter [2.6.19]. These systems replace paper menus with a digital interface but maintain the same single-function architecture — the ordering app does not communicate with the kitchen display in real time, and neither communicates with a robot fleet or an AI agent.

All three generations share a fundamental architectural limitation: each system serves one role, with polling-based refresh, and no shared real-time state across roles.

**WebSocket push for real-time synchronization.** WebSocket provides a persistent, full-duplex TCP connection between client and server, enabling the server to push events to clients as they occur [2.6.20]. This is the standard technology for real-time web applications — chat applications, live sports scores, financial trading dashboards — where state changes must be reflected on all connected clients within milliseconds of occurring.

Applied to a restaurant, WebSocket enables a fundamentally different architecture: the server is the single source of truth, and every connected client receives state changes as server-pushed events. An order is created by the AI agent → server emits `order.created` → kitchen panel receives it immediately. The order status is advanced to completed by kitchen staff → server emits `order.updated` → dispatcher creates a delivery task. The robot moves toward the table → server emits `robot.updated` with pose data → fleet dashboard updates the minimap in real time [2.6.21].

**Role-based pub/sub.** Not every event is relevant to every client. The kitchen panel needs `order.created` and `order.updated` but not `robot.updated` or `voice.reply`. The customer tablet needs `voice.reply` and `cart.updated` but not `task.assign`. The robot needs `task.assign` and `task.cancel` but not `order.created`. Role-based publish-subscribe routes each event to the correct subset of connected clients based on their declared role at connection time [2.6.22]. Four role types are needed: `panel` (kitchen and fleet dashboards — anonymous broadcast), `customer` (tablet — filtered by table_id), `robot` (bidirectional, indexed by robot_id), and `voice-device` (server-to-client only, indexed by robot_id for microphone arming and speaker output).

**Session lifecycle enforcement.** A restaurant service session follows a defined business process: a party checks in → a table is assigned → orders are placed → payment is requested → payment is verified → the session closes and the table is freed. This is not a sequence of independent API calls — it is a state machine with guarded transitions [2.6.23]. The backend must enforce that orders can only be placed within an active session, that payment can only be requested when at least one order is confirmed, that a table cannot be seated when it is already occupied, and that a session cannot be closed until payment is verified.

Prior restaurant management platforms (Toast, Square, Lightspeed) implement session lifecycle enforcement as proprietary, closed-source logic [2.6.24]. The session state machine is internal to the platform and exposed to external systems only through user-facing workflows. No prior platform exposes the session lifecycle as a REST API that an external AI agent can programmatically drive.

**Embedded database.** SQLite is the standard choice for embedded, single-writer applications: serverless (no separate database process), zero-configuration (a single file on disk), and ACID-compliant [2.6.25]. Write-Ahead Logging (WAL) mode enables concurrent reads during writes — multiple WebSocket clients reading order state while the backend writes a new order. At restaurant scale — dozens of orders per hour, not thousands per second — SQLite's throughput is far beyond the workload. The alternative, a client-server RDBMS (PostgreSQL, MySQL), adds deployment complexity with no benefit at this scale.

---

### → Overall Gap for §2.6

No prior restaurant system integrates: (a) a REST API for transactional business operations (orders, payments, sessions), (b) a WebSocket hub with role-based fan-out for real-time multi-client state synchronization — where 4+ distinct client types receive filtered event subsets pushed as they occur rather than on a polling cycle, (c) a session lifecycle enforced as guarded state transitions by the backend rather than by human workflow, (d) an embedded SQLite database in WAL mode with schema migrations supporting restaurant entities (tables, sessions, orders, dishes, robots, tasks, payments), and (e) an external AI agent as the primary event driver — the agent confirms orders (→ `order.created`), requests payment (→ `payment.requested`), and dispatches robots (→ `task.created`), with all roles downstream of the agent's decisions.

Four operational capabilities are needed to connect an AI agent's decisions to restaurant reality. Each capability has been addressed individually in prior work, but no system composes them into a single lightweight backend:

1. **Lightweight AI-driven fleet dispatch.** Nearest-idle task assignment with battery filtering, where tasks are created programmatically by the agent's tool calls rather than by human operator selection.
2. **Dynamic robot-table voice binding.** Table-to-robot microphone and speaker binding established on robot arrival and released on departure, surviving robot disconnection through automatic re-binding.
3. **Telemetry, liveness, and fault recovery.** RAM-based real-time pose store for dispatch scoring, periodic DB snapshot for cold-start recovery, heartbeat watchdog with automatic zombie cleanup.
4. **Real-time multi-role state synchronization.** REST API for transactional writes, WebSocket hub with role-based pub/sub for push-based state synchronization, session lifecycle enforced as guarded state transitions, embedded SQLite in WAL mode — all driven by an AI agent as the primary event source.

These gaps motivate the orchestrator architecture in §4.7 and the fleet dispatcher and voice bridge within it.
