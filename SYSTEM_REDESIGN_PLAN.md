# Smart Attendance System - Redesign Plan

## Current Issues
1. ❌ No role-based access control (RBAC)
2. ❌ All attendance data visible to all users
3. ❌ No timetable-based attendance workflow
4. ❌ Dashboard shows generic data, not role-specific
5. ❌ Students can see/mark attendance for all classes
6. ❌ No real-time dashboard updates
7. ❌ Missing Admin/Student/Teacher roles

## Redesign Objectives

### 1. Authentication & Authorization Layer
- Separate login for Admin, Teachers, Students
- JWT-based token system with role claims
- Permission checks at API level (not frontend)
- Session management with expiry

### 2. Timetable-Driven Workflow
- Attendance marking only during scheduled periods
- Auto-lock attendance after class period ends
- Teachers can only mark for their assigned classes
- Real-time validation against timetable

### 3. Data Isolation & Security
- Students see only their own attendance
- Teachers see only their assigned sections/classes
- Admin sees all data with analytics
- Course-section-student mapping in database

### 4. Dashboard Intelligence
- Role-specific views (Admin/Teacher/Student)
- Real-time update when attendance is marked
- Attendance rate calculations per section
- Period-wise attendance trends

### 5. API Security
- Role-based endpoint access
- Resource-level authorization checks
- Audit logging for all attendance changes
- Rate limiting per role

### 6. State Management
- Separation of concerns (UI vs Business Logic)
- Backend-driven authorization (not trusting frontend)
- Consistent state across web/mobile

## Reference Architecture Comparison

### How Industry Apps Work (Jigsaw, MangoERP, etc.)
1. **Role Assignment**: Admin creates users with roles
2. **Login**: User logs in, gets JWT with role+permissions
3. **View Filtering**: Each page shows only user's data
4. **Action Validation**: Server validates every action against role
5. **Audit Trail**: All changes logged with user+timestamp
6. **Real-time Sync**: WebSocket for instant updates

### Our Redesigned Approach
- Admin Panel: User mgmt, section assignment, timetable upload
- Teacher Portal: Mark attendance for assigned classes during period
- Student Dashboard: View personal attendance + analytics
- Real-time sync: WebSocket events when attendance changes
- Audit Log: Track all attendance changes with admin who made it

## Files to Modify

### Backend API
- `attendance_backend/api/admin.py` - Role checks
- `attendance_backend/api/teacher.py` - NEW: Teacher endpoints
- `attendance_backend/api/student.py` - Restrict to own data
- `attendance_backend/api/auth.py` - NEW: Auth with roles
- `attendance_backend/schemas/` - Add role/permission schemas
- `attendance_backend/database/` - Role-based queries
- `attendance_backend/config/constants.py` - Permission mappings

### Database
- `attendance_backend/models/` - User roles, permissions
- Firestore collections: users, roles, permissions, courses, sections, timetable

### Frontend
- No changes needed - same UI, different data served

## Deployment Strategy
1. Create new permission/role system (backward compatible)
2. Update database with user roles
3. Update API to check permissions
4. Create login page (simple form)
5. Test each role separately
6. Gradual rollout

---

## 6 Claude Prompts (See below)
