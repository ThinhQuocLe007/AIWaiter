## 4.1 System Requirements & Design Rationale

> **Status:** draft
> **Cross-refs:** see §4.2 for overall architecture, §4.3 for agent design
> **Figures needed:** none

---

### 4.1.1 Problem Statement

A restaurant waiter performs a closed-loop task: listen, understand, act, respond. The customer speaks in natural language; the waiter translates intent into system actions — add items to an order, search the menu, request payment — while verifying that every action is valid (the dish exists, the price is correct, the order makes sense). In a Vietnamese restaurant, this loop must operate in Vietnamese, with all its linguistic complexity: six tones, compound words, teencode, and informal speech patterns.

Commercial service robots (Bear Robotics Servi, Pudu Bellabot) handle navigation and tray delivery, but their interaction model is a touchscreen — there is no conversational layer. Cloud-based LLM chatbots (Wendy's FreshAI, Domino's AI ordering) handle English dialogue but require internet connectivity, incur API costs, and cannot dispatch a physical robot. No existing system integrates Vietnamese voice dialogue, LLM-based task execution, and autonomous robot delivery into one deployed pipeline.

This chapter presents the software system that closes that gap. It describes the AI agent, backend infrastructure, web interfaces, and voice pipeline that together form an autonomous Vietnamese-speaking waiter. The chapter is organized around a five-stage conversational pipeline — Understand, Decide, Validate, Execute, Respond — with supporting sections for the voice pipeline, backend orchestrator, robot dispatch, web interfaces, and deployment topology.

---

### 4.1.2 Functional Requirements

The system must support the following capabilities, derived from the operational workflow of a restaurant:

**FR1 — Natural language ordering in Vietnamese.** Customers must be able to speak naturally in Vietnamese to add, remove, and modify items in their order. The system must handle Vietnamese linguistic phenomena: compound words ("bún bò Huế"), tonal diacritics (ốc vs. ọc), teencode abbreviations ("ad" for anh/chị, "vs" for với, "ck" for chồng), short affirmations ("ừ", "ok", "được"), and implicit quantities ("cho 2 Ốc Hương").

**FR2 — Menu search by attributes.** Customers must be able to search the menu by taste ("món nào cay cay?"), dietary restriction ("món chay có gì?"), price range ("món dưới 100k"), food category ("có lẩu gì không?"), or vague descriptions ("món gì ấm bụng cho ngày lạnh?"). The system must retrieve relevant dishes from a 217-item Vietnamese seafood restaurant menu and present them conversationally.

**FR3 — Payment flow.** Customers must be able to request the bill, view the total (cumulative sum of all orders in the session), and confirm payment. The system must generate a payment request, display the amount, and close the session upon verification.

**FR4 — Order-to-kitchen dispatch.** When a customer confirms an order, the system must create the order in the backend, display it on the kitchen panel, and allow kitchen staff to advance its status (Chờ Bếp → Đang Làm → Xong). When marked Xong (completed), the system must automatically dispatch a robot to deliver the food to the customer's table.

**FR5 — Robot task management.** The system must manage a fleet of robots: assign delivery tasks, track robot positions and battery levels in real time, handle robot disconnections, and recover from failures (reassign tasks from a hung robot to an available one).

**FR6 — Multi-table concurrent support.** The system must serve multiple tables simultaneously. Each table has an independent conversation session, cart, and order state. Voice commands from one table must not affect another. Robot tasks for different tables must be queued and dispatched independently.

---

### 4.1.3 Non-Functional Requirements

**NFR1 — Self-hosted (no cloud LLM dependency).** The system must operate entirely on-premises. LLM inference runs on a local GPU via Ollama. Speech-to-text and text-to-speech run on the robot's Jetson edge computer. No external API calls are required during normal operation. This requirement is driven by three practical concerns: (a) restaurant WiFi may be unreliable — a cloud-dependent system fails when the internet fails; (b) API costs accumulate per-turn and are unpredictable at restaurant scale; (c) customer voice data stays on-premises, addressing privacy concerns.

**NFR2 — Low-latency voice interaction.** The total time from the customer finishing speech to the robot beginning its spoken reply must be under 5 seconds. This budget includes: voice activity detection and utterance capture (~200ms), speech-to-text transcription (~800ms with faster-whisper medium), network round-trip to the agent server (~50ms on local WiFi), agent inference (varies by intent: ~15ms for semantic-router fast-track, ~1–2s for LLM inference), and text-to-speech synthesis of the first sentence (~500ms). The 5-second target is based on human conversation turn-taking norms — longer pauses feel unnatural and cause customers to repeat themselves.

**NFR3 — Deterministic safety net between every LLM call and system action.** The LLM is probabilistic. It can hallucinate a dish name that does not exist on the menu, produce a nonsensical quantity, or attempt to confirm an order with invalid items. Before any LLM output becomes a system action (adding to cart, confirming an order, requesting payment), a deterministic validation layer must inspect the output and reject anything that would corrupt system state. This is the central safety invariant of the system: LLM → validate → act, never LLM → act.

