## 4.7 Web Interfaces — Architecture

> **Status:** draft
> **Cross-refs:** §4.2 for three-tier topology, §4.5 for orchestrator API, §4.5.4 for WebSocket events
> **Source:** `src/frontends/customer_ui/`, `kiosk/`, `panel/`, `shared/`
> **Figures needed:** Screenshots of each app (customer tablet voice mirror, kiosk table grid with seating modal, panel kitchen Kanban + minimap)

---

Three single-page applications share a common TypeScript library for REST, WebSocket, and type definitions. Each app serves a distinct role: customer ordering on the table's tablet, guest check-in at the kiosk, and staff operations on the management panel. All three are built with Vite + Vue 3 (Composition API) and communicate with the orchestrator backend via REST for writes and WebSocket for live updates.

### 4.7.1 Shared Frontend Architecture

The three SPAs import from `@shared/`, a Vite alias pointing to `src/frontends/shared/`. This directory contains three dependency-free modules (no Vue or Pinia) usable by any frontend:

| Module | Lines | Purpose |
|--------|-------|---------|
| `types.ts` | 117 | TypeScript interfaces mirroring backend Pydantic schemas: `Order`, `Table`, `Robot`, `Task`, `Layout`, `VoiceCartItem`, `UiAction`, and the `WsEvent` discriminated union for all WebSocket event types |
| `rest.ts` | 90 | REST client for the orchestrator. Functions: `fetchOrders()`, `createOrder()`, `createSeating()`, `updateTableStatus()`, `fetchRobots()`, `fetchLayout()`, `callRobot()` |
| `ws.ts` | 66 | WebSocket client with auto-reconnect (capped exponential backoff: 1s → 2s → 4s → cap 10s). Returns a `WsHandle` with `onEvent` callback and `close()` for clean teardown |

**Vite dev proxy.** All three apps proxy `/api` → `http://127.0.0.1:8000` and `/ws` → `ws://127.0.0.1:8000`, achieving same-origin access in both development and preview modes. In production behind a reverse proxy, the frontend is served from the same origin as the backend, eliminating CORS entirely.

**Per-app independence.** Each app is an independent Vite project with its own `package.json`, `node_modules`, and `dist/` output. No monorepo tooling — the `@shared` alias provides the only cross-app coupling. This allows each app to use its own dependency versions and build independently.

**State management.** The customer tablet uses Pinia stores for shared reactive state (cart, menu, voice, UI). The kiosk and panel are single-component SPAs using Vue's local reactive state only — no Pinia is needed since their data flow is simple (fetch → render → event → update).

### 4.7.2 Customer Tablet UI

The customer tablet (`customer_ui`, port 5173) is the primary customer-facing interface, displayed on the robot's 7-inch LCD touchscreen at each table. It is a full-featured Vue 3 application with Vue Router (hash mode), Pinia stores, PrimeVue UI components (Aura theme), and Tailwind CSS.

**Tech stack.** Vue 3.5, Vite 8, Pinia 2, Vue Router 4 (hash history), PrimeVue 4 (Aura preset), Tailwind CSS 4, @vueuse/motion (entrance animations), @vueuse/core (composable utilities), vue3-lottie (Lottie animations), @tabler/icons.

**Router layout.** Five routes with a navigation guard that auto-redirects to the appropriate screen based on table state:

| Route | Screen | Purpose |
|-------|--------|---------|
| `/` | WelcomeScreen | Branded splash with auto-redirect to `/service` if table is dining |
| `/service` | ServiceChoiceScreen | Two action cards: "Gọi món thêm" (order more) or "Thanh toán" (pay) |
| `/menu` | MenuScreen | Full ordering interface: categories, items, search, cart drawer |
| `/confirmation` | ConfirmationScreen | Post-order success with countdown and "back to menu" button |
| `/payment` | PaymentScreen | VietQR mock payment: QR code, bank info, amount, verify button |

**Table switching.** The tablet targets a specific table (1–6), selected from a dropdown in the top bar. Switching tables swaps the cart bucket (per-table localStorage keyed by `table_id`), resets the voice conversation, and validates the loaded cart against the backend's table status.

#### Menu Browsing

The menu is organized into 12 Vietnamese seafood categories loaded from `menu.json` via the orchestrator. The `useMenuStore` Pinia store manages:

