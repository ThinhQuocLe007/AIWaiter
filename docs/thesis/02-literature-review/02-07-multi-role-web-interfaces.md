## 2.7 Multi-Role Web Interfaces

> *Restaurant operations require several interfaces at once — a customer ordering on a tablet, a cook working a queue, a host seating a party, a manager watching the floor — each showing a different view of one underlying situation. This section surveys the technologies from which such interfaces are built: single-page application frameworks, component libraries, build tooling, and the transport mechanisms that carry updates to a browser. These are general-purpose web technologies with large literatures and mature documentation; the survey is correspondingly brief where the choices are well characterised, and dwells only on the question that the surveyed work does not settle — what changes when the events driving the interface originate from software rather than from a person.*
>
> **Cross-refs:** §2.1 (overview — restaurant software), §2.6 (operational state and its consumers; transport mechanisms are surveyed here rather than there), §4.1 (multi-role UI requirement), §4.8 (web interfaces — proposed architecture), §5.6 (web system experiments)
> **Citations:** [2.7.1]–[2.7.23]; final numbering assigned when all Ch.2 references are merged. Bibliographic entries for this section are pending — see `references.md`.
> **Figures and tables:** keyed section-scoped (`Table 2.7a`, …) so that this section can be edited independently. Flatten to sequential chapter numbering on merge, in order of first appearance.

---

### 2.7.1 Single-Page Application Frameworks

The single-page application — one document, client-side routing, and a component tree that updates in place as data changes — is the standard construction for interactive dashboards and ordering interfaces. Three frameworks account for most of the ecosystem, and the differences between them are well documented [2.7.1]–[2.7.6].

Vue 3 builds reactivity on JavaScript proxies: state declared through its reactive primitives triggers re-rendering when mutated, without explicit subscription. Its single-file component format keeps template, logic, and style together, and its companion libraries for state management and routing are maintained alongside the framework rather than chosen from competing options. React uses a virtual DOM with reconciliation and expresses components as functions with hooks; it has the largest ecosystem of the three and the widest selection of third-party components, and its state model — dependency arrays, closure capture, effect cleanup — is the most demanding of the three to use correctly. Angular is a full framework rather than a view layer, supplying dependency injection, an observable-based asynchronous model, and a prescribed project structure; it is the heaviest of the three and the most opinionated, which is an advantage on large teams with long-lived codebases and a cost on small ones.

**Table 2.7a** — Single-page application frameworks.

| Framework | Reactivity model | TypeScript support | Approximate runtime size | Scope |
|---|---|---|---:|---|
| Vue 3 | Proxy-based reactive primitives | First-class | ~33 KB gzipped | View layer with maintained companion libraries |
| React | Virtual DOM with hooks | Good; types community-maintained | ~42 KB gzipped (with DOM) | View layer; state management chosen separately |
| Angular | Change detection with observables | First-class | Substantially larger | Full framework including DI and routing |

Rendering of Vietnamese text is not a point of difference. All three emit standard HTML and rely on the browser's text engine, which handles Vietnamese diacritics through Unicode without framework-specific configuration; any of the three renders a dish name correctly. The dimensions on which these frameworks genuinely differ — runtime size, the ergonomics of their state models, the breadth of their component ecosystems, and how much structure they impose — are documented at length in general web development literature, and none of that documentation is specific to, or complicated by, the restaurant setting.

---

### 2.7.2 Component Libraries

A framework determines how components are composed; a component library supplies the components themselves — tables, forms, dialogs, cards, status indicators — so that common interface elements need not be built from primitives. Three libraries are maintained for Vue 3 and are documented in comparable detail [2.7.8]–[2.7.10].

PrimeVue offers a large catalogue oriented toward data-dense interfaces, with tabular components supporting sorting, filtering, pagination, and templated columns, and an unstyled mode in which the library supplies behaviour while the application supplies appearance. Vuetify implements Material Design, which brings a coherent visual language and the constraints that come with adopting someone else's design system — its grid, elevation model, and spacing are prescribed, and departing from them means working against the library. Ant Design Vue derives from an enterprise design system and is strongest on dense forms and complex tables, with a visual default oriented toward administrative software.

**Table 2.7b** — Component libraries for Vue 3.

| Library | Design system | Tabular components | Styling model | Bundle strategy |
|---|---|---|---|---|
| PrimeVue | None imposed | Sort, filter, paginate, column templating, row expansion | Themed or fully unstyled | Per-component imports |
| Vuetify | Material Design | Sort, filter, paginate | Material tokens; departures work against the library | Theming layer loaded as a unit |
| Ant Design Vue | Ant Design | Sort, multi-column, grouped headers, expandable rows | Configurable tokens over an enterprise baseline | Per-component imports |

The relevant differences are stylistic latitude and bundle composition, both documented. As with the frameworks, Vietnamese text rendering does not distinguish them: all three delegate to the browser.

---

### 2.7.3 Build Tooling

