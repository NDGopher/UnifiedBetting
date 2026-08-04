@echo off
setlocal EnableDelayedExpansion
title Unified Betting — Local

REM ── Always run from the folder where this bat lives ─────────────────────────
cd /d "%~dp0"

echo.
echo  ==========================================
echo    UNIFIED BETTING — ONE-CLICK LAUNCH
echo  ==========================================
echo.

REM ── Python check (any 3.x) ───────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found in PATH.
    echo          Download from https://python.org  (check "Add to PATH")
    echo          Then close and re-open this window.
    pause & exit /b 1
)
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PY_VER=%%V
echo  [OK] Python %PY_VER%

REM ── Node / npm check ─────────────────────────────────────────────────────────
npm --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Node.js / npm not found.
    echo          Download from https://nodejs.org
    pause & exit /b 1
)
echo  [OK] Node/npm found

REM ── Backend venv ─────────────────────────────────────────────────────────────
set VENV=backend\venv
set VENV_PY=%VENV%\Scripts\python.exe

if not exist "%VENV_PY%" (
    echo.
    echo  [SETUP] Creating Python virtual environment...
    python -m venv %VENV%
    if errorlevel 1 ( echo  [ERROR] venv creation failed. & pause & exit /b 1 )

    echo  [SETUP] Installing Python packages ^(first time ~2-3 min^)...
    %VENV_PY% -m pip install --upgrade pip --quiet
    %VENV_PY% -m pip install -r backend\requirements.txt --quiet
    if errorlevel 1 ( echo  [ERROR] pip install failed. & pause & exit /b 1 )

    echo  [SETUP] Downloading Playwright browser ^(~200 MB, one-time^)...
    %VENV_PY% -m playwright install chromium
    echo  [SETUP] Backend ready.
) else (
    REM Venv exists — ensure playwright + httpx are present
    %VENV_PY% -c "import playwright" >nul 2>&1
    if errorlevel 1 (
        echo  [SETUP] Installing missing packages into existing venv...
        %VENV_PY% -m pip install -r backend\requirements.txt --quiet
        %VENV_PY% -m playwright install chromium
    )
)
echo  [OK] Backend venv ready

REM ── Frontend node_modules ────────────────────────────────────────────────────
if not exist "frontend\node_modules" (
    echo.
    echo  [SETUP] Installing frontend packages ^(first time ~1-2 min^)...
    cd frontend && npm install --quiet && cd ..
    if errorlevel 1 ( echo  [ERROR] npm install failed. & pause & exit /b 1 )
    echo  [SETUP] Frontend ready.
)
echo  [OK] Frontend deps ready

REM ── Clear ports 8000 / 5000 ──────────────────────────────────────────────────
echo.
echo  [1/2] Clearing ports 8000 and 5000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 "') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 "') do taskkill /PID %%p /F >nul 2>&1
timeout /t 1 /nobreak >nul

REM ── Start servers ─────────────────────────────────────────────────────────────
echo  [2/2] Starting servers...
start "UB Backend"  cmd /k "title UB Backend  && cd /d "%~dp0backend"  && ..\%VENV_PY% -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"
start "UB Frontend" cmd /k "title UB Frontend && cd /d "%~dp0frontend" && set PORT=5000 && set BROWSER=none && npm start"

REM ── Open dashboard after backend warms up ────────────────────────────────────
echo.
echo  ==========================================
echo    Servers are starting in two windows.
echo    Browser will open in ~15 seconds.
echo.
echo    Dashboard : http://localhost:5000
echo    Backend   : http://localhost:8000/docs
echo  ==========================================
echo.
timeout /t 15 /nobreak >nul
start "" "http://localhost:5000"

endlocal
