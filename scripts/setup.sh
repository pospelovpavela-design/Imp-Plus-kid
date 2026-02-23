#!/usr/bin/env bash
# IMPLUS — macOS/Linux setup script
# Usage: bash scripts/setup.sh

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET}  $*"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $*"; }
err()  { echo -e "${RED}✗${RESET}  $*" >&2; exit 1; }
info() { echo -e "→  $*"; }

echo ""
echo -e "${BOLD}IMPLUS — Setup${RESET}"
echo "────────────────────────────────────────"

# ── Working directory ─────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
info "Project root: $ROOT_DIR"

# ── Python ────────────────────────────────────────────────────────────────────
info "Checking Python..."
PYTHON=""
for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        VER=$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 11 ]; then
            PYTHON=$cmd
            ok "Python $VER ($cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    err "Python 3.11+ required. Install via Homebrew: brew install python@3.12"
fi

# ── Node.js ───────────────────────────────────────────────────────────────────
info "Checking Node.js..."
if ! command -v node &>/dev/null; then
    err "Node.js not found. Install via Homebrew: brew install node"
fi
NODE_VER=$(node -e 'console.log(process.versions.node.split(".")[0])')
if [ "$NODE_VER" -lt 18 ]; then
    err "Node.js 18+ required (found $NODE_VER). Upgrade: brew upgrade node"
fi
ok "Node.js $(node --version)"

# ── .env ─────────────────────────────────────────────────────────────────────
info "Setting up .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    warn ".env created from .env.example"
    echo ""
    echo -e "   ${BOLD}Required:${RESET} edit .env and set:"
    echo "     ANTHROPIC_API_KEY=sk-ant-..."
    echo "     MIND_PASSWORD=your_secret_password"
    echo ""
else
    ok ".env exists"
fi

# ── Python venv ───────────────────────────────────────────────────────────────
info "Setting up Python virtual environment..."
if [ ! -d backend/.venv ]; then
    $PYTHON -m venv backend/.venv
    ok "Created backend/.venv"
else
    ok "backend/.venv already exists"
fi

info "Installing Python dependencies..."
backend/.venv/bin/pip install -q --upgrade pip
backend/.venv/bin/pip install -q -r requirements.txt
ok "Python dependencies installed"

# ── Node dependencies ─────────────────────────────────────────────────────────
info "Installing Node.js dependencies..."
cd frontend && npm install --silent && cd ..
ok "Node.js dependencies installed"

# ── SQLite data dir ───────────────────────────────────────────────────────────
mkdir -p data
ok "data/ directory ready"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Setup complete.${RESET}"
echo "────────────────────────────────────────"
echo ""

# Check if .env is actually configured
ANTHROPIC_OK=false
PASSWORD_OK=false
grep -q "^ANTHROPIC_API_KEY=sk-" .env 2>/dev/null && ANTHROPIC_OK=true
grep -q "^MIND_PASSWORD=." .env 2>/dev/null && PASSWORD_OK=true

if $ANTHROPIC_OK && $PASSWORD_OK; then
    echo -e "${GREEN}Ready to run!${RESET}"
    echo ""
    echo "  Terminal 1:  make backend   (or: cd backend && .venv/bin/uvicorn main:app --reload --port 8000)"
    echo "  Terminal 2:  make frontend  (or: cd frontend && npm run dev)"
    echo "  Browser:     http://localhost:5173"
else
    warn "Before running, edit .env:"
    $ANTHROPIC_OK || echo "     ANTHROPIC_API_KEY=sk-ant-..."
    $PASSWORD_OK  || echo "     MIND_PASSWORD=your_password"
    echo ""
    echo "  Then: make backend  (Terminal 1)"
    echo "        make frontend (Terminal 2)"
fi
echo ""
