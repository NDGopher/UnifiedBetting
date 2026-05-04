@echo off
echo.
echo ==========================================
echo   UNIFIED BETTING - LOCAL LAUNCH
echo ==========================================
echo.

REM ---- Paths ----
set VENV_PY=backend\venv\Scripts\python.exe
set NODE_CMD=npm

REM ---- Check venv exists ----
if not exist %VENV_PY% (
    echo [ERROR] Virtual environment not found at %VENV_PY%
    echo         Run setup first:  setup_dependencies.bat
    pause
    exit /b 1
)

REM ---- Kill anything already on ports 8000 / 5000 ----
echo [1/3] Clearing ports 8000 and 5000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 "') do (
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 "') do (
    taskkill /PID %%p /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

REM ---- Backend (port 8000) ----
echo [2/3] Starting backend on http://localhost:8000 ...
start "UB Backend" cmd /k "cd backend && ..\%VENV_PY% -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"

REM ---- Wait for backend to be ready ----
echo       Waiting for backend...
timeout /t 5 /nobreak >nul

REM ---- Frontend (port 5000) — BROWSER=none prevents auto-open ----
echo [3/3] Starting frontend on http://localhost:5000 ...
start "UB Frontend" cmd /k "cd frontend && set PORT=5000 && set BROWSER=none && npm start"

echo.
echo ==========================================
echo   Both servers starting in new windows.
echo.
echo   Dashboard : http://localhost:5000
echo   Backend   : http://localhost:8000
echo.
echo   No browser opens automatically.
echo   Open these yourself in Chrome:
echo     1. http://localhost:5000  (dashboard)
echo     2. pinnacleoddsdropper.com  (with Odds Dropper extension)
echo     3. betbck.com
echo.
echo   Extension must have Backend URL set to blank (localhost mode)
echo   or your remote server URL if running Replit.
echo ==========================================
echo.
