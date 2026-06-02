#!/usr/bin/env bash
# start.sh — Launch LK Deals (backend + frontend dev server)
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo ""
echo "  🛒  LK Deals — Sri Lanka Bank Supermarket Offers"
echo "  ─────────────────────────────────────────────────"

# Check Python deps
echo "  Checking Python dependencies…"
pip install -r "$BACKEND/requirements.txt" -q --break-system-packages 2>/dev/null || \
  pip install -r "$BACKEND/requirements.txt" -q
playwright install chromium --with-deps 2>/dev/null || playwright install chromium

# Check Node deps
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "  Installing Node dependencies…"
  cd "$FRONTEND" && npm install --silent && cd "$ROOT"
fi

echo ""
echo "  Starting backend  → http://localhost:8000"
echo "  Starting frontend → http://localhost:5173"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Start backend
cd "$BACKEND"
python main.py &
BACKEND_PID=$!

# Start frontend
cd "$FRONTEND"
npm run dev &
FRONTEND_PID=$!

# Open browser after a moment
sleep 2
if command -v open &>/dev/null; then
  open http://localhost:5173
elif command -v xdg-open &>/dev/null; then
  xdg-open http://localhost:5173
fi

# Wait and clean up
trap "echo ''; echo '  Stopping…'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID $FRONTEND_PID
