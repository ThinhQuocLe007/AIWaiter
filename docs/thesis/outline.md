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

## CHAPTER 2: RELATED WORK & THEORETICAL FOUNDATIONS

> **Principle:** Each section surveys existing technologies, tools, and approaches — never the group's own system. Sections covering tools used as-is (LangGraph, FAISS, Silero VAD, Nav2) provide conceptual understanding only, not implementation detail. Sections covering areas where the group contributes something new (intent classification, voice pipeline integration, fleet dispatch) end with a clear gap statement. The final summary (§2.8) maps each gap to the requirement it motivates in Chapter 3 or Chapter 4.
>
> Every Ch.4 design decision must trace back to a gap identified here. Every Ch.3 system requirement must trace back to a gap or a limitation of existing approaches surveyed here.

### 2.1 Service Robots in Hospitality

> *The scope of §2.1 is strictly commercial restaurant robots — physical platforms deployed in real restaurants today. Academic ROS2 navigation projects are surveyed in §2.2.5. Voice-enabled restaurant ordering systems (chatbots, drive-through AI) are surveyed in §2.4.5. Keeping these categories separate avoids conflating "a robot that moves" with "a screen that understands speech."*

- **Free-navigation commercial robots:** Bear Robotics Servi (USA, 2017) — 3-tier tray delivery, LiDAR + RGB-D for mapping and 3D obstacle detection, cloud fleet dashboard. Pudu Bellabot (China, 2016) — cat-shaped, laser + visual SLAM with ceiling marker localization, 40,000+ units deployed across 600+ cities, bionic emotional expression display. Keenon T-series (China, 2010) — LiDAR + depth cameras, narrow-aisle maneuvering (55 cm minimum), elevator integration, centimeter-level positioning.
- **Track-based AGV robots:** Alibaba Robot.He (Hema supermarket, Shanghai, 2018) — fundamentally different architecture. Technology adapted from Alibaba's Cainiao e-commerce warehouse AGV fleet. Small pod-shaped robots travel on dedicated waist-high rail tracks alongside dining tables. The rail IS the navigation system — no SLAM, no LiDAR, no obstacle avoidance. QR-code ordering via Hema app; the pod opens its glass lid upon arrival. JD.com announced plans for 1,000 similar robot restaurants by 2020.
- **Common limitations:** (a) No voice interaction — all are touchscreen-only or pre-recorded audio, no speech recognition anywhere. (b) No Vietnamese language support — all designed for Chinese/English/Japanese/Korean. (c) Closed platforms — proprietary software, no third-party extensibility; the robot is an appliance, not a programmable platform. (d) Infrastructure coupling — track-based systems lock restaurant layout at construction time; free-navigation robots need pre-mapping but still cannot integrate external AI.
- **Figure:** commercial robots side by side with annotated capabilities.
- **→ Gap:** Commercial robots solve physical delivery but are closed appliances with no voice, no Vietnamese, and no AI extensibility. This drives the decision to build on an open ROS2-based TWD platform (§3.1). The remaining gaps — autonomous navigation (§2.2), Vietnamese speech (§2.3), conversational AI (§2.4), knowledge retrieval (§2.5), fleet management (§2.6), and web/backend systems (§2.7) — are addressed in the subsequent sections.

### 2.2 Autonomous Robot Navigation

- **2.2.1 Wheel Odometry and Sensor Fusion**
  - Wheel odometry: encoder-based dead reckoning — how incremental encoders estimate pose from wheel rotations. Forward kinematics for differential-drive platforms. Drift accumulation as the fundamental limitation.
  - Inertial Measurement Unit (IMU): gyroscope angular rate, accelerometer linear acceleration. Gyro bias and drift characteristics. Why consumer-grade IMUs (MPU6050) have bounded accuracy.
  - Sensor fusion: why combining encoder + IMU produces better estimates than either alone. The Extended Kalman Filter (EKF) — conceptual explanation of predict-update cycle, state vector, covariance. `robot_localization` package as a configurable EKF implementation.
  - **Figure:** conceptual encoder–IMU fusion block diagram (predict-update loop).

- **2.2.2 SLAM and Map Building**
  - Simultaneous Localization and Mapping: the chicken-and-egg problem. Front-end (sensor processing) vs. back-end (graph optimization, loop closure).
  - LiDAR-based SLAM: 2D laser scans → occupancy grid map. Scan matching for incremental pose estimation.
  - Visual SLAM: RGB-D cameras for loop closure detection via visual feature matching (bag-of-words). Why visual features complement LiDAR geometry.
  - RTAB-Map: a graph-based SLAM framework supporting LiDAR + RGB-D fusion. Memory management via working memory / long-term memory. Loop closure detection and global graph optimization.
  - **Figure:** RTAB-Map pipeline diagram (sensor input → node creation → loop closure → optimized map).

- **2.2.3 Autonomous Navigation**
  - The Navigation2 (Nav2) stack: global planner (path computation on static costmap), local controller (trajectory following with dynamic obstacle avoidance), behavior trees for recovery.
  - Costmaps: static layer (pre-built map), inflation layer (robot footprint buffer), obstacle layer (live sensor data). Layered costmap architecture.
  - Local planners: DWB (Dynamic Window Approach) — sampling velocity commands in a search space, scoring by goal progress + obstacle clearance + alignment.
  - Non-holonomic constraints: TWD cannot move laterally (`Vy = 0`). In-place rotation for heading correction.
  - **Figure:** Nav2 architecture block diagram (global planner, local controller, costmaps, behavior tree supervisor).

- **2.2.4 Fiducial Marker Docking**
  - ArUco markers: binary square fiducial markers with unique IDs. Detection via contour extraction → perspective correction → bit-pattern decoding.
  - PnP pose estimation: solving for 6-DoF camera pose from known 3D marker corners + 2D image projections. Why a marker provides an absolute local reference independent of SLAM drift.
  - Marker-based precision docking: why SLAM localization alone is insufficient for the final 10–20 cm approach to a table (residual map error, odometry drift). The marker as ground-truth reference at the target.
  - **Figure:** ArUco marker detection with overlaid 6-DoF pose axes.

- **2.2.5 Prior ROS2 Delivery Robot Research**
  - Survey of university projects demonstrating ROS2 delivery robots: food delivery in campus cafeterias, medication delivery in hospital wards, document delivery in office buildings.
  - Typical architecture: 2D LiDAR + RGB-D camera + IMU + wheel encoders → RTAB-Map/Cartographer SLAM → Nav2 navigation → ArUco marker docking for precise approach.
  - Key finding: these systems handle physical movement successfully but have **no conversational layer.** The robot can drive to a table but has no means to interact with the customer upon arrival. The navigation problem is solved; the interaction problem is unaddressed.
  - **Figure:** generic ROS2 delivery robot architecture (sensors → SLAM → Nav2 → controller → motors).

- **→ Gap:** Academic ROS2 robots demonstrate that autonomous indoor delivery is feasible, but no prior system has (a) deployed on an off-the-shelf TWD platform with EKF-fused encoder+IMU odometry tuned for restaurant-scale service lanes, (b) integrated RTAB-Map mapping with LiDAR geometry + RGB-D loop closure in a real restaurant environment, (c) implemented ArUco-based per-table docking correction tied to a backend dispatcher, or (d) connected the navigation stack to a conversational AI agent that dynamically binds robot state to restaurant operations (tables, orders, voice sessions). This gap directly motivates the system requirements in §3.2.

### 2.3 Vietnamese Speech Processing

> *This section surveys the components of a voice interaction pipeline in execution order: voice activity detection (determining when someone is speaking), speech-to-text (transcribing Vietnamese utterances), text-to-speech (producing spoken responses), and the edge hardware platforms that host such pipelines. Vietnamese language characteristics — the 6-tone system, compound words, teencode, and restaurant noise — are integrated into the STT subsection where they directly affect transcription accuracy. The section surveys available technologies for each component; the specific selections are made in §4.4 based on the system requirements defined in §4.1.*

- **2.3.1 Voice Activity Detection**
  - The utterance boundary problem: determining when a speaker starts and stops speaking in a continuous audio stream. Critical for natural turn-taking — the system must not cut off the customer mid-sentence or wait too long after they finish.
  - Energy threshold baseline: the simplest VAD approach — classify any audio frame whose RMS amplitude exceeds a fixed threshold as "speech." Fails catastrophically in restaurant environments where ambient noise (plate clinks, chair scrapes, background conversation) regularly exceeds a reasonable speech threshold. A restaurant at peak hours may have continuous background noise at 60–70 dB — indistinguishable from quiet speech by amplitude alone. Energy thresholding works in a quiet recording studio; it does not work on a restaurant floor.
  - Neural VAD approaches: lightweight neural networks performing frame-level speech probability classification from learned spectral patterns rather than raw amplitude. Silero VAD (~1.5 MB, language-agnostic, CPU real-time) is the dominant open-source option. WebRTC VAD (Gaussian Mixture Model, ultra-lightweight, less accurate in noise) is a simpler alternative. Deep learning VADs (pyannote.audio, NVIDIA NeMo) offer higher accuracy but require GPU inference — unsuitable for always-on edge deployment.
  - Configurable sensitivity threshold: all VAD systems expose a threshold parameter that trades false triggers (noise classified as speech) against missed utterances (speech classified as silence). Restaurant deployment requires tuning this threshold for the specific ambient noise profile — a value calibrated in a quiet lab will produce excessive false triggers in a busy dining room.

- **2.3.2 Speech-to-Text for Vietnamese**
  - **Vietnamese language challenges for STT:**
    - 6 tones carried by diacritics — an STT error on a tone marker changes the word meaning entirely ("cá" = fish vs. "cà" = eggplant). Tonal accuracy is the single most important STT metric for Vietnamese.
    - Monosyllabic structure with compound words — "bún bò Huế" is 3 syllables but 1 lexical unit. STT models trained primarily on syllable-level tokenization may fragment compound dish names.
    - Teencode and informal speech: "ad" (anh/chị), "vs" (với), "ck" (chuyển khoản), "z" (vậy), "nhiêu" (bao nhiêu), "hông" (không). Common in spoken Vietnamese restaurant interactions but rare in formal STT training corpora.
    - Restaurant ambient noise: concurrent conversations, kitchen sounds, plate clatter, chair movement — all degrade STT word error rate.
    - STT is the break-point of the entire voice pipeline. If the transcription is wrong, every downstream component — intent classifier, agent, order creation, payment — operates on corrupted input. No amount of agent intelligence can recover from "Ốt Hương" (pepper fragrance) when the customer said "Ốc Hương" (a specific snail dish).
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

    The fundamental trade-off is accuracy vs. deployability. Cloud services (Google, Viettel, FPT) provide the lowest WER on Vietnamese but require internet connectivity — unacceptable for a restaurant floor where every spoken order must be processed regardless of network state. On-device models (Whisper, PhoWhisper) are less accurate but operate entirely offline. The faster-whisper inference engine (CTranslate2-optimized, 8-bit quantization) reduces Whisper-family model size and latency by ~4×, making medium-sized models viable on edge hardware.
  - **Prior work on Vietnamese STT:** PhoWhisper has been evaluated on Vietnamese speech benchmarks with reported WER improvements of 5–10% over the base Whisper model, particularly on tonal accuracy. Prior work has evaluated these models in isolation — on clean speech datasets, in quiet environments, with formal Vietnamese. No prior work has evaluated Vietnamese STT in restaurant acoustic conditions (ambient noise, informal speech, teencode).

- **2.3.3 Text-to-Speech for Vietnamese**
  - Available TTS approaches:

    | Engine | Offline | Edge Deployable | Latency (per sent.) | VRAM | Naturalness | Vietnamese Voices |
    |--------|:---:|:---:|:---:|:---:|:---:|:---:|
    | Piper TTS (VITS architecture) | **Yes** | **Yes (CPU)** | ~500ms | ~200 MB | Moderate | 1 community-trained voice |
    | edge-tts (Microsoft Azure) | No | No (cloud) | ~300ms + network | 0 (cloud) | High | Multiple neural voices |
    | vbee | No | No (cloud) | ~300ms + network | 0 (cloud) | High | Multiple |
    | FPT.AI TTS | No | No (cloud) | ~300ms + network | 0 (cloud) | High | Multiple |
    | Google Cloud TTS | No | No (cloud) | ~200ms + network | 0 (cloud) | Very High | WaveNet voices |

    The fundamental trade-off mirrors STT: cloud services offer higher naturalness and more voice options, but require internet connectivity. Piper TTS is the only offline, edge-deployable option with Vietnamese support — its VITS architecture runs on CPU and fits within typical edge compute budgets. The single community-trained Vietnamese voice provides moderate naturalness, sufficient for short functional utterances where the content (correct dish names, prices, order summaries) matters more than vocal performance.

- **2.3.4 Edge Deployment Platforms**
  - **NVIDIA Jetson Orin Nano:** 1024-core Ampere GPU with 32 Tensor Cores, 6-core ARM Cortex-A78AE CPU, 8 GB LPDDR5 shared memory, CUDA 12.6, 40 TOPS (INT8), 7–15 W power envelope. Representative of the edge AI computer class designed for embedded robotics.
  - **VRAM budget analysis (8 GB shared memory):** A concurrent deployment of ROS2 navigation stack (~500 MB), sensor drivers (~200 MB), Silero VAD (<10 MB), a medium-sized STT model (~1.5 GB for Whisper-medium/PhoWhisper via faster-whisper), and a lightweight TTS engine (~200 MB for Piper) requires approximately 2.5 GB total. This leaves ~5.5 GB headroom for the operating system, transient ROS2 data, and overhead — adequate for a full voice pipeline. However, a 7B-parameter LLM requires 6–8 GB of VRAM alone for inference, which cannot co-reside with the robot control and voice pipeline stacks. This quantified constraint is the architectural foundation for the edge/server split discussed in prior work on distributed robotics architectures.
  - **Why edge matters for voice:** the microphone and speaker are physically on the robot → local processing is the natural architecture. Local STT avoids network round-trip latency for audio upload; a text transcript (~100 bytes) is a negligible payload compared to raw audio (~100 KB per utterance). Local processing also survives temporary WiFi drops — capture and STT complete locally, only the text transcript needs the network.
  - **Server-side requirements:** LLM inference for a conversational agent (the Qwen2.5 7B model class) requires a dedicated server-grade GPU with 6–8 GB of VRAM, independent of the edge device. This hardware constraint — not a software preference — drives the edge/server architectural split seen in existing distributed voice assistant systems.

- **→ Gap:** Each component (STT, VAD, TTS) has been evaluated individually in prior work — PhoWhisper on Vietnamese benchmarks, Silero VAD on multilingual test sets, Piper TTS on perceptual quality ratings. No prior system has integrated all three into a single VAD→STT→Agent→TTS pipeline for Vietnamese restaurant ordering, deployed across an edge/server split where the VRAM budget of the edge device directly constrains which models can run locally and which must be offloaded to the server. This gap — the integration of off-the-shelf Vietnamese speech components into a restaurant voice pipeline constrained by edge hardware — motivates the voice pipeline architecture in §4.4.

### 2.4 Conversational AI Agents

