$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV = "$ROOT\backend\venv\Scripts\python.exe"

Write-Host ""
Write-Host "  Unified Betting - starting up..." -ForegroundColor Cyan
Write-Host ""

# ── First-time setup if venv missing ──────────────────────────────────────────
if (-not (Test-Path $VENV)) {
    Write-Host "  [SETUP] First run - this takes about 5 minutes..." -ForegroundColor Yellow
    $py = if (Get-Command "py" -ErrorAction SilentlyContinue) { "py" } else { "python" }
    & $py -3 -m venv "$ROOT\backend\venv"
    & "$VENV" -m pip install --upgrade pip -q
    & "$VENV" -m pip install -r "$ROOT\backend\requirements.txt"
    & "$VENV" -m playwright install chromium
    Write-Host "  [SETUP] Done." -ForegroundColor Green
}

# ── Kill anything on ports 8000 / 5000 (ignore errors) ────────────────────────
netstat -ano 2>$null | Select-String ":8000 " | ForEach-Object {
    $pid = ($_ -split "\s+") | Select-Object -Last 1
    if ($pid -match "^\d+$") { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue }
}
netstat -ano 2>$null | Select-String ":5000 " | ForEach-Object {
    $pid = ($_ -split "\s+") | Select-Object -Last 1
    if ($pid -match "^\d+$") { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue }
}
Start-Sleep 1

# ── Launch both servers ────────────────────────────────────────────────────────
Write-Host "  Starting Backend  (http://localhost:8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Write-Host 'UB Backend' -ForegroundColor Cyan; cd '$ROOT\backend'; & '$VENV' -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"

Write-Host "  Starting Frontend (http://localhost:5000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Write-Host 'UB Frontend' -ForegroundColor Cyan; cd '$ROOT\frontend'; `$env:PORT='5000'; `$env:BROWSER='none'; npm start"

Write-Host ""
Write-Host "  Both windows are opening. Browser in 15 seconds." -ForegroundColor Green
Write-Host "  Dashboard : http://localhost:5000" -ForegroundColor Green
Write-Host ""
Start-Sleep 15
Start-Process "http://localhost:5000"
