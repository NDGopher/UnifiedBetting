$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV = "$ROOT\backend\venv\Scripts\python.exe"
$REACT_SCRIPTS = "$ROOT\frontend\node_modules\react-scripts\bin\react-scripts.js"

Write-Host ""
Write-Host "  Unified Betting - starting up..." -ForegroundColor Cyan
Write-Host ""

# Newer Node (17+) can break CRA 5 without this OpenSSL flag
$env:NODE_OPTIONS = "--openssl-legacy-provider"

# ── Prerequisites ─────────────────────────────────────────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "  ERROR: Python is not installed or not on PATH." -ForegroundColor Red
    Write-Host "  Install Python 3.10+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "  ERROR: Node.js / npm is not installed or not on PATH." -ForegroundColor Red
    Write-Host "  Install the LTS version from https://nodejs.org then open a NEW terminal." -ForegroundColor Yellow
    exit 1
}

# ── First-time setup if venv missing ──────────────────────────────────────────
if (-not (Test-Path $VENV)) {
    Write-Host "  [SETUP] Creating Python virtualenv..." -ForegroundColor Yellow
    $py = if (Get-Command "py" -ErrorAction SilentlyContinue) { "py" } else { "python" }
    & $py -3 -m venv "$ROOT\backend\venv"
    if (-not (Test-Path $VENV)) {
        Write-Host "  ERROR: Failed to create virtualenv." -ForegroundColor Red
        exit 1
    }
    Write-Host "  [SETUP] Installing Python packages..." -ForegroundColor Yellow
    & "$VENV" -m pip install --upgrade pip -q
    & "$VENV" -m pip install -r "$ROOT\backend\requirements.txt"
    & "$VENV" -m playwright install chromium
    Write-Host "  [SETUP] Python environment ready." -ForegroundColor Green
}

# ── First-time setup: frontend node_modules ───────────────────────────────────
if (-not (Test-Path $REACT_SCRIPTS)) {
    Write-Host "  [SETUP] Installing frontend packages (first run, ~2 min)..." -ForegroundColor Yellow
    Push-Location "$ROOT\frontend"
    npm ci
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [SETUP] npm ci failed, falling back to npm install..." -ForegroundColor Yellow
        npm install
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [SETUP] Retrying with --legacy-peer-deps..." -ForegroundColor Yellow
        npm install --legacy-peer-deps
    }
    Pop-Location
    if (-not (Test-Path $REACT_SCRIPTS)) {
        Write-Host "  ERROR: Frontend install failed. From this folder run:" -ForegroundColor Red
        Write-Host "    cd frontend" -ForegroundColor Yellow
        Write-Host "    npm install" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  [SETUP] Frontend packages ready." -ForegroundColor Green
}

# ── Kill anything on ports 8000 / 5000 (ignore errors) ────────────────────────
netstat -ano 2>$null | Select-String ":8000 " | ForEach-Object {
    $procId = ($_ -split "\s+") | Select-Object -Last 1
    if ($procId -match "^\d+$") { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
}
netstat -ano 2>$null | Select-String ":5000 " | ForEach-Object {
    $procId = ($_ -split "\s+") | Select-Object -Last 1
    if ($procId -match "^\d+$") { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
}
Start-Sleep 1

# ── Launch both servers ────────────────────────────────────────────────────────
Write-Host "  Starting Backend  (http://localhost:8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Write-Host 'UB Backend' -ForegroundColor Cyan; cd '$ROOT\backend'; & '$VENV' -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"

Write-Host "  Starting Frontend (http://localhost:5000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Write-Host 'UB Frontend' -ForegroundColor Cyan; cd '$ROOT\frontend'; `$env:PORT='5000'; `$env:BROWSER='none'; `$env:NODE_OPTIONS='--openssl-legacy-provider'; npm start"

Write-Host ""
Write-Host "  Both windows are opening. Browser in 15 seconds." -ForegroundColor Green
Write-Host "  Dashboard : http://localhost:5000" -ForegroundColor Green
Write-Host "  Backend   : http://localhost:8000/healthz" -ForegroundColor Green
Write-Host ""
Start-Sleep 15
Start-Process "http://localhost:5000"
