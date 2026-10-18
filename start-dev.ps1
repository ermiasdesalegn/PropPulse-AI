<#
.SYNOPSIS
  PropPulse AI — One-Click Developer Startup Script for Windows PowerShell.

.DESCRIPTION
  Launches all 3 services for local development:
    1. FastAPI Backend (uvicorn on http://localhost:8000)
    2. Telegram Bot Poller (python -m app.poller)
    3. Next.js Frontend (npm run dev on http://localhost:3000)

.EXAMPLE
  .\start-dev.ps1
  .\start-dev.ps1 -Stop
#>

param (
    [switch]$Stop
)

$RootDir = $PSScriptRoot
if (-not $RootDir) {
    $RootDir = Get-Location
}

if ($Stop) {
    Write-Host "`nStopping all PropPulse AI processes..." -ForegroundColor Yellow
    Get-Process -Name "uvicorn", "python", "node" -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -like "*brain3*" -or $_.CommandLine -like "*app.main*" -or $_.CommandLine -like "*app.poller*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "Done.`n" -ForegroundColor Green
    exit 0
}

Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host "  PropPulse AI — Autonomous Real Estate Sales & Lifecycle Agent" -ForegroundColor Yellow
Write-Host "  Starting Full-Stack Local Development Environment..." -ForegroundColor Cyan
Write-Host "================================================================`n" -ForegroundColor Cyan

$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

# 1. Verification
if (-not (Test-Path $PythonExe)) {
    Write-Host "[!] Python venv not found at $PythonExe" -ForegroundColor Red
    Write-Host "    Please run: cd backend; python -m venv .venv; .venv\Scripts\pip install -e ." -ForegroundColor Yellow
    exit 1
}

$BackendEnv = Join-Path $BackendDir ".env"
if (-not (Test-Path $BackendEnv)) {
    Write-Host "[!] backend/.env not found." -ForegroundColor Yellow
    Write-Host "    Copying .env.example to backend/.env..." -ForegroundColor Gray
    Copy-Item (Join-Path $RootDir ".env.example") $BackendEnv
}

# 2. Start FastAPI Backend
Write-Host "[1/3] Starting FastAPI Backend on port 8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='PropPulse - FastAPI Backend (Port 8000)'; cd '$BackendDir'; & '$PythonExe' -m uvicorn app.main:app --reload --port 8000"

# 3. Start Telegram Bot Poller
Write-Host "[2/3] Starting Telegram Poller (@PropPulse1_bot)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='PropPulse - Telegram Poller'; cd '$BackendDir'; & '$PythonExe' -m app.poller"

# 4. Start Next.js Frontend
Write-Host "[3/3] Starting Next.js Frontend on port 3000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='PropPulse - Next.js Frontend (Port 3000)'; cd '$FrontendDir'; npm run dev"

Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host "  All services launched in dedicated console windows!" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  • Command Center Dashboard: " -NoNewline; Write-Host "http://localhost:3000" -ForegroundColor White
Write-Host "  • Agent Test Console:       " -NoNewline; Write-Host "http://localhost:3000/chat" -ForegroundColor White
Write-Host "  • FastAPI API Docs:         " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor White
Write-Host "  • Backend Health Check:     " -NoNewline; Write-Host "http://localhost:8000/healthz" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  To stop all services: close the terminal windows or run:" -ForegroundColor Gray
Write-Host "  .\start-dev.ps1 -Stop`n" -ForegroundColor Yellow
