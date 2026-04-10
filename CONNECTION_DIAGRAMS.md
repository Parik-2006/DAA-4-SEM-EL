# 🔗 System Connection Diagram

## Overall System Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                 COMPLETE ATTENDANCE SYSTEM FLOW                        │
└────────────────────────────────────────────────────────────────────────┘

                         USER INTERFACES
                    ┌──────────┬──────────┐
                    │  MOBILE  │   WEB    │
                    │ (Flutter)│(React TS)│
                    └────┬─────┴────┬─────┘
                         │          │
                    HTTP │ REST API │ HTTP
                    Axios│ (Bearer  │ Axios
                    (DIO)│  Token)  │(TS)
                         │          │
                         └────┬─────┘
                              │
                    ┌─────────▼─────────┐
                    │   FASTAPI BACKEND │
                    │    (Python 3.8+)  │
                    │    Port: 8000     │
                    ├───────────────────┤
                    │ • Health Endpoint │
                    │ • Auth/JWT        │
                    │ • REST API Routes │
                    │ • CORS Middleware │
                    │ • Error Handling  │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
        ┌─────────────┐ ┌──────────┐ ┌──────────────┐
        │  FIREBASE   │ │  AI      │ │  STREAM      │
        │  BACKEND    │ │ PIPELINE │ │  PROCESSOR   │
        ├─────────────┤ ├──────────┤ ├──────────────┤
        │• Firestore  │ │• YOLOv8  │ │• RTSP Input  │
        │• RTDB       │ │• FaceNet │ │• OpenCV      │
        │• Auth       │ │• FAISS   │ │• Threading   │
        │• Storage    │ │• SORT    │ │• Tracking    │
        └─────────────┘ └──────────┘ └──────────────┘
```

---

## Authentication Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                      JWT AUTHENTICATION FLOW                     │
└──────────────────────────────────────────────────────────────────┘

1. LOGIN REQUEST
   ┌─────────────────┐         HTTP POST
   │   Mobile/Web    │────────────────────────┐
   │   User Inputs   │                        │
   │   Credentials   │                        │
   └─────────────────┘                        │
                                              │
                                              ▼
                                    ┌───────────────┐
                                    │ Backend Auth  │
                                    │  Endpoint     │
                                    │  /auth/login  │
                                    └───────┬───────┘
                                            │
                                            ▼
                                    ┌───────────────┐
                        JWT Token   │ Validate Creds│
                         ◄──────────│ Generate JWT  │
                                    │ Return Token  │
                                    └───────────────┘

2. STORE TOKEN (Secure)
   ┌─────────────────────────────────────┐
   │ Mobile: FlutterSecureStorage        │
   │         (Encrypted, OS-level)       │
   └─────────────────────────────────────┘
   
   ┌─────────────────────────────────────┐
   │ Web: localStorage                   │
   │     (Session-based storage)         │
   └─────────────────────────────────────┘

3. SUBSEQUENT REQUESTS (Auto-Inject Token)
   ┌──────────────────┐
   │  Any API Call    │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────────────────────┐
   │ Request Interceptor              │
   │ - Get token from storage         │
   │ - Add header:                    │
   │   Authorization: Bearer <token>  │
   └────────┬─────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────┐
   │ Backend Validates Token          │
   │ (JWT Middleware)                 │
   │ - Decode JWT                     │
   │ - Check expiry                   │
   │ - Extract user info              │
   └────────┬─────────────────────────┘
            │
       YES  ▼  NO
     ┌──────────────┐
     ▼              ▼
  Process      Return 401
  Request
```

---

## Real-time Data Sync Flow

```
┌──────────────────────────────────────────────────────────────────┐
│              LIVE ATTENDANCE DASHBOARD SYNC                      │
└──────────────────────────────────────────────────────────────────┘

FRONTEND (POLLING)
    │
    ├─ Interval: 5 seconds
    │
    ▼
GET /api/v1/attendance/live
    │
    ├─ Browser/App Makes Request
    ├─ Axios/DIO client + Bearer Token
    ├─ HTTP → Backend on :8000
    │
    ▼
BACKEND (REQUEST HANDLER)
    │
    ├─ Authentication Middleware
    │  └─ Validates JWT token
    │
    ├─ Route Handler
    │  └─ `/api/v1/attendance/live`
    │  └─ Optional: ?courseId=X&limit=50
    │
    ├─ Database Query
    │  └─ Firestore: Query attendance collection
    │  └─ Filter: course_id, timestamp, status
    │  └─ Limit: 50 records
    │  └─ Sort: by marked_at DESC
    │
    ▼
FIREBASE FIRESTORE
    │
    ├─ Collection: /attendance
    ├─ Query: WHERE course_id=X AND status IN [present, late...]
    ├─ Return: Last 50 records with:
    │  ├─ Student name, ID, avatar
    │  ├─ Course name
    │  ├─ Timestamp (marked_at)
    │  ├─ Status (present/late/absent/excused)
    │  └─ Confidence score
    │
    ▼
BACKEND (SERIALIZE RESPONSE)
    │
    ├─ Convert Firestore docs → JSON
    ├─ Add metadata (last_updated timestamp)
    ├─ Compress if needed
    ├─ Return with HTTP 200
    │
    ▼
FRONTEND (RECEIVE DATA)
    │
    ├─ Response interceptor catches result
    ├─ Parse JSON → TypeScript interfaces
    ├─ Validate with Zod schemas
    ├─ Update Zustand store (React) / Riverpod (Flutter)
    ├─ Trigger UI re-render
    │
    └─ Display updated attendance cards
       ├─ Show Present: 45
       ├─ Show Late: 8
       ├─ Show Absent: 5
       └─ Show Excused: 2
    
    REPEAT after 5 seconds
```

