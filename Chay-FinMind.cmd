@echo off
setlocal
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" set "PS_EXE=powershell.exe"
set "CHECK_ARG="
if /i "%~1"=="--check" set "CHECK_ARG=-Check"
"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap-finmind.ps1" -Root "%~dp0." %CHECK_ARG%
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" if /i not "%~1"=="--check" pause
exit /b %EXIT_CODE%
