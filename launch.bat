@echo off
echo.
echo ========================================
echo   UNIFIED BETTING APP - ONE CLICK
echo ========================================
echo.
echo Starting Unified Betting Application...
echo.

REM Always use venv Python for launch.py to ensure all dependencies are available
set VENV_PYTHON=backend\venv\Scripts\python.exe

REM Check if venv exists, if not run setup first
if not exist %VENV_PYTHON% (
    echo Virtual environment not found. Running setup...
    echo.
    python setup_dependencies.py
    if errorlevel 1 (
        echo.
        echo Setup failed! Please check the errors above.
        pause
        exit /b 1
    )
    echo.
)

REM Use venv Python to run launch.py (this ensures all dependencies are available)
echo Using virtual environment Python...
%VENV_PYTHON% launch.py

REM If launcher fails, try setup and retry
if errorlevel 1 (
    echo.
    echo Launcher failed. Running setup first...
    echo.
    python setup_dependencies.py
    if errorlevel 1 (
        echo.
        echo Setup failed! Please check the errors above.
        pause
        exit /b 1
    )
    echo.
    echo Setup completed. Trying launcher again...
    echo.
    %VENV_PYTHON% launch.py
)

pause
