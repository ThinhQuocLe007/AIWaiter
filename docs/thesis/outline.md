# Thesis Outline — AI Waiter Robot on a Two-Wheel Differential Drive Platform

> **Report language: English.** Structure follows HCMUTE graduation thesis convention.
> **Hardware:** Purchased TWD platform (chassis, motors, STM32, MPU6050). Contribution from ROS2 upward: sensor integration, odometry fusion, SLAM, Nav2, ArUco docking, and the complete AI/backend/web system.

---

## Table of Contents (Quick Scan)

```
1. INTRODUCTION
   1.1 Overview
   1.2 Motivation
   1.3 Objectives
   1.4 Scope
   1.5 Research Methodology
   1.6 Report Structure

2. RELATED WORK & PROBLEM ANALYSIS
   2.1 Overview: The Integrated AI Waiter Problem
   2.2 Need 1: Physical Delivery to Dynamic Goals
       2.2.1 Wheel Odometry and Sensor Fusion
       2.2.2 SLAM and Map Building
       2.2.3 Autonomous Navigation
       2.2.4 Fiducial Marker Docking
       2.2.5 Prior ROS2 Delivery Robot Research
   2.3 Need 2: Vietnamese Voice Understanding on the Edge
       2.3.1 Voice Activity Detection
       2.3.2 Speech-to-Text for Vietnamese
       2.3.3 Text-to-Speech for Vietnamese
       2.3.4 Edge Deployment Constraints
   2.4 Need 3: Informal Vietnamese Speech → Correct, Validated Actions
       2.4.1 Prior Restaurant Dialogue Systems
       2.4.2 Architectures for Controlling LLMs
       2.4.3 Challenges Any Restaurant Agent Must Solve
           (a) Intent Classification
           (b) Post-Generation Validation
   2.5 Need 4: Bridging Vietnamese Food Descriptions to Menu Knowledge
       2.5.1 The Knowledge Problem and Standard RAG
       2.5.2 Retrieval Approaches and Their Limitations
       2.5.3 Beyond Retrieval — The Closed-Loop Pipeline
   2.6 Need 5: Coordinating AI Decisions with Restaurant Operations
       2.6.1 Multi-Robot Task Assignment
       2.6.2 Dynamic Robot-Table Voice Binding
       2.6.3 Telemetry, Liveness, and Fault Recovery
       2.6.4 Real-Time Restaurant State Synchronization
   2.7 Need 6: Multi-Role Web Interfaces for AI-Driven Restaurant Operations
       2.7.1 Single-Page Application Frameworks — Comparison
       2.7.2 Component Libraries and Build Tools
       2.7.3 Real-Time Communication Patterns
       2.7.4 Multi-Role SPA Architecture
   2.8 Summary: Needs → Requirements Traceability

3. PROPOSED METHOD (I) — ROBOT CONTROL AND NAVIGATION
   3.1 System Requirements
   3.2 Design Challenges (C1–C4)
   3.3 Robot Platform & Hardware Setup
   3.4 Wheel Odometry and EKF Sensor Fusion          → C1
   3.5 Map Building with RTAB-Map                     → C3
   3.6 Localization and ArUco-Based Docking            → C2
   3.7 Autonomous Navigation & Dynamic Goal Assignment → C4

4. PROPOSED METHOD (II) — AI, BACKEND & WEB SYSTEM
   4.1 System Requirements & Design Rationale
   4.2 Design Challenges (C5–C10)
   4.3 Overall Software Architecture
   4.4 Edge Voice Pipeline                → Need 2, C6
   4.5 Conversational Agent               → Need 3, C5, C7
       4.5.1 Execution Model (LangGraph StateGraph)
       4.5.2 Stage I — Intent Classification (MLP)
       4.5.3 Stage II — Tool-Calling LLM
       4.5.4 Stage III — Deterministic Validator
       4.5.5 Stage IV — Tools & State Management
       4.5.6 Stage V — Response Generation
       4.5.7 Prompt Architecture
   4.6 Knowledge Retrieval Pipeline       → Need 4, C8
       4.6.1 Query Rewriting
       4.6.2 Hybrid Retrieval
       4.6.3 Result Rephrasing
       4.6.4 Multi-Turn Search Context
   4.7 Backend Orchestrator               → Need 5, C9, C10
       4.7.1 REST API
       4.7.2 WebSocket Hub
       4.7.3 Session Lifecycle
       4.7.4 Fleet Management
       4.7.5 Database Schema
4.8 Web Interfaces                     → Need 6
4.9 Deployment Topology

5. EXPERIMENTS AND RESULTS
   5.1 Evaluation Methodology
   5.2 ROS2 Navigation Experiments        → Need 1
   5.3 AI Agent Experiments               → Need 3, Need 4
   5.4 Voice Pipeline Experiments         → Need 2
   5.5 System Integration Tests           → Need 5
   5.6 Web System Experiments
   5.7 Results Summary & Gap-to-Validation Traceability

6. CONCLUSION AND FUTURE WORKS
   6.1 Conclusion
   6.2 Limitations
   6.3 Future Works

Appendices
Front Matter
```

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
- **Intent router accuracy ≥ 90%** (achieved 97.44% on holdout, 95.6% on 45-case eval)
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

## CHAPTER 2: RELATED WORK & PROBLEM ANALYSIS

> **Principle:** This chapter is organized around five unsolved needs — real problems the literature has not fully addressed. Each section does three things: (1) states the need and why it matters, (2) surveys prior work that has attempted to meet it, (3) analyzes why those attempts fell short, yielding a specific gap. No implementation details or design decisions appear here. The final summary (§2.7) maps each gap to the system requirements it motivates in Chapter 3 (navigation) and Chapter 4 (AI/backend/web), which are validated in Chapter 5.

---

### 2.1 Overview: The Integrated AI Waiter Problem

- **The landscape:** service robots have been deployed commercially (Bear Servi, Pudu Bellabot, Keenon T-series, Alibaba Robot.He — §2.1.1 in detailed write-up). Conversational AI has advanced rapidly through large language models and voice interfaces (Wendy's FreshAI, Domino's AI, Vietnamese chatbots from Zalo/VinAI). These two fields have developed independently: commercial robots deliver food but are closed appliances with no conversational ability; conversational systems converse but do not act on the physical world.
- **The integration gap at a high level:** no existing system combines Vietnamese voice understanding, AI-driven action (ordering, payment, recommendation), and physical robot delivery into a single operational system. The individual components exist; what does not exist is their integration into a deployable system where the AI agent directly drives restaurant operations and robot behavior.
- **Five specific needs the field has not satisfied:**
  1. **Dynamic goal navigation** — a robot must navigate to the right table at the right time, with navigation goals assigned by an external AI agent based on live restaurant events, not pre-set waypoints (§2.2)
  2. **Vietnamese voice on the edge** — Vietnamese speech recognition, synthesis, and voice activity detection must operate reliably on edge hardware co-located with robot control, under real restaurant acoustic conditions (§2.3)
  3. **Informal speech → correct action** — a conversational agent must convert informal, teencode-heavy Vietnamese utterances into deterministic, validated tool calls that affect restaurant state, without hallucinating dish names or violating the order process (§2.4)
  4. **Vague descriptions → relevant items** — customers describe food by sensory experience ("món gì ấm bụng?", "ăn cay"), which shares zero lexical overlap with structured menu entries; retrieval must bridge this semantic gap, including rewriting queries before search and rephrasing results after (§2.5)
  5. **AI decisions → synchronized operations** — multiple client roles (customer tablet, kitchen display, manager dashboard, robot fleet) must share a single real-time view of restaurant state, all driven by an AI agent's business events, without cloud dependency (§2.6)
  6. **Multi-role web interfaces driven by AI events** — restaurant operations require distinct interfaces for each role (customer, kitchen, manager, kiosk) sharing a common real-time data layer; existing SPA frameworks, component libraries, and real-time communication patterns must be evaluated for this multi-role, AI-driven context (§2.7)

---

### 2.2 Need 1: Physical Delivery to Dynamic Goals

> *A robot must navigate from kitchen to table when ordered food is ready — but "which table" is not known until the AI agent decides. This section surveys how prior work handles robot navigation and goal assignment, and identifies the gap when goals are driven by external, AI-generated restaurant events.*

#### 2.2.1 Wheel Odometry and Sensor Fusion

- **Wheel odometry:** encoder-based dead reckoning for differential-drive platforms. The fundamental challenge: drift accumulates unbounded over distance — a robot that travels 10 meters relying on encoders alone accumulates significant pose error.
- **IMU:** gyroscope provides angular rate; accelerometer provides linear acceleration. Consumer-grade IMUs (MPU6050) introduce gyro bias and drift.
- **Sensor fusion via EKF:** combining encoder + IMU produces better estimates than either alone. `robot_localization` as a configurable EKF implementation with state vector `[x, y, ψ, V_x, V_y, V_ω]`.
- **Related work:** Thrun, Burgard & Fox (2005) on probabilistic robotics; Moore & Stouch (2014) on `robot_localization` for low-cost platforms; prior university projects using EKF on differential-drive platforms.
- **→ Gap:** Prior work has validated EKF fusion on consumer-grade sensors in lab environments. No prior work has validated EKF-fused odometry on a purchased TWD chassis with MPU6050 IMU under restaurant service-lane conditions (short straight segments, 90° turns, repeated in-place rotations at tables), where cumulative drift across multiple kitchen→table→kitchen cycles must remain bounded for ArUco re-detection at the docking zone.

#### 2.2.2 SLAM and Map Building

- **LiDAR-based SLAM:** 2D laser scans → occupancy grid via scan matching (ICP).
- **Visual SLAM:** RGB-D cameras for loop closure via visual feature matching — complements LiDAR geometry.
- **RTAB-Map:** graph-based SLAM fusing LiDAR + RGB-D. Memory management via working memory / long-term memory. Loop closure detection and global graph optimization. Labbé & Michaud (2019).
- **Prior work on restaurant mapping:** ROS2 delivery robots (campus cafeterias, hospital wards) typically use Cartographer or RTAB-Map in controlled indoor environments. These maps serve static navigation — the robot knows the floor plan but has no semantic understanding of "table 3 is occupied, table 5 is being cleaned."
- **→ Gap:** Prior work builds maps for navigation. No prior work has built a restaurant map that a separate backend system can query — "where is table 3?", "what is the waypoint pose for table 3?", "is there a charging dock to send the robot to when idle?" The map exists as a SLAM artifact; it is not exposed as navigation infrastructure to an external AI system.

#### 2.2.3 Autonomous Navigation

- **Nav2 stack:** global planner (path on static costmap), local controller (trajectory following with dynamic obstacle avoidance), behavior trees for recovery.
- **Non-holonomic TWD constraints:** no lateral motion; in-place rotation for heading correction.
- **DWB local planner:** sampling velocity commands, scoring by goal progress + obstacle clearance.
- **Prior work on ROS2 delivery navigation:** university projects demonstrate Nav2 for food/medication delivery. The pattern is universal: a pre-set waypoint → Nav2 drives there → arrival acknowledged. The waypoint is chosen by a human operator or a hard-coded sequence.
- **→ Gap:** The navigation stack can drive to a waypoint. What does not exist is a coupling mechanism where navigation goals are *dynamically assigned by an external AI agent based on live restaurant events*. An order finishes cooking → the backend dispatcher selects table_id → looks up table waypoint → sends goal to Nav2. The path planning is mature; the goal assignment driven by non-navigation business logic is the unsolved integration point.

#### 2.2.4 Fiducial Marker Docking

