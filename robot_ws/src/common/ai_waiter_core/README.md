# AI Waiter Core

This package contains the brain of the AI Waiter system, including the LLM orchestrator, RAG search engine, and tool integrations.

## Installation

### 1. External Dependencies
Ensure you have the following libraries installed:

```bash
pip install -r requirements.txt
```

### 2. ROS 2 Workspace
Install the package in your ROS 2 workspace:

```bash
cd ~/robot_ws
colcon build --packages-select ai_waiter_core
source install/setup.bash
```

## Running the Brain Node

To start the main AI Brain node:

```bash
ros2 run ai_waiter_core ai_brain
```

## Features
- **Hybrid Search**: Combines BM25 and Vector Search for menu retrieval.
- **Orchestrator**: Handles conversation memory and tool dispatching.
- **Pydantic Schemas**: Centralized data models for search and ordering.
