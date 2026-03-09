@echo off
echo.
echo ========================================
echo   UNIFIED BETTING - NEW PC SETUP
echo ========================================
echo.
echo This will check prerequisites and install everything needed.
echo.

REM Check Python
echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python is not installed!
    echo   Please install Python 3.8+ from https://python.org
    echo   Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
python --version
echo   OK: Python found
echo.

REM Check Node.js
echo [2/4] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Node.js is not installed!
    echo   Please install Node.js from https://nodejs.org (choose LTS version)
    pause
    exit /b 1
)
node --version
npm --version
echo   OK: Node.js and npm found
echo.

REM Check Git (optional but helpful)
echo [3/4] Checking Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo   WARNING: Git not found (optional)
) else (
    git --version
    echo   OK: Git found
)
echo.

REM Run setup
echo [4/4] Running dependency installation...
echo   This may take several minutes...
echo.
python setup_dependencies.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo   SETUP FAILED
    echo ========================================
    echo.
    echo Please check the errors above and try again.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   SETUP COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo Next steps:
echo   1. Configure your config.json file if needed
echo   2. Run: python launch.py
echo   3. Open: http://localhost:3000
echo.
pause