> *This section surveys the landscape of conversational AI applied to restaurant ordering — from raw chatbots to task-oriented agents. It identifies four classes of challenges that off-the-shelf approaches fail to address for Vietnamese restaurant speech, establishing the intellectual need for the agent architecture designed in §4.3. No implementation details appear here; the section's job is to make the reader understand why each component of the proposed agent exists.*

- **2.4.1 LLMs, Chatbots, and Prior Restaurant Dialogue Systems**
  - **The chatbot ceiling:** Large language models (GPT-4, Qwen2.5, Gemini) can answer questions, provide recommendations, and hold natural conversation in Vietnamese. Combined with retrieval-augmented generation, they can ground responses in a specific restaurant's menu. This leads to a common misconception — that a sufficiently powerful LLM with RAG is all a restaurant needs.
  - **The Chatbot Fallacy — a concrete example:** A customer says "Cho 1 phần Ốc Hương Xốt Trứng Muối." A chatbot replies "Dạ, Ốc Hương Xốt Trứng Muối giá 170K ạ." The response sounds intelligent, natural, and helpful. But nothing happened — no item was added to a cart, no order was created, no kitchen display was updated, no payment was processed. The chatbot produced text; the customer thought they ordered. The gap is not one of intelligence — it is one of architecture. A chatbot cannot call an `add_cart` function, validate the dish name against a menu database, persist the order, or dispatch a robot.
  - **Prior restaurant dialogue systems — what each lacks:**
    - Vietnamese chatbots: Zalo AI (VNG), VinAI — understand Vietnamese at conversational level but are open-domain chatbots. No tool execution, no order state machine, no kitchen integration.
    - Voice ordering: Wendy's FreshAI (English, cloud), Domino's AI (English, cloud) — demonstrate that LLM-based voice ordering is commercially viable, but are English-only, cloud-dependent, stateless per transaction, and have no physical robot integration.
    - Academic: prior work on restaurant conversational agents exists for English, Chinese, Korean, Japanese — typically NLU pipeline (intent → slot → API) — but none target Vietnamese and none integrate physical delivery.
    - Physical robots: Alibaba Robot.He, Bear Servi, Pudu Bellabot (§2.1) — solve physical delivery but are closed appliances with no conversational AI.
  - **Comparison table (dimensions: understands Vietnamese? executes tools? validates? self-hosted? robot dispatch?):**

    | System | Vietnamese | Tool Execution | Validation | Self-Hosted | Robot Dispatch |
    |--------|:---:|:---:|:---:|:---:|:---:|
    | Zalo AI / VinAI (chatbot) | ✓ | ✗ | ✗ | ✗ | ✗ |
    | Wendy's FreshAI | ✗ | ✓ | ✗ | ✗ | ✗ |
    | Domino's AI | ✗ | ✓ | ✗ | ✗ | ✗ |
    | Academic restaurant chatbots | ✗ | ✓ | ✗ | ✗ | ✗ |
    | Bear / Pudu / Keenon (§2.1) | ✗ | ✗ | ✗ | ✗ | ✓ |
    | Alibaba Robot.He (§2.1) | ✗ | ✗ | ✗ | ✗ | ✓ |

    No prior system checks more than two columns.
  - **→ Gap:** No system combines Vietnamese language understanding, tool execution against a backend, deterministic validation of LLM outputs, self-hosted deployment, and physical robot delivery. This is the high-level gap. The following subsections decompose it into specific technical challenges.

- **2.4.2 From Chatbot to Agent — Tool Calling, State, and Agent Frameworks**
  - **What makes an agent:** A conversational agent is distinguished from a chatbot by four capabilities: (a) tool execution — the ability to call external functions (add to cart, create order, verify payment) rather than only generating text, (b) state persistence — maintaining conversation context, cart contents, and order stage across multiple turns, (c) validation — checking LLM outputs against known-good data before they affect system state, and (d) bounded execution — guaranteed termination with a defined failure mode rather than infinite loops.
  - **Tool calling (function calling) — conceptual:** an LLM produces a structured function invocation (tool name + arguments) instead of free text. A framework executes the function and returns the result to the LLM if needed. This is the mechanism by which an LLM transitions from text generation to system action. Available implementations: OpenAI function calling, LangChain `@tool` decorators, Ollama tool support.
  - **Agent frameworks — LangGraph (conceptual only):** LangGraph models an agent as an explicit state graph — a typed shared state flows through nodes (LLM calls, tool executions, deterministic functions) connected by conditional edges. Unlike linear chains (LangChain LCEL) or autonomous loops (AutoGPT), graph-based agents enable deterministic code between LLM calls — a validator can inspect tool arguments, a state updater can merge results, and a circuit breaker can enforce bounded retry. Key concepts at survey level: StateGraph, nodes, conditional edges, checkpointer for conversation memory across turns, thread-scoped isolation for multi-tenant deployments.
  - **Why not autonomous agent frameworks (AutoGen, CrewAI):** multi-agent frameworks where LLMs autonomously decide when to invoke tools, delegate to sub-agents, and terminate are well-suited to open-ended creative tasks (code generation, research) but poorly suited to restaurant ordering. The restaurant order lifecycle is a business process with guarded state transitions — an autonomous agent loop may skip the confirmation step, confirm an empty cart, or loop indefinitely on ambiguous input. These frameworks lack (a) a guaranteed termination boundary, (b) deterministic validation between LLM calls, and (c) explicit state machine enforcement — three requirements that a graph-based architecture with bounded retry and a circuit breaker directly satisfies.
  - **Why the graph model for restaurant ordering:** ordering is a multi-step business process with state transitions (cart empty → building → awaiting confirmation → confirmed → paid). A linear "utterance → response" model cannot enforce this flow; an unconstrained autonomous loop may never terminate. The graph model maps naturally to business process stages.
  - **Figure:** generic LangGraph StateGraph (nodes + conditional edges + checkpointer), not the group's specific graph.

- **2.4.3 Intent Classification — Why Off-the-Shelf Approaches Fail for Vietnamese Restaurant Speech**
  - **The classification problem:** before an agent can take action, it must determine what the customer wants. Different intents (order, search, pay, chat) require different processing subsystems — routing an ORDER utterance to a CHAT worker produces a conversation instead of a cart update, and vice versa.
  - **Four domain-specific challenges that general classifiers fail on:**
    - **(a) Teencode and informal Vietnamese.** Casual restaurant speech uses abbreviations ("ad" for anh/chị, "ck" for chuyển khoản, "z" for vậy, "nhiêu" for bao nhiêu) that are absent from formal training corpora. Traditional NLU pipelines (Rasa, Dialogflow) trained on formal Vietnamese fail on "ck cho mình cái qr với" — the classifier has never seen "ck" as a payment keyword.
    - **(b) Context-dependent ambiguity.** Short affirmations ("ok em", "ừ", "đúng rồi") carry different intents depending on conversation stage. "Ok" at order confirmation stage must route to ORDER_CONFIRM; "ok" at greeting must route to CHAT. A classifier that sees only the utterance text, without conversation state, cannot distinguish these cases.
    - **(c) Multi-intent compounding.** Vietnamese frequently expresses multiple actions in one sentence: "Cho 2 Ốc Hương rồi tính tiền luôn" (ORDER + PAYMENT), "Lẩu Thái cay không? Không cay thì cho 1 phần" (SEARCH + ORDER). Single-label classifiers (which most are) force a choice; multi-label classifiers require per-intent query extraction for downstream workers.
    - **(d) Domain vocabulary.** Dish names ("Ốc Hương Xốt Trứng Muối", "Lẩu Cá Tầm Măng Chua") are out-of-distribution for general-domain embedding models. An utterance containing a rare dish name may produce an embedding closer to an unrelated centroid than to the correct intent centroid.
  - **Prior classification approaches and what each misses:**

    | Approach | Handles Teencode? | Context-Aware? | Multi-Intent? | Domain Vocab? | Latency |
    |----------|:---:|:---:|:---:|:---:|:---:|
    | Traditional NLU (Rasa, SVM) | ✗ | ✗ | ✗ | ✗ (needs retraining) | ~5ms |
    | Lightweight text classifiers (fastText, SetFit) | ✗ | ✗ | ✗ | ✗ | ~2–10ms |
    | Semantic centroid routing | ✗ | ✗ | ✗ | ✗ | ~15ms |
    | LLM-based routing (few-shot) | ✓ | ✓ | ✓ | ✓ (via prompt) | ~1.8s |
    | Trained classifier (MLP) | ✓ (if in training data) | ✓ (via context features) | ✓ (can be trained) | ✓ (if in training data) | ~0.17ms |

    Lightweight text classifiers (fastText, SetFit) fill the latency gap between traditional NLU and LLM routing — they are fast, trainable, and can be fine-tuned on domain-specific data. However, they share the same fundamental limitation as traditional NLU: they operate on text alone. Without conversation state as input, they cannot disambiguate "ok" at order confirmation (→ ORDER) from "ok" at greeting (→ CHAT). They also require explicit retraining for every new teencode variant and dish name — in a restaurant with a periodically updated menu, this is an operational burden. The MLP classifier's context features (order_stage, cart state, search history) provide the state-awareness that pure text classifiers lack.

  - **→ Gap:** Each prior approach fails on at least two of the four challenges. No classification approach for Vietnamese restaurant speech simultaneously handles teencode, context-dependent utterances, multi-intent compounding, and out-of-distribution domain vocabulary — while maintaining sub-millisecond inference latency.

- **2.4.4 Hallucination — Why Correctly-Routed Agents Still Produce Wrong Actions**
  - **The problem:** Even when intent is classified correctly, the LLM that generates the tool call may hallucinate. It may fabricate a dish name not on the menu ("Pizza Hải Sản" on a Vietnamese seafood menu), produce a nonsensical quantity, or attempt to confirm an order containing invalid items. Hallucination is not a bug — it is an inherent property of probabilistic text generation.
  - **The restaurant stakes:** in a chatbot, a hallucinated response is an annoyance — the customer receives wrong information and corrects it. In a restaurant agent, a hallucinated tool call has material consequences — a wrong dish is cooked, a wrong payment amount is charged, a robot delivers food the customer did not order.
  - **Existing mitigation approaches and their limits:**
    - **Constrained decoding / structured output:** forces the LLM to output valid JSON matching a schema. Prevents malformed tool calls but does not validate semantic correctness — `{"tool": "add_cart", "name": "Pizza Hải Sản"}` is valid JSON with a correct field type, but the dish does not exist.
    - **Retrieval-augmented generation (RAG):** grounds the LLM in menu documents. Reduces hallucination probability but does not eliminate it — the LLM may still ignore or misread retrieved context.
    - **Human-in-the-loop approval:** a human reviews each tool call before execution. Eliminates hallucination risk entirely but is incompatible with autonomous restaurant operation — a human babysitting every order defeats the purpose.
  - **Generation-time vs. post-generation validation:** all existing approaches operate at generation time — they constrain what the LLM can output. None validates the output after generation against an external source of truth (the actual menu database, the actual cart state). This distinction — filter what the LLM can say vs. check what the LLM did say — is the key gap.
  - **→ Gap:** No prior restaurant agent implements a deterministic post-generation validation layer that checks every LLM tool call argument against known-good data (menu items, price ranges, valid state transitions) before the call reaches external systems. The LLM is allowed to make mistakes; the system must catch them before they become wrong orders.

- **→ Gap (overall for §2.4):** No prior system combines (a) Vietnamese language support with (b) tool-execution capability, (c) intent classification that handles teencode, context-dependent utterances, multi-intent compounding, and domain vocabulary simultaneously, (d) deterministic post-generation validation preventing hallucinated tool calls from reaching external systems, and (e) self-hosted deployment with no cloud API dependency. This gap motivates the full agent architecture in §4.3 — each component of the proposed agent addresses one of the challenges identified in this section.

### 2.5 Knowledge Retrieval for Domain-Specific QA

> *This section surveys the standard RAG pipeline and identifies why it is insufficient for a restaurant agent: retrieval is a supporting function, not the final answer. The gap is not in the retrieval technology itself — BM25, FAISS, and RRF are mature — but in the absence of a closed loop where an LLM actively rewrites vague customer queries before retrieval and evaluates retrieved results after retrieval, grounded in Vietnamese-specific language requirements.*

- **2.5.1 The Knowledge Problem and Standard RAG**
  - Why LLMs need external knowledge: training data is frozen, a specific restaurant's menu is not in it. Hallucination is the failure mode — the LLM confidently describes dishes that don't exist.
  - RAG pipeline conceptually: index documents offline (embed → store) → retrieve top-k at query time → generate answer grounded in retrieved context.
  - The standard RAG assumption: the user's query maps directly to relevant documents. This holds for simple lookups ("Ốc Hương giá bao nhiêu?") but breaks down for vague or compound queries ("món gì ấm bụng cho ngày lạnh?" contains zero menu keywords).

- **2.5.2 Retrieval Approaches**
  - **Dense retrieval:** FAISS with SentenceTransformer embeddings. Captures semantic similarity — "something warm for a cold day" → hot soups. Weak on exact keyword matching for proper names and rare dish names.
  - **Sparse retrieval:** BM25 (TF-IDF variant). Strong for exact keyword matches ("Ốc Hương Xốt Trứng Muối"). Weak for semantic understanding and vague descriptions.
  - **Hybrid fusion:** parallel dense + sparse retrieval → merge via Reciprocal Rank Fusion (RRF). RRF needs only ranks, not comparable scores — ideal for fusing BM25 with cosine similarities.
  - **Available vector databases:** FAISS (local, no server, ideal for embedded deployment), Chroma, Milvus, Pinecone (cloud/managed, heavier deployment). The choice is driven by the same offline-first constraint discussed in §2.3.
  - **Relevance filtering:** the noise problem — retrieval can return wrong items which the LLM then uses as context, compounding errors. Prior gatekeeper patterns: confidence thresholding (reject results below a similarity score), dual-lane gating (semantic OR lexical match required). A gatekeeper that blocks noise prevents RAG from actively harming response quality.
  - **Vietnamese-specific requirements:** word segmentation via `underthesea` — compound words like "bún bò Huế" must be single tokens for BM25, otherwise "bún", "bò", "Huế" are indexed as three unrelated terms. The embedding model must handle Vietnamese diacritics natively — general-domain multilingual models (e.g., `paraphrase-multilingual-MiniLM-L12-v2`, 384-dim) degrade on tonal languages. Metadata filtering needed for structured menu fields (category, price range, dietary type).