Vite is the standard build tool for Vue 3 projects [2.7.13]. In development it serves native ES modules and transforms files on request, so start-up time is largely independent of project size and updates propagate to the browser by invalidating only the affected module chain; production builds are bundled with tree-shaking and code-splitting. The predecessor toolchain, Webpack as configured by Vue CLI, bundles the dependency graph before serving anything, giving start-up and rebuild times that grow with the project. Vue CLI has been in maintenance since 2023 and the framework's own documentation directs new projects to Vite.

This is a settled question rather than an open one, and it is included for completeness rather than because the literature leaves anything unresolved.

---

### 2.7.4 Real-Time Communication Patterns

How an interface learns that something has changed is the one part of this section with consequences for the rest of the system, and §2.6.4 defers here for the survey.

Polling has the client request current state on an interval. It is trivially implemented, requires nothing of the server beyond the endpoint it already has, and degrades predictably: the average staleness of what a user sees is half the interval, the worst case is the whole interval, and the request volume is the client count divided by the interval regardless of whether anything changed [2.7.14]. This is the mechanism on which kitchen display systems have conventionally run, and at the intervals they use it is adequate for a display consulted periodically by a person.

A WebSocket upgrades a single connection to a persistent bidirectional channel, over which either side may send at any time [2.7.15]. Updates arrive when they occur rather than when next requested, and the connection carries traffic in both directions, which matters where the client also reports — a machine sending its position, for instance. The costs are a connection held open per client and the reconnection logic that a persistent connection makes necessary, since a dropped WebSocket does not re-establish itself; exponential backoff is the documented approach [2.7.16].

Server-sent events provide a server-to-client stream over an ordinary HTTP response held open [2.7.17]. It is lighter than a WebSocket, reconnects automatically in the browser, and can resume from the last received event; it carries traffic in one direction only, which suits incremental output — a response emitted progressively as it is produced — and rules it out where the client must also send.

**Table 2.7c** — Transport mechanisms for browser interfaces.

| Mechanism | Direction | Update arrives | Reconnection | Suited to |
|---|---|---|---|---|
| Polling | Client-initiated request/response | On the next interval | Inherent — each request independent | State a person consults periodically |
| WebSocket | Bidirectional, persistent | When the change occurs | Application-level, with backoff | Shared state; clients that also report |
| Server-sent events | Server to client, persistent | When the change occurs | Automatic, resumable | Progressive output to one recipient |

A further consideration arises once several kinds of client share a connection mechanism: not every event concerns every client. Routing events to subsets by declared role is a standard publish-subscribe arrangement and is not itself difficult. What the surveyed literature documents is the mechanism; the event vocabularies themselves are application-specific, and where restaurant platforms implement such vocabularies internally they do not publish them (§2.6.4).

---

### 2.7.5 Multi-Role Interfaces and the Origin of Events

Building several role-specific applications over one backend is an established pattern, documented for enterprise software with administrative, customer-facing, and staff-facing consoles, and for operational systems that give dispatchers, field workers, and supervisors distinct views of shared work [2.7.22]–[2.7.23]. The engineering is well understood: shared type definitions and a shared client keep the applications consistent with the backend, and role-scoped subscriptions keep each application's updates relevant.

What is uniform across these documented cases, and unremarked because it is uniform, is where the events come from. An administrator saves a record and other consoles reflect it; a dispatcher assigns a job and the field worker's view updates; a supervisor changes a priority and the queue reorders. In every case the causal chain begins with a person acting on an interface. The propagation is machine-mediated, but the origin is human, and interfaces built on this assumption inherit two properties from it. A user seeing a change can generally attribute it to someone's action, and a user interacting with a region of the screen can generally assume that region is not simultaneously being altered by anyone else — because the other people who might alter it are working elsewhere, on their own screens, at human speed.

An interface driven by an autonomous component satisfies neither assumption. Changes arrive with no person having acted, so a user has no account of why the screen moved. More consequentially, the component may write to the same state the user is editing, at a moment of its choosing, with neither party aware of the other — concurrent authority over one piece of interface state, held by a human and a program that do not share a coordination mechanism. This is a recognised problem in collaborative editing, where the participants are all human and the resolution strategies assume symmetric participants who can be shown one another's presence. It is not a problem the multi-role interface literature addresses, because in the arrangement that literature documents it does not occur.

---

The technologies surveyed here are general-purpose, thoroughly documented, and not specific to this application. Frameworks, component libraries, and build tools differ from one another along dimensions — runtime size, styling latitude, rebuild speed — that are matters of engineering preference and are settled in the general web development literature; nothing about a restaurant complicates them, and Vietnamese text in particular is a non-issue, handled by the browser in every case. The transport mechanisms are equally well characterised, and the choice among them follows from directionality and from whether updates must arrive when they occur.

The one question this section reaches that its sources do not answer concerns the assumption identified in §2.7.5. Multi-role interface architectures are documented for systems in which every state change originates from a person operating one of the interfaces. Where an autonomous component originates changes instead, two properties that such architectures rely on quietly cease to hold: that a change can be attributed to an actor the user could in principle identify, and that a region of the screen a user is working in is not concurrently being written by someone else. The literature offers no account of interfaces built without those properties — not because the case is difficult, but because it has not arisen in the settings the literature describes.
