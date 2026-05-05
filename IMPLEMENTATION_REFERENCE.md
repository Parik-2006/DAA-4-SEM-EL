# Complete File Structure Reference for Redesign

## Directory Structure

```
attendance_backend/
├── api/
│   ├── __init__.py
│   ├── admin.py          ← Modify: Add admin-only filtering
│   ├── auth.py           ← NEW: Login endpoint
│   ├── attendance.py      ← Modify: Add role checks, timetable validation
│   ├── student.py         ← Modify: Filter to own data only
│   ├── teacher.py         ← Modify: Add teacher role checks, section filtering
│   ├── courses.py         ← May need role filtering
│   ├── timetable.py       ← NEW: Timetable endpoints
│   └── health.py
│
├── database/
│   ├── __init__.py
│   ├── firebase_client.py ← Modify: Add section parameter to queries
│   ├── attendance_repository.py ← Modify: Add role-aware queries
│   ├── student_repository.py ← Modify: Add section filtering
│   ├── user_repository.py ← Modify: Add role/permission queries
│   ├── section_repository.py ← NEW: Handle section data
│   ├── timetable_repository.py ← NEW or Modify: Query by time
│   └── course_repository.py ← NEW: Course data access
│
├── services/
│   ├── __init__.py
│   ├── admin_service.py ← Existing
│   ├── attendance_service.py ← Modify: Add section awareness
│   ├── auth_service.py ← NEW: JWT token generation/validation
│   ├── realtime_service.py ← NEW: WebSocket/SSE broadcasting
│   ├── timetable_service.py ← NEW: Get active periods
│   ├── audit_service.py ← NEW: Log all changes
│   ├── permission_service.py ← NEW: Permission checking
│   └── firebase_service.py ← Existing
│
├── middleware/
│   ├── __init__.py
│   ├── auth_middleware.py ← NEW: JWT validation, user context
│   ├── permission_middleware.py ← NEW: Permission checking per route
│   ├── audit_middleware.py ← NEW: Log all requests/responses
│   └── error_handler.py ← NEW: Centralized error handling
│
├── decorators/
│   ├── __init__.py
│   └── auth_decorators.py ← NEW: @require_role(), @require_resource_access()
│
├── utils/
│   ├── __init__.py
│   ├── rate_limiter.py ← NEW: Per-role rate limiting
│   ├── time_validator.py ← NEW: Check if marking is allowed
│   ├── permission_checker.py ← NEW: Helper for permission checks
│   └── csv_parser.py ← Existing
│
├── schemas/
│   ├── __init__.py
│   ├── user_schemas.py ← Modify: Add role field
│   ├── attendance_schemas.py ← Modify: Add section, period info
│   ├── teacher_schemas.py ← Existing, may add role info
│   ├── auth_schemas.py ← NEW: Login request/response
│   ├── timetable_schemas.py ← NEW: Period information
│   └── permission_schemas.py ← NEW: Permission objects
│
├── models/
│   ├── __init__.py
│   ├── facenet_extractor.py ← Existing (no changes)
│   ├── model_manager.py ← Existing (no changes)
│   ├── yolov8_detector.py ← Existing (no changes)
│   ├── user_model.py ← NEW or Modify: Add role enum
│   ├── role_model.py ← NEW: Define roles and permissions
│   └── permission_model.py ← NEW: Permission definitions
│
├── config/
│   ├── __init__.py
│   ├── constants.py ← Modify: Add ROLE_PERMISSIONS mapping, USER_ROLES
│   ├── settings.py ← Existing (may add JWT secret)
│   ├── logging_config.py ← Existing
│   └── firebase-credentials.json ← Existing
│
├── scripts/
│   ├── bootstrap_embeddings.py ← Existing
│   ├── seed_students_with_names.py ← Existing
│   ├── add_section_to_attendance.py ← NEW: Migration script
│   └── init_roles_permissions.py ← NEW: Initialize role/permission system
│
├── tests/
│   ├── test_auth.py ← NEW: Test authentication
│   ├── test_permissions.py ← NEW: Test role-based access
│   ├── test_timetable.py ← NEW: Test period validation
│   └── test_attendance.py ← NEW: Test role-filtered queries
│
├── firestore.indexes.json ← Modify: Add section-based composite indexes
├── main.py ← Modify: Add auth middleware, WebSocket support
├── requirements.txt ← Modify: Add websockets, jwt libraries
└── logs/
    └── attendance_api.log ← Existing

web-dashboard/
├── src/
│   ├── pages/
│   │   ├── AttendancePage.tsx ← No changes (receives role-specific data)
│   │   ├── DashboardPage.tsx ← No changes (receives role-specific data)
│   │   └── LoginPage.tsx ← NEW: Simple login form
│   ├── components/
│   │   ├── Layout.tsx ← Modify: Show role-specific menu
│   │   └── LoginForm.tsx ← NEW: Login component
│   └── services/
│       └── api.ts ← Modify: Add auth token to requests
│
└── No other frontend changes needed!
```

