## 2.9 Summary: Needs → Requirements Traceability

> **Cross-refs:** §3.1 (navigation requirements), §4.1 (AI/backend requirements), §5 (validation)
> **Citations:** Final numbering assigned when all Ch.2 references are merged.

---

Chapter 2 has surveyed six domains of restaurant automation. In each domain, the literature has produced capable individual solutions — a robot that navigates, a speech model that transcribes Vietnamese, a chatbot that converses, a retrieval engine that searches, a fleet manager that dispatches, a web framework that renders interfaces. What the literature has not produced is a system where these capabilities operate as a single pipeline: the customer speaks Vietnamese, speech is transcribed, intent is classified correctly despite informal language, the AI agent takes validated actions on a backend, kitchen and customer displays update in real time, knowledge retrieval bridges sensory queries to structured menus, a robot navigates to the correct table with business-context docking, and the robot's voice binding follows physical presence across the fleet.

The six needs identified in this chapter are not independent — each depends on the others. The voice pipeline's transcription feeds the intent classifier. The classifier's output determines which agent worker activates. The agent's tool calls trigger the knowledge retrieval pipeline. The agent's order confirmation triggers the fleet dispatcher. The fleet dispatcher's task assignments drive the robot's navigation goals. The backend's WebSocket hub synchronizes all roles. The failure of any one component cascades through the pipeline. The prior work surveyed in this chapter has developed each component in isolation; the integration challenge — making them operate as one system where state flows correctly from the customer's spoken word to the robot's wheel movement — is the central gap.

---

### 2.9.1 Gap-to-Requirement Traceability

The following table maps each need identified in this chapter to the system requirements it motivates, the proposed method that addresses it, and the experiments that validate it.

| §   | Need | → Requirements | → Method | → Validated In |
| --- | ---- | -------------- | -------- | -------------- |
| 2.2 | Dynamic goal navigation — navigation targets assigned by AI agent, not pre-set, with ArUco business-context docking | §3.1 R1–R7 (navigation, docking, odometry) | §3.4 (EKF odometry), §3.5 (RTAB-Map), §3.6 (ArUco docking), §3.7 (Nav2 + dynamic goal coupling) | §5.2.1–§5.2.4 |
| 2.3 | Vietnamese voice on Jetson edge — component selection (VAD, STT, TTS) driven by restaurant deployment constraints | §4.1 NFR latency, §4.4 architecture | §4.4 (selected components: selected VAD, STT, and TTS components; threaded pipeline, barge-in) | §5.4.1–§5.4.4 |
| 2.4 | Conversational AI agent — classifier handling teencode/context/multi-intent/domain-vocab + deterministic post-generation validation | §4.1 functional requirements, §4.5.1–§4.5.7 (agent architecture) | §4.5.2 (MLP classifier), §4.5.3 (tool-calling LLM), §4.5.4 (validator), §4.5.5 (state machine) | §5.3.1–§5.3.3 |
| 2.5 | Menu knowledge retrieval — closed-loop rewrite→retrieve→rephrase for Vietnamese food domain, driven by Vietnamese-specific embeddings | §4.1 menu search requirement, §4.6 | §4.6 (query rewriting, Vietnamese-specific hybrid retrieval, result rephrasing, multi-turn dedup) | §5.3.4 |
| 2.6 | AI-driven restaurant operations — lightweight fleet dispatch with voice binding, multi-role real-time sync, session lifecycle | §4.1 concurrency/multi-role requirement, §4.7 | §4.7 (REST API, WS hub with role-based pub/sub, fleet dispatcher, session lifecycle, SQLite) | §5.5, §5.6 |
| 2.7 | Multi-role web interfaces — AI-driven Vue SPA architecture with shared TS client, role-based WS pub/sub, SSE streaming | §4.1 multi-role UI requirement, §4.8 | §4.8 (3 SPAs + shared client library + WS event catalog) | §5.6 |
| 2.8 | Edge computing platform — accelerator class satisfying general-purpose programmability, decode bandwidth, and native fp16; 8 GB unified-memory ceiling determining the edge/server split | §4.1 NFR self-hosted, §4.4.1, §4.9 | §4.4.1 (edge/server split architecture), §4.9 (deployment topology) | §5.4.4 |

---

### 2.9.2 What Prior Systems Cover vs. What This Thesis Integrates

The comparison below positions this work against the landscape surveyed in this chapter. Prior systems achieve depth in one dimension; the integration across dimensions is the contribution.

| Dimension | Existing Work | This Thesis |
|-----------|--------------|-------------|
| Navigation | ROS2 delivery robots (nav-only, fixed goals), commercial robots (closed platforms) | ROS2 + EKF odometry + RTAB-Map + ArUco docking + dynamic backend-driven goal assignment on an open TWD platform |
| Voice | Vietnamese STT (standalone, clean speech), VAD (standalone, quiet conditions), TTS (standalone, quiet listening) | Integrated VAD→STT→Agent→TTS pipeline on Jetson edge, offline-first, under restaurant noise with concurrent ROS2 processes |
| Conversational agent | Cloud chatbots (English-only, no tools), NLU pipelines (brittle to Vietnamese informality), LLM routing (slow, non-deterministic) | Self-hosted LangGraph agent: trained MLP classifier (context-aware, sub-ms, deterministic), tool-calling LLM with delegate escape, deterministic post-generation validator, cart state machine |
| Knowledge retrieval | Standard RAG (retrieve→generate, fails on sensory queries), English-only closed-loop RAG | Closed-loop: LLM query rewriting → Vietnamese hybrid retrieval (BM25 + underthesea + diacritic-aware FAISS + RRF) → LLM result rephrasing → multi-turn dedup |
| Fleet and operations | Warehouse-scale frameworks (OpenRMF), manufacturer-locked cloud platforms, single-role restaurant software | Lightweight dispatcher: nearest-idle with battery filtering, dynamic table→robot voice binding with auto-rebind, heartbeat watchdog with task requeue, business-event-driven task lifecycle |
| Web interfaces | Single-role SPA dashboards, polling-based restaurant KDS, proprietary restaurant management UIs | 3 Vue 3 SPAs sharing a common TypeScript client library with Pydantic-synced types, WebSocket role-based pub/sub, SSE agent response streaming |
| Integration | Navigation XOR chatbot — no system combines conversational AI with physical delivery | End-to-end pipeline: Vietnamese voice → intent classification → agent action → order → kitchen display → robot navigation → ArUco docking → food delivery — all driven by a single AI agent, self-hosted, no cloud dependency |

---

### 2.9.3 The Integration Gap

Each individual technology component — EKF, RTAB-Map, Nav2, ArUco, Silero VAD, Whisper via CTranslate2, Piper TTS, LangGraph, FAISS, BM25, SQLite, FastAPI, Vue 3, Vite, WebSocket — is a mature, well-documented tool with established prior work. The contribution of this thesis is not the invention of any single component. It is the integration of these components into a deployed system where each component's output feeds the next in a pipeline that spans spoken Vietnamese to robot wheel movement, with deterministic safety mechanisms at every interface between probabilistic AI and real-world state.

The six needs identified in this chapter — dynamic goal navigation, Vietnamese voice on the edge, conversational agent with validation, knowledge retrieval for sensory queries, AI-driven restaurant operations, and multi-role web interfaces — together define the system that Chapters 3 and 4 propose, and that Chapter 5 validates.
