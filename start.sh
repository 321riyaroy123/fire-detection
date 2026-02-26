#!/bin/bash
# start.sh — One-command local startup for Smart Fire Detection System
# Usage: ./start.sh [--skip-train]

set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m' YELLOW='\033[1;33m' RED='\033[0;31m' NC='\033[0m'

banner() { echo -e "\n${GREEN}═══════════════════════════════════════${NC}"; echo -e "${GREEN}  $1${NC}"; echo -e "${GREEN}═══════════════════════════════════════${NC}\n"; }
info()   { echo -e "${YELLOW}▶  $1${NC}"; }
ok()     { echo -e "${GREEN}✔  $1${NC}"; }
err()    { echo -e "${RED}✘  $1${NC}"; exit 1; }

banner "Smart Fire Detection System — Local Setup"

# ── Check Python ────────────────────────────────
command -v python3 &>/dev/null || err "Python 3 not found. Install from python.org"
ok "Python $(python3 --version)"

# ── Virtual env ────────────────────────────────
if [ ! -d ".venv" ]; then
  info "Creating virtual environment…"
  python3 -m venv .venv
fi
source .venv/bin/activate
ok "Virtual environment active"

# ── Install deps ───────────────────────────────
info "Installing Python dependencies…"
pip install -q -r backend/requirements.txt
ok "Dependencies installed"

# ── Generate data ──────────────────────────────
if [ ! -f "data/sensor_data.csv" ]; then
  info "Generating synthetic sensor data…"
  python3 data/generate_data.py
  ok "Data generated"
fi

# ── Train model ────────────────────────────────
if [ "$1" != "--skip-train" ] && [ ! -f "backend/models/fire_risk_model.pkl" ]; then
  info "Training ML model…"
  python3 ml/train_model.py
  ok "Model trained"
elif [ "$1" != "--skip-train" ] && [ -f "backend/models/fire_risk_model.pkl" ]; then
  ok "ML model already exists (use --retrain to retrain)"
fi

# ── Start Flask ────────────────────────────────
banner "Starting Server"
info "Flask API + Dashboard → http://localhost:5000"
info "Press Ctrl+C to stop"
echo ""

python3 backend/app.py &
SERVER_PID=$!
sleep 2

# ── Start simulator ───────────────────────────
info "Starting sensor simulator…"
python3 scripts/simulator.py --mode random --interval 2 &
SIM_PID=$!

echo ""
ok "Dashboard: http://localhost:5000"
ok "API:       http://localhost:5000/api/latest"
echo ""
info "Simulator and server running (PIDs: $SERVER_PID, $SIM_PID)"
info "Press Ctrl+C to stop all services"

trap "echo ''; info 'Shutting down…'; kill $SERVER_PID $SIM_PID 2>/dev/null; ok 'Stopped.'" SIGINT SIGTERM
wait