- **Category navigation.** A scrollable left sidebar lists all categories with Vietnamese names and representative icons. "Best Seller" is pinned at the top. The sidebar highlights the currently visible category as the user scrolls (scroll-synced active tracking).
- **Item display.** Dishes are grouped by category in the main content area, with images, names, and unit prices. Each dish has an `AddControl` component for quantity adjustment (+/− buttons with inline count).
- **Search.** A diacritic-insensitive free-text search bar filters across all dish names, descriptions, and categories in real time. Matching results are shown in a dedicated search results section.
- **Best Seller section.** Dishes flagged as `is_best_seller` in the menu data are featured prominently at the top of the scroll view.
- **Detail modal.** Tapping a dish opens a `FoodDetailModal` with the full image, price, and "Thêm vào giỏ hàng" button.

#### Voice Mirror

The `useVoiceStore` Pinia store manages the voice conversation lifecycle, driven by WebSocket events:

| AI State | Trigger | UI Display |
|----------|---------|------------|
| `idle` | App mount, turn complete | "Bấm để nói chuyện" CTA banner |
| `listening` | Guest presses "Talk to AI" → `POST /voice/listen` | Pulsing orb, "Đang nghe..." |
| `thinking` | `voice.heard` event received | Thinking dots animation |
| `speaking` | `voice.reply` event received | AI text bubble + TTS playback on robot |

The voice conversation is displayed in a slide-up chat sheet (`VoicePanel.vue`) showing user/AI bubbles, thinking indicators, and a listening orb animation. The chat sheet also includes:
- **Cart synchronization.** On `voice.reply`, the agent's cart draft is mirrored to the visual cart via `syncFromVoice()` — the tablet's cart always matches the agent's. If the agent confirms the order (`confirmed=true`), draft items are moved to the "ordered" section.
- **UI action following.** The agent can emit `open_menu` (scroll to relevant category) or `open_payment` (navigate to payment screen) commands that the tablet executes.
- **Stop button.** A "Dừng" button sends `POST /voice/cancel` to abort an in-flight capture.
- **Per-table isolation.** WebSocket events are filtered by `table_id` — the tablet only shows conversation for its own table.

#### Cart Management

The `useCartStore` Pinia store implements a two-tier cart:

1. **Draft cart** (`items`): Editable items being composed before confirmation. Voice agent additions and manual menu additions both modify this tier.
2. **Ordered items** (`orderedItems`): Read-only items already sent to the kitchen. Populated when the agent confirms via voice or the guest taps "Xác Nhận Đặt Món."

**Per-table persistence.** Cart state is persisted to `localStorage` keyed as `aiwaiter.cart.v1:t{tableId}`. This survives page reloads and panel closure. On table switch, the store swaps to the new table's bucket.

**Server-computed totals.** Cart totals are computed by the orchestrator, not the frontend — the `createOrder` call returns verified prices from the menu database. On confirmation, the draft items are sent via `POST /orders` and the response replaces the cached totals.

#### Payment Flow

The `PaymentScreen` displays the session's cumulative total (sum of all confirmed orders), a VietQR mock QR code, and payment instructions. A "Đã thanh toán xong" button calls `POST /payments/verify`, which closes the session, clears the cart, and redirects to the welcome screen. A 30-second auto-return countdown provides a passive exit path.

### 4.7.3 Kiosk — Guest Check-in

The kiosk (`kiosk`, port 5174) is a single-component Vue 3 SPA — no router, no Pinia, no CSS framework. It runs on a tablet at the restaurant entrance and handles the guest check-in workflow.

**Table grid.** All tables are fetched via `fetchTables()` and displayed as a card grid. Each card shows the table name, capacity icon, and a color-coded status badge:
- Green "Sẵn sàng" for `TRONG` (free, tappable).
- Blue "Đang phục vụ" for actively dining tables (disabled, not tappable).
- Orange "Đã thanh toán" for tables awaiting cleanup (disabled).

A badge displays "X / N bàn trống" (available count). Background polling at 8-second intervals keeps the grid in sync — the WebSocket `table.updated` event provides faster updates, with the poll as a safety net for connection gaps.