- **ArUco markers:** binary square fiducial markers, each with a unique ID. PnP pose estimation for 6-DoF camera-to-marker transform.
- **Why ArUco for docking:** SLAM localization alone is insufficient for the final 10–20 cm approach — residual map error and odometry drift accumulate. A marker at the target table provides an absolute local reference independent of SLAM.
- **Prior work:** ArUco-based docking has been demonstrated on ROS2 robots for charging stations and delivery drop-off points. Each marker is treated as an independent navigation target.
- **→ Gap:** Prior work treats each marker as a standalone waypoint. No prior system binds markers to *business entities* — marker ID 5 is not just "a docking pose" but "table B3, currently occupied by session S42, which has an active order #O128." The marker's identity must be resolvable by the backend so the system can confirm: "the robot is at table B3, and the food on its tray belongs to order #O128 at table B3." Docking precision is evaluated; business-context docking is not.

#### 2.2.5 Prior ROS2 Delivery Robot Research — The Interaction Gap

- **Survey of academic ROS2 delivery robots:** campus cafeteria food delivery, hospital medication delivery, office document delivery. Common hardware: 2D LiDAR + RGB-D + IMU + encoders. Common software: RTAB-Map/Cartographer → Nav2 → ArUco docking.
- **What they achieve:** physical navigation from origin to destination. Success rates > 90% in controlled environments.
- **What they lack:** every system surveyed handles movement only. The robot drives to a table and stops. There is no conversational interaction — the robot cannot take orders, answer menu questions, confirm selections, or process payment. The navigation problem is solved; the interaction problem is unaddressed.
- **→ Overall gap for §2.2:** The field can build a robot that navigates to a fixed point. The field does not have a robot whose navigation goals are dynamically assigned by an AI agent managing live restaurant state, whose arrival at a table triggers an ArUco-verified business-context confirmation, and whose odometry survives repeated service cycles. These gaps motivate the system requirements for autonomous navigation in §3.1.

---

### 2.3 Need 2: Vietnamese Voice Understanding on the Edge

> *Vietnamese speech recognition, voice activity detection, and speech synthesis exist as standalone research areas. This section surveys each component and identifies the gap: no prior work has evaluated an integrated Vietnamese voice pipeline under combined restaurant acoustic conditions and edge hardware constraints, where STT/VAD/TTS must co-reside with robot control processes.*

#### 2.3.1 Voice Activity Detection

- **The utterance boundary problem:** determining when speech starts and stops in a continuous audio stream. Critical for natural turn-taking.
- **Energy threshold baseline:** RMS amplitude threshold. Fails in restaurant environments where ambient noise (60–70 dB) exceeds speech amplitude thresholds.
- **Neural VAD:** Silero VAD (~1.5 MB, language-agnostic, CPU real-time) as the dominant open-source option. WebRTC VAD (Gaussian Mixture Model, less accurate in noise). Deep VAD (pyannote, NeMo) — higher accuracy but GPU-inference, unsuitable for always-on edge.
- **Prior work:** Silero VAD evaluated on multilingual benchmarks in quiet conditions. WebRTC VAD tested on telephony speech.
- **→ Gap:** VAD accuracy has been evaluated on clean speech corpora. No prior work has evaluated VAD under restaurant acoustic conditions — concurrent conversations, plate clatter, chair movement — where the configurable sensitivity threshold must balance false triggers (noise classified as speech) against missed utterances (speech classified as silence). The threshold calibrated in a quiet lab produces excessive false triggers in a dining room.

#### 2.3.2 Speech-to-Text for Vietnamese

- **Vietnamese-specific challenges for STT:**
  - 6 tones carried by diacritics — a tone error changes word meaning entirely.
  - Monosyllabic structure with compound words — "bún bò Huế" is 3 syllables but 1 lexical unit.
  - Teencode and informal speech: "ad" (anh/chị), "ck" (chuyển khoản), "z" (vậy), "nhiêu" (bao nhiêu), "hông" (không). Absent from formal STT training corpora.
  - Restaurant ambient noise degrades WER.
  - STT is the break-point of the entire voice pipeline — if transcription is wrong, every downstream component (classifier, agent, order creation, payment) operates on corrupted input.

- **Available STT approaches:**

  | Model / Service | Vietnamese | Edge Deployable | Offline | Latency (3s utterance) | VRAM | WER on VN (est.) |
  |-----------------|:---:|:---:|:---:|:---:|:---:|:---:|
  | Whisper tiny/base | Partial (multilingual) | Yes | Yes | ~200–400ms | ~0.5–1 GB | 20–30% |
  | Whisper medium | Partial (multilingual) | Yes | Yes | ~800ms | ~1.5 GB | 15–20% |
  | Whisper large-v3 | Partial (multilingual) | Borderline | Yes | ~1.5s | ~3 GB | 10–15% |
  | PhoWhisper (Whisper fine-tuned on VN) | **Yes** | Yes (via faster-whisper) | Yes | ~800ms | ~1.5 GB | 10–15% |
  | Google Cloud Speech-to-Text | **Yes** | No | No | ~200ms + network | 0 (cloud) | 5–8% |
  | Viettel AI STT | **Yes** | No | No | ~200ms + network | 0 (cloud) | 5–8% |
  | FPT.AI STT | **Yes** | No | No | ~200ms + network | 0 (cloud) | 5–8% |

  The fundamental trade-off: cloud services provide the lowest WER but require internet — unacceptable on a restaurant floor. On-device models (Whisper, PhoWhisper) are less accurate but operate offline. faster-whisper (CTranslate2-optimized, 8-bit quantization) reduces Whisper-family latency by ~4×.

- **Prior work:** PhoWhisper evaluated on Vietnamese speech benchmarks with WER improvements of 5–10% over base Whisper, particularly on tonal accuracy. Evaluations are on clean speech datasets in quiet environments with formal Vietnamese.
- **→ Gap:** No prior work has evaluated Vietnamese STT in restaurant acoustic conditions — ambient noise at 60–70 dB, informal speech patterns, teencode, compound dish names — where the STT model's tendency to produce phonetically similar but semantically wrong transcriptions (e.g., "Ốt Hương" for "Ốc Hương") directly corrupts downstream agent behavior.

#### 2.3.3 Text-to-Speech for Vietnamese

- **Available TTS approaches:**

  | Engine | Offline | Edge Deployable | Latency (per sent.) | VRAM | Naturalness | Vietnamese Voices |
  |--------|:---:|:---:|:---:|:---:|:---:|:---:|
  | Piper TTS (VITS architecture) | **Yes** | **Yes (CPU)** | ~500ms | ~200 MB | Moderate | 1 community-trained voice |
  | edge-tts (Microsoft Azure) | No | No (cloud) | ~300ms + network | 0 (cloud) | High | Multiple neural voices |
  | Google Cloud TTS | No | No (cloud) | ~200ms + network | 0 (cloud) | Very High | WaveNet voices |

  The trade-off mirrors STT: cloud services offer higher naturalness but require internet. Piper TTS is the only offline, edge-deployable Vietnamese option.

- **Prior work:** Piper TTS evaluated on perceptual quality ratings for Vietnamese. Evaluation is on isolated sentences in quiet playback conditions.
- **→ Gap:** TTS naturalness has been evaluated in quiet listening environments. No prior work has evaluated whether a moderate-quality TTS voice is adequate for short functional restaurant utterances — where the content (correct dish names, prices, order summaries) matters more than vocal performance — or how customers perceive a non-human Vietnamese voice in a service context. The barge-in interaction (customer interrupts TTS mid-sentence to correct an order) has also not been studied for Vietnamese restaurant scenarios.

#### 2.3.4 Edge Deployment Constraints

- **Jetson Orin Nano:** 1024-core Ampere GPU, 6-core ARM CPU, 8 GB LPDDR5 shared memory, 7–15 W power envelope.
- **VRAM budget:** ROS2 navigation (~500 MB) + sensor drivers (~200 MB) + Silero VAD (<10 MB) + medium STT model (~1.5 GB) + Piper TTS (~200 MB) ≈ 2.5 GB. Remaining ~5.5 GB for OS, ROS2 data, overhead. Adequate for the voice pipeline. A 7B-parameter LLM requires 6–8 GB alone — cannot co-reside.
- **Prior work on edge/server split:** distributed robotics architectures (cloud robotics, edge AI) establish the pattern of splitting compute between edge and server. Evaluated for English-language systems, not Vietnamese.
- **→ Overall gap for §2.3:** The individual voice components exist. What does not exist is (a) evaluation of Vietnamese STT/VAD/TTS under combined restaurant acoustic conditions and Jetson edge hardware constraints, (b) an integrated pipeline where VAD→STT→Agent→TTS operates as a single threaded system with barge-in, and (c) a quantified VRAM budget analysis confirming that the pipeline co-resides with ROS2 robot control. These gaps motivate the voice pipeline architecture in §4.4.

---

### 2.4 Need 3: From Informal Vietnamese Speech to Correct, Validated Actions

> *Vietnamese restaurant speech is informal, teencode-heavy, and context-dependent. An agent must understand it, decide on an action, and execute that action correctly — without hallucinating dish names or violating the order process. This section surveys prior approaches to building conversational agents and identifies why each fails to satisfy all three requirements simultaneously for Vietnamese.*

#### 2.4.1 Prior Restaurant Dialogue Systems — The Chatbot Ceiling

- **Traditional NLU pipelines (Rasa, Dialogflow):** intent classification + slot filling → API call. Deployed for English, Chinese, Korean, Japanese restaurant ordering. Limitation: trained on formal corpora — Vietnamese informal variants ("ck", "z", "ad") are out-of-vocabulary. Slots handle fixed schemas but cannot represent open-ended queries ("món gì ấm bụng?").
- **LLM-based chatbots (Zalo AI, VinAI):** understand Vietnamese conversationally, can answer menu questions. Limitation: dialogue ≠ transaction. The chatbot produces text; it cannot add to cart, create orders, or dispatch robots. The gap is architectural, not linguistic.
- **Voice ordering (Wendy's FreshAI, Domino's AI):** LLM-based voice ordering integrated with POS. Limitation: English-only, cloud-dependent, stateless per transaction, no physical robot delivery.
- **Physical delivery robots (§2.1):** deliver food but have no conversational AI.
- **Comparison table:**

  | System | Vietnamese | Tool Execution | Validation | Self-Hosted | Robot Dispatch |
  |--------|:---:|:---:|:---:|:---:|:---:|
  | Traditional NLU pipeline (Rasa, Dialogflow) | ✗ (needs VN retraining) | ✓ | ✗ | ✓ | ✗ |
  | LLM chatbot (Zalo AI, VinAI) | ✓ | ✗ | ✗ | ✗ | ✗ |
  | Voice ordering (Wendy's, Domino's) | ✗ | ✓ | ✗ | ✗ | ✗ |
  | Physical delivery robots (§2.1) | ✗ | ✗ | ✗ | ✗ | ✓ |

  No prior system checks more than two of the five dimensions.

- **→ Gap:** No system combines Vietnamese language understanding, tool execution against a backend, deterministic validation of LLM outputs, self-hosted deployment, and physical robot delivery. This is the high-level gap. The following subsections decompose it into specific technical challenges.

#### 2.4.2 Architectures for Controlling LLMs

- **Tool calling (function calling):** the shared mechanism across all architectures — the LLM outputs a structured invocation (tool name + typed arguments) instead of free text. Introduced by OpenAI, adopted by Anthropic, Ollama, LangChain. Tool calling provides the *mechanism* for action; the *architecture* governs how that mechanism is controlled.
- **Chain-based (LangChain LCEL):** fixed linear DAG. Deterministic. No branching or recovery — incorrect routing at step 1 is unrecoverable.
- **Autonomous reasoning loop (ReAct, AutoGPT):** LLM decides when to call tools and when to stop. Termination is emergent — no guarantee the loop ends. Business process enforcement (confirm after cart built, not before) is impossible because the LLM selects tool order.
- **Graph-based (LangGraph):** declared state graph — typed nodes + conditional edges. Entry/exit are defined (termination is structural). Deterministic code between LLM nodes enables validation, circuit breaker, and state-machine enforcement.
- **→ Gap:** No architecture inherently enforces the combination a restaurant agent requires — guaranteed bounded execution, deterministic validation between every LLM call and tool execution, and explicit state-machine enforcement of the ordering process. Tool calling provides the mechanism; the architecture must provide the governance. This gap motivates the graph-based agent design in §4.5.1.

