$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root 'frontend'
Set-Location $frontend
Write-Host 'Starting React/Vite at http://localhost:5173' -ForegroundColor Cyan
& npm.cmd run dev
if ($LASTEXITCODE -ne 0) { Write-Host "Frontend exited with code $LASTEXITCODE" -ForegroundColor Red }
