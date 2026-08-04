@echo off
cd /d "%~dp0"
echo.
echo  Unified Betting - starting up...
echo  (this window will close when both server windows open)
echo.

set VENV=%~dp0backend\venv\Scripts\python.exe

REM ── First-time setup ─────────────────────────────────────────────────────────
if not exist "%VENV%" (
    echo [SETUP] First run - building environment. Takes ~5 min.
    py -3 --version >nul 2>&1
    if not errorlevel 1 ( set PY=py -3 ) else ( set PY=python )
    %PY% -m venv "%~dp0backend\venv"
    if errorlevel 1 ( echo [ERROR] Could not create venv & pause & exit /b 1 )
    "%VENV%" -m pip install --upgrade pip -q
    "%VENV%" -m pip install -r "%~dp0backend\requirements.txt"
    if errorlevel 1 ( echo [ERROR] pip install failed & pause & exit /b 1 )
    "%VENV%" -m playwright install chromium
)

"%VENV%" -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing missing packages...
    "%VENV%" -m pip install -r "%~dp0backend\requirements.txt" -q
    "%VENV%" -m playwright install chromium
)

if not exist "%~dp0frontend\node_modules" (
    echo [SETUP] npm install (first run ~2 min)...
    pushd "%~dp0frontend" && call npm install -q && popd
)

REM ── Kill stale processes on our ports ────────────────────────────────────────
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 " 2^>nul') do taskkill /PID %%p /F >nul 2>&1
timeout /t 1 /nobreak >nul

REM ── Launch servers ────────────────────────────────────────────────────────────
REM NOTE: No quotes around %VENV% - path has no spaces so none needed,
REM       and inner quotes would break the outer cmd /k "..." string.
start "UB Backend"  cmd /k "cd /d %~dp0backend  && %VENV% -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"
start "UB Frontend" cmd /k "cd /d %~dp0frontend && set PORT=5000 && set BROWSER=none && npm start"

echo  Both server windows launched.
echo  Dashboard opens at http://localhost:5000 in 15 seconds.
timeout /t 15 /nobreak >nul
start "" http://localhost:5000
