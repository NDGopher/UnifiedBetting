@echo off
setlocal EnableExtensions
REM Get repo root without trailing backslash (works even if double-clicked)
for /f "delims=" %%i in ("%~dp0.") do set ROOT=%%~fi

echo.
echo  Unified Betting - starting...
echo.

REM ── Prerequisites ──────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo  ERROR: Python is not installed or not on PATH.
        echo  Install Python 3.10+ from https://www.python.org/downloads/
        echo  and check "Add Python to PATH" during setup.
        pause
        exit /b 1
    )
)

where npm >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Node.js / npm is not installed or not on PATH.
    echo  Install the LTS version from https://nodejs.org then open a NEW terminal.
    pause
    exit /b 1
)

REM CRA 5 + Node 17+ needs the OpenSSL legacy provider. CI=false so warnings
REM don't fail the production build.
set "NODE_OPTIONS=--openssl-legacy-provider"
set "CI=false"
set "BROWSER=none"
set "GENERATE_SOURCEMAP=false"
set "DISABLE_ESLINT_PLUGIN=true"

REM ── First-time setup: Python venv ──────────────────────────────────────────
if not exist "%ROOT%\backend\venv\Scripts\python.exe" (
    echo  [SETUP] Creating Python virtualenv...
    py -3 --version >nul 2>&1
    if not errorlevel 1 ( py -3 -m venv "%ROOT%\backend\venv" ) else ( python -m venv "%ROOT%\backend\venv" )
    if not exist "%ROOT%\backend\venv\Scripts\python.exe" (
        echo  ERROR: Failed to create virtualenv.
        pause
        exit /b 1
    )
    echo  [SETUP] Installing Python packages...
    "%ROOT%\backend\venv\Scripts\python.exe" -m pip install --upgrade pip -q
    "%ROOT%\backend\venv\Scripts\python.exe" -m pip install -r "%ROOT%\backend\requirements.txt"
    "%ROOT%\backend\venv\Scripts\python.exe" -m playwright install chromium
    echo  [SETUP] Python environment ready.
)

REM ── First-time setup: frontend node_modules ────────────────────────────────
if not exist "%ROOT%\frontend\node_modules\react-scripts\bin\react-scripts.js" (
    echo  [SETUP] Installing frontend packages (first run, ~2 min)...
    pushd "%ROOT%\frontend"
    call npm ci
    if errorlevel 1 (
        echo  [SETUP] npm ci failed, falling back to npm install...
        call npm install
    )
    if errorlevel 1 (
        echo  [SETUP] Retrying with --legacy-peer-deps...
        call npm install --legacy-peer-deps
    )
    popd
    if not exist "%ROOT%\frontend\node_modules\react-scripts\bin\react-scripts.js" (
        echo  ERROR: Frontend install failed. From this folder run:
        echo    cd frontend
        echo    npm install
        pause
        exit /b 1
    )
    echo  [SETUP] Frontend packages ready.
)

REM ── Build dashboard (served by the backend — no second window) ─────────────
if not exist "%ROOT%\frontend\build\index.html" (
    echo  [SETUP] Building dashboard (first run, ~1-2 min)...
    pushd "%ROOT%\frontend"
    call npm run build
    if errorlevel 1 (
        echo  [SETUP] npm run build failed, retrying via node...
        node node_modules\react-scripts\bin\react-scripts.js build
    )
    popd
    if not exist "%ROOT%\frontend\build\index.html" (
        echo  ERROR: Dashboard build failed.
        echo  From this folder run:
        echo    cd frontend
        echo    set NODE_OPTIONS=--openssl-legacy-provider
        echo    npm run build
        pause
        exit /b 1
    )
    echo  [SETUP] Dashboard built.
) else (
    echo  [SETUP] Dashboard build already present.
)

REM ── Kill stale process on 8000 ─────────────────────────────────────────────
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " 2^>nul') do taskkill /PID %%p /F >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo  Starting Unified Betting on http://localhost:8000
echo  Press Ctrl+C in this window to stop.
echo.

REM Open the browser shortly after uvicorn binds
start "" cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8000"

cd /d "%ROOT%\backend"
"%ROOT%\backend\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
if errorlevel 1 (
    echo.
    echo  Backend exited with an error.
    pause
    exit /b 1
)
