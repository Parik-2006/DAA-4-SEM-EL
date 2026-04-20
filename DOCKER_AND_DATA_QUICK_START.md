DOCKER AND DATA SETUP - QUICK START GUIDE

This file has all the commands you need. Just copy and paste them.

STEP 1: INSTALL DOCKER

Go here: https://www.docker.com/products/docker-desktop
Download for Windows
Install it
Restart your computer
Open PowerShell and type: docker --version
You should see a version number like Docker version 25.0.0

STEP 2: CREATE TEST DATA FOLDER

Open PowerShell
cd p:\DAA LAB EL
mkdir attendance_backend\test_data\student_photos
mkdir attendance_backend\test_data\student_photos\student_001
mkdir attendance_backend\test_data\student_photos\student_002
mkdir attendance_backend\test_data\student_photos\student_003

Put student photos in each folder like:
P:\DAA LAB EL\attendance_backend\test_data\student_photos\student_001\photo1.jpg
P:\DAA LAB EL\attendance_backend\test_data\student_photos\student_001\photo2.jpg

STEP 3: BUILD DOCKER IMAGE

Open PowerShell in project root:
cd p:\DAA LAB EL

Build the image:
docker build -t attendance-api:latest attendance_backend/

Wait for it to finish. You will see:
Successfully tagged attendance-api:latest

STEP 4: RUN BACKEND IN DOCKER

docker run -p 8000:8000 -e FIREBASE_CREDENTIALS_PATH=/app/config/firebase-credentials.json attendance-api:latest

Open browser and go to: http://localhost:8000/health
You should see: {"status":"healthy"}

STEP 5: RUN FRONTEND

In new PowerShell window:
cd p:\DAA LAB EL\web-dashboard
npm run dev

Open browser: http://localhost:5173
You should see login page

STEP 6: RUN MOBILE

In new PowerShell window:
cd p:\DAA LAB EL\attendance_app
flutter run

App should start on your phone or emulator

STEP 7: TEST LOGIN

Go to web dashboard: http://localhost:5173
Click Sign Up
Enter email: test@example.com
Enter password: Test1234
Click Create Account
You should now be logged in

STEP 8: CREATE STUDENTS IN FIRESTORE

Go to Firebase Console: https://console.firebase.google.com
Select project daa-4th-sem
Go to Firestore Database
Click Create Collection: students

Add first student with these fields:
student_id: S001
name: John Doe
email: john@example.com
photo_url: (leave blank for now)
enrollment_date: today's date

Add second student:
student_id: S002
name: Jane Smith
email: jane@example.com
photo_url: (leave blank for now)
enrollment_date: today's date

Add third student:
student_id: S003
name: Bob Wilson
email: bob@example.com
photo_url: (leave blank for now)
enrollment_date: today's date

STEP 9: CREATE COURSES IN FIRESTORE

In Firestore, create new collection: courses

Add first course:
course_id: CS101
course_name: Object Oriented Programming
instructor: Prof. Smith
semester: Spring 2024

Add second course:
course_id: CS102
course_name: Database Management
instructor: Prof. Johnson
semester: Spring 2024

STEP 10: UPLOAD PHOTOS

Use web dashboard to upload photos:
1. Go to http://localhost:5173
2. Login
3. Go to Dashboard
4. Click on a student
5. Click Upload Photo
6. Select a student photo from your computer
7. Click Upload

Or upload to Firebase Storage directly

STEP 11: GENERATE FACE EMBEDDINGS

This creates digital fingerprints of faces for recognition.

Open PowerShell:
cd p:\DAA LAB EL\attendance_backend
python -m services.face_recognition_service

Or:
python services/face_recognition_service.py

Wait for it to process photos. You will see:
Processing student_001... completed
Processing student_002... completed
Processing student_003... completed

STEP 12: TEST ATTENDANCE MARKING

Go to web dashboard: http://localhost:5173
Go to Attendance tab
Click Mark Attendance
Take or upload a student photo
System should recognize the student
Click Mark Present
Check Firestore to see attendance record

STEP 13: CHECK EVERYTHING WORKS

Website loads: http://localhost:5173
Backend responds: http://localhost:8000/health
Mobile app starts: flutter run
Login works: test@example.com
Students in Firestore: check database
Attendance records created: check Firestore

TROUBLESHOOTING COMMANDS

Check if Docker is running:
docker ps

Stop all containers:
docker stop $(docker ps -q)

Remove image to rebuild:
docker rmi attendance-api:latest

View Docker logs:
docker logs <container_id>

Check backend logs:
http://localhost:8000/docs

Check Firebase connection:
curl http://localhost:8000/health

USEFUL DOCKER COMMANDS

See all images:
docker images

See all containers:
docker ps -a

Remove stopped container:
docker rm <container_id>

Rebuild without cache:
docker build --no-cache -t attendance-api:latest attendance_backend/

Run with interactive terminal:
docker run -it -p 8000:8000 attendance-api:latest bash

USEFUL FIREBASE COMMANDS

See all Firestore collections:
Firebase Console > Firestore Database > Collections

Export data:
Firebase Console > Firestore Database > Export Collection

Import data:
Firebase Console > Firestore Database > Import Collection

Download SDK:
Firebase Console > Project Settings > Service Accounts > Generate New Private Key

ORDER TO START EVERYTHING

Start in this order so nothing breaks:

1. Start Docker backend:
docker run -p 8000:8000 attendance-api:latest

2. Wait 5 seconds

3. Start web frontend:
cd web-dashboard && npm run dev

4. Open browser:
http://localhost:5173

5. Start mobile app:
cd attendance_app && flutter run

Now everything works together!

COMMON MISTAKES TO AVOID

Do NOT start backend twice on same port
Do NOT forget to add FIREBASE_CREDENTIALS_PATH
Do NOT put spaces in folder names
Do NOT use old photos without good lighting
Do NOT skip Firebase configuration steps
Do NOT run npm run build before testing
Do NOT forget to create test students in Firestore

WHAT TO DO IF SOMETHING BREAKS

1. Read the error message carefully
2. Check the troubleshooting section above
3. Stop all containers: docker stop $(docker ps -q)
4. Restart Docker Desktop
5. Try again

Most problems are fixed by:
Restarting Docker
Checking Firebase credentials
Checking if port 8000 is free
Checking internet connection

QUICK TEST CHECKLIST

Copy this and check off each:

[ ] Docker installed and running
[ ] Backend builds successfully
[ ] Backend runs on port 8000
[ ] Website loads on port 5173
[ ] Login works with test account
[ ] Students created in Firestore
[ ] Courses created in Firestore
[ ] Photos uploaded to storage
[ ] Face embeddings generated
[ ] Attendance recorded successfully
[ ] Mobile app runs
[ ] All three pieces communicate

If all checked, you are ready for production!

NEXT: PRODUCTION DEPLOYMENT

After testing everything:

1. Build final versions:
   docker build -t attendance-api:latest attendance_backend/
   cd web-dashboard && npm run build
   cd attendance_app && flutter build apk --release

2. Deploy backend to:
   GCP Cloud Run
   AWS EC2
   Digital Ocean
   Azure Container Instances

3. Deploy web to:
   Firebase Hosting: firebase deploy --only hosting

4. Deploy mobile to:
   Google Play Store (Android)
   Apple App Store (iOS)

You are almost done! Just follow these steps and test everything.
