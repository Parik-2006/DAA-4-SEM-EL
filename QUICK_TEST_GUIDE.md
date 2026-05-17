"""
QUICK_TEST_GUIDE.md — Testing the Smart Attendance System
════════════════════════════════════════════════════════════════════════════════

## Quick Start (5 minutes)

### 1. Setup Students
```bash
cd attendance_backend
python scripts/setup_students.py
```
✅ 8 students registered in Firebase

### 2. Start Backend
```bash
python main.py
```
✅ Backend running on http://localhost:8000

### 3. Start Frontend (in new terminal)
```bash
cd web-dashboard
npm run dev
```
✅ Dashboard running on http://localhost:3000

---

## Test Case 1: Student Login (2 min)

**Endpoint**: POST /api/v1/auth/login

**Request** (STUD_001 with correct credentials):
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "parikshithbb.cs25@rvce.edu.in",
    "password": "viratkohli18"
  }'
```

**OR Test with STUD_002**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "gagandk2005@gmail.com",
    "password": "password123"
  }'
```

**Expected Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user_id": "STUD_001",
  "email": "parikshithbb.cs25@rvce.edu.in",
  "role": "student",
  "permissions": ["view_own_attendance", "view_own_analytics"],
  "assigned_sections": []
}
```

**Save the access_token for next tests** ✅

---

## Test Case 2: Get Student Dashboard (1 min)

**Endpoint**: GET /api/v1/student/dashboard

**Request**:
```bash
curl -X GET http://localhost:8000/api/v1/student/dashboard \
  -H "Authorization: Bearer <access_token_from_above>"
```

**Expected Response**:
```json
{
  "periods": [
    {
      "period_id": "p1",
      "course_code": "CS401",
      "course_name": "Machine Learning",
      "start_time": "09:00",
      "end_time": "10:00",
      "status": "pending"
    }
  ],
  "overall_stats": {
    "total_classes": 4,
    "present": 0,
    "late": 0,
    "absent": 0,
    "pending": 4,
    "attendance_pct": 0.0
  }
}
```

**Status**: ✅ Shows student's today's schedule

---

## Test Case 3: Get Attendance Summary (1 min)

**Endpoint**: GET /api/v1/student/attendance-summary

**Request**:
```bash
curl -X GET http://localhost:8000/api/v1/student/attendance-summary \
  -H "Authorization: Bearer <access_token>"
```

**Expected Response**:
```json
{
  "total_classes": 0,
  "present": 0,
  "late": 0,
  "absent": 0,
  "pending": 0,
  "attendance_pct": 0.0,
  "band": "safe"
}
```

**Status**: ✅ Shows overall attendance stats

---

## Test Case 4: Face Detection - Success Path (3 min)

**Prerequisite**: Have a clear face image (portrait format, 640x480 or larger)

**Endpoint**: POST /api/v1/attendance/detect-face

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/attendance/detect-face \
  -F "file=@/path/to/face_image.jpg" \
  -H "Authorization: Bearer <access_token>"
```

**Expected Response** (if face matches enrolled student):
```json
{
  "matched": true,
  "message": "Attendance marked as PRESENT for Parikshith B Bilchode.",
  "record_id": "r1234567890",
  "student_name": "Parikshith B Bilchode",
  "student_id": "STUD_001",
  "status": "present",
  "confidence": 0.92,
  "timestamp": "2026-05-17T10:30:45.123456Z"
}
```

**Status**: ✅ Face detected and attendance marked

**Verify in Dashboard**:
- Refresh dashboard
- Should show "present" for current period
- Confidence score displayed
- Timestamp recorded

---

## Test Case 5: Face Detection - Failed Match (2 min)

**Request**: Upload an image of a different person

```bash
curl -X POST http://localhost:8000/api/v1/attendance/detect-face \
  -F "file=@/path/to/different_person.jpg"
```

**Expected Response**:
```json
{
  "matched": false,
  "message": "Face not recognised. Best similarity: 0.38 (threshold: 0.55)..."
}
```

**Status**: ✅ Face not matched (attempt count = 1)

---

## Test Case 6: 5-Attempt Limit Enforcement (5 min)

**Setup**: Have 5 images that DON'T match the enrolled student

**Steps**:
1. Upload image 1 → "Face not recognized" (count: 1)
2. Upload image 2 → "Face not recognized" (count: 2)
3. Upload image 3 → "Face not recognized" (count: 3)
4. Upload image 4 → "Face not recognized" (count: 4)
5. Upload image 5 → "Face not recognized" (count: 5)
6. Upload image 6 → Should get "Maximum attempts" error

**Request** (Attempt 6):
```bash
curl -X POST http://localhost:8000/api/v1/attendance/detect-face \
  -F "file=@/path/to/image6.jpg"
```

**Expected Response**:
```json
{
  "matched": false,
  "message": "Maximum detection attempts (5) reached for this period. Please ask an instructor for assistance.",
  "attempt_limit_exceeded": true
}
```

**Status**: ✅ Attempt limit enforced correctly

**Reset**: 
- Next period (new period_id) → counter resets
- Next day (tomorrow) → counter resets
- Successful detection → counter resets

---

## Test Case 7: Attendance History (1 min)

**Endpoint**: GET /api/v1/student/attendance/history

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/student/attendance/history?page=1&page_size=10" \
  -H "Authorization: Bearer <access_token>"
```

**Expected Response**:
```json
{
  "total": 1,
  "page": 1,
  "page_size": 10,
  "records": [
    {
      "record_id": "r1234567890",
      "student_id": "STUD_001",
      "student_name": "Parikshith B Bilchode",
      "timestamp": "2026-05-17T10:30:45.123456Z",
      "status": "present",
      "confidence": 0.92,
      "course_id": null,
      "period_id": null
    }
  ]
}
```

**Status**: ✅ History shows all marked attendance

---

## Test Case 8: Multiple Students

**Test with Different Students**:

**STUD_002 (Gagan D K)**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "gagan.dk.cs25@rvce.edu.in",
    "password": "password123"
  }'
```

**Expected**: Gets different JWT token with user_id=STUD_002

**Steps**:
1. Login as STUD_002
2. Get dashboard → shows STUD_002's schedule
3. Mark attendance → records under STUD_002
4. Check history → shows only STUD_002's records

**Status**: ✅ Data isolation works correctly

---

## Test Case 9: 403 Error Fix Verification (2 min)

**Before Fix** (would fail):
```bash
curl -X GET "http://localhost:8000/api/v1/student/attendance/today?student_id=STUD_001" \
  -H "Authorization: Bearer <token_for_STUD_002>"
```
❌ Would return 403 Forbidden

**After Fix**:
```bash
# Same request now works
curl -X GET "http://localhost:8000/api/v1/student/attendance/today" \
  -H "Authorization: Bearer <token_for_STUD_002>"
```
✅ Returns 200 OK (uses STUD_002's data)

---

## Test Case 10: Analytics Dashboard

**UI Test**:
1. Login as student
2. Navigate to `/analytics` or student dashboard
3. Should see:
   - ✅ Today's periods with status
   - ✅ Attendance percentage
   - ✅ Recent detections
   - ✅ Course-wise breakdown
4. Mark attendance via face
5. Dashboard should update in real-time

**Status**: ✅ Real-time updates working

---

## Full Test Flow (15 minutes)

1. ✅ Setup students (setup_students.py)
2. ✅ Start backend (python main.py)
3. ✅ Start frontend (npm run dev)
4. ✅ Login as STUD_001 (parikshithbb.cs25@rvce.edu.in, password: viratkohli18)
5. ✅ View dashboard
6. ✅ Upload matching face image
7. ✅ Verify attendance marked
8. ✅ Try 5 non-matching images
9. ✅ Verify 6th attempt blocked
10. ✅ Check attendance history
11. ✅ Login as STUD_002 (gagandk2005@gmail.com)
12. ✅ Verify data isolation
13. ✅ Check analytics dashboard

---

## Debugging

### Issue: 401 Unauthorized
**Cause**: Missing or invalid token
**Fix**: 
- Ensure token is in Authorization header
- Format: `Authorization: Bearer <token>`
- Token might be expired (8 hour TTL)

### Issue: 404 Student Not Found
**Cause**: Student not registered
**Fix**: Run setup_students.py

### Issue: Face Always Fails
**Cause**: Poor image quality or face not enrolled
**Fix**:
- Ensure image has clear face
- Good lighting
- Face 30-60cm from camera
- Upload more enrollment images

### Issue: Attempt Limit Stuck at 5
**Cause**: Firestore entry not deleted
**Fix**:
- Wait until next day (date-based reset)
- Or delete from `face_attempts` collection manually
- Successful detection resets it

### Issue: Attendance Not in History
**Cause**: Data not synced to Firestore
**Fix**:
- Check backend logs for errors
- Verify Firestore APIs enabled
- Check Firebase credentials

---

## Expected Performance

- Login: < 500ms
- Dashboard load: < 1s
- Face detection: 3-5 seconds (includes face extraction)
- History query: < 500ms
- Analytics: < 2 seconds

---

## Backend Health Check

```bash
curl http://localhost:8000/api/v1/attendance/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-05-17T10:30:45.123456Z",
  "firebase": "connected",
  "firestore": "connected"
}
```

---

## All Tests Pass! ✅

Once all test cases pass, the system is ready for production use.

For detailed setup instructions, see: SETUP_GUIDE.md
For implementation details, see: IMPLEMENTATION_SUMMARY.md
"""
