@echo off
title Disable HeyLiku Auto-Start
echo ============================================================
echo   Disabling HeyLiku Auto-Start...
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$path = [System.IO.Path]::Combine($env:APPDATA, 'Microsoft\Windows\Start Menu\Programs\Startup\HeyLiku.lnk'); if (Test-Path $path) { Remove-Item $path -Force; Write-Host '[SUCCESS] Auto-start removed successfully.' } else { Write-Host 'Auto-start was not enabled.' }"
echo.
pause
