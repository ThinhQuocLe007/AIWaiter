# Makefile - Convenience commands for AI Waiter project
# Run 'make help' to see available commands

.PHONY: help setup install update frontend menu kiosk panel monitor backend agent voice probe mockrobot simbridge hwbridge hwstack jetson robotlink checkmap caps say train-router map build serve kill reset clean

# Role-specific Python extras for the backend env (see docs/setup-deploy.md). Each machine
# picks ONLY its role: fastapi/uvicorn live in `--extra server`, STT/TTS in `--extra voice`,
# and the torch profile in `--extra cu12`/`--extra cu13`. Override per machine, e.g.:
#   make install UV_EXTRAS="--extra server --extra voice --extra cu12"   # laptop dev (CUDA 12)
#   make install UV_EXTRAS="--extra server --extra cu13"                 # server (CUDA 13)
#   make install UV_EXTRAS="--extra voice"                               # Jetson robot
UV_EXTRAS ?=

# The repo-root venv interpreter. Targets that must NOT trigger a `uv sync` (the Jetson voice
# ones — see the `voice` target) call this instead of `uv run`. Fails loudly if setup never ran.
VENV_PY := .venv/bin/python
$(VENV_PY):
	@echo "Chưa có $(VENV_PY) — chạy 'make setup' (hoặc 'make install UV_EXTRAS=\"--extra voice\"') trước."
	@exit 1

# Default target
help:
	@echo "AI Waiter - Available commands:"
	@echo ""
	@echo "  make setup      - First-time environment setup (run once)"
	@echo "  make install    - Install/update deps. Backend needs UV_EXTRAS, e.g."
	@echo "                    make install UV_EXTRAS=\"--extra server --extra voice --extra cu12\""
	@echo "  make update     - Pull latest code and reinstall dependencies"
	@echo "  make frontend   - Start all four UIs: menu, kiosk, panel, monitor (ports 5173-5176)"
	@echo "  make menu       - Start menu (ordering) dev server (port 5173)"
	@echo "  make kiosk      - Start kiosk check-in dev server (port 5174)"
	@echo "  make panel      - Start kitchen panel dev server (port 5175)"
	@echo "  make monitor    - Start voice monitor dev server (port 5176) — màn hình demo"
	@echo "  make build      - Build frontend for production (outputs dist/)"
	@echo "  make serve      - Serve production build locally (port 4173)"
	@echo "  make backend    - Start orchestrator backend (FastAPI, port 8000)"
	@echo "  make agent      - Start LLM agent HTTP service (port 8100)"
	@echo "  make voice      - Start edge voice device (Jetson / any mic-capable machine)"
	@echo "  make jetson     - Jetson, cả buổi demo trong 1 lệnh: voice + màn rời mở /monitor"
	@echo "  make probe      - Mic -> VAD -> Whisper only: nói vào mic, in ra text (không cần server)"
	@echo "  make robotlink  - [LAPTOP Gazebo] nhận lệnh giọng nói qua UDP, lái AGV kho"
	@echo "  make checkmap   - Kiểm tra data kho có khớp sa bàn Gazebo không"
	@echo "  make caps       - In bảng mapping giọng nói → lệnh robot"
	@echo "  make say        - Gõ câu tiếng Việt bắn sang robot: make say TEXT=\"dừng lại\" [DRY=1]"
	@echo "  make train-router - Train lại bộ phân loại ý định sau khi sửa intents.json"
	@echo "  make mockrobot  - Start a mock robot WS client (ID=robo-1 ARGS=...) to test the dispatcher"
	@echo "  make simbridge  - Gazebo robot bridge (sim demo); make backend SIM=1 for the sim map"
	@echo "  make hwstack    - REAL robot, all-in-one on the Jetson: localization + Nav2 + bridge"
	@echo "  make hwbridge   - REAL robot bridge only (localization + Nav2 already running)"
	@echo "  make map        - Re-export the minimap floor from the RTAB-Map database"
	@echo "  make reset      - Wipe demo data: clear orders/seatings, free all tables (backend must be running)"
	@echo "  make kill       - Stop all dev servers (backend 8000/8100, frontends 5173-5176, voice)"
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
	@# monitor was missing here while `build` below still built it, so a fresh clone got through
	@# `make install` cleanly and then died inside `make build` — on the one app that IS the demo.
	@echo "Installing monitor dependencies..."
	@if [ -f "src/frontends/monitor/package.json" ]; then cd src/frontends/monitor && npm install; else echo "src/frontends/monitor not scaffolded yet, skipping."; fi
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
	@echo "Starting menu (5173), kiosk (5174), panel (5175), monitor (5176)... Ctrl-C to stop all."
	@trap 'kill 0' INT TERM EXIT; \
		(cd src/frontends/customer_ui && npm run dev) & \
		(cd src/frontends/kiosk && npm run dev) & \
		(cd src/frontends/panel && npm run dev) & \
		(cd src/frontends/monitor && npm run dev) & \
		wait

