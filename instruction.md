# Project Setup Instructions for Claude

## Context

This is a **robot restaurant delivery system** project. The robot has an integrated touchscreen where users can browse the menu and order food via voice or button taps.

I'm working on the **frontend** while my teammate works on other parts. We need a reproducible development environment so that when either of us clones the repo, running a single setup script will create an identical environment.

## Team Environment (Both Developers)

- **OS**: Ubuntu 22.04.5 LTS
- **Python**: 3.10 (system default, also used by ROS2 and existing `.venv`)
- **Node.js**: 22.x (managed via nvm)
- **Package managers**: `uv` for Python, `npm` for Node.js

## Project Structure to Create

The project root already contains code from my teammate. I need to add a `frontend/` folder and supporting setup files. The final structure should look like this:

```
<project-root>/
├── frontend/                    # NEW - Vue 3 frontend (I will create this manually)
│   ├── .env.example
│   ├── package.json
│   └── ... (Vue files)
├── backend/                     # May already exist or be added later
│   ├── .env.example
│   ├── .python-version
│   └── pyproject.toml
├── .nvmrc                       # NEW - Lock Node.js version
├── .gitignore                   # NEW or UPDATE - Exclude env-specific files
├── setup.sh                     # NEW - One-command environment setup
├── Makefile                     # NEW - Convenience commands
├── README.md                    # NEW or UPDATE - Setup and usage instructions
└── instruction.md               # This file (do not modify)
```

## Files to Generate

Please create the following files. **All commands and comments inside files must be in English.**

---

### 1. `.nvmrc` (at project root)

Single line file specifying Node.js version:

```
22
```

---

### 2. `.gitignore` (at project root)

If a `.gitignore` already exists, **merge** these entries with existing content (do not duplicate). If not, create it fresh:

```gitignore
# Dependencies
node_modules/
.venv/
venv/
__pycache__/
*.pyc
*.pyo

# Build outputs
dist/
build/
.vite/
*.egg-info/

# Environment files - DO NOT COMMIT
.env
.env.local
.env.production
.env.*.local
**/.env
**/.env.local
**/.env.production

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db
desktop.ini

# Logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Cache
.cache/
.parcel-cache/
.pytest_cache/
.ruff_cache/
.mypy_cache/

# Coverage
coverage/
.coverage
htmlcov/
```

---

### 3. `setup.sh` (at project root)

Bash script that automates environment setup. Must be executable. All output messages should be in English.

```bash
#!/bin/bash
# setup.sh - One-command environment setup for Robot Restaurant project
# Compatible with Ubuntu 22.04 LTS

set -e  # Exit immediately on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Robot Restaurant - Environment Setup  ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check OS
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo -e "${RED}Error: This project requires Linux (Ubuntu 22.04 recommended)${NC}"
    exit 1
fi

# Step 1: Install nvm if not present
echo -e "${YELLOW}[1/5] Checking nvm installation...${NC}"
export NVM_DIR="$HOME/.nvm"

if [ ! -d "$NVM_DIR" ]; then
    echo -e "${YELLOW}Installing nvm v0.40.4...${NC}"
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
    \. "$NVM_DIR/nvm.sh"
else
    echo -e "${GREEN}nvm already installed${NC}"
    \. "$NVM_DIR/nvm.sh"
fi

# Step 2: Install Node.js version from .nvmrc
echo -e "${YELLOW}[2/5] Installing Node.js (from .nvmrc)...${NC}"
nvm install
nvm use
echo -e "${GREEN}Node.js version: $(node -v)${NC}"
echo -e "${GREEN}npm version: $(npm -v)${NC}"

# Step 3: Install uv if not present
echo -e "${YELLOW}[3/5] Checking uv installation...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add uv to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"
else
    echo -e "${GREEN}uv already installed: $(uv --version)${NC}"
fi

# Step 4: Setup frontend dependencies (if frontend folder exists)
echo -e "${YELLOW}[4/5] Setting up frontend...${NC}"
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    cd frontend
    if [ -f "package-lock.json" ]; then
        echo "Installing frontend dependencies with npm ci..."
        npm ci
    else
        echo "No package-lock.json found, running npm install..."
        npm install
    fi
    # Copy .env.example to .env if .env does not exist
    if [ -f ".env.example" ] && [ ! -f ".env" ]; then
        cp .env.example .env
        echo -e "${GREEN}Created frontend/.env from template${NC}"
    fi
    cd ..
    echo -e "${GREEN}Frontend setup complete${NC}"
else
    echo -e "${YELLOW}Frontend folder not found, skipping...${NC}"
fi

# Step 5: Setup backend dependencies (if backend folder exists)
echo -e "${YELLOW}[5/5] Setting up backend...${NC}"
if [ -d "backend" ] && [ -f "backend/pyproject.toml" ]; then
    cd backend
    echo "Syncing Python dependencies with uv..."
    uv sync
    # Copy .env.example to .env if .env does not exist
    if [ -f ".env.example" ] && [ ! -f ".env" ]; then
        cp .env.example .env
        echo -e "${GREEN}Created backend/.env from template${NC}"
    fi
    cd ..
    echo -e "${GREEN}Backend setup complete${NC}"
else
    echo -e "${YELLOW}Backend folder not found or no pyproject.toml, skipping...${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup completed successfully!         ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo ""
echo "  1. Reload your shell or run:"
echo "     source ~/.bashrc"
echo ""
echo "  2. Start the frontend dev server:"
echo "     cd frontend && npm run dev"
echo ""
echo "  3. Start the backend dev server (in another terminal):"
echo "     cd backend && uv run uvicorn main:app --reload"
echo ""
echo -e "${BLUE}Or use the Makefile shortcuts:${NC}"
echo "     make frontend    # Run frontend"
echo "     make backend     # Run backend"
echo ""
```

