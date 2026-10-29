#!/usr/bin/env bash
set -e

echo "============================================================"
echo "⚡ Starting LedgerLens AP Copilot (Linux / macOS)"
echo "============================================================"

# Check if Docker is installed and running
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo "🐳 Docker detected! Launching with Docker Compose..."
    docker compose up --build -d
    echo ""
    echo "✅ Running at: http://localhost:8000"
    echo "To stop: docker compose down"
    exit 0
fi

# Fallback to local python setup
echo "🐍 Docker not found. Using local Python environment..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install Python 3 or Docker."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

echo "📦 Installing / verifying dependencies..."
.venv/bin/pip install -q -r requirements.txt

echo "🚀 Starting server..."
echo "Access LedgerLens at: http://localhost:8000"
.venv/bin/python run.py
