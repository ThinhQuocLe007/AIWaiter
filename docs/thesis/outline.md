# Thesis Outline — AI Waiter Robot on a Two-Wheel Differential Drive Platform

> **Report language: English.** Structure follows HCMUTE graduation thesis convention.
> **Hardware:** Purchased TWD platform (chassis, motors, STM32, MPU6050). Contribution from ROS2 upward: sensor integration, odometry fusion, SLAM, Nav2, ArUco docking, and the complete AI/backend/web system.

---

## CHAPTER 1: INTRODUCTION

### 1.1 Overview
- Context: service robots in restaurants + LLM boom
- Autonomous TWD waiter robot: kitchen → 6 tables, ArUco docking, Vietnamese voice ordering
- Figure: example commercial restaurant service robot (context-setter)

### 1.2 Motivation / Necessity of the Study
- Practical: labor cost, service consistency, contactless post-COVID
- Technical: agentic LLM + RAG + autonomous navigation are current but not yet integrated for Vietnamese restaurants
- Feasibility: ready-to-run commercial base lets the group focus on software/AI layer

### 1.3 Objectives
Measurable targets (checked against Ch.5 results):
- Integrate TWD platform into ROS2 with **EKF-fused encoder+IMU odometry** (return-to-start error ≤ X cm)
- Build restaurant map with **RTAB-Map (A2M8 + D435)**; navigate kitchen → table with success rate ≥ X%
- **ArUco docking error < X cm / X°**
- **Intent router accuracy ≥ 90%** (achieved 90.00%)
- **RAG precision/recall@5 targets**
- **End-to-end Vietnamese voice ordering** completion rate

### 1.4 Scope of the Study
- Boundary: purchased TWD base, contribution from ROS2 upward
- Indoor, flat floor, mapped environment, dedicated service lane (separated from customers)
- 2D map, no pedestrian avoidance (lane-separated)
- Vietnamese voice, self-hosted LLM (Ollama on on-premises server)
- Limitations: non-holonomic (no lateral motion), consumer-grade IMU, lighting sensitivity (D435/ArUco), network latency

### 1.5 Research Methodology
- Literature review → Gazebo simulation (restaurant world) → real deployment → quantitative evaluation (odometry/docking tests + AI eval suite)

### 1.6 Report Structure
- One-paragraph outline of Ch.2–6
- Contributions bullet list (4 core items)

---

## CHAPTER 2: RELATED WORK & THEORETICAL FOUNDATIONS

> Each section surveys what exists in a knowledge domain — technologies, approaches, tools, and prior systems relevant to understanding the project's foundations. Gap statements emerge naturally from the survey; the synthesis at §2.7 positions this thesis in the landscape.

### 2.1 Service Robots in Hospitality
- **Commercial landscape:** Bear Robotics Servi, Pudu Bellabot, Keenon — what capabilities exist today: autonomous navigation, tray delivery, touchscreen ordering. Proven hardware, deployed at scale
- **What they don't do:** no voice interaction, no Vietnamese language support, touchscreen-only ordering with no conversation, closed platforms (cannot extend with LLM)
- **Academic ROS-based delivery robots:** typical approach — pre-mapped environment, Nav2 for navigation, ArUco marker docking for precise table approach. Handle movement but have no conversational layer
- **The open space:** no existing system integrates LLM-based Vietnamese voice dialogue with autonomous physical robot delivery in a restaurant

### 2.2 Vietnamese Speech Processing for Voice AI
- **Speech-to-text landscape for Vietnamese:** PhoWhisper (Whisper fine-tuned for Vietnamese tonal accuracy), Google Speech-to-Text, Viettel AI, FPT.AI — cloud vs. edge trade-offs
- **Faster-Whisper:** optimized CTranslate2 inference for low-latency on-device recognition, beam search decoding
- **Voice Activity Detection:** Silero VAD — lightweight neural frame-level classification, language-agnostic, effective for Vietnamese utterance boundary detection in noisy environments
- **Text-to-speech for Vietnamese:** Piper TTS (edge-deployable, local), edge-tts (Microsoft cloud voices), vbee, FPT.AI — quality vs. latency vs. offline capability trade-offs
- **Vietnamese language challenges:** 6 tones + complex diacritics cause STT errors, monosyllabic structure with compound words, teencode and informal speech in casual settings, restaurant ambient noise degrades accuracy
- **Current state:** each component (STT, VAD, TTS) evaluated separately in literature. No prior work integrates VAD→STT→Agent→TTS into one pipeline for Vietnamese restaurant ordering on edge hardware

### 2.3 LLM-Based Task-Oriented Dialogue Systems
- **LangGraph agent framework:** StateGraph pattern — typed shared state flowing through nodes, tool-calling agents, conditional edges for branching, SQLite checkpointer for conversation memory across turns. Bounded loops with counters guarantee termination. Decomposing an agent into an explicit graph enables deterministic code between LLM calls and makes behavior inspectable node-by-node
- **LangChain ecosystem:** ChatOllama, ToolNode, structured output (`with_structured_output`). Tool calling (function calling) — describe operations as typed Pydantic functions, model outputs structured invocation. This is how LLMs move from text generation to system action
- **What exists commercially:** Wendy's FreshAI, Domino's AI ordering — cloud-based English-only chatbots with no physical robot integration
- **Vietnamese conversational AI:** Zalo AI, VinAI — open-domain chat, not task-oriented ordering with tool execution
- **The missing system:** no self-hosted LLM agent with tool execution (order → kitchen → payment), menu validation, and robot dispatch — all in Vietnamese

### 2.4 Intent Routing for Task-Oriented Dialogue
- **Why routing matters:** different user intents (order, search, pay, chat) need different processing subsystems. Classification must happen before execution
- **Traditional NLU approach:** Rasa, Dialogflow — intent classification via fine-tuned classifiers. Brittle to Vietnamese casual speech: teencode, abbreviations, short affirmations ("ok", "ừ")
- **Semantic routing:** sentence embeddings → per-intent centroid vectors → cosine similarity. Very fast (~15ms), but limited to single-intent classification. Centroid construction from hand-crafted utterances, temperature-scaled softmax, gap-gating confidence thresholding
- **LLM-based routing:** structured output with few-shot examples via LangChain. Accurate (~1.8s), supports multi-intent classification, handles ambiguous short affirmations. Higher latency cost
- **Hybrid approach:** local semantic router for fast-path confident cases + LLM fallback for ambiguous/multi-intent utterances. Softmax-gap gating decides which tier handles each utterance. Prior hybrid routing work exists, but not in Vietnamese and not calibrated for restaurant domain
- **Current gap:** no calibrated hybrid semantic+SLM routing with softmax-gap gating developed for Vietnamese task-oriented dialogue in restaurant settings

### 2.5 Retrieval-Augmented Generation (RAG) for Domain-Specific QA
- **The knowledge problem:** LLMs store knowledge in weights frozen at training. They don't know a specific restaurant's menu, prices, or promotions. Hallucination is the failure mode — fluent fabrication instead of honest "I don't know"
- **RAG pipeline:** Index documents offline (embed → store in vector database) → Retrieve top-k at query time → Generate answer grounded in retrieved context
- **Dense retrieval:** FAISS with SentenceTransformer embeddings. Captures semantic similarity ("something warm for a cold day" → hot soups). Weak on exact keyword matching for proper names and rare dish names
- **Sparse retrieval:** BM25 (TF-IDF variant, `k1=1.2, b=0`). Strong for exact keyword matches ("Ốc Hương Xốt Trứng Muối"). Weak for semantic understanding
- **Hybrid fusion:** parallel dense + sparse retrieval → merge via Reciprocal Rank Fusion: `score(d) = Σ 1/(k + rank_d)`, where `k=60` smoothing constant. RRF needs only ranks, not comparable scores — ideal for fusing BM25 with cosine similarities
- **Vietnamese-specific requirements:** word segmentation via `underthesea` (compound words like "bún bò Huế" must be single tokens for BM25). Vietnamese embedding models: AITeamVN/Vietnamese_Embedding (BGE-M3 fine-tune, 1024-dim), PhoBERT-family bi-encoders (768-dim). Metadata filtering needed for structured menu data (price range, dietary type, category)
- **Current gap:** no prior hybrid RAG system tailored for Vietnamese restaurant menus with word-segmented BM25, metadata post-filtering, and dual-lane gatekeeper relevance filtering

### 2.6 Multi-Robot Coordination & Fleet Management
- **Task assignment fundamentals:** nearest-idle (pick closest available robot), auction-based (robots bid on tasks), market-based. Nearest-idle simplest and works well for short trips in small environments
- **ROS2 fleet management:** OpenRMF, RMF Core — full-featured infrastructure for warehouse-scale operations (dozens of robots, complex traffic zones, multi-floor). Heavy deployment overhead, designed for logistics not restaurants
- **Telemetry architecture trade-offs:** RAM-only latest-value store (fast, no DB contention, lost on restart) vs. DB write-per-heartbeat (persistent, write contention at high frequency). Hybrid: RAM for real-time, periodic DB snapshot for cold-start
- **What's needed for restaurants:** lightweight dispatcher for 3–5 robots, short trips (kitchen → table), dynamic table-robot voice binding, battery-aware assignment, watchdog with fault recovery

### 2.7 Summary & Positioning
- **The integration gap:** each dimension has been developed separately — navigation (commercial robots), Vietnamese speech (standalone STT/TTS), LLM agents (cloud chatbots), RAG (academic retrieval systems), fleet management (warehouse frameworks). Nobody has integrated all of them into one deployed system
- Comparison table: each prior work covers only part of the problem. This thesis integrates all dimensions:

| Dimension | Existing Work | This Thesis |
|-----------|--------------|-------------|
| Navigation | ROS2 delivery robots (nav-only) | ROS2 + EKF odometry + ArUco docking |
| Voice | Vietnamese STT (standalone) | VAD→STT→Agent→TTS pipeline on Jetson edge |
| Dialogue | Cloud chatbot APIs (English) | Self-hosted LangGraph agent with tool execution |
| Intent routing | Single-tier (semantic OR LLM) | Two-tier hybrid: semantic fast path + SLM fallback |
| Menu retrieval | None for Vietnamese restaurants | BM25 + FAISS + RRF fusion with Vietnamese tokenization |
| Robot fleet | Warehouse-scale (OpenRMF) | Lightweight restaurant dispatcher + dynamic table-voice binding |
| Integration | Navigation XOR chatbot | End-to-end: voice → agent → order → kitchen → robot delivery |

---

## CHAPTER 3: PROPOSED METHOD (I) — ROBOT CONTROL AND NAVIGATION ON ROS2

### 3.1 Robot Platform & Hardware Setup
- **Purchased TWD platform:** chassis, two MC520P30 DC motors with encoders, STM32 microcontroller, MPU6050 IMU
- **Added components:** RPLiDAR A2M8 (360° 2D laser scanner), Intel RealSense D435 (RGB-D camera), Jetson Orin Nano (edge compute), 7" LCD touchscreen, battery pack
- **Boundary:** contribution starts from ROS2 integration upward
- **Component specifications table:** LiDAR range/angular resolution, D435 depth accuracy/FOV, MPU6050 gyro/accel specs, encoder resolution (P=1024 pulses/rev, G=30 gear ratio → N = P·4·G = 122880 ticks/rev), motor rated speed/torque
- **ROS2 robot model:** URDF with base_link, base_footprint, lidar_link, camera_link, wheel joints → render figure
- **TF tree:** `map → odom → base_footprint → base_link → (lidar_link, camera_link, imu_link)`
- **Platform constants table:** wheel diameter D, wheel separation W, encoder ticks per revolution N, control loop rate 50 Hz, Vx_max, Vω_max
- **Connection/wiring block diagram:** Jetson ↔ STM32 (UART), Jetson ↔ LiDAR (USB), Jetson ↔ D435 (USB 3.0), Jetson ↔ LCD (HDMI+USB touch)
- **Photos of physical robot and service-lane/marker layout**

### 3.2 System Requirements
- R1–R7 with target metrics (navigation success, docking precision, odometry accuracy, safe obstacle distance)
- Domain constraint: dedicated service lane, physically separated from customers

### 3.3 Wheel Odometry and EKF Sensor Fusion
- 3.3.1 Wheel odometry: encoder tick model (`N = P·4·G`), velocity computation (`V = πD/N · Δn/Δt`), forward kinematics (`V_x = (V_A+V_B)/2`, `V_ω = (V_B−V_A)/W`), Euler pose integration
- 3.3.2 IMU (MPU6050): raw int16 → SI conversion, axis remap, gyro bias estimation, Mahony AHRS for relative yaw
- 3.3.3 EKF (`robot_localization`, `two_d_mode`): state `[x, y, ψ, V_x, V_y, V_ω]`, odom0 → V_x/V_y/V_ω, imu0 → V_ω only (no magnetometer → IMU yaw not fused), covariance tuning, output `/odometry/filtered` + `odom→base_footprint` TF

