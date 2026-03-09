@echo off
cd /d "%~dp0"
echo Starting Authenticated Scanner...
streamlit run sharp_scanner_auth.py
pause