menu:
	@cd src/frontends/customer_ui && npm run dev

kiosk:
	@cd src/frontends/kiosk && npm run dev

panel:
	@cd src/frontends/panel && npm run dev

# Voice monitor — THE demo screen: one big robot, a waveform that shows it listening / thinking /
# answering, and the answer itself. Needs the orchestrator (make backend), the agent (make agent)
# and a voice device (make voice on the Jetson) to have anything to show.
monitor:
	@cd src/frontends/monitor && npm run dev

# Build ALL FOUR web apps for production. `make backend` then serves the dist/ folders itself
# (src/server_orchestrator/main.py) on ONE origin — customer_ui at :8000/, kiosk at :8000/kiosk,
# panel at :8000/panel, monitor at :8000/monitor. Clients (Jetson chromium, entrance tablet, kitchen panel) only open a URL;
# they need neither Node nor a dev server. Run this on the SERVER after every `git pull`.
build:
	@echo "Building customer_ui, kiosk, panel, monitor for production..."
	@cd src/frontends/customer_ui && npm run build
	@cd src/frontends/kiosk && npm run build
	@cd src/frontends/panel && npm run build
	@cd src/frontends/monitor && npm run build
	@echo ""
	@echo "Done. Restart 'make backend' — it serves:"
	@echo "    http://<SERVER_IP>:8000/        customer_ui (robot / table tablet)"
	@echo "    http://<SERVER_IP>:8000/kiosk   kiosk cổng"
	@echo "    http://<SERVER_IP>:8000/panel   bảng điều khiển bếp"
	@echo "    http://<SERVER_IP>:8000/monitor màn hình demo giọng nói"

# Local sanity-check of ONE production bundle through Vite's own preview server (its proxy sends
# /api + /ws to :8000). Deploy does not use this — the backend serves dist/ directly, see `build`.
serve:
	@echo "Serving production build on http://0.0.0.0:4173"
	@cd src/frontends/customer_ui && npm run preview -- --host 0.0.0.0 --port 4173

# Orchestrator backend. Defaults to the REAL robot's floorplan (map + table waypoints read from
# the file the robot itself navigates by). For the Gazebo demo, run the same backend against the
# sim restaurant instead:  make backend SIM=1
SIM ?=
backend:
ifeq ($(SIM),)
	@uv run uvicorn src.server_orchestrator.main:app --reload --host 0.0.0.0 --port 8000
else
	@ORCH_FLOORPLAN_PATH=assets/data/floorplan.sim.json \
	uv run uvicorn src.server_orchestrator.main:app --reload --host 0.0.0.0 --port 8000
endif

# Agent (LLM) HTTP service — the brain on the SERVER. The Jetson voice loop
# (src/edge_voice/main.py) POSTs recognised text to POST /chat/stream; this runs the LangGraph
# warehouse agent and mirrors the turn to the monitor screen via the backend's /voice bridge.
#
# NO `reindex` prerequisite. The restaurant brain persisted FAISS/BM25/centroid artifacts that had
# to be rebuilt before every start; the warehouse brain builds its hybrid index IN MEMORY at
# startup from data/inventory.csv (src/agent_brain/warehouse/rag/index.py), so there is nothing to
# rebuild. The old `reindex` target ran scripts/setup.py, which imports
# src.agent_brain.services.retriever — deleted with the restaurant brain — so keeping the
# prerequisite made `make agent` die on ImportError before uvicorn ever bound :8100.
agent:
	@uv run uvicorn src.agent_brain.server:app --host 0.0.0.0 --port 8100

# Edge voice device — runs on the Jetson (or any machine with a mic + speaker). Idles for
# /start_listening commands from the backend's WS hub. Preloads the VAD + STT models at boot
# (slow first import). .env must point AGENT_URL + ORCHESTRATOR_URL at the server.
#
# Runs .venv/bin/python DIRECTLY, not `uv run`: on the Jetson `uv run` syncs the env first, and a
# bare sync uninstalls the hand-built ctranslate2/faster-whisper (docs/guides/jetson-ctranslate2-build.md).
# The venv is already the right one on both machines, so skipping uv costs nothing here.
voice: $(VENV_PY)
	@$(VENV_PY) src/edge_voice/main.py

