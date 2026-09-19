@echo off
title HeyLiku Voice Assistant
echo ============================================================
echo   Starting HeyLiku Voice Assistant...
echo ============================================================
echo.
python -u liku.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] HeyLiku exited with an error. Check if requirements are installed:
    echo pip install -r requirements.txt
    echo.
)
pause