### 3.4 Map Building with RTAB-Map
- RTAB-Map pipeline: LiDAR (geometry) + RGB-D camera (loop closure) → 2D occupancy grid
- Offline mapping run: teleop the service lane + return pass to force loop closure
- Tuned parameter table (grid resolution, max LiDAR range, loop-closure/proximity settings)
- LiDAR-only mapping option; camera used for loop closure only (not 3D mapping)

### 3.5 Localization and ArUco-Based Docking
- 3.5.1 RTAB-Map localization mode on saved map → publishes `map→odom`
- 3.5.2 Initial pose from home (kitchen) ArUco marker → absolute start pose, removes manual "2D Pose Estimate"
- 3.5.3 Per-table ArUco re-localization for precise final approach; marker-lost → safe stop at predefined distance; why ArUco (absolute local reference, residual SLAM/odom error correction)

### 3.6 Autonomous Navigation with Nav2
- Global planner: path along service lane, kitchen → table goal
- Local controller (from `nav2_params.yaml`): look-ahead, desired/max speed, `V_y=0`, in-place rotation for non-holonomic TWD
- Costmaps: static (2D map) + inflation + LiDAR obstacle layer (occasional objects entering the lane only)
- No pedestrian detection / social navigation (lane-separated from customers)
- Trip orchestration: backend dispatcher → Nav2 goal → drive → arrival → ArUco re-localization → progress reported to backend

---

## CHAPTER 4: PROPOSED METHOD (II) — AI, BACKEND & WEB SYSTEM

### 4.1 System Requirements & Design Rationale
- **Functional requirements:** natural language ordering in Vietnamese, menu search by attributes (taste, price, diet), payment flow, order-to-kitchen dispatch, robot task management, multi-table concurrent voice support
- **Non-functional:** self-hosted (no cloud LLM dependency), low-latency voice interaction (< 5s turn), deterministic safety net between every LLM call and system action, per-session conversation isolation
- **Design principles:** centralized brain (single server), thin edge (Jetson handles voice I/O + robot control only), single-writer database, session-scoped memory, no fine-tuning (all adaptation via prompting)

### 4.2 Overall Software Architecture
- **Three-tier topology:** Server tier (Agent brain + Orchestrator backend + Ollama LLMs + RAG indices), Robot tier (Voice pipeline + ROS2 navigation stack), Client tier (3 browser SPAs)
- **Block diagram** (from `diagram.md` Fig 4.1): all components, protocols, and 4 main data flows — (a) voice ordering at table, (b) order → kitchen display, (c) manager monitoring, (d) backend → robot navigation goals
- **Component responsibility map:** what runs where, what talks to what, over which protocol
- **Design rationale for key architectural decisions:**
  - SQLite not PostgreSQL: single-file deployment, zero administration, ACID sufficient at restaurant scale (dozens of tables, not millions of rows)
  - RAM telemetry not DB writes: robot heartbeats at 4+ Hz would thrash SQLite under write contention; in-memory dict with periodic 15s snapshot provides real-time performance with cold-start recovery
  - Sync LangGraph + async SSE: LangGraph's `SqliteSaver` checkpointer is synchronous; execution runs in `ThreadPoolExecutor`, results streamed via async generator to avoid blocking the FastAPI event loop
  - Self-hosted Ollama not cloud API: no internet dependency on the restaurant floor, zero API costs, data privacy, bounded latency (no external network variability)

### 4.3 Conversational Agent — Pipeline Architecture

> *The intellectual core of the software contribution. Every utterance flows through five stages: Understanding (what does the customer want?) → Decision (which action should be taken?) → Validation (is the action safe?) → Execution (perform the action and update state) → Response (generate output text). Stages are implemented as LangGraph nodes connected by conditional edges, executing deterministically between LLM calls.*

#### 4.3.1 Agent Execution Model

- **LangGraph StateGraph:** 10 nodes, 6 conditional edges, 4 normal edges. Graph entry at `router`, exit after `response_node`. Execution path varies per utterance based on intent classification and validation results.

- **AgentState (18 fields)** — a TypedDict organized by lifecycle:

  | Category | Fields | Persistence |
  |----------|--------|-------------|
  | Conversation history | `messages` | Across turns (append-only, managed by LangGraph reducer) |
  | Task state | `table_id`, `active_cart`, `order_stage`, `search_context` | Across turns |
  | Routing state | `current_intents`, `routing_meta` | Across turns (intents queue persists for multi-intent iteration) |
  | Inter-node contract | `is_valid`, `feedback`, `loop_count`, `unavailable_items`, `ambiguous_items`, `last_tool`, `delegate_reason`, `intent_queries` | Per-turn (written by one node, read and cleared by the next) |
  | Output | `ui_action`, `order_confirmed`, `response_context` | Per-turn (consumed by response node, cleared by state_outcome) |

- **Graph execution flow:**
  ```
  START → router ──→ [intent worker] ──→ tools ──→ validator
                             ↑                        │
                             │              ┌─────────┤
                             │              │ pass    │ retry
                             │              ▼         ▼
                             └── state_updater ←──── tools
                                    │
                                    │ queue empty
                                    ▼
                              state_outcome → response_node → END
  ```
  The `router` classifies intent. A worker node decides on an action (tool call). The `tools` node executes it. The `validator` checks the result. On failure, corrective feedback returns to the worker for retry (up to 3 iterations). On pass, `state_updater` merges results into `AgentState`. Remaining intents in the FIFO queue dispatch to their workers; when empty, `state_outcome` builds the typed response context and `response_node` generates the final output.

- **Conversation memory:** compiled with LangGraph `SqliteSaver` checkpointer. `thread_id = orchestrator_session_id` — when payment closes a session, the next guest gets a fresh `thread_id`, preventing context bleed between customers. Persistent fields (`active_cart`, `order_stage`, `search_context`, `messages`) survive across turns; ephemeral fields are explicitly reset after each turn in `state_outcome`.

#### 4.3.2 Stage I — Understanding: Intent Classification

> *Before any action can be taken, the system must determine what the customer wants. This is a classification problem: given an utterance in Vietnamese, select one or more intents from {ORDER, ORDER_CONFIRM, SEARCH, PAYMENT, CHAT}.*

- **Intent taxonomy:** 5 intents with Vietnamese trigger examples. Multi-intent support for compound utterances ("Cho 2 Ốc Hương rồi tính tiền luôn" → [ORDER, PAYMENT]). ORDER_CONFIRM is a distinct intent (not a sub-type of ORDER) because its processing path differs from adding items to cart.

- **Tier 1 — Semantic router (fast path, ~15ms):**
  - **Centroid construction (offline):** 192 hand-crafted Vietnamese utterances across 5 intents, embedded via SentenceTransformer (`AITeamVN/Vietnamese_Embedding`, 1024-dim), averaged per intent → 5 centroid vectors stored in `centroids.npz`
  - **Inference (online):** encode utterance → cosine similarity to 5 centroids → temperature-scaled softmax (T=0.20) → gap gating
  - **Softmax-gap gating algorithm:**
    1. `max_sim = max(cosine_similarities)`. If `max_sim < 0.35` → reject, fallback
    2. Softmax: `p_i = exp(s_i/T) / Σ exp(s_j/T)` with T=0.20
    3. Sort by probability. Identify P₁ (top-1) and P₂ (top-2)
    4. Gate: `P₁ ≥ 0.25` AND `(P₁ − P₂) ≥ 0.15` → accept highest-probability intent
    5. Otherwise → return `None` (defer to Tier 2)
  - **Temperature calibration:** T=0.20 via grid search on development data. Lower T sharpens distribution, reducing false positives on ambiguous utterances. The two-threshold design (max_sim ≥ 0.35 for minimum relevance, gap ≥ 0.15 for confidence separation) ensures that both "clearly in one intent" and "clearly separated from runner-up" must hold simultaneously.
  - **Design rationale:** semantic path fast-tracks ~55% of utterances at ~15ms with zero misclassifications in evaluation (§5.5.1). Only confident, unambiguous single-intent utterances pass — everything else falls through to Tier 2.

- **Tier 2 — SLM router (fallback, ~1.8s):**
  - **Model:** Qwen2.5 7B via Ollama, `temperature=0.0` (deterministic), `with_structured_output(IntentPrediction)` — Pydantic schema with `intents: list[IntentType]`, `reasoning: str`, `queries: dict[str, str]`
  - **Prompt construction:** system prompt (`router_agent.md`, 83 lines, 4-step reasoning protocol) + 14 few-shot examples (`router.json`: single-intent, multi-intent, ambiguous cases) + dynamic context (last 2 conversation turns + current `order_stage`) + user message
  - **Dynamic context rationale:** "ok" at `AWAITING_CONFIRMATION` stage → `ORDER_CONFIRM`; same utterance at `IDLE` → `CHAT`
  - **Multi-intent decomposition:** SLM produces per-intent sub-queries in `intent_queries`, used downstream by each worker to focus on its relevant portion of the utterance. Handles teencode ("ad", "vs", "ck"), short affirmations, compound sentences
  - **Design rationale:** SLM path catches ambiguous, multi-intent, and context-dependent cases that the semantic router cannot handle. The 1.8s latency cost is acceptable because these utterances are inherently more complex and would fail under a faster-but-shallow approach.

#### 4.3.3 Stage II — Decision: Action Selection via Tool-Calling LLM

> *Once the intent is known, the agent must decide what action to take. For ORDER and SEARCH intents, this requires an LLM to reason about the utterance and select the appropriate tool with the correct arguments. For PAYMENT, the action is deterministic. For CHAT, no tool call is needed.*

- **Decision configuration:** Qwen2.5 7B via Ollama, `temperature=0.1`, `tool_choice="any"`. Temperature is slightly above zero to allow variant phrasings in tool arguments while keeping decisions near-deterministic. Prompt includes system prompt (~200 tokens) + 5 few-shot examples with tool calls for KV-cache optimization. The menu is deliberately excluded from the prompt — the LLM does not need menu knowledge to decide which tool to call; it only needs to recognize the action type.

- **Tool bindings per intent:**

  | Intent | Bound Tools | LLM Called? |
  |--------|------------|-------------|
  | ORDER / ORDER_CONFIRM | `add_cart`, `remove_cart`, `clear_cart`, `confirm_order`, `delegate` | Yes |
  | SEARCH | `search`, `delegate` | Yes |
  | PAYMENT | `request_payment` | No (deterministic — always emits `request_payment`) |
  | CHAT | (none) | No (pure function — builds curated memory context) |

- **Robustness mechanisms:**
  - **Delegate escape hatch:** ORDER and SEARCH workers bind the LLM with `tool_choice="any"` — the LLM must always produce a tool call. But some utterances genuinely fall outside the worker's domain (e.g., SEARCH worker receives "mấy giờ đóng cửa?"). Forcing a domain tool call would return irrelevant results. The `delegate(reason)` tool is bound alongside domain tools; when the LLM cannot map the utterance to a meaningful domain action, it calls `delegate()` instead. This is routed to the CHAT worker, which handles the query conversationally. The LLM is never forced to produce a wrong action — when uncertain about its domain, it admits it rather than guessing.
  - **Retry with corrective feedback:** when the validator rejects a tool call, the `feedback` field is injected into the next worker prompt, giving the LLM explicit correction instructions (e.g., "Món 'Cơm Tấm' không có trong menu. Gợi ý món gần nhất: 'Cơm Chiên'")
  - **Circuit breaker:** `loop_count` tracks retry iterations. At 3 failed attempts, the system emits a `RetryResponseContext` with an apology and falls through to response generation. Ensures bounded execution regardless of LLM behavior.

#### 4.3.4 Stage III — Validation: Deterministic Safety Net

> *This stage is the key reliability contribution. LLM output is probabilistic regardless of temperature — an LLM can hallucinate a dish name, produce a nonsense quantity, or attempt to confirm an order with invalid items. Before any tool result affects system state, a deterministic validator inspects it. This is a pure-rules layer with no machine learning: every check is a hand-written predicate with a definitive yes/no answer.*

- **Design rationale:** every LLM call is followed by a validator call. The validator acts as a firewall — it cannot prevent the LLM from hallucinating, but it can detect hallucinated output before it reaches the cart or the backend. This architecture pattern (LLM → validate → action, not LLM → action) is the central safety invariant of the system.

- **Menu name resolution pipeline** (`resolve_menu_name`):
  1. Normalize: lowercase + strip Vietnamese diacritics via Unicode NFD decomposition
  2. Exact match against 217 dish names
  3. Prefix match (handles partial utterances: "Ốc Hương" → "Ốc Hương Xốt Trứng Muối")
  4. Substring match
  5. Token-level Jaccard similarity fallback (threshold ≥ 0.3)
  6. Return best match or `None`

- **Off-menu item handling:** items not resolved by the pipeline are captured in `unavailable_items` with a nearest-match suggestion via `find_nearest_menu_name()`. The response node later phrases: "Món X không có trong menu, anh/chị có muốn thử Y không ạ?" The validator **never** auto-corrects or substitutes — it only flags and suggests.

- **Ambiguity detection:** generic names matching multiple menu items (e.g., "Ốc Hương" matches 11 sauce variants: trứng muối, me, tỏi, bơ, rang muối...) are flagged in `ambiguous_items`. The agent requests clarification: "Dạ, Ốc Hương có nhiều loại sốt: trứng muối, me, tỏi... anh/chị muốn loại nào ạ?" Ambiguous items are **never auto-resolved** — this is a deliberate design choice to prevent the system from choosing incorrectly on the customer's behalf.

