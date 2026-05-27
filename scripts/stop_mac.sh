#!/usr/bin/env bash
# ==============================================================================
# FinAlly macOS / Linux Teardown Automation Script
# ==============================================================================
set -euo pipefail

# Navigate to the workspace root directory (parent of scripts/)
WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE_ROOT"

echo "============================================================"
echo "          FinAlly Teardown Automation (macOS/Linux)         "
echo "============================================================"

# 1. Verify Docker Daemon accessibility
echo "🔍 Checking Docker status..."
if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker daemon is not running or accessible."
    exit 1
fi

# 2. Stop and purge Docker containers safely
echo "🛑 Stopping and removing containers (SQLite database inside './db' remains preserved)..."
docker compose down

echo ""
echo "✅ FinAlly has been successfully stopped."
echo "============================================================"
