## 2.6 Backend Orchestration & Fleet Management

> *A restaurant running robots needs four things to hold together at once: some rule for deciding which robot takes which job, some way of knowing which robot is standing at which table, some account of which robots are still alive, and some arrangement by which the customer's tablet, the kitchen display, the manager's dashboard, and the robots themselves are all looking at the same facts. This section surveys the prior work addressing each, drawn from warehouse robotics, multi-robot interaction, distributed-systems practice, and commercial restaurant software.*
>
> **Cross-refs:** §2.1 (overview — restaurant software limitation), §2.2 (navigation goals), §2.7 (client interfaces and transport mechanisms), §4.1 (backend requirements), §4.7 (orchestrator — proposed method), §5.5 (system integration tests)
> **Citations:** [2.6.1]–[2.6.25]; final numbering assigned when all Ch.2 references are merged. Bibliographic entries for this section are pending — see `references.md`.
> **Figures and tables:** keyed section-scoped (`Table 2.6a`, …) so that this section can be edited independently. Flatten to sequential chapter numbering on merge, in order of first appearance.

---

The literatures surveyed in this section were written for different settings and rarely cite one another. Task assignment comes from warehouse robotics, where fleets are large and trips are long. Device binding comes from multi-robot human interaction, where the question is which machine a person is addressing. Telemetry and liveness come from distributed systems practice, where the problem is knowing whether a remote process is still working. Restaurant operations come from commercial software, where the problem is recording what was ordered and telling the kitchen to cook it.

Each body of work is mature within its own setting. What none of them was written for is the case where the four problems occur together, at the scale of a single dining room, with the sequence of events originating from software rather than from a person.

---

### 2.6.1 Multi-Robot Task Assignment

When a delivery becomes available and more than one robot could carry it, something must choose. The multi-robot systems literature offers a spectrum of answers distinguished chiefly by how much coordination they are willing to pay for [2.6.1].

At the simplest end, greedy assignment filters the fleet to those robots currently available and selects whichever is closest to the target, by straight-line distance or by estimated travel time [2.6.2]. It requires no negotiation between robots, no shared plan, and no lookahead, and its cost is that it optimizes each assignment in isolation: a robot committed to a nearby job may have been the only one well placed for a job that arrives moments later. Auction and market-based methods address this by having robots bid on tasks according to their own state — distance, remaining charge, queue depth, estimated completion — with an auctioneer awarding to the best bid [2.6.3]. The bidding admits richer criteria than proximity and balances load across a heterogeneous fleet, at the cost of a negotiation round per task and a protocol the fleet must agree on. These methods were developed for and are deployed in warehouse settings, where trips of tens to hundreds of metres make the difference between a good assignment and a merely adequate one substantial enough to justify the overhead [2.6.4]. A third consideration cuts across both: robots whose charge is insufficient to complete a job should not be considered for it, and energy-aware assignment treats remaining charge as an eligibility condition rather than a scoring term, on the reasoning that a robot stranded mid-task costs more than a suboptimal assignment [2.6.5].

**Table 2.6a** — Task assignment strategies for multi-robot fleets.

| Strategy | Coordination required | Optimizes | Sensitive to trip length | Documented deployment setting |
|---|---|---|:---:|---|
| Greedy nearest-available | None — centralized lookup | Each assignment independently | Weakly | Small fleets; commercial service robots with operator-selected destinations |
| Auction / market-based | Bidding round per task | Fleet-wide allocation | Strongly | Warehouse AGV fleets [2.6.4] |
| Energy-aware filtering | None — an eligibility predicate | Completion reliability | Not applicable | Applied alongside either of the above [2.6.5] |

The distinction that matters for a restaurant is one of scale rather than of algorithm. The advantage auction methods hold over greedy assignment grows with the cost of a poor choice, which grows with trip length; over the distances separating a kitchen from tables in one room, the two approaches will frequently choose the same robot, and where they differ the difference is seconds. The published comparisons, however, are conducted at warehouse scale, so the point at which the advantage becomes negligible is not established.

Beyond the algorithms, two categories of fleet infrastructure exist. ROS2's Open-RMF provides scheduling across heterogeneous fleets with traffic deconfliction, lift and door integration, and multi-floor coordination — an infrastructure built for buildings, not rooms [2.6.6]. Commercial platforms from the service-robot manufacturers offer fleet dashboards for their own hardware, each closed to its vendor's ecosystem and exposing no interface through which an external system might create a task or observe one completing [2.6.7]. Between a framework scaled for buildings and a dashboard scaled for one manufacturer's robots, the surveyed work leaves unexamined the case of a handful of robots in a single room whose jobs are generated by another piece of software rather than entered by a person.

