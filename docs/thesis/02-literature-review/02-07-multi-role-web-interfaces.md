## 2.7 Multi-Role Web Interfaces for AI-Driven Restaurant Operations

> *Restaurant automation requires distinct user interfaces for each operational role — customer ordering, kitchen order management, guest check-in, and fleet monitoring — all sharing a single source of real-time truth driven by AI agent events. This section surveys single-page application frameworks, component libraries, build tools, and real-time communication patterns. The technologies are individually mature; the gap is their composition into a documented multi-role architecture where the AI agent is the primary driver of UI state.*
>
> **Cross-refs:** §2.1 (overview — restaurant software gap), §2.6 (back-end operations — real-time state synchronization), §4.7 (orchestrator WebSocket hub), §4.8 (web interfaces — proposed architecture), §5.6 (web system experiments)
> **Citations:** [2.7.1]–[2.7.23]; final numbering assigned when all Ch.2 references are merged.

---

### 2.7.1 Single-Page Application Frameworks — Comparison

The single-page application (SPA) model — a single HTML page with client-side routing where reactive component trees update in-place as data changes — is the standard pattern for real-time dashboards, interactive ordering systems, and operational panels. Three frameworks dominate the SPA ecosystem.

**Vue 3 (Composition API, TypeScript).** Vue 3 provides a reactivity system based on JavaScript Proxies: component state declared via `ref()` and `reactive()` automatically triggers DOM updates when modified [2.7.1]. The Single-File Component (SFC) format separates template (HTML), logic (TypeScript), and style (CSS) within one file — a structure well-suited to restaurant interfaces where each component (menu card, order item, kitchen ticket, robot card) has a distinct visual representation. Pinia provides cross-component state management with devtools integration [2.7.2]. Vue Router enables client-side navigation without full-page reloads. First-class TypeScript support means that the shared client library can import type definitions that mirror the backend's Pydantic schemas — a `Dish` type, an `Order` type, a `RobotState` type — ensuring type safety across the API boundary. Vue's runtime is approximately 33 KB gzipped [2.7.3]. Vietnamese character rendering requires no additional configuration — Vue's template compiler emits standard HTML that the browser renders correctly for Unicode Vietnamese text.

**React (Hooks, JSX).** React is the dominant SPA framework by market share and ecosystem size [2.7.4]. Its component model uses JSX — an HTML-in-JavaScript syntax — and hooks (`useState`, `useEffect`) for state and side-effect management. State management options include Context API (built-in), Redux, and Zustand. React's strength is its ecosystem maturity and the availability of third-party libraries for virtually any UI pattern. Its trade-offs for the restaurant context are: (a) JSX blends markup and logic in a way that can obscure template structure in complex multi-form interfaces, (b) the hooks model introduces subtle correctness pitfalls — stale closures in `useEffect` dependencies, missing cleanup functions for WebSocket subscriptions — that add debugging overhead, and (c) the runtime is approximately 42 KB gzipped (React + ReactDOM) before additional state management [2.7.5].

**Angular (TypeScript, RxJS).** Angular is an opinionated full framework with dependency injection, RxJS observables for asynchronous state streams, and a module-based architecture [2.7.6]. Strong typing and a structured project layout make it well-suited to large enterprise teams with established conventions. Its trade-off for the restaurant context is overhead: the runtime is significantly larger than Vue or React, the learning curve is steep, and the boilerplate required for simple components is disproportionate for interfaces where business logic lives on the backend server. Angular's RxJS observable model handles WebSocket event streams naturally, but the same pattern is achievable in Vue with a simple composable and in React with a custom hook — without the framework-level complexity.

**Comparison.** The following table summarizes the three frameworks against criteria relevant to a multi-role, AI-driven restaurant interface:

| Criterion | Vue 3 | React | Angular |
|-----------|:-----:|:-----:|:-------:|
| Reactivity model | Proxy-based (`ref`, `reactive`) | Virtual DOM + hooks | Zone.js + RxJS |
| TypeScript support | First-class | Good | First-class |
| Runtime size (gzipped) | ~33 KB | ~42 KB | ~65+ KB |
| Vietnamese text rendering | Native (Unicode) | Native (Unicode) | Native (Unicode) |
| SFC separation (HTML/CSS/TS) | ✓ (built-in) | ✗ (JSX) | ✓ (built-in) |
| Multi-app monorepo support | ✓ (Vite workspaces) | ✓ (Nx, Turborepo) | ✓ (Nx) |
| Developer ramp-up time | Low | Medium | High |
| Real-time WS integration | Composable pattern | Custom hook | RxJS Observable |

No framework is inherently unsuitable. The choice is determined by the specific requirements of the project: three independent SPAs sharing a common TypeScript client library, with reactive Vietnamese text rendering, WebSocket-driven UI state, and a low ramp-up time for a small team. Prior work has compared these frameworks for general web development [2.7.7]; no survey has established selection criteria for the specific context of a multi-role, AI-driven restaurant system where the event source is an external agent rather than a human user.

---

### 2.7.2 Component Libraries

A framework provides the architecture for an application — how components are defined, how state flows, how the DOM is updated. Component libraries provide the visual building blocks: the data tables, forms, cards, dialogs, and status indicators that populate the framework's component tree. Selecting a component library is not merely an aesthetic decision; it determines which interaction patterns are available without custom implementation and how closely the interface can map to its domain's native concepts.

Restaurant interfaces place specific demands on component selection. A menu browsing interface must present a catalog of Vietnamese dishes — each with a name, price, description, and category — in a format that supports scrolling, filtering, and quick visual scanning on a tablet-sized screen. A kitchen Kanban board must display incoming orders as cards that move through workflow columns (pending, cooking, ready) with status badges and elapsed-time indicators. A fleet dashboard must render robot status cards with battery gauges and live position markers. A check-in kiosk must show a table grid with real-time occupancy indicators and a party-size selector. The component library that serves all four interfaces must therefore provide data table, card, form, dialog, badge, and layout primitives — all touch-friendly, all TypeScript-typed, all capable of binding to real-time data without manual DOM manipulation.

Three component libraries have been documented for Vue 3 applications.

PrimeVue 4 [2.7.8] is a Vue 3-native library with full TypeScript support, built around data-intensive components. Its DataTable provides sorting, filtering, pagination, and row expansion — mapping directly to menu browsing where a customer scans dishes by category, filters by price, and expands rows for ingredient details. Its Form components (`InputNumber` for quantities, `Dropdown` for categories, `Textarea` for special instructions) carry built-in validation, eliminating the need for a separate validation library. Its Card and Panel containers structure the visual hierarchy of the kitchen board and fleet dashboard. Its Dialog and OverlayPanel handle payment confirmation modals and call-robot prompts. Its Badge and Tag components render order status indicators with color-coded visual states. All components accept TypeScript generics for their data models, meaning a DataTable typed with `Order[]` provides compile-time checking on column definitions and row data access. Imports are tree-shakeable — each application bundles only the components it actually uses — which is relevant in a three-application monorepo where each SPA imports a different subset (the kiosk uses Card and Button; the panel uses DataTable, Card, Badge, and Dialog; the customer tablet uses DataTable, InputNumber, Dialog, and Toast).

Vuetify 3 [2.7.9] is a Material Design component library maintained by the Vue core team. It provides a comprehensive component catalog with a consistent visual language governed by Google's Material Design specification — elevation-based layering, a structured color palette, grid-based responsive layouts. The specification's strength for data-heavy administrative interfaces becomes a constraint for customer-facing restaurant displays: Material Design's fixed grid system limits the responsive, touch-friendly layout that a menu-browsing tablet requires, where cards should reflow fluidly as the viewport changes and large tap targets should dominate the visual hierarchy. Vuetify's bundle weight is heavier than PrimeVue's tree-shakeable imports because Material Design's theming system loads its full SCSS variable set regardless of which components are used.

