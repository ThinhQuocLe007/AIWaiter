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
        4.7.5 Voice Bridge
        4.7.6 Database Schema
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
| Whisper medium | Partial (multilingual) | Yes | Yes | ~800ms | ~1.5 GB | 15–20% |
| PhoWhisper (medium, faster-whisper) | Yes | Yes | Yes | ~800ms | ~1.5 GB | 10–15% |
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
- The gap is the *combination*: published work measures each subsystem in isolation, leaving the concurrent resident footprint on a unified-memory board uncharacterised. Answered by measurement in §5.4.4.

---

### 2.9 Summary: Needs → Requirements Traceability

- **The six needs, plus the edge platform, and what they demand of the proposed system:**

  | §   | Need | → Requirements | → Method | → Validated In |
  | --- | ---- | -------------- | -------- | -------------- |
  | 2.2 | Dynamic goal navigation — navigation targets assigned by AI agent, not pre-set, with ArUco business-context docking | §3.1 R1–R7 (navigation, docking, odometry) | §3.4–§3.7 (EKF, RTAB-Map, ArUco, Nav2 + dynamic goal coupling) | §5.2.1–§5.2.3 |
  | 2.3 | Vietnamese voice on Jetson edge — component selection (VAD, STT, TTS) driven by restaurant deployment constraints | §4.1 NFR latency, §4.4 architecture | §4.4 (selected components: Silero VAD, PhoWhisper, Piper TTS; threaded pipeline, barge-in) | §5.4 |
  | 2.4 | Conversational AI agent — classifier handling teencode/context/multi-intent/domain-vocab + deterministic post-generation validation | §4.1 functional requirements, §4.5.1–§4.5.7 (agent architecture) | §4.5.2 (MLP classifier with embedding from §2.5.2), §4.5.3 (tool-calling LLM — Qwen2.5 7B, surveyed §2.4.2), §4.5.4 (validator) | §5.3.1–§5.3.3 |
  | 2.5 | Menu knowledge retrieval — closed-loop rewrite→retrieve→rephrase for Vietnamese food domain, driven by Vietnamese-specific embeddings (§2.5.2) | §4.1 menu search requirement, §4.6 | §4.6 (query rewriting, hybrid retrieval with embeddings from §2.5.2, result rephrasing, dedup) | §5.3.4 |
  | 2.6 | AI-driven restaurant operations — lightweight fleet dispatch with voice binding, multi-role real-time sync, session lifecycle | §4.1 concurrency/multi-role requirement, §4.7 | §4.7 (REST + WS hub, fleet dispatcher, session lifecycle) | §5.5, §5.6 |
  | 2.7 | Multi-role web interfaces — AI-driven Vue SPA architecture with shared TS client, role-based WS pub/sub, SSE streaming | §4.1 multi-role UI requirement, §4.8 | §4.8 (3 SPAs + shared client lib + WS event catalog) | §5.6 |
  | 2.8 | Edge computing platform — accelerator class satisfying general-purpose programmability, decode bandwidth, and native fp16; 8 GB unified-memory ceiling determining the edge/server split | §3.3 (robot hardware), §4.4.1 (edge/server split) | §4.4.1 (memory budget analysis leading to edge/server architecture) | §5.4.4 |

- **The integration gap:** each need has been addressed individually in prior work — autonomous navigation (ROS2 delivery robots), Vietnamese speech (standalone STT/TTS/VAD), edge computing (Jetson deployments), conversational agents (cloud chatbots), intent classification (NLU pipelines), menu retrieval (academic RAG), fleet management (warehouse frameworks), restaurant software (POS/KDS), and SPA web interfaces (Vue/React dashboards). No prior system has integrated all into a single deployed system where the AI agent directly drives physical delivery and real-time UI state across all roles.

---

## CHAPTER 3: PROPOSED METHOD (I) — ROBOT CONTROL AND NAVIGATION

> **Chapter requirements — this chapter answers:**
> - What must the navigation system achieve? (3.1 Requirements — derived from Ch.2 Need 1 gap)
> - What challenges make this hard? (3.2 Design Challenges C1–C4)
> - What hardware are we working with? (3.3 Platform & Hardware)
> - Per challenge: what method did we design or apply, and how does it address the challenge? (3.4–3.7)https://gemini.google.com/app/ca07af383ceb129c
> - For off-the-shelf components used in navigation (RTAB-Map, Nav2, robot_localization EKF, ArUco): they were surveyed in Ch.2; this chapter describes how they are configured, integrated, and adapted for the restaurant domain.
> - For components we designed (dynamic goal coupling, business-context ArUco docking): this chapter presents the design and its rationale.

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

> **Chapter requirements — this chapter answers:**
> - What must the software system achieve? (4.1 Requirements — derived from Ch.2 Needs 2–6)
> - What challenges make this hard? (4.2 Design Challenges C5–C10)
> - What is the overall architecture, and why these design decisions? (4.3)
> - For each subsystem: based on the Ch.2 survey, what did we SELECT (off-the-shelf) or DESIGN (new)?
>   - If selected from a Ch.2 comparison table: state what was selected and the selection rationale against our requirements.
>   - If designed new: reference the Ch.2 research gap, present the proposed method, explain how it addresses its challenge.
> - How do all subsystems fit together in deployment? (4.9)

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

