## 4.6 Robot Dispatch & Fleet Management

> **Status:** draft
> **Cross-refs:** §4.5 for orchestrator and WebSocket hub, §4.5.5 for session lifecycle, Chapter 3 for ROS2 navigation
> **Source:** `src/server_orchestrator/services/dispatcher.py` (469 lines), `fleet.py` (60 lines)
> **Figures needed:** Fig 4.6 (task lifecycle state diagram: PENDING → ASSIGNED → IN_PROGRESS → DONE)

---

The dispatch system translates business events into robot tasks and assigns them to available robots. It operates between the orchestrator's REST API (where business events originate) and the WebSocket hub (where robots receive commands). The dispatcher is the "shift manager" — it never moves anything itself; it decides which robot should serve which table at which time.

### 4.6.1 Telemetry Architecture

Robot state has two components with different access patterns: persistent identity and assignment (which robot is doing what), and transient telemetry (where the robot is right now and its battery level). These are stored in different layers with different update frequencies.

#### RAM-Only Latest-Value Store

Robot pose (x, y) and battery percentage are stored in a thread-safe Python dictionary in memory — not in the SQLite database (`fleet.py:17`). This design decision follows from the access pattern:

| Characteristic | Pose/Battery | Identity/Assignment |
|---------------|-------------|---------------------|
| **Update frequency** | 4+ Hz (every ~250ms while driving) | Once per task lifecycle event (seating, arrival, done) |
| **Staleness tolerance** | Losing one tick is harmless — the next heartbeat (~250ms later) overwrites it | Must be exactly correct — wrong assignment means wrong robot dispatched |
| **Read frequency** | Every dispatcher scoring loop, every panel minimap refresh | On panel load, robot overview |
| **Storage** | RAM (`fleet.py`, `_live` dict) | SQLite (`robots` table) |

Writing sensor-frequency telemetry to SQLite would create write contention — SQLite uses file-level locking, and a write per heartbeat at 4 Hz per robot would compete with order and payment writes. The RAM store avoids this: `fleet.update()` (`fleet.py:20-30`) is a lock-protected dictionary mutation with zero I/O.

The `fleet.overlay()` function (`fleet.py:47-60`) merges live telemetry onto a database row for consumers that need the complete robot state:
- `GET /robots` — the REST endpoint returns DB identity fields with live pose/battery overlaid.
- `_broadcast_robot()` — the panel broadcast includes live pose for the minimap.
- `_pick_robot()` — the dispatcher scores robots by their *current* Euclidean distance to the target, not their last-snapshotted position.

#### Periodic Database Snapshot

Although telemetry lives in RAM, a periodic snapshot is written to the `robots` table every 15 seconds (`dispatcher.py:281-288`). This serves cold-start recovery: after an orchestrator restart, the panel can show where robots were last reported, and the dispatcher has a starting position for distance scoring until the next heartbeat arrives. The snapshot uses `COALESCE(?, current_value)` to only update non-null fields — if a robot reports only battery (no position change), only battery is persisted.

#### Pose Broadcast Throttling

Robot pose is broadcast to the panel WebSocket at a **maximum of 5 Hz** per robot (`POSE_BCAST_EVERY = 0.2s`, `dispatcher.py:39`). Heartbeats may arrive faster (the robot streams position updates at its control loop rate), but the minimap animation only needs 5 updates per second — higher rates are imperceptible at the 30 fps browser rendering cap and only increase WebSocket traffic. The throttle timestamp is maintained per robot in `_last_pose_bcast` (`dispatcher.py:38`).

### 4.6.2 Task Assignment — Nearest-Idle Algorithm

The dispatcher uses a **nearest-idle algorithm** for task assignment — the simplest strategy, and sufficient for a small restaurant environment (6 tables, short 3–5m trips, 1–3 robots).

#### Task Model

A task is a self-contained service unit with a lifecycle:

```
PENDING → ASSIGNED → IN_PROGRESS → DONE
   │                                    │
   └──────────── CANCELLED ←────────────┘
         (table ended, robot hung)
```

