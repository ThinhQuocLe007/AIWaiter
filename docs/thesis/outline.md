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
    2.1 Overview: Automation of the Restaurant Service Loop
    2.2 Autonomous Mobile Robot
        2.2.1 Wheel Odometry and Sensor Fusion
        2.2.2 SLAM and Map Building
        2.2.3 Autonomous Navigation
        2.2.4 Fiducial Marker Docking
        2.2.5 Prior ROS2 Delivery Robot Research
    2.3 Vietnamese Voice Understanding
        2.3.1 Voice Activity Detection
        2.3.2 Speech-to-Text for Vietnamese
        2.3.3 Text-to-Speech for Vietnamese
    2.4 Conversational AI Agent
        2.4.1 From General-Purpose LLM to Task-Oriented Agent
        2.4.2 Agent Architectures — The Orchestration Layer
        2.4.3 Large Language Models — The Reasoning Component
        2.4.4 Intent Classification — The Routing Layer
        2.4.5 Action Validation — The Safety Layer
        2.4.6 Memory and State Management in Conversational Agents
        2.4.7 Agent Planning, Tool Composition, and Domain Adaptation
    2.5 Menu Knowledge Retrieval
        2.5.1 The Knowledge Problem and Standard RAG
        2.5.2 Embedding Models
        2.5.3 Indexing and Search
        2.5.4 Result Fusion
        2.5.5 Beyond Retrieve→Generate: Rewriting, Evaluation, Context
    2.6 Restaurant Operations & Fleet Management
        2.6.1 Multi-Robot Task Assignment
        2.6.2 Dynamic Robot-Table Voice Binding
        2.6.3 Telemetry, Liveness, and Fault Recovery
        2.6.4 Real-Time Restaurant State Synchronization
     2.7 Multi-Role Web Interfaces for AI-Driven Restaurant Operations
         2.7.1 Single-Page Application Frameworks — Comparison
         2.7.2 Component Libraries
         2.7.3 Build Tooling
         2.7.4 Real-Time Communication Patterns
         2.7.5 Multi-Role SPA Architecture
     2.8 Edge Computing Platform
         2.8.1 Jetson Orin Nano — Hardware & Software Stack
         2.8.2 Sensor Interfaces
         2.8.3 Prior Work on Jetson in Robotics
    2.9 Summary: Needs → Requirements Traceability

3. PROPOSED METHOD (I) — ROBOT CONTROL AND NAVIGATION
   3.1 System Overview (shared with Chapter 4)
   3.2 System Requirements
   3.3 Design Challenges (C1–C4)
   3.4 Robot Platform & Hardware Setup
   3.5 Wheel Odometry and EKF Sensor Fusion          → C1
   3.6 Map Building with RTAB-Map                     → C3
   3.7 Localization and ArUco-Based Docking            → C2
   3.8 Autonomous Navigation & Dynamic Goal Assignment → C4

4. PROPOSED METHOD (II) — AI, BACKEND & WEB SYSTEM
   4.1 AI System Requirements
   4.2 Design Challenges (C5–C10)
   4.3 Software System Architecture
   4.4 Edge Voice Pipeline                → Need 2, C6
        4.4.1 Component Selection
        4.4.2 Threaded Pipeline Architecture
4.5 Conversational Agent               → Need 3, C5, C7
        4.5.1 Agent Architecture
        4.5.2 Intent Classification
        4.5.3 Specialized Agents and Prompt Architecture
        4.5.4 Deterministic Validator
        4.5.5 State Management
        4.5.6 Response Generation
   4.6 Knowledge Retrieval Pipeline       → Need 4, C8
       4.6.1 Query Rewriting
       4.6.2 Hybrid Retrieval
       4.6.3 Result Rephrasing
       4.6.4 Multi-Turn Search Context
4.7 Backend Orchestrator               → Need 5, C9, C10
         4.7.1 API and Real-Time Events
         4.7.2 Session Lifecycle
         4.7.3 Fleet Management
         4.7.4 Database Schema
4.8 Web Interfaces                     → Need 6
        4.8.1 Customer Tablet
        4.8.2 Entrance Kiosk
        4.8.3 Management Panel
4.9 Deployment Topology

 5. EXPERIMENTS AND RESULTS
    5.1 System Under Test
        5.1.1 Server Hardware
        5.1.2 Robot Platform
        5.1.3 Software & Network Stack
    5.2 Evaluation Design
        5.2.1 Datasets Summary
        5.2.2 Metrics Definition
        5.2.3 Statistical Protocol
        5.2.4 Experiment Inventory & Reproduction
    5.3 ROS2 Navigation Experiments        → Need 1
        5.3.1 Odometry Accuracy
        5.3.2 Map Building & Localization
        5.3.3 Navigation & Docking
        5.3.4 Dynamic Goal Assignment
    5.4 AI Agent Experiments               → Need 3, Need 4
        5.4.1 Intent Classification & Routing
        5.4.2 Action Validation & Safety
        5.4.3 Multi-Intent Execution & Verbalisation
        5.4.4 Knowledge Retrieval
        5.4.5 End-to-End System Evaluation
        5.4.6 Agent Latency & Cost
    5.5 Backend & Web System Experiments    → Need 5, Need 6
        5.5.1 API Responsiveness & WebSocket Propagation
        5.5.2 Multi-Table Concurrency & Session Isolation
        5.5.3 Fleet Management & Fault Recovery
        5.5.4 Multi-Role State Consistency
    5.6 Results Summary
        5.6.1 Objective Scorecard
        5.6.2 Failure Budget Allocation
        5.6.3 Need → Requirement → Experiment Traceability
        5.6.4 Threats to Validity

6. CONCLUSION AND FUTURE WORKS
   6.1 Conclusion
   6.2 Limitations
   6.3 Future Works