---

## Firestore Collections Schema

### Before Redesign
```
Firestore
├── students/
│   └── STU001 { name, email }
├── attendance/
│   └── ATT001 { student_id, date, status }
└── users/
    └── USER001 { email, password_hash }
```

### After Redesign
```
Firestore
├── users/
│   └── USER001 { email, password_hash, role: 'admin'|'teacher'|'student', 
│                  section_id, assigned_sections[] }
├── roles/
│   ├── admin { permissions: [...] }
│   ├── teacher { permissions: [...] }
│   └── student { permissions: [...] }
├── permissions/
│   ├── list_attendance { name, description }
│   ├── mark_attendance { name, description }
│   ├── view_analytics { name, description }
│   └── manage_users { name, description }
├── courses/
│   └── COURSE001 { name, code, credits }
├── sections/
│   └── SEC001 { course_id, section_name: 'CSE_C', semester, year }
├── enrollments/
│   └── ENR001 { student_id, section_id, enrollment_date }
├── course_assignments/
│   └── CA001 { teacher_id, section_id, courses[], start_date }
├── timetable/
│   └── TIME001 { section_id, course_id, day: 'Monday', start_time, end_time, room }
├── attendance/
│   └── ATT001 { student_id, section_id, period_id, date, status, marked_by_teacher_id, timestamp }
└── audit_logs/
    └── LOG001 { user_id, action: 'mark_attendance', resource: 'attendance', 
                 resource_id, timestamp, ip_address, details }
```

---

## Key Implementation Points

### 1. JWT Token Structure
```json
{
  "user_id": "USER123",
  "email": "teacher@school.com",
  "role": "teacher",
  "assigned_sections": ["SEC001", "SEC002"],
  "permissions": ["mark_attendance", "view_analytics"],
  "iat": 1234567890,
  "exp": 1234571490
}
```

### 2. Permission Matrix
```
ADMIN:
  - list_all_students
  - list_all_attendance
  - manage_users
  - manage_sections
  - view_analytics
  - upload_timetable

TEACHER:
  - list_assigned_students
  - list_assigned_attendance
  - mark_attendance (only during period)
  - view_section_analytics

STUDENT:
  - view_own_attendance
  - view_own_analytics
```

### 3. Data Filtering Examples
```python
# Get attendance for teacher
# Teacher can only see students in their assigned sections
attendance = db.collection('attendance')\
  .where('section_id', 'in', user.assigned_sections)\
  .where('date', '==', today)\
  .stream()

# Get attendance for student
# Student can only see own records
attendance = db.collection('attendance')\
  .where('student_id', '==', user.user_id)\
  .stream()

# Get attendance for admin
# Admin can see all
attendance = db.collection('attendance')\
  .stream()
```

---

## Implementation Sequence

### Phase 1: Authentication (Day 1)
1. Create user role schema (models/role_model.py)
2. Add role field to users collection
3. Create auth service (services/auth_service.py)
4. Create login endpoint (api/auth.py)
5. Add JWT validation middleware

### Phase 2: Timetable & Sections (Day 2)
6. Create courses, sections collections
7. Create timetable schema and repository
8. Add timetable validation to attendance marking
9. Create enrollment data

### Phase 3: Data Filtering (Day 3)
10. Update all repository queries with role filtering
11. Add permission checking decorators
12. Update all API endpoints with role checks
13. Test data isolation per role

### Phase 4: Real-time & Audit (Day 4)
14. Add WebSocket support
15. Implement real-time event broadcasting
16. Add audit logging
17. Create audit log collection

### Phase 5: Security & Testing (Day 5)
18. Add rate limiting
19. Add error handling middleware
20. Write comprehensive tests
21. Security review and fixes

---

## Testing Checklist

- [ ] Admin can login
- [ ] Teacher can login  
- [ ] Student can login
- [ ] Admin sees all data
- [ ] Teacher sees only assigned section data
- [ ] Student sees only own data
- [ ] Teacher cannot mark attendance outside period
- [ ] Attendance marks update dashboard in real-time
- [ ] All changes logged to audit_logs
- [ ] No data leakage between sections
- [ ] Rate limiting works
- [ ] JWT expires and requires relogin
- [ ] Invalid token rejected