> *This section establishes the high-level architecture of the AI Waiter system: the hybrid edge/server topology, the design rationale for splitting perception from intelligence, the component responsibility map, the four primary data flows that constitute restaurant operation, the communication protocols between tiers, and the key architectural decisions. Each decision is traced back to the design challenge (C5–C10) it addresses.*

#### 4.3.1 Hybrid Architecture — Perception on Edge, Intelligence on Server

> *The system is not a monolithic application. It is a distributed system with a deliberate split: voice perception and robot motion run on the Jetson edge computer physically attached to the robot; LLM reasoning, agent orchestration, and business state run on a central x86 server with a dedicated GPU. This subsection explains what runs where and why the split was necessary.*

- **The two-machine topology.** Two physical computers, one network (local WiFi):
  - **Jetson Orin Nano (the body):** carries the microphone, speaker, LiDAR, camera, and motors. Runs the voice pipeline (VAD → STT → TTS) and ROS2 navigation (Nav2 + RTAB-Map + EKF). Does NOT run the LLM — it physically cannot fit.
  - **x86 Server with NVIDIA GPU (the brain):** runs Ollama serving Qwen2.5 7B, the LangGraph agent brain, the FastAPI orchestrator backend, two SQLite databases (business ledger + conversation memory), and the FAISS+BM25 hybrid retrieval index.

- **Why the split exists — the VRAM math.** The Jetson has 8 GB unified memory shared among all processes. ROS2 navigation (~500 MB) + sensor drivers (~200 MB) + voice pipeline STT model at float16 (~1.5 GB) + TTS model (~200 MB) already consumes ~2.5 GB. The LLM at float16 requires 6–8 GB. Co-locating the LLM would total ~9–10 GB — exceeding the Jetson's capacity. 4-bit quantization could reduce the LLM to ~4 GB but degrades Vietnamese output quality (tonal diacritics are the first to go under aggressive quantization). The solution is architectural, not compression-based: move the LLM to hardware with sufficient VRAM.

- **Why not put everything on the server?** Because the microphone and speaker are physically on the robot — putting STT and TTS on the server would mean streaming raw 16 kHz audio (~100 KB per utterance) over WiFi each turn, adding network latency and making the voice pipeline dependent on WiFi stability. Running STT locally on the Jetson means the audio never leaves the robot — only the text transcript (~100 bytes) travels over the network. And if WiFi drops, voice capture + transcription complete locally; the text payload waits for reconnection.

- **The split in terms of data volume.** The edge processes heavy data (audio, LiDAR scans, camera frames) and sends only lightweight structured outputs to the server (text transcripts, robot pose coordinates). The server processes lightweight inputs but heavy computation (LLM inference over 7B parameters, database transactions, WebSocket fan-out). This asymmetry — heavy sensing on the edge, heavy reasoning on the server — is the defining characteristic of the architecture.

- **Protocol.** The Jetson maintains two persistent WebSocket connections to the server: `role=voice-device` (receives microphone gating commands: start/cancel listening) and `role=robot` (receives Nav2 goal assignments, sends pose/battery heartbeats). The voice pipeline also makes HTTP POST calls to the agent brain for STT transcript submission. Both connections share one `robot_id`, matching the physical robot identity at the orchestrator.

#### 4.3.2 Client Tier — Roles and Responsibilities

> *In addition to the two-machine compute split, the system serves three browser-based interfaces on the staff network, each with a distinct operational role. They share a common TypeScript library for REST and WebSocket communication.*

- **Customer tablet** (`:5173`, `role=customer` via WebSocket). Runs on the 7-inch touchscreen at each table. Functions: menu browsing with 12 Vietnamese seafood categories, voice conversation mirror (see what the agent heard/said), cart synchronization (voice-ordered items appear in the visual cart), and VietQR mock payment screen. WebSocket events are filtered by `table_id` — each tablet sees only its own table's conversation.
- **Kiosk** (`:5174`, REST only). Runs on a tablet at the restaurant entrance. Single-component Vue 3 SPA: table grid with real-time status, party size selector, one-button check-in. The seating action cascades through the orchestrator: marks table occupied, creates an active session, dispatches a robot to guide the party to the table.
- **Management panel** (`:5175`, `role=panel` via WebSocket). Runs in the kitchen and manager's office. Four-component dashboard: Kitchen Kanban (three-column order board: Chờ Bếp → Đang Làm → Xong, forward-advance buttons), Fleet Board (per-robot status cards with battery, activity, last-seen time), Table Overview (per-table status with live session timers), and Minimap (SLAM floor plan overlay with live robot pose dots at 5 Hz).

#### 4.3.3 Component Responsibility Map

> *A complete inventory of what runs where, what each component is responsible for, and how components communicate. This table is the single point of reference for the architecture — every connection, protocol, and direction is specified.*