# Mic → VAD → Whisper only (no server, no TTS): nói vào mic, in ra text. Chạy sau mỗi lần reboot
# hoặc đổi cổng USB để tách bạch lỗi audio khỏi lỗi mạng/agent trước khi chạy `make voice`.
probe: $(VENV_PY)
	@$(VENV_PY) scripts/probe_stt_live.py 2>/dev/null

# Mock robot WS client — stands in for a real Jetson robot to test the dispatcher end-to-end.
# Override id/position: make mockrobot ID=robo-2 ARGS="--x 2.3 --y 0.5".
# It drives to the waypoints of the REAL floorplan by default; against a `make backend SIM=1`
# server run it with ORCH_FLOORPLAN_PATH=assets/data/floorplan.sim.json so both agree.
ID ?= robo-1
mockrobot:
	@uv run python scripts/mock_robot.py --id $(ID) $(ARGS)

# Voice → warehouse-AGV link. Runs on the LAPTOP hosting Gazebo + Nav2 + V-JEPA, in a terminal
# that has already sourced ROS (`source /opt/ros/jazzy/setup.bash`). Listens for the UDP command
# datagrams the Jetson's voice loop sends and drives `warehouse_agv_demo` through the interfaces it
# already exposes — it modifies nothing in that project. See src/robot_link/bridge.py.
#
#   make robotlink                                  # cổng mặc định 45455
#   make robotlink DEMO_DIR=~/warehouse_agv_demo    # sa bàn ở chỗ khác
#   make robotlink ORCH=http://100.66.165.221:8000  # gương trạng thái lên web monitor
#   make robotlink ARGS="--dry-run"                 # in lệnh, không chạy nhiệm vụ thật
DEMO_DIR ?= ../warehouse_agv_demo
UDP_BIND ?= 0.0.0.0:45455
ORCH ?=
robotlink:
	@python3 -m src.robot_link.bridge --demo-dir $(DEMO_DIR) --bind $(UDP_BIND) \
		$(if $(ORCH),--orchestrator $(ORCH),) $(ARGS)

# Train lại bộ phân loại ý định (MLP trên embedding tiếng Việt) từ
# src/agent_brain/warehouse/router/intents.json, lưu vào storage/router/ (gitignored).
# BẮT BUỘC chạy sau khi thêm/sửa ví dụ trong intents.json — nhất là khi thêm lớp mới: model cũ
# chỉ biết các lớp nó từng thấy. In luôn classification_report + confusion matrix để soi lớp nào yếu.
train-router:
	@uv run python -m src.agent_brain.warehouse.router.train

# Gõ câu tiếng Việt, bắn thẳng sang laptop Gazebo — không cần mic, không cần LLM. Cách nhanh
# nhất để tách lỗi robot ra khỏi lỗi âm thanh/mạng.
#   make say TEXT="dẫn tôi đi lấy thùng bia"
#   make say TEXT="qua khu C thôi" DRY=1        # chỉ xem sẽ ra lệnh gì, không gửi
TEXT ?=
DRY ?=
say:
	@test -n '$(TEXT)' || { echo 'Thiếu TEXT, ví dụ: make say TEXT="dừng lại"'; exit 2; }
	@python3 -m src.robot_link.say $(if $(DRY),--dry,) '$(TEXT)'

# Print the whole voice → robot command table (src/robot_link/capabilities.py). Stdlib only.
caps:
	@python3 -m src.robot_link.capabilities

# Check the brain's warehouse data still matches the sa bàn's box layout. Stdlib only — runs on
# any machine, venv or not. Run it after editing data/inventory.csv or semantic_tasks.yaml.
checkmap:
	@python3 scripts/check_warehouse_map.py --demo-dir $(DEMO_DIR)

# Sim robot bridge — drives the Gazebo TurtleBot4 as a REAL dispatcher robot: task.assign →
# Nav2/ArUco delivery → arrived/task_done + map-frame heartbeats (battery fixed 100%).
# Needs Gazebo + Nav2 already up (see docs/run-guide-vi.md) and the workspace built
# (cd robot_ws && colcon build). Point at a remote backend: make simbridge SERVER_HOST=100.x:8000
SERVER_HOST ?= 127.0.0.1:8000
simbridge:
	@cd robot_ws && . /opt/ros/humble/setup.sh && . install/setup.sh && \
	ros2 run ai_sim_bridge task_bridge --ros-args \
		-p server_host:=$(SERVER_HOST) -p robot_id:=$(ID)

