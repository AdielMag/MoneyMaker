#!/bin/bash
# Run Dashboard Locally - Connect to GCP Orchestrator
# Usage: ./scripts/run_dashboard_local.sh https://your-orchestrator-url.run.app

set -e

ORCHESTRATOR_URL="${1:-}"
PORT="${PORT:-8080}"
HOST="${HOST:-127.0.0.1}"

if [ -z "$ORCHESTRATOR_URL" ]; then
    echo "Error: Orchestrator URL is required"
    echo "Usage: ./scripts/run_dashboard_local.sh <ORCHESTRATOR_URL> [PORT] [HOST]"
    echo "Example: ./scripts/run_dashboard_local.sh https://orchestrator-abc123.run.app 8080 127.0.0.1"
    exit 1
fi

echo "========================================"
echo "MoneyMaker Dashboard - Local Development"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Set environment variables
export ORCHESTRATOR_URL="$ORCHESTRATOR_URL"
export PORT="$PORT"
export HOST="$HOST"
export PYTHONPATH="$(pwd)"

echo ""
echo "Configuration:"
echo "  Dashboard URL: http://$HOST:$PORT"
echo "  Orchestrator URL: $ORCHESTRATOR_URL"
echo ""
echo "Starting dashboard..."
echo "Press Ctrl+C to stop"
echo ""

# Run from project root
uvicorn services.dashboard.main:app --host "$HOST" --port "$PORT" --reload