| Component | Machine | Port/Protocol | Responsibility | Talks To (→ direction) |
|-----------|---------|---------------|----------------|------------------------|
| **Agent Brain** (LangGraph) | Server | 8100 / HTTP | Converts Vietnamese utterances into validated actions. 10-node graph: classifier router → 4 workers → validator → tools → state updater → state outcome → response generator. | → Ollama (LLM inference, localhost :11434) |
| | | | | ← Voice device (receives POST /chat with transcript) |
| | | | | → Orchestrator (POST /orders, /payments for tool execution) |
| | | | | → Orchestrator (POST /voice/event for tablet mirroring) |
| **Orchestrator** (FastAPI) | Server | 8000 / HTTP + WS | Central business state: REST API (20 endpoints, 10 routers), WebSocket hub (4 role-based channels), fleet dispatcher (task assignment and watchdog), session lifecycle manager, voice bridge (agent↔tablet↔robot relay). Manages two SQLite databases. | ← Agent (REST calls for orders, payments) |
| | | | | →↔ Web clients (REST + WebSocket push) |
| | | | | →↔ Robot (WebSocket: task assignment →, telemetry ←) |
| | | | | → Voice device (WebSocket: start/cancel listening) |
| **Ollama** | Server | 11434 / HTTP | Serves Qwen2.5 7B Instruct with three logical endpoints (router T=0.0, worker T=0.1, response T=0.3) sharing one loaded model. `keep_alive=-1` pins the model in GPU VRAM permanently. | ← Agent (LLM inference requests) |
| **RAG Indices** | Server | In-process | FAISS dense index (768-dim, 217 dishes, Vietnamese bi-encoder embeddings) + BM25 sparse index (tokenized via `underthesea`, compound-word-aware). Fused via RRF (k=60). | ← Agent (search tool calls) |
| **Voice Pipeline** | Jetson | Client (connects out) | VAD (Silero, CPU, ~2 MB) → STT (faster-whisper medium, PhoWhisper weights, GPU, ~1.5 GB) → TTS (Piper, CPU, ~200 MB; edge-tts fallback). Threaded: VAD thread → speech_queue → STT thread → text_queue → main loop. | ← Orchestrator (WS: start/cancel listening commands) |
| | | | | → Agent (HTTP POST /chat with transcript) |
| | | | | → Orchestrator (WS: receives TTS text via voice.reply flow) |
| **ROS2 Navigation** | Jetson | In-process (ROS2) | EKF-fused odometry, RTAB-Map localization, Nav2 path planning + DWB control, ArUco marker detection. Covered in Chapter 3. | →↔ Orchestrator (WS: receives task.assign goals, sends task status + heartbeats) |
| **Customer Tablet** | Browser | :5173 (dev) | Menu, voice mirror, cart sync, payment. `role=customer` WebSocket, filtered by table_id. | → Orchestrator (REST for orders, cart; POST /voice/listen) |
| | | | | ← Orchestrator (WS: voice.heard, voice.reply, table.updated) |
| **Kiosk** | Browser | :5174 (dev) | Table grid, party size selector, one-button check-in. REST only. | → Orchestrator (POST /seatings) |
| **Panel** | Browser | :5175 (dev) | Kitchen Kanban, fleet board, table overview, minimap. `role=panel` WebSocket. | ← Orchestrator (WS: order.created/updated, table.updated, robot.updated, task events) |
| | | | | → Orchestrator (REST: PATCH orders, PATCH tables, POST /admin/reset) |

#### 4.3.4 Primary Data Flows

> *The system executes four end-to-end data flows, each spanning multiple components and protocols. These flows are the operational backbone of the restaurant — every customer interaction, kitchen action, and robot movement traces one of these paths. Each flow is documented as a numbered sequence of steps with the responsible component, the action it takes, and the protocol used.*

##### Flow (a) — Voice Ordering at Table

> *This is the core customer interaction loop. A guest speaks Vietnamese; the system transcribes, understands, executes, validates, and responds — in spoken Vietnamese — with the tablet mirroring every step. Total duration from end-of-speech to start-of-reply: under 5 seconds.*

| Step | Component | Action | Protocol |
|------|-----------|--------|----------|
| 1 | Customer Tablet | Guest presses "Talk to AI" → POST `/voice/listen {table_id}` | HTTP REST |
| 2 | Orchestrator | Voice bridge resolves `table_id → robot_id` via dynamic binding | In-process |
| 3 | Orchestrator | Sends `start_listening` to bound robot's `voice-device` WebSocket | WebSocket |
| 4 | Jetson VAD | Silero VAD arms microphone, captures one utterance (1.5s silence timeout) | In-process (PyAudio) |
| 5 | Jetson STT | faster-whisper medium transcribes audio → Vietnamese text (~800ms) | In-process (CTranslate2) |
| 6 | Jetson Main | POSTs transcript to Agent Brain `/chat/stream {table_id, text}` | HTTP REST |
| 7 | Agent | POSTs `voice.heard` to Orchestrator → tablet shows "thinking..." + transcript | HTTP REST → WS |
| 8a | Agent Router | MLP classifier (768-dim embedding + 10 context features → 4-class, 0.17ms) | In-process |
| 8b | Agent Worker | LLM (Qwen2.5 7B, T=0.1, tool_choice="any") selects tool + arguments | Ollama HTTP |
| 8c | Agent Validator | Deterministic: resolves dish names against 217-item menu, checks state machine | In-process |
| 8d | Agent Tools | Executes tool (cart CRUD in-memory, or HTTP to orchestrator for orders/payment) | In-process / HTTP |
| 8e | Agent State | Merges results into AgentState, advances cart state machine, handles multi-intent queue | In-process |
| 9 | Agent Response | Generates Vietnamese spoken reply (templates for deterministic outcomes, LLM for search/chat) | In-process / Ollama |
| 10 | Agent | POSTs `voice.reply` (text, UI action, cart state, order confirmation) to Orchestrator | HTTP REST |
| 11 | Orchestrator | Fans `voice.reply` to all `role=customer` WebSocket clients (tablet filters by table_id) | WebSocket |
| 12 | Tablet | Displays AI response text bubble, syncs cart (`syncFromVoice`), executes UI action if set | In-process (Vue) |
| 13 | Jetson TTS | Receives response text via SSE stream → Piper TTS plays sentence-by-sentence through speaker | In-process (Piper/edge-tts) |

