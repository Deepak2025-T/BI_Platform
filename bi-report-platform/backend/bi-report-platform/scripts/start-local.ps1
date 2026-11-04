$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
$runDir = Join-Path $root '.local-run'

Write-Host "BI Report Platform - local startup (no Docker)" -ForegroundColor Cyan
Write-Host "Project: $root"

if (!(Test-Path $python)) { throw "Python environment not found: $python. Create backend\.venv and install backend\requirements.txt first." }
if (!(Test-Path (Join-Path $backend '.env'))) { throw "backend\.env was not found. Create it and set DATABASE_URL first." }
if (!(Test-Path (Join-Path $frontend 'package.json'))) { throw "Frontend package.json was not found." }
if (!$npm) { throw "npm.cmd was not found. Install Node.js and reopen this terminal." }

# Confirm PostgreSQL is reachable on the project's configured local port.
$tcp = New-Object System.Net.Sockets.TcpClient
try {
  $connect = $tcp.BeginConnect('127.0.0.1', 5432, $null, $null)
  if (!$connect.AsyncWaitHandle.WaitOne(2500, $false) -or !$tcp.Connected) {
    throw 'PostgreSQL is not listening on 127.0.0.1:5432. Start your local PostgreSQL service first.'
  }
} finally { $tcp.Close() }

# Avoid starting duplicate copies.
$health = $false
try { $r = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; if ($r.status -eq 'ok') { $health = $true } } catch {}
$frontUp = $false
try { $null = Invoke-WebRequest 'http://127.0.0.1:5173/' -TimeoutSec 2; $frontUp = $true } catch {}
if ($health -and $frontUp) {
  Write-Host 'Frontend and backend are already running.' -ForegroundColor Green
  Start-Process 'http://localhost:5173/'
  exit 0
}

New-Item -ItemType Directory -Path $runDir -Force | Out-Null

Write-Host '[1/3] Applying database migrations and demo data...' -ForegroundColor Cyan
# Python needs the backend folder as its working directory to import the app package.
Push-Location $backend
try {
  # Runs `alembic upgrade head`; a database from before Alembic is stamped first.
  & $python -m app.migrate
  if ($LASTEXITCODE -ne 0) { throw "Database migration failed (exit code $LASTEXITCODE). Check backend\.env, PostgreSQL credentials, and the error above." }
  & $python -m app.seed
  if ($LASTEXITCODE -ne 0) { throw "Database initialization failed (exit code $LASTEXITCODE). Check backend\.env, PostgreSQL credentials, and the error above." }
} finally {
  Pop-Location
}

Write-Host '[2/3] Starting FastAPI backend...' -ForegroundColor Cyan
$backendRunner = Join-Path $PSScriptRoot 'run-backend-local.ps1'
$backendProc = Start-Process powershell.exe -PassThru -WorkingDirectory $root -ArgumentList @('-NoExit','-ExecutionPolicy','Bypass','-File', $backendRunner)
Set-Content (Join-Path $runDir 'backend-terminal.pid') $backendProc.Id

Write-Host '[3/3] Starting React frontend...' -ForegroundColor Cyan
$frontendRunner = Join-Path $PSScriptRoot 'run-frontend-local.ps1'
$frontendProc = Start-Process powershell.exe -PassThru -WorkingDirectory $root -ArgumentList @('-NoExit','-ExecutionPolicy','Bypass','-File', $frontendRunner)
Set-Content (Join-Path $runDir 'frontend-terminal.pid') $frontendProc.Id

Write-Host 'Waiting for the local servers...' -ForegroundColor Cyan
$backendReady = $false
for ($i = 0; $i -lt 25; $i++) {
  Start-Sleep -Seconds 1
  try { $r = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; if ($r.status -eq 'ok') { $backendReady = $true; break } } catch {}
}
Start-Sleep -Seconds 2
Start-Process 'http://localhost:5173/'
if ($backendReady) {
  Write-Host 'App started. Frontend: http://localhost:5173 | API: http://localhost:8000/docs' -ForegroundColor Green
  Write-Host 'To stop the app, double-click stop-local.bat.' -ForegroundColor Yellow
} else {
  Write-Warning 'The app windows were opened, but the backend health check did not pass yet. Check the backend terminal for errors.'
}
