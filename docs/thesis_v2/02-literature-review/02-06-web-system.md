## 2.6 Web System: Backend, Data Storage, and Real-Time Interfaces
Section 2.1.3 described restaurant software as it stands: point-of-sale, kitchen display, and customer ordering applications each hold their own copy of the state they present, and information passes between them through a member of staff or a periodic reconciliation. The literature that would be drawn on to build such a system differently is not one literature but four, one per layer, each mature within its own scope.

Four conditions distinguish a restaurant service system from the applications these four literatures were written for, and they are what the closing paragraph of each subsection tests an option against. The deployment is a single venue with no operations staff, so anything requiring administration is a running cost nobody is there to pay. Some of the clients are robots rather than browsers, so they report as well as receive. One of the interfaces runs on the robot's own embedded computer, alongside the navigation and speech workloads, so its runtime cost is charged against the same budget as motion. And some of the writes come from an autonomous agent rather than from a person filling in a form.

---

### 2.6.1 Backend Framework and API Layer

A web backend is the process that owns an application's state and answers everything that wants to read or change it. In an ordinary business application it carries one kind of traffic: a browser sends a request, a handler runs, a response goes back, and the connection closes. A system that also announces changes as they happen, and that stays in contact with devices reporting on their own schedule, carries a second kind as well, namely connections that open once and stay open for as long as the client is running. Every framework below handles the first kind equally well. They differ in how they accommodate the second, and in how much of a request they check before a handler ever sees it [2.6.1]–[2.6.4].

The difference starts with the concurrency model. The older one is synchronous, standardised for Python as WSGI: a pool of worker threads, one occupied for the whole time it takes to serve a request. That arithmetic works while requests finish in milliseconds and breaks for a connection that stays open for hours, since such a connection holds its worker whether or not data is moving, and a server with sixteen workers can hold sixteen of them and nothing else. The newer model is asynchronous, standardised as ASGI and native to Node.js: one thread runs an event loop that suspends whatever is waiting on input, so an idle connection costs memory and no worker and a single process can hold thousands.

The second distinguishing property is where input validation sits. Boundary validation means the framework is given a declared schema per operation, checks every request against it, and rejects what does not conform before the handler runs. Without it, the same checks are written by hand in each handler, or quietly omitted.

**Table 2.6a** — Backend framework families.

| Framework | Approach | Advantages | Limitations |
|---|---|---|---|
| FastAPI (Python) | ASGI event loop; WebSocket endpoints declared beside the REST routes; Pydantic schema checked before the handler | Persistent connections and state-changing endpoints share one process and one memory; validation and OpenAPI come from the same declaration; thousands of idle connections per process | Younger ecosystem than Flask or Django; asynchronous code is harder to debug; no built-in ORM, admin, or auth |
| Flask (Python) | WSGI worker pool; WebSocket through an extension with its own worker model | Small, simple, very widely taught; large extension ecosystem | A long-lived connection occupies a worker; persistent connections effectively have to run outside the application; validation written by hand |
| Django REST (Python) | WSGI with partial async; WebSocket through Channels as a separate layer; serializer classes | Batteries included (ORM, admin, auth, migrations); mature and well documented | Heaviest of the four; Channels adds a second runtime and usually a broker; prescribed structure is a poor fit for a small service |
| Express / NestJS (Node.js) | Event loop; WebSocket library in the same process; validation by hand under Express, by decorators under NestJS | Native asynchronous model; the largest real-time ecosystem; NestJS adds structure and DI | Puts the backend in a different language from the speech and agent components; validation is optional and easy to skip under Express |

Splitting persistent connections out of the application carries a documented cost that is not about speed. Once the endpoints that change state and the connections that announce those changes run in different processes, neither can see the other's memory, so every announcement travels through a message broker, and each half holds its own idea of what is currently true [2.6.2].

For a restaurant service system the asynchronous single-process families are the ones that fit, and FastAPI has two properties the others lack together. Robots report position continuously over WebSocket while the same backend writes orders and payments, so one process removes both the broker and the second view of the state. More particular to this application, part of the writes come from an LLM agent rather than from a form, and no interface stands between the agent and the API to constrain what it submits, so declarative validation enforced before the handler runs carries a load that a form carried in the systems the literature describes. The trade is a smaller ecosystem and no built-in ORM or admin, which matter little where the schema is a few tables.