Key properties of this flow:
- **Offline-capable at every step.** VAD+STT complete locally on Jetson (no network). TTS completes locally (Piper, no network). Only the LLM call (step 8b) requires the server. A WiFi drop between steps 6-8 leaves the transcript buffered; a Wi-Fi drop during TTS playback leaves the speaker silent but doesn't crash.
- **Validation gates the LLM.** Step 8c runs after the LLM proposes (8b) but before tools execute (8d). A hallucinated dish name never reaches the cart or backend.
- **The tablet mirrors, not drives.** The tablet does not touch the microphone. It is a display and signal device — it shows what the agent heard/said and syncs the visual cart from voice state. The microphone lives on the robot, controlled by the orchestrator.

##### Flow (b) — Order to Kitchen Display

> *When the agent confirms an order, the kitchen must know immediately — not on the next page refresh.*

| Step | Component | Action | Protocol |
|------|-----------|--------|----------|
| 1 | Agent | `confirm_order` tool calls orchestrator POST `/orders` with serialized cart | HTTP REST |
| 2 | Orchestrator | Inserts order + order_items into SQLite, status `CHO_BEP` | SQLite (WAL) |
| 3 | Orchestrator | Emits `order.created` to all `role=panel` WebSocket connections | WebSocket |
| 4 | Panel (KitchenBoard) | New order card appears in "Chờ Bếp" column with items, quantities, table name, elapsed timer | In-process (Vue) |
| 5 | Kitchen Staff | Advances status: "Bắt đầu làm" → `PATCH /orders/{id} {status: DANG_LAM}` | HTTP REST |
| 6 | Orchestrator | Emits `order.updated` → panel card moves to "Đang Làm" column | WebSocket |
| 7 | Kitchen Staff | Marks complete: "Món xong ✓" → `PATCH /orders/{id} {status: XONG}` | HTTP REST |
| 8 | Orchestrator | Emits `order.updated` → card moves to "Xong" column. **Creates `deliver` task** (triggers Flow d) | WebSocket + in-process |

##### Flow (c) — Manager Monitoring (Fleet + Tables)

> *The management panel maintains a live view of the restaurant floor — robot positions, table statuses, task progress — updated in real time without polling.*

| Step | Component | Action | Frequency |
|------|-----------|--------|-----------|
| 1 | Robot (ROS2) | Sends `heartbeat` over WebSocket: `{robot_id, x, y, battery, status}` | 4+ Hz |
| 2 | Orchestrator (fleet.py) | Updates RAM-only dict with latest pose + battery (lock-protected, no DB write) | Per heartbeat |
| 3 | Orchestrator | Throttled broadcast: emits `robot.updated` to panel WebSocket | Max 5 Hz per robot |
| 4 | Panel (MiniMap) | Renders robot pose dot on SLAM map overlay at live (x, y) coordinates | On event |
| 5 | Panel (FleetBoard) | Updates robot card: status badge, activity label, battery percentage with color coding | On event |
| 6 | Orchestrator | Periodic DB snapshot: writes current pose + battery to `robots` table for cold-start recovery | Every 15s |
| — | Panel (TableOverview) | Receives `table.updated` events: seating, order confirmation, payment | On business event |
| — | Panel (FleetBoard) | Receives `task.created` / `task.updated` events: dispatcher task lifecycle | On business event |

**Why RAM telemetry, not database writes.** Writing 4+ Hz per robot to SQLite would create file-level write contention — a heartbeat write could delay a payment transaction. The RAM store (`fleet.py`, ~60 lines, thread-safe dict) absorbs sensor-frequency updates with zero I/O. The 15-second periodic snapshot provides cold-start recovery (after orchestrator restart) without competing with business transactions.

##### Flow (d) — Business Events to Robot Navigation Goals

> *The dispatcher translates three business events — a party is seated, food is ready, a guest presses the call button — into robot navigation tasks. The robot receives a Nav2 goal pose; the dispatcher manages the task lifecycle.*

| Step | Triggering Business Event | Dispatcher Action | Robot Action |
|------|--------------------------|-------------------|--------------|
| 1 | Kiosk seating → `POST /seatings` | Creates `go_to_table` task (PENDING), calls `try_assign()` | — |
| 2 | Order status → `XONG` (kitchen marks done) | Creates `deliver` task (PENDING), calls `try_assign()` | — |
| 3 | Guest presses "Gọi Robot" → `POST /tables/{id}/call` | Creates `call` task (PENDING), calls `try_assign()` | — |

