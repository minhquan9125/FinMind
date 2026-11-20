@echo off
setlocal
cd /d "%~dp0"
if not exist ".agent-state\vnstock-venv\Scripts\python.exe" (
  echo Chua co moi truong vnstock. Xem README.md de cai dat trong folder nay.
  pause
  exit /b 1
)
".agent-state\vnstock-venv\Scripts\python.exe" -B -m ohlcv.app.server --open
if errorlevel 1 pause
