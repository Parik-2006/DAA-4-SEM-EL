STEP BY STEP - EXACT COMMANDS TO RUN NOW

Follow these exactly in order. Copy and paste each command.

DAY 1: SETUP

MORNING: INSTALL DOCKER

Open browser: https://www.docker.com/products/docker-desktop
Click Download for Windows
Install it
Restart computer
Open PowerShell and run:

docker --version

You should see version number. If yes, continue.

AFTERNOON: BUILD BACKEND DOCKER

Open PowerShell:

cd p:\DAA LAB EL

Run:

docker build -t attendance-api:latest attendance_backend/

Wait 3-5 minutes. When done you see:
Successfully tagged attendance-api:latest

Test it:

docker run -p 8000:8000 attendance-api:latest

Open new browser tab: http://localhost:8000/health

You should see green checkmark or: {"status":"healthy"}

If yes, close this terminal (Ctrl+C)

EVENING: SETUP FRONTEND

Open new PowerShell:

cd p:\DAA LAB EL\web-dashboard

Install packages:

npm install

Run it:

npm run dev

Open browser: http://localhost:5173

You should see login page

Good! Close PowerShell (Ctrl+C)

DAY 2: ADD TEST DATA

MORNING: CREATE STUDENT PHOTOS FOLDER

Open PowerShell:

cd p:\DAA LAB EL

Create folders:

mkdir attendance_backend\test_data\student_photos\student_001
mkdir attendance_backend\test_data\student_photos\student_002  
mkdir attendance_backend\test_data\student_photos\student_003

Find or take photos of 3 people. Save as:
P:\DAA LAB EL\attendance_backend\test_data\student_photos\student_001\photo1.jpg
P:\DAA LAB EL\attendance_backend\test_data\student_photos\student_001\photo2.jpg
P:\DAA LAB EL\attendance_backend\test_data\student_photos\student_002\photo1.jpg
P:\DAA LAB EL\attendance_backend\test_data\student_photos\student_002\photo2.jpg
P:\DAA LAB EL\attendance_backend\test_data\student_photos\student_003\photo1.jpg
P:\DAA LAB EL\attendance_backend\test_data\student_photos\student_003\photo2.jpg

AFTERNOON: CREATE DATABASE RECORDS

Open browser: https://console.firebase.google.com
Login with your Google account
Select project daa-4th-sem
Click Firestore Database on left
Click Create Collection
Name it: students
Click Next

Add first student:
Click Add Document
Student ID: S001
Name: John Doe
Email: john@example.com
Photo URL: (leave empty)
Enrollment Date: 2024-04-20

Click Save

Add second student:
Student ID: S002
Name: Jane Smith
Email: jane@example.com
Photo URL: (leave empty)
Enrollment Date: 2024-04-20

Click Save

Add third student:
Student ID: S003
Name: Bob Wilson
Email: bob@example.com
Photo URL: (leave empty)
Enrollment Date: 2024-04-20

Click Save

Create courses collection:
Click Create Collection
Name it: courses
Click Next

Add first course:
Course ID: CS101
Course Name: Object Oriented Programming
Instructor: Prof. Smith
Semester: Spring 2024

Click Save

Add second course:
Course ID: CS102
Course Name: Database Management
Instructor: Prof. Johnson
Semester: Spring 2024

Click Save

EVENING: TEST EVERYTHING TOGETHER

Terminal 1 - Start Backend:

cd p:\DAA LAB EL
docker run -p 8000:8000 attendance-api:latest

Wait for it to say: Application startup complete

Terminal 2 - Start Frontend:

cd p:\DAA LAB EL\web-dashboard
npm run dev

Terminal 3 - Start Mobile:

cd p:\DAA LAB EL\attendance_app
flutter run

Wait for app to load

DAY 3: TEST AND FIX

MORNING: TEST LOGIN

Open http://localhost:5173
Click Sign Up
Email: testuser@example.com
Password: Test1234
Full Name: Test User
Click Create Account

If it works, you see dashboard
If it fails, check backend logs

AFTERNOON: TEST ATTENDANCE

On web dashboard:
Click Attendance tab
Click Mark Attendance
Upload a student photo
Click Mark Present
Check if recorded in Firestore

EVENING: REVIEW AND PLAN

Check if everything works:
Website: Yes or No
Mobile: Yes or No
Database: Yes or No
Photos upload: Yes or No
Attendance records: Yes or No

If any No, check error messages and fix

DAY 4: BEFORE PRODUCTION

BACKUP YOUR CODE

Open PowerShell:

cd p:\DAA LAB EL
git status
git add -A
git commit -m "Final working version before production"
git push origin main

CLEAN UP TEST DATA

In Firebase Console:
Delete test students (optional)
Delete test courses (optional)
Keep real data only

FINAL TEST

Run everything one more time:
Docker backend
npm frontend
Flutter mobile

Try full flow:
Login
View dashboard
Upload photo
Mark attendance
Check record created

If all works, ready for production!

PRODUCTION COMMANDS

When ready to go live:

Build final backend:
docker build -t attendance-api:production attendance_backend/

Build final web:
cd web-dashboard && npm run build

Push to production:
For AWS: aws deploy --region us-east-1
For GCP: gcloud app deploy
For Firebase: firebase deploy

Deploy mobile:
Google Play Store
Apple App Store

COMMON ISSUES AND FIXES

Problem: Port 8000 already in use
Fix: docker run -p 8001:8000 attendance-api:latest

Problem: npm install fails
Fix: npm cache clean --force && npm install

Problem: Flutter command not found
Fix: Add Flutter to PATH or use full path

Problem: Firebase not connecting
Fix: Check firebase-credentials.json exists and is valid

Problem: Photos not recognized
Fix: Check photo quality and face detection threshold

WHAT IF SOMETHING GOES WRONG

Step 1: Stop everything (Ctrl+C in all terminals)

Step 2: Check what failed
Read error message carefully
Google the error
Check GitHub issues

Step 3: Restart Docker
Click Docker icon > restart

Step 4: Try again
Run commands again from beginning

Step 5: Ask for help
Share error message
Share what you tried
Include command output

VERIFICATION CHECKLIST

Before going to production, verify:

Backend:
[ ] Starts without errors
[ ] http://localhost:8000/health returns healthy
[ ] Connects to Firebase
[ ] Can create records

Frontend:
[ ] Loads on port 5173
[ ] Login/signup works
[ ] Shows dashboard
[ ] Can upload photos

Mobile:
[ ] Starts on emulator or device
[ ] Login works
[ ] Shows home screen
[ ] Camera works

Database:
[ ] Students in Firestore
[ ] Courses in Firestore
[ ] Attendance records created
[ ] Photos stored

If all checked, you are ready!

TIMELINE

If you follow these steps:
Day 1: 4-6 hours (setup and configuration)
Day 2: 4-6 hours (add data and test)
Day 3: 2-4 hours (debug and fix)
Day 4: 1-2 hours (final testing)

Total: About 2-3 days of work

AFTER PRODUCTION

Monitor the system:
Check logs daily
Check user feedback
Update code if needed
Add new features
Scale if needed

You did great work! Now just follow these steps and you have a working system!
