@echo off
REM Quick start script to setup students and test the system
REM Usage: run_setup.bat

setlocal enabledelayedexpansion

REM Colors for output
cls
echo.
echo ════════════════════════════════════════════════════════════════════════════════
echo    Smart Attendance System — Student Setup & Configuration
echo ════════════════════════════════════════════════════════════════════════════════
echo.

REM Check if .venv exists
if not exist ".venv\Scripts\activate.bat" (
    echo ❌ Virtual environment not found!
    echo Please activate your Python environment first:
    echo   .\.venv\Scripts\activate.bat
    pause
    exit /b 1
)

echo ✅ Activating Python environment...
call .venv\Scripts\activate.bat

REM Step 1: Setup students
echo.
echo ════════════════════════════════════════════════════════════════════════════════
echo STEP 1: Register Students in Firebase
echo ════════════════════════════════════════════════════════════════════════════════
echo.
echo This will create 8 student records with email login credentials.
echo.
cd attendance_backend

python scripts/setup_students.py
if !errorlevel! neq 0 (
    echo.
    echo ❌ Setup failed! Check the errors above.
    cd ..
    pause
    exit /b 1
)

cd ..

echo.
echo ════════════════════════════════════════════════════════════════════════════════
echo STEP 2: Verification
echo ════════════════════════════════════════════════════════════════════════════════
echo.
echo Students are now registered with the following credentials:
echo.
echo   STUD_001: parikshithbb.cs25@rvce.edu.in (password: viratkohli18)
echo   STUD_002: gagandk2005@gmail.com
echo   STUD_003: prajwalk.cs24@rvce.edu.in
echo   STUD_004: vedu.cs25@rvce.edu.in
echo   STUD_005: pranavkumarm.cs24@rvce.edu.in
echo   STUD_006: nishchithgarg.cs24@rvce.edu.in
echo   STUD_007: nyohith.cs24@rvce.edu.in
echo   STUD_008: nrmaheshraju.cs24@rvce.edu.in
echo.
echo All students use password: password123 (except STUD_001)
echo.

echo ════════════════════════════════════════════════════════════════════════════════
echo STEP 3: Next Steps
echo ════════════════════════════════════════════════════════════════════════════════
echo.
echo 1. Start the backend server:
echo    python attendance_backend/main.py
echo.
echo 2. Start the web dashboard:
echo    cd web-dashboard
echo    npm run dev
echo.
echo 3. Login to the dashboard with a student account
echo.
echo 4. Upload face images for enrollment
echo.
echo 5. Test face detection with the 5-attempt limit
echo.
echo For detailed setup instructions, see: SETUP_GUIDE.md
echo.

echo ✅ Student setup complete!
echo.
pause