#### 2.4.3 Challenges Any Restaurant Agent Must Solve

##### (a) Intent Classification in Informal Vietnamese Restaurant Speech

- **The problem:** before executing any tool, the agent must determine what the customer wants. A 4-class decision: {ORDER, SEARCH, PAYMENT, CHAT}. Vietnamese restaurant speech introduces four domain-specific challenges:
  - **(i) Teencode and informal Vietnamese:** "ck" (chuyển khoản), "z" (vậy), "ad" (anh/chị), "nhiêu" (bao nhiêu), "hông" (không) — absent from formal training corpora.
  - **(ii) Context-dependent ambiguity:** "ok em" at order confirmation → ORDER; "ok em" at greeting → CHAT. Utterance text alone carries zero signal.
  - **(iii) Multi-intent compounding:** "Cho 2 Ốc Hương rồi tính tiền luôn" = ORDER + PAYMENT. Single-label classifiers force one choice.
  - **(iv) Domain vocabulary:** dish names ("Ốc Hương Xốt Trứng Muối") are out-of-distribution for general-domain embedding models.

- **Prior classification approaches:**

  | Approach | Handles Teencode? | Context-Aware? | Multi-Intent? | Domain Vocab? | Latency |
  |----------|:---:|:---:|:---:|:---:|:---:|
  | Traditional NLU (Rasa, SVM) | ✗ | ✗ | ✗ | ✗ (needs retraining) | ~5ms |
  | Lightweight text classifiers (fastText, SetFit) | ✗ | ✗ | ✗ | ✗ (needs retraining) | ~2–10ms |
  | Semantic centroid routing | ✗ | ✗ | ✗ | ✗ | ~15ms |
  | LLM-based routing (few-shot) | ✓ | ✓ | ✓ | ✓ (via prompt) | ~1.8s |
  | Trained classifier with context features (MLP) | ✓ (if in training data) | ✓ (via context features) | ✓ (can be trained) | ✓ (if in training data) | ~0.17ms |

  Each prior approach fails on at least two challenges. The fundamental trade-off: LLM routing is general enough to handle all four but is slow (~1.8s) and non-deterministic. ML classifiers are fast and deterministic but brittle — they operate on text alone, blind to conversation state.

- **→ Gap:** No classification approach for Vietnamese restaurant speech simultaneously handles teencode, context-dependent utterances, multi-intent compounding, and domain vocabulary while maintaining sub-millisecond latency and deterministic output. This gap motivates the trained MLP classifier with context features in §4.5.2.

##### (b) Post-Generation Validation — Preventing Hallucinated Tool Calls

- **The hallucination problem:** even with correct intent and correct worker, the LLM generating tool call arguments may fabricate dish names ("Pizza Hải Sản"), produce absurd quantities (999), or attempt invalid state transitions (confirm empty cart). Hallucination is inherent to probabilistic text generation.
- **Restaurant stakes:** in a chatbot, hallucination is a UX annoyance. In a transactional agent, a hallucinated `add_cart` or `confirm_order` means wrong food cooked, wrong payment charged — measured in money and trust.
- **Existing mitigations:**
  - **Constrained decoding:** enforces valid JSON schema but cannot validate semantic correctness — `{"name": "Pizza Hải Sản"}` is valid JSON.
  - **RAG:** reduces hallucination probability but does not eliminate it — the LLM may ignore retrieved context.
  - **Human-in-the-loop:** eliminates risk but defeats autonomous operation.
  - All are generation-time strategies — they constrain what the LLM can output. None validates *after* generation against an external source of truth.
- **→ Gap:** No prior restaurant agent implements a deterministic post-generation validation layer that checks every LLM tool call argument against known-good data (menu items, price ranges, valid state transitions) *before* the call reaches external systems. This gap motivates the deterministic validator in §4.5.4.

#### → Overall Gap for §2.4

No prior system combines Vietnamese language support, an agent architecture enforcing bounded execution with deterministic inter-LLM validation, intent classification handling all four Vietnamese-specific challenges at sub-ms latency, and post-generation hallucination safety — all self-hosted. This gap motivates the full agent architecture in §4.5.

---

### 2.5 Need 4: Bridging Vietnamese Food Descriptions to Menu Knowledge

