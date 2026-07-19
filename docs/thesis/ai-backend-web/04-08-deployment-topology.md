## 4.8 Deployment Topology

> **Status:** draft
> **Cross-refs:** §4.2 for overall architecture, §4.4 for voice pipeline deployment, §4.5 for orchestrator
> **Source:** `pyproject.toml` (171 lines), `Makefile` (158 lines), `.env.template`
> **Figures needed:** Hardware topology table (included in text)

---

The AI Waiter system is deployed across three physical machine classes connected over a local WiFi network. This section describes the hardware requirements, software installation approach, and network configuration that enable the system to operate entirely on-premises.

### 4.8.1 Hardware Topology

| Machine | Hardware | OS | Role | Services |
|---------|----------|-----|------|----------|
| **Central Server** | x86 PC with NVIDIA GPU (RTX 3070 Laptop, 8 GB VRAM) | Ubuntu 22.04 LTS | AI brain + backend | Ollama (Qwen2.5 7B), Agent Brain (:8100), Orchestrator (:8000), RAG indices, SQLite databases |
| **Robot** | Jetson Orin Nano 8 GB (aarch64, CUDA 12.6) | Ubuntu 22.04 + ROS 2 Humble | Voice I/O + navigation | Edge voice pipeline (Silero VAD, faster-whisper STT, Piper/edge-tts TTS), ROS2 Nav2 stack, sensor drivers |
| **Client devices** | Laptops / tablets (browser only) | Any | Staff interfaces | Customer tablet (menu, voice mirror, payment), Kiosk (check-in), Panel (kitchen + fleet) |

**Server GPU requirement.** The LLM (Qwen2.5 7B Instruct at float16 precision) requires approximately 6–8 GB VRAM. With `keep_alive=-1`, the model is pinned in GPU memory permanently — memory usage is constant, not per-turn.

**Jetson memory budget.** The Jetson Orin Nano's 8 GB unified memory is shared between the voice pipeline (~3 GB for faster-whisper medium at float16), the ROS2 navigation stack (~500 MB), and sensor drivers (~200 MB). Piper TTS adds ~200 MB. Total memory pressure is within the 8 GB budget, though headroom is limited.

**Client device requirements.** Client devices require only a modern web browser with WebSocket support. No installation, no GPU, no local storage beyond browser localStorage (for cart persistence). The Vite dev servers can run on any machine with Node.js 22, but production builds are static files served by any HTTP server or the orchestrator itself behind a reverse proxy.

### 4.8.2 LLM Configuration

A single Qwen2.5 7B Instruct model is served by Ollama on the central server. Three `ChatOllama` instances point to the same model with different runtime configurations for different agent stages:

| Stage | Temperature | Key Configuration | Purpose |
|-------|-------------|-------------------|---------|
| Router (Tier 2 SLM) | 0.0 | `with_structured_output(IntentPrediction)` | Deterministic classification with forced Pydantic output |
| Workers (ORDER, SEARCH) | 0.1 | `tool_choice="any"` | Near-deterministic tool selection with minor phrasing variation |
| Response | 0.3 | Free-form generation | Natural Vietnamese paraphrasing from structured context |

All three instances use `num_ctx=8192` (context window) and `keep_alive=-1` (model stays in GPU VRAM). A warmup ping at agent startup ensures the model is fully loaded before any customer utterance arrives — the first inference, which triggers GPU kernel compilation and model transfer, is absorbed at boot time rather than during the first customer interaction.

