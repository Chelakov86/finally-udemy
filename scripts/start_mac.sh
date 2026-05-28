#!/usr/bin/env bash
# ==============================================================================
# FinAlly macOS / Linux Startup Automation Script
# ==============================================================================
set -euo pipefail

# Resilient directory navigation to ensure the script executes from workspace root
WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE_ROOT"

echo "============================================================"
echo "          FinAlly Startup Automation (macOS/Linux)          "
echo "============================================================"

# 1. Environment file check and auto-generation
if [ ! -f .env ]; then
    echo "⚠️  .env configuration file not found at root."
    if [ -f .env.example ]; then
        echo "📂 Copying .env.example to .env..."
        cp .env.example .env
        echo "❌ ACTION REQUIRED: Please open '.env' and populate your 'GEMINI_API_KEY'."
        echo "❌ Once configured, rerun this script to complete the deployment."
    else
        echo "❌ Error: '.env.example' is missing. Cannot automatically instantiate '.env'."
    fi
    exit 1
fi

# 2. Verify Docker Daemon accessibility
echo "🔍 Checking Docker status..."
if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker daemon is not running or accessible."
    echo "💡 Please open Docker Desktop (or start the Docker service) and rerun this script."
    exit 1
fi

# 3. Ensure local persistent SQLite storage directory exists
mkdir -p db

# 4. Spin up containerized application idempotently
echo "🚀 Building and launching containers in detached background mode..."
docker compose up --build -d

echo ""
echo "✅ FinAlly is successfully built and launched!"
echo "🌐 UI & API are available at: http://localhost:8000"
echo ""

# 5. Open browser if supported by host CLI
if command -v open >/dev/null 2>&1; then
    echo "🖥️  Launching browser..."
    open http://localhost:8000
elif command -v xdg-open >/dev/null 2>&1; then
    echo "🖥️  Launching browser..."
    xdg-open http://localhost:8000
else
    echo "💡 Open http://localhost:8000 in your browser to view the application."
fi
echo "============================================================"
