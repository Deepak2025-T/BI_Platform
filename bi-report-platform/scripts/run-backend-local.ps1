$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
Set-Location $backend
Write-Host 'Starting BI Report Platform API at http://localhost:8000' -ForegroundColor Cyan
& $python -m uvicorn app.main:app --reload --port 8000
if ($LASTEXITCODE -ne 0) { Write-Host "Backend exited with code $LASTEXITCODE" -ForegroundColor Red }
