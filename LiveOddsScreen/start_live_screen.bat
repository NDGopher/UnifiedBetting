@echo off
setlocal ENABLEDELAYEDEXPANSION
REM Launch the LiveOddsScreen runner headlessly and open the dashboard

REM Resolve repo root from this script's directory (LiveOddsScreen)
set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%.."

REM Ensure selectors.json exists (copy sample on first run)
if not exist "LiveOddsScreen\selectors.json" (
  echo [LiveOddsScreen] Creating selectors.json from sample...
  copy /Y "LiveOddsScreen\selectors.sample.json" "LiveOddsScreen\selectors.json" >nul
)
REM Local config is optional; only create it if user wants to override backend profile
if not exist "LiveOddsScreen\config.json" (
  echo [LiveOddsScreen] Optional: create LiveOddsScreen\config.json if you want to override backend profile.
)

REM Prefer python in PATH; if you need a specific venv, activate it before running this script
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found in PATH. Please open a terminal with Python available and re-run this script.
  pause
  exit /b 1
)

set REFRESH=10
set PORT=8765
echo [LiveOddsScreen] Starting runner (refresh=%REFRESH%s, port=%PORT%)...

start "LiveOddsScreen Runner" cmd /c "python LiveOddsScreen\run_live_screen.py --refresh %REFRESH% --port %PORT%"

REM Give the server a moment to start, then open the dashboard
timeout /t 2 >nul
start "LiveOddsScreen Dashboard" http://127.0.0.1:%PORT%/LiveOddsScreen/dashboard.html

popd
endlocal
