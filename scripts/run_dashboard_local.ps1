# Run Dashboard Locally - Connect to GCP Orchestrator
# Usage: .\scripts\run_dashboard_local.ps1 -OrchestratorUrl "https://your-orchestrator-url.run.app"

param(
    [Parameter(Mandatory=$true)]
    [string]$OrchestratorUrl,
    
    [int]$Port = 8080,
    [string]$Host = "127.0.0.1"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MoneyMaker Dashboard - Local Development" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Install/upgrade dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Set environment variables
$env:ORCHESTRATOR_URL = $OrchestratorUrl
$env:PORT = $Port
$env:HOST = $Host
$env:PYTHONPATH = (Get-Location).Path

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Green
Write-Host "  Dashboard URL: http://$Host`:$Port" -ForegroundColor White
Write-Host "  Orchestrator URL: $OrchestratorUrl" -ForegroundColor White
Write-Host ""
Write-Host "Starting dashboard..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Run from project root
uvicorn services.dashboard.main:app --host $Host --port $Port --reload
