# Makefile - Convenience commands for AI Waiter project
# Run 'make help' to see available commands

.PHONY: help setup install update frontend menu kiosk panel backend reindex agent voice mockrobot build serve kill reset clean

# Role-specific Python extras for the backend env (see docs/setup-deploy.md). Each machine
# picks ONLY its role: fastapi/uvicorn live in `--extra server`, STT/TTS in `--extra voice`,
# and the torch profile in `--extra cu12`/`--extra cu13`. Override per machine, e.g.:
#   make install UV_EXTRAS="--extra server --extra voice --extra cu12"   # laptop dev (CUDA 12)
#   make install UV_EXTRAS="--extra server --extra cu13"                 # server (CUDA 13)
#   make install UV_EXTRAS="--extra voice"                               # Jetson robot
UV_EXTRAS ?=

# Default target
help:
	@echo "AI Waiter - Available commands:"
	@echo ""
	@echo "  make setup      - First-time environment setup (run once)"
	@echo "  make install    - Install/update deps. Backend needs UV_EXTRAS, e.g."
	@echo "                    make install UV_EXTRAS=\"--extra server --extra voice --extra cu12\""
	@echo "  make update     - Pull latest code and reinstall dependencies"
	@echo "  make frontend   - Start all three UIs: menu, kiosk, panel (ports 5173-5175)"
	@echo "  make menu       - Start menu (ordering) dev server (port 5173)"
	@echo "  make kiosk      - Start kiosk check-in dev server (port 5174)"
	@echo "  make panel      - Start kitchen panel dev server (port 5175)"
	@echo "  make build      - Build frontend for production (outputs dist/)"
	@echo "  make serve      - Serve production build locally (port 4173)"
	@echo "  make backend    - Start orchestrator backend (FastAPI, port 8000)"
	@echo "  make agent      - Start LLM agent HTTP service (port 8100); auto-rebuilds the index first"
	@echo "  make voice      - Start edge voice device (Jetson / any mic-capable machine)"
	@echo "  make mockrobot  - Start a mock robot WS client (ID=robo-1 ARGS=...) to test the dispatcher"
	@echo "  make reindex    - Clean rebuild of FAISS + BM25 + centroid artifacts"
	@echo "  make reset      - Wipe demo data: clear orders/seatings, free all tables (backend must be running)"
	@echo "  make kill       - Stop all dev servers (backend 8000/8100, frontends 5173-5175, voice)"
	@echo "  make clean      - Remove node_modules, .venv, and Python __pycache__"
	@echo ""

setup:
	@chmod +x setup.sh
	@./setup.sh

install:
	@echo "Installing customer_ui dependencies..."
	@if [ -f "src/frontends/customer_ui/package.json" ]; then cd src/frontends/customer_ui && npm ci; else echo "src/frontends/customer_ui not scaffolded yet, skipping."; fi
	@echo "Installing kiosk dependencies..."
	@if [ -f "src/frontends/kiosk/package.json" ]; then cd src/frontends/kiosk && npm install; else echo "src/frontends/kiosk not scaffolded yet, skipping."; fi
	@echo "Installing panel dependencies..."
	@if [ -f "src/frontends/panel/package.json" ]; then cd src/frontends/panel && npm install; else echo "src/frontends/panel not scaffolded yet, skipping."; fi
	@echo "Installing backend dependencies (root uv env)..."
	@# --inexact: keep role extras (server/voice/cu12/cu13) already installed instead of
	@# pruning them. Plain `uv sync` syncs to base-only and would REMOVE uvicorn/torch/etc.
	@# Pass UV_EXTRAS to install a role in one go, e.g. UV_EXTRAS="--extra server --extra cu12".
	@uv sync --inexact $(UV_EXTRAS)
	@if [ -z "$(UV_EXTRAS)" ] && [ ! -x .venv/bin/uvicorn ]; then \
		echo ""; \
		echo "  NOTE: backend deps (fastapi/uvicorn) are NOT installed — they live in --extra server."; \
		echo "        Run your machine's role, e.g.:  make install UV_EXTRAS=\"--extra server --extra voice --extra cu12\""; \
		echo "        See docs/setup-deploy.md for the right extras (CUDA 12 vs 13, server vs voice)."; \
	fi
	@echo "Done."

update:
	@git pull
	@$(MAKE) install

# Run all three UIs together; Ctrl-C stops the whole group (trap kills child PIDs).
frontend:
	@echo "Starting menu (5173), kiosk (5174), panel (5175)... Ctrl-C to stop all."
	@trap 'kill 0' INT TERM EXIT; \
		(cd src/frontends/customer_ui && npm run dev) & \
		(cd src/frontends/kiosk && npm run dev) & \
		(cd src/frontends/panel && npm run dev) & \
		wait

menu:
	@cd src/frontends/customer_ui && npm run dev

kiosk:
	@cd src/frontends/kiosk && npm run dev

panel:
	@cd src/frontends/panel && npm run dev

build:
	@echo "Building frontend for production..."
	@cd src/frontends/customer_ui && npm run build
	@echo "Done. Output in src/frontends/customer_ui/dist/"