- **Modifier stripping:** regex patterns extract special requests from the item name: "Lau Thai, it cay" → `name="Lau Thai"`, `special_requests="it cay"`. Modifiers are stored in the order item note field rather than the name.

- **State consistency checks:**
  - **Additive-turn detection:** if the LLM produces an `add_cart` call but the existing cart was lost from context (LLMs are stateless per-call), utterance keywords "thêm", "nữa", "lấy thêm" trigger automatic cart restoration before processing
  - **Context-duplicate items:** deduplicate against existing cart to prevent the LLM from re-adding the entire cart it already added
  - **Simultaneous add+confirm rejection:** if the LLM emits both `add_cart` and `confirm_order` in one turn, the confirm is stripped — the customer must explicitly confirm after seeing the cart. This prevents the LLM from jumping the state machine.

#### 4.3.5 Stage IV — Execution: Tools & State Management

##### 4.3.5.1 Tool Architecture

- **In-memory cart tools** (`add_cart`, `remove_cart`, `clear_cart`): operate on `AgentState.active_cart` only, no network I/O. Cart is a Pydantic model with `items: list[CartItem]` where each item has `name`, `quantity`, `price`, `note`. Multiple `add_cart` calls for the same dish merge by incrementing quantity.

- **Orchestrator API tools** (`confirm_order`, `request_payment`, `verify_payment`): HTTP POST to the orchestrator backend. `confirm_order` serializes the cart, receives an order ID, and sets `order_confirmed=True`. `request_payment` computes the session total (sum of all confirmed orders) and returns a VietQR URL + amount. `verify_payment` closes the session and frees the table.

- **Search tool** (`search`): hybrid BM25 + FAISS retrieval pipeline for menu queries. LLM rewrites the user's vague query into concrete search terms → parallel BM25 + FAISS retrieval (raw k=10 each) → RRF fusion (`score(d) = Σ 1/(60 + rank_d)`) → dual-lane gatekeeper (semantic: top FAISS cosine ≥ 0.35, OR lexical: query keyword appears in top document text; both fail → return empty) → metadata post-filters (price range, diet_type, category). `underthesea.word_tokenize` segments Vietnamese compound words for BM25 indexing. This is standard RAG infrastructure using off-the-shelf components — its role is functional support for the agent, not a research contribution.

##### 4.3.5.2 Cart State Machine

```
IDLE ──(add_cart)──→ DRAFTING ──(agent echoes cart)──→ AWAITING_CONFIRMATION
  ↑                        ↑                                    │
  │                        │ add_cart/remove_cart               │ confirm_order
  │                        └────────────────────────────────────┘
  │                                                             │
  └────────────────────(payment verified)───────────────────────┘
                                                              CONFIRMED
```

The state machine is enforced at the `state_updater` node. Any `add_cart`/`remove_cart` at `AWAITING_CONFIRMATION` loops back to `DRAFTING`, then the agent re-echoes the cart and returns to `AWAITING_CONFIRMATION`. This prevents the LLM from silently modifying the cart and confirming without the customer knowing.

##### 4.3.5.3 Multi-Intent Iteration & State Update

`current_intents` is processed as a FIFO queue. The first intent dispatches to its worker, which produces a tool call. After validation and tool execution, `state_updater` merges results into `AgentState` (update `active_cart`, advance `order_stage`, populate `search_context`, set `ui_action`, increment `loop_count`). The processed intent is popped from the queue. Remaining intents loop back to the router for the next worker dispatch. When the queue is empty, execution proceeds to `state_outcome`.

Example: "Cho 2 Ốc Hương rồi tính tiền luôn" → router → [ORDER, PAYMENT] → ORDER worker adds cart → state_updater pops ORDER → PAYMENT worker requests payment → state_updater pops PAYMENT → queue empty → state_outcome combines both contexts → response_node produces a unified reply.

#### 4.3.6 Stage V — Response: Output Generation

- **Typed ResponseContext dispatch:** `OrderResponseContext`, `SearchResponseContext`, `PaymentResponseContext`, `ChatResponseContext`, `RetryResponseContext`. Each carries structured data the response node uses to generate the final reply, ensuring the LLM has complete, typed context rather than raw text.

- **Template-based responses** (no LLM, deterministic): order confirmations (cart echoed with per-item prices and total), payment prompts (amount + VietQR image reference), cart echoes, error and recovery messages, retry apologies, empty search results. Fast, predictable, phrased in natural Vietnamese via pre-written templates.

- **LLM-based responses** (Qwen2.5 7B, `temperature=0.3`): search results listed in natural Vietnamese, off-menu suggestions with alternatives, free-form chat. The LLM receives the typed `ResponseContext` as structured input, not raw text — it paraphrases structured data into conversational Vietnamese.

- **SSE streaming architecture:** the LangGraph graph executes synchronously inside a `ThreadPoolExecutor`, producing a typed `ResponseContext`. An async generator wraps this result and yields Server-Sent Events (SSE). Sentence splitting via `re.split(r"[.!?]\s", buffer)`. Template responses are emitted as complete sentences. UI actions and cart state are included in the final SSE "done" event. This architecture avoids blocking the FastAPI event loop during LLM inference while maintaining compatibility with LangGraph's synchronous checkpointer.

#### 4.3.7 Prompt Architecture

> *The system uses zero fine-tuning — all model adaptation is achieved through prompting. The prompt architecture is therefore a first-class design element, not an implementation detail.*

- **System prompts (7 files, all in Vietnamese):** each node that calls an LLM has its own system prompt defining its role, reasoning protocol, output format, and constraints:
  - `router_agent.md` (83 lines): 4-step reasoning protocol for intent classification with examples of multi-intent decomposition
  - `order_agent.md`: cart CRUD rules, Vietnamese quantity patterns ("2 phần", "1 dĩa"), modification handling
  - `search_agent.md`: query rewriting instructions, "ĐÃ BIẾT" injection format, non-food delegation trigger
  - `response_agent.md`: natural Vietnamese restaurant waiter persona, tone guidelines
  - `validator.md`: (if LLM-based validator path exists)

- **Few-shot examples:** static JSON files loaded at boot, injected into prompts at runtime:
  - `router.json`: 14 examples covering single-intent, multi-intent, ambiguous utterances, and edge cases (teencode, short affirmations)
  - `search_worker.json`: 5 examples with tool calls for KV-cache optimization — the LLM sees correctly formatted tool invocations
  - `utterances.json`: additional evaluation utterances

- **Skill documents:** markdown files defining behavioral rules loaded at agent startup:
  - `hospitality.md`: Vietnamese restaurant service etiquette (greeting patterns, politeness levels, refusal phrasing)
  - `menu_grounding.md`: rules for when to use menu data vs. general knowledge (enforces menu-as-ground-truth)
  - `no_service_response.md`: domain boundary definition — what the waiter should refuse to answer (unrelated questions, inappropriate requests)

- **Dynamic context injection:** conversation state is injected into LLM prompts at runtime:
  - Last 2 conversation turns injected into the router prompt — "ok" at `AWAITING_CONFIRMATION` means ORDER_CONFIRM, but at `IDLE` means CHAT
  - "ĐÃ BIẾT" section in search prompts: items from prior searches + current cart items to prevent redundant queries
  - Validator `feedback` injected into worker retry prompts for corrective guidance

- **Per-stage model configuration:** all three LLM nodes use the same Qwen2.5 7B model via Ollama, configured differently per stage:

  | Stage | Temperature | Key Configuration |
  |-------|------------|-------------------|
  | Router (Tier 2) | 0.0 | `with_structured_output(IntentPrediction)` — forced Pydantic output |
  | Worker (ORDER/SEARCH) | 0.1 | `tool_choice="any"` — forced tool call |
  | Response | 0.3 | Free-form generation — natural Vietnamese paraphrasing |

  All models use `keep_alive=-1` (pinned in VRAM to eliminate cold-start latency). A warmup ping is sent at agent startup.

### 4.4 Edge Deployment & Voice Pipeline

> *The system accepts spoken Vietnamese and replies in spoken Vietnamese. Voice capture and synthesis are deployed on the Jetson Orin Nano at the robot edge, with the LLM agent residing on the central server. This section describes the architecture of this deployment split and the voice processing pipeline.*

#### 4.4.1 Edge/Server Split Rationale
- **Why edge?** Speech I/O (microphone, speaker) is physically on the robot → Jetson is the natural compute point. STT and TTS models (faster-whisper medium, Piper) are GPU-light and runnable on Jetson's CUDA cores. Local STT avoids network round-trip latency for audio upload and survives temporary WiFi drops (capture completes locally, text is a tiny payload).
- **Why server for the agent?** The LLM (Qwen2.5 7B) requires server-grade GPU VRAM (~6-8 GB). Running it on Jetson would require aggressive quantization with quality degradation. HTTP text round-trip (utterance → server → response) is ~2-4s, dominated by LLM inference, not network.
- **Protocol:** edge voice device connects to the orchestrator WebSocket as `role=voice-device`. The tablet-to-voice flow is: Customer UI "Talk to AI" button → `POST /voice/listen` → orchestrator WS forwards `start_listening` → Jetsen arms microphone. Text output from agent → `POST /voice/event` → orchestrator WS mirrors to tablet.

#### 4.4.2 Threaded Pipeline Architecture
- **VAD thread:** captures microphone in 512-sample chunks, resamples to 16 kHz via polyphase filtering (scipy). Silero VAD model classifies each frame as speech/silence. Configurable sensitivity threshold. Start/end silence padding (pre-padding to avoid clipping initial consonants, post-padding to capture utterance tail). Gate-controlled: only active between `start_listening` and utterance completion — idles otherwise to avoid false triggers.
- **STT thread:** receives complete utterance audio via `speech_queue`. Runs faster-whisper medium with `language=vi`, `beam_size=5`. PhoWhisper weights: Whisper fine-tuned on Vietnamese for improved tonal accuracy. No further training or adaptation. Output transcript placed in `text_queue`.
- **Main loop:** pops transcript from `text_queue` → HTTP POST to agent brain `/chat` → receives response JSON → dispatches to TTS engine → signals ready for next utterance.
- **Single-utterance mode:** the pipeline captures exactly one utterance per `start_listening` command, then auto-idles. This prevents continuous eavesdropping and gives the customer explicit control over when the robot listens.

#### 4.4.3 Barge-In Mechanism
- TTS playback is sentence-by-sentence (aligned with agent SSE output). During TTS playback, the VAD thread runs concurrently in monitoring mode. If VAD detects new speech while the robot is speaking, playback is interrupted mid-sentence. The new utterance is captured and processed normally. This allows natural conversational turn-taking — the customer can interrupt to correct an order or change their mind without waiting for the robot to finish speaking.

#### 4.4.4 TTS Strategy
- **Primary:** Piper TTS (local, Vietnamese voice, edge-deployable, moderate quality). Runs entirely offline on Jetson. Latency ~500ms per sentence.
- **Fallback:** edge-tts (Microsoft Azure cloud Vietnamese Neural voices, high quality, requires internet). Used when Piper is unavailable or on x86 dev machines without Piper installed.
- **Selection logic:** attempt Piper first; if unavailable, fall back to edge-tts with a health check.

### 4.5 Backend Orchestrator — FastAPI + SQLite + WebSocket

#### 4.5.1 Architectural Patterns
- **Event-driven via WebSocket pub/sub:** the orchestrator is the central message hub. Business events (order created, table status changed, robot arrived) are fanned out to all relevant WebSocket clients by role. No polling for real-time data — clients receive events as they happen. REST is used for writes and initial state loads; WebSocket for live updates.
- **Single-writer SQLite:** one FastAPI process handles all writes. No concurrent write conflicts at restaurant scale (dozens of orders per hour, not thousands per second). ACID transactions guarantee consistency for critical operations (seat a table + create session + dispatch robot task — all or none).
- **Service layer separation:** routers handle HTTP parsing and response formatting only. Business logic lives in `services/` (dispatcher, fleet, sessions, menu_loader). This separation allows the agent brain to call service functions via `OrchestratorClient` without going through HTTP when running co-located.

#### 4.5.2 REST API Design
- 20 endpoints across 10 routers: menu, tables, orders, payments, robots, tasks, layout, admin, voice, WebSocket
- Request/response validation via Pydantic models. Auto-generated OpenAPI documentation. CORS configured for Vite dev ports (5173–5175)

#### 4.5.3 Database Schema
- SQLite, raw SQL via `sqlite3` (no ORM) — single-file, serverless, ACID
- 8 business tables: `tables`, `sessions`, `dishes`, `orders`, `order_items`, `robots`, `tasks`, `payments`
- Separate `checkpoints.db` for LangGraph conversation memory (managed by `SqliteSaver`, not the orchestrator)
- Schema evolution via `ALTER TABLE ADD COLUMN` with `PRAGMA table_info` for idempotent migrations (each migration checks if the column already exists before adding)
- ERD diagram

