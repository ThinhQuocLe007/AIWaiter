# Makefile - Convenience commands for AI Waiter project
# Run 'make help' to see available commands

.PHONY: help setup install update frontend backend build serve clean

# Default target
help:
	@echo "AI Waiter - Available commands:"
	@echo ""
	@echo "  make setup      - First-time environment setup (run once)"
	@echo "  make install    - Install/update dependencies after pulling code"
	@echo "  make update     - Pull latest code and reinstall dependencies"
	@echo "  make frontend   - Start frontend dev server (customer_ui)"
	@echo "  make build      - Build frontend for production (outputs dist/)"
	@echo "  make serve      - Serve production build locally (port 4173)"
	@echo "  make backend    - Start backend dev server"
	@echo "  make clean      - Remove node_modules and .venv"
	@echo ""

setup:
	@chmod +x setup.sh
	@./setup.sh

install:
	@echo "Installing frontend dependencies..."
	@if [ -f "frontends/customer_ui/package.json" ]; then cd frontends/customer_ui && npm ci; else echo "frontends/customer_ui not scaffolded yet, skipping."; fi
	@echo "Installing backend dependencies..."
	@if [ -f "backend/pyproject.toml" ]; then cd backend && uv sync; else echo "backend not present yet, skipping."; fi
	@echo "Done."

update:
	@git pull
	@$(MAKE) install

frontend:
	@cd frontends/customer_ui && npm run dev

build:
	@echo "Building frontend for production..."
	@cd frontends/customer_ui && npm run build
	@echo "Done. Output in frontends/customer_ui/dist/"

serve:
	@echo "Serving production build on http://0.0.0.0:4173"
	@cd frontends/customer_ui && npm run preview -- --host 0.0.0.0 --port 4173

backend:
	@cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

clean:
	@echo "Removing node_modules and .venv directories..."
	@rm -rf frontends/customer_ui/node_modules
	@rm -rf backend/.venv
	@echo "Done. Run 'make install' to reinstall."