Appendices
Front Matter
```

---

## CHAPTER 1: INTRODUCTION

> **Chapter requirements — this chapter answers:**
> - What is this project? (1.1 Overview)
> - Why is it worth doing? (1.2 Motivation)
> - What specific, measurable targets must be hit? (1.3 Objectives)
> - What is in scope and out of scope? (1.4 Scope)
> - How was the work conducted? (1.5 Research Methodology)
> - How is the rest of this report organized? (1.6 Report Structure)

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
- **Intent router accuracy ≥ 90%** (see §5.4.1 for measured results)
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

> **Chapter requirements — this chapter answers:**
> - What existing technologies address each need? (Survey)
> - What does each do well, and what are its limits? (Strengths + weaknesses)
> - If we USE an off-the-shelf component (VAD, STT, TTS, embedding model, LLM, frontend framework, etc.): what options exist, and what distinguishes them? (Comparison table → Ch.3/Ch.4 selects from this table. The **selection criteria themselves belong to Ch.3/Ch.4**, not here — Ch.2 reports what the options *are* and what the literature does and does not establish about them; it does not state our requirements, walk the elimination, or resolve the trade-off.)
> - If we BUILD something new (agent architecture, validator, RAG pipeline, fleet dispatcher, etc.): what prior approaches exist, and why are they insufficient? (Survey → identify research gap → Ch.4 proposes method)
>
> **Rules for Chapter 2:**
> - No challenges (C1–C10 live in Ch.3/Ch.4). No proposed solutions. No "we did X" or "we built Y." No system design decisions.
> - Each section does three things: (1) states the need and why it matters, (2) surveys prior work that has attempted to meet it, (3) ends with either a comparison table (for off-the-shelf selection) or a gap statement (for new design).
> - The final summary (§2.9) maps each gap/selection to the system requirements in Ch.3 and Ch.4.

> **Principle:** This chapter is organized around five unsolved needs — real problems the literature has not fully addressed. Each section does three things: (1) states the need and why it matters, (2) surveys prior work that has attempted to meet it, (3) analyzes why those attempts fell short, yielding a specific gap. No implementation details or design decisions appear here. The final summary (§2.7) maps each gap to the system requirements it motivates in Chapter 3 (navigation) and Chapter 4 (AI/backend/web), which are validated in Chapter 5.

---

### 2.1 Overview: Automation of the Restaurant Service Loop

- **The landscape:** service robots for food delivery have been deployed commercially at scale. Free-navigation platforms — Bear Robotics Servi (2017), Pudu Bellabot (2016), Keenon T-series (2010) — use LiDAR and RGB-D SLAM for autonomous navigation in restaurant environments, with Pudu reporting over 40,000 units deployed across 600+ cities. Track-based platforms — Alibaba Robot.He (Shanghai, 2018) — mount pod-shaped AGVs on fixed rails alongside tables, adapted from Cainiao warehouse logistics. Both categories reliably deliver food but are closed appliances: their interaction model is a touchscreen or pre-recorded greeting; they have no speech recognition, no natural language understanding, and no third-party AI integration possible. The software stack is proprietary — developers cannot add an LLM agent, a Vietnamese speech pipeline, or a custom fleet dispatcher. The robot does one thing (delivers) and cannot be extended to do anything else.

- **The integration gap:** no existing system combines Vietnamese voice understanding, AI-driven action (ordering, payment, recommendation), and physical robot delivery into a single operational system. The individual components exist independently — navigation robots, speech pipelines, conversational models, retrieval systems, web interfaces — but have never been integrated into a deployable system where an AI agent directly drives restaurant operations and robot behavior. The following sections (§2.2–§2.8) survey each component category, identifying what prior work has achieved and where the integration gaps remain.

---

### 2.2 Autonomous Mobile Robot

> *A robot must navigate from kitchen to table when ordered food is ready — but "which table" is not known until the AI agent decides. This section surveys autonomous mobile robot technologies — odometry, SLAM, navigation, and fiducial marker docking — and identifies the gap: prior systems drive to pre-set waypoints, but none couple navigation goals dynamically to an external AI agent that assigns destinations based on live restaurant events.*

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

### 2.3 Vietnamese Voice Understanding

> *Vietnamese speech recognition, voice activity detection, and speech synthesis exist as standalone research areas. This section surveys each component: how it works, what existing methods exist, and what prior evaluations have been conducted. For each component, a comparison table is presented; the selection from these tables occurs in §4.4. The edge hardware that hosts these components is surveyed in §2.8.*

#### 2.3.1 Voice Activity Detection

Voice activity detection determines the boundaries of a spoken utterance in a continuous audio stream — when did the customer start speaking, and when did they stop? This is the first processing stage in the voice pipeline. Its output (a trimmed audio segment containing exactly one utterance) feeds directly into the STT model. If VAD cuts off speech prematurely, the STT model transcribes a truncated sentence; if VAD triggers on background noise, the pipeline processes restaurant clatter as if it were an order.

Existing VAD approaches fall into three categories:

- **Energy-threshold VAD.** Classifies any audio frame whose RMS amplitude exceeds a fixed threshold as speech. It is the simplest approach and works in quiet recording studios. In noisy environments, the threshold cannot discriminate between speech and non-speech sounds of similar amplitude — plate clatter and chair scrapes trigger false detections [2.3.1].

- **Lightweight neural VAD.** Silero VAD (~1.5 MB, language-agnostic, CPU real-time) is the dominant open-source model. It classifies each audio frame based on learned spectral patterns rather than raw energy, exposing a configurable sensitivity threshold [2.3.2]. WebRTC VAD uses a Gaussian Mixture Model — lighter weight (~100 KB) but less accurate in noise [2.3.3]. Both run on CPU without GPU dependency, making them suitable for always-on edge deployment.

- **Deep learning VAD.** Systems such as pyannote.audio and NVIDIA NeMo VAD achieve higher accuracy by using larger neural architectures, but require GPU inference [2.3.4]. On an edge device where GPU memory is shared with STT and robot control, always-on GPU inference is infeasible.

| Model | Size | Inference | Accuracy (noisy) | Edge-Suitable | Prior Evaluation |
|-------|------|-----------|-------------------|:---:|------------------|
| Energy threshold | N/A | N/A | Poor | Yes | Not viable in noise [2.3.1] |
| Silero VAD | ~1.5 MB | CPU, real-time | Good | Yes | Multilingual benchmarks, quiet conditions [2.3.2] |
| WebRTC VAD | ~100 KB | CPU, real-time | Moderate | Yes | Telephony speech, quiet conditions [2.3.3] |
| pyannote VAD | ~100 MB | GPU | High | No | Meeting/test corpora [2.3.4] |
| NeMo VAD | ~200 MB | GPU | High | No | NVIDIA benchmarks [2.3.4] |

Prior work has evaluated Silero VAD on multilingual telephone speech and meeting recordings in quiet or moderately noisy conditions. WebRTC VAD has been tested on telephony-quality speech. Neither has been benchmarked on Vietnamese speech corpora or under restaurant noise profiles. The available evaluation data covers general-domain speech; Vietnamese-specific VAD performance and restaurant-noise robustness are not characterized in existing benchmarks.

#### 2.3.2 Speech-to-Text for Vietnamese

Speech-to-text converts the audio segment isolated by VAD into Vietnamese text. The transcribed text is the input to every downstream component: the intent classifier, the agent's LLM, the validator, and the response generator all operate on this text. The accuracy of this stage determines the upper bound of the entire conversational pipeline.

Existing STT approaches for Vietnamese fall into two categories: on-device models and cloud services.

On-device models are built on the Whisper architecture, a Transformer-based encoder-decoder trained on 680,000 hours of multilingual web-scraped speech [2.3.5]. Whisper's Vietnamese capability is partial — Vietnamese was present in the training data but was not a primary target language. The model family scales across four sizes: tiny (39M parameters) through large-v3 (1.55B parameters). Larger models achieve lower word error rates but require proportionally more VRAM and inference time [2.3.6]. faster-whisper [2.3.7] is a reimplementation using CTranslate2 for optimized inference; with 8-bit quantization, it reduces latency by approximately 4× compared to the standard Whisper implementation and reduces VRAM usage by roughly half, making the medium-sized model deployable on edge hardware with approximately 1.5 GB of memory.

PhoWhisper [2.3.8] addresses the Vietnamese-specific limitation by fine-tuning Whisper on Vietnamese speech data. The fine-tuning achieves an estimated 5–10% word error rate improvement over the base multilingual Whisper, with the largest gains concentrated in tonal diacritics — the dimension where general multilingual models most underperform Vietnamese. PhoWhisper is compatible with faster-whisper's CTranslate2 backend, benefiting from the same latency and memory optimizations.

Cloud services — Google Cloud Speech-to-Text, Viettel AI STT, FPT.AI STT [2.3.9]–[2.3.11] — offer dedicated Vietnamese speech recognition with estimated word error rates of 5–8% on clean speech. These services run on server-grade infrastructure with models trained on large Vietnamese corpora. Their primary limitation is the internet dependency: every utterance requires a network round-trip, introducing variable latency outside the system's control, and a WiFi outage renders the pipeline inoperable.

| Model / Service | Vietnamese | Edge Deployable | Offline | Latency (3s utt.) | VRAM | Est. WER (clean VN) |
|-----------------|:---:|:---:|:---:|:---:|:---:|:---:|
| Whisper tiny | Partial (multilingual) | Yes | Yes | ~300ms | ~0.5 GB | 25–35% |
| Whisper base | Partial (multilingual) | Yes | Yes | ~400ms | ~0.8 GB | 20–30% |
| Whisper medium | Partial (multilingual) | Yes | Yes | ~800ms | ~3 GB | 15–20% |
| PhoWhisper (medium, faster-whisper) | Yes | Yes | Yes | ~800ms | ~3.5 GB | 10–15% |
| Whisper large-v3 | Partial (multilingual) | Borderline | Yes | ~1.5s | ~3 GB | 10–15% |
| Google Cloud STT | Yes | No | No | ~200ms + RTT | 0 (cloud) | 5–8% |
| Viettel AI STT | Yes | No | No | ~200ms + RTT | 0 (cloud) | 5–8% |
| FPT.AI STT | Yes | No | No | ~200ms + RTT | 0 (cloud) | 5–8% |

PhoWhisper has been evaluated on Vietnamese speech benchmarks — the VLSP (Vietnamese Language and Speech Processing) dataset and related academic corpora [2.3.12]. These benchmarks consist of read speech in quiet recording conditions with standard Northern or Southern Vietnamese pronunciation. Reported metrics include word error rate and character error rate, confirming the 5–10% improvement over base Whisper on Vietnamese. No benchmarks exist for Vietnamese STT under noisy conditions, informal speech patterns, or domain-specific vocabulary such as restaurant dish names.

#### 2.3.3 Text-to-Speech for Vietnamese

Text-to-speech converts the agent's Vietnamese text response into audible speech through the robot's speaker. TTS quality is measured on two dimensions: intelligibility (can the customer understand the words?) and naturalness (does the voice sound appropriate for a service context?). Latency must also fit within the overall voice interaction budget.

Existing TTS approaches for Vietnamese fall into the same two categories as STT: on-device models and cloud services.

On-device TTS is represented by Piper TTS [2.3.13], which uses the VITS (Variational Inference with adversarial learning for end-to-end Text-to-Speech) architecture — a single-stage model that converts text directly to waveform without intermediate spectrogram generation. Piper provides one community-trained Vietnamese voice model (~200 MB), runs on CPU with approximately 500ms latency per sentence, and is the only offline, edge-deployable Vietnamese TTS option. Its naturalness is moderate: clearly synthetic but intelligible, with correct tone production for Vietnamese diacritics [2.3.14].

Cloud services — edge-tts (Microsoft Azure Neural TTS), Google Cloud TTS, vbee, FPT.AI TTS [2.3.15]–[2.3.17] — offer multiple Vietnamese neural voices (male, female, regional accents) with high naturalness. These are trained on studio-quality voice recordings using architectures such as WaveNet, FastSpeech, and VITS. Their limitation mirrors cloud STT: internet dependency for every sentence, variable network latency, and the assumption of server-grade infrastructure.

| Engine | Offline | Edge Deployable | Latency (per sent.) | VRAM | Naturalness | Vietnamese Voices |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| Piper TTS (VITS) | Yes | Yes (CPU) | ~500ms | ~200 MB | Moderate | 1 community-trained |
| edge-tts (Azure) | No | No (cloud) | ~300ms + RTT | 0 (cloud) | High | Multiple neural |
| vbee TTS | No | No (cloud) | ~300ms + RTT | 0 (cloud) | High | Multiple |
| FPT.AI TTS | No | No (cloud) | ~300ms + RTT | 0 (cloud) | High | Multiple |
| Google Cloud TTS | No | No (cloud) | ~200ms + RTT | 0 (cloud) | Very High | WaveNet voices |

TTS quality is typically evaluated through Mean Opinion Score (MOS) studies where listeners rate speech samples on a 1–5 naturalness scale. Cloud neural voices consistently score in the 4.0–4.5 range; Piper's Vietnamese voice is estimated in the 2.5–3.5 range [2.3.14]. These evaluations were conducted in quiet listening environments with general-domain Vietnamese text (news sentences, conversational phrases). No MOS evaluations exist for Vietnamese restaurant-domain utterances or for TTS playback under restaurant ambient noise conditions.

---

---

### 2.4 Conversational AI Agent

Traces the evolution from general-purpose LLM to task-oriented agent: Transformers → post-hoc parsing → function calling → the six layers that govern LLM-tool interaction. The section surveys each layer in turn: architectures for orchestrating LLM-tool interaction, the LLM reasoning engine, intent classification, action validation, memory and state management, and planning with domain adaptation. Each subsection identifies what prior work has achieved and where documented limitations remain for Vietnamese task-oriented dialogue.

#### 2.4.1 From General-Purpose LLM to Task-Oriented Agent

Establishes the conceptual trajectory: the Transformer architecture and scaling laws that produced LLMs, the limitation of text-only generation for transactional domains, the brittleness of post-hoc parsing, and the function-calling mechanism that made structured tool invocation a first-class API capability. Concludes that function calling provides the mechanism for action but the layers surrounding the LLM determine whether actions are safe. [Figure 2.7 — Function calling mechanism.]

#### 2.4.2 Agent Architectures — The Orchestration Layer

Surveys four architectural patterns documented in the agent literature: chain-based (LangChain LCEL — deterministic but rigid), autonomous reasoning loops (ReAct, AutoGPT — flexible but no termination guarantee, no process enforcement), graph-based (LangGraph — structural governance via topology, conditional edges, checkpointers, circuit breakers), and multi-agent (AutoGen, CrewAI, CAMEL — specialization at the cost of LLM-mediated coordination and attention dilution). Each pattern described with its documented strengths, limitations, and evaluation scope. [Figure 2.8 — Four architecture patterns. Table 2.4a — Architecture property comparison.] No architecture has been evaluated for Vietnamese task-oriented dialogue.

#### 2.4.3 Large Language Models — The Reasoning Component

Surveys three categories of Vietnamese-capable LLMs: Vietnamese-specific models (PhoGPT — excellent language quality, no function calling), open-weight multilingual models (Qwen2.5, Llama 3, Gemma 2 — function calling via BFCL-benchmarked APIs, moderate Vietnamese quality), and commercial API models (GPT-4o, Claude, Gemini — best quality and tool-calling, cloud-dependent). Covers cross-cutting dimensions: context window capacities (4K to 1M tokens, bounded by "lost in the middle" findings) and token consumption of Vietnamese text. Surveys serving infrastructure: Ollama (single-GPU local serving), vLLM (concurrent throughput), llama.cpp (quantization trades quality for VRAM). [Table 2.4b — Function-calling and Vietnamese quality. Table 2.4c — Context window capacities.] The three documented properties have been evaluated independently but never jointly.

#### 2.4.4 Intent Classification — The Routing Layer

Surveys five routing approaches: rule-based/SVM classifiers (Rasa, Dialogflow — fast, deterministic, but language-specific and stateless), lightweight neural classifiers (fastText, SetFit — subword robustness, still stateless), semantic centroid routing (embedding-space similarity — handles domain vocabulary, fails on teencode/context/multi-intent), LLM-based routing (handles all accuracy criteria, cost is latency and non-determinism; decomposition-only variant reduces LLM role but untested on Vietnamese), and state-augmented classification (dialogue state features improve context-dependent accuracy — demonstrated on English, not Vietnamese). [Figure 2.9 — Five routing approaches. Table 2.4d — Routing approach comparison.] The gap: no approach combines speed and determinism with Vietnamese-language handling — using an LLM only for utterance decomposition while a Vietnamese-aware, state-augmented classifier handles all other cases.

#### 2.4.5 Action Validation — The Safety Layer

Surveys three approaches to preventing argument-level hallucination: constrained decoding (schema enforcement — syntax only, no semantic check), RAG grounding (injecting authoritative data into prompt — reduces error probability, no detection mechanism for remaining errors), and human-in-the-loop (eliminates all errors at the cost of autonomy). The structural insight: all three operate at generation time; none provides autonomous post-generation inspection against an authoritative source. [Figure 2.10 — Generation-time vs. post-generation validation. Table 2.4e — Validation approach properties.] An autonomous, deterministic, post-generation validator that inspects every tool call argument and blocks invalid calls has not been demonstrated.

#### 2.4.6 Memory and State Management in Conversational Agents

Surveys four memory strategies: sliding window, periodic summarization (MemGPT), vector-based retrieval (MemoryBank), and hybrid approaches (LongMem). Documents the "lost in the middle" phenomenon and attention boundary preference as constraints on all strategies, tightened further by Vietnamese token consumption. Identifies the distinction between conversation history and application state (cart, order stage, search context) as a separation that general-purpose frameworks do not natively provide. Documents dialogue state tracking and LangGraph checkpointing as mechanisms for session-scoped persistence. [Figure 2.11 — Memory strategies and application state separation.] No prior work characterizes a memory architecture for Vietnamese conversations combining conversation history, persistent state, session isolation, and context window allocation.

#### 2.4.7 Agent Planning, Tool Composition, and Domain Adaptation

Covers three cross-cutting concerns. Tool composition: sequential, parallel, and conditional patterns; the documented gap between per-call tool selection accuracy and compositional correctness. Prompt engineering for domain adaptation: system prompts, few-shot examples, dynamic context injection, and DSPy optimization — techniques documented in the literature but untested on Vietnamese restaurant ordering. Cross-domain patterns: healthcare, customer service, and code generation agents sharing a validation-gated execution model (LLM proposes, deterministic code validates) that has not been formally characterized as a general architectural requirement. [Figure 2.12 — Tool composition patterns and domain adaptation stack.]

Concludes with a synthesis of the integration gap: three paragraphs identifying (1) layer interdependence that prior evaluations do not capture, (2) Vietnamese linguistic properties that compound design constraints at every layer simultaneously, and (3) the validation-gated execution pattern that has not been combined with the other five layers for Vietnamese task-oriented dialogue.

---

### 2.5 Menu Knowledge Retrieval

> *Retrieval-augmented generation (RAG) grounds LLM outputs in domain-specific documents. This section surveys the RAG pipeline bottom-up: why retrieval is needed and how the standard RAG architecture evolved from naive embedding→retrieve→generate to advanced modular pipelines (§2.5.1); the embedding models — dense (bi-encoders) and sparse (BM25) — that convert text into searchable representations, including the Vietnamese-specific preprocessing prerequisite of word segmentation (§2.5.2); how these representations are indexed and searched — dense vector indices (FAISS) and sparse inverted indices (§2.5.3); how results from multiple retrieval strategies are fused into a single ranking (§2.5.4); and pipeline extensions beyond the standard retrieve→generate paradigm — query rewriting, post-retrieval evaluation, and multi-turn search context (§2.5.5).*

#### 2.5.1 The Knowledge Problem and Standard RAG

- **Why retrieval is necessary:** closed-book hallucination. LLM training data is frozen; domain-specific knowledge (a restaurant's menu) is absent. Without retrieval, the LLM fabricates plausible but incorrect domain facts.
- **The evolution of the RAG architecture:**
  - **Naive RAG:** the classic pipeline — embed documents offline via a sentence encoder, store in a vector index, at query time embed the query and retrieve top-k most similar documents, inject into the LLM prompt as grounding context (Lewis et al., 2020).
  - **Advanced RAG:** improvements on the naive pipeline — chunk optimization (sliding window, semantic splitting), re-ranking retrieved documents for better precision, query expansion before retrieval.
  - **Modular RAG:** the modern architecture pattern — retrieval, rewriting, evaluation, and generation are independent modules with configurable composition. This modularity enables per-domain optimization but introduces the challenge of coordinating modules that each operate on different assumptions about the query and documents.
- **The retrieval assumption and its failure mode.** All RAG variants share one assumption: the query embedding lies close to relevant document embeddings in vector space. This holds when the query shares vocabulary with the target documents. It fails when the query describes information needs through terms absent from the document vocabulary — a retrieval failure that is structural (not a matter of index quality or encoder choice) because the query and documents occupy disconnected semantic regions.
- **→ Gap.** The standard RAG pipeline — in all three variants, naive through modular — treats the LLM as a passive consumer of retrieved context: retrieval happens, then the LLM generates. No prior pipeline architecture gives the LLM an active role in controlling retrieval quality. The LLM does not decide which retrieval strategy to use, does not inspect the results, and does not adjust its approach when retrieval fails. This architectural gap — the absence of a control loop where the LLM acts as a retrieval quality controller with corrective feedback — is the fundamental limitation that §2.5.5 surveys. The Vietnamese-specific preprocessing concerns (diacritic sensitivity in embeddings, compound-word integrity in segmentation) compound this gap by making retrieval quality more variable and harder to guarantee without active quality control.

#### 2.5.2 Embedding Models

> *Embedding models convert text into representations that can be compared for relevance. Two paradigms exist: dense embeddings produce continuous vectors capturing semantic similarity; sparse embeddings produce high-dimensional term-weight vectors capturing exact lexical match. Vietnamese word segmentation is a prerequisite for both: text must be split into word-level tokens before representation. This section surveys all three — segmentation tools, dense embedding models, and sparse models — as off-the-shelf components. Comparison tables enable selection in Chapter 4.*

- **Vietnamese word segmentation.** Vietnamese script places spaces between syllables, not between words. A compound like "bún bò Huế" is written as three space-separated tokens but is one lexical item. Without segmentation, both dense and sparse models represent per-syllable fragments rather than the compound unit.
  - `underthesea` — CRF-based, trained on Vietnamese Treebank. ~97% accuracy (VLSP 2013), pure Python, ~50 MB.
  - `VnCoreNLP` — Java-based pipeline with richer features (RNN, word embeddings). Higher accuracy than `underthesea` but requires Java runtime.
  - `pyvi` — dictionary-based, pure Python. Lower accuracy, particularly weak on compound terms with ambiguous syllable boundaries.
  - **Comparison table:** accuracy, compound-word handling, deployment requirements, limitations.

- **Dense embedding models.** Sentence encoders that map text to continuous vectors for similarity-based search. Two categories:
  - **Vietnamese-native bi-encoders** — `bkai-foundation-models/vietnamese-bi-encoder` (768-dim, PhoBERT-base, trained on Vietnamese sentence pairs including informal registers), `VoVanPhuc/sup-SimCSE-VietNamese-phobert-base` (SimCSE contrastive training on PhoBERT), `AITeamVN/Vietnamese_Embedding` (1024-dim, BART-based). Evaluated on Vietnamese STS and ViText2Vec benchmarks where they outperform multilingual alternatives, but retrieval-specific benchmarks are unreported.
  - **Multilingual models** — `BAAI/bge-m3` (568M params, native dense+sparse+multi-vector retrieval, SOTA on MIRACL), `intfloat/multilingual-e5-large` (E5 contrastive recipe, top-ranked on cross-lingual retrieval), `paraphrase-multilingual-MiniLM-L12-v2` (384-dim compact baseline). Vietnamese diacritic handling is partial; compound-word boundaries are not recognized.
  - **Comparison table:** dimension, Vietnamese-native, diacritic-aware, strengths (documented), limitations (documented).

- **Sparse/keyword models.** Term-weighting models that rank documents by the frequency and distinctiveness of query terms they contain. BM25 (Robertson & Walker, 1994) is the standard, extending TF-IDF with document-length normalization. Its effectiveness depends on tokenization quality: if compound words are not segmented into single tokens, individual syllables match across unrelated documents. Sparse models capture exact keyword match with high precision; they are blind to semantic relationships — a query with zero vocabulary overlap with the document corpus returns zero results regardless of parameter tuning.
  - **Comparison:** parameters (k1, b), tokenization dependency, strengths (exact match), limitations (vocabulary gap), Vietnamese-specific considerations.

#### 2.5.3 Indexing and Search

> *Once text is converted to representations (§2.5.2), those representations must be stored in a searchable index and queried efficiently. The indexing strategy is determined by the representation: dense vectors require a vector index supporting similarity search; sparse term-weight vectors require an inverted index. This section surveys both indexing approaches and their documented performance characteristics.*

- **Dense vector indexing.** FAISS (Facebook AI Similarity Search, Johnson et al., 2017) is the standard library. Index types range from exact flat search (`IndexFlatL2` — exhaustive comparison, sufficient for small corpora) to approximate indices (`IndexIVFFlat`, `IndexHNSW` — sub-linear search for large-scale deployment). Distance metrics (cosine via L2 on normalized vectors, inner product, Euclidean) determine what "similar" means. The index stores both the vector and a reference to the original document for retrieval.
- **Sparse inverted indexing.** An inverted index maps each vocabulary term to the list of documents containing it, with per-document term frequency and position data. At query time, BM25 scores are computed over the intersection of query terms and document postings lists. For Vietnamese, the term vocabulary depends on word segmentation quality — mis-segmented compound terms fragment the index, diluting term specificity.
- **Comparison table:** index type (flat, IVF, HNSW), search complexity, distance metric, corpus scale suitability, memory footprint.

#### 2.5.4 Result Fusion

> *When multiple retrieval strategies produce separate ranked lists, those lists must be combined into a single ranking. Fusion methods address the incommensurability of scores from different retrievers (BM25 scores are unbounded; cosine similarities are bounded). This section surveys fusion techniques as off-the-shelf methods, with documented properties and limitations.*

- **Reciprocal Rank Fusion (RRF).** Introduced by Cormack et al. (2009) for meta-search. Operates on document ranks, not scores: `score(d) = Σ 1/(k + rank_r(d))` with k=60. Eliminates score normalization entirely — ranking is invariant to score scale. Documents appearing in both result lists receive contributions from both; documents in only one list receive a single contribution.
- **Linear combination.** Weighted sum of normalized scores: `score(d) = α × s₁(d)/‖s₁‖ + (1−α) × s₂(d)/‖s₂‖`. Requires score normalization per retriever and a domain-tuned weight α. Higher potential accuracy than RRF when α is well-calibrated; weights do not transfer across domains or document collections.
- **Condorcet voting.** Pairwise comparison of all documents across retrieval lists. A document "beats" another if it is ranked higher in more retrieval lists. O(n²) comparison cost; no documented advantage over RRF for two-retriever fusion.
- **Comparison table:** score normalization requirement, domain transfer, computational cost, handling of single-list documents.

#### 2.5.5 Beyond Retrieve→Generate: Rewriting, Evaluation, Context

> *The standard RAG pipeline — embed query, retrieve documents, generate — has no architectural position for intervening when retrieval quality is poor. Three classes of extensions have been proposed: pre-retrieval query transformation, post-retrieval result evaluation, and multi-turn context persistence. Each has been evaluated as a point solution on English benchmarks. None addresses the interaction between rewriting, retrieval, and evaluation in a single pipeline.*

- **Pre-retrieval query rewriting.**
  - HyDE (Gao et al., 2023): LLM generates a hypothetical relevant document, embeds it for retrieval instead of the raw query. Insight: LLM-generated text shares vocabulary with real documents even if factually incorrect. Limitation: unbounded generation — the LLM may fabricate terms absent from the corpus, pulling retrieval toward the hallucination.
  - Step-Back Prompting (Zheng et al., 2023): LLM abstracts the query to a higher-level concept, retrieves against the abstraction. Reduces HyDE's hallucination risk but requires the LLM to correctly identify the appropriate abstraction level.
  - Query2Doc (Wang et al., 2023): combines both — LLM generates a rewritten query and a hypothetical document. Two LLM calls per retrieval; documented latency barrier to real-time deployment.
  - All three evaluated on English benchmarks (TREC DL, Web Questions) where the vocabulary gap is formal-question to formal-document. None evaluated on Vietnamese text where the LLM's domain knowledge — the associations that power rewriting — is less grounded.

- **Post-retrieval evaluation.**
  - Self-RAG (Asai et al., 2023): uses fine-tuned reflection tokens for relevance assessment. Fine-tuning requirement limits applicability to models where training infrastructure is available.
  - CRAG (Yan et al., 2024): LLM scores each retrieved document for relevance at inference time (no fine-tuning). Adds one LLM call per retrieval. Evaluated on English QA; effectiveness depends on LLM's relevance assessment accuracy for the target language and domain.
  - FLARE (Jiang et al., 2023): interleaves generation and retrieval — triggers new retrieval when LLM encounters uncertain tokens. Designed for long-form generation; computational cost unsuitable for latency-constrained settings.
  - All three evaluated on English QA and fact-verification where relevance is objectively verifiable. None evaluated on domain-specific retrieval where relevance depends on structured metadata matching (ingredients, taste profile, preparation method).

- **Multi-turn search context.** In conversational search, multiple queries occur within one dialogue session. Dialogue state tracking maintains per-session structured state for slot-filling but is not natively integrated with RAG retrieval. Memory-augmented RAG (MemoryBank, LongMem) persists retrieved context across sessions via vector databases for user modeling, not for within-session retrieval deduplication. No prior work addresses the entity resolution problem specific to multi-turn retrieval: determining whether a new utterance refers to a previously retrieved item and answering from memory rather than re-querying.

- **→ Gap.** Each extension — rewriting, evaluation, context persistence — has been evaluated in isolation as a point improvement on the standard pipeline, on English benchmarks. No prior work connects them into a closed control loop where the LLM acts as a retrieval quality controller: (a) the LLM inspects the query and decides on a retrieval strategy (direct keyword lookup, semantic search, or rewritten query), (b) retrieval executes with quality gating — when all strategies produce noise, the pipeline rejects cleanly with empty results rather than feeding irrelevant documents to the LLM, (c) the LLM inspects the retrieved results, evaluates relevance against the original information need, and rephrases relevant items in natural language — detecting empty results and responding gracefully rather than hallucinating, and (d) the LLM maintains multi-turn context to determine whether a new utterance refers to a previously retrieved item and answers from memory rather than re-querying. The gap is not the absence of any individual extension, but the absence of a pipeline architecture where these extensions operate in a feedback loop with the LLM as the controller — deciding, evaluating, and adjusting — rather than as a passive downstream consumer of whatever retrieval returns.

- **→ Overall Gap for §2.5.** The RAG literature provides individually mature components at each pipeline stage — embedding models, indexing methods, and fusion techniques — surveyed in §2.5.2–§2.5.4 as off-the-shelf selections. The single architectural gap identified is the absence of a retrieval architecture where the LLM functions as an active quality controller in a closed loop — not a passive consumer of retrieved documents. Prior extensions to the standard pipeline (query rewriting, post-retrieval evaluation, multi-turn context) exist as disconnected point solutions, each evaluated in isolation on English benchmarks. No prior work composes them into an architecture where: the LLM rewrites queries and routes to the appropriate retrieval strategy; retrieval results are gated for quality and rejected when all strategies fail; the LLM evaluates and rephrases relevant results against the original intent; and multi-turn context prevents redundant retrieval cycles. This closed-loop control architecture — where the LLM decides how to retrieve, inspects what was retrieved, and adjusts accordingly — is the research contribution addressed in §4.6.

---

### 2.6 Restaurant Operations & Fleet Management

> *A restaurant operator needs a customer tablet for ordering, a kitchen display for cooking, a manager dashboard for oversight, and a robot fleet for delivery — all seeing the same real-time state. An AI agent must drive this state through API calls, triggering robot navigation, kitchen display updates, and session lifecycle transitions. This section surveys existing approaches for fleet management and restaurant operations, and identifies the gap: no lightweight, self-contained system integrates all roles under a single AI-driven real-time state.*

#### 2.6.1 Multi-Robot Task Assignment

The simplest assignment strategy is nearest-idle: assign the task to the closest available robot. For short trips (3–5m kitchen-to-table), this minimizes travel time and is computationally trivial. Auction-based and market-based approaches have robots bid on tasks based on state (battery, distance, queue depth), optimizing for fleet-wide efficiency at the cost of communication overhead [2.6.n]. These are deployed in warehouse AGV fleets — Amazon Kiva, Cainiao — where trip distances of 50–200m make route optimization worthwhile. Battery-aware filtering excludes robots below a charge threshold from the candidate pool.

Existing fleet management frameworks include ROS2 OpenRMF, a warehouse-scale scheduler, and manufacturer portals such as Bear Universe, PuduCloud, and Keenon Cloud — each proprietary and locked to its vendor's hardware. Neither category integrates with an external AI agent that triggers tasks based on live restaurant events: a guest is seated → dispatch a go-to-table task; an order is marked ready → dispatch a delivery task; a session ends → return robot to dock.

The gap is lightweight multi-robot coordination for restaurant scale (6 tables, 3–5 robots) where the task source is an AI agent responding to business events, not a pre-computed schedule.

#### 2.6.2 Dynamic Robot-Table Voice Binding

Robots are table-agnostic: any robot can serve any table. When a customer presses "Talk to AI" on the tablet at table 3, the system must route the microphone activation command to whichever robot is physically at table 3. This binding must be dynamic — established when the robot arrives at the table and released when it departs.

Prior approaches include static binding (each robot permanently assigned to one table — inflexible, wastes idle robots), broadcast-to-all (all robots in range hear the command — privacy concern), and dynamic binding (established on physical arrival, released on departure — the standard pattern, but not demonstrated for restaurant voice scenarios with per-table microphone and speaker routing).

The gap is dynamic table-to-robot-to-microphone binding where the binding is established on physical arrival at the table and released on departure, routing voice capture commands and voice reply playback to the correct robot's speaker — and surviving disconnection, where a new robot must rebind without the customer noticing.

#### 2.6.3 Telemetry, Liveness, and Fault Recovery

Robot telemetry (pose, battery, status) arrives at 4+ Hz per robot. Writing each heartbeat to a database creates write contention with order and payment transactions. Prior work on edge robotics telemetry establishes two patterns: RAM-only latest-value stores for high-frequency updates, where losing a single tick is harmless, and periodic database snapshots (every 15s) for cold-start recovery after server restart [2.6.n].

Liveness monitoring uses a heartbeat watchdog: a process that maintains an open socket but produces no heartbeats is a zombie. The watchdog detects silence beyond a timeout (typically 30s), marks the robot offline, and triggers recovery — requeue its tasks, close its WebSocket, and release its voice binding. Fault-tolerant task reassignment is a standard pattern in multi-robot systems [2.6.n].

These patterns are known individually. The gap is their composition into a single lightweight dispatcher that simultaneously handles task assignment, voice binding, and fault recovery — all driven by restaurant business events rather than warehouse logistics.

#### 2.6.4 Real-Time Restaurant State Synchronization

Restaurant management software has evolved from standalone POS terminals to kitchen display systems (KDS) to QR-code ordering applications. Each generation serves one role and operates independently: a kitchen display learns about a new order on its next poll cycle (typically every 5–10 seconds). The customer ordering app does not know the kitchen's queue depth. The robot does not know the customer just paid. There is no shared real-time state across roles.

WebSocket push replaces polling by delivering events as they occur. Role-based pub/sub routes events to the correct client subset: kitchen panel receives `order.created`; robot receives `task.assign`; customer tablet receives `voice.reply`. REST APIs and multi-role SPA architectures are individually mature technologies, and restaurant management platforms (Toast, Square, Lightspeed) implement real-time state propagation internally but do not expose it as a public API for an external AI agent to drive.

The gap is a lightweight, self-contained system where: (a) an AI agent creates orders, updates cart state, and dispatches robots; (b) all client roles see these changes in real time via WebSocket push; (c) session lifecycle is enforced as guarded state transitions (check-in → order → pay → release); and (d) the entire system runs on a single server with no cloud dependency. This integration gap motivates the backend orchestrator architecture in §4.7.

---

### 2.7 Multi-Role Web Interfaces

> *Restaurant automation requires distinct user interfaces for each operational role — customer ordering, kitchen order management, guest check-in, and fleet monitoring — all sharing a single source of real-time truth driven by AI agent events. This section surveys single-page application frameworks, component libraries, build tools, and real-time communication patterns. The technologies are individually mature; the gap is their composition into a documented multi-role architecture where the AI agent is the primary driver of UI state.*

#### 2.7.1 Single-Page Application Frameworks

The single-page application (SPA) model — a single HTML page with client-side routing where reactive component trees update in-place as data changes — is the standard pattern for real-time dashboards, interactive ordering systems, and operational panels. Three frameworks dominate the SPA ecosystem.

Vue 3 with Composition API and TypeScript provides reactive data binding via `ref()` and `reactive()`, Pinia for cross-component state management, Vue Router for client-side navigation, and first-class TypeScript support. Its runtime is approximately 33 KB gzipped. Vietnamese character rendering works through Unicode standard support with no additional configuration. The ecosystem includes Vite for builds, PrimeVue for components, and Tabler Icons.

React with hooks and JSX is the dominant SPA framework by market share, using virtual DOM reconciliation. State management options include Context API, Redux, or Zustand. The larger ecosystem (Next.js, Material UI, Ant Design) and the complexity of reactive state patterns (useEffect dependencies, stale closures) give React a steeper learning curve than Vue for complex multi-form interfaces.

Angular with TypeScript and RxJS is an opinionated full framework with dependency injection and module-based architecture. It is strongly typed and well-suited to enterprise teams, but its heavier runtime, steep learning curve, and verbose boilerplate for simple components make it disproportionate for restaurant interfaces where business logic resides on the backend server.

All three frameworks have been used for restaurant ordering, dashboard, and monitoring interfaces. No academic survey has compared them specifically for the multi-role, AI-driven restaurant context where the selected framework must support multiple role-specific SPAs sharing a common TypeScript client library, real-time UI updates from WebSocket events originating from an AI agent, and reactive Vietnamese text rendering for conversation transcripts, dish names, and order summaries.

#### 2.7.2 Component Libraries and Build Tools

PrimeVue 4 is a Vue 3-native component library with full TypeScript support. Its data-intensive components — DataTable with sorting, filtering, and pagination; Form components with validation; Card and Panel containers; Dialog and Overlay panels; Toast notifications; Badge indicators — map directly to restaurant UI needs: menu browsing via DataTable, order forms via Form and InputNumber, kitchen Kanban via Card layout, status badges for order states, and payment dialogs.

Vuetify 3 (Material Design) is an opinionated component library strong for admin dashboards but constrained by Material Design's rigid grid system and elevation-based layering, which limit responsive, touch-friendly menu browsing. It also carries a heavier bundle weight than PrimeVue. Ant Design Vue is an enterprise-grade library with comprehensive form and table components, well-suited to data management interfaces (kitchen panel, fleet dashboard) but with a visual style optimized for enterprise back-office rather than customer-facing restaurant interfaces.

Vite 8 is a next-generation build tool with a native ES module dev server providing hot module replacement in under 50ms. Production builds use Rollup with tree-shaking. It is significantly faster than Webpack-based toolchains — relevant for a 3-app monorepo where each SPA must be built and served independently during development. Webpack via Vue CLI, the traditional toolchain, is slower on dev server startup and HMR on large projects.

Component library comparisons exist for general web development, but no evaluation covers restaurant-specific UIs requiring Vietnamese diacritic rendering accuracy, touch-friendly tablet interfaces with large tap targets, and real-time data binding to WebSocket events from a backend orchestrator.

#### 2.7.3 Real-Time Communication Patterns

Polling — the client sends an HTTP GET every N seconds — is the traditional pattern in restaurant POS and KDS systems. A new order appears on the kitchen display 0–10 seconds late, averaged across poll cycles. This is acceptable for a standalone KDS but unacceptable for voice-driven interaction where the agent's response and cart update must appear immediately.

WebSocket push delivers events as they occur over a persistent full-duplex connection. Role-based pub/sub routes events to the correct client subset: the kitchen panel receives `order.created`, the robot receives `task.assign`, the customer tablet receives `voice.reply`. Auto-reconnection with exponential backoff handles WiFi instability.

Server-Sent Events (SSE) provide server-to-client streaming over HTTP, lighter weight than WebSocket for unidirectional traffic. SSE is used to stream LLM-generated responses sentence-by-sentence to the voice pipeline and tablet. SSE is not suitable for bidirectional communication such as robot telemetry or tablet commands.

Restaurant management platforms (Toast, Square, Lightspeed) implement real-time state propagation internally but do not expose documented WebSocket event catalogs for external AI agents. Academic work on real-time multi-role web systems exists for hospital monitoring, logistics control panels, and financial trading UIs, but not for restaurant operations where the event source is an AI agent.

#### 2.7.4 Multi-Role SPA Architecture

The multi-role SPA pattern deploys multiple single-role applications — each serving one user type with role-specific UI and event subscriptions — sharing a common TypeScript client library for API calls, WebSocket connections, and type definitions. This is the standard pattern when different user roles need different views of the same underlying data.

Multi-role SPA architectures have been documented for enterprise SaaS platforms with admin, customer, and agent dashboards. No prior restaurant system implements this architecture where the shared state is driven by an AI agent: the agent creates orders (triggering kitchen panel updates), modifies cart state (triggering tablet updates), and dispatches robots (triggering fleet dashboard updates), with all roles seeing the changes in real time.

The gap for §2.7 is a documented architecture and framework selection for a multi-role, AI-driven restaurant system combining Vue 3-based SPAs with a shared TypeScript client library mirroring backend schemas, PrimeVue component selection justified by restaurant-specific UI requirements, Vite-based build tooling for a multi-app monorepo, role-based WebSocket pub/sub for real-time state synchronization, and SSE streaming for AI agent response delivery. The technologies are individually mature; their composition and the criteria justifying their selection have not been documented. This gap motivates the web interface architecture in §4.8.

---

### 2.8 Edge Computing Platform — [MIXED]

> *The robot's computational platform is a purchased component — no custom hardware was developed and no comparative procurement study preceded the purchase. This section is therefore written as a **constraint-satisfaction check performed after the fact**: it derives the computational requirements the workload imposes, examines which classes of embedded accelerator satisfy them, describes the NVIDIA Jetson Orin Nano and its software stack, and surveys prior deployment in academic robotics. The platform's resource constraints motivate the architectural decisions in Chapter 4.*
>
> **Framing note (revised 23-Jul-2026).** Earlier drafts recorded "no gap claimed here — hardware is off-the-shelf," and the draft written from it opened by declining to compare alternatives. That conflicted with the chapter's [USE] classification. The first revision made §2.8 a full [USE] section but introduced **two faults**: (a) it defined requirements `R-E1–R-E4` inside Chapter 2, creating a fourth requirement namespace alongside §3.1 R1–R7, §4.1 R1–R6/NFR1–5, and §4.2 C5–C10 — and requirements belong to §4.1, not the survey chapter; (b) it derived those requirements from "the LLM does not run on this board (§4.4.1)" while §4.4.1 justifies that placement by §2.8's memory ceiling — **a circular dependency**.
>
> Both are fixed by making §2.8 **[MIXED]** and putting *placement* before *hardware*. §2.8.2 now establishes the vehicle/infrastructure split on grounds independent of the board (cloud-robotics + offloading literature); §2.8.3 onward then asks what board hosts the resulting onboard workload. Dependency is one-way. §2.8.1 describes *workload characteristics*, never numbered requirements, and says so explicitly.
>
> **Never imply boards were evaluated in advance**, and **never let the memory ceiling be the sole justification for the split** — that framing reduces the architecture to a budget artifact and invites "so a 16 GB board would have changed your design?"

#### 2.8.1 The Workload Aboard a Service Robot

- Descriptive, not normative. Two workload families: perception/motion from §2.2 (RGB-D graph SLAM, Nav2 costmaps, EKF, ArUco — CPU-bound, concurrent, hard-real-time in practice); speech from §2.3 (VAD, Whisper-family recogniser, TTS). The third family — the LLM — is deferred to §2.8.2 as an open placement question, **not** asserted absent.
- Why *medium* and not smaller: WER degradation below medium falls disproportionately on tonal diacritics (§2.3). The model size is what makes the platform argument load-bearing — state it, it is the point of attack.
- Four workload characteristics, **unnumbered and unlabelled** (no R-E namespace): general-purpose accelerator not fixed-function; memory bandwidth for autoregressive decode; native fp16 without mandatory quantisation; vendor-supported ROS2 on the host architecture. Plus battery/chassis constraints.
- Closes by stating explicitly that these are workload characteristics, that requirements live in §4.1, and that the selection is made in §4.9.

#### 2.8.2 Placement of Computation: Onboard, Offboard, and the Split — [BUILD]

- **The missing Ch2 section.** Before this revision, Chapter 2 had *no* coverage of computation offloading, cloud robotics, or thin-edge architectures — so the edge/server split, a Ch4 contribution, had no related work to stand on and was supported only by the 8 GB ceiling.
- Field: **cloud robotics** [Kehoe et al. survey; RoboEarth] + **mobile edge computing / computation offloading** [Mach & Becvar].
- Three positions surveyed with strength+limitation each: fully onboard (no network dependence; capability permanently bounded by the vehicle, upgrades replicated per vehicle); fully offboard (max capability, min vehicle cost; connectivity failure *stops* rather than degrades — a safety matter when motion control is across the link); split (what the literature recommends).
- Literature's offload criteria are **latency, energy, bandwidth** — resource optimisation.
- Three further considerations it treats only incidentally, **all independent of vehicle compute capacity**: (i) **data residence** — a service robot is physically exposed and unattended in a public space; business data resident on it shares that exposure; (ii) **fleet consistency** — replicated state diverges, a menu updated on 3 of 4 robots is a pricing error (§2.6); (iii) **update surface** — one server vs. N vehicles.
- **Keep (i) qualitative and understated — deliberate.** No formal threat model, no attack enumeration. Stated as a design consideration; `references.md` [2.8.22] records that this weight is intentional. Verified in code: `log_turn` is called only from `agent_brain/server.py` (server-side), edge logging is stdout-only with no FileHandler, robot needs little beyond `ORCH_AGENT_URL` — so "the vehicle holds no authoritative state" is checkable, not aspirational.
- **→ Gap.** Both literatures frame placement as resource optimisation. Neither characterises a split drawn on *functional* grounds — a boundary placed so the vehicle holds no authoritative state or business data at all, keeping only undelegatable perception/motion plus transcription that must survive an outage. Answered in §4.4.1.

#### 2.8.3 Accelerator Classes: GPU, NPU, and the TOPS Metric

- **This is the examiner-facing subsection.** It answers the standard objection: "an NPU board gives more TOPS per dollar — why a Jetson?"
- TOPS measures dense INT8 convolution throughput (high arithmetic intensity). Autoregressive Transformer decoding has arithmetic intensity ≈ 1 → **memory-bandwidth-bound, not compute-bound** [roofline; Pope et al.]. Bandwidth predicts decode latency; TOPS does not.
- Operator set: embedded NPUs target statically shaped INT8 CNNs. Decoding needs dynamic sequence length, growing KV cache, beam search. Encoder-decoder ASR under beam search is unsupported in production NPU toolchains; community ports run encoder on NPU and fall back to CPU for the decoder — the part that dominates latency.
- Precision: most fixed-function accelerators are INT8-only with no fp16 fallback → quantisation is mandatory, not optional. Risk concentrated on tonal diacritics; **state as a risk requiring empirical characterisation, not as an established result** (no source located).
- Toolchain tax: vendor graph compiler, per-op support matrix, calibration. A GPU runs the unmodified upstream runtime; an NPU requires a port that must be re-entered on every model change.
- Conclusion: the required property is *not* throughput. It is general-purpose programmability + bandwidth + native fp16 — exactly the three properties the best TOPS-per-dollar classes lack.

#### 2.8.4 Jetson Orin Nano — Hardware & Software Stack

- Hardware: 1024-core Ampere GPU + 32 Tensor Cores, 6 ARM cores, 8 GB unified memory, 7-15W. Unified memory = CPU/GPU share one pool; exceeding 8 GB triggers OOM killer — failure is abrupt, not gradual, and on a robot the large allocations belong to perception and motion.
- Software stack: JetPack SDK = L4T (Ubuntu 22.04 ARM64) + CUDA + cuDNN + TensorRT. ROS2 Humble installs natively from vendor binaries.
- **TensorRT is available but unused — say so deliberately.** The recogniser runs on CTranslate2, which performs its own fusion/quantisation and addresses CUDA directly. Justification: tuned kernels already exist for this architecture, and TensorRT's larger payoff on this board class accrues to LLM inference, which does not happen here. Note as future work (§6.3), do not claim as an optimization performed.

#### 2.8.5 Platform Comparison

- **Table 2.8a** — candidate platform *classes* against the §2.8.1 workload characteristics: Raspberry Pi 5; Pi 5 + discrete NN accelerator; RK3588 SBC; Intel N100 mini-PC; **Jetson Orin Nano**; Jetson Orin NX; Jetson AGX Orin. Columns: accelerator, memory bandwidth, half precision, ASR runtime path, ROS2 support, power, indicative cost.
- **Table 2.8b** — Jetson family positioning (retained from the earlier draft).
- Three observations: (i) no-GPU boards cannot host the recogniser at all — a statement about the workload, not their capability; (ii) **the N100 mini-PC is the closest competitor and is conceded, not dismissed** — mature INT8 CPU kernels make it viable for a voice-only edge node, weaker for one that must also perceive; the margin is empirical and this chapter does not settle it; (iii) boards ≥16 GB could host the LLM locally — be precise about what that would change: it removes the *memory* argument only, and leaves §2.8.2's three capacity-independent considerations untouched. **Do not write that a larger board would have reversed the design.** The claim is that the ceiling and the design agree — weaker than the ceiling causing the design, and much more robust.
- Cost at scale: a fleet amortises one server across many robots → per-robot BOM governs, so the smallest sufficient board is correct at scale, not a prototype compromise. The follow-up ("why keep STT on the robot at all?") is answered in §4.4.1 on network-dependence / audio-bandwidth / locality grounds, not cost.
- **All quantitative cells are `*Unverified*` pending vendor datasheets.** Prices are indicative single-unit USD, volatile, undated. See `references.md` §2.8.

#### 2.8.6 Sensor Interfaces

- RPLiDAR A2M8 (USB 2.0, 8 Hz scans), RealSense D435 (USB 3.0, 30 Hz RGB-D), MPU6050 IMU (I²C → STM32 → UART → Jetson), USB mic (16 kHz mono), Bluetooth speaker, 7" LCD (HDMI + USB touch). Device specifics belong to §3.3; §2.8.5 records the aggregate only (Table 2.8c).
- Depth camera dominates — the sole reason USB 3.0 is a requirement. Beyond bandwidth the aggregate raises a *scheduling* question, not a capacity one.

#### 2.8.7 Prior Work on Jetson in Robotics

- Extensively used for ROS2 SLAM, Nav2, sensor fusion; speech workloads separately documented. Suitability for either category alone is not in question.
- The gap is the *combination*: published work measures each subsystem in isolation, leaving the concurrent resident footprint on a unified-memory board uncharacterised. The edge resource budget is acknowledged as unevaluated in §5.6.4.

---

### 2.9 Summary: Needs → Requirements Traceability

- **The six needs, plus the edge platform, and what they demand of the proposed system:**

  | §   | Need | → Requirements | → Method | → Validated In |
  | --- | ---- | -------------- | -------- | -------------- |
  | 2.2 | Dynamic goal navigation — navigation targets assigned by AI agent, not pre-set, with ArUco business-context docking | §3.1 R1–R7 (navigation, docking, odometry) | §3.4–§3.7 (EKF, RTAB-Map, ArUco, Nav2 + dynamic goal coupling) | §5.3.1–§5.3.3 |
  | 2.3 | Vietnamese voice on Jetson edge — component selection (VAD, STT, TTS) driven by restaurant deployment constraints | §4.1 NFR latency, §4.4 architecture | §4.4 (selected components: Silero VAD, PhoWhisper, Piper TTS; threaded pipeline, barge-in) | *(voice pipeline unevaluated; see §5.6.4)* |
  | 2.4 | Conversational AI agent — classifier handling teencode/context/multi-intent/domain-vocab + deterministic post-generation validation | §4.1 functional requirements, §4.5.1–§4.5.6 (agent architecture) | §4.5.2 (MLP classifier with embedding from §2.5.2), §4.5.3 (tool-calling LLM — Qwen2.5 14B, surveyed §2.4.2), §4.5.4 (validator) | §5.4.1–§5.4.3 |
  | 2.5 | Menu knowledge retrieval — closed-loop rewrite→retrieve→rephrase for Vietnamese food domain, driven by Vietnamese-specific embeddings (§2.5.2) | §4.1 menu search requirement, §4.6 | §4.6 (query rewriting, hybrid retrieval with embeddings from §2.5.2, result rephrasing, dedup) | §5.4.4 |
  | 2.6 | AI-driven restaurant operations — lightweight fleet dispatch with voice binding, multi-role real-time sync, session lifecycle | §4.1 concurrency/multi-role requirement, §4.7 | §4.7 (REST + WS hub, fleet dispatcher, session lifecycle) | §5.5 |
  | 2.7 | Multi-role web interfaces — AI-driven Vue SPA architecture with shared TS client, role-based WS pub/sub, SSE streaming | §4.1 multi-role UI requirement, §4.8 | §4.8 (3 SPAs + shared client lib + WS event catalog) | §5.5 |
  | 2.8 | Edge computing platform — accelerator class satisfying general-purpose programmability, decode bandwidth, and native fp16; 8 GB unified-memory ceiling determining the edge/server split | §3.3 (robot hardware), §4.4.1 (edge/server split) | §4.4.1 (memory budget analysis leading to edge/server architecture) | *(edge resource budget unevaluated; see §5.6.4)* |

- **The integration gap:** each need has been addressed individually in prior work — autonomous navigation (ROS2 delivery robots), Vietnamese speech (standalone STT/TTS/VAD), edge computing (Jetson deployments), conversational agents (cloud chatbots), intent classification (NLU pipelines), menu retrieval (academic RAG), fleet management (warehouse frameworks), restaurant software (POS/KDS), and SPA web interfaces (Vue/React dashboards). No prior system has integrated all into a single deployed system where the AI agent directly drives physical delivery and real-time UI state across all roles.

---

## CHAPTER 3: PROPOSED METHOD (I) — ROBOT CONTROL AND NAVIGATION

> **Chapter requirements — this chapter answers:**
> - What is the complete system, and how do the two proposed-method chapters divide the work? (3.1 System Overview — shared with Chapter 4)
> - What must the navigation system achieve? (3.2 Requirements — derived from Ch.2 Need 1 gap)
> - What challenges make this hard? (3.3 Design Challenges C1–C4)
> - What hardware are we working with? (3.4 Platform & Hardware)
> - Per challenge: what method did we design or apply, and how does it address the challenge? (3.5–3.8)
> - For off-the-shelf components used in navigation (RTAB-Map, Nav2, robot_localization EKF, ArUco): they were surveyed in Ch.2; this chapter describes how they are configured, integrated, and adapted for the restaurant domain.
> - For components we designed (dynamic goal coupling, business-context ArUco docking): this chapter presents the design and its rationale.

> *This chapter opens with a whole-system overview shared with Chapter 4 (§3.1), then addresses Need 1 (dynamic goal navigation, §2.2) following the structure: navigation requirements derived from the gap (§3.2) → design challenges that make these requirements difficult (§3.3) → proposed method: how the system solves each challenge (§3.4–§3.8).*

### 3.1 System Overview

> **Status:** to draft
> **Scope note:** The single whole-system map, shared by both proposed-method chapters. It is placed here, at the start of the first proposed-method chapter, so the reader holds the complete architecture before either half is detailed. The detailed *software* architecture (agent-brain internals, orchestrator, data flows) is deferred to §4.3, which zooms into the server tier of the diagram introduced here.
> **Figures needed:** Fig 3.1 (whole-system three-tier block diagram — simplified)

- **The three tiers.** The system is one distributed application spanning three physical tiers on a local WiFi network:
  - **Tier 1 — Central Server (the brain):** x86 PC with an NVIDIA GPU. Runs the conversational agent (LangGraph + Ollama LLM), the backend orchestrator (FastAPI REST + WebSocket hub + fleet dispatcher), the hybrid RAG retriever, and the business + conversation databases. Detailed in Chapter 4.
  - **Tier 2 — Robot (the body):** Jetson Orin Nano carrying microphone, speaker, LiDAR, camera, and motors. Runs the voice I/O pipeline and ROS2 navigation. Navigation is detailed in this chapter (§3.5–§3.8); the voice pipeline in Chapter 4 (§4.4).
  - **Tier 3 — Staff Devices (the interfaces):** browser SPAs — customer tablet, entrance kiosk, kitchen/manager panel. Detailed in Chapter 4 (§4.8).
- **The defining split — perception on the edge, intelligence on the server.** The robot senses and acts; the server reasons and remembers. Heavy data (audio, LiDAR scans, camera frames) is processed on the edge and reduced to lightweight structured messages (text transcripts, pose coordinates, navigation goals) before crossing the network; the LLM never runs on the robot. The split follows the Jetson's shared-memory ceiling (analyzed in §2.8) and is reinforced by keeping business data off a physically exposed robot. It is developed as a design decision — not only a hardware constraint — in §4.3.1.
- **How the two proposed-method chapters divide the system.** Chapter 3 covers the Tier-2 navigation stack — odometry/EKF, RTAB-Map mapping, ArUco docking, and Nav2 with dynamic goal assignment (the robot half). Chapter 4 covers the Tier-1 intelligence, the Tier-3 interfaces, and the Tier-2 voice pipeline — the agent brain, RAG, orchestrator, and web apps (the AI/backend/web half). The two halves meet at one seam: the orchestrator's fleet dispatcher assigns Nav2 goals from business events (§4.7.4 → §3.8), and the robot reports arrival back to bind the table's voice channel (§3.7 → §4.7.5).
- **Figure:** whole-system three-tier block diagram — Server / Robot / Staff Devices, one-line responsibilities per tier and the network seam. A simplified view of the detailed component map in §4.3.3.

---

### 3.2 System Requirements

- R1–R7 with target metrics (navigation success, docking precision, odometry accuracy, safe obstacle distance)
- Each requirement traceable to a specific gap in §2.2
- Domain constraint: dedicated service lane, physically separated from customers

### 3.3 Design Challenges

- **C1 — Consumer-grade IMU drift:** MPU6050 gyro bias accumulates angular error. Over a 10m round trip with multiple in-place rotations, uncorrected yaw drift may exceed ArUco marker field-of-view at the docking zone.
- **C2 — TWD non-holonomic constraints:** no lateral motion. Every position correction requires a rotation + translation sequence. In narrow service lanes (80–100 cm width), the robot's turning radius must be respected or the robot will collide with lane boundaries during in-place rotation.
- **C3 — SLAM-to-navigation infrastructure gap:** RTAB-Map produces an occupancy grid for localization. The backend dispatcher must query navigation waypoints by table ID — RTAB-Map does not expose table semantics; it exposes poses. A bridging layer must map table IDs to waypoint poses.
- **C4 — Dynamic goal coupling:** Nav2 accepts a single goal pose. The backend must be able to send a new goal at any time — when an order is ready, when the robot finishes a delivery and needs a new destination, when the session ends and the robot returns home.

### 3.4 Robot Platform & Hardware Setup

- **Purchased TWD platform:** chassis, two MC520P30 DC motors with encoders, STM32 microcontroller, MPU6050 IMU
- **Added components:** RPLiDAR A2M8 (360° 2D laser scanner), Intel RealSense D435 (RGB-D camera), Jetson Orin Nano (edge compute), 7" LCD touchscreen, battery pack
- **Boundary:** contribution starts from ROS2 integration upward
- **Component specifications table:** LiDAR range/angular resolution, D435 depth accuracy/FOV, MPU6050 gyro/accel specs, encoder resolution (P=1024 pulses/rev, G=30 gear ratio → N = P·4·G = 122880 ticks/rev), motor rated speed/torque
- **ROS2 robot model:** URDF with base_link, base_footprint, lidar_link, camera_link, wheel joints → render figure
- **TF tree:** `map → odom → base_footprint → base_link → (lidar_link, camera_link, imu_link)`
- **Platform constants:** wheel diameter D, wheel separation W, encoder ticks per revolution N, control loop rate 50 Hz, Vx_max, Vω_max
- **Connection/wiring block diagram:** Jetson ↔ STM32 (UART), Jetson ↔ LiDAR (USB), Jetson ↔ D435 (USB 3.0), Jetson ↔ LCD (HDMI+USB touch)
- **Photos of physical robot and service-lane/marker layout**

### 3.5 Wheel Odometry and EKF Sensor Fusion

- **How it addresses C1 (IMU drift):**
  - Wheel odometry: encoder tick model (`N = P·4·G`), velocity computation (`V = πD/N · Δn/Δt`), forward kinematics (`V_x = (V_A+V_B)/2`, `V_ω = (V_B−V_A)/W`), Euler pose integration
  - IMU (MPU6050): raw int16 → SI conversion, axis remap, gyro bias estimation, Mahony AHRS for relative yaw
  - EKF (`robot_localization`, `two_d_mode`): state `[x, y, ψ, V_x, V_y, V_ω]`, odom0 → V_x/V_y/V_ω, imu0 → V_ω only (no magnetometer → IMU yaw not fused), covariance tuning, output `/odometry/filtered` + `odom→base_footprint` TF
  - EKF fuses complementary sensor strengths: encoders provide short-term accuracy (no drift over 1–2m), IMU provides angular rate for sharp turns where encoder slippage is worst
  - **Figure:** EKF predict-update cycle diagram

### 3.6 Map Building with RTAB-Map

- **How it addresses C3 (SLAM-to-navigation gap):**
  - RTAB-Map pipeline: LiDAR (geometry) + RGB-D camera (loop closure) → 2D occupancy grid
  - Offline mapping run: teleop the service lane + return pass to force loop closure
  - Waypoint layer: after mapping, each table's docking pose is manually annotated in a configuration file keyed by table_id → {x, y, yaw}. The backend reads this config to resolve "go to table 3" → Nav2 goal pose
  - Tuned parameter table (grid resolution, max LiDAR range, loop-closure/proximity settings)
  - LiDAR-only mapping option; camera used for loop closure only (not 3D mapping)

### 3.7 Localization and ArUco-Based Docking

- **How it addresses C2 (non-holonomic TWD) and completes C1 (drift correction):**
  - RTAB-Map localization mode on saved map → publishes `map→odom`
  - Initial pose from home (kitchen) ArUco marker → absolute start pose, removes manual "2D Pose Estimate"
  - Per-table ArUco re-localization: at ~1m from the table, the D435 detects the table's ArUco marker → PnP computes 6-DoF camera-to-marker transform → pose corrected → final approach with sub-centimeter precision
  - Marker-lost → safe stop at predefined distance
  - Each marker is configured with table_id → backend verifies: "robot is at table B3, order #O128 belongs to session S42 at table B3" — business-context docking
  - **Figure:** ArUco marker pose estimation with annotated coordinate axes

### 3.8 Autonomous Navigation with Nav2 & Dynamic Goal Assignment

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

> **Chapter requirements — this chapter answers:**
> - What must the software system achieve? (4.1 Requirements — derived from Ch.2 Needs 2–6)
> - What challenges make this hard? (4.2 Design Challenges C5–C10)
> - What is the overall architecture, and why these design decisions? (4.3)
> - For each subsystem: based on the Ch.2 survey, what did we SELECT (off-the-shelf) or DESIGN (new)?
>   - If selected from a Ch.2 comparison table: state what was selected and the selection rationale against our requirements.
>   - If designed new: reference the Ch.2 research gap, present the proposed method, explain how it addresses its challenge.
> - How do all subsystems fit together in deployment? (4.9)

> *This chapter addresses Needs 2–6 (§2.3–§2.7). It follows the structure: system requirements derived from the gaps (§4.1) → design challenges (§4.2) → overall architecture and design rationale (§4.3) → per-component method: how each subsystem solves its challenges (§4.4–§4.8).*

### 4.1 AI System Requirements

> *Requirements only. A short paragraph bridging Ch.1 objectives and Ch.3 deliverables, then a compact list of what the AI, backend, and web system must provide — no subsections, no Ch.2 gap references, no explanations. The Ch.2 traceability lives in the design chapters; this section states only the requirements.*

### 4.2 Design Challenges

> *Six challenges that make the §4.1 requirements difficult to meet simultaneously. Each is stated as the problem — no solutions here. No C5/C6/etc. labels. One compact paragraph per challenge, tracing to the §4.1 requirements and pointing forward to the proposed-method sections that resolve them.*

- Informal Vietnamese is hard to classify reliably: teencode, context-dependent short affirmations, multi-intent turns, and rare dish names break four different classifier families in four different ways. The system must be accurate, fast, and deterministic — properties prior approaches trade against each other.

- The Jetson's 8 GB of shared memory is consumed by navigation, sensors, and the voice pipeline, leaving too little for a capable language model. The LLM must run on the server, and the work must be divided between robot and server without adding unacceptable network latency.

- The language model is a probabilistic component in a system that must behave deterministically. It can invent dish names, produce impossible quantities, or attempt invalid state transitions. Such errors cannot be prevented without fine-tuning — they must be detected and blocked before reaching the cart or backend, on every call and with no human review.

- The way customers describe food does not match how the menu is stored. Customers ask by taste, sensation, or occasion; the menu is organised by name, category, and price. Standard RAG fails when query and document share no vocabulary. Retrieval must bridge this gap, before and after the search.

- The backend is a shared state machine driven by the AI rather than by staff. Several client roles need different live views of agent-driven events. Polling is too slow; a cloud dependency fails when WiFi drops. The entire backend must run on one machine and push changes as they happen.

- The bond between a robot and the table it serves must survive disconnection. When a robot reaches a table, that table's voice commands are routed to that robot. If the robot disconnects mid-session, the system must release the binding, hand the task to another robot, and rebind the new one — without the customer noticing which robot is speaking.

### 4.3 Software System Architecture

[Figure 4.1. System Architecture Overview: three-tier deployment block diagram]

This section gives the whole-system view before any single part is opened: what pieces exist, where each one runs, and how a spoken order travels through them. It is the map the rest of the chapter fills in one piece at a time.

Opening: a plain lead-in paragraph (the restaurant service loop, and why the overview comes first), then a concrete high-level picture of the topology: two machines (Jetson + server), three staff-facing browser apps, two server processes (agent + orchestrator), and the data-flow principle, anchored visually on Figure 4.1. Written in plain, concrete language with no cross-section citations; parts are named directly rather than pointed at by section number.

#### 4.3.1 Topology and Responsibilities

Goal of this subsection: make the hybrid split clear, meaning why navigation and perception run on the robot and why the language model, the reasoning, and the business state run on the server. Plain, concrete language, no cross-section citations. Built around one organising principle and two tables, anchored on Figure 4.1. (No protocol detail here; that is 4.3.2.)

- The organising principle: the work divides into two kinds. Work bound to the robot's body and its senses must run on the robot. Work bound to thought and to shared state belongs on the server. State this principle first, then let the table show it.
  - On the robot: reading the sensors (LiDAR, depth camera, IMU), fusing them into a pose (EKF), localizing on the map (RTAB-Map), planning and following paths while avoiding obstacles (Nav2), and capturing and playing sound at the microphone and speaker (VAD, STT, TTS). Two constraints force these onto the robot, and neither is memory: they are wired to hardware that is physically on the robot, and they close real-time control loops that a WiFi round trip would break. Their raw data (scans, camera frames, audio) is also large and is best reduced to small results locally.
  - On the server: the language model, the agent that reasons over the request, the business records (tables, sessions, orders, payments), and the menu knowledge and search. None of these is tied to one robot's body; all are common to every table and every robot, so they live once, in one central place.

[Table 4.1. Where each job runs, and the constraint that fixes its place. This table is the hybrid architecture at a glance; it replaces the old flat "what each machine runs" list.]

| Job | Runs on | Constraint that fixes its place |
|-----|---------|---------------------------------|
| Motor control, wheel odometry (EKF) | Robot | Wired to the motors; needs real-time timing beside the actuators |
| Sensing and localization (LiDAR, depth camera, IMU, RTAB-Map) | Robot | Sensors are on the robot; raw scans are large and reduced locally |
| Navigation (Nav2 path planning and obstacle avoidance) | Robot | Closes a real-time control loop with the sensors and motors |
| Voice capture and playback (VAD, STT, TTS) | Robot | Microphone and speaker are on the robot; keeps audio off the network |
| Language model and conversational agent | Server | Too large for the robot's memory; tied to no robot's body |
| Business records (tables, sessions, orders, payments) | Server | Shared state; one source of truth for all tables and robots |
| Menu knowledge and search | Server | Shared, updated centrally, used by every robot |

- The one job that could go either way is the language model, because it is wired to no sensor. So why not put it on the robot too and drop the network hop entirely? What rules it out is memory, and the robot does not start empty. Show the Chapter 3 navigation/localization stack (Table 4.2), which already holds part of the 8 GB. IMPORTANT: do NOT name the specific model (Qwen2.5 14B, Q6_K); the overview stays generic, the model is introduced in §4.5. Perception is NOT detailed here (its budget belongs in §4.4); Table 4.2 lists ONLY the Chapter 3 ROS components.

[Table 4.2. Memory the robot's navigation and localization already use (the Chapter 3 stack). ROS components only; perception excluded; numbers are the team's measured/estimated values, confirmed 2026-07-25.]

| ROS component | Approx. memory |
|---------------|---------------:|
| ROS 2 core and DDS middleware | ~0.2 GB |
| Sensor drivers (LiDAR, depth camera, IMU) | ~0.5 GB |
| Localization on the prebuilt map (RTAB-Map) | ~2.0 GB |
| Navigation (Nav2 planners, costmaps, behaviour trees) | ~0.7 GB |
| Odometry fusion (EKF) and ArUco docking | ~0.3 GB |
| **Used by the Chapter 3 stack** | **~3.7 GB** |
| **Free of the 8 GB** | **~4.3 GB** |

Prose after the table: about 4 GB is free, and it is into this 4 GB (not the whole board) that this chapter's work must fit. The voice pipeline takes a further share (perception runs on the robot; its own budget is detailed in §4.4). Even setting perception aside, a capable LLM needs more than the 4 GB that remain; a model squeezed under that limit is small and heavily compressed and loses accuracy; and the 4 GB is really the peak headroom the nav stack needs, so a model claiming it would starve work that must never stall. Hence the LLM runs on the server. Note: Figure 4.1's SVG still labels the model box "Qwen2.5 14B"; genericise the diagram box if the model is fully deferred to §4.5 (pending).

- The other three reasons for the split, none depending on memory:
  - Speed. Only small text and pose messages cross the WiFi, never audio or video (a transcript is about a hundred bytes; the raw audio it replaces is about a hundred kilobytes), so the split adds almost no delay.
  - Safety of data. The robot is physically exposed; every durable record lives on the server, so a damaged, stolen, or switched-off robot loses no customer data and a replacement works at once. Keep this understated: a design preference, not a formal threat model.
  - Consistency across the fleet. One model on one server serves every robot identically; behaviour does not drift from unit to unit, and an update is installed once on the server. Close with one line: the memory ceiling and these three properties agree, and a larger board would relax only the first.

- What the server runs, concretely: two processes. The agent (understand the request, decide the operation, check it against the menu and the current order, run it, write the reply; its language model is served locally by Ollama, kept resident so no request waits to load; the specific model stays unnamed here and is chosen in §4.5). The orchestrator (the web API, the live-push channel, the delivery dispatcher, and the record of tables, sessions, orders, and payments, behind two small single-file SQLite databases). Why two processes: slow reasoning, which takes seconds and blocks while it runs, must never delay the orchestrator's millisecond bookkeeping and screen updates, and either can restart without the other.

Note on table numbering: Table 4.1 = job placement, Table 4.2 = the Chapter 3 memory stack, Table 4.3 = the §4.3.2 protocol table.

#### 4.3.2 Messages Between Components

How the components communicate. The section opens with a short paragraph explaining that the system uses two primary communication patterns, request/response for CRUD operations and push for real-time events, and that two sequence diagrams illustrate how these patterns compose across components. A protocol summary table closes the section with the rationale behind each choice. Plain, concrete language; no cross-section citations in the prose.

- Why these two flows. The voice ordering sequence is the core customer interaction; it touches every component from the tablet to the robot's microphone to the agent to the speaker. The order-to-delivery sequence shows how an AI decision (confirm order) cascades through the kitchen display, the fleet dispatcher, and the robot's navigation, the path from thought to physical action. Together they cover the two halves of the system: the conversational half and the operational half.

- Voice ordering sequence. Introduce Figure 4.2, a sequence diagram with five participants (tablet, orchestrator, voice device, agent brain, Ollama). Walk through the numbered steps: (1) guest presses "Talk to AI" on tablet → POST /voice/listen, (2) orchestrator resolves table→robot binding, sends start_listening via WebSocket, (3) VAD captures utterance, STT transcribes (~800ms), (4) voice device POSTs transcript to agent /chat, (5) agent immediately mirrors voice.heard to tablet via orchestrator, the tablet shows the transcript and a "đang suy nghĩ" indicator, (6) agent runs the graph (router → worker → validator → tools), (7) agent generates response, streams sentences via SSE, (8) TTS plays sentence-by-sentence on the robot speaker, (9) agent POSTs voice.reply (text, cart state, UI action) to orchestrator, fans out to tablet via WebSocket. Conclude with three property claims annotated on the diagram: VAD+STT+TTS run locally on the Jetson (no audio crosses the network), the validator sits between LLM output and tool execution, and the tablet is a passive viewer that never controls the microphone.

- Order-to-delivery sequence. Introduce Figure 4.3, a sequence diagram with five participants (agent, orchestrator, panel, dispatcher, robot). Walk through the numbered steps: (1) agent calls confirm_order → orchestrator persists order in SQLite, (2) orchestrator emits order.created to panel WebSocket → order card appears in "Chờ Bếp" column, (3) kitchen staff advances: Chờ Bếp → Đang Làm → Xong via PATCH /orders, each push emits order.updated to panel, (4) when status reaches Xong, orchestrator creates a deliver task → dispatcher.try_assign() selects nearest idle robot with battery ≥ 20%, (5) dispatcher sends task.assign via WebSocket → robot receives Nav2 goal, (6) robot navigates to table, docks with ArUco, reports arrived → dispatcher binds table↔robot voice channel, (7) robot completes delivery, reports task_done → dispatcher frees robot, clears binding. Conclude with protocol annotations on the diagram: REST for agent→orchestrator and kitchen→orchestrator, WebSocket for orchestrator→panel push, WebSocket for orchestrator↔robot bidirectional.

- Protocol summary. End the subsection with a compact table and a closing sentence:

[Table 4.3. Protocol choices]

| Path | Protocol | Reason |
|------|----------|--------|
| Agent → Ollama | HTTP (localhost) | Native protocol, single machine, negligible latency |
| Agent → Orchestrator | HTTP (localhost) | Request/response for tool execution; fire-and-forget for voice events |
| Voice device → Agent | HTTP POST | RPC pattern, send transcript, receive reply; stateless |
| Orchestrator → Clients | WebSocket | Real-time push; polling would add 5–10s lag to critical events |
| Orchestrator ↔ Robot | WebSocket | Bidirectional: task assignment out, telemetry + status in, one persistent connection |
| Clients → Orchestrator | HTTP REST | CRUD operations map naturally to HTTP verbs and status codes |

One sentence of prose after the table: the combination of HTTP for request/response paths and WebSocket for live event paths means the system never polls, and critical events reach their destination in under 50 ms.

---

### 4.4 Edge Voice Pipeline

The microphone and speaker are on the robot, so the voice pipeline runs on the robot: capture spoken Vietnamese, transcribe it, play back the reply. This section picks the three components and shows how they are wired. SCOPE: strict outline, only 4.4.1 Component Selection + 4.4.2 Threaded Pipeline. The draft's separate TTS-strategy and latency-budget subsections are DROPPED, and the draft's "Edge/Server Split Rationale" is NOT repeated (that argument lives in 4.3.1). STYLE: plain, concrete prose; no cross-section citations; no em dashes; no file:line code refs. The LLM is not named here. The STT is written as PhoWhisper (author's decision 2026-07-25; team converting PhoWhisper to CTranslate2) — describe the real conversion step, do NOT write the false "weights loaded as checkpoints when available".

Opening: one paragraph. Two hard limits: small (must fit the ~4 GB the navigation stack leaves free) and offline. Perception total ~3.7 GB (this fulfils the perception budget 4.3 deferred here): fills nearly all the free memory, which is why no LLM can join it.

#### 4.4.1 Component Selection

FLOW (criteria-first, grounded in the Chapter 2 survey + the challenge): (1) state the yardstick before picking anything, then (2) apply it to each component in pipeline order (VAD -> STT -> TTS). This matches the Ch2-surveys / Ch4-selects contract: Chapter 2 laid out the candidate options and their properties; here we read those tables against our needs and pick.

- Placement first (fulfils the Chapter 2 §2.8 promise that §4.4.1 argues the voice-placement split). Open 4.4.1 with WHY the voice pipeline stays on the robot rather than following the LLM to the server, on the three grounds Chapter 2 §2.8 names: audio locality (mic/speaker on the robot), network dependence (must survive a WiFi drop, transcribe locally, only text waits), and aggregate audio bandwidth (raw audio fleet-wide is far more traffic than text). Defer the general split to 4.3; here only the voice-specific "why not offload it too". THEN the yardstick.

- The yardstick (state first). Three requirements, straight from the challenge, and the same axes the Chapter 2 survey compared the candidates on:
  (a) offline, no cloud, because the network can drop and the robot must still take the order;
  (b) small enough to fit the ~4 GB the navigation stack leaves free, with no graphics headroom the robot does not have;
  (c) good at Vietnamese, its six tones and diacritics.
  Selecting is then a matter of reading the Chapter 2 tables against these three needs. State each pick's memory (this is the perception budget 4.3 deferred).

- VAD: Silero VAD. "Based on the survey of voice-activity detection in Section 2.3.1 of Chapter 2, ..." Apply the yardstick to the survey's VAD options. ~2 MB, offline, CPU real-time, language-agnostic (so it handles Vietnamese with no change), single sensitivity threshold. Beats WebRTC (weaker in restaurant noise) and the GPU detectors pyannote/NeMo (need the graphics memory the robot cannot spare).

- STT: PhoWhisper medium, served through faster-whisper (CTranslate2). "Based on the survey of speech-to-text in Section 2.3.2, ..." Apply the yardstick to the survey's STT options. Vietnamese fine-tuned Whisper; offline; float16 on the robot GPU ~3.5 GB; ~800 ms/utterance; beam width 5. Deployment = one extra step over stock Whisper: convert the weights once into the runtime's format, then load like any model. Beats cloud STT (breaks offline), plain multilingual Whisper of the same size (weaker on Vietnamese tones), and the largest Whisper (too big for the memory left).

- TTS: Piper only. "Based on the survey of text-to-speech in Section 2.3.3, ..." Apply the yardstick to the survey's TTS options. Piper: VITS on CPU, ~200 MB, ~500 ms/sentence, the only offline Vietnamese voice, so it wins. Reject the cloud voices for network dependence (more natural but each reply would wait on the network). DECISION 2026-07-25: do NOT mention the edge-tts cloud fallback in §4.4 — it is a dev-machine convenience, not robot behaviour, and it undercuts the offline thesis. Cloud appears only as a rejected survey option, parallel to the STT paragraph.

- Close 4.4.1: the three picks sum to ~3.7 GB, filling nearly all the free memory (the perception budget 4.3 deferred), which is why no LLM can join them on the robot.

#### 4.4.2 Threaded Pipeline Architecture

How the three components are wired.

[Figure 4.4. Edge Voice Pipeline: VAD thread -> speech queue -> STT thread -> text queue -> main loop, with the barge-in path.]

- Design rationale. Three threads decouple listening, transcribing, and the network round trip, so no stage blocks the next. While STT transcribes one utterance, the VAD captures the next and the main loop sends an earlier transcript.

- Listening thread. Owns the microphone and Silero VAD. Idle until the server sends start-listening (customer presses "Talk to AI"). Gathers audio while the customer speaks, flushes after ~1.5 s of silence, disarms. Listens only when asked, so no continuous recording.

- Recognition thread. Waits for an utterance, runs PhoWhisper (~800 ms), passes the Vietnamese text on. A one-time warm-up transcription at start-up hides the model-load cost.

- Main thread. Sends the text to the agent, consumes the streamed reply sentence by sentence, speaks each sentence as it arrives (first sentence in ~0.5 s, so the robot answers while still receiving the rest).

- Interruption (barge-in). The listening thread keeps watching during playback; sustained speech stops the current sentence and starts a new capture. A brief noise does not trigger it; only continued speech.

- Tone by stage. The voice shifts slightly by order stage as a wordless cue: a little faster while adding items, slower when reading the order back, warmer after payment. Subtle; felt, not noticed. (Prose, no table.)

- Close. The design meets the two limits: fits the free memory, needs no internet to take an order, and the streamed, interruptible reply keeps a turn short.


---

### 4.5 Conversational AI Agent

The conversational agent is the system's decision engine. §4.1 requires it to accept informal Vietnamese utterances, map them to domain actions, and keep the cart consistent across voice and touch. §4.2 identifies two challenges that make this difficult: informal Vietnamese breaks classifier families in different ways (teencode, context-dependent affirmations, multi-intent compounding, rare dish names), and the LLM that selects actions is a probabilistic component — it can hallucinate dishes, quantities, or state transitions that must be caught before they reach the cart or backend.

This section presents the five-stage pipeline that addresses both: every utterance is classified into an intent, a worker LLM selects the tool to invoke, a deterministic validator inspects the arguments, the tool executes and state is updated, and a response is generated. Figure 2 shows the full component overview; Figure 3 shows the graph topology.

#### 4.5.1 Agent Architecture

The agent is built as a directed graph — not a monolithic LLM call — for three reasons. First, deterministic code runs between every LLM call: the validator inspects tool arguments before execution, the state updater advances the order stage machine, and the outcome node resets per-turn fields. The LLM never directly affects the cart, confirms an order, or requests payment. Second, every utterance follows a traceable path through the graph, making errors inspectable. Third, a circuit breaker limits retries to three attempts — the graph cannot loop indefinitely.

[Figure 3 — Agent StateGraph Topology: 10 nodes with routing edges, retry loops, and the final response path]

- Graph structure. The graph has ten nodes connected by directed edges. Routing is handled by six conditional edges that branch based on runtime state — which intent was classified, whether the worker produced a tool call, whether the validator passed or rejected, and whether more intents remain in the queue after processing. A compact table lists the ten nodes with their type (LLM or deterministic) and responsibility in one sentence.

- Execution flow. The ASCII graph below shows how an utterance traces through the nodes. The key paths: (a) classification → worker → validator → tools → state updater — the normal tool-execution path with a retry loop back to the worker on validation failure, (b) classification → chat worker → state outcome — the leaf path for general conversation that bypasses tools, (c) state updater loops back to the next worker for multi-intent turns until the intent queue is empty, (d) state outcome → response node → end — every path terminates at response generation.

[ASCII graph — keep the existing flow diagram]

- Shared state. All ten nodes read and write from a single typed state object passed along the edges. The fields fall into four categories: conversation history (accumulated messages across turns, never cleared), application state (the cart, order stage, and search context — persistent across turns), per-turn routing (the intent queue and routing metadata), and the inter-node contract (validator decisions, feedback, retry count — reset each turn). The state object is the only communication channel between nodes — no global variables, no side effects outside the graph.

- Conversation memory. The graph is compiled with LangGraph's SQLite checkpointer. Each session is identified by a thread ID that matches the orchestrator's session ID, ensuring that conversation state is scoped to a single party's visit. When a session ends, the checkpoint is cleared — the next guests at the same table start with a clean graph. Persistent fields (conversation history, cart, order stage, search context) survive across turns within a session; ephemeral fields (validator results, feedback, retry count) are reset each turn in the state outcome node.

- What this design solves. The graph topology directly addresses the two challenges from §4.2. The router handles classification under Vietnamese informality — even when it classifies incorrectly, the validator catches the downstream error and routes back with feedback. The circuit breaker guarantees bounded execution regardless of LLM behavior. The separation of deterministic nodes from LLM nodes means the agent can never skip validation, bypass the state machine, or produce an unbounded number of LLM calls.

#### 4.5.2 Intent Classification

The first stage of every utterance must decide what the customer wants — order food, search the menu, pay the bill, or just chat. This is the classification problem described in §4.2: informal Vietnamese with teencode abbreviations, context-dependent short affirmations, multi-intent turns, and domain-specific dish names breaks standard approaches. The router must be accurate, fast, and deterministic — three properties that prior approaches trade against each other.

[Figure 4 — Intent Classification: pipeline showing word segmentation → bi-encoder embedding → concatenation with context features → MLP → four-class output]

- Design decision: why an MLP, not an LLM. Classifying with an LLM (sending the utterance to Qwen2.5 and asking it to label the intent) achieves high accuracy but costs roughly 1.8 seconds per call — an unacceptable latency tax on every turn before the real work even begins. It is also non-deterministic: the same utterance can produce different labels on successive calls. A trained classifier is deterministic (same input always produces the same output), runs in under a millisecond, and is free — no GPU inference, no VRAM consumption. The trade-off is accuracy: the classifier must approximate what the LLM would decide, with a small fraction of the compute.

- Architecture. The classifier takes two inputs and combines them. The customer's utterance is segmented into words, then embedded using the same Vietnamese bi-encoder that powers the retrieval pipeline (selected in §2.5.2) — a 768-dimensional vector that captures semantic meaning in Vietnamese. Ten additional features encode the conversation state: the current order stage (one-hot encoded across five states), whether the cart contains items and how many, whether prior search results exist and how many, and the utterance length. These context features let the classifier distinguish "ok" at idle (agreeing to a greeting — a chat response) from "ok" at the confirmation stage (confirming an order — a decisive action). The combined 778-dimensional vector passes through a small three-layer neural network to produce a four-class probability distribution.

- Training. The classifier was trained on 3,712 synthetically generated Vietnamese utterances spanning all four intents, each paired with the conversation state that would accompany it. The training corpus was produced by a language model prompted with intent definitions and Vietnamese utterance templates, then validated against the menu. Embeddings were precomputed offline, making training fast — roughly two minutes on CPU with no GPU required. An 80/20 stratified split ensures each intent class is proportionally represented in both training and evaluation.

- Inference. At runtime, the classifier operates in three steps: segment the utterance into words, embed it with the bi-encoder, extract and concatenate the ten context features, and run the forward pass through the network. The output is the predicted intent, a confidence score, and the full probability distribution across all four classes. The entire pipeline completes in under a millisecond — three orders of magnitude faster than an LLM call.

- What this design solves. The MLP classifier addresses the informality challenge by combining semantic understanding (the bi-encoder embedding handles Vietnamese vocabulary and teencode) with state awareness (the context features resolve ambiguous short utterances). The embedding model is the same one used for menu retrieval — a deliberate coupling that ensures the classifier and the search system share the same Vietnamese semantic space. The classifier is not perfect: context-dependent affirmations and multi-intent utterances remain hard cases that the downstream validator and retry loop must catch. But it provides a fast, deterministic first decision that sets the graph in motion on every turn.

#### 4.5.3 Specialized Agents and Prompt Architecture

After the classifier decides the intent, a worker must decide the action. This is the second challenge from §4.2: the LLM is a probabilistic component in a system that must behave deterministically. The worker LLM can propose the wrong tool, fabricate a dish name, or produce impossible quantities. The response to this challenge is not to prevent the LLM from erring — that is not achievable without fine-tuning — but to give it a constrained surface to work on and let the downstream validator catch what slips through.

- Configuration. The worker LLM is Qwen2.5 14B served through Ollama at temperature 0.1 — low enough to suppress creative variation but high enough to avoid repetitive outputs. The key constraint is forced tool calling: the LLM is configured to always produce a tool call, never free-form text. This means every output is a structured instruction (which tool, with what arguments) that the validator can inspect. The system prompt is small, roughly 200 tokens, describing the worker's role and the available tools. Eleven few-shot examples demonstrate each tool with realistic Vietnamese utterances, positioned before the conversation to benefit from Ollama's key-value cache — the static prefix is loaded once and reused across turns.

- Tool bindings. Each intent class binds only the tools relevant to its task. The order worker has four cart operations and a delegate escape: add items, remove items, clear the cart, confirm the order, and delegate to chat when the utterance is not a cart action. The search worker has only search and delegate — it cannot modify the cart. The payment worker is deterministic: it always emits a request for payment with no LLM call at all. The chat worker is not an LLM node; it is a pure Python function that builds a curated memory context from prior search results and cart state. This binding per intent reduces the LLM's decision space — an order worker cannot accidentally call search, and a search worker cannot modify the cart.

- Delegate escape hatch. A delegate tool is bound alongside domain tools in every LLM worker. When the LLM cannot map the utterance to a meaningful domain action — a customer asks about pricing during an order turn, or asks for a recommendation during a search turn — it calls delegate with a reason string. The graph routes delegate-only calls to the chat worker, which handles the turn as a conversational query rather than a tool action. This mechanism means the LLM is never forced to produce a wrong action: if no domain tool fits, it delegates to conversation instead.

- Retry with corrective feedback. When the validator rejects a tool call — a dish name does not resolve, a quantity is invalid, or the order stage forbids the action — the rejection includes a feedback message explaining what failed and how to fix it. This feedback is injected into the worker's next prompt as a mandatory correction instruction. The LLM sees its previous attempt, the validator's specific complaint, and retries with the corrected arguments. This retry loop runs up to three times. After three failures, a circuit breaker triggers: the turn is terminated with an apology response, and no tool executes. The graph never loops indefinitely.

Prompt architecture (merged in from the former 4.5.7). Every LLM call in the agent is driven by prompts; there is no fine-tuned model and no domain-specific training. The prompts are the only surface through which the LLM learns the restaurant domain, Vietnamese service etiquette, and the tool-calling protocol. This makes the prompt architecture a first-class design element, not an implementation detail.

- System prompts. Seven files, all written in Vietnamese. Each LLM-calling node has its own prompt: the order worker's prompt defines the cart CRUD role and the critical rule that only new items should be passed to add (never re-pass the entire cart), the search worker's prompt defines how to rewrite conversational queries into search parameters, and the response node's prompt defines how to paraphrase structured contexts into polite Vietnamese service speech. Each prompt is roughly fifty to eighty lines — concise enough to leave room for conversation history within the context window, detailed enough to constrain the LLM's behavior.

- Few-shot examples. Static sequences of Vietnamese utterances paired with the correct tool calls, loaded at startup and injected between the system prompt and the conversation history. The order worker receives eleven examples covering basic addition, multi-item addition, removal, cart clearing, confirmation, substitution, delegate instruction, and conversational edge cases. The search worker receives eleven examples covering direct lookup, conversational rewrite, price filtering, dietary filtering, combined filters, delegate instruction, and menu-info queries. These examples are static — positioned before the dynamic conversation, they benefit from Ollama's key-value cache and are loaded once per session.

- Dynamic context. Three pieces of information are injected fresh on every turn. The last two conversation turns give the LLM awareness of what was just discussed. A section labeled "ĐÃ BIẾT" (already known) lists dishes from prior search results and the current cart to prevent redundant queries. When the validator rejects a tool call, its specific feedback message is injected as a mandatory correction instruction — the LLM sees exactly what failed and how to fix it.

- Model configuration. All LLM nodes use the same Qwen2.5 14B model served by Ollama, pinned in GPU memory with keep-alive enabled so no request waits for model loading. Temperature varies by role: 0.1 for workers (low variation — the LLM should consistently select the correct tool), 0.1 for the response node (low enough to stay faithful to structured context while allowing mild variation in natural speech). The router uses the trained MLP classifier — no LLM call at all.

---

#### 4.5.4 Deterministic Validator

The validator is the safety net between the probabilistic LLM and the deterministic system. It addresses the second challenge from §4.2 directly: the LLM can hallucinate — invent dish names, produce impossible quantities, or attempt actions forbidden by the order stage. The validator does not prevent hallucination; it detects and blocks it. Every LLM output that proposes a tool call passes through the validator before execution. No tool ever runs on unvalidated arguments. This is the invariant that keeps the cart and the backend safe: LLM proposes → validator inspects → action executes. Never LLM → action.

[Figure 5a — Validator Control Flow: LLM output enters → menu resolution → state consistency checks → pass with validated arguments, or reject with feedback]

- Menu name resolution. The most common hallucination is a dish name the customer never said — the LLM hears "Ốc Hương" and produces "Ốc Hương Xốt Trứng Muối" without knowing which variant the customer meant. The validator resolves every dish name against the authoritative menu of 217 items through a five-stage cascade, introduced in Figure 5b. Stage one normalises the input by lowercasing and stripping diacritics via Unicode decomposition. Stage two checks for an exact match. Stage three attempts prefix matching — a customer who says "Ốc Hương" is matched to every dish beginning with those words. Stage four widens to substring matching. Stage five, the fallback, computes token-level Jaccard similarity and accepts matches above a threshold. If all five stages fail, the item is flagged as unavailable.

[Figure 5b — Menu Resolution Cascade: five stages in sequence, with the match found and fallback path annotated]

- Off-menu items and ambiguity. Items that fail resolution are collected as unavailable items, each with a suggestion of the nearest-matching dish from the menu. The validator never auto-corrects — if the customer said "Cơm Tấm" but the restaurant does not serve it, the validator flags it, and the response layer tells the customer the item is unavailable and suggests the closest alternative. Items that match multiple menu entries — "Ốc Hương" resolves to eleven sauce variants — are collected as ambiguous items. The validator never auto-selects among them; the response layer asks the customer to clarify which variant.

- Modifier extraction. Vietnamese customers frequently attach requests to dish names: "Lẩu Thái ít cay" or "Bia Sài Gòn lạnh". A regex-based extractor separates the dish name from the modifier before resolution, storing the modifier as a note on the order item. This prevents "Lẩu Thái ít cay" from failing resolution because the full string does not appear in the menu.

- State consistency checks. Beyond name resolution, the validator enforces the order stage machine. If the customer is at the confirmation stage and says "thêm một phần nữa" (add one more), the validator detects that this is an additive turn in the wrong stage and loops the cart back to drafting. If the LLM produces both an add and a confirm in the same turn, the validator strips the confirm — the customer must explicitly confirm after seeing the full cart. If the LLM drops context and proposes adding only the new item while forgetting the existing cart, the validator restores the prior items automatically. These checks are deterministic rules applied to the tool call arguments and the current agent state — no LLM judgment is involved.

- What this design solves. The validator provides a guarantee that no other component in the pipeline can offer: every action that affects the cart, the backend, or the payment system has been inspected against an authoritative source. The LLM is free to hallucinate; the validator catches it before any damage is done. The five-stage cascade handles the full range of Vietnamese dish name variation — from exact matches to domain-specific abbreviations to diacritic-stripped informal text. Combined with the circuit breaker in the worker (§4.5.3), the system guarantees bounded execution with zero side effects from invalid tool calls.

#### 4.5.5 State Management

The validator has approved the tool call. Now it must execute, and its results must update the shared state that subsequent turns will read. This is the fourth stage of the pipeline — the bridge between decision and effect.

[Figure 9 — Cart / Order Stage Machine: IDLE → DRAFTING → AWAITING_CONFIRMATION → CONFIRMED, with the transitions that each tool triggers]

- In-memory cart tools. Adding, removing, and clearing items operate entirely on the agent's in-memory cart — no network I/O, no database writes. Multiple additions of the same dish increment the quantity rather than creating duplicate line items. This isolation means cart operations are fast (sub-millisecond) and the cart is always consistent before confirmation. Only when the customer explicitly confirms does the agent serialize the cart and send it to the orchestrator as a committed order.

- Backend tools. Confirmation, payment requests, and payment verification contact the orchestrator over HTTP. The confirm tool serializes the entire cart as order items and receives an order ID in return. The payment request tool asks the orchestrator to compute the session total across all confirmed orders and returns a payment URL and amount. The verify tool marks the payment as settled, closes the session, and frees the table. These three tools are the only agents of permanent change in the system — everything else is in-memory state that resets when the session ends.

- Order stage machine. The cart advances through four states enforced by the state updater node. The cart starts idle. The first add transitions to drafting — the agent echoes each addition back to the customer. When the customer appears finished (either by stopping additions or by an implicit confirmation cue), the stage advances to awaiting confirmation. In this state, further additions or removals loop the cart back to drafting and the updated cart is re-echoed. Only an explicit confirmation moves to confirmed — a terminal state from which no further cart modifications are allowed. Payment verified loops back to idle for the next session.

- Multi-intent iteration. Some utterances contain multiple requests: "Cho 2 Ốc Hương rồi tính tiền luôn" (give me two Ốc Hương and the bill). The classifier produces a queue of intents. The graph processes them sequentially: the first intent (order) runs through worker → validator → tools → state updater, then the updater checks whether more intents remain. If yes, it routes back to the appropriate worker for the next intent (payment). Only when the queue is empty does the graph advance to the state outcome node, which combines all results into a single response. This sequential processing ensures that each intent's tool execution sees the state produced by the previous intent — the payment request correctly totals the cart after the order has been added.

#### 4.5.6 Response Generation

The final stage produces the Vietnamese spoken reply. After the tools have executed and state has been updated, the state outcome node builds a typed response context — a structured object containing all the information the reply must convey: which dishes were added, what the search returned, the cart total, or an error message. The response node converts this structured context into natural Vietnamese speech.

- Two response paths. Template-based responses handle outcomes that are deterministic: order confirmations list the cart items and total, payment prompts present the amount and QR code, and error messages explain what went wrong. These are pre-written Vietnamese phrases with placeholders for the dynamic content — the response node fills the blanks and returns without calling the LLM. LLM-based responses handle outcomes that require free-form generation: search results rephrased in conversational Vietnamese, off-menu suggestions with alternative dishes, and general chat responses. The LLM receives the typed context as a structured block and paraphrases it into natural speech at temperature 0.1 — low enough to stay faithful to the provided facts.

- Streaming delivery. The response node streams the LLM output sentence-by-sentence through a thread-safe queue bridged to an SSE endpoint. The edge voice device receives each sentence as it is produced and dispatches it to TTS immediately — the first sentence reaches the speaker before the full response is generated. This reduces perceived latency from the full graph execution time to the time of the first sentence, roughly half a second.

- Safety after generation. Even after the response is generated, two guard functions run. The grounding guard verifies that any dish names in an LLM-generated search response are present in the actual retrieval results — if the LLM hallucinates a recommendation, the response is replaced with a deterministic listing of what the retriever actually found. The sentence sanitization guard strips residual CJK characters and markdown formatting that Qwen2.5 occasionally leaks into Vietnamese output, ensuring the TTS engine receives clean text.

### 4.6 Knowledge Retrieval Pipeline

§4.1 requires the system to let customers find dishes by describing taste, dietary type, price, or occasion — not only by name. §4.2 identifies the challenge that makes this difficult: sensory queries and menu entries share no vocabulary. A customer says "trời lạnh ăn gì ấm bụng" (cold weather, something warming), but the menu is organized by name, category, and price — none of which match. Standard retrieval, which embeds the query and searches for similar documents, fails when the query and the relevant documents occupy disconnected regions of the semantic space.

This section presents a closed-loop pipeline that addresses this gap. It has four stages, shown in Figure 6. First, an LLM rewrites the vague query into concrete search terms using Vietnamese culinary knowledge — "ấm bụng" becomes "cháo, lẩu, súp, món nước nóng." Second, a hybrid retriever combining exact keyword matching (BM25) and semantic similarity (FAISS) searches the menu, fusing results through reciprocal rank fusion. Third, the LLM evaluates the retrieved dishes against the original customer intent and rephrases the relevant ones in natural Vietnamese. Fourth, search results persist across turns so follow-up questions are answered from memory rather than re-querying. Together, these four stages form a loop where the LLM is not a passive consumer of retrieval output but an active controller — deciding what to search for before retrieval and evaluating what was found after it.

[Figure 6 — Hybrid Retrieval Pipeline: customer utterance → LLM rewrite → BM25 + FAISS → RRF fusion → LLM evaluate + rephrase → conversational reply]

#### 4.6.1 Query Rewriting

The first stage transforms the customer's experiential description into terms that match the menu's vocabulary. This is not a keyword extraction step — it requires domain reasoning. Knowing that "ấm bụng" (warming the stomach) in Vietnamese food culture means hot soups, porridges, and stews is culinary knowledge that an embedding model does not encode. The rewriting step uses the worker LLM to bridge this gap: it receives the customer's original utterance and produces a set of concrete search terms in Vietnamese.

- How it works. The search worker's system prompt includes a Vietnamese-to-search-term mapping: descriptions of feelings, occasions, and vague preferences mapped to specific dish categories and ingredients that appear in the menu. When the customer says "trời lạnh ăn gì ấm bụng," the LLM outputs "cháo, lẩu, súp, món nước nóng." When the customer says "ăn cay quá, có món nào đỡ hơn không," it outputs search filters for mild dishes. The rewritten query serves two purposes: the terms become the input to BM25 keyword search, and the full query string is embedded for FAISS semantic search.

- Why an LLM. A rule-based synonym dictionary cannot handle the range of Vietnamese experiential language — "ấm bụng," "mát ruột," "đưa cơm," "lạ miệng" each map to different culinary categories, and new variations appear in every conversation. The LLM handles these through its general Vietnamese language understanding, guided by the system prompt's domain-specific mapping. The rewriting call is lightweight — a single short prompt with no tool calling — and completes in under a second.

#### 4.6.2 Hybrid Retrieval

The rewritten query enters a hybrid search pipeline that combines two retrieval strategies with complementary strengths: exact keyword matching and semantic similarity.

- BM25 sparse retrieval. The rewritten terms are tokenized using Vietnamese word segmentation that recognizes compound words as single units — "bún bò Huế" is one token, not three syllables. The inverted index maps each token to the menu items containing it, and BM25 scores each document by term frequency and distinctiveness. This captures exact matches: if the rewritten query contains "lẩu," every dish whose name, category, or tags include "lẩu" receives a score. But BM25 is blind to semantic relationships — a query for "ấm bụng" that is rewritten to "lẩu, súp" will miss "Bò Kho" (braised beef stew) unless the word "kho" or "bò" appears in the query.

- FAISS dense retrieval. The rewritten query is embedded using the same Vietnamese bi-encoder that powers the classifier and the document index — a 768-dimensional vector that captures semantic meaning. The query vector is compared against the index of 217 menu dish embeddings via cosine similarity. This captures semantic relationships: "lẩu, súp" is semantically close to "Bò Kho" even though they share no words, because both are hot, liquid-based dishes that appear in similar culinary contexts. The bi-encoder is diacritic-aware, trained on Vietnamese sentence pairs including informal registers.

- Fusion and filtering. BM25 and FAISS each return their top ten results. Reciprocal rank fusion combines the two lists by rank position rather than by raw score, which is essential because BM25 scores are unbounded while cosine similarities are bounded — attempting to weight them directly would require score normalization that is sensitive to query difficulty. Fusion operates on the principle that a document ranked highly by both strategies is more likely to be relevant than one ranked highly by only one. Metadata filters for price range, dietary type, and category are applied to each retriever's results independently before fusion — this ensures that a semantically strong but price-filtered result does not crowd out affordable alternatives in the final ranking.

- Empty results. When both BM25 returns zero matches and no FAISS result exceeds the similarity threshold, the retriever returns an empty set. The search worker's delegate mechanism routes empty results to the chat worker, which produces a graceful "not found" response. No dish name is fabricated to fill the gap.

#### 4.6.3 Result Rephrasing

After retrieval, the fused results are raw menu entries — dish names, prices, tags, and descriptions. The customer did not ask for a data dump. The third stage uses the response LLM to evaluate the results against the original query and rephrase only the relevant dishes in natural Vietnamese.

- Evaluation. The LLM receives the original customer utterance, the fused search results, and the instruction to select only dishes that match the customer's stated constraints. If the customer asked for mild dishes and the results include both mild and spicy items, only the mild ones are verbalized. If the customer asked for dishes under 100,000 VND and some results exceed that, only the affordable ones are mentioned.

- Rephrasing. Selected dishes are presented conversationally: "Dạ, cho ngày lạnh quán có Lẩu Cá Tầm, Cháo Hải Sản, và Súp Cua ạ." Each dish includes its price and a brief note on why it matches (e.g., "nóng, ấm bụng"). The rephrasing call uses the response LLM at temperature 0.3 — natural variation across turns without inventing facts.

- Empty-result response. When the retriever returns no results, the LLM does not attempt to suggest alternatives from its own knowledge — that is how closed-book hallucination happens. Instead, the response layer produces a templated apology: "Dạ, quán không có món đó ạ. Anh/chị muốn em gợi ý món khác không?" This keeps the system honest about gaps in the menu.

#### 4.6.4 Multi-Turn Search Context

A customer rarely asks one question and stops. A typical conversation builds on prior turns: "Ốc Hương giá bao nhiêu?" → "Có cay không?" → "Vậy cho 2 phần đi." The second and third turns refer to a dish that was searched in the first turn, not explicitly named again. Without memory, the system would treat "Có cay không?" as a new, orphaned query with no referent.

- How context persists. After every search turn, the state outcome node writes the retrieved results into the agent's shared state. The chat worker reads this search context on subsequent turns and converts it into a curated memory — a compact record of up to five recently discussed dishes, each with its name, price, tags, taste profile, and category. This curated memory is injected into the chat worker's context block, giving the response LLM the information needed to answer follow-up questions without re-querying.

- Deduplication. A section labeled "ĐÃ BIẾT" in the search worker's prompt lists dishes already in the curated memory and the current cart. If the customer searches for "Ốc Hương" a second time, the LLM sees that the system already holds these results and responds from memory rather than re-running the retrieval pipeline.

- Context lifetime. Search context persists until the customer pays, at which point the session ends and all conversation memory is cleared. A search context is overwritten by the next search — the system remembers only the most recent search, not a complete search history. This is a deliberate design choice: the curated memory cap of five dishes ensures that follow-up context remains focused on the most recent topic without accumulating unrelated searches across many turns.

---

### 4.7 Backend Orchestrator

§4.1 requires the system to persist orders, push real-time updates to all client roles, enforce the session lifecycle, manage a fleet of robots, and serve six tables concurrently — all on a single self-hosted machine. §4.2 identifies two challenges: the backend is a shared state machine driven by the AI agent rather than by human staff, with multiple client roles needing live views of agent-driven events (polling is too slow, cloud fails when WiFi drops); and the bond between a robot and the table it serves must survive disconnection, with tasks requeued and voice bindings released transparently.

This section presents the backend orchestrator, a single FastAPI process that coordinates restaurant operations. It has four responsibilities: exposing a REST API for commands and a WebSocket hub for real-time events, managing the lifecycle of each customer session from seating through payment, dispatching navigation tasks to the robot fleet and binding voice channels on arrival, and persisting all business records in an embedded SQLite database.

#### 4.7.1 API and Real-Time Events

The backend serves two kinds of traffic: request/response commands over REST and pushed events over WebSocket. Separating them means a slow LLM inference turn never delays a kitchen display update, and a burst of robot telemetry never queues behind a payment transaction.

- REST API. Twenty endpoints across ten logical groups — menu, tables, orders, payments, robots, tasks, layout, admin, voice, and the WebSocket endpoint itself. Request and response bodies are validated through Pydantic schemas that mirror the TypeScript interfaces shared with the frontend applications. All endpoints produce and consume JSON. The API is self-documenting through auto-generated OpenAPI documentation.

- WebSocket hub. A single endpoint serves four distinct client roles distinguished by a query parameter, introduced in Figure 13. The panel role broadcasts kitchen display updates, fleet status changes, and task lifecycle events to all connected management dashboards — anonymous broadcast, every panel instance receives every event. The customer role also broadcasts anonymously, but each event carries a table identifier, and each tablet filters by its own table — a tablet at table three silently discards events for table five. The robot role is indexed by robot identifier and carries bidirectional traffic: task assignment from the server to the robot, telemetry and status from the robot to the server. The voice-device role is indexed by robot identifier and carries server-to-client commands only — start and cancel listening signals that control the microphone.

[Figure 13 — WebSocket Hub: four roles, one endpoint, with fan-out and indexed routing]

- Event catalog. Nine event types cover the full restaurant operation cycle: orders created and updated, tables updated, robots updated, tasks created and updated, voice heard and voice reply, and a system-wide reset. Each event type is routed to the subset of roles that need it — a voice event reaches the customer tablet and the voice device but not the kitchen display; a task event reaches the panel and the robot but not the customer.

#### 4.7.2 Session Lifecycle

A session represents one party's entire visit — from the moment they are seated until they pay and leave. This is the unit of billing: all orders placed during a session accumulate into a single payment, and conversation state is scoped to the session so the next party at the same table starts with a clean slate.

[Figure 11b — Session Lifecycle: seating → orders → payment → table release, with conversation thread isolation]

- Seating. The entrance kiosk sends a seating request with a table identifier and party size. The orchestrator opens a new session with status active, marks the table as occupied, and dispatches a go-to-table task to guide the party. The session identifier becomes the LangGraph thread identifier in the agent brain — conversation memory is now scoped to this visit.

- Ordering. Every confirmed order is associated with the active session. The session accumulates orders across multiple turns — a party can order appetizers, then mains, then drinks, each as a separate confirmation. The session total is computed server-side as the sum of all confirmed order amounts, preventing the client or agent from miscalculating.

- Payment. When the agent requests payment, the orchestrator computes the session total and generates a payment record with a VietQR URL. The customer scans and pays. The verify endpoint confirms the payment, marks the session as closed, sets the table to available, and cancels any pending robot tasks for that table. The agent brain's checkpoint for this session is cleared, freeing conversation memory.

- Manual intervention. Staff can manually close a table through the management panel if a party leaves without paying or a session needs to be reset. This clears the table state, cancels pending tasks, and sends any robot at that table back to the dock.

#### 4.7.3 Fleet Management

The dispatcher translates business events into robot navigation tasks. It selects the appropriate robot, tracks fleet status in real time, and recovers when a robot disconnects.

[Figure 12a — Task Lifecycle + Robot States: PENDING → ASSIGNED → IN_PROGRESS → DONE, with robot states driven by task assignments]

- Telemetry. Each robot sends a heartbeat over its WebSocket connection at four or more times per second, reporting its current position, battery level, and status. These heartbeats are stored in a thread-safe in-memory dictionary — not written to the database. Writing four heartbeats per second per robot to SQLite would create file-level contention with order and payment transactions. A periodic snapshot writes the most recent pose and battery to the database every fifteen seconds for cold-start recovery after server restart, but live operations read exclusively from memory.

- Task assignment. On every new task and every robot state change, the dispatcher scans pending tasks in FIFO order. For each task, it scores all eligible robots — those with idle status, an alive WebSocket connection, and battery above twenty percent — by Euclidean distance from the robot's live position to the target table's waypoint. The nearest robot receives the assignment in a SQLite transaction that atomically marks the task assigned and the robot busy. The task is then sent over the robot's WebSocket as a navigation goal. The three task kinds — go to table, deliver, and call — correspond to the three business events that trigger robot movement: a party is seated, an order is ready, or a guest presses the call button.

- Task lifecycle. A task progresses through four states: pending (awaiting assignment), assigned (a robot has been selected but has not yet acknowledged), in progress (the robot is navigating), and done (the robot has arrived and completed the task). When a robot arrives at a table, the dispatcher establishes a dynamic binding between that table and that robot — all voice commands from that table's tablet are now routed to this robot's microphone and speaker. When the task completes, the binding is released and the robot returns to idle.

[Figure 12b — Dynamic Voice Binding: table → robot → voice-device resolution on arrival and release on departure]

- Fault recovery. A watchdog runs every five seconds. Any robot that has sent no heartbeat for thirty seconds is marked offline. Its current tasks are requeued to pending. Its voice binding is released. Its WebSocket connection is closed. The next call to the assignment function will select a different robot for the requeued tasks. If the orchestrator process itself restarts, pending tasks survive in the database, robots reconnect as idle, and the periodic pose snapshots provide approximate last-known positions for assignment scoring. The customer never specifies which robot to use — the dispatcher abstracts over individual robots entirely.

#### 4.7.4 Database Schema

All business records are stored in a single SQLite database file using raw SQL with no object-relational mapping layer. SQLite's write-ahead logging mode enables concurrent reads during writes, which is essential when the kitchen panel is loading order details at the same moment a new order is being inserted.

[Figure 10a — Database Schema: business ledger · Figure 10b — Database Schema: fleet tables]

- Business tables. Eight tables model the restaurant domain. Tables records each physical table with its capacity and current status. Sessions links a visit to a table, tracking the party size, start time, and end time. Dishes is a cached copy of the menu for quick lookup. Orders associates a confirmed order with a session and a table, carrying a status that advances through the kitchen workflow. Order items lists each line item with its dish reference, quantity, unit price, and optional note. Payments records the session total, payment method, transaction reference, and status. Robots stores the fleet inventory with periodic pose and battery snapshots. Tasks records every dispatcher assignment with its kind, target table, assigned robot, and status.

- Conversation memory. A separate SQLite file stores LangGraph checkpoints — the agent's conversation state per session. This database is managed entirely by LangGraph's built-in persistence layer. It is logically separate from the business ledger: clearing a conversation has no effect on orders or payments, and restoring the business database from a backup does not alter in-progress conversations.

- Schema evolution. The database is evolved through a migration function that adds columns via SQLite's alter table command, using table introspection to make each migration idempotent — running it twice is safe. This avoids the complexity of a full migration framework while allowing the schema to grow as features are added during development.

---

### 4.8 Web Interfaces

§4.1 requires three role-specific interfaces — a customer tablet, an entrance kiosk, and a management panel — all reflecting backend state in real time through push rather than polling. This section describes each application and the shared architecture that keeps them consistent with the orchestrator. No dedicated figures; the communication patterns reference Figure 1 (system topology), Figure 7 (voice ordering flow), and Figure 13 (WebSocket hub).

Opening prose. One paragraph stating the shared approach: all three applications are Vue 3 single-page applications built with Vite, sharing a common TypeScript library that mirrors the backend's Pydantic schemas for type-safe API communication. Each application manages its own state through Pinia stores. Development proxies route API calls and WebSocket connections to the orchestrator on port 8000.

#### 4.8.1 Customer Tablet

The tablet at each table is the customer's primary interface. It lets the customer browse the menu, see what the AI heard and said, manage the cart, and pay.

- Menu browsing. Twelve seafood categories displayed in a scroll-synced navigation panel. A diacritic-insensitive search bar accepts Vietnamese queries without requiring correct tone marks — "oc huong" finds "Ốc Hương." A Best Seller section highlights popular dishes. The menu data is fetched from the orchestrator's REST API on first load and cached.

- Voice mirror. The tablet maintains a persistent WebSocket connection with the customer role. When the agent processes an utterance, the tablet receives two events: voice.heard (the transcribed text with a "đang suy nghĩ" thinking indicator) and voice.reply (the agent's spoken response, updated cart state, and an optional UI action such as opening the payment screen). The conversation history scrolls in a chat-like panel, with customer utterances on one side and agent replies on the other. The cart synchronizes bidirectionally — items added by voice appear in the visual cart, and items added by touch are pushed to the agent's checkpoint so subsequent voice commands operate on the correct state.

- Cart and payment. The cart shows each item with its name, quantity, unit price, and any special request note. The total is computed by the orchestrator, not the tablet, to prevent client-side miscalculation. A confirm button sends the cart to the agent for final confirmation. When the agent requests payment, the tablet displays a VietQR code and the session total.

#### 4.8.2 Entrance Kiosk

The kiosk runs on a tablet at the restaurant entrance. It has a single function: seat a party at a table.

- Table grid. A visual grid shows all six tables with their current status — available tables in green, occupied tables in red. The staff member selects an available table and enters the party size. A single button sends the seating request to the orchestrator.

- Cascading effects. The seating action triggers a chain: the orchestrator opens a session, marks the table occupied, creates a go-to-table task for the fleet dispatcher, and broadcasts a table.updated event to all panels. The kiosk does not need to know about these downstream effects — it sends one request and the orchestrator handles the rest. If two kiosks attempt to seat the same table simultaneously, the orchestrator returns a conflict response and the kiosk refreshes the grid to reflect the updated state.

#### 4.8.3 Management Panel

The management panel runs in the kitchen and manager's office. It has four views, all updated in real time through a panel-role WebSocket connection.

- Kitchen Kanban. A three-column board displaying orders grouped by status: Chờ Bếp (awaiting preparation), Đang Làm (in progress), and Xong (complete). Each order card shows the table name, the items with quantities, and an elapsed timer since the order was placed. Staff advance orders by pressing a button — each advance sends a PATCH request to the orchestrator, which emits an order.updated event that moves the card to the next column. When an order reaches Xong, the orchestrator creates a delivery task for the fleet dispatcher.

- Fleet board. A grid of robot cards, each showing the robot's name, status badge (idle, busy, returning, offline), battery percentage with color coding, current activity label, and time since last heartbeat. The data updates at up to five hertz from the throttled telemetry broadcast.

- Table overview. A grid of all six tables with current status, party size, session duration timer, and links to active orders. This view lets the manager see the restaurant floor at a glance — which tables are occupied, how long each party has been seated, and whether any table needs attention.

- Minimap. The restaurant floor plan with the SLAM map as a background and live robot position dots overlaid at five hertz. Each robot is represented by a colored marker whose position updates as telemetry arrives. This is the only view that consumes high-frequency sensor data — all other panel views update on business events.

### 4.9 Deployment Topology

The system runs on three classes of hardware connected by the restaurant's local WiFi network. No cloud services are required in normal operation. Figure 1 provides the full deployment view.

- Central server. An x86 desktop computer with an NVIDIA GPU. It runs three processes: the Ollama inference server hosting Qwen2.5 14B at Q6_K quantization (pinned in GPU memory), the agent brain on port 8100, and the backend orchestrator on port 8000. Two SQLite database files store the business ledger and conversation memory. The RAG indices — FAISS and BM25 — are loaded into the orchestrator process memory. All components on the server communicate over the local loopback interface.

- Robot. An NVIDIA Jetson Orin Nano mounted on the TWD chassis, connected to a LiDAR, depth camera, IMU, microphone, speaker, and touchscreen. It runs the ROS2 navigation stack, the threaded voice pipeline, and two persistent WebSocket connections to the orchestrator. The Jetson's 8 GB of shared memory holds navigation (~500 MB), sensor drivers (~200 MB), the STT model (~1.5 GB), and the TTS model (~200 MB). The LLM does not run here.

- Staff devices. Standard tablets and laptops running a web browser on the local WiFi network. No software installation is required — the orchestrator serves the three single-page applications as static files. Each device opens one of the three interfaces by navigating to the appropriate URL on the server.

- LLM configuration. A single Qwen2.5 14B model serves three logical roles through temperature variation: workers at 0.1 (deterministic tool selection), the response node at 0.3 (natural variation in speech). The model is kept permanently resident in GPU memory with Ollama's keep-alive setting. A warmup ping at agent startup ensures the model is loaded before the first customer utterance arrives.

- Package management. Python dependencies are managed through uv with role-based extras — installing only the packages needed for the server role, the voice device role, or development. Frontend dependencies are managed through npm workspaces, with three Vite applications and one shared TypeScript library in a single repository. This separation means the Jetson installs only the voice pipeline and ROS2 dependencies, not the agent or orchestrator packages.

---

## CHAPTER 5: EXPERIMENTS AND RESULTS

> **Chapter requirements — this chapter answers:**
> - What hardware and software was the system tested on? (5.1: server, robot, software stack)
> - How was evaluation designed? (5.2: datasets, metrics, statistical protocol)
> - For each §1.3 objective and each Ch.2 need: what was tested, what were the results, do the results meet the target?
> - Per experiment: goal → dataset → methodology → metrics → results → analysis → ablation (where applicable)
> - What is the failure budget? Which component contributed the most failures? (5.6)
> - Do the aggregate results confirm the system design proposed in Ch.3–Ch.4? (5.6 traceability)

> *Each experiment validates one or more requirements from §3.1 and §4.1, which trace back to needs identified in Chapter 2. Structure per experiment: goal → dataset → methodology → metrics → results → analysis → ablation.*

---

### 5.1 System Under Test

#### 5.1.1 Server Hardware

*(See `05-01-system-under-test.md` for full prose.)*

#### 5.1.2 Robot Platform

*(See `05-01-system-under-test.md` for full prose.)*

#### 5.1.3 Software & Network Stack

*(See `05-01-system-under-test.md` for full prose.)*

---

### 5.2 Evaluation Design

#### 5.2.1 Datasets Summary

*(See `05-02-evaluation-design.md` for full prose.)*

#### 5.2.2 Metrics Definition

*(See `05-02-evaluation-design.md` for full prose.)*

#### 5.2.3 Statistical Protocol

*(See `05-02-evaluation-design.md` for full prose.)*

#### 5.2.4 Experiment Inventory and Reproduction

*(See `05-02-evaluation-design.md` for full prose.)*

---

### 5.3 ROS2 Navigation Experiments

---

#### 5.3.1 Odometry Accuracy Test

- Goal: validate EKF-fused odometry accuracy on TWD platform
- Dataset: 10–20 return trips, kitchen → table → kitchen, varied table distances
- Methodology: record `/odometry/filtered` → compare start/end pose
- Metrics: return-to-start error (cm), RMS trajectory error vs. ground truth
- Ablation: encoder-only vs. EKF-fused (with and without IMU yaw)
- **→ Validates requirement R(odometry) from §3.1; maps to §2.2 gap**

#### 5.3.2 Map Building and Localization Test

- Goal: evaluate RTAB-Map map quality and localization reliability
- Dataset: offline mapping run + localization-only runs
- Methodology: build map → run localization → measure localization consistency
- Metrics: loop closure events, localization drift over time, map resolution
- Additional: verify the map is queryable as navigation infrastructure — table waypoint poses
  and the dock pose resolvable by the backend, which is the §2.2.2 gap rather than map quality
  alone
- **→ Validates requirement R(mapping) from §3.1; maps to §2.2.2 gap**

#### 5.3.3 Navigation and Docking Test

- Goal: end-to-end navigation + ArUco docking precision
- Dataset: kitchen → 6 tables → kitchen, 5–10 trials per table
- Methodology: Nav2 goal → drive → ArUco re-localization → measure final pose
- Metrics: navigation success rate, docking error (cm, °), ArUco detection rate
- Ablation: with and without ArUco correction on final approach
- **→ Validates requirements R(navigation) + R(docking) from §3.1; maps to §2.2 gap**

#### 5.3.4 Dynamic Goal Assignment Test

- Goal: validate that backend-generated Nav2 goals are executed correctly
- Dataset: 10 sequences: backend API → goal change mid-navigation
- Methodology: send goal A → robot en route → send goal B → verify robot routes to B
- Metrics: goal switch latency, correct arrival at new goal
- **→ Maps to §2.2 core gap: dynamic goal coupling with external AI agent**

---

### 5.4 AI Agent Experiments *(→ Need 3, §2.4; Need 4, §2.5)*

> *This section carries the thesis's primary contribution. It is ordered by the agent's own
> execution path — classify (§5.4.1), validate (§5.4.2), execute and verbalise (§5.4.3),
> retrieve (§5.4.4) — then evaluates the composition of those stages end to end (§5.4.5) and
> against its cost (§5.4.6). All experiments in §5.4 feed the agent typed text; the voice
> pipeline is described architecturally in §4.4 and acknowledged as unevaluated in §5.6.4.*

#### 5.4.1 Intent Classification & Routing *(→ §2.4.4)*

The routing contribution is a joint claim about accuracy **and** cost: a trained classifier
reaches LLM-level routing accuracy at a fraction of the latency.

- **Six-arm paired ablation.** Locate the proposed classifier against every routing approach
  surveyed in §2.4.4 on 130 identical cases. Arms: Centroid, SLM (qwen2.5:3b), Hybrid
  semantic→SLM, MLP with context ablated, MLP+context (proposed), and LLM zero-shot
  (qwen2.5:14b-instruct). Metrics: accuracy with Wilson CI, confusion matrix, p50/p95 latency, peak
  memory, accuracy-per-cost. Statistics: paired McNemar exact against the proposed arm,
  reporting discordant counts and exact p-values. The defensible claim is the latency ratio at
  statistically indistinguishable accuracy.

- **Context-feature ablation.** Arm D vs. arm E on 21 context-dependent utterances where
  "ok" at IDLE differs from "ok" at AWAITING_CONFIRMATION. At n=21 the comparison cannot reach
  significance; report the effect with its interval and state the required sample size.

- **Clean holdout.** 39-case set partitioned before augmentation, never used for tuning.
  Reported as a fraction with its Wilson interval — the number that gets defended.

- **Vocabulary-coverage diagnostic.** Measure the training corpus's unique-token count and
  per-evaluation-set out-of-vocabulary rate. Cross-tabulate misclassifications against OOV
  membership and confidence. Establishes *why* the classifier fails: a narrow-corpus softmax
  over an unseen region is confidently wrong, which is why a confidence threshold fails.
  The corpus regeneration attempt and its coverage-vs-quality trade-off are reported as a
  negative result. → Feeds §6.2 with measured evidence.

#### 5.4.2 Action Validation & Safety *(→ §2.4.5)*

- **Name resolution by stage.** 70 pairs through the five-stage cascade (normalise → exact →
  diacritic → prefix → substring → token-Jaccard). Accuracy per stage; rejection correctness on
  misspelled inputs. Run once, reported as exact fractions.

- **Ambiguity detection.** 25 cases where a generic name matches multiple menu variants (e.g.
  "Ốc Hương" → 11 sauce variants). Metrics: precision, recall, false positive/negative rates.
  The validator flags ambiguity for clarification and never auto-selects.

- **Validator ablation — the central safety claim.** The validator node is replaced by a
  pass-through before graph construction. Run 41 scenarios in both arms (ON vs OFF) and measure
  what reaches the cart, the kitchen, and the payment system. Off-menu leakage must be
  determined by resolving item names against `menu.json`, not read from an `is_valid` flag
  written by the validator. A null result bounds the claim to "the validator is a guarantee,
  not an observed-necessary correction." Metrics: off-menu items reaching the cart, scenario
  pass rate, validator catch rate, circuit-breaker rate.

- **Out-of-menu robustness.** 30 adversarial scenarios across 7 categories, including a
  negative control (on-menu request that must not be rejected). Metrics: pass rate, off-menu
  leak rate, false-rejection rate. The assertion runner must fail on any unrecognised key.

- **Delegate escape hatch.** With `tool_choice="any"`, a worker obliged to call a tool when
  none applies can call `delegate(reason)` instead. Measure delegate rate per worker,
  correctness of each delegation, and — with the delegate unbound — the count of wrong tool
  calls. → Validates R(validation) from §4.1; maps to the §2.4.5 gap.

#### 5.4.3 Multi-Intent Execution & Verbalisation *(→ §2.4.7)*

- **Goal:** for one utterance carrying several intents, measure separately whether the system
  (a) executed them all and (b) told the customer about all of them.
- **Dataset:** 25 multi-intent turns with per-intent lexical evidence.
- **Metrics:** verbalisation rate, coverage of what the customer asked, router-queued-all rate,
  each broken down by the number of intents in the turn.
- **Analysis:** attribute the loss between the router and the response layer. Report how the
  rate degrades as intents accumulate. This is expected to be a negative result — a quantified,
  mechanism-explained limitation is stronger than an unmeasured claim of completeness.

#### 5.4.4 Knowledge Retrieval *(→ Need 4, §2.5)*

- **Retrieval quality.** 24 menu queries with graded relevance. Metrics: P@5, R@5, MRR, Hit
  Rate, per-difficulty breakdown. In a conversational suggestion setting, recall and hit rate
  matter more than precision — the agent presents candidates and the customer selects.

- **Retriever ablation.** BM25-only vs. FAISS-only vs. RRF fusion on the same 24 queries.
  Second ablation: with and without query rewriting, isolating the rewriter's contribution.

- **Dual-lane gatekeeper.** Per-query characterisation: semantic-lane pass, lexical-lane pass,
  both, neither; correct rejections, false rejections, false approvals; raw top-1 similarity
  distribution. → Validates R(retrieval) from §4.1; maps to the §2.5 closed-loop gap.

#### 5.4.5 End-to-End System Evaluation *(→ §2.4, §2.6)*

- **E2E conversations.** 11 scripted ordering flows (6 happy-path, 5 edge-case) plus 4
  real-life scenarios as qualitative case studies. Per-turn assertions on tool calls, cart
  state, and order stage. Metrics: scenario pass rate with Wilson CI, per-turn failure
  attribution by stage. Where the agent verbalises an action it never took, record it as a
  distinct failure mode — the validator protects state but not free text.

- **Long-conversation state integrity.** A 15-turn couple's visit: browse, ask, order across
  several turns, substitute, review cart, confirm, pay. Metrics: cart correctness at each
  checkpoint, order-stage transitions, context retention on late references to items discussed
  early, and turn latency drift as history grows. Validates the memory architecture of §4.5.5.
  → Validates R(agent) + R(e2e) from §4.1.

#### 5.4.6 Agent Latency & Cost *(→ §2.4, §2.8)*

- **Goal:** account for the turn budget — where the time goes and which stage dominates.
- **Methodology:** instrument every LangGraph node with high-resolution timestamps over the E2E
  set; compare cold-start against warm-cache.
- **Metrics:** stage latency p50/p95 per node, turn latency p50/p95 per intent class, peak GPU
  and host memory. Percentiles, never means — LLM stages are heavily skewed.
- **Analysis:** identify the dominant stage and state what it implies for the deployment
  decision (LLM on the server, not the robot). → Supplies the cost half of the §5.4.1 trade-off.

---

### 5.5 Backend & Web System Experiments *(→ Need 5, §2.6; Need 6, §2.7)*

> *These experiments validate the orchestrator and web interfaces as infrastructure that
> supports the AI agent, not as independent web-engineering contributions.*

#### 5.5.1 API Responsiveness & WebSocket Propagation

- **Goal:** validate that the FastAPI + SQLite + WebSocket design meets the real-time
  requirement — the claim in §4.7 that push replaces polling.
- **Methodology:** exercise all REST endpoints under concurrent table load; measure event
  propagation by stamping `sent_at` server-side and `received_at` at a subscribed client,
  N = 50 events per type.
- **Metrics:** per-endpoint latency p50/p95/p99, per-event-type propagation latency, SQLite
  read/write latency. Compare against the 5–10 s poll cycle of KDS systems surveyed in §2.6.4.

#### 5.5.2 Multi-Table Concurrency & Session Isolation

- **Goal:** validate that simultaneous conversations at different tables do not bleed into one
  another — the correctness property that makes per-table state trustworthy.
- **Methodology:** 2–3 concurrent voice sessions at different tables, ordering overlapping
  dishes.
- **Metrics:** session isolation accuracy, per-table cart correctness, cross-session leakage
  count (which must be zero, reported as a count, not a rate).

#### 5.5.3 Fleet Management & Fault Recovery

- **Goal:** validate dispatcher assignment, watchdog liveness detection, and dynamic voice
  binding — including the failure path (§2.6.3).
- **Methodology:** simulate robot connect, arrival, disconnect and silent-zombie conditions;
  verify task requeue, WebSocket close, and voice rebinding.
- **Metrics:** task assignment latency, watchdog detection time, task requeue latency, voice
  rebind correctness, and whether a customer-visible interruption occurs.

#### 5.5.4 Multi-Role State Consistency

- **Goal:** validate that all three SPAs reflect a single source of truth when the AI agent —
  not a human operator — is the one changing state.
- **Methodology:** drive an agent-initiated change (cart update, order created, robot
  dispatched) and verify each role's view converges to the backend state.
- **Metrics:** cross-role data consistency, WebSocket event → visible UI update latency,
  reconnect success and recovery time under forced disconnection.

---

### 5.6 Results Summary

#### 5.6.1 Objective Scorecard

Each measurable target from §1.3 against its measured result, with the experiment that produced
it and an explicit verdict. Targets that were not met, and targets that could not be measured,
appear with the same prominence as those that were.

| # | Objective (§1.3) | Target | Experiment | Result | Verdict |
|---|-----------------|--------|-----------|--------|---------|
| 1 | EKF-fused odometry error | ≤ X cm | §5.3.1 | | |
| 2 | Navigation success rate | ≥ X% | §5.3.3 | | |
| 3 | ArUco docking error | < X cm / X° | §5.3.3 | | |
| 4 | Intent router accuracy | ≥ 90% | §5.4.1 | | |
| 5 | Retrieval quality | [set target] | §5.4.4 | | |
| 6 | E2E ordering completion | [set target] | §5.4.5 | | |
| 7 | Voice turn latency | < 5 s | §5.4.6 | | |
| 8 | Validator off-menu leak rate | 0% | §5.4.2 | | |

#### 5.6.2 Failure Budget Allocation

Every failure observed across all experiments, categorised by root cause and attributed to a
component. Identifies the system's weakest link for §6.3.

| Failure Category | Count | % of Total | Component (§4.x) |
|-----------------|-------|-----------|------------------|
| Router misclassification | | | Intent classifier (§4.5.2) |
| Worker tool-call error | | | Tool-calling worker (§4.5.3) |
| Validator false positive | | | Validator (§4.5.4) |
| Response verbalisation error | | | Response generation (§4.5.6) |
| Retrieval miss | | | Knowledge retrieval (§4.6) |
| Backend / infrastructure | | | Orchestrator (§4.7) |

#### 5.6.3 Need → Requirement → Experiment Traceability

| Need (§2) | Requirement | Experiment | Key Result |
|-----------|-------------|------------|------------|
| 2.2 Dynamic navigation | §3.1 R(odometry, nav, docking) | §5.3.1–§5.3.4 | |
| 2.4 Informal speech → action | §4.1 R(classification, validation, agent) | §5.4.1–§5.4.5 | |
| 2.5 Sensory → relevant items | §4.1 R(retrieval) | §5.4.4 | |
| 2.6 AI-driven operations | §4.1 R(concurrency, fleet) | §5.5.1–§5.5.3 | |
| 2.7 Multi-role interfaces | §4.1 R(web) | §5.5.4 | |

#### 5.6.4 Threats to Validity

- **Typed text vs. speech.** Every experiment in §5.4 feeds the agent clean text. The voice
  pipeline (§4.4) is described architecturally with component selection justified against the
  Chapter 2 survey, but it has not been evaluated experimentally — STT word error rate, VAD
  boundary accuracy, barge-in effectiveness, and the speech-to-decision cascade remain
  unmeasured. Results in §5.4 are upper bounds on what a customer speaking through the
  deployed voice pipeline would experience.
- **Self-authored evaluation data.** The datasets were written by the author against one
  restaurant's menu. They are not an independent benchmark, and dish-name familiarity may
  flatter both retrieval and name resolution.
- **Sample sizes.** Several comparisons are underpowered; where a difference does not reach
  significance, the chapter says so rather than reporting the point estimate as a finding.
- **Stochastic components.** Any result from a single run of an LLM-dependent arm is one draw
  from a distribution; §5.2.3's N = 5 protocol applies, and any result not yet meeting it is
  marked as such.
- **Single deployment.** One restaurant, one menu, one robot, one network. Nothing here
  establishes behaviour at multi-restaurant or multi-robot scale.

---

## CHAPTER 6: CONCLUSION AND FUTURE WORKS

> **Chapter requirements — this chapter answers:**
> - What was achieved? Tick each §1.3 objective against Ch.5 results. (6.1 Conclusion)
> - What are the known limitations of the current system? (6.2 Limitations)
> - What should be done next? (6.3 Future Works)

### 6.1 Conclusion

- Tick each §1.3 objective against Ch.5 numbers
- Summarize both contribution legs:
  - Autonomous TWD navigation + EKF-fused odometry + RTAB-Map + Nav2 + ArUco docking
  - Trained MLP intent classifier + agentic LangGraph workflow (multi-intent queue, tool execution, deterministic validator) + closed-loop RAG (rewrite→retrieve→rephrase for Vietnamese menus) + voice pipeline + 3 web UIs

### 6.2 Limitations

- Consumer-grade IMU (MPU6050) → yaw drift, no magnetometer
- Wheel slip on smooth floors
- ArUco docking: lighting sensitivity (D435), no final-approach controller implemented
- Router: SEARCH accuracy 80% (on 100-case balanced set); delivery query confusion with PAYMENT; teencode-heavy utterances degrade embedding quality; ORDER_CONFIRM critical error on "Ghi nhận đơn hàng của tôi" (→PAYMENT at conf=1.00)
- Voice pipeline: STT, VAD and TTS components are selected and described architecturally (§4.4) but not evaluated experimentally — WER, VAD boundary accuracy, barge-in, and speech-to-decision cascade remain unmeasured
- E2E: backend dependency failures inflate error rates; chitchat→order transitions fragile
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
- Voice pipeline evaluation: measure STT WER/CER, VAD accuracy under restaurant noise, and speech-to-decision cascade degradation with native Vietnamese speakers
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
