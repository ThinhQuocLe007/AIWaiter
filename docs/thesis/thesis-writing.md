# Thesis Writing Guide — AI Waiter Robot on a Two-Wheel Differential Drive (TWD) Platform

> **Report language: English.** Structure and writing style follow the sample HCMUTE graduation theses you collected (`nhom_Trung`, `nhom_Canh`, `nhom_NamHuy`).
> **Hardware (purchased complete, ready-to-run):** RPLiDAR A2M8 · Intel RealSense D435 · IMU MPU6050 · 2× MC520P30 12 V DC gear motors (Hall encoder **1024 PPR**, gear ratio **1:30**) · 7-inch LCD. Drive type: **two-wheel differential drive (TWD)**, non-holonomic, free indoor navigation (no rail).
> **Your contribution = from ROS2 upward:** sensor integration, odometry fusion, SLAM, Nav2 navigation, ArUco docking, and the entire AI/backend/web system (LangGraph agent, hybrid router, hybrid RAG, voice pipeline, 3 web UIs).
>
> **Chapter structure (mirrors nhom_Trung / nhom_Canh):**
> Ch.1 Introduction → Ch.2 Theoretical Basis → Ch.3 Proposed Method I: ROS2 Control & Navigation → Ch.4 Proposed Method II: AI, Backend & Web → Ch.5 Experiments & Results → Ch.6 Conclusion & Future Works.

---

## ⭐ Which reference file to use for what

| Reference file | Use it for |
|---|---|
| **塔克创新 kinematics tutorial (XTARK)** | **Private guide only — never cited, never mentioned in the report.** Use it to get the TWD kinematics derivation right (§2.2), written in your own words with a figure you redraw yourself. These are standard textbook equations anyway; leave a citation placeholder `[n]` and later attach a standard robotics reference you pick yourself (any classic mobile-robotics textbook covers the identical derivation). |
| **ProjectAI (Duy, your own earlier report)** | **Port the fusion content over in full** (you have the source to copy fast) — wheel odometry model, IMU measurement model, EKF formulation, `robot_localization` config. **But do NOT paste as-is**: the original was criticized as disorganized and it contains real errors. Follow the **restructuring plan + fix-list in §2.5–2.6 below**. Math goes to §2.5–2.6; implementation/config goes to §3.5. Also a private guide — not a citable reference. |
| **nhom_Trung, nhom_Canh** | **English structure & tone**: chapter naming, TOC style, how sections open with a requirement/lead-in, how experiments are organized around metrics. |
| **nhom_NamHuy** | The closest *content* template (service robot + ROS + RTAB-Map + chatbot/RAG + web). Follow how it splits robot chapters vs. AI chapter, how Ch.2 covers theory "generically," and how the Experiments chapter opens with the fabricated model. **Do NOT copy its Ch.3 (mechanical design) / Ch.4 (electrical design)** — you purchased the hardware, so those chapters do not exist in your report. |

**Framing rule (repeat it consistently):** *"The group uses a commercially available differential-drive mobile platform (chassis, motors, motor driver, power system) as the base; the group's contribution begins at the ROS2 layer: sensor integration, state estimation, mapping, navigation, precision docking, and the complete AI/backend/web system."* Present this as a deliberate scoping decision. Consequences:
- **No** motor/gear/battery selection calculations anywhere.
- **No** mechanical or electrical design chapters.
- Hardware appears only as: (a) one short platform paragraph + sensor role table at the start of Ch.3, and (b) the **component list + connection diagram + photos in Ch.5.1** (this is where the reader "meets" the physical robot in detail — same as nhom_NamHuy's "Thi công mô hình" and nhom_Trung's "Hardware model" result sections).

**Your core contributions to highlight** (put diagrams + numbers wherever these appear):
1. **Two-tier hybrid router** (semantic centroid + softmax/gap gating → SLM fallback; 91.25%).
2. **Agentic LangGraph workflow** (router → workers → validator → tools, multi-intent, order state machine).
3. **Hybrid RAG (BM25 + FAISS + RRF)** for Vietnamese + a quantitative eval suite.
4. **Integrated autonomous TWD robot**: EKF-fused odometry, RTAB-Map (LiDAR + RGB-D), Nav2 navigation, ArUco table docking.

**Honesty note:** only report what actually runs and has numbers; unfinished parts (some UIs, TTS, etc.) go to Future Works.