> *Customers describe what they want in sensory terms: "món gì ấm bụng cho ngày lạnh?" (what's warm and filling for a cold day?). Restaurant menus are structured by name, category, and price — not by the feeling a dish produces. Retrieval-augmented generation (RAG) is the standard technique for grounding LLMs in documents, but standard RAG fails when user queries share no lexical overlap with the target documents. This section surveys RAG approaches and identifies the gap: a closed-loop pipeline where the LLM actively rewrites the query before retrieval and rephrases the results after — both grounded in Vietnamese food-domain knowledge.*

#### 2.5.1 The Knowledge Problem and Standard RAG

- **Why LLMs need external knowledge:** training data is frozen, a specific restaurant's menu is not in it. Without retrieval, the LLM confidently describes dishes that do not exist.
- **Standard RAG pipeline:** embed documents offline → retrieve top-k at query time → generate answer grounded in retrieved context.
- **The standard RAG assumption:** the user's query maps directly to relevant documents. True for "Ốc Hương giá bao nhiêu?" (Ȩc Hương appears in menu). False for "món gì ấm bụng?" (zero keyword overlap with any dish).

#### 2.5.2 Retrieval Approaches and Their Limitations

- **Dense retrieval (FAISS + SentenceTransformer):** captures semantic similarity. Weak on exact keyword matching for proper names and rare dish names.
- **Sparse retrieval (BM25):** strong for exact keyword matches. Weak for semantic understanding and vague descriptions.
- **Hybrid fusion (RRF):** parallel dense + sparse → merge via Reciprocal Rank Fusion. RRF combines rankings without requiring comparable scores.
- **Vietnamese-specific requirements:** word segmentation via `underthesea` — compound words ("bún bò Huế") must be single tokens for BM25. Embedding model must handle Vietnamese diacritics natively (general-domain multilingual models degrade on tonal languages).
- **Prior work:** RAG applied to restaurant menus exists for English — retrieve relevant dishes, generate recommendation. The retrieve→generate pipeline assumes queries contain menu vocabulary. Vietnamese food-domain RAG has not been evaluated.
- **→ Gap (standard RAG):** standard RAG fails when Vietnamese customers use sensory language. The retrieval problem is fundamentally one of **query-document mismatch** — not indexing quality.

#### 2.5.3 Beyond Retrieval — The Closed-Loop Pipeline

- **Pre-retrieval: query rewriting.** Before retrieval, an LLM rewrites the customer's vague utterance into concrete search terms. "Món gì ấm bụng cho ngày lạnh?" → "cháo, lẩu, súp, món nước nóng". This is not keyword extraction — the LLM reasons about Vietnamese culinary categories. Prior work on query rewriting for RAG exists for English; Vietnamese food-domain rewriting has not been studied.
- **Post-retrieval: result rephrasing.** After retrieval returns top-k dishes, an LLM evaluates which results match the original customer intent, selects the best, and rephrases them in natural Vietnamese. The LLM also detects empty results and responds appropriately ("Dạ, quán không có món đó ạ") rather than hallucinating. Prior work on LLM-as-evaluator for RAG exists; Vietnamese restaurant application does not.
- **Multi-turn deduplication:** when a customer searches for "Ốc Hương" twice, the agent should recall it already returned those results. Requires search context persisting across turns — outside the standard stateless RAG pipeline.
- **Prior work on closed-loop RAG:** self-reflective RAG, CRAG, Self-RAG propose LLM evaluation of retrieved documents. None has been applied to Vietnamese food-domain search where the bridge between sensory query and structured menu requires cultural knowledge of what constitutes "ấm bụng" in Vietnamese cuisine.
- **→ Overall gap for §2.5:** No prior system combines (a) LLM-based query rewriting for Vietnamese food-domain vocabulary, (b) Vietnamese-specific hybrid retrieval with word-segmented BM25 and diacritic-aware embeddings, (c) LLM-based post-retrieval rephrasing that selects relevant items and detects empty results, and (d) multi-turn search context deduplication — forming a closed-loop rewrite→retrieve→rephrase pipeline. This gap motivates the knowledge retrieval tool in §4.6.

---

### 2.6 Need 5: Coordinating AI Decisions with Restaurant Operations

> *A restaurant operator needs: a customer tablet for ordering, a kitchen display for cooking, a manager dashboard for oversight, and a robot fleet for delivery — all seeing the same real-time state. An AI agent must drive this state through API calls, triggering robot navigation, kitchen display updates, and session lifecycle transitions. This section surveys existing systems for fleet management, restaurant operations, and real-time web infrastructure, and identifies the gap: no lightweight, self-contained system integrates all roles under a single AI-driven real-time state.*

#### 2.6.1 Multi-Robot Task Assignment

- **Nearest-idle assignment:** assign task to the closest available robot. Simplest approach, works for short trips (3–5m kitchen→table).
- **Auction-based and market-based:** robots bid on tasks based on state (battery, distance, queue). Prior work in warehouse AGV fleets (Amazon Kiva, Cainiao) where trips are 50–200m.
- **Battery-aware filtering:** robots below charge threshold excluded from candidate pool.
- **Prior fleet frameworks:** ROS2 OpenRMF (warehouse-scale, heavy deployment); Bear Universe/PuduCloud/Keenon Cloud (proprietary, manufacturer-locked).
- **→ Gap:** Warehouse frameworks are disproportionate to restaurant scale (6 tables, 3–5 robots). Manufacturer portals are closed. Neither integrates with an external AI agent that triggers tasks based on live restaurant events (seating → dispatch, order ready → dispatch, payment → release). The open problem is lightweight multi-robot coordination where the task source is the AI agent, not a pre-computed schedule.

#### 2.6.2 Dynamic Robot-Table Voice Binding

- **The voice binding problem:** robots are table-agnostic — any robot can serve any table. When a customer presses "Talk to AI" on their tablet, the system must know which robot's microphone to activate. The binding must be dynamic — established on arrival, released on departure.
- **Prior approaches:** static binding (inflexible), broadcast-to-all (privacy concern), dynamic binding (standard pattern but not demonstrated for restaurant voice scenarios).
- **→ Gap:** No prior restaurant fleet system implements dynamic table→robot→microphone binding where the binding is established on physical robot arrival and released on departure, routing both voice capture commands and voice reply playback to the correct robot's speaker.

#### 2.6.3 Telemetry, Liveness, and Fault Recovery

- **Telemetry:** RAM-only latest-value store for pose + battery (lock-free reads at 4+ Hz) vs. DB write-per-heartbeat (write contention). Hybrid approach: RAM for real-time, periodic DB snapshot (every 15s) for cold-start recovery.
- **Liveness monitoring:** heartbeat watchdog — a hung process can maintain an open socket while producing no heartbeats. Standard pattern in robotics telemetry.
- **Fault recovery:** offline robot → tasks requeued to PENDING, zombie connection closed, voice binding released. Prior work on fault-tolerant multi-robot task reassignment.
- **→ Gap:** These patterns are known individually. No prior restaurant system composes them into a single lightweight dispatcher that simultaneously handles task assignment, voice binding, and fault recovery — all driven by restaurant business events rather than warehouse logistics.

#### 2.6.4 Real-Time Restaurant State Synchronization

- **Restaurant management evolution:** traditional POS → KDS → QR-code menus. Each system serves one role with polling-based refresh (5–10s poll cycles). A new order appears on the kitchen display when the next poll hits, not when the order is created.
- **WebSocket push vs. polling:** push delivers events as they occur. Role-based pub/sub routes events to the correct clients.
- **Multi-role architecture:** 4+ client types (customer tablet, kitchen panel, manager dashboard, robot) sharing one real-time state. Each role subscribes to a different event subset — kitchen needs `order.created`; robot needs `task.assign`; tablet needs `voice.reply`.
- **Session lifecycle:** a restaurant-specific business process (check-in → order → pay → release table) enforced as guarded state transitions, not just CRUD. Prior POS systems implement this as proprietary closed logic; no open API for external AI to drive.
- **Prior work:** REST APIs for ordering exist. WebSocket hubs for real-time dashboards exist. Multi-role SPAs exist. The individual technologies are mature.
- **→ Overall gap for §2.6:** No prior system integrates (a) lightweight multi-robot task assignment driven by AI agent events, (b) dynamic robot-table voice binding, (c) heartbeat-based liveness monitoring with automatic fault recovery, (d) role-based WebSocket state synchronization across 4+ client types, and (e) a session lifecycle state machine enforced by the backend — all in a self-contained single-server deployment with no cloud dependency. The components exist individually; their composition into a single system where an AI agent is the primary driver of all business events is the integration gap. This motivates the backend orchestrator architecture in §4.7 and fleet dispatcher in §4.7.

---

### 2.7 Need 6: Multi-Role Web Interfaces for AI-Driven Restaurant Operations

> *Restaurant automation requires distinct user interfaces for each operational role — customer ordering, kitchen order management, guest check-in, and fleet monitoring — all sharing a single source of real-time truth driven by AI agent events. This section surveys single-page application frameworks, component libraries, build tools, and real-time communication patterns, and identifies the gap: no prior restaurant system provides a multi-role SPA architecture where the AI agent is the primary driver of UI state across all roles.*

#### 2.7.1 Single-Page Application Frameworks — Comparison

- **The SPA model for restaurant interfaces:** a single HTML page with client-side routing. Reactive component trees update in-place as data changes — no full-page reloads. This is the standard modern pattern for real-time dashboards, interactive ordering systems, and operational panels.
- **Vue 3 (Composition API + TypeScript):** reactive data binding via `ref()` and `reactive()`. Pinia for cross-component state management. Vue Router for client-side navigation. First-class TypeScript support. Small runtime (~33 KB gzipped). Vietnamese-character rendering via Unicode standard support — no additional configuration needed. Ecosystem: Vite (build), PrimeVue (component library), Tabler Icons (icon set).
- **React (hooks + JSX):** the dominant SPA framework by market share. Virtual DOM reconciliation. State management via Context API, Redux, or Zustand. Larger ecosystem (Next.js, Material UI, Ant Design). Trade-off: JSX mixes markup and logic in a way that can obscure the separation of concerns in complex multi-form interfaces; the learning curve for reactive state patterns (useEffect dependencies, stale closures) is higher than Vue's explicit reactivity.
- **Angular (TypeScript + RxJS):** opinionated full framework with dependency injection, RxJS observables for async state, and a module-based architecture. Strongly typed, well-suited to enterprise teams. Trade-off: significantly heavier runtime, steep learning curve, verbose boilerplate for simple components — disproportionate overhead for restaurant interfaces where the business logic lives on the backend server, not in the browser.
- **Comparison summary table (Vue 3 vs. React vs. Angular):** dimensions — reactivity model, TypeScript support, bundle size, Vietnamese i18n readiness, developer ramp-up time, suitability for multi-role SPA architecture with shared TypeScript types.
- **Prior work:** all three frameworks have been used for restaurant ordering systems, dashboard applications, and real-time monitoring interfaces. No academic survey has compared them specifically for the multi-role, AI-driven restaurant context.
- **→ Gap for frameworks:** The framework choice for a restaurant AI system is not arbitrary — the framework must support (a) multiple role-specific SPAs sharing a common TypeScript client library with types mirroring the backend Pydantic schemas, (b) real-time UI updates driven by WebSocket events from an AI agent, and (c) reactive Vietnamese text rendering for conversation transcripts, dish names, prices, and order summaries. No prior survey establishes selection criteria for this specific multi-role, AI-driven context.

#### 2.7.2 Component Libraries and Build Tools

- **PrimeVue 4:** Vue 3-native component library with full TypeScript support. Provides data-intensive components — DataTable with sorting/filtering/pagination, Form components with validation, Card/Panel containers, Dialog/Overlay panels, Toast notifications, and Badge indicators — that map directly to restaurant UI needs: menu browsing (DataTable), order forms (Form + InputNumber), kitchen Kanban (Card layout), status badges (Badge for order states), and payment dialogs (Dialog).
- **Vuetify 3 (Material Design):** opinionated Material Design Vue component library. Strong for admin dashboards and data-heavy panels. Trade-off: Material Design's visual language is not restaurant-native — the rigid grid system and elevation-based layering constrain the kind of responsive, touch-friendly menu browsing interface that restaurant tablets require. Heavier bundle weight than PrimeVue.
- **Ant Design Vue:** enterprise-grade component library with comprehensive form and table components. Well-suited to data management interfaces (kitchen panel, fleet dashboard). Trade-off: component API complexity, larger bundle size, and a visual style optimized for enterprise back-office applications rather than customer-facing restaurant interfaces.
- **Vite 8:** next-generation build tool with native ES module dev server — hot module replacement in <50ms regardless of project size. Production builds via Rollup with tree-shaking. Significantly faster than Webpack-based toolchains — relevant for a 3-app monorepo where each SPA must be built and served independently during development.
- **Webpack (via Vue CLI):** the traditional Vue build toolchain. Slower dev server startup and HMR on large projects. Vite has largely superseded Webpack in the Vue ecosystem as of 2024.
- **Prior work:** component library comparisons exist for general web development contexts. No evaluation exists for restaurant-specific UIs where the requirements are (a) Vietnamese text rendering with diacritic accuracy, (b) touch-friendly tablet interfaces with large tap targets, and (c) real-time data binding to WebSocket events from a backend orchestrator.

#### 2.7.3 Real-Time Communication Patterns for Restaurant UIs

- **Polling (REST-based refresh):** the traditional pattern in restaurant POS and KDS systems. The client sends an HTTP GET every N seconds (typically 5–10s) to check for state changes. A new order appears on the kitchen display 0–10 seconds late, averaged across poll cycles. Acceptable for a standalone KDS where a human cook looks at the screen periodically. Unacceptable for a voice-driven customer interaction where the agent's response and cart update must appear on the tablet immediately — a 5-second delay between "Cho 2 Ốc Hương" and seeing the cart update breaks the conversational flow.
- **WebSocket push:** persistent full-duplex connection. The server pushes events to clients as they occur — `order.created`, `cart.updated`, `robot.position`. Role-based fan-out routes events to the correct client subset (kitchen panel receives `order.created`; customer tablet receives `voice.reply`; robot receives `task.assign`). Auto-reconnection with exponential backoff handles WiFi instability — standard pattern for real-time web applications.
- **Server-Sent Events (SSE):** server-to-client streaming over HTTP. Lighter weight than WebSocket for server→client only traffic. Used by the agent brain to stream LLM-generated responses sentence-by-sentence to the voice pipeline and tablet. Not suitable for bidirectional communication (robot telemetry, tablet commands).
- **Prior work on real-time restaurant systems:** restaurant management platforms (Toast, Square, Lightspeed) implement real-time state propagation internally but do not expose it as a public API. Academic work on real-time multi-role web systems exists for domains outside restaurants (hospital monitoring dashboards, logistics control panels, financial trading UIs). No prior system provides a documented WebSocket event catalog for restaurant operations where the event source is an AI agent rather than a human operator.

#### 2.7.4 Multi-Role SPA Architecture

- **The multi-role SPA pattern:** instead of one monolithic application, multiple single-role SPAs — each serving one user type (guest, kitchen staff, manager) with role-specific UI and event subscriptions — sharing a common TypeScript client library for API calls, WebSocket connections, and type definitions. This is the standard pattern for systems where different user roles need different views of the same underlying data.
- **Prior work:** multi-role SPA architectures have been documented for enterprise SaaS platforms (admin vs. customer vs. agent dashboards). No prior restaurant system implements this architecture where the shared state is driven by an AI agent — the agent creates orders (→ kitchen panel updates), modifies cart state (→ tablet updates), and dispatches robots (→ fleet dashboard updates), with all roles seeing the changes in real time.
- **→ Overall gap for §2.7:** No prior restaurant system combines (a) a Vue 3-based multi-role SPA architecture with a shared TypeScript client library mirroring backend Pydantic schemas, (b) PrimeVue component selection justified by restaurant-specific UI requirements (Vietnamese text, touch-friendly interaction, data-intensive displays), (c) Vite-based build tooling for a multi-app monorepo, (d) role-based WebSocket pub/sub for real-time AI-driven state synchronization, and (e) SSE streaming for AI agent response delivery. The individual technologies — Vue 3, PrimeVue, Vite, WebSocket, SSE — are individually mature. Their composition into a multi-role, AI-driven restaurant interface architecture, and the framework selection criteria that justify that composition, has not been documented. This gap motivates the web interface architecture in §4.8.

---

### 2.8 Summary: Needs → Requirements Traceability

- **The six needs and what they demand of the proposed system:**

  | §   | Need | → Requirements | → Method | → Validated In |
  | --- | ---- | -------------- | -------- | -------------- |
  | 2.2 | Dynamic goal navigation — navigation targets assigned by AI agent, not pre-set, with ArUco business-context docking | §3.1 R1–R7 (navigation, docking, odometry) | §3.4–§3.7 (EKF, RTAB-Map, ArUco, Nav2 + dynamic goal coupling) | §5.2.1–§5.2.3 |
  | 2.3 | Vietnamese voice on Jetson edge — integrated pipeline under restaurant noise + concurrent robot processes | §4.1 NFR latency, §4.4 architecture | §4.4 (VAD→STT→Agent→TTS threaded pipeline, barge-in) | §5.3.5, §5.4.4 |
  | 2.4 | Informal speech → correct validated action — classifier handling teencode/context/multi-intent/domain-vocab + deterministic post-generation validation | §4.1 functional requirements, §4.5.1–§4.5.7 (agent architecture) | §4.5.2 (MLP classifier), §4.5.3 (tool-calling LLM), §4.5.4 (validator) | §5.3.1–§5.3.3 |
  | 2.5 | Vague descriptions → relevant items — closed-loop rewrite→retrieve→rephrase for Vietnamese food domain | §4.1 menu search requirement, §4.6 | §4.6 (query rewriting, hybrid retrieval, result rephrasing, dedup) | §5.3.4 |
  | 2.6 | AI-driven restaurant operations — lightweight fleet dispatch with voice binding, multi-role real-time sync, session lifecycle | §4.1 concurrency/multi-role requirement, §4.7 | §4.7 (REST + WS hub, fleet dispatcher, session lifecycle) | §5.5, §5.6 |
  | 2.7 | Multi-role web interfaces — no AI-driven Vue SPA architecture with shared TS client, role-based WS pub/sub, SSE streaming | §4.1 multi-role UI requirement, §4.8 | §4.8 (3 SPAs + shared client lib + WS event catalog) | §5.6 |

- **The integration gap:** each need has been addressed individually in prior work — autonomous navigation (ROS2 delivery robots), Vietnamese speech (standalone STT/TTS/VAD), conversational agents (cloud chatbots), intent classification (NLU pipelines), menu retrieval (academic RAG), fleet management (warehouse frameworks), restaurant software (POS/KDS), and SPA web interfaces (Vue/React dashboards). No prior system has integrated all six into a single deployed system where the AI agent directly drives physical delivery and real-time UI state across all roles.

---

## CHAPTER 3: PROPOSED METHOD (I) — ROBOT CONTROL AND NAVIGATION

> *This chapter addresses Need 1 (dynamic goal navigation, §2.2). It follows the structure: system requirements derived from the gap (§3.1) → design challenges that make these requirements difficult (§3.2) → proposed method: how the system solves each challenge (§3.3–§3.7).*

### 3.1 System Requirements

- R1–R7 with target metrics (navigation success, docking precision, odometry accuracy, safe obstacle distance)
- Each requirement traceable to a specific gap in §2.2
- Domain constraint: dedicated service lane, physically separated from customers

### 3.2 Design Challenges

- **C1 — Consumer-grade IMU drift:** MPU6050 gyro bias accumulates angular error. Over a 10m round trip with multiple in-place rotations, uncorrected yaw drift may exceed ArUco marker field-of-view at the docking zone.
- **C2 — TWD non-holonomic constraints:** no lateral motion. Every position correction requires a rotation + translation sequence. In narrow service lanes (80–100 cm width), the robot's turning radius must be respected or the robot will collide with lane boundaries during in-place rotation.
- **C3 — SLAM-to-navigation infrastructure gap:** RTAB-Map produces an occupancy grid for localization. The backend dispatcher must query navigation waypoints by table ID — RTAB-Map does not expose table semantics; it exposes poses. A bridging layer must map table IDs to waypoint poses.
- **C4 — Dynamic goal coupling:** Nav2 accepts a single goal pose. The backend must be able to send a new goal at any time — when an order is ready, when the robot finishes a delivery and needs a new destination, when the session ends and the robot returns home.

### 3.3 Robot Platform & Hardware Setup

- **Purchased TWD platform:** chassis, two MC520P30 DC motors with encoders, STM32 microcontroller, MPU6050 IMU
- **Added components:** RPLiDAR A2M8 (360° 2D laser scanner), Intel RealSense D435 (RGB-D camera), Jetson Orin Nano (edge compute), 7" LCD touchscreen, battery pack
- **Boundary:** contribution starts from ROS2 integration upward
- **Component specifications table:** LiDAR range/angular resolution, D435 depth accuracy/FOV, MPU6050 gyro/accel specs, encoder resolution (P=1024 pulses/rev, G=30 gear ratio → N = P·4·G = 122880 ticks/rev), motor rated speed/torque
- **ROS2 robot model:** URDF with base_link, base_footprint, lidar_link, camera_link, wheel joints → render figure
- **TF tree:** `map → odom → base_footprint → base_link → (lidar_link, camera_link, imu_link)`
- **Platform constants:** wheel diameter D, wheel separation W, encoder ticks per revolution N, control loop rate 50 Hz, Vx_max, Vω_max
- **Connection/wiring block diagram:** Jetson ↔ STM32 (UART), Jetson ↔ LiDAR (USB), Jetson ↔ D435 (USB 3.0), Jetson ↔ LCD (HDMI+USB touch)
- **Photos of physical robot and service-lane/marker layout**

### 3.4 Wheel Odometry and EKF Sensor Fusion

- **How it addresses C1 (IMU drift):**
  - Wheel odometry: encoder tick model (`N = P·4·G`), velocity computation (`V = πD/N · Δn/Δt`), forward kinematics (`V_x = (V_A+V_B)/2`, `V_ω = (V_B−V_A)/W`), Euler pose integration
  - IMU (MPU6050): raw int16 → SI conversion, axis remap, gyro bias estimation, Mahony AHRS for relative yaw
  - EKF (`robot_localization`, `two_d_mode`): state `[x, y, ψ, V_x, V_y, V_ω]`, odom0 → V_x/V_y/V_ω, imu0 → V_ω only (no magnetometer → IMU yaw not fused), covariance tuning, output `/odometry/filtered` + `odom→base_footprint` TF
  - EKF fuses complementary sensor strengths: encoders provide short-term accuracy (no drift over 1–2m), IMU provides angular rate for sharp turns where encoder slippage is worst
  - **Figure:** EKF predict-update cycle diagram

### 3.5 Map Building with RTAB-Map

- **How it addresses C3 (SLAM-to-navigation gap):**
  - RTAB-Map pipeline: LiDAR (geometry) + RGB-D camera (loop closure) → 2D occupancy grid
  - Offline mapping run: teleop the service lane + return pass to force loop closure
  - Waypoint layer: after mapping, each table's docking pose is manually annotated in a configuration file keyed by table_id → {x, y, yaw}. The backend reads this config to resolve "go to table 3" → Nav2 goal pose
  - Tuned parameter table (grid resolution, max LiDAR range, loop-closure/proximity settings)
  - LiDAR-only mapping option; camera used for loop closure only (not 3D mapping)

### 3.6 Localization and ArUco-Based Docking

- **How it addresses C2 (non-holonomic TWD) and completes C1 (drift correction):**
  - RTAB-Map localization mode on saved map → publishes `map→odom`
  - Initial pose from home (kitchen) ArUco marker → absolute start pose, removes manual "2D Pose Estimate"
  - Per-table ArUco re-localization: at ~1m from the table, the D435 detects the table's ArUco marker → PnP computes 6-DoF camera-to-marker transform → pose corrected → final approach with sub-centimeter precision
  - Marker-lost → safe stop at predefined distance
  - Each marker is configured with table_id → backend verifies: "robot is at table B3, order #O128 belongs to session S42 at table B3" — business-context docking
  - **Figure:** ArUco marker pose estimation with annotated coordinate axes

### 3.7 Autonomous Navigation with Nav2 & Dynamic Goal Assignment

- **How it addresses C4 (dynamic goal coupling):**
  - Global planner: path along service lane, kitchen → table goal. Goal pose resolved from waypoint config by table_id
  - Dynamic goal interface: the backend dispatcher sends a new Nav2 goal via `NavigateToPose` action when an event occurs (order ready, seating complete, session ended). Nav2 preempts any in-flight goal and routes to the new one
  - Goal lifecycle: `go_to_table` (seating) → `deliver` (order done) → `return_home` (session paid). Each goal kind has a pre-configured target — table waypoint for table 3, home waypoint for kitchen
  - Local controller (`nav2_params.yaml`): look-ahead, desired/max speed, `V_y=0`, in-place rotation for non-holonomic TWD
  - Costmaps: static (2D map) + inflation + LiDAR obstacle layer
  - No pedestrian detection / social navigation (lane-separated from customers)
  - Progress reporting: arrival at waypoint → ArUco re-localization at close range → progress reported to backend via WebSocket → backend advances task state

---

## CHAPTER 4: PROPOSED METHOD (II) — AI, BACKEND & WEB SYSTEM

> *This chapter addresses Needs 2–6 (§2.3–§2.7). It follows the structure: system requirements derived from the gaps (§4.1) → design challenges (§4.2) → overall architecture and design rationale (§4.3) → per-component method: how each subsystem solves its challenges (§4.4–§4.8).*

### 4.1 System Requirements & Design Rationale

- **Functional requirements (from §2.3–§2.6):**
  - Natural language ordering in Vietnamese with tool execution (from §2.4)
  - Menu search by sensory attributes — taste, feel, occasion — not just by name (from §2.5)
  - Payment flow with session total computation (from §2.6)
  - Order-to-kitchen dispatch with real-time status updates (from §2.6)
  - Robot task management with dynamic goal assignment (from §2.2, §2.6)
  - Multi-table concurrent voice support (from §2.3, §2.6)
- **Non-functional:**
  - Self-hosted — no cloud LLM dependency (from §2.3 edge constraint, §2.4 chatbot limitation)
  - Low-latency voice interaction — utterance → response < 5s (from §2.3 edge deployment)
  - Deterministic safety — every LLM call validated before affecting system state (from §2.4 hallucination gap)
  - Per-session conversation isolation — no context bleed between tables (from §2.6 session lifecycle)
- **Design principles:**
  - Centralized brain (single server), thin edge (Jetson handles voice I/O + robot control only) — from §2.3 VRAM budget
  - Single-writer SQLite — from §2.6 restaurant scale (dozens of orders/hour, not thousands/second)
  - Sync LangGraph + async SSE — LangGraph's `SqliteSaver` is sync; execution in `ThreadPoolExecutor`, results streamed via async generator
  - Self-hosted Ollama not cloud API — from §2.3 edge constraint, §2.4 self-hosted gap
  - No fine-tuning — all adaptation via prompting (from §2.4 teencode gap — classifier handles this, not LLM)

### 4.2 Design Challenges

- **C5 — The Vietnamese informality frontier:** Teencode variants, context-dependent "ok", multi-intent compounding, and rare dish names break four different classifier families in four different ways. No single approach handles all. The system must be accurate (>90%), fast (<1ms), and deterministic — three properties that prior approaches trade against each other.
- **C6 — VRAM is zero-sum on the edge:** 8 GB shared on Jetson. ROS2 navigation + sensor drivers consume ~700 MB. STT model (~1.5 GB) + VAD (<10 MB) + TTS (~200 MB) leave ~5.5 GB. The 7B LLM needs 6–8 GB alone. The agent cannot run on the Jetson — it must run on the server. The system must split compute between edge and server without introducing unacceptable network latency in the voice pipeline.
- **C7 — The LLM is a probabilistic component in a deterministic system:** The agent's LLM can hallucinate dish names, wrong quantities, and invalid state transitions. The constraint is not to prevent hallucination (that's impossible without fine-tuning) but to *detect and block it* before any hallucinated output reaches external systems — on every single LLM call, without human review.
- **C8 — Sensory queries don't match menu structure:** Customers use experiential language ("ấm bụng", "ăn cay"). The menu is structured by name/category/price. Standard RAG fails when query and document share zero vocabulary. The retrieval pipeline must actively bridge this semantic gap — before and after the search.
- **C9 — The backend is a state machine the AI drives:** 4+ client roles, each seeing different event subsets, all updated in real time as the AI agent creates orders, updates cart state, dispatches robots, and processes payments. A polling-based architecture introduces 5–10s lag on critical events (a new order sitting invisible on the kitchen display). A cloud-dependent architecture fails when WiFi drops. The entire system must run on one machine.
- **C10 — Robot-table voice binding must survive disconnection:** When a robot arrives at table 3, its microphone is bound to the tablet at table 3. If the robot's WiFi drops mid-session, the binding must be released, the task must be requeued for another robot, and the new robot must rebind — without the customer noticing which robot is talking to them.

