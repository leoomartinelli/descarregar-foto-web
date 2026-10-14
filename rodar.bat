@echo off
cd /d "%~dp0"
rem As dependencias sao (re)instaladas sempre que o requirements.txt mudar (ex.: depois de uma atualizacao).
if not exist .venv python -m venv .venv
fc /b requirements.txt .venv\requirements.txt >nul 2>&1 || (
  .venv\Scripts\pip install -r requirements.txt && copy /y requirements.txt .venv\requirements.txt >nul
)
.venv\Scripts\python run.py