**Seating flow.** Three steps in a modal overlay:
1. Guest taps a free table card.
2. Party-size stepper appears (default 2, capped at the table's capacity). +/− buttons adjust the count.
3. "Vào bàn" (Enter) calls `createSeating(tableId, partySize)`.

On success, a checkmark overlay confirms the seating ("{name} đã sẵn sàng — Mời quý khách vào bàn và đặt món trên màn hình tại bàn") and auto-returns to the grid after 6 seconds. On 409 Conflict (another kiosk seated the same table simultaneously), the kiosk shows a flash notice and auto-reloads the table grid.

### 4.7.4 Management Panel — Kitchen & Fleet Operations

The management panel (`panel`, port 5175) is a single-component Vue 3 SPA with four child components, displayed as a dashboard for kitchen and floor staff. It loads all state on mount and maintains it reactively via WebSocket events with a 15-second polling safety net.

**Kitchen Kanban** (`KitchenBoard.vue`). A three-column board representing the order workflow:

| Column | Status | Description |
|--------|--------|-------------|
| **Chờ bếp** | `CHO_BEP` | Newly confirmed orders awaiting cooking. Oldest first (FIFO). |
| **Đang làm** | `DANG_LAM` | Orders being prepared. "Bắt đầu làm" button advances from Chờ bếp. |
| **Xong** | `XONG` | Completed orders ready for delivery. "Món xong ✓" button advances from Đang làm. Most recent 15 shown. |

Each order card displays: table name, elapsed time since creation, item breakdown (qty × name with notes), and total price. When an order advances to `XONG`, the orchestrator creates a `deliver` task — the kitchen board action cascades to robot dispatch automatically.

**Fleet Board** (`RobotBoard.vue`). A grid of robot cards displaying per-robot status. Each card shows:
- Robot name (with emoji icon).
- Status badge: Rảnh (idle, green), Bận (busy, blue), Ngoại tuyến (offline, gray).
- Current activity description (e.g., "Đang phục vụ · Bàn 3").
- Battery percentage with color coding (red below 25%).

**Table Overview** (`TablesOverview.vue`). A grid of table cards mirroring the restaurant floor, color-coded by status:
- Green: `TRONG` (empty, ready for seating).
- Active dining: Shows party size, time since seated (live ticking clock), ordered dish count, kitchen status badge, order total.
- Orange: `DA_THANH_TOAN` (paid, awaiting cleanup).

Each active table card includes:
- **"Gọi Robot"** button — enqueues a `call` task via `POST /tables/{id}/call`.
- **"Kết thúc bàn"** button (for paid tables) — sets status back to `TRONG`, frees the table, and releases the robot.

**Minimap** (`MiniMap.vue`). A draggable floating HUD overlay showing the SLAM floor plan. The SLAM map PNG (served by `GET /layout`) is rendered as an SVG `<image>` backdrop, rotated 90° counter-clockwise to align the dock at the bottom of the screen. SVG overlay elements include:
- **Dock:** Fixed reference point at the origin.
- **Tables:** Six colored rectangles positioned at their world-frame waypoints. Color indicates status: muted (free), active (dining), orange (paid).
- **Robots:** Pulsing halo dots at live world-frame (x, y) coordinates received via `robot.updated` events at up to 5 Hz. Robots with no pose reported fall back to the dock position.

The minimap converts between the SLAM map's metric coordinate frame and pixel coordinates using the map's resolution and origin metadata, then applies the rotation transformation for screen display.

**System Reset.** A "↺ Reset hệ thống" button with a confirmation dialog calls `POST /admin/reset`, which wipes all orders, seatings, tasks, frees all tables, and resets mock robots. The panel dismisses stale state via a full browser reload.

### 4.7.5 Frontend Data Flow Summary

| Data | Source | Protocol | Update Pattern |
|------|--------|----------|---------------|
| Menu (dishes, categories) | `GET /menu` | REST | On mount only (static) |
| Table statuses | `GET /tables` + `table.updated` WS | REST + WS push | Mount load + live push |
| Orders | `GET /orders` + `order.created/updated` WS | REST + WS push | Kitchen board live sync |
| Robot positions | `robot.updated` WS | WS push | 5 Hz live pose stream |
| Tasks | `GET /tasks` + `task.created/updated` WS | REST + WS push | Mount load + live push |
| Voice conversation | `voice.heard/reply` WS | WS push | Per-turn live events |
| Cart state | Agent via `voice.reply` WS | WS push | Synced from agent to tablet |
| Layout (SLAM map) | `GET /layout` | REST | On mount only (static) |