### 4.3 Overall Software Architecture

- **Three-tier topology:** Server tier (Agent brain + Orchestrator backend + Ollama LLMs + RAG indices), Robot tier (Voice pipeline + ROS2 navigation stack), Client tier (3 browser SPAs)
- **Block diagram** (from `diagram.md` Fig 4.1): all components, protocols, and 4 main data flows:
  - (a) Voice ordering at table: tablet "Talk to AI" → backend WS → Jetson mic armed → VAD→STT→Agent→TTS → text reply + UI action → tablet display
  - (b) Order → kitchen display: agent confirms order → backend creates order row → WS `order.created` → kitchen panel updates Kanban
  - (c) Manager monitoring: robot poses at 4+ Hz → RAM store → WS broadcast at 5 Hz → fleet dashboard minimap
  - (d) Backend → robot navigation goals: order status → XONG → dispatcher assigns deliver task → WS `task.assign` → robot receives Nav2 goal
- **Component responsibility map:** what runs where, what talks to what, over which protocol
- **Design rationale addressing each challenge:**
  - C5 (Vietnamese informality): MLP classifier with context features — frozen bi-encoder embedding (768-dim) + 10 conversation state features (order_stage, cart state, search history) → 778-dim input → 3-layer MLP → 0.17ms → deterministic
  - C6 (VRAM budget): edge/server split — microphone+speaker on Jetson, LLM on server GPU. Audio → STT locally (text is ~100 bytes), text → server HTTP (negligible payload), response text → TTS locally
  - C7 (probabilistic LLM): deterministic validator between every LLM call and tool execution — menu name resolution, off-menu detection, state consistency checks, circuit breaker (max 3 retries)
  - C8 (sensory queries): closed-loop RAG — LLM rewrites vague query → hybrid retrieval (BM25 + FAISS + RRF fusion) → LLM evaluates and rephrases results
  - C9 (state machine backend): single FastAPI + SQLite process, WAL mode, WebSocket fan-out by role, session lifecycle enforced with state transitions
  - C10 (voice binding): dynamic bind/unbind on robot arrival/departure, watchdog (30s timeout), requeue on failure

