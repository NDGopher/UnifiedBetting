@echo off
echo.
echo ==========================================
echo   UNIFIED BETTING - AUTO BETTOR
echo ==========================================
echo.
echo Connecting to backend at http://localhost:8000
echo Listening for +EV POD alerts via SSE stream...
echo.
echo [DRY RUN by default — no bets placed]
echo To go live add:  --no-dry-run --customer-id YOUR_ID --password YOUR_PASS
echo.

set VENV_PY=backend\venv\Scripts\python.exe

if not exist %VENV_PY% (
    echo [ERROR] Virtual environment not found. Run setup_dependencies.py first.
    pause
    exit /b 1
)

REM Install auto-bettor deps if needed
%VENV_PY% -c "import sseclient" 2>nul || (
    echo Installing sseclient-py...
    %VENV_PY% -m pip install sseclient-py >nul
)
%VENV_PY% -c "import playwright" 2>nul || (
    echo Installing playwright...
    %VENV_PY% -m pip install playwright >nul
    %VENV_PY% -m playwright install chromium >nul
)

REM Launch auto-bettor (dry-run, 4% min EV, $50 stake)
%VENV_PY% auto_bettor\auto_bettor.py ^
    --backend http://localhost:8000 ^
    --min-ev 4.0 ^
    --stake 50

pause