serve:
	@echo "Serving production build on http://0.0.0.0:4173"
	@cd src/frontends/customer_ui && npm run preview -- --host 0.0.0.0 --port 4173

backend:
	@uv run uvicorn src.server_orchestrator.main:app --reload --host 0.0.0.0 --port 8000

# Clean rebuild of the embedding artifacts (FAISS + BM25 + router centroids) from scratch using the
# current EMBEDDING_MODEL in .env. Wipes the old files first so nothing stale survives a model/dim
# change. SQLite DBs (checkpoints/orchestrator) are left untouched. Run after switching embeddings.
reindex:
	@echo "Wiping old vector / BM25 / centroid artifacts..."
	@rm -rf storage/vector \
		src/agent_brain/agent/resources/centroids/centroids.npz \
		src/agent_brain/agent/resources/centroids/embedding_model.txt
	@echo "Rebuilding FAISS + BM25 + centroids with EMBEDDING_MODEL from .env..."
	@uv run python scripts/setup.py --force

# Agent (LLM) HTTP service — the brain on the SERVER. The Jetson voice loop
# (src/edge_voice/main.py) POSTs recognised text to POST /chat; this runs the LangGraph agent
# and mirrors the turn to the customer tablet via the backend's /voice bridge. Depends on
# `reindex` so every start rebuilds the embeddings clean (you asked for a fresh index each run
# while testing new models). To restart WITHOUT rebuilding, run the uvicorn line directly.
agent: reindex
	@uv run uvicorn src.agent_brain.server:app --host 0.0.0.0 --port 8100

# Edge voice device — runs on the Jetson (or any machine with a mic + speaker). Idles for
# /start_listening commands from the backend's WS hub. Preloads the VAD + STT models at boot
# (slow first import). .env must point AGENT_URL + ORCHESTRATOR_URL at the server.
voice:
	@uv run python src/edge_voice/main.py

# Mock robot WS client — stands in for a real Jetson robot to test the dispatcher end-to-end.
# Override id/position: make mockrobot ID=robo-2 ARGS="--x 2.3 --y 0.5".
ID ?= robo-1
mockrobot:
	@uv run python scripts/mock_robot.py --id $(ID) $(ARGS)

# Sim robot bridge — drives the Gazebo TurtleBot4 as a REAL dispatcher robot: task.assign →
# Nav2/ArUco delivery → arrived/task_done + map-frame heartbeats (battery fixed 100%).
# Needs Gazebo + Nav2 already up (see docs/run-guide-vi.md) and the workspace built
# (cd robot_ws && colcon build). Point at a remote backend: make simbridge SERVER_HOST=100.x:8000
SERVER_HOST ?= 127.0.0.1:8000
simbridge:
	@cd robot_ws && . /opt/ros/humble/setup.sh && . install/setup.sh && \
	ros2 run ai_sim_bridge task_bridge --ros-args \
		-p server_host:=$(SERVER_HOST) -p robot_id:=$(ID)

# Reset all live demo data (orders, seatings, tables → free, robots → seed) via the running
# backend. Panels reload instantly (WS 'reset' event); kiosk reflects on its next table poll.
# Offline alternative (backend stopped): rm storage/db/orchestrator.db — reseeds on next start.
reset:
	@curl -fsS -X POST http://127.0.0.1:8000/admin/reset \
		&& echo "  -> demo data reset" \
		|| echo "  backend not running on :8000 — start 'make backend', or rm storage/db/orchestrator.db"

kill:
	@echo "Stopping dev servers (ports 8000/8100/5173-5175 + voice device)..."
	@-for p in 8000 8100 5173 5174 5175; do \
		pids=$$(ss -ltnp 2>/dev/null | grep ":$$p " | grep -oP 'pid=\K[0-9]+' | sort -u); \
		if [ -n "$$pids" ]; then kill $$pids 2>/dev/null && echo "  killed port $$p (pid: $$pids)"; fi; \
	done
	@# Bracket trick ([u]vicorn / [v]ite) + token-free echoes so the pattern never
	@# matches this recipe's own shell command line (which would self-terminate make).
	@-pkill -f '[u]vicorn src.server_orchestrator.main' 2>/dev/null && echo "  stopped orchestrator backend (incl. --reload parent)" || true
	@-pkill -f '[u]vicorn src.agent_brain.server' 2>/dev/null && echo "  stopped agent HTTP service" || true
	@-pkill -f 'src.edge_voice.main' 2>/dev/null && echo "  stopped voice device" || true
	@-pkill -f 'frontends/.*[v]ite' 2>/dev/null && echo "  stopped frontend dev servers" || true
	@echo "Done."

clean:
	@echo "Removing node_modules, .venv, and Python __pycache__ directories..."
	@rm -rf src/frontends/customer_ui/node_modules
	@rm -rf src/frontends/kiosk/node_modules
	@rm -rf src/frontends/panel/node_modules
	@rm -rf .venv
	@# Wipe all __pycache__ inside src/ (skip .venv / node_modules). Keeps the
	@# working tree clean after refactors / branch switches.
	@find src -name __pycache__ -type d -prune -exec rm -rf {} +
	@echo "Done. Run 'make install' to reinstall."
