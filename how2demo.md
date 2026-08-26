# How to Demo — AI Warehouse Waiter (voice + robot simulation)

## 0. One-time prep (do this before the demo day)

```bash
# from the repo root
make install            # if deps not yet installed
make reindex            # build the RAG index + intent router (takes a few minutes, downloads a model)
```

- `make reindex` only needs to run once, or after you change the embedding model / warehouse data.
- On demo day you do **not** need to run it again.

---

## 1. Clean start (always do this first)

```bash
make kill                                   # stop any leftover servers
rm -f storage/db/orchestrator.db            # IMPORTANT: drop any old DB (old schema silently breaks navigation)
```

> Why the `rm`: an old `orchestrator.db` can be missing the `pose_*` columns the dispatcher needs,
> and the task would fail *silently* (agent says "navigate" but the robot never moves). A fresh DB
> reseeds itself on next start.

---

## 2. Start the 5 components (5 terminals)

Open five terminals in the repo root. Start them in this order:

| # | Terminal | Command | What it is |
|---|----------|---------|------------|
| 1 | Backend  | `make backend`   | REST + WebSocket server (port 8000) — the single source of truth |
| 2 | Robot sim| `make mockrobot` | **Simulated AGV** (stand-in for the real robot) — watches its terminal for drive logs |
| 3 | Brain    | `make agent`     | LLM agent service (port 8100) — understands speech, decides answer vs navigate |
| 4 | Voice    | `make voice`     | **Edge voice device** (mic + speaker) — needs a microphone & speakers on this machine |
| 5 | Tablet   | `make menu`      | Customer tablet UI (http://localhost:5173) — what the "guest" uses |

Optional but nice for the teacher: also run `make panel` (terminal 6) → http://localhost:5175,
the **warehouse map** where you can watch the robot dot move to Khu B and back.

Wait until each terminal prints it is "ready"/listening before moving on:
- backend: `Uvicorn running on http://127.0.0.1:8000`
- mockrobot: `[robo-1] connected to ws://.../ws?role=robot&robot_id=robo-1`
- agent: `Uvicorn running on http://127.0.0.1:8100` + `Warmup complete`
- voice: `[READY] đã kết nối backend (robo-1) — chờ điều tới bàn...`
- menu: `Local: http://localhost:5173`

> All on one laptop is fine. If voice runs on a different machine, set `AGENT_URL` and
> `ORCHESTRATOR_URL` in `.env` to the server's IP (not `localhost`) before `make voice`.

---

## 3. The demo script (say these out loud via the tablet)

1. Open **http://localhost:5173** in a browser (this is the "tablet").
   (Open **http://localhost:5175** too if you started the panel — you'll watch the map there.)
2. Click the **"Nói Chuyện Với AI"** (Talk to AI) button.
3. **Turn 1 — ask for info** (no movement expected):
   > "Bột mì để ở đâu?"
   - Robot speaks the location (e.g. "Bột mì nằm ở khu A, lối 3, bin 12").
   - The simulated robot must **stay at the dock** (no drive).
4. Click **Talk** again.
   **Turn 2 — ask to go to Khu B** (this should trigger movement):
   > "Đưa tôi đến khu B"
   - Robot speaks: "Đang dẫn bạn đến Khu B (khu B)."
   - **The mock-robot terminal (terminal 2) starts driving** and the panel map dot moves toward Khu B.
5. **Turn 3 — ask about Khu B WHILE it is moving** (the key moment):
   Click **Talk** again (you can do this right after Turn 2, while the dot is still moving):
   > "Khu B có những gì?"
   - Robot answers the list of items in Khu B (e.g. "Khu B có: Thùng bia, Nước ngọt, Cà phê, Trà, Sữa hộp.").
   - **No second drive** is triggered — the robot keeps its existing trip to Khu B.

That's the whole story: the guest gets info, asks to be taken somewhere, and can keep
asking questions *during* the ride without interrupting the navigation.

---

## 4. How to prove it actually worked (what to point at)

On the teacher's screen / your terminals, show these:

- **Terminal 2 (mockrobot)** — the AGV's own log proves it received and executed the command:
  ```
  [robo-1] task 1 (navigate → B) → accept
  [robo-1] task 1 → arrived (B)
  [robo-1] task 1 → done
  [robo-1] về tới dock
  ```
- **Terminal 3 (agent)** — proves the brain decided to navigate and forwarded it:
  ```
  [INFO] [src.agent_brain]: forwarding navigate token 'B' to orchestrator
  ```
- **Terminal 1 (backend)** — proves the HTTP signal left the agent:
  ```
  INFO: ... "POST /navigation HTTP/1.1" 201 Created
  ```
- **Panel map (localhost:5175)** — visual proof: the robot dot travels to Khu B and returns to dock.
- **Turn 3 reply** — proves context is kept: it answers about Khu B *without* re-issuing a move,
  so the robot doesn't get a contradictory second command mid-trip.

Quick DB check (run anytime) confirms a task was dispatched and completed:
```bash
sqlite3 storage/db/orchestrator.db "SELECT id,kind,target_token,robot_id,status FROM tasks;"
# → 1|navigate|B|robo-1|DONE
```

---

## 5. Troubleshooting (if something looks wrong live)

- **Robot doesn't move on Turn 2, but agent says "Đang dẫn bạn đến Khu B":**
  - Check terminal 2 (`mockrobot`) shows `connected`. If not, restart `make mockrobot`.
  - Check terminal 1 shows `POST /navigation ... 201`. If not, the DB is likely stale →
    `make kill`, `rm -f storage/db/orchestrator.db`, restart from section 2.
  - Run the DB check above; if `tasks` is empty, the signal never arrived.
- **Turn 2 answers "Khu B có: …" instead of navigating:**
  - You are on old code. Make sure the router fix is present
    (`src/agent_brain/warehouse/nodes/mlp_router_node.py`: a section + movement cue → `NAVIGATE`).
- **Voice device not hearing / no reply:**
  - Confirm `make voice` is running and the mic works (`make probe` tests mic→STT).
  - If voice is on another machine, fix `AGENT_URL` / `ORCHESTRATOR_URL` in `.env` to the server IP.
- **Panel map not moving:** open the **panel** UI (`:5175`), not just the tablet (`:5173`).

---

## 6. What was fixed to make this demo possible (for your own notes)

1. **Router bug** — any mention of "khu X" was forced to *answer*, so "move to Khu B" could never
   navigate. Fixed: a section + a movement cue (đến/tới/dẫn/đưa…) is now `NAVIGATE`;
   a bare "khu B có gì" stays `ANSWER`.
2. **Stale DB schema** — an old `orchestrator.db` lacked the `pose_*` columns, so task assignment
   crashed silently. Fix: delete the DB so it reseeds with the current schema (section 1 / 5 above).

Both are already applied in the code; the only manual step is the `rm` of the old DB on a fresh machine.
