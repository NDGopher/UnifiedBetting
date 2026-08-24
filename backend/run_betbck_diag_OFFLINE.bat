@echo off
REM ============================================================
REM SAFE (recommended): analyze Get_SportsLeagues JSON from Chrome
REM NO BetBCK login. NO Lines calls.
REM
REM How to get the JSON:
REM   1. Log into betbck.com in Chrome yourself
REM   2. DevTools -> Network -> filter Get_SportsLeagues
REM   3. Click the request -> Response tab
REM   4. Copy all JSON -> paste into:
REM      backend\data\betbck_diag\from_chrome_Get_SportsLeagues.json
REM   5. Double-click this bat
REM
REM Output: backend\data\betbck_diag\sports_leagues_summary.txt
REM Paste that summary back in chat if needed.
REM ============================================================
cd /d "%~dp0"
if not exist "data\betbck_diag" mkdir "data\betbck_diag"

set INPUT=data\betbck_diag\from_chrome_Get_SportsLeagues.json
if not exist "%INPUT%" (
  echo.
  echo Missing: %INPUT%
  echo.
  echo Create that file by pasting the Get_SportsLeagues Response JSON from Chrome.
  echo Then run this bat again.
  echo.
  pause
  exit /b 1
)

.\venv\Scripts\python.exe tools\betbck_diag_leagues.py offline --input "%INPUT%"
echo.
echo Done. Open: data\betbck_diag\sports_leagues_summary.txt
pause