---

### 2.6.2 Dynamic Robot-Table Voice Binding

A robot that carries a microphone and a speaker introduces a question that a robot carrying only a tray does not. Any robot can deliver to any table, so robots are interchangeable with respect to delivery. They are not interchangeable with respect to speech: a customer speaking at one table is audible to the machine standing beside them and not to the machine three tables away, and a reply is heard from wherever the speaker producing it happens to be. Voice is bound to physical proximity in a way that a delivery is not, and something must maintain the correspondence between a place and the machine currently occupying it [2.6.8].

Three arrangements appear in the multi-robot interaction literature. Permanent assignment gives each location its own dedicated machine, which removes the question entirely and with it the flexibility that made the fleet worth having: a robot assigned to one table is unavailable to another even while idle, and a table whose robot is charging has no voice service at all. Broadcasting sends every capture command and every reply to the whole fleet, which requires no correspondence to be maintained but produces speech from the wrong machines and captures audio from locations other than the one being addressed. Presence-based binding establishes the correspondence when a machine arrives somewhere and dissolves it when the machine leaves, which is the arrangement the interaction literature generally adopts [2.6.9], and which trades the previous two problems for the requirement that arrival and departure be detected reliably and that the binding survive whatever happens between them.

**Table 2.6b** — Approaches to associating a location with a speech-capable machine.

| Approach | Correspondence maintained by | Fleet flexibility | Failure mode |
|---|---|:---:|---|
| Permanent assignment | Configuration; fixed at deployment | None — machines are not reusable across locations | A machine unavailable leaves its location without service |
| Broadcast to fleet | Nothing — every machine receives everything | Full | Speech emitted from and captured at the wrong locations |
| Presence-based binding | Arrival and departure events | Full | Depends entirely on arrival and departure being detected correctly |

That last failure mode is the one the surveyed work leaves least examined. A binding established on arrival is correct only while the arrival remains true, and the events that can falsify it are not all orderly departures: a machine may lose its network connection while standing where it was, may stop responding while still holding an open connection, or may be reassigned elsewhere mid-interaction. The literature describes binding as a lifecycle with two transitions, established and released, which is a sufficient account where machines are assumed to remain reachable. What it does not treat is the case where the arrangement must degrade — where the correspondence must be revoked by something other than the machine that holds it, on evidence weaker than a departure message, and re-established afterward without the person at that location being required to notice that anything occurred.

---

### 2.6.3 Telemetry, Liveness, and Fault Recovery

A fleet whose members are moving produces a continuous stream of position and status data, and the arrangement that receives it faces a well-documented tension. Written to durable storage, each update contends with whatever else that storage is doing, and a fleet reporting several times a second per robot generates a write load out of proportion to the value of any individual reading — the value of a position lies almost entirely in it being the current one. Held only in memory, the data is available without contention and lost on restart. The pattern documented for this class of data keeps the working copy in memory and writes to storage periodically rather than per update, on the reasoning that what must survive a restart is an approximate last-known position rather than a complete history [2.6.11]–[2.6.12].

**Table 2.6c** — Storage patterns for high-frequency telemetry.

| Pattern | Contention with transactional writes | Survives restart | Data retained |
|---|:---:|:---:|---|
| Write per update | High — proportional to fleet size and report rate | ✓ | Complete history |
| In-memory only | None | ✗ | Current values |
| In-memory with periodic snapshot | Low — independent of report rate | Approximately | Current values; last snapshot after restart |

Separately from where the data is kept is the question of what its absence means. A process that has crashed cleanly closes its connection and is easily detected. A process that has hung does not: it holds its connection open, satisfies any check performed at the transport layer, and reports nothing. Because the transport cannot distinguish a working process from a stalled one, liveness must be established at the application layer by requiring positive evidence at intervals and treating silence beyond some tolerance as failure [2.6.13]. What follows from a declaration of failure is the recovery procedure, and the pattern documented for fault-tolerant multi-robot systems is to return the failed member's outstanding work to the pool for reassignment rather than to wait for its return [2.6.14]–[2.6.15].