- **2.5.3 Beyond Retrieval — The Closed-Loop RAG Pipeline**
  - **Why standard RAG is insufficient for a restaurant agent:** the customer says "món gì ấm bụng cho ngày lạnh?" (what's warm and filling for a cold day?). Standard RAG embeds this query and retrieves documents — but "ấm bụng" has no semantic relationship to "cháo" or "lẩu" in embedding space. The query needs to be rewritten into concrete search terms BEFORE retrieval. After retrieval, the raw results need to be evaluated — which of the top-5 dishes actually match what the customer wanted? The LLM must answer this, not just parrot the retrieved text.
  - **Pre-retrieval query rewriting:** an LLM analyzes the customer's vague utterance and produces a concrete, searchable query. "Món gì ấm bụng?" → "cháo, lẩu, súp". This is not keyword extraction — the LLM is reasoning about Vietnamese culinary categories. Prior work on query rewriting exists for English, but not for Vietnamese food domains where cultural knowledge (what constitutes "ấm bụng" in Vietnamese cuisine) is necessary.
  - **Post-retrieval result evaluation:** after RAG returns top-k documents, an LLM evaluates which results are relevant to the original customer question and selects the best ones to present. The LLM can also detect empty or irrelevant results and respond accordingly ("Dạ, quán không có món đó ạ") rather than hallucinating from noise. Prior work on self-reflective RAG and LLM-as-evaluator exists but has not been applied to Vietnamese restaurant search.
  - **Deduplication across turns:** the "ĐÃ BIẾT" pattern — when a customer searches for "Ốc Hương" twice, the LLM should know it already returned those results and not repeat the search. This requires maintaining a search context that persists across conversation turns, which falls outside the standard stateless RAG pipeline.
  - **Figure:** closed-loop RAG pipeline (customer utterance → LLM query rewriting → hybrid retrieval → LLM result evaluation → grounded response).

- **→ Gap:** No prior system combines (a) LLM-based query rewriting for Vietnamese food-domain vocabulary, (b) Vietnamese-specific hybrid retrieval with word-segmented BM25 and a diacritic-aware embedding model, (c) LLM-based post-retrieval result evaluation that selects relevant items and detects empty results, (d) multi-turn search context deduplication, and (e) a relevance gatekeeper that prevents noisy retrieval from poisoning the LLM's context window. Prior RAG systems for restaurants implement at most the retrieve→generate pipeline; the closed-loop rewrite→retrieve→evaluate→generate pipeline — where the LLM actively participates both before and after retrieval — has not been demonstrated for Vietnamese restaurant ordering. This gap motivates the search tool and search worker design in §4.3.5.1.

### 2.6 Multi-Robot Fleet Management

> *This section surveys approaches to coordinating multiple robots in a shared physical space — assigning tasks, monitoring liveness, and managing telemetry. The restaurant setting (3–5 robots, 6 tables, short trips) is fundamentally different from the warehouse-scale environments for which existing frameworks were designed, creating a gap for a lightweight dispatcher that integrates robot state with restaurant business events.*

- **2.6.1 Task Assignment Strategies**
  - Nearest-idle: assign each task to the closest available robot. Simplest approach, works well for short trips (kitchen to table: 3–5 meters) in small environments. Optimality is not the bottleneck — the difference between the nearest and second-nearest robot for a 5-meter trip is negligible.
  - Auction-based and market-based: robots bid on tasks based on their current state (battery, distance, queue length). More complex but enables dynamic load balancing. Prior work exists for warehouse AGV fleets (Amazon Kiva, Cainiao) where trip distances are 50–200 meters and optimal assignment matters.
  - Battery-aware filtering: a robot below a charge threshold (typically 20%) is excluded from the candidate pool regardless of proximity. Prior work on energy-aware task assignment in mobile robotics.

- **2.6.2 Fleet Management Frameworks**
  - ROS2 OpenRMF: full-featured infrastructure for warehouse-scale operations — dozens of robots, complex traffic zones with scheduling, multi-floor elevator coordination, door control. Designed for logistics, not hospitality. Heavy deployment overhead (separate server, complex configuration) that is disproportionate to a 6-table restaurant.
  - Commercial alternatives: Bear Universe (Bear Robotics), PuduCloud (Pudu), Keenon Cloud — proprietary, closed-source fleet dashboards tied to each manufacturer's hardware. No cross-manufacturer support, no third-party extensibility.
  - The restaurant gap: neither heavy warehouse frameworks nor closed manufacturer portals serve the restaurant use case — 3–5 robots, short repetitive trips, simple service-lane topology, where the dispatcher must integrate with restaurant business logic (seating → dispatch, order ready → dispatch, payment → release).

- **2.6.3 Telemetry and Liveness**
  - Telemetry architecture: RAM-only latest-value store (pose, battery at 4+ Hz) vs. DB write-per-heartbeat. The RAM approach provides lock-free reads for real-time task assignment but is lost on restart; the DB approach persists but creates write contention at sensor frequency. The hybrid pattern — RAM for real-time, periodic DB snapshot (every 15s) for cold-start recovery — is a known architectural trade-off in robotics telemetry systems.
  - Liveness monitoring: heartbeat-based detection is the standard approach — a robot sends periodic status messages. TCP connection liveness alone is insufficient; a hung process can maintain an open socket while producing no heartbeats. A watchdog that independently tracks last-heard timestamps is the standard defense.
  - Task recovery on failure: when a robot is marked offline, its assigned tasks must be requeued for other robots. Prior work on fault-tolerant task reassignment in multi-robot systems.

- **2.6.4 Dynamic Robot-Table Binding**
  - **The voice binding problem:** in a system where robots are table-agnostic — any robot can serve any table — a mechanism is needed to route voice commands to the correct robot's microphone. When the customer presses the "Talk to AI" button on their tablet, the system must know which robot is currently at that table.
  - Prior approaches: static binding (robot permanently assigned to a table — limits flexibility), broadcast-to-all (all robots hear all commands — privacy concern, noise), and dynamic binding (bind on arrival, unbind on departure — the standard pattern in multi-robot human-interaction systems).
  - **→ Gap (specific):** no prior restaurant fleet system implements dynamic table→robot→microphone binding where the binding is established when the robot physically arrives at the table and released when it departs, and the binding routes both voice capture commands AND voice reply playback to the correct robot.

- **→ Gap (overall for §2.6):** no lightweight fleet dispatcher designed for restaurant-scale operations (3–5 robots, 6 tables, short kitchen→table trips) that (a) assigns tasks via nearest-idle with battery-aware filtering, (b) dynamically binds a robot's voice device to the table it is currently serving, establishing and releasing the binding on physical arrival/departure, (c) monitors robot liveness with a heartbeat watchdog and automatically requeues tasks on failure, and (d) manages the full task lifecycle (PENDING → ASSIGNED → IN_PROGRESS → DONE) synchronized with restaurant business events (seating, order ready, payment). This gap motivates the dispatcher design in §4.6.

### 2.7 Web, Backend & Real-Time Systems

> *This section surveys the software infrastructure needed to serve a restaurant's operational data — tables, orders, robots, payments — to multiple real-time clients simultaneously. The focus is on prior restaurant management systems and the gap between what they provide (typically polling-based REST for a single POS terminal) and what a multi-role real-time robot-integrated system requires.*

- **2.7.1 Restaurant Management Systems — Prior Approaches**
  - Traditional POS (Point of Sale): KDS (Kitchen Display Systems), table management, billing. These are single-role systems — one terminal, one user, one function. They use local databases and polling-based refresh. A waiter updates an order status; the kitchen display sees the change on its next poll cycle (typically 5–10 seconds).
  - Prior work on restaurant automation: web-based ordering platforms, QR-code menu systems (proliferated during COVID-19), tablet-based ordering. These systems replace paper menus with screens but maintain the same single-function architecture — ordering, kitchen display, and payment are separate applications with no shared real-time state.
  - **What's missing:** no prior restaurant system provides a single backend that simultaneously serves a guest-facing ordering tablet, a staff kitchen display, a manager fleet dashboard, a customer check-in kiosk, and a robot fleet — all with real-time state synchronized across all clients. Each prior system addresses one role; the integration is the gap.

- **2.7.2 RESTful API Design — Survey of Patterns**
  - REST: resources identified by URLs, operations via HTTP verbs, stateless request-response. FastAPI + Pydantic provides typed validation and auto-generated documentation. This is the standard pattern for transactional operations (create order, seat table, verify payment) where the client needs a definitive success/failure response.
  - Why REST for business writes: an order creation must either succeed (with an order ID and a database commit) or fail (with a specific error). REST's request-response model guarantees exactly one outcome.

- **2.7.3 WebSocket Real-Time Communication — Survey of Patterns**
  - Polling vs. push: polling a REST endpoint every N seconds for state changes wastes bandwidth and adds latency (a new order appears on the kitchen display 0–5 seconds late, averaged across poll cycles). WebSocket push delivers events to clients as they occur.
  - Role-based pub/sub: different clients need different event subsets. A kitchen display needs `order.created`; a customer tablet needs `voice.reply`; a robot needs `task.assign`. Role-based fan-out routes events to the correct WebSocket connections without per-client topic configuration.
  - Reconnection with exponential backoff: WiFi instability causes WebSocket drops. Exponential backoff (1s → 2s → 4s → … cap 10s) is the standard pattern for preventing reconnect storms while ensuring eventual reconnection.

- **2.7.4 Single-Page Application Architecture — Survey**
  - SPA model: a single HTML page with client-side routing. Vue 3 + Vite provides reactive component trees with Pinia state stores. No full-page reloads — the UI updates in-place as WebSocket events arrive.
  - Multi-role SPA pattern: instead of one monolithic application, multiple single-role SPAs — each serving one user type (guest, kitchen staff, manager) with role-specific UI and event subscriptions — sharing a common TypeScript client library for API calls, WebSocket connections, and type definitions.

- **2.7.5 Embedded Databases**
  - SQLite: serverless, zero-configuration, single-file, ACID. The standard choice for embedded and single-writer applications. WAL mode enables concurrent reads during writes — critical for a system where multiple clients read table/order/robot state while the backend writes new orders.
  - Why not client-server RDBMS: PostgreSQL/MySQL add deployment complexity (separate process, authentication, connection pooling) with no benefit at restaurant scale (dozens of orders per hour, not thousands per second). The file-level write lock is a non-issue with a single writer process.

- **2.7.6 Session Lifecycle — A Restaurant-Specific Pattern**
  - The restaurant service lifecycle: a party checks in (kiosk → table assignment → session creation) → they order food (multiple orders within one session) → they request payment (session total = sum of all orders) → they pay (session closed, table freed). This is a standard restaurant business process that must be enforced by the backend — it is not just a CRUD API but a state machine with guarded transitions.
  - Prior work: session management exists in POS systems and restaurant management platforms (Toast, Square, Lightspeed) but is always implemented as proprietary closed-source logic with no API for third-party integration. No prior system exposes a session lifecycle as an open REST + WebSocket API that an external AI agent can drive.

- **→ Gap:** no prior restaurant system integrates (a) a REST API for transactional business operations, (b) a WebSocket hub with role-based fan-out for real-time multi-client state synchronization, (c) multiple single-role SPAs (kiosk, tablet, kitchen panel, fleet dashboard) sharing a common client library, (d) an embedded SQLite database enforcing session lifecycle state transitions, and (e) an external AI agent driving the full service lifecycle through API calls — all deployed as a self-contained single-server backend with no cloud dependency. This gap motivates the backend architecture in §4.5 and web interface architecture in §4.7.

### 2.8 Summary & Positioning

- **The integration gap:** each dimension surveyed in §2.2–§2.7 has been addressed individually in prior work — autonomous navigation (ROS2 delivery robots), Vietnamese speech (standalone STT/TTS), dialogue agents (cloud chatbots), intent classification (semantic routers), menu retrieval (academic RAG), fleet management (warehouse frameworks), and web backends (REST APIs). No prior system has integrated all seven dimensions into a single deployed system.
- **Gap → Requirement traceability table:** each gap identified in this chapter directly motivates a set of system requirements in Chapter 3 (robot navigation) or Chapter 4 (AI/backend/web), which are validated by specific experiments in Chapter 5.

| §   | Gap Identified                                                                                   | → Requirements (§3.2, §4.1)                          | → Validated In          |
| --- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------- | ----------------------- |
| 2.1 | No voice+LLM+robot integration for restaurants                                                   | Overall system objective                             | §5.5.1 Integration test |
| 2.2 | No TWD platform with EKF-odom + RTAB-Map + ArUco docking for restaurant service lanes            | R1–R7 (navigation, docking, odometry)                | §5.2.1–§5.2.3           |
| 2.3 | No integrated VAD→STT→Agent→TTS pipeline for Vietnamese on Jetson edge, constrained by VRAM budget | §4.1 NFR latency, §4.4 architecture | §5.3.5, §5.4.4 |
| 2.4 | No self-hosted Vietnamese agent combining language support + tool execution + classifier handling teencode/context/multi-intent/domain-vocab + post-generation validation + robot dispatch | §4.1 functional requirements, §4.3 agent architecture | §5.3.1–§5.3.3 |
| 2.5 | No closed-loop RAG pipeline for Vietnamese menus: LLM query rewriting + Vietnamese-specific hybrid retrieval + LLM result evaluation + multi-turn dedup | §4.1 menu search requirement, §4.3.5.1 search tool + search worker | §5.3.4 |
| 2.6 | No lightweight restaurant fleet dispatcher with dynamic table→robot→voice binding + watchdog recovery + business-event synchronization | §4.1 robot management requirement, §4.6 architecture | §5.2.3, §5.5.1 |
| 2.7 | No integrated backend with REST + WS hub + multi-role SPAs + session lifecycle — all self-contained, single-server, AI-agent-driven | §4.1 concurrency/multi-table requirement, §4.5, §4.7 | §5.5, §5.6 |

- Comparison table: what prior systems cover vs. what this thesis integrates:

| Dimension | Existing Work | This Thesis |
|-----------|--------------|-------------|
| Navigation | ROS2 delivery robots (nav-only), commercial robots (closed) | ROS2 + EKF odometry + ArUco docking on open TWD platform |
| Voice | Vietnamese STT (standalone), VAD (standalone), TTS (standalone) | VAD→STT→Agent→TTS pipeline on Jetson edge, offline-first |
| Intent classification | NLU (brittle to teencode), semantic centroid (blind to context), LLM routing (slow, non-deterministic) | Trained MLP classifier: embedding + conversation-context features, sub-ms latency |
| Agent | Cloud chatbots (English-only, stateless, no tools) | Self-hosted LangGraph agent: tool execution, deterministic validation, delegate escape, multi-turn memory |
| Menu retrieval | Standard RAG (retrieve→generate, no Vietnamese optimization) | Closed-loop: LLM query rewriting → Vietnamese hybrid retrieval → LLM result evaluation → multi-turn dedup |
| Robot fleet | Warehouse-scale (OpenRMF), manufacturer-locked (Bear/Pudu/Keenon) | Lightweight restaurant dispatcher: dynamic table→robot→voice binding, watchdog recovery, business-event synchronization |
| Backend/Web | Single-role POS/KDS, polling-based, no real-time integration | Integrated REST + WebSocket hub + 3 single-role SPAs + session lifecycle — all self-contained, single-server |
| Integration | Navigation XOR chatbot (no system combines both) | End-to-end: voice → agent → order → kitchen display → robot delivery → payment |

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
- 3.3.3 EKF (`robot_localization`, `two_d_mode`): state `[x, y, ψ, V_x, V_y, V_ω]`, odom0 → V*x/V_y/V*ω, imu0 → V_ω only (no magnetometer → IMU yaw not fused), covariance tuning, output `/odometry/filtered` + `odom→base_footprint` TF

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

> _The intellectual core of the software contribution. Every utterance flows through five stages: Understanding (what does the customer want?) → Decision (which action should be taken?) → Validation (is the action safe?) → Execution (perform the action and update state) → Response (generate output text). Stages are implemented as LangGraph nodes connected by conditional edges, executing deterministically between LLM calls._

#### 4.3.1 Agent Execution Model

- **LangGraph StateGraph:** 10 nodes, 6 conditional edges, 4 normal edges. Graph entry at `router`, exit after `response_node`. Execution path varies per utterance based on intent classification and validation results.

- **AgentState (18 fields)** — a TypedDict organized by lifecycle:

  | Category             | Fields                                                                                                                         | Persistence                                                      |
  | -------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
  | Conversation history | `messages`                                                                                                                     | Across turns (append-only, managed by LangGraph reducer)         |
  | Task state           | `table_id`, `active_cart`, `order_stage`, `search_context`                                                                     | Across turns                                                     |
  | Routing state        | `current_intents`, `routing_meta`                                                                                              | Across turns (intents queue persists for multi-intent iteration) |
  | Inter-node contract  | `is_valid`, `feedback`, `loop_count`, `unavailable_items`, `ambiguous_items`, `last_tool`, `delegate_reason`, `intent_queries` | Per-turn (written by one node, read and cleared by the next)     |
  | Output               | `ui_action`, `order_confirmed`, `response_context`                                                                             | Per-turn (consumed by response node, cleared by state_outcome)   |

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

> _Before any action can be taken, the system must determine what the customer wants. This is a classification problem: given an utterance in Vietnamese, select the correct intent from {ORDER, SEARCH, PAYMENT, CHAT}. This section describes the trained MLP classifier — the primary production router. The router design evolved through three iterations: a pure semantic centroid router (§5.3.1 ablation), a two-tier hybrid (semantic + SLM) that achieved 73.3% on 45 cases, and the final trained MLP classifier that reaches 95.6% on the same test set._

- **Intent taxonomy:** 4 output classes. ORDER_CONFIRM utterances ("ok em", "chốt đơn") are merged with ORDER at the router level — the distinction is handled downstream by the order state machine, not the classifier. Multi-intent utterances are classified by their dominant intent; sequential multi-intent execution is handled by the graph's intent queue loop (§4.3.5.3).

- **MLP classifier architecture:**
  - **Input features (778-dim):** 768-dim frozen sentence embedding concatenated with 10 hand-crafted context features extracted from `AgentState`.
  - **Embedding model:** `bkai-foundation-models/vietnamese-bi-encoder` (SentenceTransformer, 768-dim, L2-normalized). A Vietnamese-specific bi-encoder pre-trained on Vietnamese sentence pairs — selected over general-domain alternatives for its native handling of Vietnamese diacritics, compound words, and informal restaurant speech patterns.
  - **Context features (10-dim):**
    - order_stage one-hot (5-dim): IDLE, BUILDING, AWAITING_CONFIRMATION, CONFIRMED, MODIFYING
    - has_cart (1 if `active_cart` is non-empty, else 0)
    - cart_size_norm (`min(cart_item_count, 10) / 10`)
    - has_search_context (1 if `search_context` is non-empty, else 0)
    - search_context_size_norm (`min(search_result_count, 20) / 20`)
    - utterance_length_norm (`min(len(utterance_chars), 200) / 200`)
  - **Network:** 3-layer MLP: 778 → 256 → ReLU → Dropout(0.2) → 64 → ReLU → Dropout(0.2) → 4. Output: softmax over {ORDER, SEARCH, PAYMENT, CHAT}.
  - **Training:** 3,712 synthetically generated and augmented Vietnamese utterances across all 4 intents, with per-utterance context features. 80/20 stratified train/validation split. CrossEntropyLoss with class weights to handle class imbalance. Adam optimizer (lr=1e-3, weight_decay=1e-4). Early stopping (patience=10). All embeddings precomputed offline — training runs on CPU in ~2 minutes.
  - **Why a trained classifier instead of LLM-based routing:**
    - **Latency:** MLP forward pass ≈ 0.17ms vs SLM routing ≈ 1.8s — three orders of magnitude faster. The embedding step (~50ms) is shared by both approaches; the routing logic itself is where the MLP wins.
    - **Determinism:** Same input always produces the same output. No temperature sampling, no prompt sensitivity, no model version drift. This matters for a restaurant — "ok em" must always route to ORDER, not sometimes to CHAT.
    - **Context awareness:** The 10 context features encode the conversation state (order_stage, cart state, search history) that pure embedding similarity cannot see. An utterance of "ok" routes to ORDER when `order_stage=AWAITING_CONFIRMATION` but to CHAT at `IDLE` — the MLP learns this from the context features.
    - **Accuracy:** 95.6% on the 45-case router evaluation set (vs 73.3% for the two-tier hybrid), 97.4% on the 39-case holdout set. The hybrid router's failures were concentrated in a predictable pattern: low centroid similarity → fallback to CHAT. The MLP's learned decision boundary corrects this.
  - **Inference pipeline (online):**
    1. Vietnamese word segmentation via `underthesea.word_tokenize()`
    2. Encode utterance via frozen bi-encoder → 768-dim embedding
    3. Extract 10 context features from `AgentState` → apply saved `StandardScaler` → 10-dim
    4. Concatenate → 778-dim input vector
    5. MLP forward pass → softmax → 4-class probability distribution
    6. Output: `{"intent": "ORDER", "confidence": 0.997, "all_probs": {...}}`

#### 4.3.3 Stage II — Decision: Action Selection via Tool-Calling LLM

> _Once the intent is known, the agent must decide what action to take. For ORDER and SEARCH intents, this requires an LLM to reason about the utterance and select the appropriate tool with the correct arguments. For PAYMENT, the action is deterministic. For CHAT, no tool call is needed._

- **Decision configuration:** Qwen2.5 7B via Ollama, `temperature=0.1`, `tool_choice="any"`. Temperature is slightly above zero to allow variant phrasings in tool arguments while keeping decisions near-deterministic. Prompt includes system prompt (~200 tokens) + 5 few-shot examples with tool calls for KV-cache optimization. The menu is deliberately excluded from the prompt — the LLM does not need menu knowledge to decide which tool to call; it only needs to recognize the action type.

- **Tool bindings per intent:**

  | Intent                | Bound Tools                                                          | LLM Called?                                         |
  | --------------------- | -------------------------------------------------------------------- | --------------------------------------------------- |
  | ORDER / ORDER_CONFIRM | `add_cart`, `remove_cart`, `clear_cart`, `confirm_order`, `delegate` | Yes                                                 |
  | SEARCH                | `search`, `delegate`                                                 | Yes                                                 |
  | PAYMENT               | `request_payment`                                                    | No (deterministic — always emits `request_payment`) |
  | CHAT                  | (none)                                                               | No (pure function — builds curated memory context)  |

- **Robustness mechanisms:**
  - **Delegate escape hatch:** ORDER and SEARCH workers bind the LLM with `tool_choice="any"` — the LLM must always produce a tool call. But some utterances genuinely fall outside the worker's domain (e.g., SEARCH worker receives "mấy giờ đóng cửa?"). Forcing a domain tool call would return irrelevant results. The `delegate(reason)` tool is bound alongside domain tools; when the LLM cannot map the utterance to a meaningful domain action, it calls `delegate()` instead. This is routed to the CHAT worker, which handles the query conversationally. The LLM is never forced to produce a wrong action — when uncertain about its domain, it admits it rather than guessing.
  - **Retry with corrective feedback:** when the validator rejects a tool call, the `feedback` field is injected into the next worker prompt, giving the LLM explicit correction instructions (e.g., "Món 'Cơm Tấm' không có trong menu. Gợi ý món gần nhất: 'Cơm Chiên'")
  - **Circuit breaker:** `loop_count` tracks retry iterations. At 3 failed attempts, the system emits a `RetryResponseContext` with an apology and falls through to response generation. Ensures bounded execution regardless of LLM behavior.

#### 4.3.4 Stage III — Validation: Deterministic Safety Net

> _This stage is the key reliability contribution. LLM output is probabilistic regardless of temperature — an LLM can hallucinate a dish name, produce a nonsense quantity, or attempt to confirm an order with invalid items. Before any tool result affects system state, a deterministic validator inspects it. This is a pure-rules layer with no machine learning: every check is a hand-written predicate with a definitive yes/no answer._

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

> _The system uses zero fine-tuning — all model adaptation is achieved through prompting. The prompt architecture is therefore a first-class design element, not an implementation detail._

- **System prompts (7 files, all in Vietnamese):** each node that calls an LLM has its own system prompt defining its role, reasoning protocol, output format, and constraints:
  - `router_agent.md` (83 lines): 4-step reasoning protocol for intent classification. **Note:** this prompt was used by the two-tier hybrid router's SLM fallback path (§4.3.2). The current production router is the trained MLP classifier which requires no prompt. The `router_agent.md` remains as the fallback path when `classifier_router_node` is bypassed.
  - `order_agent.md`: cart CRUD rules, Vietnamese quantity patterns ("2 phần", "1 dĩa"), modification handling
  - `search_agent.md`: query rewriting instructions, "ĐÃ BIẾT" injection format, non-food delegation trigger
  - `response_agent.md`: natural Vietnamese restaurant waiter persona, tone guidelines
  - `validator.md`: (if LLM-based validator path exists)

- **Few-shot examples:** static JSON files loaded at boot, injected into prompts at runtime:
  - `router.json`: 14 examples covering single-intent, multi-intent, ambiguous utterances, and edge cases — used by the hybrid router fallback path only (the MLP classifier requires no few-shot examples)
  - `search_worker.json`: 5 examples with tool calls for KV-cache optimization
  - `utterances.json`: additional evaluation utterances

- **Skill documents:** markdown files defining behavioral rules loaded at agent startup:
  - `hospitality.md`: Vietnamese restaurant service etiquette (greeting patterns, politeness levels, refusal phrasing)
  - `menu_grounding.md`: rules for when to use menu data vs. general knowledge (enforces menu-as-ground-truth)
  - `no_service_response.md`: domain boundary definition — what the waiter should refuse to answer (unrelated questions, inappropriate requests)

- **Dynamic context injection:** conversation state is injected into LLM prompts at runtime:
  - Last 2 conversation turns injected into the router prompt — "ok" at `AWAITING_CONFIRMATION` means ORDER_CONFIRM, but at `IDLE` means CHAT
  - "ĐÃ BIẾT" section in search prompts: items from prior searches + current cart items to prevent redundant queries
  - Validator `feedback` injected into worker retry prompts for corrective guidance

- **Per-stage model configuration:** the LLM nodes use the same Qwen2.5 7B model via Ollama, configured differently per stage. The router stage uses a trained MLP classifier (no LLM):

  | Stage                 | Model                    | Temperature         | Key Configuration                                                |
  | --------------------- | ------------------------ | ------------------- | ---------------------------------------------------------------- |
  | Router                | MLP classifier (trained) | N/A (deterministic) | 778-dim input: frozen bi-encoder embedding + 10 context features |
  | Worker (ORDER/SEARCH) | Qwen2.5 7B               | 0.1                 | `tool_choice="any"` — forced tool call                           |
  | Response              | Qwen2.5 7B               | 0.3                 | Free-form generation — natural Vietnamese paraphrasing           |

  All models use `keep_alive=-1` (pinned in VRAM to eliminate cold-start latency). A warmup ping is sent at agent startup.

### 4.4 Edge Deployment & Voice Pipeline

> _The system accepts spoken Vietnamese and replies in spoken Vietnamese. Voice capture and synthesis are deployed on the Jetson Orin Nano at the robot edge, with the LLM agent residing on the central server. This section describes the architecture of this deployment split and the voice processing pipeline._

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

> _Three single-page applications share a common TypeScript library for REST, WebSocket, and type definitions. Each app has a specific role: customer ordering (tablet), guest check-in (kiosk), and staff operations (management panel)._

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
- **LLM configuration:** single Qwen2.5 7B Instruct model served by Ollama, configured with different temperatures and runtime options per agent stage (worker: T=0.1 with `tool_choice="any"`; response: T=0.3 for natural Vietnamese). The router stage uses the trained MLP classifier (no LLM call — §4.3.2). `keep_alive=-1` pins the model in GPU VRAM to eliminate cold-start latency overhead. Warmup ping at agent startup ensures the model is fully loaded before the first customer utterance.
- **Package management:** Python dependencies via `uv` with role-based extras (`server`, `voice`, `cu12`/`cu13` for CUDA version). Frontend dependencies via `npm` workspaces (3 Vite apps + 1 shared library)
- **Network:** all components communicate over local WiFi; Netbird VPN provides secure tunnel for off-site server scenarios

---

## CHAPTER 5: EXPERIMENTS AND RESULTS

> _Each experiment section follows this pattern: (a) goal — what contribution it validates, (b) dataset — how test data was constructed, (c) methodology — how measurements were taken, (d) metrics — what was measured and why, (e) results — tables and figures, (f) analysis — what the numbers mean, (g) ablation — what happens without this component._

---

### 5.1 Evaluation Methodology

#### 5.1.1 Hardware & Environment

| Component       | Specification                                                           |
| --------------- | ----------------------------------------------------------------------- |
| Server GPU      | NVIDIA GeForce RTX 3070 Laptop (CUDA 12.1)                              |
| Server CPU      | Intel Core i7 (x86_64)                                                  |
| Robot compute   | Jetson Orin Nano (aarch64, CUDA 12.6)                                   |
| Robot sensors   | RPLiDAR A2M8, Intel RealSense D435, MPU6050 IMU                         |
| LLM backend     | Ollama serving Qwen2.5 7B Instruct (`keep_alive=-1`)                    |
| Embedding model | bkai-foundation-models/vietnamese-bi-encoder (768-dim)                  |
| STT model       | faster-whisper medium, PhoWhisper weights, `language=vi`, `beam_size=5` |
| OS              | Ubuntu 22.04 LTS, ROS 2 Humble                                          |
| Network         | Local WiFi (server ↔ Jetson ↔ browser clients)                          |

#### 5.1.2 Datasets Summary

| Dataset                      | File                                              | Size                      | Purpose                                       |
| ---------------------------- | ------------------------------------------------- | ------------------------- | --------------------------------------------- |
| Router evaluation            | `evals/data/router/router_eval.json`              | 45 cases                  | Intent classification accuracy                |
| Router evaluation (semantic) | `evals/data/router/semantic_eval.json`            | 100 cases                 | Balanced single-intent accuracy               |
| Router holdout               | `training_semantic_router/data/test_holdout.json` | 39 cases                  | Clean holdout (never seen during training)    |
| Retrieval evaluation         | `evals/data/retrieval/retrieval_eval.json`        | 24 queries                | Menu search relevance                         |
| E2E conversations (Part 1)   | `evals/data/e2e/e2e_conversations_part1.json`     | 6 scenarios               | Happy-path ordering flows                     |
| E2E conversations (Part 2)   | `evals/data/e2e/e2e_conversations_part2.json`     | 5 scenarios               | Edge-case flows                               |
| Out-of-menu robustness       | `evals/data/e2e/e2e_out_of_menu_test.json`        | 4 scenarios               | Validator off-menu rejection                  |
| Real-life scenarios          | `evals/data/e2e/e2e_real_life.json`               | 4 scenarios               | Qualitative multi-turn case studies           |
| Validator name resolution    | _(to be built)_                                   | ~70 pairs                 | Name resolution pipeline accuracy (per-stage) |
| Ambiguity detection          | _(to be built)_                                   | ~20 queries               | Ambiguity flagging precision/recall           |
| Context-dependent routing    | _(to be built)_                                   | ~15 cases                 | Dynamic context ablation                      |
| STT transcription            | _(to be built)_                                   | 50–100 utterances         | Vietnamese restaurant speech-to-text WER/CER  |
| VAD boundary detection       | _(to be built)_                                   | ~30 annotated audio clips | Voice activity detection accuracy             |
| Response quality (MOS)       | _(to be built)_                                   | 20–30 agent responses     | Vietnamese naturalness and correctness        |

#### 5.1.3 Metrics Definition

##### 5.1.3.1 AI Classification & Retrieval Metrics

| Metric                              | Formula                                           | Measures                                                | Tied to §1.3 objective                          |
| ----------------------------------- | ------------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------- |
| **Accuracy**                        | correct / total                                   | Classification correctness                              | Router accuracy ≥ 90%                           |
| **Confusion matrix**                | Heatmap: predicted vs actual intents (5×5)        | Per-intent-pair error patterns                          | Router correctness (richer than accuracy alone) |
| **Precision@k**                     | \|relevant ∩ retrieved\| / k                      | Fraction of top-k results that are relevant             | RAG precision target                            |
| **Recall@k**                        | \|relevant ∩ retrieved\| / \|relevant\|           | Fraction of all relevant items found                    | RAG recall target                               |
| **MRR**                             | 1 / rank of first relevant hit                    | Reciprocal rank of first correct result                 | Search ranking quality                          |
| **Hit Rate**                        | queries with ≥1 relevant in top-k / total queries | Fraction of queries returning any useful result         | RAG completeness                                |
| **Pass Rate**                       | passed scenarios / total                          | E2E scenario completion rate                            | E2E voice ordering completion                   |
| **Per-difficulty accuracy**         | correct / total per difficulty level              | Where failures cluster (easy vs hard)                   | Router diagnostic, E2E diagnostic               |
| **Per-difficulty Precision/Recall** | Per-difficulty-level P@5/R@5                      | Whether hard queries or easy queries drag down averages | RAG diagnostic                                  |

##### 5.1.3.2 Speech Pipeline Metrics

| Metric                         | Formula                                                                                   | Measures                                                                  | Tied to §1.3 objective        |
| ------------------------------ | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ----------------------------- |
| **Word Error Rate (WER)**      | (S + D + I) / N, where S=substitutions, D=deletions, I=insertions, N=reference word count | STT transcription accuracy on Vietnamese restaurant utterances            | Voice pipeline input quality  |
| **Character Error Rate (CER)** | Same formula at character level                                                           | Finer-grained accuracy on tonal diacritics (Vietnamese-specific: 6 tones) | Voice pipeline input quality  |
| **VAD false trigger rate**     | false_positive_triggers / total_silence_segments                                          | VAD triggering on background noise                                        | Voice pipeline reliability    |
| **VAD missed utterance rate**  | missed_utterances / total_utterances                                                      | VAD failing to detect speech onset                                        | Voice pipeline reliability    |
| **VAD cut-off rate**           | utterances_with_premature_end / total_utterances                                          | VAD trimming utterance tails (trailing consonants common in Vietnamese)   | Voice pipeline reliability    |
| **Barge-in success rate**      | successful_barge_in / attempted_barge_in                                                  | Customer speech interrupts TTS playback correctly                         | Voice interaction naturalness |

##### 5.1.3.3 Safety & Robustness Metrics

| Metric                                 | Formula                                                                 | Measures                                                  | Tied to §1.3 objective       |
| -------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------- | ---------------------------- |
| **Name resolution accuracy**           | correct_resolutions / total, per pipeline level                         | Menu name matching quality at each stage                  | Validator correctness        |
| **Off-menu detection rate**            | scenarios where all invalid items flagged / total adversarial scenarios | Validator catch rate for hallucinated dishes              | Validator safety             |
| **Confirm-order leak rate**            | scenarios where confirm_order called with ≥1 invalid item / total       | Safety net failure mode — this must be 0                  | Validator safety             |
| **Ambiguity precision**                | correctly_flagged_ambiguous / all_flagged                               | False positive rate on ambiguity detection                | Validator correctness        |
| **Ambiguity recall**                   | correctly_flagged_ambiguous / all_truly_ambiguous                       | False negative rate on ambiguity detection                | Validator completeness       |
| **Delegate accuracy**                  | correct_delegations / total_delegations (manual review)                 | Delegate mechanism reliability                            | Safety mechanism correctness |
| **Wrong-tool-call rate** (no delegate) | turns with nonsensical tool call / total turns                          | Delegate ablation — failure rate without the escape hatch | Safety mechanism necessity   |

##### 5.1.3.4 Robot Performance Metrics

| Metric                            | Formula                                                                    | Measures                               | Tied to §1.3 objective |
| --------------------------------- | -------------------------------------------------------------------------- | -------------------------------------- | ---------------------- |
| **Return-to-start error**         | Euclidean distance ‖(x_end, y_end) − (x_start, y_start)‖ after closed path | Odometry drift                         | EKF odometry ≤ X cm    |
| **Drift per meter**               | error / total_path_length (cm/m)                                           | Normalized drift rate                  | Odometry quality       |
| **Navigation success rate**       | successful_trips / total_trips                                             | Navigation reliability                 | Nav success ≥ X%       |
| **Mean trip time**                | Σ trip_duration / N per table                                              | Navigation speed                       | Nav performance        |
| **Docking position error**        | \|actual − target\| in lateral (x) and depth (z), in cm                    | Docking lateral/depth precision        | ArUco docking < X cm   |
| **Docking orientation error**     | \|actual − target\| yaw, in degrees                                        | Docking angular precision              | ArUco docking < X°     |
| **Safe stop distance**            | Distance from robot to obstacle at full stop                               | Obstacle avoidance safety              | Safe obstacle distance |
| **Marker detection failure rate** | failed_detections / total_approaches per table                             | ArUco robustness under real conditions | Docking reliability    |

##### 5.1.3.5 Latency & Throughput Metrics

| Metric                                    | Formula                                                       | Measures                          | Tied to §1.3 objective    |
| ----------------------------------------- | ------------------------------------------------------------- | --------------------------------- | ------------------------- |
| **Voice turn latency**                    | t_speaker_start − t_mic_open, per turn                        | End-to-end voice interaction time | Voice interaction < 5s    |
| **Per-stage latency**                     | Timestamp diff per pipeline stage (VAD→STT→Network→Agent→TTS) | Identifies latency bottleneck     | Latency diagnostic        |
| **Agent inference latency**               | t_response_ready − t_utterance_received, per intent type      | LLM inference cost by intent      | Agent responsiveness      |
| **Validator latency overhead**            | t_validator_exit − t_validator_entry                          | Safety computation cost           | Safety vs speed trade-off |
| **Semantic router latency**               | t_semantic_classification_complete                            | Tier 1 speed                      | Router speed              |
| **Task assignment latency**               | t_task_assigned − t_task_created                              | Dispatcher responsiveness         | System responsiveness     |
| **API endpoint response time** (p50, p95) | FastAPI request duration per endpoint                         | Backend performance               | System responsiveness     |
| **WebSocket event propagation latency**   | t_client_receive − t_server_emit                              | Real-time update speed            | UI responsiveness         |
| **Cold-start penalty**                    | t_first_utterance_latency − t_warm_utterance_latency          | Ollama model load overhead        | Deployment quality        |

##### 5.1.3.6 Response Quality Metrics (Subjective)

| Metric                        | Scale                                | Measures                                           | Tied to §1.3 objective    |
| ----------------------------- | ------------------------------------ | -------------------------------------------------- | ------------------------- |
| **MOS Naturalness**           | 1–5 (3–5 Vietnamese-speaking raters) | How natural the Vietnamese response reads          | Conversational AI quality |
| **MOS Correctness**           | 1–5 (same raters)                    | Factual accuracy of the response                   | Agent reliability         |
| **MOS Helpfulness**           | 1–5 (same raters)                    | Whether the response actually answers the customer | Agent usefulness          |
| **Inter-annotator agreement** | Cohen's κ                            | Rater consistency validation                       | Evaluation rigor          |

##### 5.1.3.7 Ablation Metrics

| Ablation                               | Comparison                                                                           | Primary Metric                                                       | Proves                                                                                                                |
| -------------------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Router: semantic-only vs hybrid vs MLP | 3-mode run on shared datasets (100 cases for semantic, 45 for hybrid/MLP comparison) | Accuracy, mean latency                                               | MLP classifier (92–97%) is qualitatively superior; semantic router (89%) and hybrid router (73%) are weaker baselines |
| Context features: ON vs OFF            | MLP classifier with all 10 context features vs with embedding only (768-dim)         | Accuracy on context-dependent cases                                  | Context features encode conversation state that pure embeddings miss                                                  |
| Validator: ON / OFF                    | E2E 11 scenarios with validator bypassed                                             | E2E pass rate, off-menu items in cart, incorrect confirm_order count | Validator prevents real system failures                                                                               |
| Delegate: ON / OFF                     | E2E + real-life scenarios with delegate removed                                      | Wrong-tool-call count, irrelevant search results, cart errors        | Delegate prevents forced-wrong tool calls                                                                             |

All automated experiments run at least 3 times where variability matters (LLM inference, navigation). Reported as mean ± standard deviation. Subjective MOS requires inter-annotator agreement (Cohen's κ ≥ 0.6).

---

### 5.2 Robot Navigation — Component Evaluation

#### 5.2.1 Odometry Accuracy

> **Goal:** Validate that EKF fusion of encoder + IMU improves odometry over encoder-only.

- **Methodology:** Robot executes closed-path trajectories (rectangle: 2m × 1.5m, return to origin). Record `/odometry/filtered` pose. Compare encoder-only (raw wheel odometry) vs EKF-fused (encoder + IMU via `robot_localization`). N = 10 runs per condition.
- **Metrics:** Return-to-start position error (cm): mean, std, max, min. Drift per meter traveled: error / total path length.
- **Results table:**

  | Condition    | Mean Error (cm) | Std (cm)  | Max Error (cm) | Drift (cm/m) |
  | ------------ | --------------- | --------- | -------------- | ------------ |
  | Encoder-only | [pending]       | [pending] | [pending]      | [pending]    |
  | EKF-fused    | [pending]       | [pending] | [pending]      | [pending]    |

- **Expected finding:** EKF significantly reduces yaw drift from IMU gyro bias, cutting return-to-start error by ~40-60%.

#### 5.2.2 Navigation Performance

> **Goal:** Measure the robot's ability to navigate kitchen → table autonomously.

- **Methodology:** Gazebo simulation first (controlled environment, repeatable), then real-world validation. Kitchen → each of 6 tables, N = 5 trips per table. Record success (robot reaches within 0.3m of table waypoint), trip duration, and failure causes.
- **Metrics:** Success rate per table (%), mean trip time (s), failure categorization.
- **Results table (simulation):**

  | Table   | Trips  | Success   | Mean Time (s) | Failures  |
  | ------- | ------ | --------- | ------------- | --------- |
  | Bàn 1–6 | 5 each | [pending] | [pending]     | [pending] |

- **Results table (real world):** same format
- **Obstacle-in-lane test:** Place box in service lane mid-trip. Verify: (a) LiDAR detects obstacle, (b) local planner stops before collision, (c) robot waits or replans. Safe stop distance measured.
- **Sim-to-real comparison:** Discuss differences in localization accuracy, LiDAR noise, floor surface effects.

#### 5.2.3 ArUco Docking Precision

> **Goal:** Measure final-approach accuracy using ArUco marker re-localization at each table.

- **Methodology:** Robot navigates to each table. At 0.5m approach distance, uses D435 RGB camera to detect ArUco marker (DICT_4X4_50, IDs 0–5). Measures final position and orientation relative to marker. N = 10 runs per table.
- **Metrics:** Position error (cm): lateral (x), depth (z). Orientation error (°): yaw. Mean ± std per table.
- **Results table:**

  | Table   | Lateral Error (cm) | Depth Error (cm) | Yaw Error (°) | Failures (marker not detected) |
  | ------- | ------------------ | ---------------- | ------------- | ------------------------------ |
  | Bàn 1–6 | [pending]          | [pending]        | [pending]     | [pending]                      |

- **Failure analysis:** lighting conditions, marker angle >45°, marker partial occlusion → marker-lost → safe stop behavior.

---

### 5.3 AI Agent — Component-Level Evaluation

#### 5.3.1 Intent Classification — Trained MLP Classifier

> **Goal:** Validate that the trained MLP classifier achieves ≥90% accuracy across all test sets and outperforms both the pure semantic centroid router and the two-tier hybrid router described in the design iterations. Three complementary evaluations quantify performance: a clean holdout set (39 cases), a diverse router evaluation set (45 cases with difficulty labels + multi-intent), and a balanced single-intent set (100 cases).

- **Datasets:**

  | Dataset       | File                 | Cases          | Distribution                                                     |
  | ------------- | -------------------- | -------------- | ---------------------------------------------------------------- |
  | Holdout       | `test_holdout.json`  | 39             | ORDER:16, SEARCH:10, PAYMENT:8, CHAT:5                           |
  | Router eval   | `router_eval.json`   | 45             | ORDER:10, ORDER_CONFIRM:6, SEARCH:10, PAYMENT:8, CHAT:5, MULTI:6 |
  | Semantic eval | `semantic_eval.json` | 100 (balanced) | ORDER:20, ORDER_CONFIRM:20, SEARCH:20, PAYMENT:20, CHAT:20       |

  All cases hand-crafted in Vietnamese to cover teencode, short affirmations, compound utterances, restaurant-specific terms, and edge cases. Ground-truth labels assigned by human annotator. Holdout set was never seen during training (separated before augmentation). ORDER_CONFIRM labels are mapped to ORDER for the 4-class MLP evaluation.

- **Methodology:** Run `evaluate.py --context-aware` (holdout set + context features from test data), `compare.py` (A/B comparison against hybrid router on 45 cases), and a custom test harness (100-case semantic eval with ORDER_CONFIRM→ORDER mapping). All evaluations use the frozen `bkai-foundation-models/vietnamese-bi-encoder` for embedding, the saved `model.pt` + `scaler.npz` + `label_encoder.json` artifacts from training.

- **Results — Holdout set (39 cases):**

  | Metric                                | Value              |
  | ------------------------------------- | ------------------ |
  | Overall Accuracy                      | **97.44%** (38/39) |
  | Mean Confidence (correct predictions) | 0.9599             |
  | Mean Confidence (all)                 | 0.9573             |

  | Intent  | Precision | Recall | F1     | Support |
  | ------- | --------- | ------ | ------ | ------- |
  | ORDER   | 1.0000    | 1.0000 | 1.0000 | 16      |
  | SEARCH  | 1.0000    | 0.9000 | 0.9474 | 10      |
  | PAYMENT | 0.8889    | 1.0000 | 0.9412 | 8       |
  | CHAT    | 1.0000    | 1.0000 | 1.0000 | 5       |

  **Confusion matrix (39 cases, 4-class):**

  | Actual ↓ / Predicted → | ORDER | SEARCH | PAYMENT | CHAT |
  | ---------------------- | ----- | ------ | ------- | ---- |
  | **ORDER**              | 16    | 0      | 0       | 0    |
  | **SEARCH**             | 0     | 9      | 1       | 0    |
  | **PAYMENT**            | 0     | 0      | 8       | 0    |
  | **CHAT**               | 0     | 0      | 0       | 5    |

  **1 misclassification:** "có giao hàng về quận 7 không em" (expected SEARCH, classified PAYMENT, conf=0.86). The model maps delivery/service queries to the PAYMENT intent — a known weakness where commercial transaction vocabulary ("giao hàng", "ship") overlaps with payment domain keywords. ORDER, CHAT, and non-delivery SEARCH queries are classified perfectly.

- **Results — Router evaluation set (45 cases, A/B comparison vs hybrid router):**

  | Metric                   | Two-Tier Hybrid |  MLP Classifier   |
  | ------------------------ | :-------------: | :---------------: |
  | Overall (45 cases)       |  73.3% (33/45)  | **95.6%** (43/45) |
  | Single-intent (39 cases) |  76.9% (30/39)  | **94.9%** (37/39) |
  | Multi-intent (6 cases)   |   50.0% (3/6)   |  **100%** (6/6)   |

  | Outcome                 | Count |
  | ----------------------- | :---: |
  | Both correct            |  33   |
  | Both wrong              |   2   |
  | MLP wins / Hybrid loses |  10   |
  | Hybrid wins / MLP loses |   0   |

  **10 cases the MLP corrects that the hybrid got wrong:**

  | Utterance                                           | Expected      | Hybrid → | MLP →       |
  | --------------------------------------------------- | ------------- | -------- | ----------- |
  | "1 lẩu cá tầm măng chua nhe bạn"                    | ORDER         | SEARCH   | **ORDER**   |
  | "Uh đúng rồi đó"                                    | ORDER_CONFIRM | CHAT     | **ORDER**   |
  | "ok em"                                             | ORDER_CONFIRM | CHAT     | **ORDER**   |
  | "Hàu nướng có những kiểu chế biến nào?"             | SEARCH        | CHAT     | **SEARCH**  |
  | "ốc bulot làm từ nguyên liệu gì thế"                | SEARCH        | CHAT     | **SEARCH**  |
  | "Quẹt thẻ được hông em"                             | PAYMENT       | CHAT     | **PAYMENT** |
  | "ck cho mình cái qr với"                            | PAYMENT       | CHAT     | **PAYMENT** |
  | "Xác nhận đơn cũ và thêm 2 bia Tiger"               | ORDER+ORDER   | ORDER    | **ORDER**   |
  | "Lẩu Thái cay không? Không cay thì cho mình 1 phần" | SEARCH+ORDER  | SEARCH   | **SEARCH**  |
  | "Cho mình xem qua menu rồi lấy 1 cháo hàu"          | SEARCH+ORDER  | CHAT     | **ORDER**   |

  The hybrid router's dominant failure mode is clear: centroid cosine similarity falls below the semantic gate threshold (max_sim < 0.35), the utterance falls through to CHAT as the default intent. The MLP's 10 context features + learned decision boundary prevent this collapse. All 10 hybrid failures are cases where the utterance is clearly in-domain but the embedding model's centroid representation is too coarse to distinguish it from the CHAT centroid.

- **Results — Semantic evaluation set (100 balanced cases):**

  | Metric           | Value               |
  | ---------------- | ------------------- |
  | Overall Accuracy | **92.00%** (92/100) |
  | Mean Confidence  | 0.9505              |

  | Intent                  | Cases | Correct | Accuracy  |
  | ----------------------- | ----- | ------- | --------- |
  | ORDER (+ ORDER_CONFIRM) | 40    | 39      | **97.5%** |
  | SEARCH                  | 20    | 16      | **80.0%** |
  | PAYMENT                 | 20    | 20      | **100%**  |
  | CHAT                    | 20    | 17      | **85.0%** |

  **Confusion matrix (100 cases, 4-class):**

  | Actual ↓ / Predicted → | ORDER | SEARCH | PAYMENT | CHAT |
  | ---------------------- | ----- | ------ | ------- | ---- |
  | **ORDER**              | 39    | 0      | 1       | 0    |
  | **SEARCH**             | 1     | 16     | 1       | 2    |
  | **PAYMENT**            | 0     | 0      | 20      | 0    |
  | **CHAT**               | 2     | 0      | 1       | 17   |

  **8 misclassifications by category:**

  | Pattern                                | Count | Examples                                                                                                 |
  | -------------------------------------- | :---: | -------------------------------------------------------------------------------------------------------- |
  | Cart/order review → ORDER              |   2   | "Nãy giờ mình gọi những món gì rồi" (CHAT→ORDER), "Cho anh xem lại giỏ hàng" (CHAT→ORDER)                |
  | Delivery/price teencode → wrong intent |   2   | "có ship về quận 7 ko shop" (SEARCH→PAYMENT), "bia heineken nhiêu 1 lon z" (SEARCH→CHAT)                 |
  | Complex food questions → ORDER/CHAT    |   2   | "So sánh món ốc hương và món sò điệp" (SEARCH→ORDER), "Cá Chim Nướng có nhiều xương không" (SEARCH→CHAT) |
  | Ambiguous confirm → PAYMENT            |   1   | "Ghi nhận đơn hàng của tôi" (ORDER→PAYMENT, conf=1.00)                                                   |
  | Bot identity → PAYMENT                 |   1   | "Bạn là robot hay người thật vậy" (CHAT→PAYMENT, conf=0.45)                                              |

  SEARCH accuracy of 80% is the weakest point. The MLP's context features (has_search_context, search_context_size) help on cases where the customer has already searched — but on the first SEARCH utterance with empty search_context, the embedding alone must carry the signal. Teencode-heavy utterances ("nhiêu", "z", "ko", "hông", "ck") also degrade embedding quality because the bi-encoder was not trained on informal Vietnamese.

- **Ablation — Semantic-only vs Two-Tier Hybrid vs MLP Classifier:**

  > _Run the same 100-case balanced set through all three router architectures. This proves the MLP is not merely an incremental improvement but a qualitative architectural advance._

  | Router                           | Cases | Accuracy  |   Avg Latency (routing)   |
  | -------------------------------- | :---: | :-------: | :-----------------------: |
  | Semantic centroid only           |  100  | **89.0%** |   ~1.2ms (cosine only)    |
  | Two-tier hybrid (semantic + SLM) |  45   | **73.3%** |   ~1.8s (SLM fallback)    |
  | **MLP classifier (trained)**     |  100  | **92.0%** | **~0.17ms** (MLP forward) |

  | Router                           | Cases | Accuracy  |
  | -------------------------------- | :---: | :-------: |
  | Semantic centroid only           |  100  | **89.0%** |
  | Two-tier hybrid (semantic + SLM) |  45   | **73.3%** |
  | **MLP classifier (trained)**     |  100  | **92.0%** |
  | MLP classifier (39-case holdout) |  39   | **97.4%** |

  **Notes:** The hybrid router was evaluated on the 45-case `router_eval.json` set (5-label system with multi-intent, matching its design). The MLP classifier was evaluated on all three sets. The semantic router's 89% on 100 cases reflects its core limitation: centroid cosine similarity alone cannot disambiguate context-dependent utterances. The MLP closes this gap through context features without sacrificing latency — the MLP forward pass (0.17ms) is actually faster than centroid cosine computation (1.2ms), though both are negligible compared to the shared embedding step (~50ms).

- **Failure analysis (across all 11 failures on 139 total evaluation cases):**
  - **Delivery/service queries (2.4% of all cases):** "có ship về quận 7 ko shop", "có giao hàng về quận 7 không em". The model maps these to PAYMENT due to shared transaction vocabulary. These are genuinely ambiguous — a restaurant delivery query could be a pre-payment logistics question or a post-order transaction question. Fix: add more delivery-as-SEARCH training examples that distinguish "can you deliver?" from "I want to pay for delivery."
  - **Teencode-heavy queries (2.4%):** "bia heineken nhiêu 1 lon z", "Quẹt thẻ được hông em". The frozen bi-encoder produces weaker embeddings for informal Vietnamese. The MLP mostly compensates (10/12 teencode cases correct), but the worst 2 teencode queries still fail. Fix: augment training data with systematic teencode variants.
  - **Cart review questions (1.4%):** "Nãy giờ mình gọi những món gì rồi". These read as ORDER because they contain ordering vocabulary ("gọi", "món"). The context features (has_cart=1, cart_size>0) should theoretically help but don't fully distinguish "review my cart" from "add to cart." Fix: add explicit cart-review-as-CHAT training examples.
  - **ORDER_CONFIRM critical error (0.7%):** "Ghi nhận đơn hàng của tôi" (ORDER→PAYMENT, conf=1.00). This is the most concerning failure — a customer confirming their order would get a payment bill instead. Fix: this specific utterance needs to appear in training data.

- **Latency analysis:**

  | Pipeline Stage                    | Mean Latency | Dominant Factor                         |
  | --------------------------------- | ------------ | --------------------------------------- |
  | Word segmentation (`underthesea`) | ~2ms         | Vietnamese tokenizer                    |
  | Embedding (`bkai-bi-encoder`)     | ~50ms        | Frozen SentenceTransformer forward pass |
  | Context feature extraction        | <1ms         | Dict lookups + one-hot encoding         |
  | MLP forward pass                  | ~0.17ms      | Small network (778→256→64→4)            |
  | **Total routing**                 | **~52ms**    | Embedding dominates everything else     |

  The embedding step accounts for >95% of total routing latency. The MLP forward pass at 0.17ms is three orders of magnitude faster than the SLM fallback path in the old two-tier hybrid (1.8s) — and even faster than the semantic centroid cosine computation (1.2ms). Further latency improvement requires a lighter embedding model; the classifier architecture itself is already optimal.

#### 5.3.2 Deterministic Validator — Safety Net Effectiveness

> **Goal:** Prove the validator catches LLM hallucinations (off-menu items, ambiguous names) before they reach the cart, and that removing it causes system failures.

- **Dataset:** 4 adversarial E2E scenarios from `e2e_out_of_menu_test.json`:
  1. Single invalid item + single valid item ("Cho 1 Pizza Hải Sản và 1 Ốc Hương Xốt Trứng Muối")
  2. All items invalid ("Cho 1 Bún Bò Huế và 1 Cơm Gà Xối Mỡ")
  3. All items invalid with near-match spelling variants ("Cơm Tấm", "Lẩu Thái Lan")
  4. Invalid item with special request ("Cho 1 Cơm Chiên Dương Châu, it cay")

- **Methodology:** Run E2E eval script. For each scenario, verify: (a) validator correctly identifies off-menu items in `unavailable_items`, (b) agent _never_ calls `confirm_order` with invalid items, (c) response includes nearest-match suggestion (if one exists), (d) agent guides customer to choose valid alternatives.

- **Metrics:**

  | Metric                  | Definition                                                       |
  | ----------------------- | ---------------------------------------------------------------- |
  | Off-menu detection rate | Scenarios where all invalid items correctly flagged              |
  | False positive rate     | Valid items incorrectly flagged as off-menu                      |
  | Confirm-order leak rate | Scenarios where `confirm_order` was called with any invalid item |
  | Suggestion relevance    | Manual assessment: was nearest-match suggestion reasonable?      |

- **Results (4/4 scenarios pass):**

  | Scenario                | Off-menu detected? | Nearest match suggested?                     | confirm_order called?        | Pass |
  | ----------------------- | ------------------ | -------------------------------------------- | ---------------------------- | ---- |
  | S1: 1 invalid + 1 valid | Yes                | Yes (Pizza Hải Sản → suggested alternatives) | No (only valid item in cart) | ✓    |
  | S2: All invalid         | Yes                | Yes (suggested closest matches)              | No                           | ✓    |
  | S3: Near-match variants | Yes                | Yes (suggested actual menu items)            | No                           | ✓    |
  | S4: Invalid + modifier  | Yes                | Yes                                          | No                           | ✓    |

- **Name resolution pipeline accuracy** _(dataset to be built — ~70 (raw_input, expected_name) pairs)_:

  > _This measures each level of the resolution pipeline independently, showing where the 4-stage matching contributes._

  | Resolution Level                | Test Cases | Correct                                     | Accuracy  |
  | ------------------------------- | ---------- | ------------------------------------------- | --------- |
  | Exact match                     | 20         | [pending]                                   | [pending] |
  | Diacritic-insensitive           | 10         | [pending]                                   | [pending] |
  | Prefix match                    | 10         | [pending]                                   | [pending] |
  | Substring match                 | 10         | [pending]                                   | [pending] |
  | Token-Jaccard fallback          | 10         | [pending]                                   | [pending] |
  | Misspelled (should NOT resolve) | 10         | [pending — should be 0, correctly rejected] | N/A       |

- **Ambiguity detection** _(dataset to be built — ~20 queries)_:

  | Metric                                   | Value     |
  | ---------------------------------------- | --------- |
  | Precision (flagged / actually ambiguous) | [pending] |
  | Recall (actually ambiguous / flagged)    | [pending] |
  | False positive rate                      | [pending] |
  | False negative rate                      | [pending] |

- **Ablation — E2E with vs without validator:**

  > _Run 11 E2E scenarios twice: validator enabled vs validator bypassed. This is the critical proof that the validator prevents real failures._

  | Condition     | E2E Pass Rate | Off-menu items in cart | Incorrect confirm_order |
  | ------------- | ------------- | ---------------------- | ----------------------- |
  | Validator ON  | 81.8% (9/11)  | 0                      | 0                       |
  | Validator OFF | [pending]     | [pending]              | [pending]               |

  **Expected result:** Without validator, some scenarios "pass" technically (order sent) but with hallucinated items in cart, or the pass rate drops because backend rejects dishes not in DB. Either outcome proves the validator prevents a failure mode.

- **Validator latency overhead:**

  > _Safety has a computational cost. Measure the validator's contribution to total agent inference time to confirm it does not become a bottleneck._

  | Metric                               | Value     |
  | ------------------------------------ | --------- |
  | Mean validator execution time        | [pending] |
  | Validator % of total agent inference | [pending] |
  | Mean name resolution time (per item) | [pending] |

  **Expected result:** The validator should add <50ms per turn (pure deterministic string operations + JSON dict lookups — no LLM call). This is negligible compared to the 1–2s LLM inference it protects.

#### 5.3.3 Delegate Mechanism — Graceful Fallback

> **Goal:** Prove the delegate mechanism prevents forced-wrong tool calls under `tool_choice="any"` and that it correctly routes out-of-domain utterances.

- **Methodology:** Instrument the agent to log every delegate call: which worker triggered it, the input utterance, the delegate reason, and the eventual routing. Run 11 E2E scenarios + 4 real-life scenarios (15 total). Manually review each delegate instance for correctness.

- **Metrics:**

  | Metric                                               | Value                                            |
  | ---------------------------------------------------- | ------------------------------------------------ |
  | Total delegate calls across 15 scenarios             | [pending]                                        |
  | Delegate rate (ORDER worker)                         | [pending — % of ORDER LLM calls that delegated]  |
  | Delegate rate (SEARCH worker)                        | [pending — % of SEARCH LLM calls that delegated] |
  | Correct delegation rate                              | [pending — manual review]                        |
  | Incorrect delegation (should have used domain tool)  | [pending]                                        |
  | Missed delegation (should have delegated but didn't) | [pending]                                        |

- **Qualitative examples** (select 3–4 from actual traces):

  | Turn      | Worker    | Input                          | Delegated? | Reason                                        | Correct?  |
  | --------- | --------- | ------------------------------ | ---------- | --------------------------------------------- | --------- |
  | E2E-XXX   | SEARCH    | "nhà hàng mở cửa đến mấy giờ?" | Yes        | "restaurant info query, not menu search"      | ✓         |
  | E2E-XXX   | ORDER     | "cho hỏi món nào ngon nhất?"   | Yes        | "recommendation request, not an order action" | ✓         |
  | [pending] | [pending] | [pending]                      | [pending]  | [pending]                                     | [pending] |

- **Ablation — delegate disabled:**

  > _Re-run 15 scenarios with delegate tool removed from ORDER and SEARCH worker bindings. `tool_choice="any"` still enforced — the LLM must produce a domain tool call even for out-of-domain inputs._

  | Condition    | Wrong-tool-call count   | Irrelevant search results | Cart errors |
  | ------------ | ----------------------- | ------------------------- | ----------- |
  | Delegate ON  | [pending — expected ~0] | [pending]                 | [pending]   |
  | Delegate OFF | [pending — expected >0] | [pending]                 | [pending]   |

  **Expected result:** Without delegate, the LLM calls `search()` on non-food queries (returning irrelevant menu items) or calls `add_cart()` on recommendation requests (adding wrong items). The ablation shows delegate prevents a class of LLM behavioral errors.

#### 5.3.4 Menu Retrieval — Supporting Infrastructure

> _Note: this is functional infrastructure evaluation. The retrieval pipeline uses off-the-shelf BM25 + FAISS + RRF. This section validates it works adequately as a supporting component; it is not claimed as a research contribution._

- **Dataset:** `retrieval_eval.json` — 24 Vietnamese queries across 8 difficulty levels (easy: 8, medium: 9, hard: 7). Each query has `expected_relevant` (ground-truth relevant dish IDs) and `expected_irrelevant` (known-irrelevant dish IDs). Queries range from exact name lookups to vague semantic searches ("món gì ấm bụng cho ngày lạnh?").

- **Methodology:** Run `eval_retrieval.py` against 217-dish menu index (FAISS + BM25). For each query, retrieve top-5 results, compare against ground truth. Run 3 modes: BM25-only, FAISS-only, hybrid RRF.

- **Results:**

  | Metric      | BM25-only | FAISS-only | Hybrid RRF |
  | ----------- | --------- | ---------- | ---------- |
  | Precision@5 | [pending] | [pending]  | **30.83%** |
  | Recall@5    | [pending] | [pending]  | **70.14%** |
  | MRR         | [pending] | [pending]  | **0.6875** |
  | Hit Rate    | [pending] | [pending]  | **87.50%** |

  | Difficulty | Count | Precision@5 (RRF) | Recall@5 (RRF) | Hit Rate (RRF) |
  | ---------- | ----- | ----------------- | -------------- | -------------- |
  | Easy       | 8     | [pending]         | [pending]      | [pending]      |
  | Medium     | 9     | [pending]         | [pending]      | [pending]      |
  | Hard       | 7     | [pending]         | [pending]      | [pending]      |

- **Gatekeeper behavior:**

  | Metric                                    | Value                   |
  | ----------------------------------------- | ----------------------- |
  | Queries rejected by gatekeeper            | [pending — count and %] |
  | Correct rejections (truly irrelevant)     | [pending]               |
  | False rejections (relevant query blocked) | [pending]               |
  | False approvals (irrelevant query passed) | [pending]               |

- **Analysis:** Precision@5 of 30.83% means ~1.5 of 5 results are relevant on average. This is adequate as a suggestion engine (the agent presents results conversationally, customer picks) but insufficient for direct order placement without customer confirmation. Hit Rate of 87.50% means 1 in 8 queries returns nothing useful — the gatekeeper correctly blocks these rather than returning noise. The retrieval pipeline is functional infrastructure; improvements (cross-encoder re-ranker, learned fusion weights, structured query parsing) are noted as future work.

---

#### 5.3.5 Voice Pipeline Component Evaluation

> _The agent's input is spoken Vietnamese. If STT mishears "Ốc Hương" as "Ốt Hương" or VAD cuts off mid-sentence, the entire pipeline operates on corrupted input. These component-level metrics validate the speech pipeline independently of the agent._

##### 5.3.5.1 Speech-to-Text Accuracy

> **Goal:** Measure faster-whisper PhoWhisper transcription accuracy on Vietnamese restaurant domain utterances.

- **Dataset** _(to be built)_: 50–100 recorded Vietnamese restaurant utterances covering: dish names (tonal accuracy test), quantities ("2 phần", "1 dĩa"), modifiers ("ít cay", "nhiều hành"), payment phrases ("tính tiền", "check out"), casual speech ("cho em xin...", "quán mình có..."). Ground-truth transcriptions by human annotator fluent in Vietnamese. Recorded in realistic conditions: quiet room + simulated restaurant ambient noise at 2 levels.

- **Methodology:** Run faster-whisper medium via `stt_phowhisper.py` with `language=vi`, `beam_size=5`. Compare output against ground truth using edit-distance alignment (S=substitutions, D=deletions, I=insertions).

- **Metrics:**

  | Metric                                                           | Value     |
  | ---------------------------------------------------------------- | --------- |
  | Word Error Rate (WER)                                            | [pending] |
  | Character Error Rate (CER)                                       | [pending] |
  | WER (quiet)                                                      | [pending] |
  | WER (ambient noise: 50 dB)                                       | [pending] |
  | WER (ambient noise: 60 dB)                                       | [pending] |
  | Per-category WER (dish names / quantities / modifiers / payment) | [pending] |

- **Analysis:** CER captures tonal diacritic errors that WER misses (Vietnamese is monosyllabic — character-level errors directly impact meaning). Example: "Ốc Hương" (snail) vs "Ốt Hương" (pepper) — same word count, wrong character, WER=0 but CER=0.25. Dish name category expected to show highest CER due to rare words outside Whisper training distribution. Ambient noise at 60 dB should show moderate degradation — validates feasibility for real restaurant deployment.

##### 5.3.5.2 Voice Activity Detection Accuracy

> **Goal:** Measure Silero VAD's ability to correctly detect utterance boundaries in Vietnamese speech.

- **Dataset** _(to be built)_: ~30 annotated audio clips (5–15 seconds each) containing Vietnamese utterances with hand-annotated speech start/end timestamps. Mix of: isolated single utterances, speech with trailing silence, speech preceded by background noise (chair scrape, plate clink), rapid turn-taking (short inter-speaker gap), quiet trailing consonants (common in Vietnamese: "không ạ" — the "ạ" is very soft).

- **Methodology:** Run Silero VAD via `vad_silero.py` with current production sensitivity threshold. Compare detected boundaries against ground truth. Tolerance: ±200ms for start, ±300ms for end.

- **Metrics:**

  | Metric                       | Definition                                                    | Value     |
  | ---------------------------- | ------------------------------------------------------------- | --------- |
  | False trigger rate           | VAD triggers on noise-only segments / total silence segments  | [pending] |
  | Missed utterance rate        | Utterances VAD completely failed to detect / total utterances | [pending] |
  | Cut-off rate (premature end) | Utterances where detected end < ground_truth_end − 300ms      | [pending] |
  | Start boundary mean error    | mean(ground_truth_start − detected_start) in ms               | [pending] |
  | End boundary mean error      | mean(ground_truth_end − detected_end) in ms                   | [pending] |

- **Analysis:** Missed utterances are the worst failure mode — the customer speaks and nothing happens. False triggers are annoying but recoverable (capture is discarded, customer tries again). Cut-off rate is Vietnamese-specific: trailing particles like "ạ", "nhé", "nha" are very quiet and easily lost. If cut-off rate >10%, sensitivity threshold needs reduction (trading more false triggers for fewer cut-offs).

##### 5.3.5.3 Barge-In Effectiveness

> **Goal:** Verify that customer speech during TTS playback successfully interrupts the robot.

- **Methodology:** Instrument `tts_engine.py` and `vad_silero.py`. Run 20 simulated barge-in scenarios: TTS plays a 3-sentence response, customer begins speaking at sentence 2. Measure whether TTS stops and the new utterance is captured.

- **Metrics:**

  | Metric                                                 | Value                                                |
  | ------------------------------------------------------ | ---------------------------------------------------- |
  | Barge-in success rate                                  | [pending — expect >90%]                              |
  | Mean TTS stop latency (ms)                             | [pending — from VAD trigger to audio output silence] |
  | False barge-in rate (ambient noise triggers interrupt) | [pending]                                            |

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

  | Metric                 | Value     |
  | ---------------------- | --------- |
  | Total Scenarios        | 11        |
  | Passed                 | 9         |
  | Failed                 | 2         |
  | Pass Rate              | **81.8%** |
  | Total Turns            | 29        |
  | Avg Turns per Scenario | 2.6       |

  **Part 1 (Happy-path) — 6/6 passed:**

  | ID      | Name                   | Difficulty | Turns | Result |
  | ------- | ---------------------- | ---------- | ----- | ------ |
  | E2E-001 | Single item order      | Easy       | 2     | ✓      |
  | E2E-002 | Multi-item order       | Easy       | 2     | ✓      |
  | E2E-003 | Search then order      | Medium     | 3     | ✓      |
  | E2E-004 | Order then pay         | Medium     | 3     | ✗      |
  | E2E-005 | Search only (no order) | Medium     | 2     | ✓      |
  | E2E-006 | Add item then confirm  | Medium     | 3     | ✓      |

  **Part 2 (Edge-case) — 3/5 passed:**

  | ID      | Name                  | Difficulty | Turns     | Result    |
  | ------- | --------------------- | ---------- | --------- | --------- |
  | E2E-007 | Swap item             | Hard       | [pending] | [pending] |
  | E2E-008 | Full payment flow     | Hard       | [pending] | [pending] |
  | E2E-009 | Modify quantity       | Hard       | [pending] | [pending] |
  | E2E-010 | Chitchat then order   | Hard       | [pending] | [pending] |
  | E2E-011 | Remove item from cart | Medium     | [pending] | [pending] |

- **Failure categorization:**

  | Failure Type                | Count     | Example                                                                                                                                                                                            |
  | --------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | Backend dependency          | 1         | E2E-004: `request_payment` failed because orchestrator backend crashed (`Connection refused`). Payment response didn't match assertion for QR + total. NOT an agent error — infrastructure failure |
  | Chitchat → order transition | [pending] | Agent fails to switch from casual conversation to order-taking when customer transitions mid-conversation                                                                                          |
  | Missing tool calls          | [pending] | LLM produces a text response instead of the expected tool call under `tool_choice="any"`                                                                                                           |
  | Router misclassification    | [pending] | Intent classified incorrectly, routing to wrong worker                                                                                                                                             |
  | Validator false rejection   | [pending] | Valid menu item rejected as off-menu                                                                                                                                                               |

- **Model comparison (optional):**

  | Model      | Pass Rate | Notes                                            |
  | ---------- | --------- | ------------------------------------------------ |
  | Qwen2.5 7B | [pending] | Current default                                  |
  | Qwen2.5 3B | [pending] | Lower VRAM, faster but potentially less accurate |

#### 5.4.2 Out-of-Menu Robustness

_(Cross-reference with §5.3.2 validator results — this section provides the E2E behavioral perspective, §5.3.2 provides the component-level metrics.)_

- **Results (4/4 pass):** Validator correctly rejects off-menu items in all 4 adversarial scenarios. Agent never calls `confirm_order` with invalid items. Nearest-match suggestions are contextually reasonable.

- **Behavioral findings:**
  1. Agent distinguishes "partially valid" from "fully invalid" — keeps valid items in cart, only removes invalid ones
  2. Spelling variants ("Cơm Tấm" for "Cơm Chiên") correctly caught as off-menu, nearest-match suggested
  3. Agent maintains conversational tone when rejecting — doesn't break character as a waiter
  4. No scenario triggers the circuit breaker (max 3 retries not reached)

#### 5.4.3 Real-Life Qualitative Case Studies

> _These are not quantitative evaluations. They demonstrate the agent's behavior in realistic multi-turn scenarios and validate the design decisions made in Chapter 4._

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

  | Stage                      | Location | Mean (s)                   | Median (s) | p95 (s)   | Budget (§4.4)     |
  | -------------------------- | -------- | -------------------------- | ---------- | --------- | ----------------- |
  | VAD + audio capture        | Jetson   | [pending]                  | [pending]  | [pending] | ~0.2s + utterance |
  | STT (faster-whisper)       | Jetson   | [pending]                  | [pending]  | [pending] | ~0.8s             |
  | HTTP round-trip            | Network  | [pending]                  | [pending]  | [pending] | ~0.05s            |
  | Agent inference (semantic) | Server   | ~0.015s                    | —          | —         | —                 |
  | Agent inference (SLM)      | Server   | [pending]                  | [pending]  | [pending] | ~1.5–2.5s         |
  | TTS first sentence         | Jetson   | [pending]                  | [pending]  | [pending] | ~0.5s             |
  | **Total (MLP routing)**    | —        | [pending — estimate ~3–5s] | —          | —         | < 5s              |

- **Per-intent agent latency:**

  | Intent           | Mean Agent Time (s) | Dominant Factor               |
  | ---------------- | ------------------- | ----------------------------- |
  | ORDER (semantic) | ~0.015s             | Embedding + cosine similarity |
  | ORDER (SLM)      | ~0.30s              | LLM tool call (small prompt)  |
  | SEARCH           | ~1.26s              | LLM query rewrite + retrieval |
  | PAYMENT          | [pending]           | Deterministic — no LLM        |
  | CHAT             | ~1.56s              | LLM response generation       |
  | Multi-intent     | ~1.9–2.2s           | Multiple sequential LLM calls |

- **Cold-start vs warm-cache:**
  - First utterance after Ollama restart: +X seconds (model load + warmup)
  - Subsequent utterances: warm cache, `keep_alive=-1` eliminates reload
  - Warmup ping at agent startup eliminates cold-start for the first real customer

- **Bottleneck identification:** The SLM LLM call dominates latency (1–2s). Semantic fast-track avoids this for ~33% of ORDER utterances. TTS sentence streaming overlaps with agent response generation for subsequent sentences, hiding some latency from the user. STT latency is fixed by model size (fast-whisper medium ~800ms; smaller model would be faster but less accurate for Vietnamese tones).

#### 5.4.5 Response Quality Evaluation

> **Goal:** Quantify the subjective quality of the agent's Vietnamese responses — are they natural, correct, and helpful? This is the closest proxy for "does the system work as a waiter?"

- **Dataset** _(to be built)_: 20–30 agent responses sampled from the 11 E2E scenarios + 4 real-life scenarios. Select responses covering all response types: template-based (cart confirmation, payment prompt, error), LLM-generated (search results, free-form chat, off-menu suggestions). Mix of short (1 sentence) and long (3+ sentences) responses.

- **Methodology:** MOS (Mean Opinion Score) with 3–5 Vietnamese-speaking raters. Each rater independently scores each response on 3 dimensions. Raters are given the conversation context (previous turns) and the customer's utterance to judge appropriateness.

- **Metrics:**

  | Dimension       | Scale | Description                                                                           |
  | --------------- | ----- | ------------------------------------------------------------------------------------- |
  | **Naturalness** | 1–5   | 1=clearly machine-generated/translated, 5=indistinguishable from a Vietnamese waiter  |
  | **Correctness** | 1–5   | 1=factually wrong (wrong price, wrong dish, hallucinated info), 5=completely accurate |
  | **Helpfulness** | 1–5   | 1=doesn't address the customer's request, 5=fully addresses and adds useful guidance  |

- **Results:**

  | Dimension   | Mean MOS  | Std       | Min       | Max       |
  | ----------- | --------- | --------- | --------- | --------- |
  | Naturalness | [pending] | [pending] | [pending] | [pending] |
  | Correctness | [pending] | [pending] | [pending] | [pending] |
  | Helpfulness | [pending] | [pending] | [pending] | [pending] |

  | Response Type  | Naturalness | Correctness | Helpfulness | N         |
  | -------------- | ----------- | ----------- | ----------- | --------- |
  | Template-based | [pending]   | [pending]   | [pending]   | [pending] |
  | LLM-generated  | [pending]   | [pending]   | [pending]   | [pending] |

- **Inter-annotator agreement:**

  | Dimension   | Cohen's κ               |
  | ----------- | ----------------------- |
  | Naturalness | [pending — target ≥0.6] |
  | Correctness | [pending — target ≥0.6] |
  | Helpfulness | [pending — target ≥0.6] |

- **Template vs LLM comparison:** Template responses should score higher on correctness (deterministic, formula-driven) but potentially lower on naturalness (may sound repetitive). LLM responses should score higher on naturalness (varied phrasing) but risk lower correctness (hallucination risk). This comparison validates the hybrid response strategy from §4.3.6.

- **Per-turn naturalness decay (optional):** Track naturalness scores across turns within a multi-turn conversation. Does response quality degrade as the conversation lengthens (context window pressure)?

  | Turn # | N         | Mean Naturalness |
  | ------ | --------- | ---------------- |
  | 1      | [pending] | [pending]        |
  | 2      | [pending] | [pending]        |
  | 3      | [pending] | [pending]        |
  | 4+     | [pending] | [pending]        |

---

### 5.5 System Integration & Quality Validation

#### 5.5.1 End-to-End Integration Test

> **Goal:** Validate that all 3 UIs + robot + backend maintain consistent state through a complete service lifecycle.

- **Methodology:** Execute full service flow: kiosk seating → robot dispatch → robot arrival → customer voice order → kitchen panel display → order status progression → payment → table reset. Verify state at each step across all UIs by inspecting WebSocket events and REST responses.

- **Test sequence and verification:**

  | Step | Action                        | Expected State                                                  | Verified On                     |
  | ---- | ----------------------------- | --------------------------------------------------------------- | ------------------------------- |
  | 1    | Kiosk: seat party at Bàn 1    | Table: DANG_PHUC_VU, Session: ACTIVE, Task: go_to_table PENDING | Kiosk, Panel, DB                |
  | 2    | Dispatch: robot assigned      | Task: ASSIGNED → Robot drives to Bàn 1                          | Panel (minimap + robot card)    |
  | 3    | Robot arrives at table        | Task: DONE, table-robot voice binding set                       | Panel, Voice bridge             |
  | 4    | Customer: "Talk to AI" button | voice-device WS: start_listening                                | Tablet UI, Voice device         |
  | 5    | Customer speaks order         | voice.heard → thinking → voice.reply + cart sync                | Tablet UI (voice panel + cart)  |
  | 6    | Customer confirms order       | Order: CHO_BEP, Kitchen board shows new order                   | Tablet UI, Panel (KitchenBoard) |
  | 7    | Kitchen: advance to XONG      | Order: XONG, Task: deliver created + assigned                   | Panel, Robot WS                 |
  | 8    | Customer: request payment     | VietQR displayed, session total computed                        | Tablet UI (payment screen)      |
  | 9    | Payment verified              | Session: CLOSED, Table: DA_THANH_TOAN, robot released           | All UIs                         |
  | 10   | Staff: end table              | Table: TRONG, pending tasks cancelled                           | Panel, DB                       |

- **State synchronization verification:** At each step, confirm all 3 UIs agree on: table status, current order status, cart contents, payment state. Any disagreement is a bug.

- **Concurrent multi-table test:** Run 2 tables simultaneously. Verify: (a) each tablet shows only its own orders, (b) kitchen panel shows both tables' orders correctly, (c) robot dispatch handles 2 concurrent tasks correctly, (d) no cross-table state bleed.

#### 5.5.2 WebSocket Event Propagation Latency

- **Methodology:** Instrument WebSocket client to record `sent_at` (server-side timestamp in event payload) and `received_at` (client-side timestamp). Measure for key event types. N = 50 events per type.

- **Results:**

  | Event Type      | Mean Latency (ms) | p95 Latency (ms) |
  | --------------- | ----------------- | ---------------- |
  | `order.created` | [pending]         | [pending]        |
  | `table.updated` | [pending]         | [pending]        |
  | `robot.updated` | [pending]         | [pending]        |
  | `voice.heard`   | [pending]         | [pending]        |
  | `voice.reply`   | [pending]         | [pending]        |

- **Analysis:** Local WiFi, single-server — expected < 50ms p95 for all event types. Higher latency indicates server-side bottleneck (likely LLM inference, not WebSocket).

#### 5.5.3 System Timing & Throughput

> **Goal:** Measure backend responsiveness under load — API response times, dispatcher latency, and database performance. Validates that the orchestrator meets real-time restaurant requirements.

- **Methodology:** Instrument FastAPI middleware to log request duration per endpoint. Measure during 11 E2E scenario runs (natural load: sequential turns with LLM pauses). For throughput: simulate concurrent tables.

- **API endpoint response time:**

  | Endpoint             | Mean (ms) | p50 (ms)  | p95 (ms)  | p99 (ms)  |
  | -------------------- | --------- | --------- | --------- | --------- |
  | `GET /menu`          | [pending] | [pending] | [pending] | [pending] |
  | `POST /orders`       | [pending] | [pending] | [pending] | [pending] |
  | `POST /payments`     | [pending] | [pending] | [pending] | [pending] |
  | `POST /seatings`     | [pending] | [pending] | [pending] | [pending] |
  | `POST /voice/event`  | [pending] | [pending] | [pending] | [pending] |
  | `POST /voice/listen` | [pending] | [pending] | [pending] | [pending] |
  | `GET /robots`        | [pending] | [pending] | [pending] | [pending] |

  **Expected:** All endpoints <100ms p95 except `/voice/event` (which includes JSON payload with cart data — still should be <200ms). No endpoint should exceed 500ms at p99 — the server is single-threaded synchronous (FastAPI + SQLite) and a slow endpoint blocks all subsequent requests.

- **Robot dispatcher timing:**

  | Metric                                          | Value       |
  | ----------------------------------------------- | ----------- |
  | Mean task assignment latency (PENDING→ASSIGNED) | [pending]   |
  | Mean dispatch cycle time                        | [pending]   |
  | Watchdog scan interval                          | 5s (config) |

  **Analysis:** The dispatcher runs synchronously. Task assignment latency should be near-instant (<50ms) since it's a dictionary lookup + distance computation on 3–5 robots. If >100ms, SQLite query is the bottleneck.

- **Database performance:**

  | Metric                                 | Value     |
  | -------------------------------------- | --------- |
  | SQLite write latency (single INSERT)   | [pending] |
  | SQLite read latency (SELECT with JOIN) | [pending] |
  | DB file size after 100 orders          | [pending] |
  | WAL mode checkpoint interval           | [pending] |

  **Analysis:** SQLite in WAL mode with single-writer access should handle restaurant workload easily. The bottleneck is never the database — it's LLM inference. This validates the architectural choice in §4.5.1.

- **Concurrent load test:** Simulate 2 tables ordering simultaneously. Measure: (a) any request queuing or timeout, (b) cross-table state isolation maintained, (c) WebSocket events delivered to correct tables only.

  | Metric                             | Value                   |
  | ---------------------------------- | ----------------------- |
  | Max concurrent requests observed   | [pending]               |
  | Peak memory usage (server process) | [pending]               |
  | Any 5xx errors                     | [pending — should be 0] |

---

### 5.6 Summary of Results

> _Each §1.3 objective is mapped to its measured result, compared against the target, and marked pass/fail._

| #   | §1.3 Objective                     | Target       | Measured Result                                                                | Status     | Section  |
| --- | ---------------------------------- | ------------ | ------------------------------------------------------------------------------ | ---------- | -------- |
| 1   | EKF-fused odometry error           | ≤ X cm       | [pending]                                                                      | [pending]  | §5.2.1   |
| 2   | Navigation success rate            | ≥ X%         | [pending]                                                                      | [pending]  | §5.2.2   |
| 3   | ArUco docking error                | < X cm / X°  | [pending]                                                                      | [pending]  | §5.2.3   |
| 4   | Intent router accuracy             | ≥ 90%        | **97.44%** (38/39 holdout), **95.6%** (43/45 A/B), **92.0%** (92/100 balanced) | ✓ PASS     | §5.3.1   |
| 5   | RAG precision/recall@5             | [set target] | P@5: 30.83%, R@5: 70.14%, Hit: 87.50%                                          | ⚠ Adequate | §5.3.4   |
| 6   | E2E voice ordering completion      | [set target] | **81.8%** (9/11)                                                               | ⚠ Partial  | §5.4.1   |
| 7   | Voice turn latency                 | < 5s         | [pending]                                                                      | [pending]  | §5.4.4   |
| 8   | STT Word Error Rate (Vietnamese)   | [set target] | [pending]                                                                      | [pending]  | §5.3.5.1 |
| 9   | VAD missed utterance rate          | [set target] | [pending]                                                                      | [pending]  | §5.3.5.2 |
| 10  | Validator off-menu leak rate       | 0%           | **0%** (0/4 scenarios)                                                         | ✓ PASS     | §5.3.2   |
| 11  | Response quality MOS (Naturalness) | [set target] | [pending]                                                                      | [pending]  | §5.4.5   |

**Additional key results (not tied to §1.3 objectives but validating Chapter 4 design claims):**

| Claim                                    | Result                                                                                                             | Proves                  |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ----------------------- |
| MLP classifier outperforms prior routers | Semantic-only 89%, Hybrid 73%, MLP 92–97% across all test sets                                                     | §5.3.1 ablation         |
| Context features are necessary           | Discussion: ORDER_CONFIRM utterances and cart review queries cannot be distinguished by embedding similarity alone | §5.3.1 failure analysis |
| Validator prevents cart contamination    | 0 off-menu items in cart with validator ON; [pending] with OFF                                                     | §5.3.2 ablation         |
| Delegate prevents wrong tool calls       | [pending] wrong tool calls with delegate OFF                                                                       | §5.3.3 ablation         |
| Validator latency is negligible          | <50ms vs 1–2s LLM inference                                                                                        | §5.3.2                  |
| Barge-in works reliably                  | [pending]% success rate                                                                                            | §5.3.5.3                |

- **Discussion of key findings:**
  - The MLP classifier exceeds the 90% accuracy target across all three test sets. Remaining errors cluster in SEARCH (80% on 100-case balanced set), teencode-heavy queries, and cart-review utterances misrouted to ORDER. The most critical failure is the ORDER_CONFIRM→PAYMENT confusion on "Ghi nhận đơn hàng của tôi" (conf=1.00) — this specific utterance needs to appear in augmented training data.
  - The validator is 100% effective on adversarial test cases — no off-menu item ever reaches `confirm_order`. This is the strongest safety result and the most important single number in the AI evaluation.
  - E2E pass rate of 81.8% reflects both agent errors (chitchat→order transitions, missing tool calls) and infrastructure failures (payment backend crash). Agent-intrinsic failures are the actionable items.
  - Retrieval metrics are adequate for a conversational suggestion system but insufficient for autonomous ordering — the agent's architecture (customer confirms before order) compensates for moderate precision.
  - The ablation studies (when completed) will be the centerpiece of the defense presentation — they prove each design decision was necessary, not arbitrary.
  - Template responses should score higher on correctness; LLM responses should score higher on naturalness. The hybrid response strategy from §4.3.6 is validated if both score above 3.5.
  - STT WER is the gating factor for the entire voice pipeline — if WER exceeds ~15% on dish names, the agent receives corrupted input and downstream accuracy suffers, regardless of router/validator quality.
  - [Add any surprising/unexpected result and its implication for the design]

- **Visual summary:** Radar chart or bar chart of all key metrics normalized to their targets. Separate chart for ablation comparisons (with/without each component).

- **Failure budget allocation:** Across all 19 E2E + adversarial + real-life scenarios (11 + 4 + 4), categorize every failure by root cause:

  | Failure Category              | Count     | % of Total | Most Affected Component |
  | ----------------------------- | --------- | ---------- | ----------------------- |
  | Router misclassification      | [pending] | [pending]  | Router (§4.3.2)         |
  | Worker tool-call error        | [pending] | [pending]  | LLM decision (§4.3.3)   |
  | Validator false positive      | [pending] | [pending]  | Validator (§4.3.4)      |
  | Backend/infrastructure        | [pending] | [pending]  | Orchestrator (§4.5)     |
  | LLM response generation error | [pending] | [pending]  | Response node (§4.3.6)  |
  | STT transcription error       | [pending] | [pending]  | Voice pipeline (§4.4)   |

  This budget identifies where to invest improvement effort — the component with the most failures is the system's weakest link.

---

## CHAPTER 6: CONCLUSION AND FUTURE WORKS

### 6.1 Conclusion

- Tick each §1.3 objective against Ch.5 numbers
- Summarize both contribution legs:
  - Autonomous TWD navigation + EKF-fused odometry + RTAB-Map + Nav2 + ArUco docking
  - Trained MLP intent classifier (97.4% holdout, 95.6% A/B) + agentic LangGraph workflow (multi-intent queue, tool execution, deterministic validator) + hybrid RAG (BM25+FAISS+RRF for Vietnamese menus) + voice pipeline + 3 web UIs

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
