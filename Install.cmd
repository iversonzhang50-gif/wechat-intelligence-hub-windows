@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\Install.ps1" %*
exit /b %errorlevel%
