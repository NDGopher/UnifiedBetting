$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV = "$ROOT\backend\venv\Scripts\python.exe"
$REACT_SCRIPTS = "$ROOT\frontend\node_modules\react-scripts\bin\react-scripts.js"
$FRONTEND_INDEX = "$ROOT\frontend\build\index.html"

Write-Host ""
Write-Host "  Unified Betting - starting up..." -ForegroundColor Cyan
Write-Host ""

# CRA 5 + Node 17+ needs the OpenSSL legacy provider
$env:NODE_OPTIONS = "--openssl-legacy-provider"
$env:CI = "false"
$env:BROWSER = "none"
$env:GENERATE_SOURCEMAP = "false"
$env:DISABLE_ESLINT_PLUGIN = "true"

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

# ── Build dashboard (served by the backend — no second window) ────────────────
if (-not (Test-Path $FRONTEND_INDEX)) {
    Write-Host "  [SETUP] Building dashboard (first run, ~1-2 min)..." -ForegroundColor Yellow
    Push-Location "$ROOT\frontend"
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [SETUP] npm run build failed, retrying via node..." -ForegroundColor Yellow
        node "node_modules\react-scripts\bin\react-scripts.js" build
    }
    Pop-Location
    if (-not (Test-Path $FRONTEND_INDEX)) {
        Write-Host "  ERROR: Dashboard build failed." -ForegroundColor Red
        Write-Host "    cd frontend" -ForegroundColor Yellow
        Write-Host "    `$env:NODE_OPTIONS='--openssl-legacy-provider'" -ForegroundColor Yellow
        Write-Host "    npm run build" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  [SETUP] Dashboard built." -ForegroundColor Green
} else {
    Write-Host "  [SETUP] Dashboard build already present." -ForegroundColor Green
}

# ── Kill anything on port 8000 (ignore errors) ────────────────────────────────
netstat -ano 2>$null | Select-String ":8000 " | ForEach-Object {
    $procId = ($_ -split "\s+") | Select-Object -Last 1
    if ($procId -match "^\d+$") { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
}
Start-Sleep 1

Write-Host ""
Write-Host "  Starting Unified Betting on http://localhost:8000" -ForegroundColor Green
Write-Host "  Press Ctrl+C in this window to stop." -ForegroundColor Green
Write-Host ""

Start-Job -ScriptBlock {
    for ($i = 0; $i -lt 90; $i++) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/healthz" -TimeoutSec 1
            if ($r.StatusCode -eq 200) {
                Start-Process "http://localhost:8000"
                break
            }
        } catch {}
        Start-Sleep 1
    }
} | Out-Null

Set-Location "$ROOT\backend"
& $VENV -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
