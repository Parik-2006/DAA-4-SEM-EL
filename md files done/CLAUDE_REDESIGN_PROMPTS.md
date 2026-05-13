# 6 Claude Prompts for System Redesign

---

## PROMPT 1: Authentication & Role-Based Access Control (RBAC) Architecture

"Design a production-grade authentication and authorization system for our Smart Attendance application that currently has no role-based access control. We need to support three distinct user roles: Admin (manages system, creates users), Teacher (marks attendance for assigned classes), and Student (views own attendance). Currently all users can see all data. Please design: (1) User entity schema with roles and permissions, (2) JWT token structure including role claims and permissions, (3) Permission matrix mapping roles to actions (list_attendance, mark_attendance, view_analytics, manage_users), (4) Login endpoint that returns JWT with user metadata, (5) Middleware to validate JWT and check permissions before each API call, (6) Database schema for storing user roles, role-permission mappings, and user-role assignments. Reference files to review and modify: attendance_backend/database/user_repository.py (add role/permission queries), attendance_backend/api/user.py (add role to user registration), attendance_backend/config/constants.py (add ROLE_PERMISSIONS mapping), attendance_backend/schemas/user_schemas.py (add role/permission fields), attendance_backend/main.py (add auth middleware). Also create: attendance_backend/api/auth.py (new login endpoint), attendance_backend/services/auth_service.py (token generation and validation), attendance_backend/middleware/auth_middleware.py (permission checking). Ensure backward compatibility with existing attendance records."

---

## PROMPT 2: Timetable-Driven Attendance Marking Workflow

"Redesign our attendance marking system to be timetable-driven rather than allowing teachers to mark attendance anytime. Currently teachers can mark attendance at any moment for any class. We need: (1) A system where attendance can only be marked during scheduled class periods from the timetable, (2) Automatic attendance period detection based on current time and timetable, (3) Validation that prevents marking attendance outside class hours, (4) Period-specific marking (only the current period's students in the interface), (5) Locking mechanism after class period ends (optional: 15-minute grace period), (6) Teacher can only see/mark students in their assigned section during their assigned periods. Design should include: timetable schema with days, start_time, end_time, course, section, room, (2) CourseAssignment schema linking teacher to section+course, (3) API endpoint that returns available periods for logged-in teacher, (4) Attendance endpoint that validates period is active before accepting marks, (5) Real-time period status (in_progress, not_started, finished). Files to modify: attendance_backend/models/timetable.py (add period fields), attendance_backend/database/timetable_repository.py (query by current time), attendance_backend/api/attendance.py (add period validation), attendance_backend/schemas/attendance_schemas.py (add period info), attendance_backend/services/attendance_lock_service.py (extend with period checking). New files: attendance_backend/services/timetable_service.py (get current active periods), attendance_backend/utils/time_validator.py (check if marking is allowed)."

---

## PROMPT 3: Role-Based Dashboard & Real-time Data Updates

"Our dashboard currently shows generic attendance data to all users. Redesign it for role-specific views: Admin dashboard shows system-wide analytics (total students, overall attendance rate, section-wise breakdown, trends), Teacher dashboard shows only their assigned sections with attendance status for current period (who marked present/absent/pending), Student dashboard shows only their personal attendance record (present/absent for each period, attendance percentage, class-wise breakdown). Ensure: (1) Dashboard API endpoints return only role-specific, filtered data, (2) Real-time updates when attendance is marked (one teacher marks a student, all viewing the same section see it update), (3) Caching strategy for analytics (cache teacher's section data for 5 seconds), (4) Student cannot see other students' data, (5) Prevent frontend from requesting data it shouldn't access (all filtering on backend). Design real-time update mechanism using WebSocket or Server-Sent Events (SSE) where backend broadcasts 'attendance_marked' event to all connected clients viewing that section. Files to modify: attendance_backend/api/admin.py (add admin-only endpoints with aggregations), attendance_backend/api/teacher.py (filter to assigned sections only), attendance_backend/api/student.py (filter to own records), attendance_backend/database/attendance_repository.py (add role-aware query methods like 'get_section_attendance', 'get_student_attendance'), attendance_backend/schemas/attendance_schemas.py (add role-specific response schemas). New files: attendance_backend/services/realtime_service.py (WebSocket/SSE event broadcasting), attendance_backend/api/websocket.py (WebSocket connection handler)."

---

## PROMPT 4: Database Schema Redesign for Multi-Tenant Course-Section Isolation