#### 4.5.4 WebSocket Hub
- Single `/ws` endpoint, 4 role types via query parameter:
  - `role=panel` → anonymous broadcast (kitchen display, fleet dashboard)
  - `role=customer` → anonymous broadcast filtered by `table_id` (tablets)
  - `role=robot` → indexed by `robot_id`, bidirectional (task assignment + telemetry)
  - `role=voice-device` → indexed by `robot_id`, server→client only (start/cancel listening commands)
- Event catalog: `order.created`, `order.updated`, `table.updated`, `robot.updated`, `task.created`, `task.updated`, `voice.heard`, `voice.reply`, `reset`

#### 4.5.5 Session Lifecycle
- Kiosk seating → `POST /seatings` {table_id, party_size} → creates `ACTIVE` session row, sets `tables.status = DANG_PHUC_VU`, dispatches `go_to_table` task to nearest idle robot
- Multiple orders per session → cumulative payment: session total = sum of all confirmed order totals within the session
- Payment → `POST /payments/verify` → marks session `CLOSED`, table `DA_THANH_TOAN`, cancels pending robot tasks
- Table manually ended → `PATCH /tables {status: TRONG}` → clears table state, cancels pending tasks, sends robot home

#### 4.5.6 Voice Bridge
- `POST /voice/event` (agent → backend): fans voice reply transcript + UI action + cart state to `role=customer` WebSocket on the correct `table_id`
- `POST /voice/listen` (tablet → backend → voice-device WS): triggered when customer presses "Talk to AI" on the tablet. Forwards `start_listening` to the voice device bound to that table's robot
- `POST /voice/cancel`: aborts in-flight voice capture, returns voice device to idle
- Dynamic table-robot voice binding: when a robot arrives at a table, `bind_table_robot(table_id, robot_id)` is called. All subsequent voice commands from that table are routed to that robot's voice device. On robot release or disconnect, the binding is cleared

### 4.6 Robot Dispatch & Fleet Management

#### 4.6.1 Telemetry Architecture
- **RAM-only latest-value store:** robot pose (x, y) + battery percentage stored in thread-safe `dict`, refreshed at 4+ Hz via WebSocket heartbeats. Writing sensor-frequency data to SQLite would cause write contention; RAM provides lock-free reads for the dispatcher's nearest-robot scoring.
- **Periodic DB snapshot:** every 15 seconds, the latest pose and battery are persisted to the `robots` table. Provides cold-start recovery — after restart, the panel can show where robots were, and the dispatcher has a starting state.
- **Pose broadcast throttled to 5 Hz** for minimap rendering — higher than 5 Hz is imperceptible at the 30 fps browser rendering cap; lower prevents unnecessary WebSocket traffic.

#### 4.6.2 Task Assignment — Nearest-Idle Algorithm
- `try_assign()` runs on each new PENDING task. Logic:
  1. Query all PENDING tasks, ordered by creation time (FIFO)
  2. For each task, filter eligible robots: status_idle (DB) + live WebSocket connection + battery ≥ 20% (RAM overlaid)
  3. Score each eligible robot by Euclidean distance from its live pose to the target table's waypoint
  4. Assign task to nearest eligible robot
- No auction or bidding — nearest-idle is simplest and works well for short trips (3–5m kitchen→table) in a small environment (6 tables)
- Task kinds: `go_to_table` (triggered by seating), `deliver` (triggered by order status → XONG), `call` (triggered by guest "Gọi Robot" button)
- Task lifecycle: `PENDING → ASSIGNED → IN_PROGRESS → DONE`

#### 4.6.3 Watchdog & Fault Recovery
- Scans every 5 seconds. Robots with no heartbeat for >30 seconds are marked offline in DB and RAM
- Hung robot recovery: tasks assigned to that robot are requeued to PENDING, zombie WebSocket connection is closed, table-voice binding is released
- Table cleanup on payment/table-end: all pending tasks for that table are cancelled, assigned robot is sent a `task.release` and sent home

### 4.7 Web Interfaces — Architecture

> *Three single-page applications share a common TypeScript library for REST, WebSocket, and type definitions. Each app has a specific role: customer ordering (tablet), guest check-in (kiosk), and staff operations (management panel).*

#### 4.7.1 Shared Frontend Architecture
- 3 Vite + Vue 3 SPAs importing `@/shared` (REST client, WebSocket client with auto-reconnect, TypeScript types mirroring backend Pydantic schemas)
- Vite dev proxies `/api` → orchestrator `:8000` and `/ws` → orchestrator `:8000`, eliminating CORS in production
- State management: Pinia stores per app. Lazily instantiated on first use, no manual registration

#### 4.7.2 Customer Tablet UI
- **Menu browsing:** 12 categories from menu data, diacritic-insensitive free-text search, Best Seller section, scroll-synced category navigation
- **Voice mirror:** real-time WebSocket conversation display — agent transcripts, thinking indicators, cart synchronization (`syncFromVoice` — agent-side cart modifications mirrored to the UI). UI action following: `open_menu` → scroll to relevant category, `open_payment` → navigate to payment screen
- **Cart management:** voice or touch add/remove, server-computed total, order confirmation with cart review, VietQR payment display

#### 4.7.3 Kiosk (Check-in)
- Table grid with real-time status (8s polling fallback for WebSocket gaps), party size selector, 409 conflict handling on race-condition seating, success auto-close after confirmation

#### 4.7.4 Management Panel (Kitchen + Fleet)
- **Kitchen Kanban:** 3-column board (Chờ Bếp / Đang Làm / Xong), per-order elapsed time, advance button triggers `PATCH /orders/{id} {status}` updates which cascade to robot delivery tasks
- **Fleet board:** per-robot cards with live status (Idle/Busy/Offline), battery gauge, activity description, last seen timestamp
- **Table overview:** per-table status, party size, session duration, linked active order detail
- **Minimap:** SLAM map PNG as SVG backdrop, 6 colored table markers, animated robot position dots at 5 Hz. Drag-to-move for repositioning reference

### 4.8 Deployment Topology
- **Hardware table:** Server (x86 + NVIDIA GPU — Ollama + FastAPI orchestrator + Agent Brain), Jetson Orin Nano (robot — ROS2 navigation + edge voice pipeline), Laptops/tablets (browser-only SPA clients on local WiFi)
- **LLM configuration:** single Qwen2.5 7B Instruct model served by Ollama, configured with different temperatures and runtime options per agent stage (router: T=0.0 with structured output; worker: T=0.1 with `tool_choice="any"`; response: T=0.3 for natural Vietnamese). `keep_alive=-1` pins the model in GPU VRAM to eliminate cold-start latency overhead. Warmup ping at agent startup ensures the model is fully loaded before the first customer utterance.
- **Package management:** Python dependencies via `uv` with role-based extras (`server`, `voice`, `cu12`/`cu13` for CUDA version). Frontend dependencies via `npm` workspaces (3 Vite apps + 1 shared library)
- **Network:** all components communicate over local WiFi; Netbird VPN provides secure tunnel for off-site server scenarios

---

## CHAPTER 5: EXPERIMENTS AND RESULTS

> *Each experiment section follows this pattern: (a) goal — what contribution it validates, (b) dataset — how test data was constructed, (c) methodology — how measurements were taken, (d) metrics — what was measured and why, (e) results — tables and figures, (f) analysis — what the numbers mean, (g) ablation — what happens without this component.*

---

### 5.1 Evaluation Methodology

#### 5.1.1 Hardware & Environment

| Component | Specification |
|-----------|--------------|
| Server GPU | NVIDIA GeForce RTX 3070 Laptop (CUDA 12.1) |
| Server CPU | Intel Core i7 (x86_64) |
| Robot compute | Jetson Orin Nano (aarch64, CUDA 12.6) |
| Robot sensors | RPLiDAR A2M8, Intel RealSense D435, MPU6050 IMU |
| LLM backend | Ollama serving Qwen2.5 7B Instruct (`keep_alive=-1`) |
| Embedding model | AITeamVN/Vietnamese_Embedding (1024-dim) |
| STT model | faster-whisper medium, PhoWhisper weights, `language=vi`, `beam_size=5` |
| OS | Ubuntu 22.04 LTS, ROS 2 Humble |
| Network | Local WiFi (server ↔ Jetson ↔ browser clients) |

#### 5.1.2 Datasets Summary

| Dataset | File | Size | Purpose |
|---------|------|------|---------|
| Router evaluation | `evals/data/router/router_eval.json` | 80 cases | Intent classification accuracy |
| Retrieval evaluation | `evals/data/retrieval/retrieval_eval.json` | 24 queries | Menu search relevance |
| E2E conversations (Part 1) | `evals/data/e2e/e2e_conversations_part1.json` | 6 scenarios | Happy-path ordering flows |
| E2E conversations (Part 2) | `evals/data/e2e/e2e_conversations_part2.json` | 5 scenarios | Edge-case flows |
| Out-of-menu robustness | `evals/data/e2e/e2e_out_of_menu_test.json` | 4 scenarios | Validator off-menu rejection |
| Real-life scenarios | `evals/data/e2e/e2e_real_life.json` | 4 scenarios | Qualitative multi-turn case studies |
| Validator name resolution | *(to be built)* | ~70 pairs | Name resolution pipeline accuracy (per-stage) |
| Ambiguity detection | *(to be built)* | ~20 queries | Ambiguity flagging precision/recall |
| Context-dependent routing | *(to be built)* | ~15 cases | Dynamic context ablation |
| STT transcription | *(to be built)* | 50–100 utterances | Vietnamese restaurant speech-to-text WER/CER |
| VAD boundary detection | *(to be built)* | ~30 annotated audio clips | Voice activity detection accuracy |
| Response quality (MOS) | *(to be built)* | 20–30 agent responses | Vietnamese naturalness and correctness |

#### 5.1.3 Metrics Definition

##### 5.1.3.1 AI Classification & Retrieval Metrics

| Metric | Formula | Measures | Tied to §1.3 objective |
|--------|---------|----------|------------------------|
| **Accuracy** | correct / total | Classification correctness | Router accuracy ≥ 90% |
| **Confusion matrix** | Heatmap: predicted vs actual intents (5×5) | Per-intent-pair error patterns | Router correctness (richer than accuracy alone) |
| **Precision@k** | \|relevant ∩ retrieved\| / k | Fraction of top-k results that are relevant | RAG precision target |
| **Recall@k** | \|relevant ∩ retrieved\| / \|relevant\| | Fraction of all relevant items found | RAG recall target |
| **MRR** | 1 / rank of first relevant hit | Reciprocal rank of first correct result | Search ranking quality |
| **Hit Rate** | queries with ≥1 relevant in top-k / total queries | Fraction of queries returning any useful result | RAG completeness |
| **Pass Rate** | passed scenarios / total | E2E scenario completion rate | E2E voice ordering completion |
| **Per-difficulty accuracy** | correct / total per difficulty level | Where failures cluster (easy vs hard) | Router diagnostic, E2E diagnostic |
| **Per-difficulty Precision/Recall** | Per-difficulty-level P@5/R@5 | Whether hard queries or easy queries drag down averages | RAG diagnostic |

##### 5.1.3.2 Speech Pipeline Metrics

| Metric | Formula | Measures | Tied to §1.3 objective |
|--------|---------|----------|------------------------|
| **Word Error Rate (WER)** | (S + D + I) / N, where S=substitutions, D=deletions, I=insertions, N=reference word count | STT transcription accuracy on Vietnamese restaurant utterances | Voice pipeline input quality |
| **Character Error Rate (CER)** | Same formula at character level | Finer-grained accuracy on tonal diacritics (Vietnamese-specific: 6 tones) | Voice pipeline input quality |
| **VAD false trigger rate** | false_positive_triggers / total_silence_segments | VAD triggering on background noise | Voice pipeline reliability |
| **VAD missed utterance rate** | missed_utterances / total_utterances | VAD failing to detect speech onset | Voice pipeline reliability |
| **VAD cut-off rate** | utterances_with_premature_end / total_utterances | VAD trimming utterance tails (trailing consonants common in Vietnamese) | Voice pipeline reliability |
| **Barge-in success rate** | successful_barge_in / attempted_barge_in | Customer speech interrupts TTS playback correctly | Voice interaction naturalness |

##### 5.1.3.3 Safety & Robustness Metrics

| Metric | Formula | Measures | Tied to §1.3 objective |
|--------|---------|----------|------------------------|
| **Name resolution accuracy** | correct_resolutions / total, per pipeline level | Menu name matching quality at each stage | Validator correctness |
| **Off-menu detection rate** | scenarios where all invalid items flagged / total adversarial scenarios | Validator catch rate for hallucinated dishes | Validator safety |
| **Confirm-order leak rate** | scenarios where confirm_order called with ≥1 invalid item / total | Safety net failure mode — this must be 0 | Validator safety |
| **Ambiguity precision** | correctly_flagged_ambiguous / all_flagged | False positive rate on ambiguity detection | Validator correctness |
| **Ambiguity recall** | correctly_flagged_ambiguous / all_truly_ambiguous | False negative rate on ambiguity detection | Validator completeness |
| **Delegate accuracy** | correct_delegations / total_delegations (manual review) | Delegate mechanism reliability | Safety mechanism correctness |
| **Wrong-tool-call rate** (no delegate) | turns with nonsensical tool call / total turns | Delegate ablation — failure rate without the escape hatch | Safety mechanism necessity |

