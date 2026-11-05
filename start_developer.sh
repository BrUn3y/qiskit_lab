#!/bin/bash

export DEVELOPER_MODEL="${DEVELOPER_MODEL:-ollama:granite4.2:8b}"

# Start the Quantum Developer Agent.
# Port: 8001
# Model: Granite 4.2 8B through Ollama

echo "=================================="
echo "🎯 Quantum Developer Agent"
echo "=================================="
echo ""
echo "Starting the quantum code specialist agent..."
echo "Port: 8001"
echo "Model: $DEVELOPER_MODEL"
echo ""
echo "Press Ctrl+C to stop"
echo "=================================="
echo ""

# Activate the virtual environment if available.
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Start the Developer Agent and preserve its output for view_logs.sh.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${AGENT_LOG_DIR:-$SCRIPT_DIR/.logs}"
mkdir -p "$LOG_DIR"
: > "$LOG_DIR/developer.log"
set -o pipefail
PYTHONUNBUFFERED=1 uv run python3 -m beeai_agents.quantum_developer_agent 2>&1 | tee -a "$LOG_DIR/developer.log"

# Made with Bob