**Important**: After creating this file, mark it as executable by including this note in the README or running `chmod +x setup.sh`.

---

### 4. `Makefile` (at project root)

Use **TAB indentation** (not spaces) - this is critical for Makefile syntax.

```makefile
# Makefile - Convenience commands for Robot Restaurant project
# Run 'make help' to see available commands

.PHONY: help setup install update frontend backend clean

# Default target
help:
	@echo "Robot Restaurant - Available commands:"
	@echo ""
	@echo "  make setup      - First-time environment setup (run once)"
	@echo "  make install    - Install/update dependencies after pulling code"
	@echo "  make update     - Pull latest code and reinstall dependencies"
	@echo "  make frontend   - Start frontend dev server"
	@echo "  make backend    - Start backend dev server"
	@echo "  make clean      - Remove node_modules and .venv"
	@echo ""

setup:
	@chmod +x setup.sh
	@./setup.sh

install:
	@echo "Installing frontend dependencies..."
	@if [ -d "frontend" ]; then cd frontend && npm ci; fi
	@echo "Installing backend dependencies..."
	@if [ -d "backend" ]; then cd backend && uv sync; fi
	@echo "Done."

update:
	@git pull
	@$(MAKE) install

frontend:
	@cd frontend && npm run dev

backend:
	@cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

clean:
	@echo "Removing node_modules and .venv directories..."
	@rm -rf frontend/node_modules
	@rm -rf backend/.venv
	@echo "Done. Run 'make install' to reinstall."
```

---

### 5. `README.md` (at project root)

If a `README.md` already exists with project description, **append** the setup section. If creating fresh, use this content:

```markdown
# Robot Restaurant Delivery System

A robot delivery system for restaurants with an integrated touchscreen UI. Users can browse the menu and place orders via voice or touch input.

## Tech Stack

- **Frontend**: Vue 3 + Vite + PrimeVue + Tailwind CSS
- **Backend**: FastAPI + Python 3.10
- **Robot Control**: ROS2 + Nav2
- **LLM**: Local inference via Ollama (on Jetson Orin Nano)

## System Requirements

- Ubuntu 22.04 LTS
- Git
- Internet connection (for initial setup)

## Quick Start

### First-time setup

After cloning the repository, run the setup script once:

```bash
git clone <repository-url>
cd <repository-name>
chmod +x setup.sh
./setup.sh
```

This will automatically:
- Install nvm (Node Version Manager) if not present
- Install Node.js v22 via nvm
- Install uv (Python package manager) if not present
- Install all frontend dependencies (`npm ci`)
- Install all backend dependencies (`uv sync`)
- Create `.env` files from templates

After setup completes, reload your shell:

```bash
source ~/.bashrc
```

### Running the project

Open two terminals:

**Terminal 1 - Frontend**:
```bash
cd frontend
npm run dev
# Opens at http://localhost:5173
```

**Terminal 2 - Backend**:
```bash
cd backend
uv run uvicorn main:app --reload
# API at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

Or use the Makefile shortcuts:

```bash
make frontend    # Terminal 1
make backend     # Terminal 2
```

## Daily Workflow

### After pulling new code from the repository

Always reinstall dependencies in case `package-lock.json` or `uv.lock` changed:

```bash
make update
```

Or manually:

```bash
git pull
cd frontend && npm ci && cd ..
cd backend && uv sync && cd ..
```

### Adding a new dependency

**Frontend (npm)**:
```bash
cd frontend
npm install <package-name>
# This updates package.json and package-lock.json
git add package.json package-lock.json
git commit -m "feat: add <package-name>"
```

**Backend (uv)**:
```bash
cd backend
uv add <package-name>
# This updates pyproject.toml and uv.lock
git add pyproject.toml uv.lock
git commit -m "feat: add <package-name>"
```

**Important**: Always commit lock files (`package-lock.json`, `uv.lock`) together with the manifest files (`package.json`, `pyproject.toml`).

## Environment Variables

Both `frontend/` and `backend/` use `.env` files for configuration. These files are **never committed** to git.

When you first clone the repo, `setup.sh` automatically creates `.env` from `.env.example`. Edit the values in `.env` to match your local setup.

To see what variables are required, check:
- `frontend/.env.example`
- `backend/.env.example`

