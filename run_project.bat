@echo off
setlocal enabledelayedexpansion
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

echo.
echo [SYSTEM INFO] Checking available memory...
for /f "tokens=3,4 delims= " %%A in ('tasklist /v ^| find "python"') do (
    echo [INFO] Python process found using memory
)

echo [MEMORY TIP] Models use ~2-3GB RAM. Close unused apps if needed.
echo.

:: Enable memory optimization for Python
set OPENBLAS_NUM_THREADS=2
set OMP_NUM_THREADS=2
set PYTHONHASHSEED=0

echo [1/2] Starting Backend API (Port 8000)...
echo [INFO] Using optimized memory settings (OPENBLAS_NUM_THREADS=2)
start "Backend API" cmd /k "title Backend API && cd attendance_backend && ..\.venv\Scripts\python.exe -u main.py 2>&1"

echo [INFO] Waiting 20 seconds for backend to initialize models...
timeout /t 20 /nobreak

echo [INFO] Checking backend health...
powershell -Command "$ErrorActionPreference='SilentlyContinue'; for ($i=1; $i -le 15; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/attendance/health; if ($r.StatusCode -eq 200) { Write-Host '[OK] Backend is healthy.'; exit 0 } } catch {} Start-Sleep -Seconds 1 }; Write-Host '[WARNING] Backend may still be initializing...'; exit 1"

echo [2/2] Starting Web Dashboard (Vite)...
echo [INFO] Dashboard will be available at http://localhost:3000
start "Web Dashboard" cmd /k "title Web Dashboard && cd web-dashboard && npm run dev"

echo.
echo ============================================================
echo   SUCCESS: Servers are starting in separate windows.
echo   - Backend:  http://127.0.0.1:8000
echo   - Dashboard: http://localhost:3000 (usually)
echo ============================================================
echo.
echo TROUBLESHOOTING:
echo   - If backend crashes: Close all windows and try again
echo   - If "Memory allocation failed": Close other apps and retry
echo   - Check backend window for detailed error messages
echo.
echo Keep this window open to close both servers later.
pause
