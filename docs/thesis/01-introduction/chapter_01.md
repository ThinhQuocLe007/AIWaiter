## CHAPTER 1: INTRODUCTION

> **Status:** draft v1
> **Cross-refs:** §2.1 (overview of existing restaurant automation), §3.1, §4.1 (system requirements), §5 (validation)
> **Figures needed:** Fig 1.1 — example commercial restaurant service robot for context (cite source)

---

### 1.1 Overview

Service robots have entered restaurants. Over the past decade, autonomous delivery platforms have been deployed commercially — robots that navigate from kitchen to table, carry food on multiple tray levels, and present dishes to customers. In parallel, artificial intelligence has advanced to a point where machines can understand spoken language, reason about user intent, and take actions on software systems. These two developments — physical delivery by autonomous robots and conversational intelligence by large language models — have so far progressed along separate trajectories.

The robot that delivers food does not talk to the customer. The system that understands spoken orders does not dispatch a robot to deliver them. A restaurant that wants both must operate two independent systems and bridge them manually. The result is that autonomous food delivery remains a narrow capability — moving objects between fixed points — while AI-powered conversation remains disembodied — producing text but unable to act on the physical world.

This thesis proposes an integrated system: an autonomous waiter robot that accepts spoken Vietnamese orders, processes them through a conversational AI agent, dispatches the order to the kitchen, and delivers the food to the correct table. The contribution spans four domains: autonomous robot navigation on a purchased two-wheel differential-drive platform, a Vietnamese voice processing pipeline deployed on edge hardware, an AI agent that converts informal Vietnamese speech into validated backend actions, and a real-time restaurant management system that synchronizes order state, kitchen display, and robot fleet movement across multiple client roles.

The project is organized around five specific problems that the literature has not fully solved: (i) navigating a robot to targets dynamically assigned by an external AI agent rather than pre-set waypoints, (ii) processing Vietnamese speech reliably on edge hardware co-located with robot control under real restaurant acoustic conditions, (iii) converting informal, teencode-heavy Vietnamese utterances into correct, validated tool calls without hallucination, (iv) bridging Vietnamese sensory food descriptions ("món gì ấm bụng?") to structured menu databases where dishes are indexed by name and category, and (v) coordinating AI-driven business events — orders, payments, robot tasks — across multiple client roles in real time. Chapter 2 surveys prior work on each problem and identifies the gaps. Chapters 3 and 4 present the proposed solutions. Chapter 5 validates them experimentally.

---

### 1.2 Motivation

The motivation is grounded in three observable trends: a structural labor challenge in food service, a growing market for service automation, and a technical readiness gap — the component technologies exist independently but have not been integrated into a deployed system.

**Labor challenge in food service.** The restaurant industry has faced a persistent and worsening labor shortage. In the United States, the restaurant workforce remained approximately 3.6% below pre-pandemic levels as of 2024, with quit rates in hospitality consistently outpacing all other sectors [n]. In Vietnam, the food and beverage sector — valued at over 590 trillion VND in 2024 and forecast to grow at 9–10% annually [n] — faces its own recruitment pressures. A 2024 survey of Vietnamese F&B enterprises found that 48% reported difficulty in recruiting and retaining service staff, citing high turnover, wage pressure, and a growing preference among younger workers for office-based employment over physical service roles [n]. These conditions create a structural need for automation that can handle the high-frequency, repetitive tasks of table service — taking orders, delivering food, processing payment — not to replace human workers, but to absorb the portion of the workload that human staff are increasingly unavailable or unwilling to perform.

**Market trajectory for service robotics.** Investment in food service automation has accelerated. The global food robotics market was valued at $2.9 billion in 2023 and is projected to reach $6.8 billion by 2030, growing at a compound annual rate of 12.7% [n]. In the Asia-Pacific region, which accounted for the largest revenue share, robot deliveries in restaurants have moved from novelty to expectation — a major Chinese robot manufacturer reported over 40,000 units deployed across more than 600 cities as of 2023 [n]. Vietnamese restaurants, particularly in the fast-growing casual dining and hot-pot segments in Ho Chi Minh City, Hanoi, and Da Nang, have begun experimenting with robotic delivery platforms imported from China and South Korea. However, these deployments are uniformly non-interactive: the robot delivers food that was ordered through a human waiter or a QR-code menu application. The ordering conversation and the physical delivery remain disconnected.