---

### 4.4 Edge Voice Pipeline *(→ Need 2, §2.3)*

> *How the Jetson processes spoken Vietnamese and produces spoken replies, under the constraints identified in §2.3 (restaurant noise, edge VRAM budget, co-located robot control).*

#### 4.4.1 Edge/Server Split Rationale

- Addressing C6 (VRAM budget): microphone and speaker on Jetson → STT and TTS models are GPU-light (~1.5 GB + 200 MB) → run on Jetson's CUDA cores. LLM (Qwen2.5 7B, ~6–8 GB) runs on server GPU.
- Local STT avoids network round-trip latency for audio upload. Text transcript (~100 bytes) is a negligible payload compared to raw audio (~100 KB).
- Protocol: Jetson connects to orchestrator WebSocket as `role=voice-device`. The tablet→voice flow: Customer presses "Talk to AI" → `POST /voice/listen` → orchestrator WS forwards `start_listening` to bound voice device → Jetson arms microphone. After agent produces text output → `POST /voice/event` → orchestrator WS mirrors to tablet.

#### 4.4.2 Threaded Pipeline Architecture

- **VAD thread:** captures microphone in 512-sample chunks, resamples to 16 kHz. Silero VAD classifies each frame as speech/silence. Configurable sensitivity threshold tuned for restaurant noise. Gate-controlled: only active between `start_listening` and utterance completion.
- **STT thread:** receives complete utterance audio via `speech_queue`. Runs faster-whisper medium with `language=vi`, `beam_size=5`. PhoWhisper weights for improved tonal accuracy. Output transcript → `text_queue`.
- **Main loop:** pops transcript → HTTP POST to agent brain `/chat` → receives response JSON → dispatches to TTS → signals ready for next utterance.
- **Single-utterance mode:** pipeline captures exactly one utterance per `start_listening`, then auto-idles. Prevents continuous eavesdropping.

#### 4.4.3 Barge-In Mechanism

- TTS playback is sentence-by-sentence (aligned with agent SSE output).
- During TTS playback, VAD thread runs concurrently in monitoring mode.
- If VAD detects new speech → playback interrupted mid-sentence → new utterance captured and processed.
- Enables natural turn-taking — customer can interrupt to correct an order.

#### 4.4.4 TTS Strategy

- **Primary:** Piper TTS (local, Vietnamese voice, CPU, ~500ms/sentence). Offline on Jetson.
- **Fallback:** edge-tts (Azure Vietnamese Neural voices). Used when Piper unavailable or on x86 dev machines.
- Selection: attempt Piper first → health check → fall back to edge-tts.

---

### 4.5 Conversational Agent *(→ Need 3, §2.4)*

> *The intellectual core of the software contribution. How the agent converts informal Vietnamese utterances into deterministic, validated actions — addressing C5 (Vietnamese informality) and C7 (probabilistic LLM in a deterministic system). Every utterance flows through five stages: Understanding → Decision → Validation → Execution → Response. The graph topology enforces the restaurant ordering state machine (from §2.4.2 architecture gap).*

#### 4.5.1 Agent Execution Model

- **LangGraph StateGraph:** 10 nodes, 6 conditional edges, 4 normal edges. Entry at `router`, exit after `response_node`.
- **AgentState (18 fields, TypedDict):**
  - Conversation history: `messages` (across turns, append-only)
  - Task state: `table_id`, `active_cart`, `order_stage`, `search_context` (across turns)
  - Routing state: `current_intents`, `routing_meta` (intents queue for multi-intent iteration)
  - Inter-node contract: `is_valid`, `feedback`, `loop_count`, `unavailable_items`, `ambiguous_items`, `last_tool`, `delegate_reason`, `intent_queries` (per-turn)
  - Output: `ui_action`, `order_confirmed`, `response_context` (per-turn)
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
- **Conversation memory:** compiled with LangGraph `SqliteSaver`. `thread_id = orchestrator_session_id`. Persistent fields survive across turns; ephemeral fields reset each turn in `state_outcome`.
- **How the graph addresses C5 (informality) and C7 (hallucination):** the router handles classification under informality (§4.5.2). The validator intercepts every tool call before execution (§4.5.4). The graph topology ensures correct function even when classification is imperfect — failed validation loops back with corrective feedback, and the circuit breaker guarantees termination.

#### 4.5.2 Stage I — Understanding: Intent Classification

> Addressing C5: Vietnamese informality.

- **Intent taxonomy:** {ORDER, SEARCH, PAYMENT, CHAT}. ORDER_CONFIRM merged at router level; distinction handled downstream by order state machine.
- **MLP classifier architecture (778-dim → 0.17ms → deterministic):**
  - **Embedding:** `bkai-foundation-models/vietnamese-bi-encoder` (768-dim, L2-normalized). Vietnamese-specific bi-encoder trained on Vietnamese sentence pairs.
  - **Context features (10-dim):** order_stage one-hot (5-dim), has_cart, cart_size_norm, has_search_context, search_context_size_norm, utterance_length_norm.
  - **Network:** 3-layer MLP: 778 → 256 → ReLU → Dropout(0.2) → 64 → ReLU → Dropout(0.2) → 4. Softmax output.
  - **Training:** 3,712 synthetically generated Vietnamese utterances across 4 intents with per-utterance context features. 80/20 stratified split. CrossEntropyLoss with class weights. Adam (lr=1e-3, weight_decay=1e-4). Early stopping (patience=10). Embeddings precomputed offline — CPU training in ~2 minutes.
  - **Why trained classifier over LLM routing:** latency (0.17ms vs 1.8s), determinism (same input → same output), context-awareness (10 features encode state that pure embeddings cannot see).
  - **Inference pipeline:** word segmentation → bi-encoder embedding → extract context features → StandardScaler → concatenate → MLP forward → softmax → `{intent, confidence, all_probs}`.

#### 4.5.3 Stage II — Decision: Tool-Calling LLM

- **Configuration:** Qwen2.5 7B via Ollama, `temperature=0.1`, `tool_choice="any"`. System prompt (~200 tokens) + 5 few-shot examples. Menu excluded from prompt — the LLM does not need menu knowledge to decide which tool to call.
- **Tool bindings per intent:**
  - ORDER: `add_cart`, `remove_cart`, `clear_cart`, `confirm_order`, `delegate`
  - SEARCH: `search`, `delegate`
  - PAYMENT: `request_payment` (deterministic — no LLM call)
  - CHAT: (none — pure function building curated memory context)
- **Delegate escape hatch:** `delegate(reason)` bound alongside domain tools. When LLM cannot map utterance to a meaningful domain action, it calls `delegate()` → routed to CHAT worker. The LLM is never forced to produce a wrong action.
- **Retry with corrective feedback:** validator rejection → `feedback` injected into next worker prompt → LLM receives explicit correction instructions.
- **Circuit breaker:** `loop_count` tracks retries. At 3 failures → `RetryResponseContext` with apology → response generation. Bounded execution regardless of LLM behavior.

#### 4.5.4 Stage III — Validation: Deterministic Safety Net

> Addressing C7: detecting and blocking hallucinated tool calls before they reach external systems.

- **Design rationale:** every LLM call followed by a validator call. Firewall pattern — validator cannot prevent hallucination but detects it before it affects the cart or backend.
- **Menu name resolution pipeline (`resolve_menu_name`):**
  1. Normalize: lowercase + strip Vietnamese diacritics via Unicode NFD decomposition
  2. Exact match against 217 dish names
  3. Prefix match (partial utterances: "Ốc Hương" → "Ốc Hương Xốt Trứng Muối")
  4. Substring match
  5. Token-level Jaccard similarity fallback (threshold ≥ 0.3)
  6. Return best match or `None`
- **Off-menu handling:** unresolved items → `unavailable_items` with nearest-match suggestion. Validator never auto-corrects — only flags and suggests.
- **Ambiguity detection:** generic names matching multiple menu items → `ambiguous_items`. Agent requests clarification. Ambiguous items never auto-resolved.
- **Modifier stripping:** regex extracts special requests ("Lau Thai, it cay" → `name="Lau Thai"`, `note="it cay"`).
- **State consistency checks:** additive-turn detection (utterance keywords "thêm", "nữa" → auto cart restoration), context-duplicate items, simultaneous add+confirm rejection (confirm stripped — customer must explicitly confirm after seeing cart).
- **How this addresses C7:** the LLM is allowed to hallucinate. The validator catches every hallucinated argument before it reaches `add_cart`, `confirm_order`, or `request_payment`. The circuit breaker prevents infinite retry loops. The safety invariant is LLM → validate → action, not LLM → action.

#### 4.5.5 Stage IV — Execution: Tools & State Management

- **In-memory cart tools:** `add_cart`, `remove_cart`, `clear_cart` operate on `AgentState.active_cart` only (no network I/O). Multiple `add_cart` for same dish → increment quantity.
- **Orchestrator API tools:** `confirm_order` → HTTP POST to orchestrator → order ID returned → `order_confirmed=True`. `request_payment` → computes session total → returns VietQR URL + amount. `verify_payment` → closes session, frees table.
- **Cart State Machine:**
  ```
  IDLE ──(add_cart)──→ DRAFTING ──(agent echoes cart)──→ AWAITING_CONFIRMATION
    ↑                        ↑                                    │
    │                        │ add_cart/remove_cart               │ confirm_order
    │                        └────────────────────────────────────┘
    │                                                             │
    └────────────────────(payment verified)───────────────────────┘
                                                                CONFIRMED
  ```
  Enforced at `state_updater`. Any `add_cart`/`remove_cart` at `AWAITING_CONFIRMATION` loops back to `DRAFTING` → cart re-echoed.
- **Multi-intent iteration:** `current_intents` as a FIFO queue. Worker processes first intent → state_updater merges results → pops intent → loops. Queue empty → state_outcome combines all ResponseContexts → unified reply.

#### 4.5.6 Stage V — Response: Output Generation

- **Typed ResponseContext dispatch:** `OrderResponseContext`, `SearchResponseContext`, `PaymentResponseContext`, `ChatResponseContext`, `RetryResponseContext`. Structured data input, not raw text.
- **Template-based responses (deterministic):** order confirmations, payment prompts, cart echoes, error/recovery messages, retry apologies, empty search results. Pre-written Vietnamese templates.
- **LLM-based responses (Qwen2.5 7B, T=0.3):** search results in natural Vietnamese, off-menu suggestions with alternatives, free-form chat. LLM receives typed `ResponseContext` → paraphrases into conversational Vietnamese.
- **SSE streaming:** LangGraph executes synchronously in `ThreadPoolExecutor` → produces `ResponseContext` → async generator wraps → yields SSE events. Sentence splitting via `re.split(r"[.!?]\s", buffer)`.

#### 4.5.7 Prompt Architecture

> *The system uses zero fine-tuning — all model adaptation is through prompting. The prompt architecture is a first-class design element.*

