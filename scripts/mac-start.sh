#!/usr/bin/env bash
# IMPLUS — Mac quick start
# Run from project root: bash scripts/mac-start.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET}  $*"; }
warn() { echo -e "${YELLOW}!${RESET}  $*"; }
err()  { echo -e "${RED}✗${RESET}  $*"; exit 1; }
info() { echo -e "→  $*"; }

echo ""
echo -e "${BOLD}IMPLUS — Mac Start${RESET}"
echo "────────────────────────────"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ── 1. Check Python ──────────────────────────────────────────────────────────
info "Python..."
PYTHON=""
for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        VER=$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MINOR" -ge 11 ]; then
            PYTHON=$cmd
            ok "Python $VER"
            break
        fi
    fi
done
[ -z "$PYTHON" ] && err "Python 3.11+ required. Install: brew install python@3.12"

# ── 2. Check Node ────────────────────────────────────────────────────────────
info "Node.js..."
command -v node &>/dev/null || err "Node not found. Install: brew install node"
ok "Node $(node --version)"

# ── 3. .env ──────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    warn ".env created — fill in ANTHROPIC_API_KEY and MIND_PASSWORD"
fi

KEY=$(grep "^ANTHROPIC_API_KEY=" .env | cut -d= -f2 || true)
PASS=$(grep "^MIND_PASSWORD=" .env | cut -d= -f2 || true)

if [ -z "$KEY" ] || [ "$KEY" = "sk-ant-..." ]; then
    echo ""
    echo -e "${YELLOW}Нужно заполнить .env${RESET}"
    echo ""
    echo "Открываю .env в TextEdit..."
    sleep 1
    open -e .env
    echo ""
    echo "После сохранения .env — запусти скрипт снова:"
    echo "  bash scripts/mac-start.sh"
    echo ""
    exit 0
fi

if [ -z "$PASS" ] || [ "$PASS" = "your_password_here" ]; then
    echo ""
    warn "MIND_PASSWORD не задан. Открываю .env..."
    open -e .env
    echo "После сохранения — запусти снова: bash scripts/mac-start.sh"
    exit 0
fi

ok ".env настроен"

# ── 4. Install dependencies if needed ────────────────────────────────────────
if [ ! -d backend/.venv ]; then
    info "Создаю virtual environment..."
    $PYTHON -m venv backend/.venv
fi

if [ ! -f backend/.venv/lib/*/site-packages/fastapi/__init__.py ] 2>/dev/null; then
    info "Устанавливаю Python зависимости..."
    backend/.venv/bin/pip install -q --upgrade pip
    backend/.venv/bin/pip install -q -r requirements.txt
    ok "Python зависимости установлены"
fi

if [ ! -d frontend/node_modules ]; then
    info "Устанавливаю Node зависимости..."
    cd frontend && npm install --silent && cd ..
    ok "Node зависимости установлены"
fi

mkdir -p data

# ── 5. Start ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Запускаю IMPLUS...${RESET}"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  Пароль:   $PASS"
echo ""
echo "  Остановить: Ctrl+C"
echo ""

sleep 1
open http://localhost:5173 &

trap 'kill 0' INT TERM
(cd backend && .venv/bin/uvicorn main:app --reload --port 8000 2>&1 | sed 's/^/[back] /') &
(cd frontend && npm run dev 2>&1 | sed 's/^/[front] /') &
wait