These three concerns — where telemetry lives, how liveness is established, what recovery does — are documented separately and in different literatures, and each is treated as a self-contained problem. What is less examined is that they are not independent in a system that also assigns work. The assignment decision reads positions, and positions come from telemetry; the eligibility of a robot to receive work depends on whether it is alive, which is the liveness question; and recovery returns work to the same assignment mechanism that dispatched it. Whether the tolerances appropriate to each concern in isolation remain appropriate when the three are coupled — whether a liveness timeout chosen to avoid false alarms is compatible with an assignment loop that must not offer work to a machine that has already stopped — is not a question the separate treatments raise.

---

### 2.6.4 Real-Time Restaurant State Synchronization

Restaurant software has accumulated in layers, each addressing one role. Point-of-sale systems record orders and payments for the person operating the terminal [2.6.17]. Kitchen display systems present tickets to the person cooking, typically refreshed by polling on an interval of seconds, which is unobjectionable for a display a cook glances at periodically [2.6.18]. Customer-facing ordering applications, widely adopted during the pandemic, let a diner browse and order from their own device [2.6.19]. Each generation solved the problem in front of it and each is internally coherent.

What they have in common is more consequential than what distinguishes them: each maintains its own state for its own consumer, and the consumer is in every case a person reading a screen. The kitchen display does not know the customer application's cart. The ordering application does not know the kitchen's queue depth. Neither knows anything about a robot. Where information does cross between them, it crosses through a person or through a periodic reconciliation, and the interval of that reconciliation is chosen against human tolerance for staleness rather than against any machine's requirement.

The transport mechanisms available for closing that interval — polling, persistent bidirectional connections, and unidirectional server-initiated streams — are mature, well documented, and surveyed in §2.7.4, where they bear on the client interfaces that consume them. The observation belonging here concerns not the mechanism but what the surveyed systems do with it. Commercial restaurant platforms do propagate state internally in something close to real time; the propagation is not the missing capability. It is that the propagation terminates at the vendor's own applications. There is no documented interface by which an external process might subscribe to an order being created, and correspondingly no expectation that anything other than the vendor's own software would want to.

Underneath the display question is a structural one. A visit proceeds through a sequence — a party is seated, orders accumulate, a bill is settled, the table is released — in which the permissible next steps depend on the current position, and the sequence is a state machine whether or not it is implemented as one [2.6.23]. Where the transitions are driven by staff, the constraints are enforced by the workflow: a person does not settle a bill for a table nobody is sitting at, and the software need not prevent it. Commercial platforms implement these lifecycles internally and expose them through the interfaces staff use rather than as operations a program could invoke [2.6.24]. The question of what enforcement is required when the entity driving the transitions is not a person, and cannot be relied upon to observe an implicit workflow, does not arise in systems built on the assumption that it always is one.

At the scale of a single restaurant, the storage question is settled and worth stating only briefly. An embedded database serving one writer handles dozens of transactions an hour with several orders of magnitude of headroom, and the concurrency mode that permits reads to proceed during writes is standard [2.6.25]. The interesting constraints in this section are not throughput constraints.

---

The four problems surveyed here are addressed in four separate literatures, and the accounts are individually adequate. Read together, they share an assumption about who or what the state is for.

In every system surveyed, operational state is maintained in order to be *rendered*. The point-of-sale terminal holds the order so that a cashier can see it; the kitchen display holds the queue so that a cook can work through it; the fleet dashboard holds robot positions so that an operator can watch them; the warehouse scheduler holds the plan so that it can be executed by machines whose only role is to execute it. In each case the state has one intended consumer, that consumer is a person looking at a screen or a machine carrying out an instruction, and the interfaces are shaped accordingly — refresh intervals set against human patience, event vocabularies internal to the vendor, lifecycle constraints enforced by the order in which a person is expected to press buttons.

A system in which an autonomous component conducts the conversation, decides what has been ordered, and dispatches the machine that delivers it inverts that arrangement. State must be readable by programs as well as rendered to people; it must be writable by something that has not been trained to follow an implicit workflow, and therefore explicitly constrained; and every consumer — the person cooking, the person at the table, the person managing the floor, and the machine crossing it — must be reading the same facts at the same time, because the component coordinating them is not present in the room to reconcile discrepancies. None of the surveyed work is wrong about its own setting. What none of it supplies is an account of operational state designed to be consumed by something that is not a person.
