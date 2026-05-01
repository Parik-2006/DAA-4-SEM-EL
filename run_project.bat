@echo off
setlocal
title Smart Attendance System - Master Launcher

echo ============================================================
echo   Smart Attendance System - One-Click Launcher
echo ============================================================
echo.

:: Check for Backend Venv
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Backend virtual environment not found in .venv/
    echo Please run the installation steps provided first.
    pause
    exit /b
)

:: Check for Frontend node_modules
if not exist "web-dashboard\node_modules\" (
    echo [WARNING] Frontend node_modules not found. 
    echo Attempting to install frontend dependencies...
    cd web-dashboard && npm install && cd ..
)

echo [1/2] Starting Backend API (Port 8000)...
start "Backend API" cmd /k "echo Smart Attendance Backend Server && echo -------------------------------- && cd attendance_backend && ..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000"

echo Waiting for backend health check...
powershell -Command "$ErrorActionPreference='SilentlyContinue'; for ($i=1; $i -le 30; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/attendance/health; if ($r.StatusCode -eq 200) { exit 0 } } catch {} Start-Sleep -Seconds 1 }; exit 1"
if errorlevel 1 (
    echo [WARNING] Backend health check failed after 30 seconds. Starting frontend anyway...
) else (
    echo [OK] Backend is healthy.
)

echo [2/2] Starting Web Dashboard (Vite)...
start "Web Dashboard" cmd /k "echo Smart Attendance Web Dashboard && echo --------------------------------- && cd web-dashboard && npm run dev"

echo.
echo ============================================================
echo   SUCCESS: Servers are starting in separate windows.
echo   - Backend:  http://127.0.0.1:8000
echo   - Dashboard: http://localhost:3000 (usually)
echo ============================================================
echo.
echo Keep this window open if you want to close both later, 
echo or close it now - the other windows will stay active.
pause
