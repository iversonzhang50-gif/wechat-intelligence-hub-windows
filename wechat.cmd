@echo off
setlocal
set PYTHONUTF8=1
if not exist "%~dp0.runtime\Scripts\python.exe" (
  echo Run Install.cmd first.
  exit /b 2
)
"%~dp0.runtime\Scripts\python.exe" -X utf8 "%~dp0windows\launch.py" %*
