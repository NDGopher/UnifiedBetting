@echo off
setlocal EnableDelayedExpansion
title Unified Betting — Local

echo.
echo  ==========================================
echo    UNIFIED BETTING — ONE-CLICK LAUNCH
echo  ==========================================
echo.

REM ── Locate a Python 3.10+ in PATH ──────────────────────────────────────────
set PYTHON=
for %%C in (python python3) do (
    if not defined PYTHON (
        %%C --version >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=2" %%V in ('%%C --version 2^>^&1') do (
                for /f "tokens=1,2 delims=." %%A in ("%%V") do (
                    if %%A GEQ 3 if %%B GEQ 10 set PYTHON=%%C
                )
            )
        )
    )
)
if not defined PYTHON (
    echo  [ERROR] Python 3.10+ not found in PATH.
    echo          Download from https://python.org  (check "Add to PATH")
    pause & exit /b 1
)
echo  [OK] Python: %PYTHON%

REM ── Node / npm check ────────────────────────────────────────────────────────
npm --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Node.js / npm not found.
    echo          Download from https://nodejs.org
    pause & exit /b 1
)
echo  [OK] Node/npm found

REM ── Backend venv ────────────────────────────────────────────────────────────
set VENV=backend\venv
set VENV_PY=%VENV%\Scripts\python.exe

if not exist "%VENV_PY%" (
    echo.
    echo  [SETUP] Creating Python virtual environment...
    %PYTHON% -m venv %VENV%
    if errorlevel 1 ( echo  [ERROR] venv creation failed. & pause & exit /b 1 )
    echo  [SETUP] Installing Python packages (first time, ~2-3 min)...
    %VENV_PY% -m pip install --upgrade pip --quiet
    %VENV_PY% -m pip install -r backend\requirements.txt --quiet
    if errorlevel 1 ( echo  [ERROR] pip install failed. & pause & exit /b 1 )
    echo  [SETUP] Installing Playwright browser (~200 MB, one-time)...
    %VENV_PY% -m playwright install chromium 2>&1
    if errorlevel 1 ( echo  [WARN] Playwright install had issues — browser scraping may fail. )
    echo  [SETUP] Backend ready.
) else (
    REM Venv exists — make sure playwright + httpx are installed (safe to re-run, fast if already present)
    %VENV_PY% -c "import playwright" >nul 2>&1
    if errorlevel 1 (
        echo  [SETUP] Installing missing packages into existing venv...
        %VENV_PY% -m pip install -r backend\requirements.txt --quiet
    )
    REM playwright install is a no-op when browser is already present
    %VENV_PY% -m playwright install chromium >nul 2>&1
)
echo  [OK] Backend venv ready

REM ── Frontend node_modules ───────────────────────────────────────────────────
if not exist "frontend\node_modules" (
    echo.
    echo  [SETUP] Installing frontend packages (first time, ~1-2 min)...
    cd frontend && npm install --quiet && cd ..
    if errorlevel 1 ( echo  [ERROR] npm install failed. & pause & exit /b 1 )
    echo  [SETUP] Frontend ready.
)
echo  [OK] Frontend deps ready

REM ── Clear ports 8000 / 5000 ─────────────────────────────────────────────────
echo.
echo  [1/2] Clearing ports 8000 and 5000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 "') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 "') do taskkill /PID %%p /F >nul 2>&1
timeout /t 1 /nobreak >nul

REM ── Start Backend ────────────────────────────────────────────────────────────
echo  [2/2] Starting servers...
start "UB Backend" cmd /k "title UB Backend && cd backend && ..\%VENV_PY% -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"

REM ── Start Frontend ───────────────────────────────────────────────────────────
start "UB Frontend" cmd /k "title UB Frontend && cd frontend && set PORT=5000 && set BROWSER=none && npm start"

REM ── Open browser after backend warms up ─────────────────────────────────────
echo.
echo  ==========================================
echo    Servers starting in two new windows.
echo    Dashboard will open in ~15 seconds.
echo.
echo    Dashboard : http://localhost:5000
echo    Backend   : http://localhost:8000/docs
echo  ==========================================
echo.
timeout /t 15 /nobreak >nul
start "" "http://localhost:5000"

endlocal