The same shift shows up in how APIs are described. OpenAPI and JSON Schema state machine-readably what operations exist and what arguments each takes, and the literature documents them as tooling: generate a client, publish reference docs, drive contract tests [2.6.5]. A language model choosing which operation to call reads that same statement, which makes the wording of a field description part of how the system behaves rather than part of its documentation. That use is documented in the agent literature (§2.4.1), and neither body of work cites the other.

---

### 2.6.2 Data Storage

Transaction volumes at single-venue scale are low: tens of seatings, orders, and payments an hour, written by one application process. At that volume the database literature treats the choice as a question of operational cost and concurrency semantics rather than of throughput [2.6.6].

**Table 2.6b** — Data stores for a single-venue deployment.

| Store | Approach | Advantages | Limitations |
|---|---|---|---|
| SQLite | Embedded in the application process, one file on disk | Nothing to install, secure, or keep running; no network hop; relational constraints enforced by DDL; WAL mode lets readers proceed during a write | One writer at a time; no access from another machine; limited concurrent write throughput |
| PostgreSQL | Separate service reached over a network protocol | Many concurrent writers with row-level locking; richer constraint and index types; access from other machines | A service to install, secure, back up, and keep running; a network hop on every query; unused capacity at this transaction rate |
| MongoDB | Separate service, document-oriented | Schema can change without migration; suits heterogeneous or nested records | No enforced schema, so lifecycle rules move into application code; joins across collections are awkward; same administrative cost as a server database |

Restaurant records are strongly relational and their value lies in a lifecycle being enforced. A visit runs as a sequence in which a party is seated, orders accumulate, a bill is settled, and the table is released, and which step is permissible next depends on the current position [2.6.7]. Where staff drive those transitions the constraints are carried by the workflow rather than by the schema: nobody settles a bill for a table with no one sitting at it, and the software need not prevent it. Commercial platforms implement these lifecycles internally and expose them through the interfaces staff use, not as operations a program can invoke [2.6.8]. What enforcement becomes necessary when the entity driving the transitions is not a person, and cannot be relied on to observe an implicit workflow, does not arise in systems built on the assumption that it always is one.

SQLite is the option whose limitations do not bind here. One backend process performs every write, so the single-writer restriction costs nothing; the database and the application are the same program, so remote access is not wanted; and the throughput ceiling sits orders of magnitude above tens of transactions an hour. What it removes is the administrative surface of a database service, the recurring cost in a venue with no operations staff. A document store would fit worst, because the schema is exactly the part worth keeping once an agent is among the writers.

A separate storage question concerns data that is not transactional at all. A fleet of moving robots reports position and battery several times a second per robot, and each reading is superseded within milliseconds, so its worth lies almost entirely in being the current one. Written to the same file as orders and payments, that traffic contends for the write lock at a rate out of proportion to the value of any individual reading. Three patterns are documented [2.6.9]–[2.6.10].

**Table 2.6c** — Storage patterns for high-frequency telemetry.

| Pattern | Advantages | Limitations |
|---|---|---|
| Write every update to the database | Complete history; survives restart exactly | Write load proportional to fleet size and report rate; contends with order and payment writes for the same lock |
| Keep in memory only | No contention at all; lowest latency | Everything is lost on restart, so a client reconnecting before the next report sees nothing |
| Keep in memory, snapshot periodically | Contention independent of report rate; a recent value survives restart | The persisted value is approximate; no history is retained |

The third pattern suits a restaurant fleet, because the only consumer of a robot's position is a live map, and a map that is a few seconds stale after a restart is acceptable where an order that is a few seconds stale is not. Separating the two kinds of data by how they are stored is what keeps a robot streaming pose from slowing down the ledger.

---

### 2.6.3 Real-Time Transport

How a client learns that something has changed is the layer with the widest spread of documented options [2.6.11]–[2.6.14].

**Table 2.6d** — Transport mechanisms for browser and device clients.

| Mechanism | Approach | Advantages | Limitations |
|---|---|---|---|
| Polling | Client re-requests current state on a fixed interval | Trivial to implement; needs nothing beyond an existing endpoint; each request is independent, so recovery is automatic | Mean staleness is half the interval; request volume is client count divided by interval whether or not anything changed; no way for the server to initiate |
| WebSocket | One connection upgraded to a persistent bidirectional channel | Updates arrive when the change occurs; the client can report as well as receive; one connection carries both directions | A connection held open per client; a dropped socket does not re-establish itself, so the application supplies reconnection logic; an open socket is not evidence the peer is working |
| Server-sent events | Server-to-client stream over an HTTP response held open | Lighter than a WebSocket; reconnects automatically in the browser; can resume from the last event received | One direction only, so a client that must also send needs a second channel; limited concurrent connections per origin over HTTP/1.1 |

