# One-time setup for Windows. Run from the project folder in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "Missing: $cmd. $hint" -ForegroundColor Red; exit 1
  }
}
Need "docker" "Install Docker Desktop and start it."
Need "node"   "Install Node.js 22 LTS from nodejs.org."
Need "py"     "Install Python 3.12 from python.org (tick 'Add python.exe to PATH')."

Write-Host "`n[1/5] Starting PostgreSQL in Docker..." -ForegroundColor Cyan
docker compose up -d
Start-Sleep -Seconds 5

Write-Host "`n[2/5] Creating Python virtual environment..." -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "`n[3/5] Creating backend .env with a random secret..." -ForegroundColor Cyan
if (-not (Test-Path ".env")) {
  $secret = & ".\.venv\Scripts\python.exe" -c "import secrets; print(secrets.token_urlsafe(48))"
  (Get-Content ".env.example") -replace "JWT_SECRET=.*", "JWT_SECRET=$secret" | Set-Content ".env"
}

Write-Host "`n[4/5] Creating tables (Alembic), demo accounts and sample data..." -ForegroundColor Cyan
# app.migrate runs `alembic upgrade head`; a database from before Alembic is stamped first.
& ".\.venv\Scripts\python.exe" -m app.migrate
if ($LASTEXITCODE -ne 0) { Write-Host "Database migration failed. Read the error above." -ForegroundColor Red; exit 1 }
& ".\.venv\Scripts\python.exe" -m app.seed

Write-Host "`n[5/5] Installing frontend packages..." -ForegroundColor Cyan
Set-Location "$root\frontend"
npm install

Set-Location $root
Write-Host "`nSetup complete. Start the app with:  .\scripts\start-dev.ps1" -ForegroundColor Green