| State | Meaning | Trigger |
|-------|---------|---------|
| **PENDING** | Task created, waiting for a free robot | Business event (seating, order done, call button) |
| **ASSIGNED** | Assigned to a specific robot, waiting for acceptance | `try_assign()` picks a robot |
| **IN_PROGRESS** | Robot has accepted and is executing | Robot sends `task_accepted` |
| **DONE** | Task completed successfully | Robot sends `task_done` |
| **CANCELLED** | Task aborted (table ended, robot went offline) | Table close or watchdog |

**Three task kinds** (`dispatcher.py:9`):

| Kind | Triggering Event | Robot's Behavior | Activity Label |
|------|-----------------|------------------|----------------|
| `go_to_table` | Kiosk seating (`POST /seatings`) | Navigate to table, wait for customer to order, release when order confirmed | "Đang phục vụ · Bàn N" |
| `deliver` | Order status → `XONG` (kitchen marks done) | Navigate to table, wait for handoff, auto-return to dock | "Đang giao món · Bàn N" |
| `call` | Guest presses "Gọi Robot" button | Navigate to table, wait for assistance, release on order/payment | "Đang hỗ trợ · Bàn N" |

#### Assignment Logic

`try_assign()` (`dispatcher.py:173-225`) runs on every task creation and robot state change:

1. **Query all PENDING tasks**, ordered by `created_at` (FIFO — oldest request served first).
2. **For each task, find the best robot** via `_pick_robot()`:
   - Filter: robots with `status = 'idle'` in the database.
   - Filter: robot's WebSocket connection must be alive (`manager.connected_robot_ids()`).
   - Filter: battery from RAM telemetry must be `≥ MIN_BATTERY (20%)` or `None` (unreported — assume charged).
   - Score: Euclidean distance from robot's live pose `(x, y)` to the target table's waypoint `TABLE_POS[table_id]`. Robots with no pose reported default to the dock position `(0, 0)`.
   - Select the robot with the minimum score (nearest to target).
3. **Assign and push.** In a SQLite transaction:
   - Update task: `status = ASSIGNED`, `robot_id = chosen_robot`.
   - Update robot: `status = busy`, `current_task_id = task.id`, `activity = human-readable label`.
4. **Deliver over WebSocket** (outside the transaction). Send `task.assign` with `{task_id, kind, table_id}` to the chosen robot. If delivery fails (robot disconnected between assignment and push), requeue the task.

**FIFO ordering with nearest-idle scoring** means the oldest task gets the nearest available robot — not necessarily the globally optimal assignment. This is a greedy approximation; optimal assignment (Hungarian algorithm) would require solving a bipartite matching problem, which adds complexity with negligible benefit at a scale of 3–5 robots and 6 tables.

**Table waypoints** (`dispatcher.py:51-58`). The dispatcher knows pre-configured (x, y) waypoints for each table and the dock. These are used *only* for nearest-robot scoring — the robot navigates autonomously using its own Nav2 stack (Chapter 3). The waypoints are static per table and do not change unless the restaurant layout changes.

#### Task Lifecycle Callbacks

Robots report status changes over WebSocket, and the dispatcher responds:

**`on_accepted`** (`dispatcher.py:297-307`). The robot confirms it received the task and is beginning execution. The task is marked `IN_PROGRESS`.

**`on_arrived`** (`dispatcher.py:310-334`). The robot has reached the table's approach waypoint. Two things happen:
1. The robot's activity label changes from "Đang tới bàn N" (traveling) to "Đang phục vụ · Bàn N" (serving). For `go_to_table` and `call` tasks, the robot now waits at the table until released — the customer can speak their order. For `deliver` tasks, the robot hands off the food and auto-returns to dock.
2. **Voice binding is established.** `manager.bind_table_robot(table_id, robot_id)` records that this robot now serves this table. All subsequent "Talk to AI" presses from the tablet route to this robot's microphone. The binding persists until the robot leaves or disconnects.

**`on_done`** (`dispatcher.py:337-354`). The task is marked `DONE`. The robot is freed (`status = idle`, `current_task_id = NULL`). The voice binding is cleared (`manager.unbind_robot(robot_id)`). The dispatcher calls `try_assign()` to give the freed robot another queued task.

