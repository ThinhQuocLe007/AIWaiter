# Design — Server → Screen bridge (the `emit_action` seam)

> How a UI command produced by the shared agent reaches the **right** customer screen.
> Status: design agreed (2026-06-25). Not yet implemented.
> Read with [system-architecture.md](system-architecture.md) (§2, §12) and the action seam in
> `ai_waiter_core/ai_waiter_core/agent/actions.py` (`emit_action`).

---

## 1. Problem

The agent runs **once on the server, shared by all robots**. It already decides *what* should
happen on a guest's screen — `build_action()` produces `{"type":"ui","action":"open_menu"}` /
`"open_payment"` ([actions.py](../ai_waiter_core/ai_waiter_core/agent/actions.py)). The delivery
half is a deliberate seam, `emit_action(table_id, action)`, which today only logs — the command is
never delivered.

The customer screen (`customer_ui`) is a **kiosk browser bolted to the robot's body** (served by
the server, points at `:8000`). The robot moves between tables, so "the screen serving table 3"
changes over time. The bridge must push a command from the server to exactly one of N screens,
and must keep working as the fleet grows (demo runs 1 robot, design targets N).

## 2. Decomposition — three independent axes

| Axis | Question | Decision |
|---|---|---|
| A. Transport | how does the command travel? | **WS `role=customer` on the existing hub** (`ws.py`) |
| B. Addressing | which screen receives it? | **Key by static `robot_id`**; resolve `table_id → robot_id` server-side |
| C. Payload | what is sent? | **Desired screen-state derived from `table.status` + an in-memory overlay** |

### Axis A — Transport: reuse the WS hub
`ws.py` already fans out by `role` and tracks identified two-way sockets (`send_to_robot`). Adding
`role=customer` is near-free and reuses the frontend's auto-reconnecting client
(`src/frontends/shared/ws.ts`). SSE/polling were rejected: SSE is one-way (the guest answer would
need a separate REST path) and polling is laggy.

> Note: with the voice-driven choice (Axis C below), the screen→server (upward) channel is **not
> required** for the core flow — the guest speaks, the agent classifies. WS two-way is kept only
> because it is cheap and useful later, not depended on.

### Axis B — Addressing: key by `robot_id`, not `table_id`
The physical screen belongs to the **robot**, not the table. `robot_id` is static (set once at
kiosk boot), so the WS connection never re-registers when the robot changes tables. The
`table → robot` mapping already lives in the `tasks` table (`robot_id`, `table_id`) maintained by
the dispatcher, so `emit_action(table_id)` just looks it up.

Rejected: keying by `table_id` would force the screen to re-register its identity every time the
robot changes tables — an extra sync mechanism that is easy to get out of step.

Scaling: adding robot N is just one more entry in the socket dict — identical to how
`send_to_robot` already works. Send logic is unchanged between 1 and 20 robots.

### Axis C — Payload: push desired state, derived from `table.status`
A kiosk runs all day and will reload / briefly disconnect. A one-shot command ("open_menu") is
lost on reconnect and leaves the screen stuck. So the server pushes the **desired screen-state**
and the screen renders it; on reconnect the screen re-fetches current state and self-heals.

The screen-state is a pure function of `table.status` plus a small in-memory **overlay** for
transitions the status does not capture. No DB schema change.

```python
def screen_for(table_id):
    overlay = _screen_overlay.get(table_id)   # most recent agent emit (menu/payment) wins
    if overlay:
        return overlay
    return {                                   # default derived from the table lifecycle
        "DANG_GOI_MON":   "menu",
        "CHO_THANH_TOAN": "payment",
        "DANG_AN":        "idle",
    }.get(status, "waiting")
```

## 3. Decided behaviour (the two product choices)

- **Add-more vs pay is voice-driven.** The guest speaks; the agent classifies intent → tool →
  action. The branching is *already* encoded in `actions._TOOL_TO_UI_ACTION`
  (`search`/`sync_cart → open_menu`, `request_payment → open_payment`). No "two-button choice
  screen" and no new branching logic. When a robot arrives for a `call` task it shows a neutral
  **greeting** screen ("how can I help?"); the guest's words then drive menu vs payment.
- **Screen-state is in-memory, derived from `table.status`.** No new DB column. Overlay is cleared
  when the serving lifecycle moves on, so the screen falls back to the status-derived default.

## 4. Work items

| # | Where | What |
|---|---|---|
| 1 | `src/backend/app/ws.py` | clone `send_to_robot` → `send_to_customer(robot_id, msg)`; accept `role=customer&robot_id=` |
| 2 | `src/backend/app/screen.py` (new) | `_screen_overlay` dict + `screen_for(table_id)` + `GET /screen?robot_id=` (reconnect/refresh) |
| 3 | `ai_waiter_core/.../agent/actions.py` | `emit_action`: stop logging-only → set overlay, resolve robot from `tasks`, `send_to_customer` |
| 4 | `src/frontends/customer_ui` | connect WS `role=customer&robot_id=`; on state → `router.push`; on mount `GET /screen` |
| + | `src/backend/app/dispatcher.py` | `on_arrived`, `call` branch: set overlay `"greeting"` + push the waiting screen |

Chặng 1 (agent → backend) follows the `llm-server-pivot` decision (agent co-located with backend
on the server) → in work item #3 `emit_action` calls the screen function **in-process**, no
network hop.

## 5. End-to-end flow (1 robot demo)

```
guest at table 3: "cho tôi xem menu"
  → STT → agent (server) → tool search → action open_menu
  → emit_action(table_id=3, {open_menu})
        overlay[3] = "menu"
        robot_id = tasks.lookup(table_id=3)   # → robo-2
        send_to_customer("robo-2", screen_for(3))   # {"screen":"menu"}
  → customer_ui on robo-2 → router.push('/menu')
guest reloads kiosk → GET /screen?robot_id=robo-2 → screen_for(3) → "menu"  (self-heals)
```
