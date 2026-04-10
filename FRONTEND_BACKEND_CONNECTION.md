# Frontend-Backend Connection Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web Browser                                  │
│  ┌──────────────────────────────────────┐                      │
│  │    React Dashboard (Frontend)         │                      │
│  │  - Dashboard Page                    │                      │
│  │  - History Page                      │                      │
│  │  - Students Page                     │                      │
│  │  - Settings Page                     │                      │
│  └──────────┬───────────────────────────┘                      │
└─────────────┼────────────────────────────────────────────────────┘
              │ HTTP/REST API
              │ (Axios Client)
              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Backend API Server (FastAPI)                       │
│  ┌──────────────────────────────────────┐                      │
│  │    REST Endpoints                    │                      │
│  │  /api/v1/attendance/live             │                      │
│  │  /api/v1/attendance/stats            │                      │
│  │  /api/v1/attendance/history          │                      │
│  │  /api/v1/students                    │                      │
│  │  /api/v1/courses                     │                      │
│  │  /api/v1/health                      │                      │
│  └──────────┬───────────────────────────┘                      │
└─────────────┼────────────────────────────────────────────────────┘
              │
              ▼
      Database + Face Recognition
      (PostgreSQL + TensorFlow)
```

---

## API Endpoints Reference

### Base Configuration

**Development:**
```
API_BASE_URL=http://localhost:8000
TIMEOUT=15000ms
```

**Production (Render):**
```
API_BASE_URL=https://attendance-api.onrender.com
TIMEOUT=15000ms
```

### Authentication

All requests should include Authorization header:
```json
{
  "Authorization": "Bearer <JWT_TOKEN>"
}
```

The Axios client automatically injects the token from localStorage:

```typescript
// Stored as: localStorage.setItem('token', 'your_jwt_token')
// Automatically added by interceptor
headers: {
  "Authorization": "Bearer " + token
}
```

### Core Endpoints

#### 1. Health Check
**Purpose:** Verify backend is running

```http
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "uptime": 3600,
  "version": "1.0.0"
}
```

**Dashboard Usage:** System status indicator

---

#### 2. Live Attendance
**Purpose:** Get real-time attendance records

```http
GET /api/v1/attendance/live?courseId=COURSE123&limit=50
```

**Query Parameters:**
- `courseId` (optional): Filter by course
- `limit` (optional, default=50): Number of records

**Response:**
```json
[
  {
    "id": "att_123",
    "student_name": "Ahmad Hassan",
    "student_id": "S001",
    "course_name": "CS101 - Data Structures",
    "marked_at": "2024-01-15T10:30:45Z",
    "status": "present",
    "avatar_url": "https://api.com/avatars/s001.jpg",
    "confidence": 0.95
  }
]
```

**Dashboard Usage:**
```typescript
// Fetched every 5 seconds for real-time updates
const records = await attendanceAPI.getLiveAttendance(courseId);
useDashboardStore.setLiveRecords(records);
```

---

#### 3. Attendance Statistics
**Purpose:** Get summarized attendance counts

```http
GET /api/v1/attendance/stats?courseId=COURSE123&date=2024-01-15
```

**Query Parameters:**
- `courseId` (optional): Filter by course
- `date` (optional): Filter by date (ISO format)

**Response:**
```json
{
  "total_present": 45,
  "total_late": 8,
  "total_absent": 5,
  "total_excused": 2,
  "last_updated": "2024-01-15T10:30:45Z"
}
```

**Dashboard Usage:**
```typescript
// Displays StatCard components
const stats = await attendanceAPI.getAttendanceStats();
// Shows: 45 Present, 8 Late, 5 Absent, 2 Excused
```

---

#### 4. Attendance History
**Purpose:** Get paginated historical records with filtering

```http
GET /api/v1/attendance/history?courseId=COURSE123&startDate=2024-01-01&endDate=2024-01-31&page=1&limit=30
```

**Query Parameters:**
- `courseId` (optional): Filter by course
- `startDate` (optional): ISO format date
- `endDate` (optional): ISO format date
- `page` (default=1): Pagination page number
- `limit` (default=30): Records per page

**Response:**
```json
[
  {
    "id": "att_456",
    "student_name": "Fatima Ahmed",
    "student_id": "S102",
    "course_name": "CS101 - Data Structures",
    "marked_at": "2024-01-14T10:15:30Z",
    "status": "late",
    "avatar_url": "https://api.com/avatars/s102.jpg",
    "confidence": 0.92
  }
]
```

**Dashboard Usage:**
```typescript
// History Page with search, filtering, pagination
const history = await attendanceAPI.getAttendanceHistory(
  courseId,
  startDate,
  endDate,
  page,
  limit
);
```

---

#### 5. Attendance Summary
**Purpose:** Get aggregate statistics for date ranges

```http
GET /api/v1/attendance/summary?courseId=COURSE123&startDate=2024-01-01&endDate=2024-01-31
```

**Response:**
```json
{
  "total_students": 60,
  "total_records": 450,
  "average_attendance_rate": 0.87,
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "by_status": {
    "present": 350,
    "late": 60,
    "absent": 30,
    "excused": 10
  }
}
```

---

#### 6. Students List
**Purpose:** Get all student information

```http
GET /api/v1/students?courseId=COURSE123
```

**Query Parameters:**
- `courseId` (optional): Filter by course

**Response:**
```json
[
  {
    "id": "std_001",
    "name": "Ahmad Hassan",
    "student_id": "S001",
    "email": "ahmad@university.edu",
    "department": "Computer Science",
    "semester": "4",
    "avatar_url": "https://api.com/avatars/s001.jpg"
  }
]
```

**Dashboard Usage:**
```typescript
// Students Page - list all students with search/filter
const students = await attendanceAPI.getStudents(courseId);
```

---

#### 7. Courses List
**Purpose:** Get all available courses

```http
GET /api/v1/courses
```

**Response:**
```json
[
  {
    "id": "course_001",
    "code": "CS101",
    "name": "Data Structures",
    "instructor": "Dr. Mohamed",
    "students_count": 60
  },
  {
    "id": "course_002",
    "code": "CS102",
    "name": "Algorithms",
    "instructor": "Dr. Fatima",
    "students_count": 55
  }
]
```

**Dashboard Usage:**
```typescript
// Course filter buttons on Dashboard
const courses = await attendanceAPI.getCourses();
// Display as filter chips
```

---

## Implementation Details

### Request Flow

```typescript
// User clicks "Refresh" on Dashboard
→ DashboardPage calls handleRefresh()
→ fetchAttendanceData() triggered
→ attendanceAPI.getLiveAttendance() called
→ Axios request sent to /api/v1/attendance/live
→ Request Interceptor adds Bearer token
→ Backend receives authenticated request
→ Backend queries database
→ Response received with attendance records
→ Response Interceptor checks for 401
→ Data parsed and stored in Zustand store
→ React components re-render with new data
```

### Error Handling

**Scenario 1: Network Error**
```typescript
try {
  const data = await attendanceAPI.getLiveAttendance();
} catch (err) {
  setError(`Failed to fetch attendance: ${err.message}`);
  setSystemRunning(false);
}
```

**Scenario 2: 401 Unauthorized**
```typescript
// Response interceptor automatically:
// 1. Clears localStorage token
// 2. Redirects to /login
// 3. Shows "Session Expired" message
```

**Scenario 3: API Timeout**
```typescript
// Axios timeout: 15 seconds
// If backend doesn't respond, error thrown
setError('Request timeout - backend may be offline');
```

---

## Development Setup

### Step 1: Start Backend API

```bash
cd path/to/backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
# Backend runs on http://localhost:8000
```

### Step 2: Configure Frontend

```bash
cd web-dashboard
cp .env.example .env
# Edit .env:
# VITE_API_BASE_URL=http://localhost:8000
```

### Step 3: Start Frontend Dev Server

```bash
npm install
npm run dev
# Frontend runs on http://localhost:5173
```

### Step 4: Test Connection

1. Open http://localhost:5173 in browser
2. Open Developer Console (F12)
3. Check Dashboard page loads
4. Verify API requests appear in Network tab
5. Check for "System Online" indicator

---

## Production Deployment

### Backend Connection via Render

**Scenario:** Backend deployed on Render, Frontend deployed on Render

1. **Backend URL:** `https://attendance-api.onrender.com`
2. **Frontend .env:**
```env
VITE_API_BASE_URL=https://attendance-api.onrender.com
```

