@echo off
cd /d "%~dp0frontend"
if not exist "node_modules\react-scripts\bin\react-scripts.js" (
    echo Installing frontend dependencies...
    call npm ci
    if errorlevel 1 call npm install
    if errorlevel 1 call npm install --legacy-peer-deps
)
if not exist "node_modules\react-scripts\bin\react-scripts.js" (
    echo ERROR: react-scripts is missing. Run: cd frontend ^&^& npm install
    pause
    exit /b 1
)
set PORT=5000
set BROWSER=none
set NODE_OPTIONS=--openssl-legacy-provider
call npm start