Ant Design Vue [2.7.10] is an enterprise-grade library adapted from Ant Design React, providing comprehensive form, table, and layout components designed for complex data management workflows. Its DataTable supports multi-column sorting, grouped headers, and expandable rows — features that serve the kitchen panel's order management and the fleet dashboard's robot monitoring equally well. Its visual style, however, is optimized for enterprise back-office applications: dense forms with compact spacing, tables with subdued alternating row colors, and a blue-gray color palette designed for information density rather than visual appeal. At a customer-facing tablet where the interface should feel warm, spacious, and inviting — the opposite of an enterprise data entry screen — Ant Design's visual defaults require significant customization to match the expected restaurant ambiance.

| Criterion | PrimeVue 4 | Vuetify 3 | Ant Design Vue |
|-----------|:---:|:---:|:---:|
| Vue version | Vue 3 native | Vue 3 native | Vue 3 native |
| TypeScript | Full (typed props, events, slots) | Full | Full |
| DataTable capabilities | Sort, filter, paginate, row expansion, column templating | Sort, filter, paginate | Sort, multi-column, grouped headers, expandable rows |
| Form components | InputNumber, Dropdown, Textarea, Checkbox, Radio + validation | Input + Vuelidate validation rules | Form with comprehensive validation |
| Dialog / Overlay | Dialog, OverlayPanel, Sidebar, Toast | Dialog, Snackbar, Menu, Tooltip | Modal, Drawer, Popover, Notification |
| Status indicators | Badge, Tag, Chip, ProgressBar | Badge, Chip, Progress | Badge, Tag, Progress |
| Theming flexibility | Unstyled mode — CSS variables override defaults; per-component passthrough | Material Design specification — elevation, palette, and grid are fixed | Configurable theme tokens but visual baseline is enterprise |
| Bundle strategy | Tree-shakeable per-component imports | Full SCSS theming bundle loaded regardless of component usage | Tree-shakeable per-component imports |
| Touch-friendly | Large tap targets on DataTable; configurable row height | Constrained by Material grid density | Moderate touch support; optimized for mouse-driven desktop |
| Vietnamese diacritics | Native Unicode handling; no special configuration | Native Unicode handling | Native Unicode handling |

Component library comparisons exist for general web development [2.7.12], typically evaluating component counts, bundle sizes, and community activity. No evaluation has assessed these libraries against the specific intersection of requirements that a multi-role restaurant system demands: Vietnamese text rendering for dish names with diacritic accuracy; touch-friendly interfaces for 7-inch customer tablets with large tap targets; and real-time data binding to WebSocket events where component state updates are driven by an external publisher rather than direct user interaction.

### 2.7.3 Build Tooling

A multi-application project — three independent SPAs that share a TypeScript client library — places demands on the build toolchain that a single-application project does not. Each SPA must be developed, served with hot module replacement, and built for production independently, yet all three must resolve imports from the same shared library without duplicating its compiled output or introducing circular dependency chains.

Vite [2.7.13] is the standard build tool for Vue 3 projects as of 2024. During development, it operates a native ES module dev server: when the browser requests a `.vue` or `.ts` file, Vite transforms the file on-demand using esbuild for TypeScript transpilation and its own plugin pipeline for Vue SFC compilation. Because the server never bundles application code during development — it serves individual ES modules — startup time is independent of project size, and hot module replacement completes in under 50 milliseconds by invalidating only the module chain affected by a changed file. Production builds use Rollup with tree-shaking and code-splitting, producing optimized bundles that exclude unused code paths. For a three-application monorepo, each SPA references its own `vite.config.ts` with an independent set of plugins, an independent dev server port, and path aliases that resolve the shared TypeScript library relative to the monorepo root.

