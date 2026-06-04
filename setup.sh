#!/bin/bash
# setup.sh - One-command environment setup for AI Waiter project
# Compatible with Ubuntu 22.04 LTS

set -e  # Exit immediately on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI Waiter - Environment Setup         ${NC}"
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

# Step 4: Setup frontend dependencies (customer_ui touchscreen app)
echo -e "${YELLOW}[4/5] Setting up frontend (src/frontends/customer_ui)...${NC}"
FRONTEND_DIR="src/frontends/customer_ui"
if [ -d "$FRONTEND_DIR" ] && [ -f "$FRONTEND_DIR/package.json" ]; then
    cd "$FRONTEND_DIR"
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
        echo -e "${GREEN}Created $FRONTEND_DIR/.env from template${NC}"
    fi
    cd - > /dev/null
    echo -e "${GREEN}Frontend setup complete${NC}"
else
    echo -e "${YELLOW}Frontend not scaffolded yet (no package.json in $FRONTEND_DIR), skipping...${NC}"
    echo -e "${YELLOW}Run 'npm create vue@latest .' inside $FRONTEND_DIR to scaffold it.${NC}"
fi

# Step 5: Setup backend dependencies (if a backend folder is added later)
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
    cd - > /dev/null
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
echo "     cd src/frontends/customer_ui && npm run dev"
echo ""
echo "  3. Start the backend dev server (once a backend exists):"
echo "     cd backend && uv run uvicorn main:app --reload"
echo ""
echo -e "${BLUE}Or use the Makefile shortcuts:${NC}"
echo "     make frontend    # Run frontend"
echo "     make backend     # Run backend"
echo ""
