# Chapter 4 — Diagram Inventory

17 figures, all for Chapter 4. Source: `docs/thesis/diagram.md` (PlantUML) — the single source of
truth; this file is the plain inventory. Rendered to `docs/thesis/images/`. Figures carry no
in-diagram title; each is named only by its document caption.

---

## §4.3 — Software System Architecture

| Figure | Description | Type |
|--------|-------------|------|
| 1 | System Architecture Overview (three-tier deployment block diagram) | Block |
| 7 | Voice Ordering Sequence (end-to-end: tablet → orchestrator → voice device → agent → reply → TTS) | Sequence |
| 11a | Order-to-Delivery Sequence (agent confirms → kitchen display → dispatcher → robot navigation) | Sequence |

### Figure 1 — Visualization Reference

Three columns (Server / Jetson / Browsers), boxes for processes, labelled arrows for protocols and data direction. Keep it high-level: no internal node detail of the agent graph, no API endpoint lists.

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │                     CENTRAL SERVER (x86 + GPU)                     │
 │                                                                     │
 │  ┌──────────────────────┐    ┌──────────────────────────────────┐  │
 │  │  agent_brain (:8100) │    │  server_orchestrator (:8000)     │  │
 │  │  LangGraph agent      │◄──►│  FastAPI REST + WebSocket hub    │  │
 │  │  - router → workers   │HTTP│  - SQLite ledger (orchestrator.db)│  │
 │  │  - validator → tools  │    │  - fleet dispatcher + watchdog   │  │
 │  │  - response generator │    │  - voice bridge (agent↔tablet)   │  │
 │  │                       │    │  - session lifecycle manager     │  │
 │  └──────────┬────────────┘    └────────┬────────────┬────────────┘  │
 │             │                          │            │               │
 │             ▼                          │            │               │
 │  ┌──────────────────────┐              │            │               │
 │  │  Ollama (:11434)     │              │            │               │
 │  │  Qwen2.5 14B Q6_K    │◄─────────────┘            │               │
 │  │  keep_alive = -1     │                           │               │
 │  └──────────────────────┘                           │               │
 │                                                     │               │
 │  ┌──────────────────────┐                           │               │
 │  │  RAG Indices (in-mem)│                           │               │
 │  │  FAISS + BM25 + RRF  │◄──────────────────────────┘               │
 │  │  217 menu dishes     │                                           │
 │  └──────────────────────┘                                           │
 │                                                                     │
 │  ┌──────────────────────┐  ┌──────────────────────────────────────┐ │
 │  │  checkpoints.db      │  │  orchestrator.db                     │ │
 │  │  (LangGraph memory)  │  │  tables · sessions · orders · robots │ │
 │  └──────────────────────┘  └──────────────────────────────────────┘ │
 └──────────────────┬──────────────────────────────────┬───────────────┘
                    │                                  │
              WiFi  │  text transcripts,                │  task.assign,
                    │  voice events                     │  heartbeats
                    │                                  │
 ┌──────────────────▼──────────┐    ┌──────────────────▼────────────────┐
 │  JETSON ORIN NANO (robot)   │    │  STAFF BROWSERS (local WiFi)      │
 │                              │    │                                  │
 │  ┌────────────────────────┐  │    │  customer_ui  ─── WS (role=cust)│
 │  │  Voice Pipeline         │  │    │  (tablet at each table)         │
 │  │  SileroVAD → PhoWhisper │──┼────│  - menu · voice mirror · cart  │
 │  │  → Piper/edge-tts       │  │    │  - VietQR payment screen       │
 │  └────────────────────────┘  │    │                                  │
 │                              │    │  kiosk  ─── REST                 │
 │  ┌────────────────────────┐  │    │  (entrance check-in)             │
 │  │  ROS2 Navigation         │  │    │  - table grid · seat party     │
 │  │  Nav2 · RTAB-Map · EKF   │──┼────│                                  │
 │  │  ArUco docking           │  │    │  panel  ─── WS (role=panel)    │
 │  │  LiDAR · D435 · motors   │  │    │  (kitchen + manager)            │
 │  └────────────────────────┘  │    │  - Kanban board · fleet status  │
 └──────────────────────────────┘    │  - minimap · session timers     │
                                     └──────────────────────────────────┘
