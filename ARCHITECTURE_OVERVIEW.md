# System Architecture Comparison & Design Overview

## How Industry Attendance Apps Work

### Jigsaw (School Management System)
1. **Multi-tenancy**: Each school is isolated in database
2. **Role Hierarchy**: Admin → Principal → Teacher → Student
3. **Section Management**: Classes organized by section, year, stream
4. **Timetable-Driven**: Attendance marking tied to scheduled periods
5. **Real-time Sync**: Teachers mark → Dashboard updates instantly
6. **Audit Trail**: Every action logged with user+timestamp
7. **Analytics**: Role-specific dashboards with insights

### MangoERP (Educational ERP)
1. **User Management**: Centralized user creation with roles
2. **Authentication**: JWT/OAuth with session management
3. **Permission Model**: Granular permissions per role
4. **Data Isolation**: Section-wise data separation
5. **Workflow Automation**: Period-based attendance marking
6. **Reporting**: Admin-level analytics and reports
7. **Mobile Support**: Same backend, different frontends

### Our Redesigned System (Following Industry Best Practices)

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (No Changes)                   │
│  AttendancePage │ DashboardPage │ LoginPage (NEW)            │
└────────────────────────────────────────────────────────────┬─┘
                                                               │
                              HTTP/WebSocket                  │
                                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (Modified)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Auth Middleware (JWT Validation)             │   │
│  └──────────────┬──────────────────────────────────────┘   │
│                 │                                            │
│  ┌──────────────▼──────────────────────────────────────┐   │
│  │    Permission Middleware (Role Check)               │   │
│  └──────────────┬──────────────────────────────────────┘   │
│                 │                                            │
│  ┌──────────────▼──────────────────────────────────────┐   │
│  │         Route Handlers                              │   │
│  │  ├─ POST /auth/login (public)                      │   │
│  │  ├─ GET /admin/attendance (admin only)             │   │
│  │  ├─ GET /teacher/sections (teacher only)           │   │
│  │  ├─ POST /attendance/mark (teacher, timetable validation)  │
│  │  └─ GET /student/attendance (own data only)        │   │
│  └──────────────┬──────────────────────────────────────┘   │
│                 │                                            │
│  ┌──────────────▼──────────────────────────────────────┐   │
│  │         Audit Middleware (Log Changes)              │   │
│  └──────────────┬──────────────────────────────────────┘   │
│                 │                                            │
│  ┌──────────────▼──────────────────────────────────────┐   │
│  │         Real-time Service (WebSocket)               │   │
│  │         Broadcast events to connected clients        │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────┬────────────────────────────────────────────┘
                 │
          Database Calls
                 │
         ┌───────▼────────┐
         │ Service Layer  │
         │ ├─ Auth        │
         │ ├─ Timetable   │
         │ ├─ Attendance  │
         │ └─ Audit       │
         └───────┬────────┘
                 │
         ┌───────▼────────────────────┐
         │    Repository Layer        │
         │ ├─ Role-aware queries      │
         │ ├─ Section filtering       │
         │ └─ Permission checks       │
         └───────┬────────────────────┘
                 │
         ┌───────▼──────────────────────────────────┐
         │      Firebase Firestore Database          │
         │  Collections:                             │
         │  ├─ users (with roles)                   │
         │  ├─ courses                              │
         │  ├─ sections                             │
         │  ├─ enrollments                          │
         │  ├─ course_assignments                   │
         │  ├─ timetable                            │
         │  ├─ attendance (with section_id)         │
         │  └─ audit_logs                           │
         └──────────────────────────────────────────┘
```

## Data Flow: Teacher Marks Attendance

```
1. Teacher opens app
   ↓
2. Login → JWT token with role='teacher', assigned_sections=['SEC001']
   ↓
3. Dashboard loads
   → API: GET /teacher/sections?teacher_id=T123
   → Middleware checks role (teacher) ✓
   → Repository filters: assigned_sections = ['SEC001']
   → Returns only SEC001 data ✓
   ↓
4. Teacher clicks "Mark Attendance" for SEC001
   → API: POST /attendance/mark
   → Middleware validates JWT ✓
   → Service: Check if current time is within timetable period for SEC001 ✓
   → Service: Validate teacher is assigned to SEC001 ✓
   → Repository: Save to attendance collection with section_id='SEC001'
   → Audit: Log "Teacher T123 marked attendance for SEC001, timestamp"
   → WebSocket: Broadcast 'attendance_marked' event to all connected clients viewing SEC001
   ↓
5. Real-time update
   → All teacher dashboards viewing SEC001 see the new marks instantly
   → All student dashboards (in SEC001) see updated attendance rate
   → Admin dashboard gets updated analytics
```

## Data Flow: Student Views Attendance

```
1. Student opens app
   ↓