Polling degrades predictably, and kitchen display systems have conventionally run on it at intervals of several seconds, which the sources treat as unobjectionable for a screen a cook consults periodically (§2.1.3). Those characterisations are written against human tolerance for staleness. None of them reports what interval is appropriate when what waits on the state is a machine.

For a restaurant service system the two persistent mechanisms are complementary rather than competing, and which one fits depends on the client. Robots have to report position and task progress as well as receive assignments, and a browser panel showing a live map benefits from the same channel, so a WebSocket is the mechanism that suits shared operational state. An agent's spoken reply is a different shape of traffic: it is produced progressively, flows one way to one tablet, and gains nothing from a return path, which is the case server-sent events were designed for. Polling remains adequate for anything a person merely glances at, and its cost is that it stops being adequate the moment a machine is the one waiting.

Two further properties are documented as mechanism and left open as content. Routing events to subsets of clients by declared role is a standard publish-and-subscribe arrangement and is not itself difficult [2.6.14]; the event vocabularies are application-specific, and where commercial restaurant platforms implement one internally they do not publish it (§2.1.3). The second is that an open connection is not evidence of a working peer. A process that has crashed closes its socket and is easily detected. A process that has hung holds the socket open, satisfies any check made at the transport layer, and reports nothing. Liveness therefore has to be established at the application layer, by requiring positive evidence at intervals and treating silence beyond a tolerance as failure [2.6.15]. The sources give the mechanism but no general value for the tolerance, since what it should be depends on what the system does once failure is declared.

---

### 2.6.4 Frontend Stack

Interfaces of the kind restaurant operations call for, one per role over shared state, are built as single-page applications: one document, client-side routing, and a component tree updated in place as data changes. Three frameworks account for most of the ecosystem [2.6.16]–[2.6.17].

**Table 2.6e** — Single-page application frameworks.

| Framework | Approach | Advantages | Limitations |
|---|---|---|---|
| Vue 3 | Proxy-based reactive state; single-file components; routing and state management maintained alongside the framework | Smallest runtime of the three (~33 KB gzipped); dependency tracking re-renders only the components whose data changed, with no virtual-DOM diff; first-class TypeScript; one obvious choice per companion library | Smaller third-party component market than React; fewer developers available |
| React | Virtual DOM with reconciliation; components as functions with hooks | Largest ecosystem and component selection; largest hiring pool | ~42 KB gzipped with DOM; state model (dependency arrays, closure capture, effect cleanup) is the most error-prone of the three; routing and state management chosen separately |
| Angular | Full framework with dependency injection, observables, and a prescribed structure | Consistent structure across a large codebase; first-class TypeScript; everything included | Substantially larger runtime; steepest learning curve; the imposed structure is overhead on a small application |

Vietnamese text does not distinguish them: all three emit standard HTML and leave diacritics to the browser's Unicode text engine.

Runtime cost does, for a reason particular to this deployment. One of these interfaces does not run on a device bought to display it: it runs in a browser on the robot's own embedded computer, beside the navigation stack and the speech models, drawing on a memory pool shared between CPU and GPU (§3.2.1). Bundle size is the smaller part of that, since the runtime loads once. The cost paid continuously is the work done per update, because these screens sit on a WebSocket delivering robot poses several times a second: Vue tracks dependencies through proxies and re-renders only the components whose data changed, React re-runs component functions and reconciles a virtual DOM on every state change, and Angular's change detection walks the tree. On a board whose CPU is shared with control loops, that difference is capacity the interface does not take from motion. React's larger component market and Angular's imposed structure would repay themselves on a large application built by a large team, which is not what these interfaces are.

Two supporting choices follow. For a table-heavy operations screen PrimeVue supplies data-dense components with an unstyled mode, whereas Vuetify commits to Material Design and Ant Design Vue to an enterprise default [2.6.18]; and Vite serves native ES modules in development, so start-up is largely independent of project size, while its production build tree-shakes the payload [2.6.19]. Building several role-specific applications over one backend is itself established practice, documented for enterprise consoles and for operational systems giving dispatchers, field workers, and supervisors distinct views of shared work [2.6.20], where shared type definitions keep each one consistent with the backend and role-scoped subscriptions keep its updates relevant.