```

### Figure 7 — Voice Ordering Sequence (Visualization Reference)

UML sequence diagram with five participants: Tablet, Orchestrator, Voice Device (Jetson), Agent Brain, Ollama. Numbered steps with protocol labels on arrows. Annotate the right side with three key property claims.

```
 Tablet        Orchestrator       Voice Device        Agent Brain        Ollama
   │                │                   │                   │                │
   │① POST /voice/listen               │                   │                │
   │───────────────►│                   │                   │                │
   │                │ ② resolve binding │                   │                │
   │                │──► table→robot    │                   │                │
   │                │                   │                   │                │
   │                │③ WS: start_listening                  │                │
   │                │──────────────────►│                   │                │
   │                │                   │                   │                │
   │                │                   │④ VAD capture      │                │
   │                │                   │   → STT transcribe│                │
   │                │                   │   (~800ms)        │                │
   │                │                   │                   │                │
   │                │                   │⑤ POST /chat       │                │
   │                │                   │  {table_id, text} │                │
   │                │                   │──────────────────►│                │
   │                │                   │                   │⑥ voice.heard   │
   │                │◄──────────────────────────────────────│                │
   │⑦ WS: voice.heard                  │                   │                │
   │◄───────────────│                   │                   │                │
   │  (show transcript,                 │                   │                │
   │   "dang suy nghi")                 │                   │                │
   │                │                   │                   │⑧ router→worker │
   │                │                   │                   │───────────────►│
   │                │                   │                   │⑨ validator→    │
   │                │                   │                   │   tools        │
   │                │                   │                   │⑩ response_node │
   │                │                   │                   │───────────────►│
   │                │                   │                   │                │
   │                │                   │⑪ SSE: sentence 1  │                │
   │                │                   │◄──────────────────│                │
   │                │                   │ → TTS plays       │                │
   │                │                   │⑫ SSE: sentence 2  │                │
   │                │                   │◄──────────────────│                │
   │                │                   │ → TTS plays       │                │
   │                │                   │                   │                │
   │                │⑬ POST /voice/event│                   │                │
   │                │◄──────────────────────────────────────│                │
   │⑭ WS: voice.reply                  │                   │                │
   │◄───────────────│                   │                   │                │
   │  (display reply,                   │                   │                │
   │   sync cart,                       │                   │                │
   │   execute UI action)               │                   │                │
   │                │                   │                   │                │

   Key properties (annotate on diagram right side):
   ┌─────────────────────────────────────────┐
   │ VAD+STT+TTS all run locally on Jetson  │
   │ → no audio crosses the network         │
   │                                         │
   │ Validator sits between LLM output      │
   │ and tool execution (steps ⑧→⑨)        │
   │                                         │
   │ Tablet is a passive viewer —           │
   │ it never controls the microphone       │
   └─────────────────────────────────────────┘
```

### Figure 11a — Order-to-Delivery Sequence (Visualization Reference)

UML sequence diagram with five participants: Agent Brain, Orchestrator, Panel (Kitchen Display), Dispatcher, Robot. Shows how an AI decision cascades into a physical robot action.

```
 Agent Brain      Orchestrator       Panel (Kitchen)     Dispatcher       Robot
     │                 │                   │                  │              │
     │① confirm_order  │                   │                  │              │
     │  POST /orders   │                   │                  │              │
     │────────────────►│                   │                  │              │
     │                 │② INSERT order     │                  │              │
     │                 │   into SQLite     │                  │              │
     │                 │                   │                  │              │
     │                 │③ WS: order.created                  │              │
     │                 │──────────────────►│                  │              │
     │                 │                   │④ card appears    │              │
     │                 │                   │   "Cho Bep"      │              │
     │                 │                   │                  │              │
     │                 │                   │⑤ PATCH /orders   │              │
     │                 │                   │   status=DANG_LAM│              │
     │                 │                   │─────────────────►│              │
     │                 │⑥ WS: order.updated                  │              │
     │                 │──────────────────►│                  │              │
     │                 │                   │⑦ card → "Dang Lam"             │
     │                 │                   │                  │              │
     │                 │                   │⑧ PATCH /orders   │              │
     │                 │                   │   status=XONG     │              │
     │                 │                   │─────────────────►│              │
     │                 │                   │                  │              │
     │                 │⑨ WS: order.updated + create deliver task           │
     │                 │                   │                  │              │
     │                 │                   │                  │⑩ try_assign()│
     │                 │                   │                  │  nearest idle│
     │                 │                   │                  │  battery≥20%│
     │                 │                   │                  │              │
     │                 │                   │                  │⑪ WS: task.assign
     │                 │                   │                  │─────────────►│
     │                 │                   │                  │              │
     │                 │                   │                  │⑫ task_accepted
     │                 │                   │                  │◄─────────────│
     │                 │                   │                  │              │
     │                 │                   │                  │              │⑬ Nav2 navigate
     │                 │                   │                  │              │   to table
     │                 │                   │                  │              │
     │                 │                   │                  │⑭ WS: arrived │
     │                 │                   │                  │◄─────────────│
     │                 │⑮ bind table↔robot voice channel     │              │
     │                 │                   │                  │              │
     │                 │                   │                  │⑯ WS: task_done
     │                 │                   │                  │◄─────────────│
     │                 │                   │                  │  free robot  │
     │                 │                   │                  │  clear bind  │

   Protocols used (annotate on diagram):
   ┌──────────────────────────────────┐
   │ REST:  agent→orchestrator        │
   │        kitchen→orchestrator      │
   │                                  │
   │ WS:    orchestrator→panel (push) │
   │        orchestrator↔robot (bi)   │
   └──────────────────────────────────┘
