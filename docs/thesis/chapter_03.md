CHAPTER 4: PROPOSED METHOD (II) — AI, BACKEND & WEB SYSTEM
4.1 System Requirements & Design Rationale
- Functional requirements: natural language ordering in Vietnamese, menu search, payment flow, order→kitchen dispatch, robot task management, multi-table voice support
- Non-functional: self-hosted (no cloud LLM dependency), low-latency voice interaction, deterministic validation guarding LLM outputs, per-session conversation isolation
- Design principles: centralized brain (single server), thin edge (Jetson handles only voice I/O + robot control), deterministic safety net between every LLM call and system action, session-scoped memory
4.2 Overall Software Architecture
- Three-tier topology: Server tier (Agent brain + Orchestrator backend + Ollama LLMs + RAG indices), Robot tier (Voice pipeline + ROS2 navigation stack), Client tier (3 browser SPAs)
- Block diagram: from diagram.md Fig 4.1 — show all components, protocols, and the 4 main data flows: (a) voice ordering, (b) order→kitchen, (c) manager monitoring, (d) backend→robot goals
- Component responsibility map: what runs where, what talks to what over which protocol
4.3 Conversational Agent — LangGraph StateGraph
This is the intellectual core of the software contribution. Give it the most depth.
4.3.1 Agent State Definition
- AgentState TypedDict: 20 fields organized by purpose — conversation history (messages), task state (active_cart, order_stage, search_context), routing state (current_intents, routing_meta), and per-turn ephemeral fields (validation, feedback, UI actions, loop counters)
- State reducer functions: messages append (not overwrite), cart merges, stage transitions
- What persists across turns vs. what resets each turn
4.3.2 Graph Architecture
- Full StateGraph: START → router → (order_worker | search_worker | payment_dispatch | chat_worker) → validator → tools → state_updater → [multi-intent loop] → state_outcome → response_node → END
- 11 nodes, 7 conditional edges, 5 normal edges
- Three-stage conceptual pipeline: Classify (router determines what the user wants) → Execute (workers call tools, validator checks, tools run, state updates — looping per intent) → Respond (build typed response context, generate text or template)
- Compiled with SQLite checkpointer (thread_id = session_id)
4.3.3 Intent Classification — Trained MLP Classifier
- Intent taxonomy: 4-class output (ORDER, SEARCH, PAYMENT, CHAT). ORDER_CONFIRM merged into ORDER at router level; downstream order state machine handles the distinction
- Input features (778-dim): 768-dim frozen sentence embedding (bkai-foundation-models/vietnamese-bi-encoder) + 10 context features from AgentState
- Context features: order_stage one-hot (5-dim), has_cart, cart_size_norm, has_search_context, search_context_size_norm, utterance_length_norm
- Network: 3-layer MLP (778→256→64→4) with ReLU, Dropout(0.2), softmax output
- Training: 3,712 synthetic utterances, 80/20 split, class-weighted CrossEntropyLoss, Adam, early stopping
- Why trained classifier over LLM routing: (a) ~0.17ms vs ~1.8s forward pass — 10,000× faster, (b) deterministic (same input → same output), (c) context features encode conversation state that embeddings miss, (d) 95.6% vs 73.3% accuracy on 45-case A/B comparison
- Inference: word segmentation → embedding → context extraction → StandardScaler → concatenate → MLP → softmax (total ~52ms, embedding dominates at ~50ms)
- The router design evolved through three iterations evaluated as an ablation: semantic centroid (89.0% on 100 cases) → two-tier hybrid (73.3% on 45 cases) → trained MLP (92.0% on 100 cases, 97.4% on 39-case holdout)
4.3.4 Workers — Per-Intent Processing
Worker	Type	What it does	Why this design
ORDER	LLM call	Qwen2.5 7B, temp=0.1, tool_choice="any" → one cart CRUD tool	Menu NOT in prompt (~200 tokens). 5 few-shot examples with tool calls for KV-cache sharing. Retry on empty output
SEARCH	LLM call	Same model → search() or delegate()	Dynamic "đã biết" context (prior search results + cart items) prevents redundant searches. Query rewriting: "ấm bụng" → "cháo, lẩu, súp"
PAYMENT	Deterministic, no LLM	Always emits request_payment	Router already decided. No LLM latency for a fixed action
CHAT	Pure function, no LLM	Builds ChatResponseContext with curated memory from search history + cart	Follow-up questions about dishes shouldn't require LLM calls
- Multi-intent execution loop: current_intents as a queue. After each tool executes and state updates, pop front → route to next worker. Empty queue → proceed to response. Supports "Cho 2 Ốc Hương rồi tính tiền luôn" → [ORDER, PAYMENT] sequential execution in one turn
4.3.5 Deterministic Validator — Between LLM and Action
This is the safety mechanism that makes the LLM-based system reliable enough for a real restaurant.
- Fully rule-based, no LLM — predictable, fast, debuggable
- Menu name resolution (resolve_menu_name): normalize (lowercase + strip diacritics via Unicode NFD) → exact match → prefix match → substring match → token-Jaccard fallback (threshold 0.3)
- Edge cases handled:
- Simultaneous add_cart + confirm_order in one turn → stripped, error
- Additive turn LLM forgetting existing cart → auto-restore if additive markers detected ("thêm", "nữa", "lấy thêm")
- Off-menu items → captured in unavailable_items with nearest-match suggestion
- Ambiguous names (e.g., "Ốc Hương" matches 11 sauce variants) → flagged for clarification, never auto-resolved
- Modifier stripping ("Lau Thai, it cay" → name="Lau Thai", special_requests="it cay")
- Context-duplicate items → deduplicated against existing cart
- Circuit breaker: max 3 retry loops with feedback → RetryResponseContext → apology output
4.3.6 Cart State Machine
- States: IDLE → DRAFTING → AWAITING_CONFIRMATION → CONFIRMED
- Transitions: first add_cart moves to DRAFTING. Agent echoes cart → AWAITING_CONFIRMATION. Customer confirms or adds/removes (loop back to DRAFTING then AWAITING_CONFIRMATION). confirm_order → CONFIRMED. Payment → IDLE
- Why a formal state machine: prevents the LLM from confirming an empty cart, overwriting a confirmed order, or jumping stages
4.3.7 Tool Inventory
Tool	Type	Backend Action
search	RAG	Query hybrid retriever, return top-k menu items
add_cart	State-only	Add items to cart (validator resolves names)
remove_cart	State-only	Remove named item from cart
clear_cart	State-only	Empty cart, reset to IDLE
confirm_order	Backend API	POST /orders → create order, get ID
request_payment	Backend API	POST /payments → generate VietQR
verify_payment	Backend API	POST /payments/verify → mark paid
delegate	Escape hatch	Route to CHAT worker with reason
4.3.8 Response Generation
- Typed ResponseContext dispatch: OrderResponseContext, SearchResponseContext, PaymentResponseContext, ChatResponseContext, RetryResponseContext
- Template-based for deterministic cases (order confirmation, payment prompts, errors, retries) — fast and predictable
- LLM-based for open-ended cases (search results, off-menu suggestions, free-form chat) — Qwen2.5 7B with sentence-level SSE streaming
- Sentence splitting: re.split(r"[.!?]\s", buffer) → each complete sentence emitted as SSE event
4.4 Knowledge Retrieval System — Hybrid RAG
4.4.1 Knowledge Sources & Document Structure
- 217 dishes from menu.json across 12 categories. Per-dish document: Vietnamese natural-language description + structured metadata (name, price, category, diet_type, taste_profile, tags)
- Supporting sources: restaurant_info.txt, best_seller.json, customer_info.json (FAQ)
4.4.2 Index Construction
- FAISS dense index: bkai-foundation-models/vietnamese-bi-encoder (768-dim). Fingerprint file verifies model identity at load time to prevent dimension mismatches
- BM25 sparse index: rank_bm25.BM25Okapi with k1=1.2, b=0. Vietnamese word segmentation via underthesea.word_tokenize for both indexing and querying. Index text: concatenated metadata fields optimized for keyword matching
4.4.3 Hybrid Retrieval with RRF Fusion
- Parallel BM25 + FAISS search via ThreadPoolExecutor (2 workers), raw k=10 each
- Dual-lane gatekeeper: semantic lane (top FAISS score ≥ 0.35) OR lexical lane (at least one query keyword matches top document). Both lanes fail → return empty (safer than feeding noisy context to LLM)
- RRF fusion: score(d) = Σ 1/(60 + rank_d) — sums scores from both retrievers for documents appearing in both lists
- Metadata post-filters: max_price, min_price, diet_type, category — applied via substring matching to menu-type documents only
- Final results: sorted by fused score descending, truncated to k=5
4.4.4 Vietnamese-Specific Handling
- BM25 tokenization via underthesea: "ốc_hương xốt trứng_muối" (compound words preserved as units)
- Embedding: BGE-M3 fine-tune handles Vietnamese natively, raw text input, no pre-processing
- Gatekeeper: lowercase + punctuation removal only. No diacritic stripping (tones carry meaning)
4.5 Voice Processing Pipeline
4.5.1 Pipeline Architecture
- Microphone → Silero VAD (utterance boundary detection) → faster-whisper PhoWhisper (STT, language=vi, beam_size=5) → LangGraph agent (§4.3) → Piper TTS (local) / edge-tts (cloud fallback) → speaker
- Edge/server split: Jetson Orin Nano runs VAD + STT + TTS. Server runs agent + LLMs. Split rationale: STT/TTS are GPU-light inferable on Jetson; LLM requires server-grade GPU
- Threaded pipeline: VAD thread (mic capture, 512-sample chunks, speech probability) → speech queue → STT thread (faster-whisper transcription) → text queue → agent HTTP call
- Latency budget: VAD ~200ms → STT ~800ms → Agent 2-4s → TTS 500ms
4.5.2 Voice Activity Detection
- Silero VAD: neural frame-level speech probability output. Configurable sensitivity threshold. Utterance capture with start/end silence padding. Barge-in: VAD detects new speech during TTS playback → interrupts current output
4.5.3 Speech-to-Text
- faster-whisper with Whisper medium, language=vi, beam_size=5. PhoWhisper: Whisper weights fine-tuned on Vietnamese data for improved tonal recognition. No further training performed
4.5.4 Text-to-Speech
- Piper TTS (local, Vietnamese voice, edge-deployable, lower quality). edge-tts (cloud, Vietnamese Neural voices, higher quality, requires network). Streaming playback — speak each sentence as it is generated
4.6 Backend Orchestrator — FastAPI + SQLite + WebSocket
4.6.1 REST API Design
- 20 endpoints across 10 routers: menu, tables, orders, payments, robots, tasks, layout, admin, voice, WebSocket
- Request/response validation via Pydantic models. Auto-generated OpenAPI documentation. CORS for Vite dev ports
4.6.2 Database Schema
- SQLite, raw SQL via sqlite3 (no ORM) — single-file, serverless, ACID transactions
- 7 business tables: tables, sessions, dishes, orders, order_items, robots, tasks, payments
- Separate checkpoints.db for LangGraph conversation memory
- Migration via ALTER TABLE ADD COLUMN with PRAGMA table_info for idempotent schema evolution
- ERD diagram
4.6.3 Session Lifecycle
- Kiosk seating → POST /seatings → creates ACTIVE session, table → DANG_PHUC_VU, dispatches go_to_table task
- Multiple orders per session → cumulative payment (session total = sum of all order totals)
- Payment → POST /payments/verify → PAID, session → CLOSED, table → DA_THANH_TOAN
- Table-ended → PATCH /tables → TRONG, clears state, cancels pending robot tasks
4.6.4 WebSocket Hub
- Single /ws endpoint, 4 role types via query parameter:
- role=panel → anonymous broadcast (kitchen display, fleet dashboard)
- role=customer → anonymous broadcast filtered by table_id (tablets)
- role=robot → indexed by robot_id, bidirectional (task assignment + telemetry)
- role=voice-device → indexed by robot_id, server→client only (start/cancel listening)
- Event catalog: order.created, order.updated, table.updated, robot.updated, task.created, task.updated, voice.heard, voice.reply, reset
4.6.5 Voice Bridge
- POST /voice/event (agent → backend) → fans voice reply + UI action + cart state to role=customer WS
- POST /voice/listen (tablet → backend → voice-device WS) → triggers mic capture on the Jetson at that table
- POST /voice/cancel → aborts in-flight capture
- Dynamic table-robot voice binding: on robot arrival → bind_table_robot(table_id, robot_id). On release/disconnect → unbind
4.7 Web Interfaces
4.7.1 Customer Tablet UI
- Vue 3 + Vite + PrimeVue + Pinia (4 stores: ui, menu, cart, voice) + TailwindCSS 4
- Menu browsing: 12 categories, diacritic-insensitive free-text search, grouped items with scroll-based nav highlighting, Best Seller showcase
- Voice mirror: real-time conversation bubbles, agent cart sync, UI action following (open menu/payment triggers automatic navigation)
- Cart management: +/- controls, server-calculated total, order confirmation, VietQR payment
- Voice panel: listening orb (VAD active), thinking dots, recommended item quick-add, mute/close, barge-in stop
4.7.2 Kiosk (Check-in)
- Table grid (6 tables), real-time status (8s polling), party size selector
- Race condition handling: 409 → bounce guest to pick another table
- Success auto-close after 6 seconds
4.7.3 Management Panel (Kitchen + Fleet)
- Kitchen Kanban: 3 columns (Cho Bếp / Đang Làm / Xong), per-order time tracking, advance button
- Fleet board: robot cards (name, status, battery), activity description
- Table overview: status, party size, duration, active order details, call robot / end table actions
- Minimap: SLAM map SVG backdrop, color-coded tables, animated robot dots (5Hz live pose), drag-to-move
4.8 Robot Dispatch & Fleet Management
4.8.1 Telemetry Architecture
- RAM-only latest-value store: robot pose (x, y) + battery via heartbeat (4+ Hz) into thread-safe dict. Avoids SQLite write contention at sensor frequency
- Periodic DB snapshot every 15 seconds for cold-start recovery and panel reload
- Pose broadcast throttled to 5 Hz for minimap rendering
4.8.2 Task Assignment
- try_assign(): query PENDING tasks (FIFO), for each pick nearest idle robot:
- Filter: robot idle (DB) + live WS connection + battery ≥ 20% (RAM overlaid)
- Score: Euclidean distance from robot's live pose to table waypoint
- Assign: nearest
- Task kinds: go_to_table (seating), deliver (food ready), call (guest pressed button)
- Task lifecycle: PENDING → ASSIGNED → IN_PROGRESS → DONE
4.8.3 Watchdog & Fault Recovery
- Scans every 5 seconds, marks robots silent >30s as offline
- Hung robot: requeue tasks, kick zombie WS, unbind from table
- Table cleanup on payment/end: cancel all tasks, send robot home
4.9 Conversation Memory & Session Management
- LangGraph SqliteSaver checkpointer with thread_id = orchestrator_session_id
- Payment closes session → new guest → new thread_id → fresh context, no bleed between customers
- Persistent state across turns: active_cart, order_stage, search_context, full message history
- Per-turn cleanup: ui_action, feedback, is_valid, delegate_reason, unavailable_items, ambiguous_items, intent_queries reset each turn
4.10 Deployment Topology
- Hardware table: Server (x86 + GPU — Ollama + FastAPI + Agent), Jetson Orin Nano (robot — voice + ROS2), Laptops (browser-only SPA clients)
- LLM configuration: 3 models via Ollama (ROUTER_MODEL: temp=0.0, WORKER_MODEL: temp=0.1, RESPONSE_MODEL: temp=0.3), all keep_alive=-1 (pinned in VRAM), warmup ping at startup
- Package management: uv with role extras (server, voice, cu12/cu13), npm workspaces, Netbird VPN for off-site server