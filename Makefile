.PHONY: install setup backend frontend dev check-env

# ── Setup ─────────────────────────────────────────────────────────────────────

install: setup
	@echo ""
	@echo "✓  IMPLUS installed. Next steps:"
	@echo "   1. Edit .env  (set MIND_PASSWORD + GROQ_API_KEY)"
	@echo "   2. make backend    (Terminal 1)"
	@echo "   3. make frontend   (Terminal 2)"
	@echo "   4. Open http://localhost:5173"

setup:
	@echo "→  Checking .env..."
	@[ -f .env ] || (cp .env.example .env && echo "   Created .env — edit it before running")
	@echo "→  Creating Python virtual environment..."
	@cd backend && python3 -m venv .venv
	@echo "→  Installing Python dependencies..."
	@cd backend && .venv/bin/pip install -q --upgrade pip && \
	    .venv/bin/pip install -q -r ../requirements.txt
	@echo "→  Installing Node.js dependencies..."
	@cd frontend && npm install --silent
	@echo "✓  Dependencies installed."

# ── Run ───────────────────────────────────────────────────────────────────────

backend: check-env
	@echo "→  Backend: http://localhost:8000"
	cd backend && .venv/bin/uvicorn main:app --reload --port 8000

frontend:
	@echo "→  Frontend: http://localhost:5173"
	cd frontend && npm run dev

# Run both in the current terminal (Ctrl+C stops both)
dev: check-env
	@echo "→  Starting backend (:8000) and frontend (:5173)"
	@echo "   Press Ctrl+C to stop both."
	@trap 'kill 0' INT; \
	 (cd backend && .venv/bin/uvicorn main:app --reload --port 8000 2>&1 | sed 's/^/[backend] /') & \
	 (cd frontend && npm run dev 2>&1 | sed 's/^/[frontend] /') & \
	 wait

# ── Helpers ───────────────────────────────────────────────────────────────────

check-env:
	@[ -f .env ] || (echo "✗  .env not found. Run: make setup"; exit 1)
	@grep -q "^GROQ_API_KEY=gsk_" .env 2>/dev/null || \
	    (echo "✗  Set GROQ_API_KEY in .env (get it at https://console.groq.com/keys)"; exit 1)
	@grep -q "^MIND_PASSWORD=" .env 2>/dev/null || \
	    (echo "✗  Set MIND_PASSWORD in .env"; exit 1)

# Reset the mind (deletes SQLite DB — mind is reborn)
reset-mind:
	@echo "⚠  This will delete data/mind.db and reset the mind's memory."
	@read -p "   Type 'yes' to confirm: " yn && [ "$$yn" = "yes" ] || exit 1
	rm -f data/mind.db
	@echo "✓  Mind reset. Run 'make backend' to start fresh."