```

## §4.4 — Edge Voice Pipeline

| Figure | Description | Type |
|--------|-------------|------|
| 8 | Edge Voice Pipeline (SileroVAD → PhoWhisper → Piper, threaded with speech_queue + text_queue) | Pipeline + threading |

## §4.5 — Conversational AI Agent

| Figure | Description | Type |
|--------|-------------|------|
| 2 | Agent Brain Component Overview (nodes, edges, tools, databases at a glance) | Block |
| 3 | Agent StateGraph Topology (10 nodes, 5 normal edges, 6 conditional edges) | Directed graph |
| 4 | Intent Classification (MLP: 768-dim embedding + 10 context features → 4-class output) | Pipeline + NN |
| 5a | Validator Control Flow (LLM output → menu resolution → state checks → pass/reject + feedback) | Flowchart |
| 5b | Menu Resolution Cascade (5-stage pipeline: exact → diacritic → prefix → substring → Jaccard) | Flowchart |
| 9 | Cart / Order Stage Machine (IDLE → DRAFTING → AWAITING_CONFIRMATION → CONFIRMED) | State machine |

### Figure 3 — Agent StateGraph Topology (Visualization Reference)

A directed graph diagram showing ten nodes connected by edges. Normal edges are solid arrows, conditional edges are dashed with labels explaining the branching condition. Four annotated paths highlight the key execution traces.

```
                              ┌──────────┐
                              │  START   │
                              └────┬─────┘
                                   │
                                   ▼
                         ┌─────────────────┐
                         │ classifier_router│  ← intent = ORDER|SEARCH|PAYMENT|CHAT
                         └───┬───┬───┬─────┘
                             │   │   │
              ┌──────────────┘   │   └──────────────┐
              ▼                  ▼                  ▼
    ┌─────────────────┐  ┌──────────────┐  ┌──────────────────┐
    │  order_worker   │  │search_worker │  │payment_dispatch  │  ← LLM (T=0.1, tool_choice="any")
    │  tools: add_cart│  │ tools: search│  │ tools: request_  │
    │  remove_cart    │  │ delegate     │  │        payment   │
    │  clear_cart     │  └──────┬───────┘  └────────┬─────────┘
    │  confirm_order  │         │                    │
    │  delegate       │         │                    │
    └────────┬────────┘         │                    │
             │                  │                    │
             │    ┌─────────────┘                    │
             │    │                                  │
             ▼    ▼                                  ▼
    ┌─────────────────────────────────────────────────────────┐
    │              _route_if_tool_call                       │  ← conditional edge
    │   has tool_call? ──yes──→                              │
    │   only delegate? ──yes──→ state_updater (skip tools)   │
    │   no tool_call + ORDER intent? ──→ chat_worker         │
    └──────────────────────┬──────────────────────────────────┘
                           │ (has CRUD tool call)
                           ▼
                  ┌─────────────────┐
                  │   validator     │  ← deterministic, pure Python
                  │  resolve_menu() │
                  │  check_stage()  │
                  │  check_cart()   │
                  └────────┬────────┘
                           │
              ┌────────────┴────────────┐
              │ _route_after_validator  │  ← conditional edge
              │   valid? ──yes──→ tools │
              │   invalid + retry<3? ──→ back to worker │
              │   invalid + retry≥3? ──→ state_outcome  │
              └────────────┬───────────┘
                           │ (valid)
                           ▼
                  ┌─────────────────┐
                  │     tools       │  ← LangGraph ToolNode
                  │  execute tool   │
                  │  return result  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  state_updater  │  ← deterministic
                  │  merge results  │
                  │  advance cart   │
                  │  pop intent     │
                  └────────┬────────┘
                           │
              ┌────────────┴────────────┐
              │  _route_after_updater   │  ← conditional edge
              │   more intents? ──yes──→ next worker │
              │   queue empty? ──yes──→ state_outcome│
              └────────────┬───────────┘
                           │ (done)
                           ▼
                  ┌─────────────────┐
                  │  state_outcome  │  ← deterministic
                  │  build Response │
                  │  Context        │
                  │  reset per-turn │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  response_node  │  ← LLM (T=0.3) or templates
                  │  generate reply │
                  └────────┬────────┘
                           │
                           ▼
                      ┌──────────┐
                      │   END    │
                      └──────────┘

                              ┌─────────────────────┐
                              │     chat_worker     │  ← deterministic leaf
                              │  build curated      │
                              │  memory context     │
                              └──────────┬──────────┘
                                         │
                                         │ (bypasses validator + tools + state_updater)
                                         ▼
                                  state_outcome → response_node → END

   Four annotated paths (highlight on diagram with distinct colours or line styles):

   Path A — Tool execution (ORDER, SEARCH, PAYMENT):
     router → worker → [validator → tools → state_updater] × N intents → state_outcome → response_node → END

   Path B — Retry loop (validator rejects, retry < 3):
     validator ──(invalid + feedback)──→ worker (retries with correction instructions)

   Path C — Circuit breaker (validator rejects, retry ≥ 3):
     validator ──(invalid, exhausted)──→ state_outcome (apology response, no side effects)

   Path D — Chat leaf (CHAT intent or delegate-only):
     router → chat_worker → state_outcome → response_node → END
     (validator, tools, and state_updater are bypassed — no actions to validate)

   Key properties (annotate on diagram):
   ┌──────────────────────────────────────────────┐
   │ All LLM nodes (order_worker, search_worker, │
   │ response_node) are marked with a GPU icon    │
   │                                               │
   │ All deterministic nodes (classifier_router,   │
   │ validator, state_updater, state_outcome,      │
   │ chat_worker) are marked with a gear icon      │
   │                                               │
   │ Conditional edges show the branching logic    │
   │ ── _route_if_tool_call,                      │
   │    _route_after_validator,                    │
   │    _route_after_updater                       │
   │                                               │
   │ Circuit breaker: loop_count ≥ 3 → forced     │
   │ exit through state_outcome                    │
   └──────────────────────────────────────────────┘