---

## General principles

- Write in **English**; keep Vietnamese only inside quoted user utterances / menu items (italics + English gloss).
- Open every chapter with a short lead-in; open Ch.3 and Ch.4 with a **"System requirements"** subsection (both nhom_Trung and nhom_NamHuy do this — it reads well).
- Academic tone, "the group/we." Cite `[n]` for others' theory/figures/formulas (a standard mobile-robotics textbook for kinematics/EKF, RTAB-Map paper, Nav2 docs, component pages like the sample theses do...); write "the group designed/configured/implemented" for your own work. **The private guide files (XTARK tutorial, ProjectAI) are never cited or mentioned.**
- Every figure/table is referenced in the text before it appears; caption + source.
- **Ch.2 = generic theory only** (never mentions "our robot", exactly like the sample theses' Theoretical Basis chapters); **Ch.3–4 = your design**.
- Prefer diagrams: ROS2 node graph, TF tree, agent graph, pipelines.

---

## CHAPTER 1: INTRODUCTION

Follow the section list of nhom_Canh/nhom_Trung Ch.1.

### 1.1 Overview / Introduction
- Context: service robots in restaurants + the LLM boom. The idea: an autonomous TWD waiter robot navigating from the kitchen to 6 tables, docking precisely at each, letting customers order and ask questions **by voice in Vietnamese**, with orders pushed to the kitchen. Broad → narrow, ~1–1.5 pages. Weave in 2–3 positioning sentences (existing works handle either navigation or restaurant chatbots separately; this work integrates both).
- 🖼️ **Figure:** one real-world example photo of a commercial restaurant service robot (context-setter, like nhom_NamHuy §1.1 opens with example robots). Cite the source.

### 1.2 Motivation / Necessity of the study
- Practical (labor cost, service consistency), technical (agentic LLM + RAG + autonomous navigation are current), feasibility (a ready-to-run commercial base lets the group concentrate on the software/AI layer — state it positively).

### 1.3 Objectives
- 1 general + measurable specific objectives (checked against Ch.5):
  - Integrate the TWD platform into ROS2 with **fused encoder+IMU odometry (EKF)** reaching ≤ X cm return-to-start error on a closed test path.
  - Build the restaurant map with **RTAB-Map (A2M8 + D435)**; navigate kitchen → correct table with success rate ≥ X%.
  - **ArUco docking error < X cm / X°**.
  - Intent router accuracy ≥ 90% (currently 91.25%); RAG precision/recall@k targets; end-to-end Vietnamese voice ordering.

### 1.4 Scope of the study
- Open with the boundary sentence (framing rule above). Then: indoor, flat floor, mapped environment, **robot on a dedicated service lane physically separated from customers** (kitchen → tables), moderate speed, Vietnamese voice, LLM served locally via Ollama on an on-premises server. **Map is 2D.** Limitations: non-holonomic (no lateral motion), 2D navigation, consumer-grade IMU, lighting sensitivity (D435/ArUco), network latency.
- ⚠️ **Domain note (keep consistent with Ch.3):** the lane is separated from people → no pedestrian avoidance / social navigation; obstacle handling is only for objects that accidentally enter the lane. Drop any "free indoor navigation / avoid people / no rail" wording here and in Ch.2 §2.2/§2.5.4.

### 1.5 Research methodology
- Literature/tool review → **Gazebo simulation** (restaurant world) → real deployment → quantitative evaluation (odometry/docking tests + AI eval suite). Emphasize sim-first-then-real.

### 1.6 Contents of the report
- Work blocks + one-paragraph outline of Ch.2–6. Optional short **Contributions** bullet list (the 4 items above). Team task-allocation table if the template requires it.

---

## CHAPTER 2: THEORETICAL BASIS

> **Full report draft lives in `chapter2.md`.** This is the guide/outline only (section list + writing notes + figure notes).
Generic theory only, written the way the sample theses do (nhom_NamHuy Ch.2 is the closest model: mobile robot overview → kinematic model → ROS/SLAM/RTAB-Map/navigation → chatbot/LLM/RAG → web tech). Only include theory you actually use in Ch.3–5.
> **🖼️ Figure notes below:** lines marked 🖼️ mark where an illustrative figure genuinely helps the reader; all are **generic concept diagrams** (Ch.2 never shows the actual robot/parts/measured data — those live in Ch.3–5). Sections without a 🖼️ note don't need an added figure — prose/table is enough there. Every figure gets a caption + a cited source.
### 2.1 Overview of Mobile Robots
> *Outline reference (drive-type taxonomy paraphrased from the private XTARK tutorial; holonomic/non-holonomic and the navigation pipeline are standard textbook material — attach a mobile-robotics reference to the `[n]` placeholders). This section stays neutral and does not pick a configuration yet — the choice is made and justified at the start of the next section. **Draft below — edit freely.***
🖼️ **Figure 2.1 — [Common types of wheeled mobile robots]** *(top-view sketch of the three drive mechanisms above; drawn by the group; caption + source `[n]`).*
🖼️ **Figure 2.2 — [Steps of indoor autonomous navigation]** *(block diagram: perception → localization → mapping → planning → control; drawn by the group).*
### 2.2 Kinematic Model of the Two-Wheel Differential Drive Robot
> *Derivation and figure follow the XTARK tutorial's own notation, chosen as the report's standard: `V_A, V_B` (left/right wheel speed), `V_x` (forward), `V_y` (sideways, = 0), `V_ω` (yaw rate), `W` (wheel track), `R` (turning radius), `S_L, S_M, S_R` (arc paths), `θ` (turn angle). The private tutorial itself is never cited/mentioned; Figure 2.3 is a fresh redraw (the group's own figure), not a screenshot. Leave `[n]` for a standard robotics textbook. Keep numbers (1024 PPR, 1:30) out of Ch.2 — they go in §3.4. **⚠ Sections 2.5–2.6 (fusion) must use these same symbols** — convert the ported ProjectAI math from `v_L/v_R/b/ω_z` to `V_A/V_B/W/V_ω`. **Draft below.***
🖼️ **Figure 2.3 — [Top-view geometry of the differential drive]** *(the group's own redrawn figure: turning centre and reference point $O$, wheel track $W$, left/right wheel speeds $V_A, V_B$, body-frame vectors $V_x, V_y, V_\omega$, turning radius $R$, arc paths $S_L, S_M, S_R$, and turn angle $\theta$; caption + cited source `[n]`).*
> **⚠ Keep notation consistent** across §2.2, §2.5, §2.6: `V_A, V_B, W, V_x, V_y, V_ω`. In particular the turning rate is always `V_ω = (V_B − V_A)/W` (this is FIX 1 — the old ProjectAI text sometimes divided by 2 by mistake). When porting the fusion math, rewrite its `v_L/v_R/b/ω_z` into these symbols.
### 2.3 Sensors for Indoor Mobile Robots
> *Concept-level only — what each sensor is, what it measures, and what it is used for. No derivations or numbers here; the full step-by-step measurement math with the robot's real constants (from `sensor_math_full.md`) is presented in Chapter 3. Every 🖼️ figure is a generic principle diagram, not a photo of the group's part. Draft below.*
🖼️ **Figure 2.4 — [Sensing principle of a 2D LiDAR, an RGB-D camera, and an IMU]** *(three small illustrative panels: 360-degree laser time-of-flight scanning, infrared depth sensing, and a three-axis gyroscope/accelerometer; drawn by the group; caption + source `[n]`).*
🖼️ **Figure 2.5 — [Working principle of an incremental wheel encoder]** *(a slotted/hall encoder disc with two offset output channels A and B; drawn by the group; caption + source `[n]`).*
### 2.4 Odometry and Sensor Fusion
> *Concept-level only — odometry types, fusion, and the Kalman/EKF idea. No formulas here; the full derivation with the robot's constants is in §3.4–§3.5. Draft below.*
🖼️ **Figure 2.6 — [Encoder–IMU fusion with an EKF]** *(a conceptual block diagram: wheel odometry and IMU both feeding an EKF predict/update loop that outputs a single fused pose; drawn by the group; caption + source `[n]`).*
### 2.5 ROS2 and the Autonomous Navigation Stack
> *Group the whole robot-software stack here, as one section with subsections (nhom_NamHuy Ch.2 is the model). Everything below is **generic theory**; the group's tuned parameters, maps, and screenshots are Ch.3. Figure numbers 2.7–2.11 continue from Figure 2.6 in §2.4 — renumber if the earlier figure count changes. Draft below.*
#### 2.5.1 Robot Operating System (ROS2)
🖼️ **Figure 2.7 — [ROS2 node–topic communication]** *(a small block diagram: sensor driver nodes publishing to topics that are consumed by processing and navigation nodes, illustrating the publish–subscribe pattern; drawn by the group; caption + source `[n]`).*
#### 2.5.2 SLAM and RTAB-Map
🖼️ **Figure 2.8 — [Principle of SLAM: front end and back end]** *(a block diagram: sensors → front-end signal processing and motion estimation → back-end optimisation → map + trajectory; drawn by the group; caption + source `[n]`).*
🖼️ **Figure 2.9 — [RTAB-Map graph SLAM with LiDAR and RGB-D]** *(a system/pipeline diagram: LiDAR scans and RGB-D frames feeding node creation, a bag-of-words loop-closure detection, and back-end graph optimisation correcting an accumulated-drift trajectory into a consistent map; drawn by the group; caption + source `[n]`).*
#### 2.5.3 Localization on a Known Map
> ✏️ *[ArUco marker docking — planned but not implemented yet. When the marker-based final-approach code is finished, add here: what fiducial/ArUco markers are, detection, PnP pose estimation, and why a marker gives an absolute reference for the precise final approach to a table. Also add the corresponding figure (detected marker with 6-DoF axes). Leave this placeholder until the code exists so the thesis never describes unbuilt features.]*
#### 2.5.4 Navigation (Nav2)
🖼️ **Figure 2.10 — [Nav2 navigation architecture]** *(a block diagram: goal → planner server on the global costmap → controller server on the local costmap → velocity commands, with the behaviour/recovery layer supervising; drawn by the group; caption + source `[n]`).*
> ✏️ *[Planned: fusing the D435 depth stream into the costmaps as an additional obstacle source (so obstacles outside the LiDAR plane appear in the local costmap). Not implemented yet — the current costmaps use the LiDAR scan only, and the text above reflects that. When the fusion is done, extend the costmap paragraph accordingly.]*
#### 2.5.5 Robot Simulation with Gazebo
🖼️ **Figure 2.11 — [Robot and sensors simulated in Gazebo]** *(the robot model in a simulated indoor restaurant world, with the LiDAR, depth-camera, IMU, and differential-drive plugins publishing the same kinds of ROS2 topics as the real hardware; drawn by the group; caption + source `[n]`).*
### 2.6 Large Language Models and Conversational AI
#### 2.6.1 Large Language Models
🖼️ **Figure 2.12 — Conceptual structure of a Transformer block: multi-head self-attention followed by the feed-forward sub-layer, with residual connections and layer normalization** *(redrawn from [n]).*
#### 2.6.2 Prompt Engineering
🖼️ **Figure 2.13 — Zero-shot versus few-shot prompting on the same classification task** *(drawn by the group, adapted from [n]).*
#### 2.6.3 Intent Routing and the Semantic Router
🖼️ **Figure 2.14 — Semantic routing in a 2-D sketch of the embedding space: utterance embedding, per-intent centroids, and the gap-gating decision** *(drawn by the group).*
#### 2.6.4 Retrieval-Augmented Generation (RAG) and Agentic RAG
🖼️ **Figure 2.15 — Plain RAG (retrieval hard-wired into a fixed pipeline) versus Agentic RAG (retrieval exposed as a tool the agent decides when and how to call)** *(drawn by the group, adapted from [n]).*
#### 2.6.5 LLM Agents and the LangGraph Framework
🖼️ **Figure 2.16 — A LangGraph StateGraph: a shared typed state flowing through nodes (LLM calls, tools, and plain code), with normal edges, a conditional branch, and a bounded loop** *(drawn by the group).*
### 2.7 Speech Processing: VAD, STT, TTS
🖼️ **Figure 2.17 — The voice interaction pipeline: microphone audio → VAD → STT → text → (dialogue agent) → text → TTS → loudspeaker audio** *(drawn by the group).*
### 2.8 Web, Backend and Deployment Technologies
#### 2.8.1 Vue.js and Vite
🖼️ **Figure 2.18 — Component-based structure of a Vue single-page application: a tree of reusable components bound reactively to shared application data** *(drawn by the group).*
#### 2.8.2 FastAPI
#### 2.8.3 RESTful API
#### 2.8.4 WebSocket
🖼️ **Figure 2.19 — HTTP request–response with polling versus a persistent WebSocket connection with server push** *(drawn by the group, adapted from [n]).*
#### 2.8.5 SQLite
#### 2.8.6 Ollama

---

## CHAPTER 3: PROPOSED METHOD (I) — ROBOT CONTROL AND NAVIGATION ON ROS2

> **Full report draft lives in `chapter3.md`.** This is the guide/outline only.
> **Algorithm & configuration only** — impersonal report style, no "the group/we".
> **Moved OUT to Chapter 5 (Experiments):** the physical build, the ROS2 robot model (URDF, TF tree, node/topic graph), the numeric platform constants, and all simulation runs. Method equations use *symbols* here; their measured *values* go in the Ch.5 implementation section.
> **Domain (updated):** the robot runs on a **dedicated service lane physically separated from customers** — no pedestrians in the path, only occasional objects that accidentally enter the lane. **Map is 2D.** No human detection / social navigation. The RGB-D camera is used only for RTAB-Map loop closure and ArUco docking, not for 3D obstacle sensing.
> ⚠️ **Propagate this domain change** to Ch.1 Scope and Ch.2 (§2.2 "aisles between tables" wording, §2.5.4 Nav2) — drop any "free indoor navigation / avoid people / no rail" framing.

**Section structure:**
> 3.1 System Requirements → 3.2 Wheel Odometry and EKF Sensor Fusion (IMU included) → 3.3 Map Building with RTAB-Map → 3.4 Localization and ArUco-Based Docking → 3.5 Autonomous Navigation with Nav2.

### 3.1 System Requirements
- Requirements R1–R7 (full text in chapter3.md). Opens the chapter like nhom_NamHuy §5.1. Fill the `[X]` targets from Ch.5 (suggested: R2 ≤ 5 cm, R4 ≥ 90%, R5 < 2 cm / 3°). R4 wording reflects the lane (no pedestrian avoidance; stop for objects that enter the lane); R5 docking = kitchen + each table.

### 3.2 Wheel Odometry and EKF Sensor Fusion *(math-heavy core; IMU in full)*
- 3.2.1 Wheel odometry: `N = P·4·G`; `d_tick = πD/N`; `V = (πD/N)(Δn/Δt)`; FK `V_x=(V_A+V_B)/2, V_y=0, V_ω=(V_B−V_A)/W`; Euler pose integration + heading wrap. **FIX 1**: `V_ω = (V_B−V_A)/W` (÷W not ÷2). STM32↔ROS2 "who computes what"; verify `D`/`W` by straight-line + in-place-rotation field tests.
- 3.2.2 IMU (MPU6050): raw int16 → SI (`s_a = A_max/2^15`, `s_g = Ω_max/2^15`; ±2 g, ±500 °/s); axis remap (firmware); gyro bias at rest `b_g = (1/M)Σ`; **Mahony AHRS** → orientation, **yaw-only + relative** (no magnetometer → drifts).
- 3.2.3 EKF (`robot_localization`, `two_d_mode`): state `[x, y, ψ, V_x, V_y, V_ω]`; **odom0 → V_x, V_y, V_ω** (V_y=0 enforces non-holonomic); **imu0 → V_ω only** (IMU yaw NOT fused — no magnetometer); non-linear model + Jacobian; covariance rationale (small stationary / large moving / huge on out-of-plane + lateral); output `/odometry/filtered` + `odom → base_footprint` TF. **FIX 2–5** still apply. Evidence figure + return-to-start table → data in Ch.5.

### 3.3 Map Building with RTAB-Map
- RTAB-Map consumes the fused `/odom`; **LiDAR = geometry, camera = loop closure**; output a **2D occupancy grid**. Offline mapping run: teleop the whole lane + a return pass to force a loop closure. Tuned-parameter table (grid resolution, max LiDAR range, loop-closure/proximity settings, update rate) with reasons. Camera NOT used for a 3D map (lane + 2D). A LiDAR-only mapping option also exists on the robot — state which map navigation uses. Point out one real loop closure (screenshot → Ch.5).

### 3.4 Localization and ArUco-Based Docking
- 3.4.1 RTAB-Map **localization mode** on the saved map → publishes `map → odom`.
- 3.4.2 **Initial pose from the home (kitchen) ArUco marker** → absolute start pose, removes the manual "2D Pose Estimate".
- 3.4.3 **Per-table ArUco re-localization** for a precise stop; why ArUco (residual SLAM/odom error; an absolute *local* reference where precision matters); marker-lost → safe stop at a set distance + report.
- ✏️ Final-approach docking **controller** NOT implemented yet — describe as planned (short non-holonomic approach, `V_y=0`, marker-lost handling, safe stop distance). Report only what runs.

### 3.5 Autonomous Navigation with Nav2 *(basic Nav2 running; mark the rest planned)*
- Global planner: path along the lane, kitchen → table goal. Local controller (from `nav2_params.yaml`): look-ahead, desired/max speed, `V_y=0`, in-place rotation for the non-holonomic TWD.
- Costmaps: static (2D map) + inflation + **LiDAR obstacle layer for the occasional object that enters the lane**. **No pedestrian detection / social navigation** (lane separated from customers). Robot radius / inflation / resolution sized to the lane width. Parameter table from the real config.
- **Trip orchestration** (bridge to Ch.4): backend dispatcher → Nav2 goal → drive along lane → arrival → §3.4.3 ArUco re-localization → progress reported back.

---

## CHAPTER 4: PROPOSED METHOD (II) — AI, BACKEND & WEB SYSTEM

The heaviest chapter. Open with **System requirements** (AI / backend / web — nhom_NamHuy Ch.6 opens exactly this way), then:

### 4.1 Overall Software Architecture
- Block diagram: 3 web UIs (kiosk / customer_ui / management panel) + robot (Ch.3 stack) ↔ FastAPI backend ↔ **LangGraph agent** ↔ LLM (Ollama, self-hosted on the on-premises server) ↔ SQLite/vector DB. Main flows: (a) voice ordering at the table, (b) order → kitchen, (c) manager monitoring, (d) backend → robot navigation goals.

### 4.2 Voice Processing Pipeline (VAD → STT → Agent → TTS)
- Mic → Silero VAD → faster-whisper (Whisper medium, `language=vi`) → agent → TTS; what runs on the robot's voice device (VAD+STT) vs. the server (agent/LLM); note honestly that TTS is not yet wired in — replies are currently shown as text; per-stage latency. Sequence diagram.

### 4.3 Orchestration Agent (LangGraph) — the heart of the system
- Draw your actual graph: `START → router → (order/search/payment/chat worker) → validator → tools → state_updater → (multi-intent loop) → END`. Explain AgentState (messages, active_cart, order_stage `IDLE → AWAITING_CONFIRMATION → CONFIRMED`, current_intents, table_id) and per-table checkpointer memory. One overview diagram + per-node description + one traced example conversation.

### 4.4 Two-Tier Hybrid Router *(write in the most depth)*
- Tier 1 semantic: sentence embedding → per-intent centroid → cosine → softmax + gap gating (T=0.20, prob≥0.30, gap≥0.20) → ~15 ms fast path.
- Tier 2 SLM: the small Ollama-served instruct model (see `.env` — `qwen3:4b-instruct` per template, `gemma4:e2b-it-qat` code default), 14 few-shot examples, structured `IntentPrediction`, multi-intent support.
- Centroid construction from `utterances.json`; temperature calibration. Two-tier diagram + fast-path vs. fallback example table; preview 91.25% (details in Ch.5).

### 4.5 Knowledge Retrieval System (Hybrid RAG)
- Menu data source; chunking + embedding; BM25 + FAISS in parallel; RRF fusion; Vietnamese normalization; top-k/threshold. Pipeline diagram + one example query.

### 4.6 Workers, Tools & Validator
- 4 workers (order/search/payment via the worker LLM; chat worker is pure code, no LLM); 5 Pydantic tools (`search`, `sync_cart`, `confirm_order`, `request_payment` with VietQR, `verify_payment`); deterministic validator (fuzzy dish-name check before tool calls, loop back on failure); sequential multi-intent handling. Tool table + validate→tool→state_updater loop diagram.

### 4.7 Backend (FastAPI) & Database
- API/WebSocket design; per-table sessions; SQLite schema (ERD: dish, order, table, status); config via pydantic-settings; deployment: self-hosted single server on the LAN, remote access via WireGuard mesh VPN (Netbird) — no cloud, no tunneling service. Endpoint table.

### 4.8 The Three Web Interfaces
- 4.8.1 Kiosk (booking: table + party size); 4.8.2 customer_ui on the robot's **7" LCD** (menu, tap/voice ordering, confirmation); 4.8.3 Management panel (robot status, per-table status, kitchen KDS). Screenshot + functions + one real scenario each; state honestly what is unfinished.

---

## CHAPTER 5: EXPERIMENTS AND RESULTS

Check every objective from §1.3 with numbers. Follow the sample theses' pattern: fabricated/assembled model first, then per-subsystem results with evaluation criteria stated before each experiment.

### 5.1 Robot Model & Hardware Connection Diagram *(the ONLY place hardware is detailed)*
- **Component list table.** The robot integrates the following components (this is the definitive component list — reuse these exact model names + specs consistently throughout the report):

| # | Component | Model | Key specifications | Role in the system | Interface |
|---|---|---|---|---|---|
| 1 | 2-D LiDAR | RPLiDAR **A2M8** | 360° scan, ~12 m range, 2-D laser scan | SLAM & localization (RTAB-Map), obstacle scan for Nav2 | USB/UART |
| 2 | RGB-D camera | Intel RealSense **D435** | RGB-D, 87°×58° depth FOV, active stereo depth | RTAB-Map RGB-D input; ArUco marker detection for docking | USB 3.0 |
| 3 | IMU | **MPU6050** (soldered on the base STM32 board) | 6-DOF (3-axis accel + 3-axis gyro), I²C | Angular-rate source fused into EKF odometry | I²C → STM32 → serial |
| 4 | Drive motors + encoders | 2× **MC520P30** 12 V DC gear motor | 12 V, **1024 PPR** Hall encoder, gear ratio **1:30** | Differential-drive actuation; wheel odometry (encoder ticks) | Motor driver ↔ STM32 |
| 5 | Display | **7-inch LCD** | 7″ panel | On-robot customer UI (menu, voice ordering) | HDMI + USB |
| 6 | Onboard computer | **NVIDIA Jetson Orin Nano 8GB** *(added)* | runs the full ROS2 stack + edge voice | ROS2 nodes, sensor drivers, voice capture | — |
| 7 | Base controller | **STM32 board** *(base)* | encoder counting, kinematics, motor PID @ 50 Hz; reads MPU6050 | low-level control; wheel-velocity + raw IMU over serial | serial ↔ Jetson |
| 8 | Power system | *(fill in battery model)* | *(voltage / capacity)* | powers base + sensors + compute | power tree |

  **Purchased base vs. added (boundary):** the commercial TWD base provides the chassis, motors + encoders, motor driver, the **STM32 board with the on-board MPU6050**, and the battery; its firmware ends at reporting wheel velocities + raw IMU over serial. **Added for this thesis:** the **Jetson Orin Nano 8GB** (runs all ROS2), the **RPLiDAR A2M8**, the **Intel RealSense D435**, and the **7-inch LCD**. State this once here.
- **ROS2 robot model (URDF):** the URDF (links, wheel spacing, sensor mounting poses) + a render of the robot model. *(Moved here from the method chapter.)*
- **TF tree figure:** `map → odom → base_footprint → base_link → laser_link / camera_link / imu_link`; capture with `ros2 run tf2_tools view_frames` (do not hand-draw).
- **ROS2 node/topic graph:** `rqt_graph` of the running system + a node table (node, in/out topics, rate): base driver, EKF (`/odometry/filtered`), LiDAR (`/scan`), D435 (RGB/depth), RTAB-Map, Nav2, ArUco/docking, backend bridge.
- **Platform constants table (the numeric values the Ch.3 symbols refer to):** `D`, `r = D/2`, `W`, `P = 1024 PPR`, ×4 quadrature, `G = 30`, `N = P·4·G`, loop rate 50 Hz, `V_x,max`, `V_ω,max`. ⚠️ **Verify which shaft the 1024 PPR sits on** (motor shaft → `N = 122880`; wheel shaft → `N = 4096`): 10-revolution hand-count test. Measure `D`, `W` (straight-line + in-place-rotation tests).
- **Connection/wiring block diagram**: motors ↔ driver ↔ STM32; encoders → STM32; MPU6050 → I²C → STM32; STM32 ↔ Jetson (serial); A2M8 → USB; D435 → USB 3.0; 7″ LCD → HDMI + USB; power tree. One clean figure.
- Photos of the physical robot and the service-lane / marker layout. One sentence restating the purchased-base boundary.

### 5.2 Evaluation Criteria
- Metrics table covering all subsystems: odometry return-to-start / drift; navigation success rate + trip time; safe distance to obstacles; ArUco docking error (cm, deg; mean ± std, ≥10 runs/table); router accuracy; retrieval precision/recall/hit-rate@k; E2E task completion; voice per-stage latency; STT accuracy. (nhom_NamHuy states criteria before each experiment — do the same.)

### 5.3 ROS2 Experiments — Simulation *(all simulation lives here, not in the method chapter)*
- Same ROS2 stack/config as the real robot in a Gazebo service-lane world (diff-drive model with real `r`, `W`, sensor poses; 2D map). Mapping, localization, navigation (and docking once implemented); kitchen→table scenarios; sim-to-real differences (slip, sensor noise, ArUco lighting) and fixes; sim vs. real side-by-side. Screenshots + result tables.

### 5.4 ROS2 Experiments — Real World
- (a) Odometry: closed-path tests, encoder-only vs. EKF-fused error table (full data for the §3.2 figure). (b) Real service-lane map + loop closures. (c) Navigation: N trips per table, success rate, average time; **obstacle test = an object placed in the lane** (the robot detects it and stops/re-routes) — no pedestrian tests, since the lane is separated from customers. (d) Docking: per-table statistics, worst case; photo frames.

### 5.5 AI System Experiments *(run the eval scripts)*
- Router (`eval_router.py`): 91.25% on 80 cases; fast-path vs. fallback ratio; per-branch latency; honest analysis of the 7 failure cases (SEARCH↔PAYMENT confusion).
- Retrieval (`eval_retrieval.py`): hybrid vs. BM25-only vs. vector-only (shows RRF helps).
- E2E (`eval_e2e.py`): completion rate of multi-step ordering conversations.
- Number tables + charts + a few correct/incorrect examples.

### 5.6 Web System Experiments
- Test-case table (action – expected – result): booking (kiosk) → ordering (customer_ui) → kitchen/panel display; state synchronization.

---

## CHAPTER 6: CONCLUSION AND FUTURE WORKS

### 6.1 Conclusion
- Tick each §1.3 objective against Ch.5 numbers; summarize both contribution legs (autonomous TWD navigation + docking; hybrid router + agentic workflow + hybrid RAG).

### 6.2 Limitations
- Candidly: consumer-grade IMU drift; wheel slip; docking sensitivity to lighting; router SEARCH↔PAYMENT confusion; cloud LLM latency; unfinished UI/TTS blocks; single-robot, single-restaurant scope.

### 6.3 Future Works
- Tie each to a limitation: complete all UIs + TTS; better IMU / add visual odometry; dynamic obstacle handling; on-device LLM (quantization); multi-robot coordination; returning-customer recognition.

---

## Front matter (write last)
- Abstract (1 page: problem, method, key numbers), lists of tables/figures/acronyms (auto-generated — the sample theses all have them), acknowledgements, declaration per the university template. All in English (check which title pages must stay bilingual).

## Suggested writing order
1. **Ch.4** (agent — strongest, freshest) → 2. **Ch.3** (ROS2) → 3. **Ch.5** (run odometry/docking tests + AI evals for numbers) → 4. **Ch.2** (pull kinematics from XTARK + fusion from ProjectAI + generic sections) → 5. **Ch.1 + Ch.6** → 6. Abstract + front matter.

## Source → section mapping
| Source | Sections |
|---|---|
| XTARK tutorial *(private — never cited)* | 2.1 (taxonomy skeleton), **2.2 (derivation logic + figure; report standard notation V_A/V_B/W/V_ω/V_x/V_y)** → applied in 3.4, 3.8.2 |
| ProjectAI *(private — never cited; port in full + apply FIX 1–5)* | **2.5–2.6 (full math, restructured)** → 3.5 (implementation/config, rewritten for the real robot) → 5.4 (odometry results) |
| nhom_Trung / nhom_Canh | chapter naming, English tone, TOC style, experiment organization |
| nhom_NamHuy | Ch.2 topic coverage, RTAB-Map/DWA depth, AI+web chapter split, "criteria-first" experiments, model-fabrication-opens-Ch.5 |
| AIWaiter repo (`agent/`, `services/`, `interfaces/`, `evals/`, frontends) | 4.1–4.8, 5.5–5.6 |
| Robot workspace (launch, URDF, Nav2/RTAB configs, docking node) | 3.2–3.9, 5.3–5.4 |
