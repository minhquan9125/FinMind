@echo off
rem Answers ssh's password prompt for the launcher's tunnel. The value comes from the
rem launcher's environment (backend\.env, not in git); nothing secret is stored here.
echo %FINMIND_TUNNEL_PASSWORD%
