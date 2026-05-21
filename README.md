# AI Waiter - Capstone Project

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

### First-time setup

After cloning the repository, run the setup script once:

```bash
chmod +x setup.sh
./setup.sh
```

This will automatically:
- Install nvm (Node Version Manager) if not present
- Install Node.js v22 via nvm
- Install uv (Python package manager) if not present
- Install frontend dependencies for `frontends/customer_ui` (once it is scaffolded)
- Create `.env` files from `.env.example` templates
- Skip the backend step gracefully until a `backend/` folder exists

After setup completes, reload your shell:

```bash
source ~/.bashrc
```

### Scaffolding the frontend (one time)

The `frontends/customer_ui` folder is a placeholder. To create the Vue 3 app:

```bash
cd frontends/customer_ui
npm create vue@latest .
npm install
```

`./setup.sh` will then pick it up automatically on subsequent runs.

### Running the project

```bash
cd frontends/customer_ui
npm run dev
# Opens at http://localhost:5173
```

Or use the Makefile shortcuts:

```bash
make help        # List all commands
make setup       # First-time setup
make frontend    # Start the customer_ui dev server
make install     # Reinstall deps after pulling code
make update      # git pull + reinstall
make clean       # Remove node_modules / .venv
```

### Environment variables

`frontends/customer_ui` uses a `.env` file (never committed). On first setup it
is created from `frontends/customer_ui/.env.example`. Edit the values to match
your local backend / rosbridge endpoints.

> Note: the root `.env.template` (HF token, model config) is separate and used by
> the Python pipeline; copy it to `.env` and fill in your own values.

### Files to commit

Commit: `.nvmrc`, `.gitignore`, `setup.sh`, `Makefile`, `README.md`,
`frontends/customer_ui/.env.example`, and (after scaffolding)
`frontends/customer_ui/package.json` + `package-lock.json`.

Never commit: any `.env`, `node_modules/`.

---
University Student - Ho Chi Minh City