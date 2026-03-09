@echo off
echo ---------------------------------------------------
echo STARTING SHARP MONEY DEBUGGER
echo Watch this window for REAL-TIME LOGS...
echo ---------------------------------------------------
cd /d "%~dp0"
streamlit run debug_dashboard.py
pause