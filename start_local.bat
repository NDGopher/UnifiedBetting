@echo off
setlocal EnableDelayedExpansion

REM Always run from the folder containing this bat
cd /d "%~dp0"

title Unified Betting
echo.
echo  ============================================
echo    UNIFIED BETTING  -  ONE-CLICK LAUNCH
echo  ============================================
echo.

set ROOT=%~dp0
set VENV_PY=backend\venv\Scripts\python.exe

REM ─────────────────────────────────────────────────────────────────────────────
REM If the venv already exists we have everything we need — skip Python PATH check
REM ─────────────────────────────────────────────────────────────────────────────
if exist "%VENV_PY%" goto :venv_ready

REM ── Venv does not exist yet — need Python to create it ───────────────────────
echo  [CHECK] Looking for Python...

REM Try the Windows Python Launcher first (most reliable on Windows 10/11)
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=py -3
    goto :python_found
)

REM Fall back to plain python
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON=python
    goto :python_found
)

echo.
echo  [ERROR] Python not found.
echo.
echo  Install Python 3.10+ from https://python.org
echo  During install: check the box "Add Python to PATH"
echo  Then close this window and run again.
echo.
pause
exit /b 1

:python_found
for /f "tokens=2" %%V in ('%PYTHON% --version 2^>^&1') do echo  [OK] Python %%V

REM ── npm check (only needed on first run for frontend) ────────────────────────
npm --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Node.js not found.
    echo  Install from https://nodejs.org then run again.
    echo.
    pause
    exit /b 1
)

REM ── Create venv and install everything ───────────────────────────────────────
echo.
echo  [SETUP] Creating virtual environment...
%PYTHON% -m venv backend\venv
if errorlevel 1 (
    echo.
    echo  [ERROR] Could not create virtual environment.
    echo  Check the error above for details.
    echo.
    pause & exit /b 1
)

echo  [SETUP] Installing Python packages  (first run, ~3 min)...
call "%VENV_PY%" -m pip install --upgrade pip --quiet
call "%VENV_PY%" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo.
    echo  [ERROR] pip install failed — see above.
    echo.
    pause & exit /b 1
)

echo  [SETUP] Downloading Playwright browser  (one-time, ~200 MB)...
call "%VENV_PY%" -m playwright install chromium

echo  [SETUP] First-time setup complete!

:venv_ready
echo  [OK] Backend venv ready

REM ── Ensure playwright is installed in the venv (catches the missing-package case)
call "%VENV_PY%" -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo  [SETUP] Installing missing packages (playwright/httpx)...
    call "%VENV_PY%" -m pip install -r backend\requirements.txt --quiet
    call "%VENV_PY%" -m playwright install chromium
)

REM ── Frontend node_modules ────────────────────────────────────────────────────
if not exist "frontend\node_modules" (
    echo.
    echo  [SETUP] Installing frontend packages  (first run, ~2 min)...
    pushd frontend
    call npm install
    popd
    if errorlevel 1 (
        echo.
        echo  [ERROR] npm install failed.
        echo.
        pause & exit /b 1
    )
)
echo  [OK] Frontend deps ready

REM ── Kill anything on ports 8000 / 5000 ───────────────────────────────────────
echo.
echo  Clearing ports 8000 / 5000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " 2^>nul') do (
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 " 2^>nul') do (
    taskkill /PID %%p /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

REM ── Write helper scripts (avoids quote-nesting inside start "...") ────────────
(
    echo @echo off
    echo cd /d "%ROOT%backend"
    echo "%ROOT%backend\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
) > "%ROOT%_ub_backend_run.bat"

(
    echo @echo off
    echo cd /d "%ROOT%frontend"
    echo set PORT=5000
    echo set BROWSER=none
    echo npm start
) > "%ROOT%_ub_frontend_run.bat"

REM ── Launch ───────────────────────────────────────────────────────────────────
echo  Starting Backend...
start "UB Backend"  cmd /k ""%ROOT%_ub_backend_run.bat""

echo  Starting Frontend...
start "UB Frontend" cmd /k ""%ROOT%_ub_frontend_run.bat""

echo.
echo  ============================================
echo   Servers are starting in two new windows.
echo   Browser opens automatically in ~15 sec.
echo.
echo   Dashboard : http://localhost:5000
echo   API docs  : http://localhost:8000/docs
echo  ============================================
echo.
timeout /t 15 /nobreak >nul
start "" "http://localhost:5000"
