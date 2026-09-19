@echo off
title Setup HeyLiku Auto-Start
echo ============================================================
echo   Setting up HeyLiku to start automatically on laptop boot...
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$Wsh = New-Object -ComObject WScript.Shell; $path = [System.IO.Path]::Combine($env:APPDATA, 'Microsoft\Windows\Start Menu\Programs\Startup\HeyLiku.lnk'); $s = $Wsh.CreateShortcut($path); $s.TargetPath = '%~dp0run.bat'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Save()"

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] HeyLiku is now set to start automatically!
    echo Every time you turn on or open your laptop, Liku will automatically
    echo start listening for your voice commands.
) else (
    echo [ERROR] Failed to set up auto-start shortcut.
)
echo.
pause