```

## §4.6 — Knowledge Retrieval Pipeline

| Figure | Description | Type |
|--------|-------------|------|
| 6 | Hybrid Retrieval Pipeline (query → LLM rewrite → BM25 + FAISS → RRF fusion → LLM rephrase) | Pipeline |

## §4.7 — Backend Orchestrator & Real-Time Systems

| Figure | Description | Type |
|--------|-------------|------|
| 10a | Database Schema — business ledger (tables, sessions, orders, order_items, payments) | ERD |
| 10b | Database Schema — fleet tables (robots, tasks, join to tables) | ERD |
| 11b | Session Lifecycle (seating → orders → payment → table release, with conversation thread isolation) | Sequence |
| 12a | Task Lifecycle + Robot States (PENDING → ASSIGNED → IN_PROGRESS → DONE, robot state driven by tasks) | State machine |
| 12b | Dynamic Voice Binding (table → robot → voice-device resolution on arrival + release on departure) | State machine |
| 13 | WebSocket Hub (four roles: panel, customer, robot, voice-device, one /ws endpoint) | Component |

## §4.8 — Web Interfaces

No dedicated figures; the three SPAs are described in prose with reference to Figures 1, 7, and 13 for their communication patterns.

## §4.9 — Deployment Topology

No dedicated figure; covered by Figure 1 (System Architecture Overview) and the prose description of the two-machine topology.
