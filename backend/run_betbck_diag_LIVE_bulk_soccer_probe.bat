@echo off
REM ============================================================
REM OPTIONAL: live leagues + ONE bulk-soccer probe
REM Tests if SportType=SOCCER with empty subtype returns all boards
REM (if yes, EV can avoid dozens of league clicks — much safer).
REM Total: 1 login + 1 leagues + 1 Lines call. Run once only.
REM ============================================================
cd /d "%~dp0"
if not exist "data\betbck_diag" mkdir "data\betbck_diag"

echo.
echo This does 1 login + 1 leagues list + 1 bulk SOCCER lines pull.
echo Press Ctrl+C to cancel, or
pause

.\venv\Scripts\python.exe tools\betbck_diag_leagues.py live --probe-bulk-soccer
echo.
echo Check probe_bulk_soccer_lines.json — if Lines count is large,
echo bulk soccer works and we can avoid per-league spam.
pause