`try_assign()` logic (runs on every task creation and robot state change):
1. Query all PENDING tasks, ordered by `created_at` (FIFO).
2. For each task, score all eligible robots: `status = idle` AND WebSocket alive AND battery ≥ 20%. Score = Euclidean distance from robot's live pose (RAM) to target table's waypoint.
3. Select nearest robot. In a SQLite transaction: mark task `ASSIGNED`, mark robot `busy`, set `activity` label.
4. Send `task.assign {task_id, kind, table_id}` to the robot's WebSocket.
5. Robot responds: `task_accepted` → `IN_PROGRESS`, begins Nav2 navigation to goal.
6. Robot arrives: sends `arrived` → dispatcher binds `table_id → robot_id` in voice bridge → tablet "Talk to AI" now routes to this robot's microphone.
7. Task completes: robot sends `task_done` → dispatcher marks `DONE`, frees robot (`idle`), clears voice binding, calls `try_assign()` for next queued task.

**Fault recovery.** The watchdog scans every 5 seconds: any robot with no heartbeat for >30s is marked offline, its current task is requeued to PENDING, its voice binding is cleared, and its zombie WebSocket is force-closed. If the orchestrator restarts: PENDING tasks survive in the database, robots reconnect as idle, periodic pose snapshots provide last-known positions, and `try_assign()` resumes.

#### 4.3.5 Communication Protocol Summary

> *Why each protocol was chosen for each communication path, with latency and reliability rationale.*

| Communication Path | Protocol | Why This Protocol |
|-------------------|----------|-------------------|
| Agent → Ollama | HTTP (localhost) | Ollama's native protocol. Same-machine, negligible latency (~1ms). One process, multiple logical model instances sharing one loaded model. |
| Agent → Orchestrator | HTTP (localhost) | Synchronous request/response for tool execution (create order, request payment). Fire-and-forget for voice event mirroring. Separate processes (ports 8100 vs 8000) prevent LLM inference from blocking WebSocket event delivery. |
| Orchestrator → Web Clients | WebSocket (push) | Real-time state changes (order created, table updated, robot moved) must reach all clients in <50ms. Polling at 1 Hz generates hundreds of requests/minute, most returning unchanged data. WebSocket push: clients receive events only when state changes. |
| Orchestrator → Robot | WebSocket (bidirectional) | Task assignment requires server-to-robot push (the robot doesn't poll for tasks). Telemetry requires robot-to-server push (the server doesn't poll robot sensors). Bidirectional WebSocket satisfies both with one persistent connection. |
| Robot → Agent | HTTP (POST) | The voice transcript is a request/response pattern: send text, receive text. WebSocket would add framing overhead for what is inherently RPC. HTTP is simpler, stateless, and the agent brain doesn't need to maintain a persistent connection to every robot. |
| Frontends → Orchestrator | HTTP (REST) | CRUD operations (seat a table, advance order status, fetch menu) are inherently request/response. REST with standard HTTP verbs and status codes maps cleanly to these operations. JSON payloads validated via Pydantic (backend) and TypeScript interfaces (frontend). |

#### 4.3.6 Design Rationale — How the Architecture Addresses Each Challenge

> *Each architectural decision is traced to the design challenge (C5–C10 from §4.2) it resolves. This table is the architecture's thesis statement: given these challenges, here is why the system is structured as it is.*

| Challenge | Architectural Response | Where Detailed |
|-----------|----------------------|----------------|
| **C5 — Vietnamese informality** | MLP classifier with context features: frozen Vietnamese bi-encoder embedding (768-dim) + 10 conversation state features → 778-dim input → 3-layer MLP → 0.17ms → deterministic 4-class output. Handles teencode, context-dependent ambiguity, multi-intent, domain vocabulary — properties prior approaches trade against each other. | §4.5.2 |
| **C6 — VRAM is zero-sum on the edge** | Edge/server split: microphone + speaker on Jetson (voice pipeline within 2.5 GB budget), LLM on server GPU (Qwen2.5 7B within 8 GB VRAM). Audio stays local — only text transcripts cross the network. | §4.3.1, §4.4.2 |
| **C7 — Probabilistic LLM in a deterministic system** | Deterministic validator between every LLM call and tool execution: 5-level menu name resolution, off-menu detection, state consistency checks, circuit breaker (max 3 retries). Safety invariant: LLM → validate → action, never LLM → action. | §4.5.4 |
| **C8 — Sensory queries don't match menu structure** | Closed-loop RAG: LLM rewrites vague query into concrete search terms → BM25+FAISS hybrid retrieval with RRF fusion → LLM evaluates and rephrases results in natural Vietnamese. "Ấm bụng" → "lẩu, súp, cháo, món nước nóng" → menu search → conversational reply. | §4.6 |
| **C9 — Backend is a state machine the AI drives** | Single FastAPI + SQLite process: WAL mode for concurrent reads, RAM telemetry to avoid write contention, role-based WebSocket fan-out (not polling), session lifecycle enforced with guarded state transitions. | §4.7 |
| **C10 — Robot-table voice binding must survive disconnection** | Dynamic bind/unbind on robot arrival/departure, watchdog (30s heartbeat timeout), automatic task requeue and voice rebind on disconnection. The customer never knows which robot is listening — the system abstracts over individual robots. | §4.7.4 |

---

