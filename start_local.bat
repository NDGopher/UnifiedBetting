@echo off
REM Get repo root without trailing backslash (works even if double-clicked)
for /f "delims=" %%i in ("%~dp0.") do set ROOT=%%~fi

echo.
echo  Unified Betting - starting...
echo.

REM ── First-time setup: only runs if venv missing ───────────────────────────────
if not exist "%ROOT%\backend\venv\Scripts\python.exe" (
    echo  [SETUP] First run - building environment, ~5 min...
    py -3 --version >nul 2>&1
    if not errorlevel 1 ( py -3 -m venv "%ROOT%\backend\venv" ) else ( python -m venv "%ROOT%\backend\venv" )
    "%ROOT%\backend\venv\Scripts\python.exe" -m pip install --upgrade pip -q
    "%ROOT%\backend\venv\Scripts\python.exe" -m pip install -r "%ROOT%\backend\requirements.txt"
    "%ROOT%\backend\venv\Scripts\python.exe" -m playwright install chromium
    echo  [SETUP] Done.
)

REM ── Kill stale processes on 8000 / 5000 ──────────────────────────────────────
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " 2^>nul') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 " 2^>nul') do taskkill /PID %%p /F >nul 2>&1
timeout /t 1 /nobreak >nul

REM ── Launch via PowerShell windows (avoids all cmd quoting issues) ─────────────
echo  Starting Backend...
start "UB Backend"  powershell -NoExit -Command "cd '%ROOT%\backend'; & '%ROOT%\backend\venv\Scripts\python.exe' -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"

echo  Starting Frontend...
start "UB Frontend" powershell -NoExit -Command "cd '%ROOT%\frontend'; $env:PORT='5000'; $env:BROWSER='none'; npm start"

echo.
echo  Two PowerShell windows should now be open.
echo  Dashboard : http://localhost:5000
echo.
timeout /t 15 /nobreak >nul
start "" http://localhost:5000