**`release_robot_at_table`** (`dispatcher.py:357-376`). Called by the orders/payments routers when a customer finishes ordering or paying — the robot no longer needs to wait at the table. Sends `task.release` to the robot, which navigates home and reports `task_done`. If no robot is at the table (it already left, or never arrived), this is a no-op.

### 4.6.3 Watchdog & Fault Recovery

Robots can fail silently: a Jetson might freeze, a network cable might unplug without the TCP socket closing (leaving the WebSocket connection half-open), or a process might crash after accepting a task but before reporting completion. The watchdog detects these failures and recovers.

**Heartbeat monitoring.** Each robot sends periodic `heartbeat` messages (pose + battery) over its `role=robot` WebSocket. The dispatcher records the last-seen monotonic timestamp in `_last_seen[robot_id]` (`dispatcher.py:33`). The heartbeat also updates the RAM telemetry store (`fleet.update()`) and triggers a throttled panel broadcast.

**Watchdog loop** (`dispatcher.py:457-469`). A background `asyncio.Task` started at orchestrator startup (`main.py:32`) runs `watchdog_tick()` every `watchdog_interval_s` (default: 5 seconds):

```
watchdog_tick():
    1. Scan _last_seen for robots where (now - last_seen) > heartbeat_timeout_s (30s).
    2. For each stale robot:
       a. Log warning with gap duration.
       b. Call on_robot_disconnect(robot_id):
          - Mark robot offline in DB (status = offline, current_task_id = NULL).
          - Requeue its current task (if any) back to PENDING.
          - Clear voice binding (table no longer routes to this robot's mic).
       c. Force-close the zombie WebSocket via manager.kick_robot(robot_id).
    3. Next tick calls try_assign() — the orphaned task, now PENDING, can be picked up
       by another robot.
```

The 30-second timeout is long enough to survive temporary WiFi hiccups (the robot's Nav2 stack can continue navigating locally during a brief network loss) but short enough to reassign tasks before customers wait too long.

**Hung robot recovery** (`on_robot_disconnect`, `dispatcher.py:242-264`). When a robot disconnects (either detected by the watchdog or by a normal WebSocket close), the dispatcher:
1. Marks the robot `offline` in the database with activity "Mất kết nối".
2. Requeues any current task back to `PENDING` via `_requeue_task()`.
3. Clears the table-robot voice binding — the table's "Talk to AI" returns to "no device" state.
4. `try_assign()` is called after the next task creation or robot reconnection to reassign orphaned tasks.

**Table cleanup** (`cancel_table_tasks`, `dispatcher.py:379-416`). When a table is ended (`PATCH /tables {status: TRONG}`) or payment is verified:
1. All non-DONE tasks for that table are marked `DONE` (cleaned from the queue).
2. Any robot still standing at the table is sent `task.release` to go home.
3. The voice binding is cleared.
4. `try_assign()` is called to give freed robots new work.

**Fault hierarchy.** The system handles three levels of robot failure:
1. **Transient task failure** (robot disconnects mid-task): Task requeued, robot marked offline. Another robot takes over on next `try_assign()`.
2. **Zombie robot** (process frozen, socket still open): Watchdog detects missing heartbeats at 30s timeout, tears down the connection, requeues tasks.
3. **Server restart** (orchestrator crashes and restarts): All robots reconnect over WebSocket, marked idle. Periodic DB snapshots provide last-known positions for panel display. PENDING tasks survive in the database. `try_assign()` runs on reconnection.

#### Design Limitations

The dispatcher makes two simplifying assumptions appropriate for a small restaurant:

1. **Nearest-idle, not optimal assignment.** With 3+ robots and multiple pending tasks, nearest-idle may not minimize total travel time. A market-based or auction-based approach would be necessary for larger fleets but adds complexity unjustified at this scale.

2. **No task prioritization.** Tasks are FIFO by creation time. A late-arriving `deliver` task (hot food waiting) cannot preempt an earlier `go_to_table` task (customer waiting to be seated). In practice, the fleet is small enough that all tasks complete quickly, and the 20% battery threshold prevents a low-battery robot from accepting a task it cannot finish.
