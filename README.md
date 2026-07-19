# AI Waiter - Capstone Project

> 📦 **Cài đặt + Chạy web:** xem **[docs/guides/run-guide-vi.md](docs/guides/run-guide-vi.md)** (clone → `make install` → chạy 3 web + backend).
> 🏗️ **Kiến trúc:** xem **[docs/architecture/code-architecture.md](docs/architecture/code-architecture.md)**.
> (Phần *System Architecture* + *Setup* bên dưới mô tả pipeline **bản cũ (all-in-one)** — đã được pivot 2026-06 thay thế.)
>
> 🧭 **Layout 2026-06 (sau refactor):** `src/agent_brain/` (LLM brain) · `src/edge_voice/` (Jetson voice device) · `src/server_orchestrator/` (FastAPI backend) · `src/_shared/` (cross-role paths + types) · `src/frontends/` (3 Vite/Vue apps). Xem [tasks_on_section.md](tasks_on_section.md) để biết chi tiết từng phase.

## Introduction
This project is an AI-powered waiter designed to take restaurant orders in Vietnamese. It allows customers to order food and ask menu questions using natural voice commands.

The goal is to build a seamless system that understands context, retrieves menu information, and processes orders using Large Language Models.

## System Architecture
The system follows a specific pipeline to handle voice inputs and generate appropriate responses.

![System Pipeline](pipeline.jpg)

### How it works

The pipeline consists of three main stages:

1. **Input Processing:**
   - The microphone captures audio.
   - **Silero VAD** detects voice activity.
   - **PhoWhisper** converts Vietnamese speech into text.

2. **Llama 3 Decision Engine (The Core):**
   - The text is sent to the Llama 3 model to understand user intent.
   - The system splits into two logic branches:
     - **Branch 1 (Action/Info):** If the user wants to order or asks about food, the system uses **RAG** to search the menu or **Function Calling** to create an order/payment via API.
     - **Branch 2 (General Chat):** If the user is just chatting, the system generates a conversational response without using tools.

3. **Output Synthesis:**
   - The final text response is converted back to speech for the user.

## Tech Stack

- **LLM:** Llama 3 (running locally or on server)
- **Speech-to-Text:** PhoWhisper (Vietnamese specific)
- **Voice Detection:** Silero VAD
- **Knowledge Retrieval:** RAG (Retrieval-Augmented Generation) for Menu Search
- **Actions:** Function Calling (API for Orders/Payments)
- **Deployment:** Kaggle (Prototype) -> AWS (Final)

## Project Status

- [x] System Design & Architecture
- [ ] Text Processing Implementation (Llama 3 + RAG + Tools)
- [ ] Voice Integration
- [ ] Final Deployment

## Development Environment Setup

This repo ships with a one-command setup so any teammate can clone and get an
identical environment. Lock files (`package-lock.json`, `uv.lock`) pin exact
dependency versions across machines.

### Team environment

- **OS:** Ubuntu 22.04 LTS
- **Python:** 3.10 (system default, also used by ROS2)
- **Node.js:** 22.x (managed via nvm, pinned in `.nvmrc`)
- **Package managers:** `uv` for Python, `npm` for Node.js

### Clone and run — fresh machine (no Node/nvm/uv yet)

Use this on a new Ubuntu machine that does not yet have the toolchain. The
setup script installs everything for you.

```bash
git clone <repo-url>
cd AI_Waiter        # the cloned folder
make setup          # runs ./setup.sh: installs nvm + Node 22 + uv, npm ci, creates .env
source ~/.bashrc    # reload the shell so node/nvm are on PATH
make frontend       # start the dev server at http://localhost:5173
```

`make setup` automatically:
- Installs nvm (Node Version Manager) if not present
- Installs Node.js v22 via nvm (pinned in `.nvmrc`)
- Installs uv (Python package manager) if not present
- Runs `npm ci` in `src/frontends/customer_ui` (exact versions from `package-lock.json`)
- Creates `.env` from `.env.example`
- Skips the backend step gracefully until a `backend/` folder exists

> Note: `setup.sh` only runs on Linux (Ubuntu 22.04). On macOS/Windows, install
> Node 22 manually (e.g. via nvm), then follow the "already have Node" steps below.

### Clone and run — machine that already has Node 22

If the toolchain is already installed, skip the setup script:

```bash
git clone <repo-url>
cd AI_Waiter/src/frontends/customer_ui
npm ci              # install exact versions from package-lock.json
npm run dev         # opens at http://localhost:5173
```

Or, from the repo root, use the Makefile shortcuts:

```bash
make install        # npm ci for the frontend
make frontend       # start the dev server
```

### Makefile shortcuts

```bash
make help        # List all commands
make setup       # First-time setup
make frontend    # Start the customer_ui dev server
make install     # Reinstall deps after pulling code
make update      # git pull + reinstall
make clean       # Remove node_modules / .venv
```

### Environment variables

`src/frontends/customer_ui` uses a `.env` file (never committed). On first setup it
is created from `src/frontends/customer_ui/.env.example`. Edit the values to match
your local backend / rosbridge endpoints.

> Note: the root `.env.template` (HF token, model config) is separate and used by
> the Python pipeline; copy it to `.env` and fill in your own values.

### Files to commit

Commit: `.nvmrc`, `.gitignore`, `setup.sh`, `Makefile`, `README.md`, the whole
`src/frontends/customer_ui/` source tree (including `package.json` +
`package-lock.json` and `.env.example`).

Never commit: any `.env`, `node_modules/`, `dist/`.

---
University Student - Ho Chi Minh City