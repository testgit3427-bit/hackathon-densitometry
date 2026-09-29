@echo off
cd /d "%~dp0\.."
start "Backend" cmd /c "cd backend && .venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000"
start "Frontend" cmd /c "cd frontend && npm run dev"
