@echo off
cd /d "%~dp0backend"
"%~dp0backend\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
