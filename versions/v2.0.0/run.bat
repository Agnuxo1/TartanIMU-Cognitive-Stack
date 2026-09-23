@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
set "JEV_ORCHESTRATOR_ROOT=%ROOT%"
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo JEV runtime missing: %ROOT%.venv\Scripts\python.exe
  exit /b 2
)
"%ROOT%.venv\Scripts\python.exe" -m jev_orchestrator.cli %*
