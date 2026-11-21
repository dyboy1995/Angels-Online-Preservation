@echo off
setlocal
echo Return to character selection or exit the game before stopping the server.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-local.ps1"
set "result=%errorlevel%"
if not "%result%"=="0" echo Shutdown failed. Check the message above.
pause
exit /b %result%