### 4.4 Edge Voice Pipeline *(→ Need 2, §2.3)*

> *Selects the STT, VAD, and TTS components from the comparison tables surveyed in §2.3, and presents the threaded pipeline architecture that integrates them. The Vietnamese-specific constraints that drove these selections — tonal diacritics, compound words, teencode, restaurant noise — are stated as design context below. These were not surveyed in Ch.2 (which surveys technology, not domain-specific challenges) and are presented here as the constraints the selected components must satisfy.*

#### 4.4.1 Vietnamese Voice Constraints (Design Context)

The following constraints are inherent to Vietnamese restaurant speech processing and are not properties of any specific technology — they are the conditions under which the selected components must operate:

- **Tonal diacritics.** Vietnamese has six tones carried by diacritic marks. The words "cá" (fish), "cà" (eggplant), "cả" (all), and "cạ" (to rub) differ only in tone. An STT model that correctly identifies segmental phonemes but misclassifies the tone produces a different dish name — ordering "cá kho tộ" vs. "cà kho tộ" is braised fish vs. braised eggplant.
- **Monosyllabic structure with compound words.** "Bún bò Huế" is three syllables but one lexical unit (a specific noodle soup). STT models must recognize these as compounds, not as independent syllables.
- **Teencode and informal speech.** Casual Vietnamese uses abbreviations absent from formal STT training corpora: "ad" (anh/chị), "ck" (chuyển khoản), "z" (vậy), "nhiêu" (bao nhiêu), "hông" (không). These are standard spoken Vietnamese in informal contexts, not errors.
- **Restaurant ambient noise.** Concurrent conversations, kitchen sounds, plate and utensil contact produce sustained broadband noise at 60–70 dB. STT accuracy degrades in noise; VAD must discriminate speech from this noise profile without excessive false triggers.
- **STT as the pipeline break-point.** A transcription error propagates through every downstream component — classifier, LLM, validator, response generator — all operate on corrupted input. No downstream intelligence can fully recover from an STT error that changes a dish name.

#### 4.4.2 Edge/Server Split Rationale

- Addressing C6 (VRAM budget): microphone and speaker on Jetson → STT and TTS models are GPU-light (~1.5 GB + 200 MB) → run on Jetson's CUDA cores. LLM (Qwen2.5 7B, ~6–8 GB) runs on server GPU.
- Local STT avoids network round-trip latency for audio upload. Text transcript (~100 bytes) is a negligible payload compared to raw audio (~100 KB).
- Protocol: Jetson connects to orchestrator WebSocket as `role=voice-device`. The tablet→voice flow: Customer presses "Talk to AI" → `POST /voice/listen` → orchestrator WS forwards `start_listening` to bound voice device → Jetson arms microphone. After agent produces text output → `POST /voice/event` → orchestrator WS mirrors to tablet.

#### 4.4.3 Component Selection from §2.3 Survey

- Based on the comparison tables in §2.3, the following components are selected for this system:
  - **VAD:** Silero VAD — language-agnostic, ~1.5 MB, CPU real-time, configurable sensitivity threshold. Selected over WebRTC (lower accuracy in noise) and GPU-based options (infeasible on edge).
  - **STT:** PhoWhisper medium via faster-whisper — Vietnamese fine-tuned Whisper with CTranslate2 8-bit quantization. Selected over cloud services (offline requirement) and base Whisper (lower tonal accuracy).
  - **TTS:** Piper TTS (primary, offline, Vietnamese VITS model) with edge-tts (Azure fallback for x86 development). Selected over cloud-only TTS services (offline requirement).

#### 4.4.4 Threaded Pipeline Architecture

- **VAD thread:** captures microphone in 512-sample chunks, resamples to 16 kHz. Silero VAD classifies each frame as speech/silence. Configurable sensitivity threshold tuned for restaurant noise. Gate-controlled: only active between `start_listening` and utterance completion.
- **STT thread:** receives complete utterance audio via `speech_queue`. Runs faster-whisper medium with `language=vi`, `beam_size=5`. PhoWhisper weights for improved tonal accuracy. Output transcript → `text_queue`.
- **Main loop:** pops transcript → HTTP POST to agent brain `/chat` → receives response JSON → dispatches to TTS → signals ready for next utterance.
- **Single-utterance mode:** pipeline captures exactly one utterance per `start_listening`, then auto-idles. Prevents continuous eavesdropping.

#### 4.4.5 Barge-In Mechanism

- TTS playback is sentence-by-sentence (aligned with agent SSE output).
- During TTS playback, VAD thread runs concurrently in monitoring mode.
- If VAD detects new speech → playback interrupted mid-sentence → new utterance captured and processed.
- Enables natural turn-taking — customer can interrupt to correct an order.

#### 4.4.6 TTS Strategy

- **Primary:** Piper TTS (local, Vietnamese voice, CPU, ~500ms/sentence). Offline on Jetson.
- **Fallback:** edge-tts (Azure Vietnamese Neural voices). Used when Piper unavailable or on x86 dev machines.
- Selection: attempt Piper first → health check → fall back to edge-tts.
- **Per-stage voice modulation:** the TTS playback rate and pitch are adjusted based on conversation context — rate +10% during cart drafting (energetic confirmation), rate −5% during order confirmation (deliberate, careful), and pitch +2 Hz after payment completion (warm closing). These modulations provide non-verbal cues that reinforce the conversational stage without the agent stating transitions explicitly.

