$root = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $root '.local-run'
$pidFiles = @('backend-terminal.pid', 'frontend-terminal.pid')
$stoppedAny = $false
foreach ($name in $pidFiles) {
  $path = Join-Path $runDir $name
  if (Test-Path $path) {
    $raw = (Get-Content $path -Raw).Trim()
    $id = 0
    if ([int]::TryParse($raw, [ref]$id)) {
      $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
      if ($proc) {
        Write-Host "Stopping $name (PID $id)..."
        & taskkill.exe /PID $id /T /F | Out-Null
        $stoppedAny = $true
      }
    }
    Remove-Item $path -Force -ErrorAction SilentlyContinue
  }
}
if (Test-Path $runDir) {
  $remaining = Get-ChildItem $runDir -Force -ErrorAction SilentlyContinue
  if (!$remaining) { Remove-Item $runDir -Force -ErrorAction SilentlyContinue }
}
if ($stoppedAny) {
  Write-Host 'App processes stopped.' -ForegroundColor Green
} else {
  Write-Host 'No app terminals were recorded. If you started them manually, press Ctrl+C in each backend/frontend terminal.' -ForegroundColor Yellow
}
Write-Host 'Your PostgreSQL Windows service was left running so other local apps are not affected.' -ForegroundColor DarkGray