The historical alternative, Webpack via Vue CLI, served as the Vue ecosystem's build tool for most of Vue 2's lifecycle. Webpack bundles the entire application dependency graph at dev server startup — every module is resolved, transpiled, and concatenated before the first request is served — producing startup times that grow with project size. On large projects, startup takes 2–10 seconds and HMR updates take 200–500 milliseconds. Vue CLI has been in maintenance mode since 2023, with the Vue team recommending Vite for all new Vue 3 projects. For a multi-application monorepo where the developer switches between three SPAs during development, the cumulative cost of Webpack cold starts — three projects, each requiring a full dependency graph bundle — is a measurable friction on the development workflow.

Prior work: build tool benchmarks comparing Vite and Webpack exist for single-application scenarios [2.7.14], typically measuring dev server startup time and HMR latency against project size. No evaluation has characterized the build toolchain requirements of a multi-application monorepo where three independent SPAs share a common TypeScript client library at development time and produce separate optimized production bundles — a configuration that tests the build tool's module resolution, path aliasing, and code-splitting behavior under shared-dependency conditions.

---

### 2.7.4 Real-Time Communication Patterns

Restaurant interfaces cannot rely on polling-based data refresh. When an AI agent creates an order, the kitchen display must show it immediately — not on the next 5–10 second poll cycle. When the agent modifies a cart, the customer tablet must reflect the change before the next utterance. Three communication patterns exist for real-time web applications:

**Polling (REST-based periodic refresh).** The client sends an HTTP GET request every N seconds to check for state changes. This is the standard pattern in traditional restaurant POS and KDS systems, where a human operator glances at the screen periodically and a 5–10 second delay is acceptable [2.7.14]. For a voice-driven customer interaction, a 5-second delay between the utterance and seeing the cart update breaks conversational flow. For a display panel with 10-second poll cycles, the average latency from event occurrence to UI update is 5 seconds, with worst-case 10 seconds.

**WebSocket (full-duplex persistent connection).** A single TCP connection is upgraded to a WebSocket, providing bidirectional communication for the lifetime of the session [2.7.15]. The server pushes events to clients as they occur: `order.created`, `cart.updated`, `robot.position`, `voice.reply`. Role-based fan-out routes each event to the correct client subset. Event delivery latency is sub-second. Auto-reconnection with exponential backoff (1s → 2s → 4s → … cap 30s) handles temporary WiFi drops — the standard resilience pattern for production WebSocket deployments [2.7.16].

**Server-Sent Events (SSE).** SSE provides server-to-client streaming over a standard HTTP connection [2.7.17]. The server opens a long-lived HTTP response and writes events as they occur; the browser's `EventSource` API receives them. SSE is lighter-weight than WebSocket for unidirectional server→client traffic and reconnects automatically. It is suitable for streaming LLM-generated responses sentence-by-sentence. SSE is not suitable for bidirectional communication: robot telemetry (robot → server), tablet commands (tablet → server), and kiosk seating requests require the client to send data, which SSE does not support.

The three communication patterns are not mutually exclusive. A system that requires bidirectional state synchronization between server and multiple client roles (WebSocket), one-way streaming of LLM-generated responses (SSE), and CRUD operations on business entities (REST polling) uses each pattern for the communication path it is suited for, rather than selecting one pattern to serve all paths. The following table summarizes the documented properties of each pattern:

| Property | Polling | WebSocket | SSE |
|----------|---------|-----------|-----|
| Direction | Client → Server (request/response) | Bidirectional (server ↔ client) | Server → Client (unidirectional stream) |
| Connection lifecycle | New TCP connection per request | Persistent; upgraded from HTTP (101 Switching Protocols) | Persistent HTTP response; kept open by server |
| Event delivery latency | N/2 seconds on average (half the poll interval); worst-case N seconds | Sub-100ms (server pushes on event) | Sub-100ms (server writes to open response) |
| Reconnection | Inherent — each poll is an independent request | Must implement application-level reconnection with backoff | Browser `EventSource` API reconnects automatically with `Last-Event-ID` |
| Server resource per client | Negligible — connection closed after response | One socket per client; requires event loop with async I/O | One open HTTP response per client; lighter than WebSocket (no framing protocol) |
| Bidirectional data | Client → Server: each poll is a new request with full HTTP headers | Native; both directions over the same socket | Not supported — no client-to-server channel over the open response |
| Standard restaurant use | POS/KDS polling for order updates (5–10s intervals) | Real-time dashboards; live cart sync; robot telemetry | LLM response streaming; notification feeds |
| Documented API | REST endpoints with OpenAPI/Swagger | Custom JSON message catalog per application | Standard `text/event-stream` format; event types defined per application |