- **System prompts (7 files, all Vietnamese):** each LLM-calling node has its own prompt defining role, reasoning protocol, output format, constraints.
- **Few-shot examples:** static JSON loaded at boot, injected at runtime.
  - Order worker: 5 examples with tool calls for KV-cache optimization
  - Search worker: 5 examples with `search` + `delegate` calls
  - (Router prompt unused by MLP classifier — fallback path only)
- **Skill documents:** `hospitality.md` (Vietnamese restaurant service etiquette), `menu_grounding.md` (menu-as-ground-truth rules), `no_service_response.md` (domain boundary).
- **Dynamic context injection:** last 2 conversation turns into prompts for context awareness; "ĐÃ BIẾT" section for search deduplication; validator `feedback` into retry prompts.
- **Per-stage model configuration:**

  | Stage | Model | Temperature | Key Configuration |
  |-------|-------|-------------|-------------------|
  | Router | MLP classifier (trained) | N/A (deterministic) | 778-dim: bi-encoder embedding + context features |
  | Worker (ORDER/SEARCH) | Qwen2.5 7B | 0.1 | `tool_choice="any"` — forced tool call |
  | Response | Qwen2.5 7B | 0.3 | Free-form generation — natural Vietnamese |

  All models: `keep_alive=-1` (pinned in VRAM). Warmup ping at agent startup.

---

### 4.6 Knowledge Retrieval Pipeline *(→ Need 4, §2.5)*

