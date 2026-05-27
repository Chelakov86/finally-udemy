# ==============================================================================
# FinAlly Windows Startup Automation PowerShell Script
# ==============================================================================
$ErrorActionPreference = "Stop"

# Determine workspace root cleanly relative to scripts folder
$WorkspaceRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $WorkspaceRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "             FinAlly Startup Automation (Windows)           " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Environment validation & creation
$EnvFile = Join-Path $WorkspaceRoot ".env"
$EnvExample = Join-Path $WorkspaceRoot ".env.example"

if (-not (Test-Path $EnvFile)) {
    Write-Host "⚠️  .env configuration file not found at root." -ForegroundColor Yellow
    if (Test-Path $EnvExample) {
        Write-Host "📂 Copying .env.example to .env..." -ForegroundColor Gray
        Copy-Item $EnvExample $EnvFile
        Write-Host "❌ ACTION REQUIRED: Please edit '.env' at '$EnvFile' and populate your 'GEMINI_API_KEY'." -ForegroundColor Red
        Write-Host "❌ Once configured, rerun this script to complete deployment." -ForegroundColor Red
    } else {
        Write-Host "❌ Error: '.env.example' is missing. Cannot automatically instantiate '.env'." -ForegroundColor Red
    }
    Exit 1
}

# 2. Check Docker daemon status
Write-Host "🔍 Checking Docker Desktop status..." -ForegroundColor Gray
try {
    & docker info 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not active"
    }
} catch {
    Write-Host "❌ Error: Docker daemon is not running or accessible." -ForegroundColor Red
    Write-Host "💡 Please open Docker Desktop and ensure it is fully started before running this script." -ForegroundColor Yellow
    Exit 1
}

# 3. Initialize persistent database folder
$DbDir = Join-Path $WorkspaceRoot "db"
if (-not (Test-Path $DbDir)) {
    New-Item -ItemType Directory -Force -Path $DbDir | Out-Null
}

# 4. Spin up containerized application
Write-Host "🚀 Building and launching containers in detached background mode..." -ForegroundColor Green
& docker compose up --build -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ FinAlly is successfully built and launched!" -ForegroundColor Green
    Write-Host "🌐 UI & API are available at: http://localhost:8000" -ForegroundColor Cyan
    Write-Host ""
    
    # 5. Launch browser
    try {
        Write-Host "🖥️  Launching default browser..." -ForegroundColor Gray
        Start-Process "http://localhost:8000"
    } catch {
        Write-Host "💡 Open http://localhost:8000 in your browser to view the application." -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ Error: 'docker compose up' failed with exit code $LASTEXITCODE." -ForegroundColor Red
    Exit 1
}
Write-Host "============================================================" -ForegroundColor Cyan
