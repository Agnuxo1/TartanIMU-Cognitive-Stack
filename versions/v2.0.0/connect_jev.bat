@echo off
setlocal
cd /d "%~dp0"
set "JEV_ORCHESTRATOR_ROOT=%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo JEV runtime missing: .venv\Scripts\python.exe
  exit /b 2
)
".venv\Scripts\python.exe" -m jev_orchestrator.connection %*
exit /b %errorlevel%