2. Login → JWT token with role='student', student_id='STU001'
   ↓
3. Dashboard loads
   → API: GET /student/attendance?student_id=STU001
   → Middleware checks role (student) ✓
   → Middleware checks: requested_student_id == JWT.student_id ✓
   → Repository filters: attendance.student_id = 'STU001' only
   → Returns only own attendance data ✓
   ↓
4. Attendance displayed
   → Shows STU001's attendance record only
   → Cannot see other students' data
   → Cannot see data from other sections
```

## Security Boundaries

### What Each Role CAN Do

**ADMIN**
- Create/edit/delete users
- Assign roles to users
- Manage sections and courses
- Upload timetable
- View all attendance records
- View analytics dashboard
- View audit logs

**TEACHER**
- View assigned sections only
- Mark attendance for assigned sections
- Only during scheduled class periods
- View section-level analytics
- View attendance for students in assigned sections

**STUDENT**
- View own attendance record
- View own attendance analytics
- Cannot modify any data
- Cannot see other students' data

### What Each Role CANNOT Do

**ADMIN**
- Cannot mark attendance (not authenticated to do so)

**TEACHER**
- Cannot see sections they're not assigned to
- Cannot mark attendance outside class period
- Cannot modify past attendance (optional: after grace period)
- Cannot view other teachers' sections

**STUDENT**
- Cannot mark attendance
- Cannot modify attendance
- Cannot access teacher/admin data
- Cannot see other students' records

---

## Database Query Examples

### Teacher Fetching Their Sections
```python
# JWT contains: assigned_sections = ['SEC001', 'SEC002']
sections = db.collection('sections')\
  .where('section_id', 'in', user.assigned_sections)\
  .stream()
```

### Preventing Cross-Section Access
```python
# Teacher tries to mark attendance for SEC003 (not assigned)
attendance = {
  'student_id': 'STU001',
  'section_id': 'SEC003',  # DANGER: SEC003 not in user.assigned_sections
  'status': 'present'
}

# Middleware blocks it:
if attendance['section_id'] not in user.assigned_sections:
  raise PermissionError("Cannot mark attendance for unauthorized section")
```

### Timetable-Based Validation
```python
# Teacher tries to mark attendance at 9:00 PM
current_time = 21:00

# Get active periods for teacher's assigned sections
active_periods = db.collection('timetable')\
  .where('section_id', 'in', user.assigned_sections)\
  .where('day', '==', current_day)\
  .where('start_time', '<=', current_time)\
  .where('end_time', '>=', current_time)\
  .stream()

if not active_periods:
  raise ValueError("No active period for marking attendance")
```

---

## Real-time Architecture (WebSocket)

```
Connected Teacher 1     Connected Teacher 2     Connected Student
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │
                           WebSocket
                          Server (Uvicorn)
                                │
                    ┌───────────┼───────────┐
                    │           │           │
                 Event: "attendance_marked"
                section_id='SEC001'
                    │           │           │
                ┌───▼───┐  ┌───▼───┐  ┌───▼───┐
                │ Check │  │ Check │  │ Check │
                │SEC001?│  │SEC001?│  │SEC001?│
                └───┬───┘  └───┬───┘  └───┬───┘
                    │           │           │
              Update view  Update view  Update view
```

---

## Implementation Timeline

| Phase | Duration | Key Tasks | Files Modified |
|-------|----------|-----------|-----------------|
| 1: Auth | 1 day | JWT, roles, login | auth.py, auth_service.py, user_schemas.py |
| 2: Timetable | 1 day | Period validation, courses/sections | timetable_service.py, attendance.py |
| 3: Filtering | 1 day | Role-based data queries | All repositories, all API endpoints |
| 4: Real-time | 0.5 day | WebSocket events | realtime_service.py, main.py |
| 5: Audit | 0.5 day | Logging changes | audit_service.py, audit_middleware.py |
| 6: Testing | 1 day | Unit & integration tests | test_auth.py, test_permissions.py |

**Total: 5 days to production-ready system**

---

## Frontend: Zero Changes Required

The existing frontend works perfectly! It will simply:
1. Receive a login redirect (or login modal)
2. Store JWT token
3. Send JWT in Authorization header
4. Receive role-specific data
5. Display only what it receives

No code changes needed in React/TypeScript! The backend now serves different data per role.

---

## Migration Path from Current System

1. **Day 0**: Backup existing data
2. **Day 1-2**: Run migration script to add section_id to all existing attendance records
3. **Day 3**: Deploy new role system (backward compatible)
4. **Day 4**: Create first admin user
5. **Day 5**: Upload timetable and user data
6. **Day 6**: Test with live users
7. **Day 7**: Go live

All existing data preserved, zero data loss!
