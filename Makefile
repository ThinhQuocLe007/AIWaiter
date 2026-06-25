# Makefile - Convenience commands for AI Waiter project
# Run 'make help' to see available commands

.PHONY: help setup install update frontend menu kiosk panel backend mockrobot build serve kill reset clean

# Default target
help:
	@echo "AI Waiter - Available commands:"
	@echo ""
	@echo "  make setup      - First-time environment setup (run once)"
	@echo "  make install    - Install/update dependencies after pulling code"
	@echo "  make update     - Pull latest code and reinstall dependencies"
	@echo "  make frontend   - Start all three UIs: menu, kiosk, panel (ports 5173-5175)"
	@echo "  make menu       - Start menu (ordering) dev server (port 5173)"
	@echo "  make kiosk      - Start kiosk check-in dev server (port 5174)"
	@echo "  make panel      - Start kitchen panel dev server (port 5175)"
	@echo "  make build      - Build frontend for production (outputs dist/)"
	@echo "  make serve      - Serve production build locally (port 4173)"
	@echo "  make backend    - Start backend dev server (port 8000)"
	@echo "  make mockrobot  - Start a mock robot WS client (ID=robo-1 ARGS=...) to test the dispatcher"
	@echo "  make reset      - Wipe demo data: clear orders/seatings, free all tables (backend must be running)"
	@echo "  make kill       - Stop all dev servers (backend 8000, frontends 5173-5175)"
	@echo "  make clean      - Remove node_modules and .venv"
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
	@uv sync
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
	@uv run uvicorn src.backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Mock robot WS client — stands in for a real Jetson robot to test the dispatcher end-to-end.
# Override id/position: make mockrobot ID=robo-2 ARGS="--x 2.3 --y 0.5".
ID ?= robo-1
mockrobot:
	@uv run python scripts/mock_robot.py --id $(ID) $(ARGS)

# Reset all live demo data (orders, seatings, tables → free, robots → seed) via the running
# backend. Panels reload instantly (WS 'reset' event); kiosk reflects on its next table poll.
# Offline alternative (backend stopped): rm storage/db/orchestrator.db — reseeds on next start.
reset:
	@curl -fsS -X POST http://127.0.0.1:8000/admin/reset \
		&& echo "  -> demo data reset" \
		|| echo "  backend not running on :8000 — start 'make backend', or rm storage/db/orchestrator.db"

kill:
	@echo "Stopping dev servers (ports 8000, 5173-5175)..."
	@-for p in 8000 5173 5174 5175; do \
		pids=$$(ss -ltnp 2>/dev/null | grep ":$$p " | grep -oP 'pid=\K[0-9]+' | sort -u); \
		if [ -n "$$pids" ]; then kill $$pids 2>/dev/null && echo "  killed port $$p (pid: $$pids)"; fi; \
	done
	@# Bracket trick ([u]vicorn / [v]ite) + token-free echoes so the pattern never
	@# matches this recipe's own shell command line (which would self-terminate make).
	@-pkill -f '[u]vicorn src.backend.app.main' 2>/dev/null && echo "  stopped backend (incl. --reload parent)" || true
	@-pkill -f 'frontends/.*[v]ite' 2>/dev/null && echo "  stopped frontend dev servers" || true
	@echo "Done."

clean:
	@echo "Removing node_modules and .venv directories..."
	@rm -rf src/frontends/customer_ui/node_modules
	@rm -rf src/frontends/kiosk/node_modules
	@rm -rf src/frontends/panel/node_modules
	@rm -rf .venv
	@echo "Done. Run 'make install' to reinstall."