3. **CORS Configuration (Backend):**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://attendance-dashboard.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Verify Production Connection

```bash
# From browser console
fetch('https://attendance-api.onrender.com/api/v1/health')
  .then(r => r.json())
  .then(d => console.log('Backend status:', d))
```

---

## Polling Mechanism

### How Real-time Updates Work

```typescript
// Dashboard polls backend every 5 seconds
setInterval(async () => {
  const records = await attendanceAPI.getLiveAttendance();
  setLiveRecords(records);
}, 5000);
```

### Configure Polling Interval

**In `.env`:**
```env
VITE_POLLING_INTERVAL=5000  # milliseconds (5 seconds)
```

**In Settings Page:**
- Users can adjust interval from 1-60 seconds
- Lower values = faster updates, higher server load
- Recommended: 5-10 seconds for optimal performance

---

## Security Best Practices

1. **Never commit `.env` with real credentials**
2. **Use HTTPS in production** (auto-enabled on Render)
3. **Implement JWT expiration** (recommend 1 hour)
4. **Refresh tokens** before expiration
5. **Validate CORS** on backend
6. **Rate limit** API endpoints
7. **Use httpOnly cookies** for tokens (future enhancement)

---

## Troubleshooting Checklist

- [ ] Backend is running and accessible: `curl https://your-api.com/api/v1/health`
- [ ] `VITE_API_BASE_URL` matches your backend URL
- [ ] CORS is enabled on backend for your frontend URL
- [ ] Network tab shows successful API requests (200 status)
- [ ] No authentication 401 errors
- [ ] Console shows no TypeScript/JavaScript errors
- [ ] All environment variables are set in Render dashboard

---

## Monitoring

### Check API Performance

```typescript
// Add timing to requests
const startTime = Date.now();
const data = await attendanceAPI.getLiveAttendance();
const duration = Date.now() - startTime;
console.log(`Request took ${duration}ms`);
```

### Monitor System Health

Dashboard displays:
- System Online/Offline status (green/red dot)
- Last sync time
- Error messages
- Error log in browser console

---

## Future Enhancements

1. **WebSocket** instead of polling for true real-time
2. **Firebase Realtime** for cloud-based updates
3. **GraphQL** for efficient data fetching
4. **API Caching** to reduce server load
5. **Offline Mode** with service workers

---

## Support

For issues or questions:
1. Check this guide first
2. Review browser console for errors
3. Check Render deployment logs
4. Verify backend API is running
5. Contact backend team for API documentation
