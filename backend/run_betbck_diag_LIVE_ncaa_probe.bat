@echo off
REM ============================================================
REM OPTIONAL: live leagues + ONE NCAA COLLEGE lines probe
REM Total: 1 login + 1 Get_SportsLeagues + 1 Get_LeagueLines2
REM Run at most once when checking NCAA Football EV.
REM ============================================================
cd /d "%~dp0"
if not exist "data\betbck_diag" mkdir "data\betbck_diag"

echo.
echo This does 1 login + 1 leagues list + 1 COLLEGE lines pull.
echo Press Ctrl+C to cancel, or
pause

.\venv\Scripts\python.exe tools\betbck_diag_leagues.py live --probe-ncaa
echo.
echo Check:
echo   data\betbck_diag\sports_leagues_summary.txt
echo   data\betbck_diag\probe_ncaa_college_lines.json
pause