**Technical readiness and the integration gap.** The component technologies required for an AI waiter are individually mature. Large language models achieve human-competitive performance on Vietnamese conversational benchmarks [n]. Speech recognition models fine-tuned on Vietnamese deliver word error rates below 15% under clean conditions [n]. ROS2 navigation stacks reliably drive differential-drive platforms in mapped indoor environments [n]. Restaurant management software — point-of-sale systems, kitchen display systems, QR-code ordering — is a mature commercial category. What does not exist is a system where these components operate as a single pipeline: a customer speaks Vietnamese to a robot, that speech is transcribed, the intent is classified correctly despite informal language, the AI agent takes validated actions on a backend, the kitchen display updates in real time, and a robot navigates to the correct table to deliver the food. Each component has been developed for a different context — cloud chatbots for customer support, warehouse fleet managers for logistics, academic navigation stacks for controlled lab environments. Their integration into one working system introduces challenges that no prior work has addressed, and these challenges — not the individual components — form the intellectual contribution of this thesis.

**Feasibility.** The project uses a purchased two-wheel differential-drive robot platform as its physical base — chassis, motors, encoders, microcontroller, and IMU are provided. The group's contribution begins from ROS2 integration upward: adding sensors, implementing sensor fusion, building the navigation stack, and developing the complete AI, backend, and web software layer. This boundary allows the work to focus on system integration and AI capability rather than mechanical engineering. The entire system runs on commodity hardware: a laptop-grade GPU for LLM inference, an NVIDIA Jetson edge computer for on-robot voice processing, and standard web browsers for the client interfaces — making the architecture reproducible at a hardware cost accessible to small and medium-sized restaurant operators.

---

### 1.3 Objectives

The overall objective is to design, implement, and evaluate an autonomous AI waiter system that accepts Vietnamese spoken orders, processes them through a conversational agent, dispatches orders to the kitchen, and delivers food to the correct table using a two-wheel differential-drive robot. The following specific, measurable objectives are verified in Chapter 5:

1. **EKF-fused odometry:** Integrate encoder and IMU data through an Extended Kalman Filter on the TWD platform, achieving a return-to-start error within target thresholds after a closed kitchen-to-table-to-kitchen path.
2. **RTAB-Map-based navigation:** Build a restaurant map using LiDAR and RGB-D camera data via RTAB-Map. Navigate from kitchen to the correct table with a success rate meeting the target threshold.
3. **ArUco precision docking:** Achieve per-table docking precision using ArUco marker re-localization, with final pose error within target values for both position and orientation.
4. **Intent classification accuracy:** Classify Vietnamese restaurant utterances into the correct intent (order, search, payment, chat) with accuracy at or above 90%. Current results: 97.44% on the 39-case clean holdout set, 95.6% on the 45-case router evaluation set.
5. **Knowledge retrieval quality:** Retrieve relevant menu items from the 217-dish menu given Vietnamese sensory queries, measured by precision and recall at rank 5.
6. **End-to-end Vietnamese voice ordering:** Complete full ordering scenarios — from spoken utterance to confirmed order to kitchen display — with a pass rate meeting the target threshold.

---

### 1.4 Scope

**In scope.** The system operates in an indoor, flat-floor restaurant environment with a pre-mapped layout consisting of a kitchen area and six dining tables connected by a dedicated service lane. The lane is physically separated from customers — the robot does not navigate through dining areas and does not perform pedestrian avoidance. The map is two-dimensional. Navigation is autonomous within the service lane; robot arrival at a table triggers a precision docking step using ArUco fiducial markers. The customer interacts with the system through spoken Vietnamese, processed by a voice pipeline running on the robot's edge computer. The AI agent, knowledge retrieval system, and backend orchestrator run on a local server with a self-hosted large language model. Three web interfaces — a customer ordering tablet, a guest check-in kiosk, and a kitchen-and-fleet management panel — provide the operational frontend. All components communicate over local WiFi without cloud dependency during normal operation.

**Out of scope.** The robot platform is purchased — the mechanical design, chassis, motors, and low-level motor control firmware are not part of this work. The contribution begins from ROS2 integration upward. The system supports Vietnamese speech only; multi-language support is not implemented. The LLM agent is prompted, not fine-tuned. Only one restaurant environment is mapped and evaluated. Multi-floor operation, elevator integration, and dynamic obstacle handling (pedestrians in the lane) are not addressed.

