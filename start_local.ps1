$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV = "$ROOT\backend\venv\Scripts\python.exe"

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host "   UNIFIED BETTING - ONE-CLICK LAUNCH" -ForegroundColor Cyan
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host ""

# ── First-time setup ──────────────────────────────────────────────────────────
if (-not (Test-Path $VENV)) {
    Write-Host "  [SETUP] First run - building environment (~5 min)..." -ForegroundColor Yellow
    $py = if (Get-Command "py" -ErrorAction SilentlyContinue) { "py" } else { "python" }
    & $py -3 -m venv "$ROOT\backend\venv"
    if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] venv creation failed" -ForegroundColor Red; Read-Host "Press Enter"; exit 1 }
    & $VENV -m pip install --upgrade pip -q
    & $VENV -m pip install -r "$ROOT\backend\requirements.txt"
    if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] pip install failed" -ForegroundColor Red; Read-Host "Press Enter"; exit 1 }
    & $VENV -m playwright install chromium
}

# Check playwright installed
$playwrightOk = & $VENV -c "import playwright" 2>$null; $playwrightOk = $LASTEXITCODE -eq 0
if (-not $playwrightOk) {
    Write-Host "  [SETUP] Installing missing packages..." -ForegroundColor Yellow
    & $VENV -m pip install -r "$ROOT\backend\requirements.txt" -q
    & $VENV -m playwright install chromium
}

# Frontend deps
if (-not (Test-Path "$ROOT\frontend\node_modules")) {
    Write-Host "  [SETUP] npm install - first run, ~2 min..." -ForegroundColor Yellow
    Push-Location "$ROOT\frontend"
    npm install --silent
    Pop-Location
}

Write-Host "  [OK] Environment ready" -ForegroundColor Green
Write-Host ""

# ── Kill anything on ports 8000 / 5000 ───────────────────────────────────────
$ports = @(8000, 5000)
foreach ($port in $ports) {
    $procs = netstat -ano | Select-String ":$port " | ForEach-Object {
        ($_ -split "\s+")[-1]
    } | Sort-Object -Unique
    foreach ($pid in $procs) {
        if ($pid -match '^\d+$') {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
}
Start-Sleep 1

# ── Launch servers ────────────────────────────────────────────────────────────
Write-Host "  Starting Backend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT\backend'; & '$VENV' -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"
)

Write-Host "  Starting Frontend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT\frontend'; `$env:PORT='5000'; `$env:BROWSER='none'; npm start"
)

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host "   Both servers launching in new windows." -ForegroundColor Green
Write-Host "   Dashboard  : http://localhost:5000" -ForegroundColor Green
Write-Host "   API docs   : http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Browser opens in 15 seconds. Press Enter to skip." -ForegroundColor Gray
$null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Start-Process "http://localhost:5000"
