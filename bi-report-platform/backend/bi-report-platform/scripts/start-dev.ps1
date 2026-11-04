# Starts the database, the API and the React app (two new windows).
#   powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
docker compose up -d

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"
