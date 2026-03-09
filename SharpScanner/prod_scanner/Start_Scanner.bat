@echo off
REM ========================================
REM Sports Liquidity Scanner - One-Click Launcher
REM ========================================

REM Prevent window from closing on error
setlocal enabledelayedexpansion

title Sports Liquidity Scanner

REM Change to script directory FIRST (before any echo commands)
cd /d "%~dp0"

echo.
echo ========================================
echo   SPORTS LIQUIDITY SCANNER
echo   Production Launcher
echo ========================================
echo.
echo Current directory: %CD%
echo.

REM Check for Python
echo [1/5] Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ========================================
    echo   [ERROR] Python Not Found!
    echo ========================================
    echo.
    echo Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.8+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: During installation, check:
    echo   [x] "Add Python to PATH"
    echo.
    echo After installing, close this window and try again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo    [OK] Python %PYTHON_VERSION% found
echo.

REM Check for virtual environment
echo [2/5] Checking virtual environment...
if not exist ".venv" (
    echo    [INFO] Virtual environment not found. Creating...
    echo    This may take a minute...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ========================================
        echo   [ERROR] Failed to Create Virtual Environment!
        echo ========================================
        echo.
        echo The virtual environment could not be created.
        echo.
        echo Troubleshooting:
        echo   1. Make sure Python is installed correctly
        echo   2. Try running: python -m venv .venv
        echo   3. Check if you have write permissions in this folder
        echo.
        pause
        exit /b 1
    )
    echo    [OK] Virtual environment created
) else (
    echo    [OK] Virtual environment found
)
echo.

REM Activate virtual environment
echo [3/5] Activating virtual environment...
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo ========================================
    echo   [ERROR] Virtual Environment Corrupted!
    echo ========================================
    echo.
    echo The .venv folder exists but is incomplete.
    echo.
    echo Solution: Delete the .venv folder and try again.
    echo   This script will recreate it automatically.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo ========================================
    echo   [ERROR] Failed to Activate Virtual Environment!
    echo ========================================
    echo.
    echo The virtual environment could not be activated.
    echo.
    echo Solution: Delete the .venv folder and try again.
    echo.
    pause
    exit /b 1
)
echo    [OK] Virtual environment activated
echo.

REM Check for requirements.txt
echo [4/5] Checking dependencies...
if exist "requirements.txt" (
    echo    Checking if dependencies are installed...
    .venv\Scripts\python.exe -m pip show streamlit >nul 2>&1
    if errorlevel 1 (
        echo    [INFO] Installing dependencies from requirements.txt...
        echo    This may take a few minutes on first run...
        .venv\Scripts\python.exe -m pip install -r requirements.txt
        if errorlevel 1 (
            echo.
            echo ========================================
            echo   [WARNING] Dependency Installation Failed!
            echo ========================================
            echo.
            echo Some dependencies may have failed to install.
            echo.
            echo Troubleshooting:
            echo   1. Check your internet connection
            echo   2. Try running manually: .venv\Scripts\python.exe -m pip install -r requirements.txt
            echo   3. Check if pip is up to date: .venv\Scripts\python.exe -m pip install --upgrade pip
            echo.
            echo Continuing anyway... (may cause errors)
            echo.
            timeout /t 5
        ) else (
            echo    [OK] Dependencies installed successfully
        )
    ) else (
        echo    [OK] Dependencies already installed
    )
) else (
    echo    [WARNING] requirements.txt not found!
    echo    Installing core dependencies...
    .venv\Scripts\python.exe -m pip install streamlit streamlit-autorefresh pandas aiohttp kalshi-python py-clob-client python-dotenv cryptography
    if errorlevel 1 (
        echo.
        echo ========================================
        echo   [WARNING] Core Dependency Installation Failed!
        echo ========================================
        echo.
        echo Some dependencies may have failed to install.
        echo Continuing anyway... (may cause errors)
        echo.
        timeout /t 5
    ) else (
        echo    [OK] Core dependencies installed
    )
)
echo.

REM Check for .env file
echo [5/5] Checking configuration...
if not exist ".env" (
    echo    [WARNING] .env file not found!
    echo.
    echo ========================================
    echo   Configuration File Missing
    echo ========================================
    echo.
    echo Please create a .env file with your API credentials.
    echo.
    echo Steps:
    echo   1. Copy env_example.txt to .env
    echo   2. Edit .env and add your Kalshi credentials:
    echo      KALSHI_API_KEY=your_key_id
    echo      KALSHI_PRIVATE_KEY_PATH=kalshi.key
    echo.
    echo Note: Polymarket does not require credentials.
    echo The scanner will work without .env, but Kalshi will be skipped.
    echo.
    echo Continuing in 5 seconds...
    timeout /t 5
) else (
    echo    [OK] Configuration file found
)
echo.

REM Create logs directory if it doesn't exist
if not exist "logs" (
    echo Creating logs directory...
    mkdir logs
    echo    [OK] Logs directory created
)

REM Verify main.py exists
if not exist "main.py" (
    echo.
    echo ========================================
    echo   [ERROR] main.py Not Found!
    echo ========================================
    echo.
    echo The main.py file is missing from this directory.
    echo.
    echo Current directory: %CD%
    echo.
    echo Make sure you're running Start_Scanner.bat from the
    echo prod_scanner folder.
    echo.
    pause
    exit /b 1
)

REM Optional: Run Kalshi jailbreak script (first time only)
if exist "jailbreak_kalshi.py" (
    echo.
    echo [Optional] Checking if Kalshi library needs patching...
    echo    Run jailbreak_kalshi.py manually if you get validation errors.
    echo    Command: .venv\Scripts\python.exe jailbreak_kalshi.py
    echo.
)

REM Run the scanner using venv Python
echo ========================================
echo   Starting Streamlit Dashboard...
echo ========================================
echo.
echo The dashboard will open in your browser automatically.
echo Press Ctrl+C to stop the scanner
echo.
echo If you see any errors below, read them carefully.
echo.
echo ----------------------------------------
echo.

REM CRITICAL: Use venv Python explicitly
.venv\Scripts\python.exe -m streamlit run main.py
set SCANNER_EXIT_CODE=%ERRORLEVEL%

echo.
echo ----------------------------------------
echo.

REM Check exit code
if %SCANNER_EXIT_CODE% neq 0 (
    echo.
    echo ========================================
    echo   Scanner Exited with Error Code: %SCANNER_EXIT_CODE%
    echo ========================================
    echo.
    echo The scanner encountered an error.
    echo.
    echo Common issues:
    echo   - Missing dependencies (run: .venv\Scripts\python.exe -m pip install -r requirements.txt)
    echo   - API connection issues (check internet connection)
    echo   - Configuration errors (check .env file)
    echo.
    echo Check the error messages above for details.
    echo.
) else (
    echo.
    echo ========================================
    echo   Scanner Stopped Normally
    echo ========================================
    echo.
)

echo Press any key to close this window...
pause >nul
exit /b %SCANNER_EXIT_CODE%
