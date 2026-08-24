@echo off
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

REM Newer Node (17+) can break CRA 5 without this OpenSSL flag
set "NODE_OPTIONS=--openssl-legacy-provider"

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

REM ── Kill stale processes on 8000 / 5000 ────────────────────────────────────
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 " 2^>nul') do taskkill /PID %%p /F >nul 2>&1
timeout /t 1 /nobreak >nul

REM ── Launch via PowerShell windows (avoids all cmd quoting issues) ──────────
echo  Starting Backend...
start "UB Backend"  powershell -NoExit -Command "cd '%ROOT%\backend'; & '%ROOT%\backend\venv\Scripts\python.exe' -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"

echo  Starting Frontend...
start "UB Frontend" powershell -NoExit -Command "cd '%ROOT%\frontend'; $env:PORT='5000'; $env:BROWSER='none'; $env:NODE_OPTIONS='--openssl-legacy-provider'; npm start"

echo.
echo  Two PowerShell windows should now be open.
echo  Dashboard : http://localhost:5000
echo  Backend   : http://localhost:8000/healthz
echo.
echo  Waiting 30s for frontend to finish starting...
timeout /t 30 /nobreak >nul
start "" http://localhost:5000