---

## Attendance Marking Flow (AI Pipeline)

```
┌──────────────────────────────────────────────────────────────────┐
│          ATTENDANCE AUTO-MARKING VIA FACE RECOGNITION           │
└──────────────────────────────────────────────────────────────────┘

1. CAPTURE
   ┌───────────────────┐
   │  RTSP Stream      │
   │  OR Webcam        │
   │  (OpenCV)         │
   └────────┬──────────┘
            │ Video frames
            ▼

2. FACE DETECTION (YOLOv8)
   ┌───────────────────┐
   │  YOLOv8 Model     │
   │  Input: Frame     │
   │  Output: Face     │
   │  Bounding boxes   │
   │  + confidence     │
   └────────┬──────────┘
            │ Detected faces
            ▼

3. EMBEDDING GENERATION (FaceNet)
   ┌───────────────────┐
   │  FaceNet Model    │
   │  Input: Face crop │
   │  Output: 128D     │
   │  embedding vector │
   │  (Face signature) │
   └────────┬──────────┘
            │ Face embeddings
            ▼

4. STUDENT MATCHING (FAISS)
   ┌───────────────────┐
   │  FAISS Index      │
   │  Query: embedding │
   │  Top-k: 5 results │
   │  Return: student  │
   │  IDs + distances  │
   └────────┬──────────┘
            │ Top matches
            ▼

5. VERIFICATION & SCORING
   ┌───────────────────┐
   │  Confidence       │
   │  Threshold: 0.6   │
   │  Temporal check:  │
   │  No duplicate in  │
   │  last 5 mins      │
   │  Min face size:   │
   │  20x20 pixels     │
   └────────┬──────────┘
            │ Verified match
            ▼

6. MULTI-OBJECT TRACKING (SORT)
   ┌───────────────────┐
   │  SORT Tracker     │
   │  Buffer: 30 frames│
   │  Track across     │
   │  video frames     │
   │  Avoid duplicates │
   │  Smooth trajectory│
   └────────┬──────────┘
            │ Tracked detections
            ▼

7. DATABASE STORAGE
   ┌───────────────────┐
   │  Firebase Store   │
   │  Document:        │
   │  {                │
   │   student_id,     │
   │   course_id,      │
   │   marked_at,      │
   │   confidence,     │
   │   status          │
   │  }                │
   └────────┬──────────┘
            │ Stored
            ▼

8. API RESPONSE
   ┌───────────────────┐
   │  Frontend Gets    │
   │  New Attendance   │
   │  Record via:      │
   │  GET /attendance/ │
   │  live (polling)   │
   │                   │
   │  Display Updated  │
   │  on Dashboard     │
   └───────────────────┘
```

---

## Request/Response Example: Get Live Attendance

```
┌─────────────────────────────────────────────────────────────────┐
│                    REQUEST (Frontend → Backend)                 │
├─────────────────────────────────────────────────────────────────┤

GET http://localhost:8000/api/v1/attendance/live?courseId=COURSE123&limit=50

Headers:
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  Content-Type: application/json
  User-Agent: Mozilla/5.0 (or Dio/Flutter)

Body: (empty)

```

```
┌─────────────────────────────────────────────────────────────────┐
│                   RESPONSE (Backend → Frontend)                 │
├─────────────────────────────────────────────────────────────────┤

HTTP/1.1 200 OK

Headers:
  Content-Type: application/json
  Access-Control-Allow-Origin: http://localhost:5173
  Cache-Control: no-cache
  Date: Mon, 11 Apr 2026 10:30:45 GMT

Body (JSON):
[
  {
    "id": "att_001",
    "student_name": "Ahmed Hassan",
    "student_id": "STU001",
    "course_name": "Data Structures",
    "marked_at": "2026-04-11T10:25:30Z",
    "status": "present",
    "avatar_url": "https://firebase-storage.../profile_001.jpg",
    "confidence": 0.95
  },
  {
    "id": "att_002",
    "student_name": "Fatima Al-Mansouri",
    "student_id": "STU002",
    "course_name": "Data Structures",
    "marked_at": "2026-04-11T10:24:15Z",
    "status": "late",
    "avatar_url": "https://firebase-storage.../profile_002.jpg",
    "confidence": 0.87
  },
  ...
]

```