## Project Structure

```
.
├── frontend/              # Vue 3 application
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── package-lock.json  # Locked dependency versions (COMMIT)
│   ├── .env               # Local config (DO NOT COMMIT)
│   └── .env.example       # Template (COMMIT)
├── backend/               # FastAPI application
│   ├── pyproject.toml
│   ├── uv.lock            # Locked dependency versions (COMMIT)
│   ├── .python-version    # Python version (COMMIT)
│   ├── .env               # Local config (DO NOT COMMIT)
│   └── .env.example       # Template (COMMIT)
├── .nvmrc                 # Node.js version (COMMIT)
├── .gitignore
├── setup.sh               # One-command setup script
├── Makefile               # Convenience commands
└── README.md
```

## Troubleshooting

### `npm ci` fails with "lock file is outdated"

This means `package.json` was changed but `package-lock.json` was not updated. Run:

```bash
cd frontend
rm package-lock.json
npm install
git add package-lock.json
git commit -m "fix: regenerate package-lock.json"
```

### `nvm: command not found` after running setup.sh

Reload your shell:

```bash
source ~/.bashrc
# or close and reopen the terminal
```

### Python version mismatch

The project requires Python 3.10 (Ubuntu 22.04 default). Check:

```bash
python3 --version
# Should print Python 3.10.x
```

If `uv` complains about Python version, it will automatically download the correct version.

### Port already in use

Default ports:
- Frontend: 5173
- Backend: 8000

If a port is busy, you can change it:
- Frontend: edit `vite.config.ts`
- Backend: change `--port` in the run command

## License

[Your license here]
```

---

### 6. `frontend/.env.example` (template for frontend env vars)

Create this file as a template. The actual `frontend/.env` will be created by `setup.sh`.

```bash
# Frontend environment variables
# All variables must be prefixed with VITE_ to be exposed to the browser

# Backend API URL
VITE_API_URL=http://localhost:8000

# WebSocket URL for streaming (LLM responses, robot status)
VITE_WS_URL=ws://localhost:8000/ws

# ROS2 rosbridge WebSocket URL (for robot navigation commands)
VITE_ROS_BRIDGE_URL=ws://localhost:9090

# App display name
VITE_APP_NAME=Robot Restaurant

# Feature flags
VITE_ENABLE_VOICE=true
VITE_ENABLE_DEBUG_PANEL=false
```

---

### 7. `backend/.env.example` (template for backend env vars)

Only create this file if the `backend/` folder exists. If my teammate hasn't created it yet, skip this file but note in your output that it should be created later.

```bash
# Backend environment variables

# Server configuration
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000

# CORS allowed origins (comma-separated)
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# LLM configuration (Ollama on Jetson Orin Nano)
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=qwen2.5:3b-instruct-q4_K_M

# ROS2 bridge configuration
ROS_BRIDGE_HOST=localhost
ROS_BRIDGE_PORT=9090

# Database (if used)
DATABASE_URL=sqlite:///./robot.db

# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

---

### 8. `backend/.python-version` (only if backend folder exists)

```
3.10
```

---

## Important Instructions for Claude

When generating these files, please:

1. **Check existing files first**: If `.gitignore`, `README.md`, or any other file already exists in the repo, **merge** content intelligently. Do not overwrite my teammate's work.

2. **Preserve existing project content**: If there are existing folders (like `backend/`, ROS2 packages, etc.), do not modify them. Only add the new files listed above.

3. **All file content in English**: Comments, error messages, log output - everything in English.

4. **Make `setup.sh` executable**: After creating it, the file should have execute permissions. Note this in your summary so I can run `chmod +x setup.sh` if needed.

5. **Verify file paths**: 
   - `.nvmrc`, `.gitignore`, `setup.sh`, `Makefile`, `README.md`, `instruction.md` → at **project root**
   - `frontend/.env.example` → inside `frontend/` folder (create folder if needed)
   - `backend/.env.example` and `backend/.python-version` → inside `backend/` folder (only if it exists)

6. **After generation, provide a summary** that includes:
   - List of files created
   - List of files modified (if any)
   - Commands I need to run to verify setup works:
     ```bash
     chmod +x setup.sh
     ./setup.sh
     ```
   - Files I should commit to git (and which ones should NOT be committed)

7. **Do not create the actual Vue project files** - I will run `npm create vue@latest frontend` manually after this setup.

8. **Do not create the `frontend/` folder contents** beyond `.env.example` - the Vue scaffold will populate it.

## Verification

After generating all files, I should be able to:

1. Run `./setup.sh` and have it complete without errors (it will skip frontend/backend folders if they don't exist yet)
2. Commit the new files to git
3. Have my teammate pull the latest commit, run `./setup.sh`, and end up with an identical environment

## Summary of Goal

Create a **one-command setup experience** so that any team member can clone the repo and run `./setup.sh` to get a working development environment matching mine exactly. Lock files (`package-lock.json`, `uv.lock`) ensure dependency versions are identical across machines.