# REAL robot, ALL-IN-ONE (one terminal on the Jetson): RTAB-Map localization → Nav2 → the
# dispatcher bridge. This is what a web demo run uses. Park the robot at the DOCK (ArUco 6) before
# starting — the bridge seeds /initialpose there itself, so no "2D Pose Estimate" in RViz.
#   make hwstack SERVER_HOST=100.66.165.221:8000 ID=robo-1
# Jetson, một lệnh cho cả buổi demo. Mặc định = cấu hình demo kho: `voice` + màn rời kiosk mở
# thẳng `/monitor` trên server, KHÔNG bật ROS (robot đứng yên; stack nặng, mà stack chết là kéo cả
# voice chết theo). Script tự `source .venv/bin/activate`, log gắn tiền tố [stack]/[voice]/[web],
# Ctrl-C một lần tắt sạch.
#
#   make jetson STACK=1                                   # thêm RTAB-Map/Nav2 khi cần robot chạy thật
#   make jetson SERVER_HOST=192.168.1.9:8000 ID=robo-2     # server / robot id khác
#   make jetson URL=http://100.66.165.221:8000/panel       # chiếu trang khác lên màn rời
#   make jetson VOICE=0   |   make jetson WEB=0            # bỏ bớt phần nào
VOICE ?= 1
WEB ?= 1
STACK ?= 0
jetson: SERVER_HOST := 100.66.165.221:8000
jetson: ID := robo-1
jetson: $(VENV_PY)
	@SERVER_HOST=$(SERVER_HOST) ID=$(ID) VOICE=$(VOICE) WEB=$(WEB) STACK=$(STACK) \
		$(if $(URL),URL=$(URL),) $(if $(KIOSK_BROWSER),KIOSK_BROWSER=$(KIOSK_BROWSER),) \
		bash scripts/jetson_run.sh

# Waypoints come from tarkbot_robot/config/floorplan.json — the same file the backend reads.
# Demo floor: Table 1 = ArUco 1, dock = ArUco 6; a guest seated at any other table is served at
# Table 1 (the server keeps their real table id). Nav2 is forward-only (min_vel_x=0).
hwstack:
	@cd robot_ws && . /opt/ros/humble/setup.sh && . install/setup.sh && \
	ros2 launch ai_hw_bridge ai_waiter.launch.py \
		server_host:=$(SERVER_HOST) robot_id:=$(ID)

# Just the bridge — for when localization and Nav2 are already up in their own terminals:
#   ros2 launch tarkbot_robot rtabmap_localization.launch.py
#   ros2 launch tarkbot_robot navigation.launch.py
# Field-test the motion with no web at all: ros2 launch tarkbot_robot deliver_test.launch.py
hwbridge:
	@cd robot_ws && . /opt/ros/humble/setup.sh && . install/setup.sh && \
	ros2 run ai_hw_bridge task_bridge --ros-args \
		-p server_host:=$(SERVER_HOST) -p robot_id:=$(ID)

# Re-export the floor the panel minimap draws (restaurant.pgm + .yaml) straight from the RTAB-Map
# database the robot localizes on — same graph, so the minimap and the robot's heartbeat pose can
# never disagree. Run on the Jetson after re-scanning the restaurant, then commit the two files
# (the .db itself is gitignored). Grid/* mirror rtabmap_localization_params.yaml.
RTABMAP_DB ?= $(HOME)/.ros/rtabmap.db
MAP_DIR := robot_ws/src/real/tarkbot_robot/maps
map:
	@. /opt/ros/humble/setup.sh && rtabmap-export --map --opt 2 \
		--output restaurant --output_dir $(MAP_DIR) \
		--Grid/Sensor 0 --Grid/RangeMax 12.0 --Grid/RayTracing true $(RTABMAP_DB)
	@echo "  -> $(MAP_DIR)/restaurant.pgm + .yaml — restart 'make backend' to pick it up"

# Reset all live demo data (orders, seatings, tables → free, robots → seed) via the running
# backend. Panels reload instantly (WS 'reset' event); kiosk reflects on its next table poll.
# Offline alternative (backend stopped): rm storage/db/orchestrator.db — reseeds on next start.
reset:
	@curl -fsS -X POST http://127.0.0.1:8000/admin/reset \
		&& echo "  -> demo data reset" \
		|| echo "  backend not running on :8000 — start 'make backend', or rm storage/db/orchestrator.db"

kill:
	@echo "Stopping dev servers (ports 8000/8100/5173-5176 + voice device)..."
	@-for p in 8000 8100 5173 5174 5175 5176; do \
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
