## 5.5 Backend and Web Infrastructure Checks

The backend orchestrator and the three web interfaces are not evaluated as contributions. They
exist so the agent has somewhere to write and the restaurant has somewhere to read, and the
question this section answers is narrower than the ones §5.4 answers: whether that infrastructure
stays out of the way. Three properties were instrumented, namely how fast the API answers,
whether a dispatched task completes its lifecycle, and whether every role converges on the same
state once the agent has changed it. Everything else about the backend is presented as designed
in §4.7 and left unmeasured; the end of this section states what that leaves open.

---

### 5.5.1 API Responsiveness

The claim made in §4.7 is that a push-based design replaces the polling cycle conventional
kitchen display systems rely on. The precondition for that claim is that the REST layer is fast
enough that no client needs to poll in the first place. Every endpoint was exercised with one
hundred samples after two warmup requests, against the live orchestrator. A hundred samples
rather than ten because a tail is what matters here, and at ten samples the 99th percentile is
just the maximum observation.

**Table 5.16.** REST endpoint latency (n = 100 samples per endpoint).

| Endpoint | p50 (ms) | p95 (ms) | p99 (ms) |
|----------|:---:|:---:|:---:|
| GET /menu | 1.0 | 1.5 | 1.6 |
| GET /tables | 1.0 | 1.4 | 1.6 |
| GET /tables/{id} | 0.9 | 1.3 | 1.6 |
| POST /seatings | 0.9 | 1.7 | 2.0 |
| GET /orders | 2.4 | 2.9 | 4.0 |
| POST /orders | 0.7 | 1.2 | 9.0 |
| GET /payments | 1.0 | 1.5 | 1.9 |
| GET /robots | 0.9 | 1.4 | 1.5 |
| GET /tasks | 1.0 | 1.4 | 1.7 |
| GET /layout | 0.7 | 1.0 | 1.2 |
| POST /voice/event | 0.7 | 1.0 | 1.3 |
| POST /voice/listen | 0.7 | 0.8 | 1.2 |

Eleven of the twelve endpoints answer within 4 ms at the 99th percentile, and their spread
between p50 and p99 stays under 2 ms. Write endpoints are as fast as read endpoints, which is
expected for SQLite at a data volume where the working set is a few dozen rows. Two and then four
simultaneous requests were also issued, all of which succeeded, at 95th-percentile latencies of
1.8 ms and 5.3 ms.

One endpoint behaves differently and the larger sample is what exposes it. `POST /orders` answers
in 0.7 ms at the median and 9.0 ms at the 99th, a tail thirteen times its typical case, where
every other endpoint stays within a factor of two. The likely cause is SQLite's write lock, which
serialises the one endpoint on the critical path of order creation. At this scale the absolute
figure is still small enough not to matter, but the shape is worth recording, because it is the
one place in the backend where a queue can form and it is invisible at the ten-sample size the
first version of this benchmark used.

Read against the agent's own median turn latency of 2.15 s from §5.4.6, the backend contributes
roughly one twentieth of one percent of a conversational turn. Whatever limits this system's
responsiveness, it is not the orchestrator, and the decision to keep business state in one small
relational file rather than a distributed store costs nothing at this scale. Against the 5 to 10
second poll cycle of the kitchen display systems surveyed in §2.6.3, an endpoint answering in
1 ms means the interval between a state change and a client learning about it is bounded by the
notification mechanism rather than by the database.

---

### 5.5.2 Fleet Task Lifecycle

The dispatcher described in §4.7 assigns delivery and call tasks to robots, tracks their
liveness, and returns them to the dock when idle. One full lifecycle was driven with a mock robot
connected over WebSocket in the robot role.

**Table 5.17.** Robot state transitions through one task lifecycle.

| Step | Robot status | Reported activity |
|------|-------------|-------------------|
| Before connection | `offline` | none |
| WebSocket connect and heartbeat | `idle` | Đang ở dock |
| Task created (call, table 1) | `busy` | Đang tới bàn 1 (gọi phục vụ) |
| `task_done` message received | `returning` | Đang về dock |
| `at_dock` message received | `idle` | Đang ở dock |

