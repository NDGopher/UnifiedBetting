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

set VENV_PY=backend\venv\Scripts\python.exe

REM ── If venv already exists, skip straight to launching ───────────────────────
if exist "%VENV_PY%" goto :launch

REM ── First-time setup: need Python + npm to build the venv ────────────────────
echo  [CHECK] First-time setup needed...
echo.

py -3 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON=py -3 & goto :python_ok )
python --version >nul 2>&1
if not errorlevel 1 ( set PYTHON=python & goto :python_ok )

echo  [ERROR] Python not found.
echo  Install Python 3.10+ from https://python.org
echo  Tick "Add Python to PATH" during install, then run this again.
echo.
pause & exit /b 1

:python_ok
for /f "tokens=2" %%V in ('%PYTHON% --version 2^>^&1') do echo  [OK] Python %%V

npm --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Node.js not found. Install from https://nodejs.org
    echo.
    pause & exit /b 1
)
echo  [OK] npm found

echo.
echo  [SETUP] Creating virtual environment...
%PYTHON% -m venv backend\venv
if errorlevel 1 ( echo  [ERROR] venv creation failed. & pause & exit /b 1 )

echo  [SETUP] Installing Python packages  (first run ~3 min)...
call "%VENV_PY%" -m pip install --upgrade pip --quiet
call "%VENV_PY%" -m pip install -r backend\requirements.txt
if errorlevel 1 ( echo  [ERROR] pip install failed. & pause & exit /b 1 )

echo  [SETUP] Downloading Playwright browser  (one-time ~200 MB)...
call "%VENV_PY%" -m playwright install chromium
echo  [SETUP] Setup complete!
echo.

:launch
REM ── Ensure playwright is present (catches missing-package on existing venv) ──
call "%VENV_PY%" -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo  [SETUP] Installing missing packages...
    call "%VENV_PY%" -m pip install -r backend\requirements.txt --quiet
    call "%VENV_PY%" -m playwright install chromium
)
echo  [OK] Backend ready

REM ── Frontend node_modules ────────────────────────────────────────────────────
if not exist "frontend\node_modules" (
    echo  [SETUP] Installing frontend packages  (first run ~2 min)...
    pushd frontend && call npm install --quiet && popd
    if errorlevel 1 ( echo  [ERROR] npm install failed. & pause & exit /b 1 )
)
echo  [OK] Frontend ready

REM ── Clear ports 8000 / 5000 ──────────────────────────────────────────────────
echo.
echo  Clearing ports 8000 / 5000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 " 2^>nul') do taskkill /PID %%p /F >nul 2>&1
timeout /t 1 /nobreak >nul

REM ── Launch (helper bats avoid all cmd /k quoting issues) ─────────────────────
echo  Starting servers...
start "UB Backend"  cmd /k ""%~dp0_start_backend.bat""
start "UB Frontend" cmd /k ""%~dp0_start_frontend.bat""

echo.
echo  ============================================
echo   Servers starting. Browser opens in 15 sec.
echo   Dashboard : http://localhost:5000
echo   API docs  : http://localhost:8000/docs
echo  ============================================
echo.
timeout /t 15 /nobreak >nul
start "" "http://localhost:5000"
