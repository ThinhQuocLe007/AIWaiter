# AI Waiter Core

This package contains the brain of the AI Waiter system, including the LLM orchestrator, RAG search engine, and tool integrations.

## Installation

Dependencies are managed by **uv** from the repo-root `pyproject.toml`. Post-pivot
(2026-06) the brain runs on the **server** (not as a ROS node on the Jetson). Install
the `server` role extra from the repo root — see [`docs/INSTALL.md`](../docs/INSTALL.md)
for the full per-machine guide:

```bash
cd <repo-root>
uv sync --extra server --extra cu13     # x86 server (use --extra cu12 on older GPU)
```

## Features
- **Hybrid Search**: Combines BM25 and Vector Search for menu retrieval.
- **Orchestrator**: Handles conversation memory and tool dispatching.
- **Pydantic Schemas**: Centralized data models for search and ordering.