"Our current database treats attendance as global. Redesign to isolate data by course-section so admin can have multiple sections (CSE C, CSE D, etc.) with complete data separation. Schema should include: (1) Course entity (id, name, code, credits), (2) Section entity (id, course_id, section_name, semester, year, capacity), (3) Enrollment entity linking students to sections (student_id, section_id, enrollment_date), (4) CourseAssignment entity linking teachers to sections (teacher_id, section_id, courses[], start_date), (5) Timetable entity with section_id (not global), (6) Attendance records with section_id context. Ensure: When querying attendance for a period, filter by section automatically based on user's role and assignment. Add database constraints so teachers can't access other sections' data at database level. Create composite indexes for queries like: get_section_attendance(section_id, date, period), get_student_attendance(student_id), get_teacher_sections(teacher_id). Files to review: attendance_backend/firestore.indexes.json (add section-based indexes), attendance_backend/database/firebase_client.py (add section parameter to queries). Firestore collections structure: users (with role field), courses, sections, enrollments, course_assignments, timetable (with section_id), attendance (with section_id). Add data migration script: attendance_backend/scripts/add_section_to_attendance.py to backfill existing data with default section 'CSE_C'."

---

## PROMPT 5: API Security Layer & Permission Middleware

"Implement a comprehensive security layer that validates every API call against user permissions and resource ownership. Currently anyone can access any endpoint. Design: (1) Permission decorator that checks required roles before method executes, (2) Resource authorization checks (teacher can only mark attendance for their assigned section), (3) Query filtering that automatically filters results by role (students only see own data, teachers only see their sections), (4) Audit logging for all attendance changes (who changed what, when, from which IP), (5) Rate limiting per role (students: 100 req/min, teachers: 500 req/min, admin: unlimited), (6) API versioning for backward compatibility. Implementation approach: Use decorators on endpoints like @require_role('teacher') @require_resource_access('section_id'), Middleware layer that checks token, adds user context to request, adds query filters automatically, Audit service that logs to separate collection. Files to modify: attendance_backend/main.py (add security middleware), attendance_backend/api/attendance.py (add permission decorators), attendance_backend/api/admin.py (restrict to admin role), attendance_backend/api/teacher.py (add teacher role checks). New files: attendance_backend/middleware/permission_middleware.py (permission checking), attendance_backend/middleware/audit_middleware.py (logging changes), attendance_backend/services/audit_service.py (write to audit log), attendance_backend/decorators/auth_decorators.py (role/resource check decorators), attendance_backend/utils/rate_limiter.py (per-role limits). Firestore collection: audit_logs (user_id, action, resource, timestamp, ip_address)."

---

## PROMPT 6: Integrated System Architecture & Implementation Roadmap

"Create a comprehensive integration plan for all components of the redesigned attendance system. The system must work together seamlessly: Login redirects to role-specific dashboard → Dashboard shows only accessible data → Teacher marks attendance during timetable period → Dashboard updates in real-time for all viewing that section → Audit logs record the change. Design: (1) Complete user flow for each role (Admin: login → manage users/timetable → view analytics; Teacher: login → see assigned sections → mark attendance during periods → view section dashboard; Student: login → view personal attendance → see analytics), (2) Data flow diagrams showing how each component communicates, (3) API call sequences for common operations, (4) Error handling strategies, (5) Fallback behavior if real-time updates fail, (6) Testing strategy for permission isolation. Implementation roadmap: Phase 1 (Week 1): Setup auth system, roles, permissions. Phase 2 (Week 2): Add timetable validation, section isolation. Phase 3 (Week 3): Implement real-time updates. Phase 4 (Week 4): Add audit logging, security hardening. Provide a step-by-step implementation guide listing all files and their modifications in order. Files involved across all systems: attendance_backend/main.py (entry point, middleware setup), attendance_backend/config/constants.py (role definitions, permission matrix), attendance_backend/database/ (all repository classes need role filtering), attendance_backend/api/ (all endpoints need auth checks), attendance_backend/services/ (business logic for each component), attendance_backend/schemas/ (request/response validation), attendance_backend/middleware/ (auth, audit, rate limiting). Key Firestore collections: users (with role+section assignment), courses, sections, enrollments, course_assignments, timetable, attendance (with section context), audit_logs. Frontend remains unchanged - it will receive different data per role without modifications. Success criteria: Admin can manage system, Teachers mark attendance only during periods for assigned sections, Students see only own data, All changes are audited, Real-time updates work across dashboard."

---

## How to Use These Prompts

1. Copy each prompt individually
2. Paste into Claude with full context
3. Claude will provide detailed implementation for each
4. Follow the order: Auth → Timetable → Dashboard → Database → Security → Integration
5. After each prompt, Claude gives you code to implement
6. Implement in that order to avoid breaking changes
7. Test at each phase

## Benefits of This Approach
✅ No frontend changes needed (backend serves role-specific data)
✅ Backward compatible with existing data
✅ Addresses all current issues
✅ Production-ready security
✅ Scalable to other sections/institutions
✅ Clear role separation