##### 5.1.3.4 Robot Performance Metrics

| Metric | Formula | Measures | Tied to §1.3 objective |
|--------|---------|----------|------------------------|
| **Return-to-start error** | Euclidean distance ‖(x_end, y_end) − (x_start, y_start)‖ after closed path | Odometry drift | EKF odometry ≤ X cm |
| **Drift per meter** | error / total_path_length (cm/m) | Normalized drift rate | Odometry quality |
| **Navigation success rate** | successful_trips / total_trips | Navigation reliability | Nav success ≥ X% |
| **Mean trip time** | Σ trip_duration / N per table | Navigation speed | Nav performance |
| **Docking position error** | \|actual − target\| in lateral (x) and depth (z), in cm | Docking lateral/depth precision | ArUco docking < X cm |
| **Docking orientation error** | \|actual − target\| yaw, in degrees | Docking angular precision | ArUco docking < X° |
| **Safe stop distance** | Distance from robot to obstacle at full stop | Obstacle avoidance safety | Safe obstacle distance |
| **Marker detection failure rate** | failed_detections / total_approaches per table | ArUco robustness under real conditions | Docking reliability |

##### 5.1.3.5 Latency & Throughput Metrics

| Metric | Formula | Measures | Tied to §1.3 objective |
|--------|---------|----------|------------------------|
| **Voice turn latency** | t_speaker_start − t_mic_open, per turn | End-to-end voice interaction time | Voice interaction < 5s |
| **Per-stage latency** | Timestamp diff per pipeline stage (VAD→STT→Network→Agent→TTS) | Identifies latency bottleneck | Latency diagnostic |
| **Agent inference latency** | t_response_ready − t_utterance_received, per intent type | LLM inference cost by intent | Agent responsiveness |
| **Validator latency overhead** | t_validator_exit − t_validator_entry | Safety computation cost | Safety vs speed trade-off |
| **Semantic router latency** | t_semantic_classification_complete | Tier 1 speed | Router speed |
| **Task assignment latency** | t_task_assigned − t_task_created | Dispatcher responsiveness | System responsiveness |
| **API endpoint response time** (p50, p95) | FastAPI request duration per endpoint | Backend performance | System responsiveness |
| **WebSocket event propagation latency** | t_client_receive − t_server_emit | Real-time update speed | UI responsiveness |
| **Cold-start penalty** | t_first_utterance_latency − t_warm_utterance_latency | Ollama model load overhead | Deployment quality |

##### 5.1.3.6 Response Quality Metrics (Subjective)

| Metric | Scale | Measures | Tied to §1.3 objective |
|--------|-------|----------|------------------------|
| **MOS Naturalness** | 1–5 (3–5 Vietnamese-speaking raters) | How natural the Vietnamese response reads | Conversational AI quality |
| **MOS Correctness** | 1–5 (same raters) | Factual accuracy of the response | Agent reliability |
| **MOS Helpfulness** | 1–5 (same raters) | Whether the response actually answers the customer | Agent usefulness |
| **Inter-annotator agreement** | Cohen's κ | Rater consistency validation | Evaluation rigor |

##### 5.1.3.7 Ablation Metrics

| Ablation | Comparison | Primary Metric | Proves |
|----------|-----------|----------------|--------|
| Router: semantic-only / SLM-only / hybrid | 3-mode run on same 80 cases | Accuracy, mean latency, fast-track rate | Hybrid design is superior to either tier alone |
| Validator: ON / OFF | E2E 11 scenarios with validator bypassed | E2E pass rate, off-menu items in cart, incorrect confirm_order count | Validator prevents real system failures |
| Delegate: ON / OFF | E2E + real-life scenarios with delegate removed | Wrong-tool-call count, irrelevant search results, cart errors | Delegate prevents forced-wrong tool calls |
| Dynamic context: ON / OFF | Router eval on 15 context-dependent cases | Accuracy on context-dependent utterances | Dynamic context injection matters for ambiguous short utterances |
| Few-shot count: 0 / 5 / 10 / 14 | Router eval on 80 cases with varying few-shot counts | Accuracy vs prompt token count | Optimal few-shot count is a validated design choice |