---

## File Transfer Path (Student Avatar/Images)

```
┌──────────────────────────────────────────────────────────────────┐
│              FILE UPLOAD & SERVING FLOW                          │
└──────────────────────────────────────────────────────────────────┘

1. STUDENT REGISTRATION (App/Dashboard)
   │
   ├─ Camera capture face photo
   ├─ Compress image
   │
   ▼
   POST /api/v1/students/register
   Body: {multipart/form-data}
     - student_id: "STU001"
     - name: "Ahmed"
     - email: "ahmed@uni.edu"
     - face_image: <binary image data>
   
   ▼
   BACKEND:
   - Save image to Firebase Storage
   - Extract face embedding
   - Store embedding in Firestore
   - Return firebase_storage_url
   
   ▼
   FRONTEND:
   - Store returned URL in state
   - Display avatar in student cards
   
   ▼
   LATER - GET ATTENDANCE RECORDS:
   - Response includes avatar_url
   - Frontend loads from Firebase CDN
   - Displayed in attendance cards

```

---

## Error Handling & Recovery

```
┌──────────────────────────────────────────────────────────────────┐
│             ERROR HANDLING ACROSS COMPONENTS                     │
└──────────────────────────────────────────────────────────────────┘

SCENARIO 1: Token Expired (401)
   Frontend Request
        │
        ▼
   Response: 401 Unauthorized
        │
        ├─ Response Interceptor caught the 401
        ├─ POST /api/v1/auth/refresh
        ├─ Get new token
        ├─ Retry original request with new token
        │
        ▼
   Success ✅

SCENARIO 2: Network Offline
   Frontend Request
        │
        ▼
   ERROR: Network Timeout (>15 seconds)
        │
        ├─ Error interceptor logs error
        ├─ Show toast: "Connection timeout. Try again."
        ├─ User clicks retry
        ├─ Query resent
        │
        ▼
   Success (or fail again) ✅

SCENARIO 3: Backend Down
   Frontend Request
        │
        ▼
   ERROR: Connection refused
        │
        ├─ Show alert: "Backend server offline"
        ├─ Display last cached data
        ├─ Show "Offline mode" indicator
        ├─ Retry periodically
        │
        ▼
   When backend comes back online → auto-sync ✅

SCENARIO 4: Firebase Credentials Missing
   Backend Startup
        │
        ▼
   ERROR: Firebase credentials not found
        │
        ├─ Log warning in startup
        ├─ Continue without Firebase
        ├─ API still responds (uses in-memory cache)
        ├─ Data NOT persisted
        │
        └─ ⚠️ NEEDS FIX before production

SCENARIO 5: Malformed Data
   Frontend receives response
        │
        ▼
   Response doesn't match TypeScript interface
        │
        ├─ Zod validation fails
        ├─ Error caught
        ├─ Show user: "Data format error"
        ├─ Log to console
        │
        ▼
   Fail gracefully ✅
```

---

## Port Configuration Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      PORT MAPPING                                │
└──────────────────────────────────────────────────────────────────┘

PRIMARY COMPONENTS
├─ Backend API
│  ├─ Port: 8000
│  ├─ URL: http://localhost:8000
│  ├─ Endpoints: http://localhost:8000/docs (Swagger UI)
│  │
│  ├─ Exposed Ports:
│  │  ├─ 0.0.0.0:8000/api/v1/* (REST API)
│  │  ├─ 0.0.0.0:8000/docs (Swagger)
│  │  ├─ 0.0.0.0:8000/redoc (ReDoc)
│  │  └─ 0.0.0.0:8000/openapi.json (OpenAPI spec)
│  │
│  └─ Uses:
│     └─ FastAPI + Uvicorn
│
├─ Web Dashboard
│  ├─ Dev Port: 5173 (Vite)
│  ├─ URL: http://localhost:5173
│  ├─ Prod Port: 3000 (Node/PM2/nginx)
│  │
│  └─ Calls:
│     └─ Backend at http://localhost:8000
│
├─ Flutter Mobile App
│  ├─ Dev: Dynamic (emulator/device)
│  ├─ Emulator API proxy: 10.0.2.2:8000
│  ├─ Physical device: 192.168.x.x:8000
│  │
│  └─ Calls:
│     └─ Backend via configured IP
│
└─ Firebase
   ├─ Cloud endpoint: firebaseio.com
   ├─ Port: 443 (HTTPS)
   │
   └─ Called by:
      └─ Backend Python SDK
```

---

**All connections visualized. System is ready for integration testing!**
