@echo off
setlocal
set "JEV_CALLER_CWD=%CD%"
cd /d "%~dp0"
set "JEV_ORCHESTRATOR_ROOT=%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m jev_orchestrator.cli %*
) else (
  python -m jev_orchestrator.cli %*
)
exit /b %errorlevel%
