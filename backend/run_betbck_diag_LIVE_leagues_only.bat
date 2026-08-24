@echo off
REM ============================================================
REM CAREFUL LIVE DIAG (only if offline is hard):
REM   - 1 login
REM   - 1 Get_SportsLeagues
REM   - NO Lines probes by default
REM
REM Do NOT run this repeatedly. Once is enough.
REM Prefer run_betbck_diag_OFFLINE.bat when possible.
REM ============================================================
cd /d "%~dp0"
if not exist "data\betbck_diag" mkdir "data\betbck_diag"

echo.
echo This will login ONCE and fetch Get_SportsLeagues ONCE.
echo Press Ctrl+C to cancel, or
pause

.\venv\Scripts\python.exe tools\betbck_diag_leagues.py live
echo.
echo Wrote:
echo   data\betbck_diag\sports_leagues_raw.json
echo   data\betbck_diag\sports_leagues_summary.txt
echo   data\betbck_diag\sport_filter_matches.json
echo.
echo Paste sports_leagues_summary.txt in chat if you want a review.
pause
