@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1"
set "result=%errorlevel%"
if not "%result%"=="0" echo Startup failed. Check the message above.
pause
exit /b %result%