Prior work on real-time restaurant systems: Restaurant management platforms — Toast, Square, Lightspeed — implement real-time state propagation internally using proprietary WebSocket or long-polling protocols [2.7.21]. These protocols are not documented publicly and provide no API for third-party integration: an external AI agent cannot subscribe to `order.created` events, a custom kitchen display cannot receive push updates on new tickets, and a fleet monitoring dashboard cannot receive real-time robot position broadcasts. The restaurant platforms operate as closed ecosystems where the event bus is internal to the vendor's own applications. Academic work on real-time multi-role web systems exists for domains outside restaurants: hospital patient monitoring dashboards that push vital-sign alerts to nursing stations and physician tablets [2.7.22], logistics control panels that broadcast shipment status changes to dispatcher and warehouse operator views, and financial trading UIs where market data events drive synchronized updates across trader, risk manager, and compliance officer interfaces [2.7.23]. Each domain documents the event types and subscription models for its specific operational context, but none addresses the restaurant domain where the event source is neither a sensor stream (as in patient monitoring) nor a market data feed (as in trading) but an AI agent making decisions that generate business events.

---

### 2.7.5 Multi-Role SPA Architecture

The multi-role SPA pattern — multiple single-page applications, each serving one user role with role-specific UI and event subscriptions, sharing a common client library — is the standard architecture for systems where different user types need different views of the same underlying data. It has been documented for enterprise SaaS platforms (admin dashboard vs. customer portal vs. agent console) and for operational systems (dispatcher view vs. field-worker view vs. supervisor view).

What has not been documented is this pattern applied to a restaurant system where the shared state is driven by an AI agent. In a conventional multi-role SPA, the event source is typically a human user: an admin updates a record → other roles see the update. In a restaurant AI system, the event source is the agent: the agent confirms an order → the kitchen panel shows a new ticket and the customer tablet shows the confirmed cart. The agent dispatches a robot → the fleet dashboard shows the robot's status change and the robot receives a navigation goal. All roles are downstream of the agent's decisions.

The additional constraint specific to this context is the shared TypeScript client library: the SPAs must import types — `Dish`, `Order`, `CartItem`, `RobotState`, `TableStatus` — that mirror the backend's Pydantic schemas, ensuring that a type mismatch between the orchestrator API and any frontend is caught at compile time. This pattern — shared types across a Python backend and TypeScript frontends — is established in the broader web development literature (OpenAPI code generation, tRPC for TypeScript-only stacks) but has not been evaluated for the Python-FastAPI-to-Vue-TypeScript bridge that this project requires.

---

### → Overall Gap for §2.7

No prior work establishes: (a) SPA framework selection criteria for a multi-role, AI-driven restaurant system — reactivity and TypeScript requirements, Vietnamese text rendering, small-team ramp-up time, and multi-app monorepo structure, (b) component library evaluation against restaurant-specific UI requirements — Vietnamese diacritic rendering, touch-friendly tablet interfaces, data-intensive real-time displays — with a documented selection rationale, (c) a hybrid real-time communication architecture — WebSocket for bidirectional multi-role state synchronization, SSE for AI agent response streaming — with a per-role, per-event-type rationale, and (d) a multi-role SPA architecture where the shared TypeScript client library mirrors Pydantic backend schemas and all roles are downstream of an AI agent's business events.

The individual technologies — Vue 3, PrimeVue, Vite, WebSocket, SSE — are individually mature. Their composition into a documented multi-role restaurant interface architecture, and the selection criteria that justify that composition, has not been described in the literature. This gap motivates the web interface architecture in §4.8.