> *Addressing C8 (sensory queries don't match menu structure). A closed-loop pipeline: the LLM rewrites the customer's vague query into concrete search terms before retrieval, a hybrid BM25+FAISS+RRF retriever searches the menu, and the LLM rephrases the results in natural Vietnamese after retrieval.*

#### 4.6.1 Query Rewriting

- LLM analyzes the customer's vague Vietnamese utterance → produces concrete, searchable Vietnamese terms.
- Example: "Món gì ấm bụng cho ngày lạnh?" → "cháo, lẩu, súp, món nước nóng".
- Reasoning is about Vietnamese culinary categories — knowing what constitutes "ấm bụng" in Vietnamese food culture.
- Rewritten query becomes BM25 search terms and FAISS embedding input.

#### 4.6.2 Hybrid Retrieval

- **BM25 (sparse):** Vietnamese word segmentation via `underthesea.word_tokenize()`. Compound words ("bún bò Huế") become single tokens. Keyword matching on rewritten query.
- **FAISS (dense):** SentenceTransformer embedding → top-k by cosine similarity. Diacritic-aware Vietnamese bi-encoder for semantic matching.
- **RRF fusion:** `score(d) = Σ 1/(60 + rank_d)`. Parallel BM25 + FAISS (raw k=10 each) → fused ranking.
- **Dual-lane gatekeeper:** semantic lane (top FAISS cosine ≥ 0.35) OR lexical lane (query keyword appears in top document text). Both fail → return empty.
- **Metadata post-filters:** price range, diet_type, category.

#### 4.6.3 Result Rephrasing

- After retrieval, the LLM evaluates top-k results: which dishes match the original customer intent? Which are irrelevant?
- Selects and rephrases relevant results in natural Vietnamese: "Dạ, cho ngày lạnh quán có Lẩu Cá Tầm, Cháo Hải Sản, và Súp Cua ạ."
- Detects empty results → responds "Dạ, quán không có món đó ạ" — no hallucination from empty retrieval.

#### 4.6.4 Multi-Turn Search Context

- "ĐÃ BIẾT" section in search prompts: previously returned items + current cart items.
- Prevents redundant queries — if customer searches "Ốc Hương" twice, agent knows it already returned those results.
- Search context persists across turns in `AgentState.search_context`.

---

### 4.7 Backend Orchestrator & Real-Time Systems *(→ Need 5, §2.6)*

> *Addressing C9 (state machine backend) and C10 (robot-table voice binding). How the server coordinates restaurant operations — REST API, WebSocket hub, fleet dispatcher, session lifecycle, and voice bridge — all in a single self-contained FastAPI process.*

#### 4.7.1 REST API

- 20 endpoints across 10 routers: menu, tables, orders, payments, robots, tasks, layout, admin, voice, WebSocket
- Request/response validation via Pydantic. Auto-generated OpenAPI docs. CORS for Vite dev ports.

#### 4.7.2 WebSocket Hub

- Single `/ws` endpoint, 4 role types via query parameter:
  - `role=panel` → anonymous broadcast (kitchen display, fleet dashboard)
  - `role=customer` → anonymous broadcast filtered by `table_id` (tablets)
  - `role=robot` → indexed by `robot_id`, bidirectional (task assignment + telemetry)
  - `role=voice-device` → indexed by `robot_id`, server→client only (start/cancel listening)
- Event catalog: `order.created`, `order.updated`, `table.updated`, `robot.updated`, `task.created`, `task.updated`, `voice.heard`, `voice.reply`, `reset`

#### 4.7.3 Session Lifecycle

- Kiosk seating → `POST /seatings` → creates `ACTIVE` session → sets `tables.status = DANG_PHUC_VU` → dispatches `go_to_table` task
- Multiple orders per session → cumulative payment: session total = sum of all confirmed order totals
- Payment → `POST /payments/verify` → session `CLOSED` → table `DA_THANH_TOAN` → cancels pending robot tasks
- Table manually ended → `PATCH /tables {status: TRONG}` → clears state, cancels tasks, sends robot home

#### 4.7.4 Fleet Management

- **Telemetry:** RAM-only dict (pose + battery) at 4+ Hz via WS heartbeats. Periodic DB snapshot every 15s for cold-start recovery. Pose broadcast throttled to 5 Hz for minimap.
- **Task assignment (nearest-idle):** filter eligible robots (status_idle + live WS + battery ≥ 20%) → score by Euclidean distance from live pose to target table waypoint → assign to nearest.
- **Task lifecycle:** `PENDING → ASSIGNED → IN_PROGRESS → DONE`. Task kinds: `go_to_table`, `deliver`, `call`.
- **Watchdog:** scans every 5s. No heartbeat for >30s → mark offline → requeue tasks → close WS → release voice binding.
- **Dynamic voice binding (addressing C10):** on robot arrival at table → `bind_table_robot(table_id, robot_id)`. All voice commands from that table route to that robot's voice device. On release/disconnect → binding cleared. Watchdog releases stale bindings.

#### 4.7.5 Database Schema

- SQLite, raw SQL via `sqlite3` (no ORM). WAL mode for concurrent reads during writes.
- 8 business tables: `tables`, `sessions`, `dishes`, `orders`, `order_items`, `robots`, `tasks`, `payments`
- Separate `checkpoints.db` for LangGraph conversation memory (managed by `SqliteSaver`)
- Schema evolution via `ALTER TABLE ADD COLUMN` with `PRAGMA table_info` for idempotent migrations
- ERD diagram

---

### 4.8 Web Interfaces *(→ Need 5, §2.6 — multi-role real-time synchronization)*

> *Three single-page applications sharing a common TypeScript library. Each app has a specific role in the restaurant service flow.*

#### 4.8.1 Shared Architecture

- 3 Vite + Vue 3 SPAs importing `@/shared` (REST client, WS client with auto-reconnect, TS types mirroring Pydantic schemas)
- Vite dev proxies `/api` → orchestrator `:8000`, `/ws` → orchestrator `:8000`
- State management: Pinia stores per app

#### 4.8.2 Customer Tablet UI

- **Menu browsing:** 12 categories, diacritic-insensitive search, Best Seller section, scroll-synced navigation
- **Voice mirror:** real-time WS conversation display, thinking indicators, cart sync (`syncFromVoice`), UI action following (`open_menu`, `open_payment`)
- **Cart management:** voice or touch add/remove, server-computed total, order confirmation, VietQR payment display

#### 4.8.3 Kiosk (Check-in)

- Table grid with real-time status, party size selector, 409 conflict handling, success auto-close

#### 4.8.4 Management Panel (Kitchen + Fleet)

- **Kitchen Kanban:** 3-column board (Chờ Bếp / Đang Làm / Xong), per-order elapsed time, advance button → cascades to robot delivery tasks
- **Fleet board:** per-robot cards (status, battery, activity, last seen), live minimap at 5 Hz with colored markers
- **Table overview:** per-table status, party size, session duration, linked active orders

---

### 4.9 Deployment Topology

- **Hardware:** Server (x86 + NVIDIA GPU — Ollama + orchestrator + agent brain), Jetson Orin Nano (robot — ROS2 + voice pipeline), Laptops/tablets (browser SPAs on local WiFi)
- **LLM configuration:** Qwen2.5 7B Instruct via Ollama, per-stage temperature config, `keep_alive=-1`, warmup ping at startup
- **Package management:** Python via `uv` with role-based extras; frontend via `npm` workspaces (3 Vite apps + 1 shared lib)
- **Network:** local WiFi, all components; Netbird VPN for off-site server scenarios

---

## CHAPTER 5: EXPERIMENTS AND RESULTS

> *Each experiment validates one or more requirements from §3.1 and §4.1, which trace back to needs identified in Chapter 2. Structure per experiment: goal → dataset → methodology → metrics → results → analysis → ablation.*

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
| Embedding model | bkai-foundation-models/vietnamese-bi-encoder (768-dim) |
| STT model | faster-whisper medium, PhoWhisper weights, `language=vi`, `beam_size=5` |
| OS | Ubuntu 22.04 LTS, ROS 2 Humble |
| Network | Local WiFi (server ↔ Jetson ↔ browser clients) |

#### 5.1.2 Datasets Summary

| Dataset | File | Size | Purpose | Validates Need |
|---------|------|------|---------|---------------|
| Router evaluation | `evals/data/router/router_eval.json` | 45 cases | Intent classification accuracy | §2.4 |
| Router evaluation (semantic) | `evals/data/router/semantic_eval.json` | 100 cases | Balanced single-intent accuracy | §2.4 |
| Router holdout | `training_semantic_router/data/test_holdout.json` | 39 cases | Clean holdout (never seen during training) | §2.4 |
| Retrieval evaluation | `evals/data/retrieval/retrieval_eval.json` | 24 queries | Menu search relevance | §2.5 |
| E2E conversations (Part 1) | `evals/data/e2e/e2e_conversations_part1.json` | 6 scenarios | Happy-path ordering flows | §2.4, §2.6 |
| E2E conversations (Part 2) | `evals/data/e2e/e2e_conversations_part2.json` | 5 scenarios | Edge-case flows | §2.4, §2.6 |
| Out-of-menu robustness | `evals/data/e2e/e2e_out_of_menu_test.json` | 4 scenarios | Validator off-menu rejection | §2.4 |
| Real-life scenarios | `evals/data/e2e/e2e_real_life.json` | 4 scenarios | Qualitative multi-turn case studies | §2.4 |
| STT transcription | *(to be built)* | 50–100 utterances | Vietnamese restaurant WER/CER | §2.3 |
| VAD boundary detection | *(to be built)* | ~30 annotated clips | VAD accuracy in restaurant noise | §2.3 |
| Validator name resolution | *(to be built)* | ~70 pairs | Per-stage name resolution accuracy | §2.4 |
| Context-dependent routing | *(to be built)* | ~15 cases | Dynamic context ablation | §2.4 |
| Response quality (MOS) | *(to be built)* | 20–30 responses | Vietnamese naturalness | §2.4 |

#### 5.1.3 Metrics Definition

##### AI Classification & Retrieval Metrics

| Metric | Formula | Measures | Maps to Need | Maps to §1.3 Objective |
|--------|---------|----------|-------------|------------------------|
| **Accuracy** | correct / total | Classification correctness | §2.4 | Router accuracy ≥ 90% |
| **Confusion matrix** | Heatmap: predicted vs actual (5×5) | Per-intent-pair error patterns | §2.4 | Router correctness |
| **Precision@k** | |relevant ∩ retrieved| / k | Fraction of top-k results relevant | §2.5 | RAG precision target |
| **Recall@k** | |relevant ∩ retrieved| / |relevant| | Fraction of all relevant items found | §2.5 | RAG recall target |
| **MRR** | 1 / rank of first relevant hit | Rank of first correct result | §2.5 | Search ranking quality |
| **Hit Rate** | queries with ≥1 relevant / total | Queries returning any useful result | §2.5 | RAG completeness |
| **Pass Rate** | passed scenarios / total | E2E scenario completion | §2.4, §2.6 | Voice ordering completion |

##### Speech Pipeline Metrics

| Metric | Formula | Measures | Maps to Need |
|--------|---------|----------|-------------|
| **WER** | (S + D + I) / N | STT accuracy on Vietnamese restaurant speech | §2.3 |
| **CER** | Same at character level | Tonal diacritic accuracy (6 tones) | §2.3 |
| **VAD false trigger rate** | false_positive_triggers / total_silence | VAD triggering on restaurant noise | §2.3 |
| **VAD missed utterance rate** | missed / total utterances | VAD failing to detect speech onset | §2.3 |
| **VAD cut-off rate** | utterances_with_premature_end / total | VAD trimming utterance tails | §2.3 |
| **Barge-in success rate** | successful_barge_in / attempted | Customer interrupts TTS correctly | §2.3 |

##### Safety & Robustness Metrics

| Metric | Formula | Measures | Maps to Need |
|--------|---------|----------|-------------|
| **Validator catch rate** | blocked / total_hallucinated | Validator correctly blocks hallucinated tool calls | §2.4 |
| **Validator false positive rate** | wrongly_blocked / total_valid_calls | Validator incorrectly blocks correct calls | §2.4 |
| **Circuit breaker rate** | breaker_triggered / total_retries | How often retry exhausts; LLM quality indicator | §2.4 |
| **Delegate rate** | delegate_calls / total_tool_calls | How often LLM cannot find domain action; escape hatch quality | §2.4 |

##### Navigation Metrics (from §2.2)

| Metric | Measures | Maps to Need |
|--------|----------|-------------|
| **Return-to-start error** | EKF odometry drift after kitchen→table→kitchen | §2.2 |
| **Navigation success rate** | Kitchen→table trips with arrival at ArUco zone | §2.2 |
| **ArUco docking error** | Final pose error (cm + degrees) after marker correction | §2.2 |
| **Goal assignment latency** | Backend event → Nav2 goal active → robot starts moving | §2.2, §2.6 |

---

### 5.2 ROS2 Navigation Experiments *(→ Need 1, §2.2)*

#### 5.2.1 Odometry Accuracy Test

- Goal: validate EKF-fused odometry accuracy on TWD platform
- Dataset: 10–20 return trips, kitchen → table → kitchen, varied table distances
- Methodology: record `/odometry/filtered` → compare start/end pose
- Metrics: return-to-start error (cm), RMS trajectory error vs. ground truth
- Ablation: encoder-only vs. EKF-fused (with and without IMU yaw)
- **→ Validates requirement R(odometry) from §3.1; maps to §2.2 gap**

#### 5.2.2 Map Building and Localization Test

- Goal: evaluate RTAB-Map map quality and localization reliability
- Dataset: offline mapping run + localization-only runs
- Methodology: build map → run localization → measure localization consistency
- Metrics: loop closure events, localization drift over time, map resolution

#### 5.2.3 Navigation and Docking Test

- Goal: end-to-end navigation + ArUco docking precision
- Dataset: kitchen → 6 tables → kitchen, 5–10 trials per table
- Methodology: Nav2 goal → drive → ArUco re-localization → measure final pose
- Metrics: navigation success rate, docking error (cm, °), ArUco detection rate
- Ablation: with and without ArUco correction on final approach
- **→ Validates requirements R(navigation) + R(docking) from §3.1; maps to §2.2 gap**

#### 5.2.4 Dynamic Goal Assignment Test

- Goal: validate that backend-generated Nav2 goals are executed correctly
- Dataset: 10 sequences: backend API → goal change mid-navigation
- Methodology: send goal A → robot en route → send goal B → verify robot routes to B
- Metrics: goal switch latency, correct arrival at new goal
- **→ Maps to §2.2 core gap: dynamic goal coupling with external AI agent**

---

### 5.3 AI Agent Experiments *(→ Need 3, §2.4)*

#### 5.3.1 Intent Classification Accuracy

- Goal: validate MLP classifier against all 5 baseline approaches
- Datasets: router_eval (45), semantic_eval (100), test_holdout (39)
- Methodology: per-utterance classification, compare predicted vs. actual
- Metrics: accuracy, per-class precision/recall/F1, confusion matrix, per-difficulty breakdown
- Ablation: MLP vs. centroid router (original) vs. two-tier hybrid vs. LLM routing
- Per-challenge analysis: accuracy on teencode utterances, context-dependent utterances, multi-intent utterances, domain-vocabulary utterances
- **→ Validates requirement R(classification) from §4.1; maps to §2.4 gap**

#### 5.3.2 Validator Safety Test

- Goal: validate deterministic validator catches hallucinated tool calls
- Dataset: out-of-menu test (4 scenarios) + injected hallucination cases
- Methodology: feed LLM prompts designed to elicit hallucination → verify validator blocks
- Metrics: validator catch rate, false positive rate, circuit breaker rate, delegate rate
- **→ Validates requirement R(validation) from §4.1; maps to §2.4 hallucination gap**

#### 5.3.3 End-to-End Agent Test

- Goal: validate full agent pipeline on complete ordering scenarios
- Datasets: e2e_conversations_part1 (6), e2e_conversations_part2 (5)
- Methodology: run automated conversations through agent → check all outputs
- Metrics: pass rate, per-stage failures, per-difficulty pass rate
- Failure analysis: which agent stage (router → worker → validator → response) fails most often
- **→ Validates requirements R(agent) + R(e2e) from §4.1; maps to §2.4 overall gap**

#### 5.3.4 Retrieval Evaluation

- Goal: validate closed-loop RAG pipeline accuracy
- Dataset: retrieval_eval (24 queries)
- Methodology: query rewriting → hybrid retrieval → result rephrasing → evaluate correctness
- Metrics: Precision@5, Recall@5, MRR, Hit Rate, per-difficulty breakdown
- Ablation: BM25-only vs. FAISS-only vs. hybrid; with and without query rewriting
- **→ Validates requirement R(retrieval) from §4.1; maps to §2.5 gap**

---

### 5.4 Voice Pipeline Experiments *(→ Need 2, §2.3)*

#### 5.4.1 STT Word Error Rate (WER)

- Goal: evaluate STT accuracy on Vietnamese restaurant speech
- Dataset: 50–100 recorded restaurant utterances with ground-truth transcripts
- Methodology: faster-whisper medium, PhoWhisper weights → compare transcript vs. ground truth
- Metrics: WER, CER, per-utterance breakdown, key dish-name substitution rate
- Ablation: Whisper base vs. medium, with and without PhoWhisper weights

#### 5.4.2 VAD Accuracy in Restaurant Noise

- Goal: evaluate VAD boundary detection under ambient restaurant noise
- Dataset: ~30 annotated audio clips with speech/silence ground truth
- Methodology: Silero VAD with varied sensitivity thresholds → compare detected vs. ground truth boundaries
- Metrics: false trigger rate, missed utterance rate, cut-off rate
- Ablation: different sensitivity thresholds; Silero vs. WebRTC

#### 5.4.3 Barge-In Test

- Goal: validate barge-in interrupts TTS correctly
- Dataset: 10–15 simulated barge-in scenarios
- Methodology: TTS playing → speak during playback → verify interrupt → verify new utterance captured
- Metrics: barge-in success rate, interrupt latency

#### 5.4.4 Edge Performance Benchmark

- Goal: validate voice pipeline runs within Jetson VRAM budget
- Methodology: monitor GPU memory usage during concurrent operation (ROS2 + VAD + STT + TTS)
- Metrics: GPU memory (MB), CPU utilization (%), STT/TTS latency (ms)
- **→ Validates C6; maps to §2.3 gap**

---

### 5.5 System Integration Tests *(→ Need 5, §2.6)*

#### 5.5.1 End-to-End Integration

- Goal: validate full system: voice → agent → backend → kitchen display → robot dispatch
- Dataset: 5–10 integration scenarios
- Methodology: automated scripts simulating customer voice ordering through full pipeline
- Metrics: pass rate, end-to-end latency, per-component failure attribution

#### 5.5.2 Multi-Table Concurrency

- Goal: validate correct session isolation across simultaneous conversations
- Dataset: 2–3 concurrent voice sessions at different tables
- Methodology: simultaneous automated conversations → verify no context bleed
- Metrics: session isolation accuracy, per-table cart correctness

#### 5.5.3 Fleet Management

- Goal: validate dispatcher task assignment, watchdog recovery, voice binding
- Methodology: simulated robot connect/disconnect → verify requeue + rebind
- Metrics: task requeue latency, voice rebind correctness

---

### 5.6 Web System Experiments

#### 5.6.1 UI Correctness

- Goal: validate 3 SPAs display correct data under real-time updates
- Methodology: automated UI checks via browser testing → verify state mirrors backend
- Metrics: data consistency across roles, WS event → UI update latency

#### 5.6.2 WebSocket Stress Test

- Goal: validate WS hub handles concurrent connections
- Methodology: multiple simultaneous WS clients across all 4 roles
- Metrics: connection stability, event delivery rate, reconnect success

---

### 5.7 Results Summary & Gap-to-Validation Traceability

Table mapping each Ch.2 need → requirement → experiment → key result:

| Need (§2) | Requirement | Experiment | Key Result |
|-----------|-------------|------------|------------|
| 2.2 Dynamic nav | R1–R7 | §5.2.1–§5.2.4 | Odometry error X cm, docking error Y cm, nav success Z% |
| 2.3 Vietnamese voice | §4.1 NFR | §5.4.1–§5.4.4 | STT WER X%, VAD false trigger Y%, edge VRAM Z MB |
| 2.4 Informal speech → action | §4.1 agent | §5.3.1–§5.3.3 | Classifier 97.4% holdout, validator catch rate X%, E2E pass Y% |
| 2.5 Sensory → relevant items | §4.1 search | §5.3.4 | P@5 X, R@5 Y, MRR Z |
| 2.6 AI-driven operations | §4.1 concurrency | §5.5.1–§5.5.3, §5.6 | Integration pass rate X%, session isolation Y%, fleet recovery Zs |

---

## CHAPTER 6: CONCLUSION AND FUTURE WORKS

### 6.1 Conclusion

- Tick each §1.3 objective against Ch.5 numbers
- Summarize both contribution legs:
  - Autonomous TWD navigation + EKF-fused odometry + RTAB-Map + Nav2 + ArUco docking
  - Trained MLP intent classifier (97.4% holdout, 95.6% A/B) + agentic LangGraph workflow (multi-intent queue, tool execution, deterministic validator) + closed-loop RAG (rewrite→retrieve→rephrase for Vietnamese menus) + voice pipeline + 3 web UIs

### 6.2 Limitations

- Consumer-grade IMU (MPU6050) → yaw drift, no magnetometer
- Wheel slip on smooth floors
- ArUco docking: lighting sensitivity (D435), no final-approach controller implemented
- Router: SEARCH accuracy 80% (on 100-case balanced set); delivery query confusion with PAYMENT; teencode-heavy utterances degrade embedding quality; ORDER_CONFIRM critical error on "Ghi nhận đơn hàng của tôi" (→PAYMENT at conf=1.00)
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
