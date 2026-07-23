# TABLE OF CONTENTS

## CHAPTER 1 — INTRODUCTION
- 1.1 Overview
- 1.2 Motivation
- 1.3 Objectives
- 1.4 Scope
- 1.5 Research Methodology
- 1.6 Report Structure

## CHAPTER 2 — RELATED WORK & PROBLEM ANALYSIS

> **Note for the reviewer — how to read this chapter.** Each section is one of two kinds:
> - **[USE]** — a survey of mature, off-the-shelf tools; it ends in a *comparison table*, and Chapter 4 selects one. It makes no research claim. Sections: **§2.3, §2.7**.
> - **[BUILD]** — a survey of prior approaches showing why none fits, ending in a *gap statement* that Chapter 4 answers. These carry the contribution. Sections: **§2.4, §2.5, §2.6**.
> - **[MIXED]** — off-the-shelf components plus one integration contribution: **§2.2** (mature navigation stack + AI-assigned goals) and **§2.8** (off-the-shelf board + the placement of computation between vehicle and infrastructure). §2.1 frames the problem; §2.9 is the traceability matrix.

- 2.1 Overview: Automation of the Restaurant Service Loop
  - 2.1.1 Service Robots in the Restaurant Industry
  - 2.1.2 Conversational Ordering Systems
  - 2.1.3 Restaurant Management Software
  - 2.1.4 The Integration Gap
- 2.2 Autonomous Mobile Robot
  - 2.2.1 Wheel Odometry and Sensor Fusion
  - 2.2.2 SLAM, Map Building, and Localization
  - 2.2.3 Autonomous Navigation
  - 2.2.4 Fiducial Marker Docking
  - 2.2.5 Prior ROS2 Delivery Robot Research
- 2.3 Vietnamese Voice Understanding
  - 2.3.1 Voice Activity Detection
  - 2.3.2 Speech-to-Text for Vietnamese
  - 2.3.3 Text-to-Speech for Vietnamese
- 2.4 Conversational AI Agent
  - 2.4.1 From General-Purpose LLM to Task-Oriented Agent
  - 2.4.2 Agent Architectures — The Orchestration Layer
  - 2.4.3 Large Language Models — The Reasoning Component
  - 2.4.4 Intent Classification — The Routing Layer
  - 2.4.5 Action Validation — The Safety Layer
  - 2.4.6 Memory and State Management in Conversational Agents
  - 2.4.7 Tool Composition, Domain Adaptation, and the Cross-Domain Validation Pattern
- 2.5 Menu Knowledge Retrieval (RAG)
  - 2.5.1 The Knowledge Problem and Standard RAG
  - 2.5.2 Embedding Models
  - 2.5.3 Indexing and Search
  - 2.5.4 Result Fusion
  - 2.5.5 Beyond Retrieve→Generate: Rewriting, Evaluation, Context
- 2.6 Backend Orchestration & Fleet Management
  - 2.6.1 Multi-Robot Task Assignment
  - 2.6.2 Dynamic Robot-Table Voice Binding
  - 2.6.3 Telemetry, Liveness, and Fault Recovery
  - 2.6.4 Real-Time Restaurant State Synchronization
- 2.7 Multi-Role Web Interfaces
  - 2.7.1 Single-Page Application Frameworks
  - 2.7.2 Component Libraries
  - 2.7.3 Build Tooling
  - 2.7.4 Real-Time Communication Patterns
  - 2.7.5 Multi-Role Interfaces and the Origin of Events
- 2.8 Edge Computing Platform
  - 2.8.1 The Workload Aboard a Service Robot
  - 2.8.2 Placement of Computation: Onboard, Offboard, and the Split
  - 2.8.3 Accelerator Classes: GPU, NPU, and the TOPS Metric
  - 2.8.4 The Jetson Orin Nano — Hardware and Software Stack
  - 2.8.5 Platform Comparison
  - 2.8.6 Sensor Interfaces
  - 2.8.7 Prior Work on Jetson in Robotics
- 2.9 Summary: Needs → Requirements Traceability
  - 2.9.1 Gap-to-Requirement Traceability
  - 2.9.2 What Prior Systems Cover vs. What This Thesis Integrates
  - 2.9.3 The Integration Gap

## CHAPTER 3 — PROPOSED METHOD (I): ROBOT CONTROL AND NAVIGATION
- 3.1 System Requirements
- 3.2 Design Challenges (C1–C4)
- 3.3 Robot Platform & Hardware Setup
- 3.4 Wheel Odometry and EKF Sensor Fusion
- 3.5 Map Building with RTAB-Map
- 3.6 Localization and ArUco-Based Docking
- 3.7 Autonomous Navigation & Dynamic Goal Assignment

## CHAPTER 4 — PROPOSED METHOD (II): AI, BACKEND & WEB SYSTEM
- 4.1 System Requirements & Design Rationale
- 4.2 Design Challenges (C5–C10)
- 4.3 Overall Software Architecture
- 4.4 Edge Voice Pipeline
- 4.5 Conversational Agent
  - 4.5.1 Execution Model (LangGraph StateGraph)
  - 4.5.2 Stage I — Intent Classification (MLP)
  - 4.5.3 Stage II — Tool-Calling LLM
  - 4.5.4 Stage III — Deterministic Validator
  - 4.5.5 Stage IV — Tools & State Management
  - 4.5.6 Stage V — Response Generation
  - 4.5.7 Prompt Architecture
- 4.6 Knowledge Retrieval Pipeline
  - 4.6.1 Query Rewriting
  - 4.6.2 Hybrid Retrieval
  - 4.6.3 Result Rephrasing
  - 4.6.4 Multi-Turn Search Context
- 4.7 Backend Orchestrator
  - 4.7.1 REST API
  - 4.7.2 WebSocket Hub
  - 4.7.3 Session Lifecycle
  - 4.7.4 Fleet Management
  - 4.7.5 Database Schema
- 4.8 Web Interfaces
- 4.9 Deployment Topology

## CHAPTER 5 — EXPERIMENTS AND RESULTS
- 5.1 Evaluation Methodology
- 5.2 ROS2 Navigation Experiments
- 5.3 AI Agent Experiments
- 5.4 Voice Pipeline Experiments
- 5.5 System Integration Tests
- 5.6 Web System Experiments
- 5.7 Results Summary & Gap-to-Validation Traceability

## CHAPTER 6 — CONCLUSION AND FUTURE WORK
- 6.1 Conclusion
- 6.2 Limitations
- 6.3 Future Work

## APPENDICES
## FRONT MATTER
