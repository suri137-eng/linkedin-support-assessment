# Runs the assessment server using the local virtual environment.
# Usage:  ./run.ps1        (port comes from .env PORT, else $env:PORT, else 8000)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $here

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    py -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

# Resolve the port: explicit $env:PORT wins, then PORT= in .env, else 8000.
$port = $env:PORT
if (-not $port -and (Test-Path ".env")) {
    $line = Select-String -Path ".env" -Pattern '^\s*PORT\s*=\s*(\d+)' | Select-Object -First 1
    if ($line) { $port = $line.Matches[0].Groups[1].Value }
}
if (-not $port) { $port = "8000" }

# Warn if the chosen port is already in use.
if (Get-NetTCPConnection -State Listen -LocalPort ([int]$port) -ErrorAction SilentlyContinue) {
    Write-Host "WARNING: port $port is already in use. Stop the process using it, or set a different PORT in .env." -ForegroundColor Yellow
}

Write-Host "Starting on http://localhost:$port  (Ctrl+C to stop)" -ForegroundColor Green
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port $port
