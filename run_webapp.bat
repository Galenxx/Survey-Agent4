@echo off
chcp 65001 >nul
echo ========================================
echo  Research Gap Analysis - Web App
echo ========================================
echo.
echo  Starting Backend (FastAPI on :8000) ...
start "RG-Backend" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000 --host 127.0.0.1 --reload"
echo  Backend started in new window.
echo.
echo  Starting Frontend (Vite on :5173) ...
cd /d %~dp0\frontend
start "RG-Frontend" cmd /k "npm run dev"
echo  Frontend started in new window.
echo.
echo  Open http://localhost:5173 in your browser
pause