**Known limitations.** The platform is non-holonomic — it cannot move laterally and corrects heading through in-place rotation. The consumer-grade MPU6050 IMU has bounded yaw accuracy; drift over long distances is corrected by ArUco markers at the tables but not during transit. The Intel RealSense D435 depth camera and ArUco detection are sensitive to lighting conditions. All components communicate over WiFi; network latency and occasional packet loss are managed through reconnection logic but not eliminated.

---

### 1.5 Research Methodology

The project followed a four-phase methodology:

1. **Literature and technology review.** Existing work in restaurant service robots, Vietnamese speech processing, conversational AI agents, knowledge retrieval, fleet management, and restaurant operations software was surveyed. For each domain, prior approaches were analyzed to identify what they achieve and where they fall short. These gaps motivated the system requirements in Chapters 3 and 4.

2. **Simulation-based development (Gazebo).** The robot's navigation stack — sensor drivers, EKF fusion, RTAB-Map SLAM, and Nav2 configuration — was first developed and tested in a Gazebo simulation environment modeling the restaurant layout. Simulation allowed rapid parameter tuning and stress-testing of navigation scenarios before deployment on physical hardware.

3. **Real-world deployment and integration.** After simulation validation, the system was deployed on physical hardware: the TWD robot platform with mounted LiDAR, depth camera, and Jetson edge computer, a GPU-equipped server running the LLM and orchestrator, and browser-based client applications on tablets and laptops. The full pipeline — voice capture, speech recognition, intent classification, agent reasoning, order creation, kitchen display, robot dispatch, and food delivery — was integrated and tested end to end.

4. **Quantitative evaluation.** Each objective was evaluated with a dedicated experiment suite. Navigation accuracy was measured through closed-path return-to-start tests and per-table docking precision trials. AI components — intent classification, knowledge retrieval, hallucination validation, and end-to-end conversation — were evaluated against curated test datasets with defined metrics. Voice pipeline components — speech-to-text word error rate, voice activity detection accuracy under restaurant noise, and barge-in behavior — were measured separately. System integration tests validated multi-table concurrency, fleet fault recovery, and end-to-end voice-to-delivery scenarios.

---

### 1.6 Report Structure

The remainder of this report is organized as follows:

- **Chapter 2** surveys prior work across five problem domains — dynamic goal navigation, Vietnamese voice on the edge, informal speech to validated actions, sensory-to-structured menu retrieval, and AI-driven restaurant operations. For each domain, it identifies a specific gap that the proposed system addresses.

- **Chapter 3** presents the robot control and navigation system. It defines the navigation requirements, identifies four design challenges, and describes the proposed method: EKF sensor fusion, RTAB-Map mapping and localization, ArUco precision docking, and Nav2-based autonomous navigation with dynamic backend-driven goal assignment.

- **Chapter 4** presents the AI agent, backend orchestrator, and web interfaces. It defines the system requirements, identifies six design challenges, and describes the overall software architecture, voice pipeline, conversational agent (intent classification, tool-calling LLM, deterministic validator, state machine, and response generation), knowledge retrieval pipeline, backend orchestration and fleet management, and three single-page web applications.

- **Chapter 5** presents the experiments and results. Each experiment validates one or more objectives: odometry accuracy, navigation and docking precision, intent classification accuracy, knowledge retrieval quality, validator safety, end-to-end conversation pass rate, voice pipeline performance, and system integration under concurrent load.

- **Chapter 6** concludes the thesis with a summary of contributions, limitations, and directions for future work.

The core contributions of this work are:

1. An autonomous two-wheel differential-drive robot platform with EKF-fused encoder-IMU odometry, RTAB-Map-based mapping and localization, ArUco precision docking, and Nav2 navigation controlled by an external AI-driven backend dispatcher.

2. A Vietnamese voice processing pipeline deployed on Jetson edge hardware, integrating voice activity detection, speech-to-text, and text-to-speech into a threaded system with barge-in capability, operating concurrently with robot control processes within a quantified VRAM budget.

3. A conversational AI agent built on a LangGraph state graph that converts informal Vietnamese restaurant utterances into deterministic, validated tool calls — combining a trained MLP intent classifier (context-aware, sub-millisecond latency), a tool-calling LLM with delegate escape, a deterministic post-generation validator that blocks hallucinated tool calls, and a cart state machine enforcing the correct ordering sequence.

4. A self-hosted, real-time restaurant management system integrating a REST API, a role-based WebSocket hub for multi-client state synchronization, a lightweight fleet dispatcher with dynamic robot-table voice binding and heartbeat-based fault recovery, a session lifecycle state machine, and three single-role web applications — all running as a single-server deployment with no cloud dependency.