**Why one model, not three?** Using the same base model with different runtime temperatures avoids the memory overhead of loading three separate models (3 × 7 GB = 21 GB VRAM, exceeding the RTX 3070's 8 GB). Ollama shares the model weights across all three client instances — only the inference configuration differs per call.

### 4.8.3 Package Management

Software dependencies are managed through two package ecosystems corresponding to the two programming languages in the system:

**Python (backend + agent + voice pipeline).** Managed via `uv` with role-based optional dependencies defined in `pyproject.toml`:

| Extra | Purpose | Key Dependencies |
|-------|---------|-----------------|
| `server` | Agent brain + orchestrator | langgraph, langchain-ollama, fastapi, sentence-transformers, faiss-cpu, rank-bm25, underthesea |
| `voice` | Edge voice pipeline | faster-whisper, pyaudio, edge-tts, piper-tts |
| `cu12` | x86 with CUDA 12 (e.g., RTX 3050, driver 535) | torch cu121, sentence-transformers (GPU) |
| `cu13` | x86 with CUDA 13 (e.g., Blackwell GPUs, driver ≥580) | torch ≥2.12 (PyPI), sentence-transformers (GPU) |

The `aarch64` Jetson uses torch from the NVIDIA Jetson AI Lab index (JetPack 6.2, CUDA 12.6, torch 2.11.0) configured in `pyproject.toml`:
- Server (x86, CUDA 12): `uv sync --extra server --extra cu12`
- Server (x86, CUDA 13): `uv sync --extra server --extra cu13`
- Robot (Jetson aarch64): `uv sync --extra voice`

The `Makefile` provides convenience targets: `make install UV_EXTRAS="--extra server --extra cu12"` for the server, `make install UV_EXTRAS="--extra voice"` for the Jetson.

**Frontend.** Three independent Vite projects in `src/frontends/`, each with its own `package.json` and `node_modules`. All use Node.js 22 (pinned via `.nvmrc`). Installation is documented in `setup.sh`: installs nvm + Node 22, runs `npm ci` in each frontend directory. The `Makefile` provides `make menu`, `make kiosk`, `make panel`, and `make frontend` (all three) targets.

### 4.8.4 Network

All components communicate over a local WiFi network, with no internet dependency during normal operation:

| Communication | Protocol | Port | Path |
|--------------|----------|------|------|
| Agent ↔ Orchestrator | HTTP | 8000 | localhost (co-located on server) |
| Agent ↔ Ollama | HTTP | 11434 | localhost |
| Orchestrator ↔ Web clients | HTTP + WebSocket | 8000 | Local WiFi |
| Voice device ↔ Orchestrator | WebSocket | 8000 | Local WiFi (Jetson → server) |
| Voice device ↔ Agent | HTTP | 8100 | Local WiFi (Jetson → server) |
| ROS2 robot ↔ Orchestrator | WebSocket | 8000 | Local WiFi |

**Off-site server support.** For deployments where the GPU server is not on the restaurant LAN (e.g., a central server room serving multiple restaurant locations), Netbird VPN provides a secure encrypted overlay. All components use hostnames or static IPs configured in `.env` (`ORCHESTRATOR_URL`, `AGENT_URL`), which can point to Netbird-assigned addresses transparently.

**Offline capability.** The system's self-hosted design means the restaurant WiFi can fail and core functions continue:
- The orchestrator and agent run on the same server — no network is needed for voice ordering (the Jetson can reach the server directly via LAN IP even without internet).
- TTS falls back to Piper (offline) when edge-tts (cloud) is unreachable.
- The menu, orders, and payments are all stored in local SQLite databases — no cloud database dependency.
- The only external dependency is Ollama's model download (one-time), Piper TTS model download (one-time), and VietQR image generation (optional — the payment QR is a static mock in the current implementation).

### 4.8.5 Startup Sequence

The system starts in dependency order, enforced by the `Makefile`:

```
1. Ollama (must be running first)
   └── ollama serve      # or systemd service
   └── ollama pull qwen2.5:7b-instruct   # one-time model download

2. Orchestrator (:8000)
   └── make backend      # uv run uvicorn src.server_orchestrator.main:app --port 8000
   └── Seeds DB: tables, dishes, robots
   └── Starts watchdog (background asyncio task)

3. Agent Brain (:8100)
   └── make agent        # uv run uvicorn src.agent_brain.server:app --port 8100
   └── Warmup: pings Ollama, loads RAG indices, pre-computes centroids

4. Voice Device (Jetson)
   └── make voice        # uv run python src/edge_voice/main.py
   └── Connects to orchestrator WS as role=voice-device
   └── Warmup: loads Silero VAD, faster-whisper, Piper TTS

5. Frontends (dev servers or static build)
   └── make frontend     # Starts Vite dev servers on ports 5173-5175
```

The orchestrator is independent of the agent for core functionality — menu browsing, manual ordering, and table management continue working even if the agent is restarting. The agent requires Ollama (warmup ping verifies this at startup) and the orchestrator (for order/payment APIs). The voice device requires both the agent and the orchestrator's WebSocket hub.

### 4.8.6 Development Workflow

The `Makefile` provides a complete development workflow with single-command targets:

| Command | Action |
|---------|--------|
| `make setup` | First-time environment: installs nvm + Node 22 + uv, creates `.env` from template |
| `make install` | Installs all dependencies (npm ci for frontends, uv sync for Python) |
| `make backend` | Starts orchestrator on port 8000 with hot reload |
| `make agent` | Starts agent on port 8100 with hot reload, auto-rebuilds RAG index |
| `make voice` | Starts edge voice device (connects to server over network) |
| `make mockrobot` | Starts a mock robot WebSocket client for testing the dispatcher |
| `make frontend` | Starts all three Vite dev servers concurrently |
| `make reset` | Wipes demo data via `POST /admin/reset` |
| `make kill` | Stops all dev servers on ports 8000, 8100, 5173–5175 |
| `make reindex` | Rebuilds FAISS + BM25 indices and centroids from menu data |
| `make clean` | Removes `node_modules`, `.venv`, and Python cache |

**Hot reload.** The orchestrator and agent both use `uvicorn --reload`, watching for Python file changes and restarting automatically. Frontends use Vite's HMR (Hot Module Replacement), reflecting TypeScript and Vue changes in the browser without full page reloads. This enables rapid iteration — a prompt change in `router_agent.md` requires an agent restart (automatic with `--reload`), while a Vue component change appears immediately in the browser.
