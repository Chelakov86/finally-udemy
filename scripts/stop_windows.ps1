# ==============================================================================
# FinAlly Windows Teardown Automation PowerShell Script
# ==============================================================================
$ErrorActionPreference = "Stop"

# Determine workspace root cleanly relative to scripts folder
$WorkspaceRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $WorkspaceRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "            FinAlly Teardown Automation (Windows)           " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Check Docker daemon status
Write-Host "🔍 Checking Docker Desktop status..." -ForegroundColor Gray
try {
    & docker info 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not active"
    }
} catch {
    Write-Host "❌ Error: Docker daemon is not running or accessible." -ForegroundColor Red
    Exit 1
}

# 2. Stop and tear down docker compose environment
Write-Host "🛑 Stopping and removing containers (SQLite database inside './db' remains preserved)..." -ForegroundColor Yellow
& docker compose down

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ FinAlly has been successfully stopped." -ForegroundColor Green
} else {
    Write-Host "❌ Error: 'docker compose down' failed with exit code $LASTEXITCODE." -ForegroundColor Red
    Exit 1
}
Write-Host "============================================================" -ForegroundColor Cyan