**NFR4 — Per-session conversation isolation.** Each customer visit is a session, from seating to payment. All conversation history, cart state, order stage, and search context are scoped to that session. When payment closes the session, the next customer at the same table receives a fresh context with no memory of the previous guest. No cross-session information leakage is permitted.

**NFR5 — Graceful degradation.** The system must remain functional when individual components fail. If Ollama is unreachable, the backend and web interfaces continue operating (menu browsing, manual ordering, kitchen panel). If a robot disconnects, its tasks are requeued. If the Jetson loses WiFi, voice capture completes locally and the text payload is sent when the connection recovers.

---

### 4.1.4 Design Principles

These principles guided every architectural decision in this chapter. They are stated explicitly because they explain not just *what* was built, but *why* it was built that way.

**DP1 — Centralized brain, thin edge.** All intelligence (LLM inference, intent routing, validation, state management) runs on a single central server with a GPU. The robot's Jetson Orin Nano handles only voice input/output (microphone capture, VAD, STT, TTS) and ROS2 navigation. This split follows from hardware constraints: the LLM (Qwen2.5 7B, ~6–8 GB VRAM) requires a server-grade GPU; STT and TTS models are lightweight enough to run on the Jetson's CUDA cores. A thin edge also simplifies deployment — the Jetson runs fewer services, reducing failure modes.

**DP2 — Single-writer database.** The orchestrator backend uses SQLite with a single FastAPI process handling all writes. There is no concurrent write contention at restaurant scale (dozens of orders per hour, not thousands per second). SQLite was chosen over PostgreSQL because it requires zero administration — a single file, no server process, no configuration — which matters for a system deployed in a restaurant, not a data center. ACID transactions guarantee correctness for critical multi-step operations (seat a table, create a session, dispatch a robot — all or nothing).

**DP3 — Session-scoped memory.** Conversation memory uses LangGraph's SQLite checkpointer with `thread_id = session_id`. This design choice means: (a) each customer session is an isolated conversation thread, (b) payment closes the session and frees the thread, (c) the next customer gets a fresh thread with no context bleed. This is simpler than implementing a custom session management layer on top of a shared conversation store.

**DP4 — No fine-tuning; all adaptation via prompting.** The system uses off-the-shelf models (Qwen2.5 7B Instruct, AITeamVN/Vietnamese_Embedding, faster-whisper with PhoWhisper weights) without any fine-tuning. All domain adaptation — Vietnamese restaurant vocabulary, menu knowledge, ordering workflow, hospitality tone — is achieved through prompt engineering: system prompts (7 files), few-shot examples (14+ for the router), skill documents (hospitality rules, menu grounding), and dynamic context injection (conversation history + order stage). This principle was chosen for three reasons: (a) fine-tuning requires a labeled dataset that does not exist for Vietnamese restaurant ordering, (b) prompt-based adaptation is iterable — a prompt change takes effect immediately without retraining, (c) the system can be adapted to a different restaurant by swapping menu data and prompt files, with no model retraining.

**DP5 — Event-driven real-time updates.** All live state changes (order created, table status changed, robot position updated) are pushed to clients via WebSocket, not polled. REST is used for writes and initial state loads; WebSocket for all real-time updates. This eliminates polling overhead, reduces perceived latency on the kitchen panel and customer tablet, and ensures all UIs are synchronized within ~50ms of a state change.

**DP6 — Explicit over implicit.** Every design choice that could be implicit is made explicit in the architecture. The validator is a separate node in the graph, not hidden inside a worker. The delegate escape hatch is a named tool, not a fallback behavior. The cart state machine has named stages (IDLE, DRAFTING, AWAITING_CONFIRMATION, CONFIRMED), not implicit flags. The prompt architecture is documented as a design element (§4.3.7), not scattered as implementation details. This principle serves thesis clarity and system maintainability — a future developer (or thesis committee member) can trace the system's behavior node by node in the LangGraph visualization.

---

### 4.1.5 Scope and Boundaries

This chapter covers the software system that enables the AI waiter: the conversational agent, voice pipeline, backend orchestrator, robot dispatch, web interfaces, and deployment configuration. It does not cover:

- **Robot hardware and navigation** — the physical platform, sensor integration, EKF odometry, SLAM mapping, and autonomous navigation are presented in Chapter 3.
- **Evaluation and results** — quantitative evaluation of each component is presented in Chapter 5.
- **Related work** — the literature survey and gap analysis are presented in Chapter 2.

Within the software system, the boundaries are:

- **Server-side:** Agent brain (LangGraph agent, Ollama LLM, RAG indices), orchestrator backend (FastAPI, SQLite, WebSocket hub)
- **Robot-side:** Voice pipeline (VAD, STT, TTS on Jetson), ROS2 navigation stack (covered in Chapter 3)
- **Client-side:** Three browser SPAs (customer tablet, kiosk, management panel)

The integration between these tiers is the subject of this chapter — how voice input reaches the agent, how agent decisions reach the backend, how backend events reach the UIs and robot, and how all components recover from failure.