---

### 4.5 Conversational AI Agent *(→ §2.4)*

> *The intellectual core of the software contribution. How the agent converts informal Vietnamese utterances into deterministic, validated actions — addressing C5 (Vietnamese informality) and C7 (probabilistic LLM in a deterministic system). Every utterance flows through five stages: Understanding → Decision → Validation → Execution → Response. The graph topology enforces the restaurant ordering state machine (from §2.5.3 architecture gap).*

#### 4.5.1 Agent Execution Model

- **LangGraph StateGraph:** 10 nodes, 6 conditional edges, 4 normal edges. Entry at `router`, exit after `response_node`.
- **AgentState (18 fields, TypedDict):**
  - Conversation history: `messages` (across turns, append-only)
  - Task state: `table_id`, `active_cart`, `order_stage`, `search_context` (across turns)
  - Routing state: `current_intents`, `routing_meta` (intents queue for multi-intent iteration)
  - Inter-node contract: `is_valid`, `feedback`, `loop_count`, `unavailable_items`, `ambiguous_items`, `last_tool`, `delegate_reason`, `intent_queries` (per-turn)
   - Output: `ui_action`, `order_confirmed`, `response_context` (per-turn)
   - Anti-repetition: `shown_dishes` — dishes already recommended in prior search turns within this session; prevents redundant recommendations when the customer repeats a query
- **Graph execution flow:**
  ```
  START
    │
    ▼
  classifier_router
    │
    ├──→ order_worker ──→ validator ──(pass)──→ tools ──→ state_updater ──┐
    │        ↑ retry(feedback)          (≥3 fails)→ state_outcome          │
    │        └──────────────────────────────────────────────┘     more intents?
    │                                                             (loop to worker)
    │
    ├──→ search_worker ──→ validator ──(pass)──→ tools ──→ state_updater (same loop)
    │
    ├──→ payment_dispatch ──→ validator ──(pass)──→ tools ──→ state_updater
    │
    └──→ chat_worker ──→ state_outcome (bypasses validator + tools)

  state_updater ──(done)──→ state_outcome ──→ response_node ──→ END
  ```
- **Conversation memory:** compiled with LangGraph `SqliteSaver`. `thread_id = orchestrator_session_id`. Persistent fields survive across turns; ephemeral fields reset each turn in `state_outcome`.
- **How the graph addresses C5 (informality) and C7 (hallucination):** the router handles classification under informality (§4.5.2). The validator intercepts every tool call before execution (§4.5.4). The graph topology ensures correct function even when classification is imperfect — failed validation loops back with corrective feedback, and the circuit breaker guarantees termination.

#### 4.5.2 Stage I — Understanding: Intent Classification

> Addressing C5: Vietnamese informality. The embedding model used for the classifier's 768-dimensional input is the same `bkai-foundation-models/vietnamese-bi-encoder` surveyed in §2.5.2.

- **Intent taxonomy:** {ORDER, SEARCH, PAYMENT, CHAT}. ORDER_CONFIRM merged at router level; distinction handled downstream by order state machine.
- **MLP classifier architecture (778-dim → 0.17ms → deterministic):**
  - **Embedding:** `bkai-foundation-models/vietnamese-bi-encoder` (768-dim, L2-normalized). Vietnamese-specific bi-encoder trained on Vietnamese sentence pairs (§2.5.2).
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
- **Grounding guard (`_ground_reply`):** for LLM-generated search responses, the output is verified post-generation against the actual retrieved dishes. If the LLM's response names dishes absent from the retrieval results, the response is replaced with a deterministic listing of the actual results. This prevents hallucinated recommendations — the agent cannot recommend a dish the retriever did not find.
- **Sentence sanitization (`_sanitize_sentence`):** Qwen2.5 occasionally produces CJK (Chinese/Japanese/Korean) contamination or residual markdown in Vietnamese output. A regex filter strips non-Vietnamese characters and markdown formatting before TTS playback, ensuring the spoken output is clean Vietnamese.

#### 4.5.7 Prompt Architecture

> *The system uses zero fine-tuning — all model adaptation is through prompting (§2.4.2 justifies this choice). The prompt architecture is a first-class design element.*

- **System prompts (7 files, all Vietnamese):** each LLM-calling node has its own prompt defining role, reasoning protocol, output format, constraints.
- **Few-shot examples:** static JSON loaded at boot, injected at runtime.
  - Order worker: 5 examples with tool calls for KV-cache optimization
  - Search worker: 5 examples with `search` + `delegate` calls
  - (Router prompt unused by MLP classifier — fallback path only)
- **Skill documents:** `hospitality.md` (Vietnamese restaurant service etiquette), `menu_grounding.md` (menu-as-ground-truth rules), `no_service_response.md` (domain boundary).
- **Dynamic context injection:** last 2 conversation turns into prompts for context awareness; "ĐÃ BIẾT" section for search deduplication; validator `feedback` into retry prompts.
- **Per-stage model configuration (all Qwen2.5 7B via Ollama, surveyed in §2.4.2):**

  | Stage | Model | Temperature | Key Configuration |
  |-------|-------|-------------|-------------------|
  | Router | MLP classifier (trained) | N/A (deterministic) | 778-dim: bi-encoder embedding + context features |
  | Worker (ORDER/SEARCH) | Qwen2.5 7B | 0.1 | `tool_choice="any"` — forced tool call |
  | Response | Qwen2.5 7B | 0.3 | Free-form generation — natural Vietnamese |

  All models: `keep_alive=-1` (pinned in VRAM). Warmup ping at agent startup.