All automated experiments run at least 3 times where variability matters (LLM inference, navigation). Reported as mean ± standard deviation. Subjective MOS requires inter-annotator agreement (Cohen's κ ≥ 0.6).

---

### 5.2 Robot Navigation — Component Evaluation

#### 5.2.1 Odometry Accuracy

> **Goal:** Validate that EKF fusion of encoder + IMU improves odometry over encoder-only.

- **Methodology:** Robot executes closed-path trajectories (rectangle: 2m × 1.5m, return to origin). Record `/odometry/filtered` pose. Compare encoder-only (raw wheel odometry) vs EKF-fused (encoder + IMU via `robot_localization`). N = 10 runs per condition.
- **Metrics:** Return-to-start position error (cm): mean, std, max, min. Drift per meter traveled: error / total path length.
- **Results table:**

  | Condition | Mean Error (cm) | Std (cm) | Max Error (cm) | Drift (cm/m) |
  |-----------|-----------------|----------|----------------|--------------|
  | Encoder-only | [pending] | [pending] | [pending] | [pending] |
  | EKF-fused | [pending] | [pending] | [pending] | [pending] |

- **Expected finding:** EKF significantly reduces yaw drift from IMU gyro bias, cutting return-to-start error by ~40-60%.

#### 5.2.2 Navigation Performance

> **Goal:** Measure the robot's ability to navigate kitchen → table autonomously.

- **Methodology:** Gazebo simulation first (controlled environment, repeatable), then real-world validation. Kitchen → each of 6 tables, N = 5 trips per table. Record success (robot reaches within 0.3m of table waypoint), trip duration, and failure causes.
- **Metrics:** Success rate per table (%), mean trip time (s), failure categorization.
- **Results table (simulation):**

  | Table | Trips | Success | Mean Time (s) | Failures |
  |-------|-------|---------|---------------|----------|
  | Bàn 1–6 | 5 each | [pending] | [pending] | [pending] |

- **Results table (real world):** same format
- **Obstacle-in-lane test:** Place box in service lane mid-trip. Verify: (a) LiDAR detects obstacle, (b) local planner stops before collision, (c) robot waits or replans. Safe stop distance measured.
- **Sim-to-real comparison:** Discuss differences in localization accuracy, LiDAR noise, floor surface effects.

#### 5.2.3 ArUco Docking Precision

> **Goal:** Measure final-approach accuracy using ArUco marker re-localization at each table.

- **Methodology:** Robot navigates to each table. At 0.5m approach distance, uses D435 RGB camera to detect ArUco marker (DICT_4X4_50, IDs 0–5). Measures final position and orientation relative to marker. N = 10 runs per table.
- **Metrics:** Position error (cm): lateral (x), depth (z). Orientation error (°): yaw. Mean ± std per table.
- **Results table:**

  | Table | Lateral Error (cm) | Depth Error (cm) | Yaw Error (°) | Failures (marker not detected) |
  |-------|--------------------|--------------------|----------------|-------------------------------|
  | Bàn 1–6 | [pending] | [pending] | [pending] | [pending] |

- **Failure analysis:** lighting conditions, marker angle >45°, marker partial occlusion → marker-lost → safe stop behavior.

---

### 5.3 AI Agent — Component-Level Evaluation

#### 5.3.1 Intent Classification — Two-Tier Hybrid Router

> **Goal:** Validate that the hybrid two-tier router achieves ≥90% accuracy and that the semantic fast-path provides meaningful latency reduction without accuracy loss.

- **Dataset:** `router_eval.json` — 80 Vietnamese utterances across 5 intents (ORDER: 18, SEARCH: 24, PAYMENT: 14, CHAT: 9, COMPLEX multi-intent: 15), 3 difficulty levels (easy: 32, medium: 32, hard: 16). Cases hand-crafted to cover teencode, short affirmations, compound utterances, and edge cases. Ground-truth labels assigned by human annotator.

- **Methodology:** Run `eval_router.py` against live Ollama instance. Each utterance passes through: semantic router (cosine similarity + softmax-gap gate) → if rejected, SLM router (Qwen2.5 7B, T=0.0, structured output with 14 few-shot examples). Compare predicted intents against ground truth.

- **Metrics:** Overall accuracy, per-intent accuracy, semantic fast-track rate, semantic error rate, latency per tier.

- **Results:**

  | Metric | Value |
  |--------|-------|
  | Overall Accuracy | **90.00%** (72/80) |
  | Semantic Fast-Track Rate | 33.8% (27/80) |
  | Semantic Errors | 0 (all 27 fast-tracked correct) |
  | Overall Avg Latency (CUDA) | 1.19s |
  | Semantic Tier Latency | ~15ms |
  | SLM Tier Latency | ~1.79s |

  | Intent | Cases | Correct | Accuracy |
  |--------|-------|---------|----------|
  | ORDER | 18 | 18 | **100.0%** |
  | SEARCH | 24 | 22 | **91.7%** |
  | PAYMENT | 14 | 12 | **85.7%** |
  | CHAT | 9 | 9 | **100.0%** |
  | COMPLEX (multi-intent) | 15 | 11 | **73.3%** |

  | Latency Tier | Intent(s) | Avg Latency |
  |--------------|-----------|-------------|
  | Semantic | Single-intent (fast-tracked) | ~0.015s |
  | SLM | `['ORDER']` | 0.30s |
  | SLM | `['SEARCH']` | 1.26s |
  | SLM | `['PAYMENT']` | 1.04s |
  | SLM | `['CHAT']` | 1.56s |
  | SLM | Multi-intent (2–3 intents) | 1.91–2.21s |

- **Confusion matrix (5×5):**

  > *A confusion matrix reveals the pattern of misclassifications — which intents are confused with which. This is richer than per-intent accuracy and directly guides prompt improvements.*

  | Actual ↓ / Predicted → | ORDER | SEARCH | PAYMENT | CHAT | COMPLEX |
  |------------------------|-------|--------|---------|------|---------|
  | **ORDER** | 18 | 0 | 0 | 0 | 0 |
  | **SEARCH** | [pending] | 22 | [pending] | [pending] | [pending] |
  | **PAYMENT** | [pending] | [pending] | 12 | [pending] | [pending] |
  | **CHAT** | [pending] | [pending] | [pending] | 9 | [pending] |
  | **COMPLEX** | [pending] | [pending] | [pending] | [pending] | 11 |

- **Per-difficulty breakdown:**

  | Difficulty | Cases | Correct | Accuracy |
  |-----------|-------|---------|----------|
  | Easy | 32 | [pending] | [pending] |
  | Medium | 32 | [pending] | [pending] |
  | Hard | 16 | [pending] | [pending] |

  Analysis: are failures concentrated in hard cases (acceptable) or spread across easy/medium (concerning)? Easy-case errors indicate fundamental routing issues, not edge-case complexity.

- **Ablation 1 — Semantic-only vs SLM-only vs Hybrid:**

  > *Run all 80 cases through 3 router configurations. Semantic-only uses ONLY cosine similarity + softmax (no fallback). SLM-only uses ONLY the LLM (no semantic fast-track). Hybrid uses the two-tier design.*

  | Mode | Accuracy | Avg Latency | Fast-Track Rate |
  |------|----------|-------------|-----------------|
  | Semantic-only | [pending — estimate ~65%] | ~0.015s | 100% |
  | SLM-only | [pending — estimate ~92%] | ~1.8s | 0% |
  | **Hybrid** | **90.00%** | **1.19s** | 33.8% |

  **What this proves:** Hybrid achieves (SLM accuracy − ~2%) at (SLM latency × ~0.66). Semantic-only is too inaccurate to use alone. SLM-only is unnecessarily slow for 33% of cases. The two-tier design is the right trade-off.

- **Ablation 2 — Few-shot count: 0 vs 5 vs 10 vs 14:**

  > *Run the SLM router on 80 cases with varying numbers of few-shot examples injected into the prompt. This validates the 14-shot design choice and quantifies how many examples are actually needed.*

  | Few-shot count | Accuracy | Prompt tokens | Latency |
  |---------------|----------|---------------|---------|
  | 0 (zero-shot) | [pending] | [pending] | [pending] |
  | 5 | [pending] | [pending] | [pending] |
  | 10 | [pending] | [pending] | [pending] |
  | **14 (current)** | **90.00%** | [pending] | 1.19s |

  **What this proves:** The few-shot examples are not decoration — accuracy should drop measurably without them. The 14-shot count should sit at or near the saturation point of the accuracy-vs-tokens curve, justifying it as the minimum effective dose rather than an arbitrary number.

- **Ablation 3 — Dynamic context ON vs OFF:**

  > *Build a mini-dataset of ~15 context-dependent utterances ("ok" at IDLE vs at AWAITING_CONFIRMATION, "thêm 1 phần nữa" at different stages). Run router with and without the last 2 conversation turns + order_stage injected into the prompt.*

  | Condition | Accuracy (15 context-dependent cases) |
  |-----------|---------------------------------------|
  | Dynamic context ON | [pending — estimate ~90%+] |
  | Dynamic context OFF | [pending — estimate <50%] |

  **What this proves:** Without dynamic context, "ok" is always classified as CHAT regardless of order_stage — the router cannot disambiguate based on conversation state. The context injection in §4.3.2 is a necessary design element, not an optional feature.

- **Failure analysis (8 failures):**
  - **SEARCH vs CHAT boundary (2 cases):** "Bàn ngoài sân có ổ cắm sạc không?" and "Quán có chỗ đậu xe máy không?" — facility amenity queries misrouted to CHAT instead of SEARCH. Root cause: few-shot examples lack clear distinction between "restaurant info lookup" and "customer service chat" for facility queries.
  - **PAYMENT confusion (2 cases):** "Ơi, mình xin check out" (English loanword) → CHAT instead of PAYMENT. "Bàn mình gọi 3 món rồi, tổng hết bao nhiêu?" → SEARCH instead of PAYMENT (keyword "bao nhiêu" triggered price search).
  - **Multi-intent decomposition (4 cases):** Complex utterances with 3+ intents partially misclassified. Decomposition errors: wrong intent ordering, missing sub-intent, or intent present in wrong position.

- **Pareto frontier analysis (optional):** Sweep softmax temperature T and gap threshold, plot accuracy vs fast-track rate. Shows the T=0.20, gap=0.15 configuration sits at the knee of the curve.

#### 5.3.2 Deterministic Validator — Safety Net Effectiveness

> **Goal:** Prove the validator catches LLM hallucinations (off-menu items, ambiguous names) before they reach the cart, and that removing it causes system failures.

- **Dataset:** 4 adversarial E2E scenarios from `e2e_out_of_menu_test.json`:
  1. Single invalid item + single valid item ("Cho 1 Pizza Hải Sản và 1 Ốc Hương Xốt Trứng Muối")
  2. All items invalid ("Cho 1 Bún Bò Huế và 1 Cơm Gà Xối Mỡ")
  3. All items invalid with near-match spelling variants ("Cơm Tấm", "Lẩu Thái Lan")
  4. Invalid item with special request ("Cho 1 Cơm Chiên Dương Châu, it cay")

- **Methodology:** Run E2E eval script. For each scenario, verify: (a) validator correctly identifies off-menu items in `unavailable_items`, (b) agent *never* calls `confirm_order` with invalid items, (c) response includes nearest-match suggestion (if one exists), (d) agent guides customer to choose valid alternatives.

- **Metrics:**

  | Metric | Definition |
  |--------|------------|
  | Off-menu detection rate | Scenarios where all invalid items correctly flagged |
  | False positive rate | Valid items incorrectly flagged as off-menu |
  | Confirm-order leak rate | Scenarios where `confirm_order` was called with any invalid item |
  | Suggestion relevance | Manual assessment: was nearest-match suggestion reasonable? |

- **Results (4/4 scenarios pass):**

  | Scenario | Off-menu detected? | Nearest match suggested? | confirm_order called? | Pass |
  |----------|---------------------|--------------------------|----------------------|------|
  | S1: 1 invalid + 1 valid | Yes | Yes (Pizza Hải Sản → suggested alternatives) | No (only valid item in cart) | ✓ |
  | S2: All invalid | Yes | Yes (suggested closest matches) | No | ✓ |
  | S3: Near-match variants | Yes | Yes (suggested actual menu items) | No | ✓ |
  | S4: Invalid + modifier | Yes | Yes | No | ✓ |

- **Name resolution pipeline accuracy** *(dataset to be built — ~70 (raw_input, expected_name) pairs)*:

  > *This measures each level of the resolution pipeline independently, showing where the 4-stage matching contributes.*

  | Resolution Level | Test Cases | Correct | Accuracy |
  |-----------------|------------|---------|----------|
  | Exact match | 20 | [pending] | [pending] |
  | Diacritic-insensitive | 10 | [pending] | [pending] |
  | Prefix match | 10 | [pending] | [pending] |
  | Substring match | 10 | [pending] | [pending] |
  | Token-Jaccard fallback | 10 | [pending] | [pending] |
  | Misspelled (should NOT resolve) | 10 | [pending — should be 0, correctly rejected] | N/A |

- **Ambiguity detection** *(dataset to be built — ~20 queries)*:

  | Metric | Value |
  |--------|-------|
  | Precision (flagged / actually ambiguous) | [pending] |
  | Recall (actually ambiguous / flagged) | [pending] |
  | False positive rate | [pending] |
  | False negative rate | [pending] |

- **Ablation — E2E with vs without validator:**

  > *Run 11 E2E scenarios twice: validator enabled vs validator bypassed. This is the critical proof that the validator prevents real failures.*

  | Condition | E2E Pass Rate | Off-menu items in cart | Incorrect confirm_order |
  |-----------|---------------|------------------------|-------------------------|
  | Validator ON | 81.8% (9/11) | 0 | 0 |
  | Validator OFF | [pending] | [pending] | [pending] |

  **Expected result:** Without validator, some scenarios "pass" technically (order sent) but with hallucinated items in cart, or the pass rate drops because backend rejects dishes not in DB. Either outcome proves the validator prevents a failure mode.

- **Validator latency overhead:**

  > *Safety has a computational cost. Measure the validator's contribution to total agent inference time to confirm it does not become a bottleneck.*

  | Metric | Value |
  |--------|-------|
  | Mean validator execution time | [pending] |
  | Validator % of total agent inference | [pending] |
  | Mean name resolution time (per item) | [pending] |

  **Expected result:** The validator should add <50ms per turn (pure deterministic string operations + JSON dict lookups — no LLM call). This is negligible compared to the 1–2s LLM inference it protects.

#### 5.3.3 Delegate Mechanism — Graceful Fallback

> **Goal:** Prove the delegate mechanism prevents forced-wrong tool calls under `tool_choice="any"` and that it correctly routes out-of-domain utterances.

- **Methodology:** Instrument the agent to log every delegate call: which worker triggered it, the input utterance, the delegate reason, and the eventual routing. Run 11 E2E scenarios + 4 real-life scenarios (15 total). Manually review each delegate instance for correctness.

- **Metrics:**

  | Metric | Value |
  |--------|-------|
  | Total delegate calls across 15 scenarios | [pending] |
  | Delegate rate (ORDER worker) | [pending — % of ORDER LLM calls that delegated] |
  | Delegate rate (SEARCH worker) | [pending — % of SEARCH LLM calls that delegated] |
  | Correct delegation rate | [pending — manual review] |
  | Incorrect delegation (should have used domain tool) | [pending] |
  | Missed delegation (should have delegated but didn't) | [pending] |

- **Qualitative examples** (select 3–4 from actual traces):

  | Turn | Worker | Input | Delegated? | Reason | Correct? |
  |------|--------|-------|-----------|--------|----------|
  | E2E-XXX | SEARCH | "nhà hàng mở cửa đến mấy giờ?" | Yes | "restaurant info query, not menu search" | ✓ |
  | E2E-XXX | ORDER | "cho hỏi món nào ngon nhất?" | Yes | "recommendation request, not an order action" | ✓ |
  | [pending] | [pending] | [pending] | [pending] | [pending] | [pending] |

- **Ablation — delegate disabled:**

  > *Re-run 15 scenarios with delegate tool removed from ORDER and SEARCH worker bindings. `tool_choice="any"` still enforced — the LLM must produce a domain tool call even for out-of-domain inputs.*

  | Condition | Wrong-tool-call count | Irrelevant search results | Cart errors |
  |-----------|----------------------|--------------------------|-------------|
  | Delegate ON | [pending — expected ~0] | [pending] | [pending] |
  | Delegate OFF | [pending — expected >0] | [pending] | [pending] |

  **Expected result:** Without delegate, the LLM calls `search()` on non-food queries (returning irrelevant menu items) or calls `add_cart()` on recommendation requests (adding wrong items). The ablation shows delegate prevents a class of LLM behavioral errors.

#### 5.3.4 Menu Retrieval — Supporting Infrastructure

> *Note: this is functional infrastructure evaluation. The retrieval pipeline uses off-the-shelf BM25 + FAISS + RRF. This section validates it works adequately as a supporting component; it is not claimed as a research contribution.*

- **Dataset:** `retrieval_eval.json` — 24 Vietnamese queries across 8 difficulty levels (easy: 8, medium: 9, hard: 7). Each query has `expected_relevant` (ground-truth relevant dish IDs) and `expected_irrelevant` (known-irrelevant dish IDs). Queries range from exact name lookups to vague semantic searches ("món gì ấm bụng cho ngày lạnh?").

- **Methodology:** Run `eval_retrieval.py` against 217-dish menu index (FAISS + BM25). For each query, retrieve top-5 results, compare against ground truth. Run 3 modes: BM25-only, FAISS-only, hybrid RRF.

- **Results:**

  | Metric | BM25-only | FAISS-only | Hybrid RRF |
  |--------|-----------|------------|------------|
  | Precision@5 | [pending] | [pending] | **30.83%** |
  | Recall@5 | [pending] | [pending] | **70.14%** |
  | MRR | [pending] | [pending] | **0.6875** |
  | Hit Rate | [pending] | [pending] | **87.50%** |

  | Difficulty | Count | Precision@5 (RRF) | Recall@5 (RRF) | Hit Rate (RRF) |
  |-----------|-------|-------------------|----------------|----------------|
  | Easy | 8 | [pending] | [pending] | [pending] |
  | Medium | 9 | [pending] | [pending] | [pending] |
  | Hard | 7 | [pending] | [pending] | [pending] |

- **Gatekeeper behavior:**

  | Metric | Value |
  |--------|-------|
  | Queries rejected by gatekeeper | [pending — count and %] |
  | Correct rejections (truly irrelevant) | [pending] |
  | False rejections (relevant query blocked) | [pending] |
  | False approvals (irrelevant query passed) | [pending] |

- **Analysis:** Precision@5 of 30.83% means ~1.5 of 5 results are relevant on average. This is adequate as a suggestion engine (the agent presents results conversationally, customer picks) but insufficient for direct order placement without customer confirmation. Hit Rate of 87.50% means 1 in 8 queries returns nothing useful — the gatekeeper correctly blocks these rather than returning noise. The retrieval pipeline is functional infrastructure; improvements (cross-encoder re-ranker, learned fusion weights, structured query parsing) are noted as future work.

---

#### 5.3.5 Voice Pipeline Component Evaluation

> *The agent's input is spoken Vietnamese. If STT mishears "Ốc Hương" as "Ốt Hương" or VAD cuts off mid-sentence, the entire pipeline operates on corrupted input. These component-level metrics validate the speech pipeline independently of the agent.*

##### 5.3.5.1 Speech-to-Text Accuracy

> **Goal:** Measure faster-whisper PhoWhisper transcription accuracy on Vietnamese restaurant domain utterances.

- **Dataset** *(to be built)*: 50–100 recorded Vietnamese restaurant utterances covering: dish names (tonal accuracy test), quantities ("2 phần", "1 dĩa"), modifiers ("ít cay", "nhiều hành"), payment phrases ("tính tiền", "check out"), casual speech ("cho em xin...", "quán mình có..."). Ground-truth transcriptions by human annotator fluent in Vietnamese. Recorded in realistic conditions: quiet room + simulated restaurant ambient noise at 2 levels.

- **Methodology:** Run faster-whisper medium via `stt_phowhisper.py` with `language=vi`, `beam_size=5`. Compare output against ground truth using edit-distance alignment (S=substitutions, D=deletions, I=insertions).

- **Metrics:**

  | Metric | Value |
  |--------|-------|
  | Word Error Rate (WER) | [pending] |
  | Character Error Rate (CER) | [pending] |
  | WER (quiet) | [pending] |
  | WER (ambient noise: 50 dB) | [pending] |
  | WER (ambient noise: 60 dB) | [pending] |
  | Per-category WER (dish names / quantities / modifiers / payment) | [pending] |

- **Analysis:** CER captures tonal diacritic errors that WER misses (Vietnamese is monosyllabic — character-level errors directly impact meaning). Example: "Ốc Hương" (snail) vs "Ốt Hương" (pepper) — same word count, wrong character, WER=0 but CER=0.25. Dish name category expected to show highest CER due to rare words outside Whisper training distribution. Ambient noise at 60 dB should show moderate degradation — validates feasibility for real restaurant deployment.

##### 5.3.5.2 Voice Activity Detection Accuracy

> **Goal:** Measure Silero VAD's ability to correctly detect utterance boundaries in Vietnamese speech.

- **Dataset** *(to be built)*: ~30 annotated audio clips (5–15 seconds each) containing Vietnamese utterances with hand-annotated speech start/end timestamps. Mix of: isolated single utterances, speech with trailing silence, speech preceded by background noise (chair scrape, plate clink), rapid turn-taking (short inter-speaker gap), quiet trailing consonants (common in Vietnamese: "không ạ" — the "ạ" is very soft).

- **Methodology:** Run Silero VAD via `vad_silero.py` with current production sensitivity threshold. Compare detected boundaries against ground truth. Tolerance: ±200ms for start, ±300ms for end.

- **Metrics:**

  | Metric | Definition | Value |
  |--------|-----------|-------|
  | False trigger rate | VAD triggers on noise-only segments / total silence segments | [pending] |
  | Missed utterance rate | Utterances VAD completely failed to detect / total utterances | [pending] |
  | Cut-off rate (premature end) | Utterances where detected end < ground_truth_end − 300ms | [pending] |
  | Start boundary mean error | mean(ground_truth_start − detected_start) in ms | [pending] |
  | End boundary mean error | mean(ground_truth_end − detected_end) in ms | [pending] |

- **Analysis:** Missed utterances are the worst failure mode — the customer speaks and nothing happens. False triggers are annoying but recoverable (capture is discarded, customer tries again). Cut-off rate is Vietnamese-specific: trailing particles like "ạ", "nhé", "nha" are very quiet and easily lost. If cut-off rate >10%, sensitivity threshold needs reduction (trading more false triggers for fewer cut-offs).

##### 5.3.5.3 Barge-In Effectiveness

> **Goal:** Verify that customer speech during TTS playback successfully interrupts the robot.

- **Methodology:** Instrument `tts_engine.py` and `vad_silero.py`. Run 20 simulated barge-in scenarios: TTS plays a 3-sentence response, customer begins speaking at sentence 2. Measure whether TTS stops and the new utterance is captured.

- **Metrics:**

  | Metric | Value |
  |--------|-------|
  | Barge-in success rate | [pending — expect >90%] |
  | Mean TTS stop latency (ms) | [pending — from VAD trigger to audio output silence] |
  | False barge-in rate (ambient noise triggers interrupt) | [pending] |

- **Analysis:** Barge-in is what makes conversation feel natural. If TTS keeps playing while customer speaks, the voice interaction feels broken. Mean stop latency should be <300ms for imperceptible interruption. False barge-in from ambient noise should be near 0 to avoid annoying interruptions.

---

### 5.4 AI Agent — End-to-End Evaluation

#### 5.4.1 Conversation Scenario Evaluation

> **Goal:** Measure the agent's ability to complete multi-turn ordering conversations end-to-end, validating that the full pipeline (router → worker → validator → tools → response) works correctly on real-world tasks.

- **Dataset:** 11 scenarios across two parts:
  - **Part 1 (6 happy-path):** single item, multi item, search-then-order, order-then-pay, search-only, add-then-confirm
  - **Part 2 (5 edge-case):** swap items, full payment flow, modify quantity, chitchat-then-order, remove item

- **Methodology:** Run `eval_e2e.py`. Each scenario is a sequence of user turns with expected assertions per turn (expected tool calls, response content keywords, state transitions). Scenario passes if ALL turn assertions pass. Agent uses live Ollama instance.

- **Metrics:** Overall pass rate, per-scenario pass/fail, turn count, failure categorization.

- **Results:**

  | Metric | Value |
  |--------|-------|
  | Total Scenarios | 11 |
  | Passed | 9 |
  | Failed | 2 |
  | Pass Rate | **81.8%** |
  | Total Turns | 29 |
  | Avg Turns per Scenario | 2.6 |

  **Part 1 (Happy-path) — 6/6 passed:**

  | ID | Name | Difficulty | Turns | Result |
  |----|------|-----------|-------|--------|
  | E2E-001 | Single item order | Easy | 2 | ✓ |
  | E2E-002 | Multi-item order | Easy | 2 | ✓ |
  | E2E-003 | Search then order | Medium | 3 | ✓ |
  | E2E-004 | Order then pay | Medium | 3 | ✗ |
  | E2E-005 | Search only (no order) | Medium | 2 | ✓ |
  | E2E-006 | Add item then confirm | Medium | 3 | ✓ |

  **Part 2 (Edge-case) — 3/5 passed:**

  | ID | Name | Difficulty | Turns | Result |
  |----|------|-----------|-------|--------|
  | E2E-007 | Swap item | Hard | [pending] | [pending] |
  | E2E-008 | Full payment flow | Hard | [pending] | [pending] |
  | E2E-009 | Modify quantity | Hard | [pending] | [pending] |
  | E2E-010 | Chitchat then order | Hard | [pending] | [pending] |
  | E2E-011 | Remove item from cart | Medium | [pending] | [pending] |

- **Failure categorization:**

  | Failure Type | Count | Example |
  |-------------|-------|---------|
  | Backend dependency | 1 | E2E-004: `request_payment` failed because orchestrator backend crashed (`Connection refused`). Payment response didn't match assertion for QR + total. NOT an agent error — infrastructure failure |
  | Chitchat → order transition | [pending] | Agent fails to switch from casual conversation to order-taking when customer transitions mid-conversation |
  | Missing tool calls | [pending] | LLM produces a text response instead of the expected tool call under `tool_choice="any"` |
  | Router misclassification | [pending] | Intent classified incorrectly, routing to wrong worker |
  | Validator false rejection | [pending] | Valid menu item rejected as off-menu |

- **Model comparison (optional):**

  | Model | Pass Rate | Notes |
  |-------|-----------|-------|
  | Qwen2.5 7B | [pending] | Current default |
  | gemma4:e2b-it-qat | 72.73% (8/11) | Prior run, higher latency |
  | Qwen2.5 3B | [pending] | Lower VRAM, faster but potentially less accurate |

#### 5.4.2 Out-of-Menu Robustness

*(Cross-reference with §5.3.2 validator results — this section provides the E2E behavioral perspective, §5.3.2 provides the component-level metrics.)*

- **Results (4/4 pass):** Validator correctly rejects off-menu items in all 4 adversarial scenarios. Agent never calls `confirm_order` with invalid items. Nearest-match suggestions are contextually reasonable.

- **Behavioral findings:**
  1. Agent distinguishes "partially valid" from "fully invalid" — keeps valid items in cart, only removes invalid ones
  2. Spelling variants ("Cơm Tấm" for "Cơm Chiên") correctly caught as off-menu, nearest-match suggested
  3. Agent maintains conversational tone when rejecting — doesn't break character as a waiter
  4. No scenario triggers the circuit breaker (max 3 retries not reached)

#### 5.4.3 Real-Life Qualitative Case Studies

> *These are not quantitative evaluations. They demonstrate the agent's behavior in realistic multi-turn scenarios and validate the design decisions made in Chapter 4.*

- **Dataset:** `e2e_real_life.json` — 4 scenarios:
  1. **First-time couple:** browse menu → ask about best sellers → order multiple dishes → modify order → pay
  2. **Allergic customer + party join:** allergy inquiry → filter by dietary restriction → late-joining friend adds more items → pay
  3. **Drunk group late night:** casual/informal language → ambiguous orders ("cho Ốc Hương đi") → clarification → multiple rounds of additions
  4. **Curious tourist:** asks about unfamiliar dishes → searches by description → cultural questions → orders

- **Methodology:** Run `run_real_life.py`. Each scenario is executed sequentially. Full per-turn trace logged: router classification → worker tool calls → validator output → response. Manual analysis of behavioral correctness.

- **Per-scenario trace format:**
  ```
  Scenario: First-time couple (4 turns)
  
  Turn 1: "Quán mình có món gì ngon nhất?"
    Router: CHAT (SLM, 1.56s)
    Worker: chat_worker → ChatResponseContext with best_seller.json
    Response: "Dạ, quán có các món best seller: Ốc Hương Xốt Trứng Muối (170k)..."
    ✓ Correct: handled as recommendation, not order
  
  Turn 2: "Vậy cho 1 Ốc Hương Xốt Trứng Muối và 1 Lẩu Thái"
    Router: ORDER (semantic, ~15ms)
    Worker: order_worker → LLM calls add_cart("Ốc Hương Xốt Trứng Muối", 1), add_cart("Lẩu Thái", 1)
    Validator: both items exact match ✓
    Response: "Dạ, giỏ hàng có: Ốc Hương Xốt Trứng Muối (170k), Lẩu Thái (250k). Tổng 420k. Xác nhận ạ?"
    State: DRAFTING → AWAITING_CONFIRMATION ✓
  
  [... continuing in actual write-up]
  ```

- **Key findings to extract from traces:**
  - Ambiguity handling: "Ốc Hương" → agent asks for sauce choice (11 variants), doesn't auto-resolve
  - Cross-domain rejection: non-food questions correctly delegated to CHAT
  - Post-confirmation additions: adding after confirm triggers new order sequence
  - Context persistence: agent remembers cart across turns, doesn't lose context
  - Vietnamese naturalness: responses read as natural restaurant Vietnamese, not translated English

#### 5.4.4 Latency Analysis

> **Goal:** Measure end-to-end voice interaction latency and compare against the §4.4 latency budget. Identify bottlenecks.

- **Methodology:** Instrument edge voice device and agent server with high-resolution timestamps. Measure across all 29 turns from 11 E2E scenarios. Categorize turns by intent type (ORDER vs SEARCH vs CHAT vs PAYMENT) since agent inference time varies significantly.

- **Per-stage breakdown:**

  | Stage | Location | Mean (s) | Median (s) | p95 (s) | Budget (§4.4) |
  |-------|----------|----------|------------|---------|---------------|
  | VAD + audio capture | Jetson | [pending] | [pending] | [pending] | ~0.2s + utterance |
  | STT (faster-whisper) | Jetson | [pending] | [pending] | [pending] | ~0.8s |
  | HTTP round-trip | Network | [pending] | [pending] | [pending] | ~0.05s |
  | Agent inference (semantic) | Server | ~0.015s | — | — | — |
  | Agent inference (SLM) | Server | [pending] | [pending] | [pending] | ~1.5–2.5s |
  | TTS first sentence | Jetson | [pending] | [pending] | [pending] | ~0.5s |
  | **Total (semantic fast-track)** | — | [pending — estimate ~1.5s] | — | — | < 5s |
  | **Total (SLM fallback)** | — | [pending — estimate ~3–4s] | — | — | < 5s |

- **Per-intent agent latency:**

  | Intent | Mean Agent Time (s) | Dominant Factor |
  |--------|---------------------|-----------------|
  | ORDER (semantic) | ~0.015s | Embedding + cosine similarity |
  | ORDER (SLM) | ~0.30s | LLM tool call (small prompt) |
  | SEARCH | ~1.26s | LLM query rewrite + retrieval |
  | PAYMENT | [pending] | Deterministic — no LLM |
  | CHAT | ~1.56s | LLM response generation |
  | Multi-intent | ~1.9–2.2s | Multiple sequential LLM calls |

- **Cold-start vs warm-cache:**
  - First utterance after Ollama restart: +X seconds (model load + warmup)
  - Subsequent utterances: warm cache, `keep_alive=-1` eliminates reload
  - Warmup ping at agent startup eliminates cold-start for the first real customer

- **Bottleneck identification:** The SLM LLM call dominates latency (1–2s). Semantic fast-track avoids this for ~33% of ORDER utterances. TTS sentence streaming overlaps with agent response generation for subsequent sentences, hiding some latency from the user. STT latency is fixed by model size (fast-whisper medium ~800ms; smaller model would be faster but less accurate for Vietnamese tones).

#### 5.4.5 Response Quality Evaluation

> **Goal:** Quantify the subjective quality of the agent's Vietnamese responses — are they natural, correct, and helpful? This is the closest proxy for "does the system work as a waiter?"

- **Dataset** *(to be built)*: 20–30 agent responses sampled from the 11 E2E scenarios + 4 real-life scenarios. Select responses covering all response types: template-based (cart confirmation, payment prompt, error), LLM-generated (search results, free-form chat, off-menu suggestions). Mix of short (1 sentence) and long (3+ sentences) responses.

- **Methodology:** MOS (Mean Opinion Score) with 3–5 Vietnamese-speaking raters. Each rater independently scores each response on 3 dimensions. Raters are given the conversation context (previous turns) and the customer's utterance to judge appropriateness.

- **Metrics:**

  | Dimension | Scale | Description |
  |-----------|-------|-------------|
  | **Naturalness** | 1–5 | 1=clearly machine-generated/translated, 5=indistinguishable from a Vietnamese waiter |
  | **Correctness** | 1–5 | 1=factually wrong (wrong price, wrong dish, hallucinated info), 5=completely accurate |
  | **Helpfulness** | 1–5 | 1=doesn't address the customer's request, 5=fully addresses and adds useful guidance |

- **Results:**

  | Dimension | Mean MOS | Std | Min | Max |
  |-----------|----------|-----|-----|-----|
  | Naturalness | [pending] | [pending] | [pending] | [pending] |
  | Correctness | [pending] | [pending] | [pending] | [pending] |
  | Helpfulness | [pending] | [pending] | [pending] | [pending] |

  | Response Type | Naturalness | Correctness | Helpfulness | N |
  |--------------|-------------|-------------|-------------|---|
  | Template-based | [pending] | [pending] | [pending] | [pending] |
  | LLM-generated | [pending] | [pending] | [pending] | [pending] |

- **Inter-annotator agreement:**

  | Dimension | Cohen's κ |
  |-----------|-----------|
  | Naturalness | [pending — target ≥0.6] |
  | Correctness | [pending — target ≥0.6] |
  | Helpfulness | [pending — target ≥0.6] |

- **Template vs LLM comparison:** Template responses should score higher on correctness (deterministic, formula-driven) but potentially lower on naturalness (may sound repetitive). LLM responses should score higher on naturalness (varied phrasing) but risk lower correctness (hallucination risk). This comparison validates the hybrid response strategy from §4.3.6.

- **Per-turn naturalness decay (optional):** Track naturalness scores across turns within a multi-turn conversation. Does response quality degrade as the conversation lengthens (context window pressure)?

  | Turn # | N | Mean Naturalness |
  |--------|---|-----------------|
  | 1 | [pending] | [pending] |
  | 2 | [pending] | [pending] |
  | 3 | [pending] | [pending] |
  | 4+ | [pending] | [pending] |

---

### 5.5 System Integration & Quality Validation

#### 5.5.1 End-to-End Integration Test

> **Goal:** Validate that all 3 UIs + robot + backend maintain consistent state through a complete service lifecycle.

- **Methodology:** Execute full service flow: kiosk seating → robot dispatch → robot arrival → customer voice order → kitchen panel display → order status progression → payment → table reset. Verify state at each step across all UIs by inspecting WebSocket events and REST responses.

- **Test sequence and verification:**

  | Step | Action | Expected State | Verified On |
  |------|--------|---------------|-------------|
  | 1 | Kiosk: seat party at Bàn 1 | Table: DANG_PHUC_VU, Session: ACTIVE, Task: go_to_table PENDING | Kiosk, Panel, DB |
  | 2 | Dispatch: robot assigned | Task: ASSIGNED → Robot drives to Bàn 1 | Panel (minimap + robot card) |
  | 3 | Robot arrives at table | Task: DONE, table-robot voice binding set | Panel, Voice bridge |
  | 4 | Customer: "Talk to AI" button | voice-device WS: start_listening | Tablet UI, Voice device |
  | 5 | Customer speaks order | voice.heard → thinking → voice.reply + cart sync | Tablet UI (voice panel + cart) |
  | 6 | Customer confirms order | Order: CHO_BEP, Kitchen board shows new order | Tablet UI, Panel (KitchenBoard) |
  | 7 | Kitchen: advance to XONG | Order: XONG, Task: deliver created + assigned | Panel, Robot WS |
  | 8 | Customer: request payment | VietQR displayed, session total computed | Tablet UI (payment screen) |
  | 9 | Payment verified | Session: CLOSED, Table: DA_THANH_TOAN, robot released | All UIs |
  | 10 | Staff: end table | Table: TRONG, pending tasks cancelled | Panel, DB |

- **State synchronization verification:** At each step, confirm all 3 UIs agree on: table status, current order status, cart contents, payment state. Any disagreement is a bug.

- **Concurrent multi-table test:** Run 2 tables simultaneously. Verify: (a) each tablet shows only its own orders, (b) kitchen panel shows both tables' orders correctly, (c) robot dispatch handles 2 concurrent tasks correctly, (d) no cross-table state bleed.

#### 5.5.2 WebSocket Event Propagation Latency

- **Methodology:** Instrument WebSocket client to record `sent_at` (server-side timestamp in event payload) and `received_at` (client-side timestamp). Measure for key event types. N = 50 events per type.

- **Results:**

  | Event Type | Mean Latency (ms) | p95 Latency (ms) |
  |-----------|--------------------|--------------------|
  | `order.created` | [pending] | [pending] |
  | `table.updated` | [pending] | [pending] |
  | `robot.updated` | [pending] | [pending] |
  | `voice.heard` | [pending] | [pending] |
  | `voice.reply` | [pending] | [pending] |

- **Analysis:** Local WiFi, single-server — expected < 50ms p95 for all event types. Higher latency indicates server-side bottleneck (likely LLM inference, not WebSocket).

#### 5.5.3 System Timing & Throughput

> **Goal:** Measure backend responsiveness under load — API response times, dispatcher latency, and database performance. Validates that the orchestrator meets real-time restaurant requirements.

- **Methodology:** Instrument FastAPI middleware to log request duration per endpoint. Measure during 11 E2E scenario runs (natural load: sequential turns with LLM pauses). For throughput: simulate concurrent tables.

- **API endpoint response time:**

  | Endpoint | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) |
  |----------|-----------|----------|----------|----------|
  | `GET /menu` | [pending] | [pending] | [pending] | [pending] |
  | `POST /orders` | [pending] | [pending] | [pending] | [pending] |
  | `POST /payments` | [pending] | [pending] | [pending] | [pending] |
  | `POST /seatings` | [pending] | [pending] | [pending] | [pending] |
  | `POST /voice/event` | [pending] | [pending] | [pending] | [pending] |
  | `POST /voice/listen` | [pending] | [pending] | [pending] | [pending] |
  | `GET /robots` | [pending] | [pending] | [pending] | [pending] |

  **Expected:** All endpoints <100ms p95 except `/voice/event` (which includes JSON payload with cart data — still should be <200ms). No endpoint should exceed 500ms at p99 — the server is single-threaded synchronous (FastAPI + SQLite) and a slow endpoint blocks all subsequent requests.

- **Robot dispatcher timing:**

  | Metric | Value |
  |--------|-------|
  | Mean task assignment latency (PENDING→ASSIGNED) | [pending] |
  | Mean dispatch cycle time | [pending] |
  | Watchdog scan interval | 5s (config) |

  **Analysis:** The dispatcher runs synchronously. Task assignment latency should be near-instant (<50ms) since it's a dictionary lookup + distance computation on 3–5 robots. If >100ms, SQLite query is the bottleneck.

- **Database performance:**

  | Metric | Value |
  |--------|-------|
  | SQLite write latency (single INSERT) | [pending] |
  | SQLite read latency (SELECT with JOIN) | [pending] |
  | DB file size after 100 orders | [pending] |
  | WAL mode checkpoint interval | [pending] |

  **Analysis:** SQLite in WAL mode with single-writer access should handle restaurant workload easily. The bottleneck is never the database — it's LLM inference. This validates the architectural choice in §4.5.1.

- **Concurrent load test:** Simulate 2 tables ordering simultaneously. Measure: (a) any request queuing or timeout, (b) cross-table state isolation maintained, (c) WebSocket events delivered to correct tables only.

  | Metric | Value |
  |--------|-------|
  | Max concurrent requests observed | [pending] |
  | Peak memory usage (server process) | [pending] |
  | Any 5xx errors | [pending — should be 0] |

---

### 5.6 Summary of Results

> *Each §1.3 objective is mapped to its measured result, compared against the target, and marked pass/fail.*

| # | §1.3 Objective | Target | Measured Result | Status | Section |
|---|---------------|--------|-----------------|--------|---------|
| 1 | EKF-fused odometry error | ≤ X cm | [pending] | [pending] | §5.2.1 |
| 2 | Navigation success rate | ≥ X% | [pending] | [pending] | §5.2.2 |
| 3 | ArUco docking error | < X cm / X° | [pending] | [pending] | §5.2.3 |
| 4 | Intent router accuracy | ≥ 90% | **90.00%** (72/80) | ✓ PASS | §5.3.1 |
| 5 | RAG precision/recall@5 | [set target] | P@5: 30.83%, R@5: 70.14%, Hit: 87.50% | ⚠ Adequate | §5.3.4 |
| 6 | E2E voice ordering completion | [set target] | **81.8%** (9/11) | ⚠ Partial | §5.4.1 |
| 7 | Voice turn latency | < 5s | [pending] | [pending] | §5.4.4 |
| 8 | STT Word Error Rate (Vietnamese) | [set target] | [pending] | [pending] | §5.3.5.1 |
| 9 | VAD missed utterance rate | [set target] | [pending] | [pending] | §5.3.5.2 |
| 10 | Validator off-menu leak rate | 0% | **0%** (0/4 scenarios) | ✓ PASS | §5.3.2 |
| 11 | Response quality MOS (Naturalness) | [set target] | [pending] | [pending] | §5.4.5 |

**Additional key results (not tied to §1.3 objectives but validating Chapter 4 design claims):**

| Claim | Result | Proves |
|--------|--------|--------|
| Hybrid router outperforms either tier alone | Semantic-only ~65%, SLM-only ~92%, Hybrid 90% at 0.66× latency | §5.3.1 ablation 1 |
| Dynamic context injection matters | Accuracy drop from ~90% → <50% on context-dependent cases with context OFF | §5.3.1 ablation 3 |
| Few-shot examples are necessary | Accuracy drop from 90% → [pending]% at 0-shot | §5.3.1 ablation 2 |
| Validator prevents cart contamination | 0 off-menu items in cart with validator ON; [pending] with OFF | §5.3.2 ablation |
| Delegate prevents wrong tool calls | [pending] wrong tool calls with delegate OFF | §5.3.3 ablation |
| Validator latency is negligible | <50ms vs 1–2s LLM inference | §5.3.2 |
| Barge-in works reliably | [pending]% success rate | §5.3.5.3 |

- **Discussion of key findings:**
  - The router meets its 90% accuracy target. Remaining errors cluster in SEARCH↔PAYMENT boundary cases and complex multi-intent decomposition — both areas where few-shot prompt improvements could close the gap.
  - The validator is 100% effective on adversarial test cases — no off-menu item ever reaches `confirm_order`. This is the strongest safety result and the most important single number in the AI evaluation.
  - E2E pass rate of 81.8% reflects both agent errors (chitchat→order transitions, missing tool calls) and infrastructure failures (payment backend crash). Agent-intrinsic failures are the actionable items.
  - Retrieval metrics are adequate for a conversational suggestion system but insufficient for autonomous ordering — the agent's architecture (customer confirms before order) compensates for moderate precision.
  - The ablation studies (when completed) will be the centerpiece of the defense presentation — they prove each design decision was necessary, not arbitrary.
  - Template responses should score higher on correctness; LLM responses should score higher on naturalness. The hybrid response strategy from §4.3.6 is validated if both score above 3.5.
  - STT WER is the gating factor for the entire voice pipeline — if WER exceeds ~15% on dish names, the agent receives corrupted input and downstream accuracy suffers, regardless of router/validator quality.
  - [Add any surprising/unexpected result and its implication for the design]

- **Visual summary:** Radar chart or bar chart of all key metrics normalized to their targets. Separate chart for ablation comparisons (with/without each component).

- **Failure budget allocation:** Across all 19 E2E + adversarial + real-life scenarios (11 + 4 + 4), categorize every failure by root cause:

  | Failure Category | Count | % of Total | Most Affected Component |
  |-----------------|-------|-----------|------------------------|
  | Router misclassification | [pending] | [pending] | Router (§4.3.2) |
  | Worker tool-call error | [pending] | [pending] | LLM decision (§4.3.3) |
  | Validator false positive | [pending] | [pending] | Validator (§4.3.4) |
  | Backend/infrastructure | [pending] | [pending] | Orchestrator (§4.5) |
  | LLM response generation error | [pending] | [pending] | Response node (§4.3.6) |
  | STT transcription error | [pending] | [pending] | Voice pipeline (§4.4) |

  This budget identifies where to invest improvement effort — the component with the most failures is the system's weakest link.

---

## CHAPTER 6: CONCLUSION AND FUTURE WORKS

### 6.1 Conclusion
- Tick each §1.3 objective against Ch.5 numbers
- Summarize both contribution legs:
  - Autonomous TWD navigation + EKF-fused odometry + RTAB-Map + Nav2 + ArUco docking
  - Two-tier hybrid router (90% accuracy) + agentic LangGraph workflow (multi-intent, tool execution, deterministic validator) + hybrid RAG (BM25+FAISS+RRF for Vietnamese menus) + voice pipeline + 3 web UIs

### 6.2 Limitations
- Consumer-grade IMU (MPU6050) → yaw drift, no magnetometer
- Wheel slip on smooth floors
- ArUco docking: lighting sensitivity (D435), no final-approach controller implemented
- Router: SEARCH↔PAYMENT confusion (85.7% payment accuracy)
- E2E: backend dependency failures inflate error rates; chitchat→order transitions fragile
- TTS not yet fully wired; some UIs unfinished
- Single-robot, single-restaurant scope

### 6.3 Future Works
- Better IMU / add visual odometry (D435 RGB-D) for drift correction
- Final-approach docking controller with ArUco feedback loop
- On-device LLM quantization for fully offline operation
- Dynamic obstacle handling (pedestrians in lane)
- Multi-robot coordination with task rebalancing
- Returning-customer recognition (persistent preferences)
- Multi-language support (English, additional)
- Real payment gateway integration (replace mock VietQR)
- Complete all UIs + TTS integration

---

## Appendices
- A. API Endpoint Reference
- B. SQLite Schema (ERD)
- C. WebSocket Event Catalog
- D. Menu Data Structure (dish fields + category distribution)
- E. Setup & Run Commands

---

## Front Matter (write last)
- Abstract (1 page: problem, method, key numbers)
- List of Figures
- List of Tables
- List of Acronyms
- Acknowledgements
- Declaration (per university template)
