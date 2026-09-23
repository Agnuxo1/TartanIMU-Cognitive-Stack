@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" routing_benchmark.py
".venv\Scripts\python.exe" batch_benchmark.py
".venv\Scripts\python.exe" benchmark_suite.py
