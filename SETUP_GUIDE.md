"""
SETUP_GUIDE.md — Firebase Student Setup & Configuration
════════════════════════════════════════════════════════════════════════════════

## Step 1: Register Students in Firebase

Run the setup script to create all students with email login credentials:

```bash
cd attendance_backend
python scripts/setup_students.py
```

This will:
✅ Create 8 student records in Firestore
✅ Hash passwords securely (SHA-256)
✅ Set up email-based login
✅ Initialize face embeddings storage structure

Expected output:
```
Setting up student records...
✅ STUD_001: Parikshith B Bilchode (parikshithbb.cs25@rvce.edu.in) created successfully
✅ STUD_002: Gagan D K (gagan.dk.cs25@rvce.edu.in) created successfully
...
✅ Setup complete: 8/8 students configured
```


## Step 2: Login with Email Credentials

Students can now login with:

**STUD_001 (Parikshith B Bilchode)**
- Email: parikshithbb.cs25@rvce.edu.in
- Password: viratkohli18

**STUD_002 (Gagan D K)**
- Email: gagandk2005@gmail.com
- Password: password123

**STUD_003 (Prajwal K)**
- Email: prajwalk.cs24@rvce.edu.in
- Password: password123

**STUD_004 (Ved U)**
- Email: vedu.cs25@rvce.edu.in
- Password: password123

**STUD_005 (Pranav Kumar M)**
- Email: pranavkumarm.cs24@rvce.edu.in
- Password: password123

**STUD_006 (Nischith G A)**
- Email: nishchithgarg.cs24@rvce.edu.in
- Password: password123

**STUD_007 (Yohith N)**
- Email: nyohith.cs24@rvce.edu.in
- Password: password123

**STUD_008 (Mahesh Raju)**
- Email: nrmaheshraju.cs24@rvce.edu.in
- Password: password123


## Step 3: Upload Face Images

1. Login as a student
2. Navigate to enrollment/face-registration
3. Upload clear face images (5-10 images recommended)
4. System will extract and store face embeddings

The more clear images uploaded, the better the face recognition accuracy.


## Step 4: Test Face Detection with 5-Attempt Limit

**How the 5-Attempt Limit Works:**

- Maximum 5 face detection attempts per student per period per day
- Counter resets daily (based on date)
- Counter resets on successful detection
- After 5 failed attempts, returns:
  ```json
  {
    "matched": false,
    "message": "Maximum detection attempts (5) reached for this period. Please ask an instructor for assistance.",
    "attempt_limit_exceeded": true
  }
  ```

**Example Flow:**
1. Attempt 1: Face not recognized → count = 1
2. Attempt 2: Face not recognized → count = 2
3. Attempt 3: Face not recognized → count = 3
4. Attempt 4: Face not recognized → count = 4
5. Attempt 5: Face not recognized → count = 5
6. Attempt 6: Returns "Maximum attempts reached" error

**Reset scenarios:**
- Successful detection → counter resets to 0
- Next day (new date) → counter resets to 0
- Admin manual reset (future) → counter resets to 0


## Step 5: Analytics & History Tracking

Once face detection is successful, attendance is recorded and appears in:

✅ **Student Dashboard**
   - Shows today's periods with attendance status
   - Updates in real-time with face detections

✅ **Attendance History**
   - Full history of all marked attendance
   - Confidence scores and timestamps
   - Course-wise attendance tracking

✅ **Analytics Page**
   - Overall attendance percentage
   - Course-wise attendance breakdown
   - Late/Present/Absent statistics

---

## Troubleshooting

### "Face not recognized" (Low confidence)
- Ensure face is clearly visible
- Good lighting condition
- Face should be within 30cm-60cm from camera
- Try uploading more face images for the student

### "Maximum detection attempts reached"
- Student exceeded 5 attempts in this period
- Contact instructor to manually mark attendance
- Counter resets next period/day

### Database/Firestore errors
- Verify Firebase credentials are set (config/firebase-credentials.json)
- Check that Firestore APIs are enabled in Google Cloud Console
- See error logs in backend: `logs/attendance_backend.log`

### Student not in database
- Run setup_students.py again
- Verify collection is "students" in Firestore
- Check student_id format (should be STUD_001, etc.)

---

## Database Schema

**Users Collection**
```
{
  "id": "STUD_001",
  "name": "Parikshith B Bilchode",
  "email": "parikshithbb.cs25@rvce.edu.in",
  "password_hash": "sha256(...)",
  "role": "student",
  "roll_no": "4CS01",
  "class_id": "4CS",
  "section": "A"
}
```

**Students Collection**
```
{
  "student_id": "STUD_001",
  "name": "Parikshith B Bilchode",
  "email": "parikshithbb.cs25@rvce.edu.in",
  "roll_no": "4CS01",
  "embeddings": [...],  // Face embeddings
  "enrollment_status": "active",
  "registered_at": "2026-05-17T..."
}
```

**Face Attempts Collection** (auto-cleanup)
```
{
  "student_id": "STUD_001",
  "period_id": "P001",
  "date": "2026-05-17",
  "count": 3,
  "last_attempt": "2026-05-17T10:30:45.123Z"
}
```

**Attendance Collection**
```
{
  "attendance_id": "STUD_001_P001_2026-05-17",
  "student_id": "STUD_001",
  "period_id": "P001",
  "section_id": "4CS-A",
  "date": "2026-05-17",
  "timestamp": "2026-05-17T10:30:45.123Z",
  "status": "present",  // or "late", "absent"
  "confidence": 0.92,
  "marked_by_teacher_id": "AUTO_DETECTED",
  "method": "face_recognition_upload"
}
```

---

## API Endpoints

### Login
```
POST /api/v1/auth/login
{
  "email": "parikshithbb.cs25@rvce.edu.in",
  "password": "password123"
}
```

### Face Detection & Mark Attendance
```
POST /api/v1/attendance/detect-face?period_id=P001
[image file uploaded]
```

Response (Success):
```json
{
  "matched": true,
  "student_name": "Parikshith B Bilchode",
  "student_id": "STUD_001",
  "status": "present",
  "confidence": 0.92,
  "record_id": "r123...",
  "timestamp": "2026-05-17T10:30:45.123Z"
}
```

Response (Failed Match):
```json
{
  "matched": false,
  "message": "Face not recognised. Best similarity: 0.45 (threshold: 0.55)...",
  "window": {...}
}
```

Response (Attempt Limit):
```json
{
  "matched": false,
  "message": "Maximum detection attempts (5) reached for this period...",
  "attempt_limit_exceeded": true
}
```

### Get Student Attendance
```
GET /api/v1/student/attendance/today
GET /api/v1/student/attendance-summary
GET /api/v1/student/attendance/history
```

---

## Notes

- Password hashing uses SHA-256 (use bcrypt in production)
- JWT tokens expire after 8 hours (configurable)
- Face embeddings are stored per student for fast matching
- Attempt counters are stored in Firestore for persistence
- All times are in ISO 8601 format
- Daily report generation happens automatically

For more details, see:
- `/attendance_backend/scripts/setup_students.py`
- `/attendance_backend/services/face_attempt_service.py`
- `/attendance_backend/api/attendance.py` (detect_face_and_mark endpoint)
"""
