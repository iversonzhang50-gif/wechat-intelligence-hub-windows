@echo off
setlocal
if not exist "%~dp0.runtime\Scripts\python.exe" exit /b 2
"%~dp0.runtime\Scripts\python.exe" -X utf8 "%~dp0windows\self_test.py"
exit /b %errorlevel%