---

### 4.6 Knowledge Retrieval Pipeline *(→ §2.5)*

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
- **Metadata post-filters before fusion:** price range, diet_type, and category filters are applied to raw BM25 and vector results independently before fusion, ensuring that out-of-constraint items never reach the final ranking. This avoids a common RAG failure mode where a top-ranked vector result (semantically strong but filtered by metadata) crowds out relevant results in the fused ranking.
- **Empty-result handling:** when BM25 returns zero matches and no FAISS result exceeds the score threshold (0.3), the retriever returns empty. The search worker's `delegate` escape hatch then routes to the CHAT worker for a graceful "not found" response rather than forcing a hallucinated match.

#### 4.6.3 Result Rephrasing

- After retrieval, the LLM evaluates top-k results: which dishes match the original customer intent? Which are irrelevant?
- Selects and rephrases relevant results in natural Vietnamese: "Dạ, cho ngày lạnh quán có Lẩu Cá Tầm, Cháo Hải Sản, và Súp Cua ạ."
- Detects empty results → responds "Dạ, quán không có món đó ạ" — no hallucination from empty retrieval.

#### 4.6.4 Multi-Turn Search Context

- "ĐÃ BIẾT" section in search prompts: previously returned items + current cart items.
- Prevents redundant queries — if customer searches "Ốc Hương" twice, agent knows it already returned those results.
- Search context persists across turns in `AgentState.search_context`.

---

### 4.7 Backend Orchestrator & Real-Time Systems *(→ §2.6, §2.7)*

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

#### 4.7.5 Voice Bridge

> *The voice bridge is the architectural glue between the AI agent, the robot's physical microphone/speaker, and the customer tablet. It does not process audio — it routes commands and responses through the correct path based on the dynamic table-to-robot binding established on arrival.*

- **Agent → Tablet mirroring (`POST /voice/event`):** the agent sends structured voice events to the orchestrator — `voice.heard` (user's transcript + thinking indicator), `voice.reply` (AI text response + cart state + UI action), `voice.progress` (SSE streaming progress). The orchestrator fans these to all `role=customer` WebSocket connections, filtered by `table_id`. The tablet is a passive viewer — it displays what the agent heard and said, and mirrors the voice-driven cart state, but never controls the microphone.
- **Tablet → Robot microphone (`POST /voice/listen`):** when the customer presses "Talk to AI" on the tablet, the voice bridge resolves `table_id → robot_id` via the dynamic binding established at robot arrival (§4.7.4), then sends `start_listening` to the bound robot's `voice-device` WebSocket. This indirection allows any robot serving any table — the customer never specifies a robot.
- **Cancel and mute (`POST /voice/cancel`, `/voice/mute`):** mid-turn cancel immediately aborts microphone capture and TTS playback. Mute toggles speaker output without affecting the conversation — useful when the table is discussing among themselves.
- **Session reset (`POST /voice/new-chat`):** forwards to the agent's `/reset` endpoint, wiping the LangGraph checkpoint for the current session's `thread_id`. Cancels any in-flight turn to prevent stale transcript processing. The customer gets a clean slate without affecting the business session (orders and payments persist in the orchestrator database).
- **Cart synchronization (`POST /voice/cart`):** when the customer manually edits the cart via the tablet touch screen (adding/removing items by touch rather than voice), the voice bridge pushes the hand-edited cart to the agent's `/cart` endpoint, updating the LangGraph checkpoint so subsequent voice commands operate on the correct cart state.

#### 4.7.6 Database Schema

- SQLite, raw SQL via `sqlite3` (no ORM). WAL mode for concurrent reads during writes.
- 8 business tables: `tables`, `sessions`, `dishes`, `orders`, `order_items`, `robots`, `tasks`, `payments`
- Separate `checkpoints.db` for LangGraph conversation memory (managed by `SqliteSaver`)
- Schema evolution via `ALTER TABLE ADD COLUMN` with `PRAGMA table_info` for idempotent migrations
- ERD diagram

---

### 4.8 Web Interfaces *(→ §2.7)*

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

> **Chapter requirements — this chapter answers:**
> - How was evaluation conducted? (5.1: hardware setup, datasets, metrics definitions)
> - For each §1.3 objective and each Ch.2 need: what was tested, what were the results, do the results meet the target?
> - Per experiment: goal → dataset → methodology → metrics → results → analysis → ablation (where applicable)
> - What is the failure budget? Which component contributed the most failures? (5.7)
> - Do the aggregate results confirm the system design proposed in Ch.3–Ch.4? (5.7 traceability)

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

> **Chapter requirements — this chapter answers:**
> - What was achieved? Tick each §1.3 objective against Ch.5 results. (6.1 Conclusion)
> - What are the known limitations of the current system? (6.2 Limitations)
> - What should be done next? (6.3 Future Works)

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
