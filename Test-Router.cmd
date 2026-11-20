@echo off
cd /d "%~dp0"
set "FINMIND_ROUTER_URL=http://127.0.0.1:8000/api/hybrid-router/test"
"%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0interactive_test.py"
