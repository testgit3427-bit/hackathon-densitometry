@echo off
cd /d "%~dp0\..\backend"
if not exist .venv\Scripts\python.exe python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\frontend
call npm install