The task advanced through its own state machine in parallel, from PENDING to ASSIGNED to DONE.
This exercises the dispatcher end to end: a task created by a business event is matched to an
available robot, the assignment is pushed to that robot over its socket, and the robot's own
progress reports drive both its status and the task's.

The trace carries more weight than its size suggests, because it is the only measurement anywhere
in this chapter that touches the coupling §2.2.5 identified as the central gap on the navigation
side, where a navigation goal originates in a business event rather than in an operator's choice
of waypoint. What it establishes is that such a goal reaches the robot and that the round trip
completes. What it does not establish is anything about physical execution, which is §5.3's
subject and was not measured.

One property of the design is visible in the trace. The robot's status is derived from the
messages it sends rather than assumed from the task state, so a robot that accepts a task and
then goes quiet does not continue to appear busy.

---

### 5.5.3 Multi-Role Convergence

Four roles observe the restaurant at once: the entrance kiosk seats guests, the agent creates
orders, the management panel monitors the floor, and the customer tablet shows one party its own
order. The design claim is that all four read a single source of truth. The check drives a
seating through the kiosk path and an order creation through the agent path, then queries each
role's own endpoint.

**Table 5.18.** Role views before and after an agent-driven state change.

| Role | Endpoint | Before | After |
|------|----------|--------|-------|
| Kiosk (seating) | `POST /seatings` on table 3 | `TRONG` | `DANG_PHUC_VU`, party_size 4 |
| Agent (order) | `POST /orders` on table 3 | no order | order created, 245,000 ₫ |
| Panel (monitor) | `GET /orders` | not listed | listed |
| Customer (tablet) | `GET /tables/3` | `TRONG` | `DANG_PHUC_VU`, current_order_id set |
| Admin | `POST /admin/reset` | | all tables freed |

Every role reflects the change within a single request and response cycle. The tablet learns the
order identifier from the same `tables` record the kiosk wrote to, and the panel reads the same
`orders` table the agent wrote to, so there is no synchronisation step between roles that could
lag or fail. The table's transition from `TRONG` (free) to `DANG_PHUC_VU` (being served) is
written once and read by three different consumers.

---

### What Was Not Measured

Four measurements were designed and not taken, and together they bound what the three checks
above support.

**Event propagation latency.** The benchmark connected successfully in both the panel and
customer roles but collected no events, because the orchestrator was idle during the measurement
window and propagation requires agent-driven traffic to observe. Measuring it properly means
stamping each event server-side at emission and again at the client on receipt, over a run in
which the agent is actively creating orders. The claim that push delivery beats polling therefore
rests on the endpoint figures above and on the architecture, not on a direct measurement of the
push path itself.

**Session isolation under concurrent load.** No test ran two or three simultaneous voice sessions
at different tables ordering overlapping dishes and reported a cross-session leakage count. The
property is argued from the session-keyed conversation memory of §4.7.2 and supported by the
absence of contamination across the scenarios in §5.4.5, each of which ran against its own table
identifier and its own thread. That absence is evidence rather than nothing: an earlier revision
of the end-to-end runner derived its thread identifier from the scenario name alone, so repeated
runs resumed the previous run's conversation and inherited its cart, and the defect was caught
precisely because cart contents that did not belong appeared in a transcript.

**The fleet failure path.** Watchdog detection time, task requeue latency after a robot
disconnects mid-task, and voice rebinding to a replacement robot were not exercised. Recovery is
argued structurally, from the dispatcher re-attempting assignment of all pending tasks on every
robot connect and disconnect event, which means a task orphaned by a disconnect is picked up when
any robot next becomes available. That is a design argument rather than a measurement, and
§5.5.2 should be read as validating the happy path of the lifecycle only.

**Browser-visible update latency.** The convergence check polls REST endpoints rather than
observing the WebSocket-driven interface, so it establishes that the four roles converge on
backend state, not how quickly a change becomes visible on a screen. The order counts underlying
it are also not a clean baseline, because the fleet lifecycle check ran immediately beforehand in
the same process and left a task and an order behind. Convergence across roles is what the check
establishes, and that holds; the absolute counts should not be read as a controlled
before-and-after.
