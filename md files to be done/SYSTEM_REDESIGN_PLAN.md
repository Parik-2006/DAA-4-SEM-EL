# Smart Attendance System - Redesign Plan

## What the system needs to become

The current app is split across Flutter, FastAPI, and a web dashboard, but the business rules are still too loose. The design goal is to make the system timetable-aware, identity-aware, and privacy-aware so every screen is showing the same truth from the same backend rules.

The main product shifts are:

1. A logged-in user should only see the periods and attendance data that belong to that user or that user’s allowed role scope.
2. Live camera should not query the entire face database if the session already knows the active identity or section.
3. History, dashboard, and analytics should all be derived from the same attendance timeline model.
4. Face recognition should improve through verified samples, not by blindly retraining on every prediction.

## Architecture Tiers

### 1. Presentation Tier

This is the UI layer in Flutter and the web dashboard. It should render role-specific views, but it must not decide access rules. It should only ask the backend for allowed data and show filtered selections for the current day and current active period.

### 2. Application Tier

This tier coordinates the flows. It decides which endpoints the UI calls, how a current user is resolved, how a selected period is validated, and how live camera sessions are started or stopped. It should also handle caching, polling fallback, and page-to-page state reuse.

### 3. Domain Tier

This is where the real rules live: timetable window logic, student/teacher/section scope, attendance visibility rules, face-candidate narrowing, and audit rules. If the backend says a student can only see self history, that rule belongs here.

### 4. Persistence Tier

Firestore and any local cache should store attendance by date, period, section, student, and actor. The query model must support day-wise, period-wise, and user-wise reads without scanning unrelated records.

### 5. Realtime Tier

WebSocket or SSE should only broadcast scoped updates. A student should only receive updates for their own attendance scope, and a teacher should only receive updates for the sections they manage.

### 6. Security Tier

Identity, role, section ownership, and resource-level authorization must be enforced server-side. The frontend can hide options, but the backend must reject illegal actions.

## How the new workflow should behave

### A. Timetable-aware live camera selection

When a user opens live camera, the app should already know the active user from auth. The backend should return the current day’s timetable, the currently open period, nearby future periods, and whether marking is allowed right now. The UI should only allow selecting a period that is valid for the current time window and the user’s role scope.

For example, if the user is a student, the camera flow should default to self-verification and should only allow the matching section and active or allowed period. If the user is a teacher, the camera flow should only show the periods for the assigned section(s) and should lock out unrelated classes.

### B. Dashboard mapped by day and period

The dashboard should not be a flat summary. It should render a day-wise calendar or period grid so the user can see attendance by day, then by period, then by subject. The same data model should feed summary cards, attendance trends, and the active-today view.

### C. Simple self-only history

The history page should be intentionally narrow. A student should only see their own marked attendance. A teacher should only see the sections or periods they are allowed to inspect. An admin can view full history, but even then the UI should stay filter-first, not raw-table-first.

### D. Privacy-aware analytics

Analytics should be role-scoped. Student analytics should be personal. Teacher analytics should be section-scoped. Admin analytics should be system-wide. The backend should never ship unrelated records to the client and expect the UI to hide them.

### E. Identity-aware face matching

If the logged-in user is Parikshith or any other student account, the live face pipeline should narrow the candidate set before matching. That can mean matching only against the logged-in user’s registered embeddings in self-attendance mode, or matching only against students enrolled in the current section in teacher mode. This improves speed, confidence, and false-positive control.

### F. Learning after verification

Do not train the model on raw predictions. Only learn from verified outcomes. The safe pattern is to store confirmed embeddings or quality-checked samples, then update the searchable face index in batches or through an offline retraining pipeline. That gives improvement without poisoning the model.

## Current files that matter

### Flutter app

- `attendance_app/lib/main.dart` - current root app entrypoint
- `attendance_app/lib/router/app_router.dart` - newer role-based router
- `attendance_app/lib/screens/home_screen.dart` - legacy home screen still used by root app
- `attendance_app/lib/screens/profile_screen.dart` - legacy profile screen still used by root app
- `attendance_app/lib/screens/login_screen.dart` - legacy login screen still used by root app
- `attendance_app/lib/screens/home/home_screen.dart` - newer routed home screen
- `attendance_app/lib/screens/profile/profile_screen.dart` - newer routed profile screen
- `attendance_app/lib/screens/auth/login_screen.dart` - newer routed login screen
- `attendance_app/lib/screens/attendance/attendance_screen.dart` - attendance actions UI
- `attendance_app/lib/screens/attendance/live_camera_screen.dart` - live camera flow
- `attendance_app/lib/screens/attendance/qr_scan_screen.dart` - QR fallback flow
- `attendance_app/lib/screens/history/history_screen.dart` - history page for routed flow
- `attendance_app/lib/screens/history/enhanced_history_screen.dart` - richer history variant
- `attendance_app/lib/screens/student/student_dashboard_screen.dart` - student dashboard
- `attendance_app/lib/screens/admin/admin_dashboard_screen.dart` - admin dashboard
- `attendance_app/lib/screens/shell/main_shell.dart` - shell for bottom-nav routes
- `attendance_app/lib/providers/auth_provider.dart` - auth state and role scope
- `attendance_app/lib/providers/attendance_provider.dart` - attendance state
- `attendance_app/lib/providers/dashboard_provider.dart` - dashboard state
- `attendance_app/lib/services/api_service.dart` - API integration layer
- `attendance_app/lib/services/api_client.dart` - shared HTTP client
- `attendance_app/lib/services/attendance_service.dart` - attendance domain service
- `attendance_app/lib/services/dashboard_service.dart` - dashboard data service
- `attendance_app/lib/models/attendance_model.dart` - attendance record model
- `attendance_app/lib/models/dashboard_model.dart` - dashboard model
- `attendance_app/lib/models/user_model.dart` - user identity model

### Web dashboard

- `web-dashboard/src/main.tsx` - web entrypoint
- `web-dashboard/src/App.tsx` - app wrapper
- `web-dashboard/src/AppRouter.tsx` - role-based routes and page wiring
- `web-dashboard/src/pages/AttendancePage.tsx` - teacher attendance workflow
- `web-dashboard/src/pages/HistoryPage.tsx` - role-aware history view
- `web-dashboard/src/pages/AttendanceAnalyticsPage.tsx` - analytics page
- `web-dashboard/src/pages/StudentDashboardPage.tsx` - student dashboard route target
- `web-dashboard/src/pages/RoleLandingPage.tsx` - role landing logic
- `web-dashboard/src/components/LiveCamera.tsx` - live camera UI
- `web-dashboard/src/components/AttendanceSheet.tsx` - teacher period/roster UI
- `web-dashboard/src/hooks/useAttendanceHooks.ts` - attendance data hooks
- `web-dashboard/src/hooks/useAttendanceAnalytics.ts` - analytics hooks
- `web-dashboard/src/services/api.ts` - dashboard API client and attendance calls
- `web-dashboard/src/utils/roles.ts` - role resolution helpers
- `web-dashboard/src/config/timetable.ts` - timetable source for dashboard and analytics

### Backend

- `attendance_backend/main.py` - backend bootstrap and router registration
- `attendance_backend/api/attendance.py` - attendance window and mark flow
- `attendance_backend/api/attendance_secured.py` - secured attendance endpoints
- `attendance_backend/api/auth.py` - login and identity flow
- `attendance_backend/api/student.py` - student-scoped reads
- `attendance_backend/api/student_secured.py` - secured student endpoints
- `attendance_backend/api/teacher.py` - teacher-scoped reads and actions
- `attendance_backend/api/teacher_secured.py` - secured teacher endpoints
- `attendance_backend/api/admin.py` - admin analytics and management
- `attendance_backend/api/admin_secured.py` - secured admin endpoints
- `attendance_backend/api/sections.py` - section metadata
- `attendance_backend/api/courses.py` - course metadata
- `attendance_backend/api/timetable.py` - timetable source of truth
- `attendance_backend/api/qr_attendance.py` - QR fallback attendance flow
- `attendance_backend/api/websocket.py` - realtime broadcast layer
- `attendance_backend/database/firebase_client.py` - Firestore client
- `attendance_backend/database/attendance_repository.py` - attendance persistence
- `attendance_backend/database/timetable_repository.py` - timetable persistence
- `attendance_backend/database/student_repository.py` - student lookup
- `attendance_backend/database/user_repository.py` - user lookup
- `attendance_backend/database/section_repository.py` - if added, section lookup should live here
- `attendance_backend/services/attendance_service.py` - attendance business rules
- `attendance_backend/services/auth_service.py` - auth and role context
- `attendance_backend/services/realtime_service.py` - realtime fan-out
- `attendance_backend/services/period_detection_service.py` - active period detection
- `attendance_backend/services/attendance_lock_service.py` - window locking
- `attendance_backend/services/audit_services.py` - audit logging
- `attendance_backend/config/constants.py` - role, timing, and threshold constants
- `attendance_backend/decorators/auth_decorators.py` - route guards
- `attendance_backend/middleware/auth_middleware.py` - auth middleware if present
- `attendance_backend/middleware/permission_middleware.py` - permission middleware if present
- `attendance_backend/schemas/` - request and response contracts
- `attendance_backend/models/` - face embedding and matching models

## Claude-ready implementation strategy

The implementation should proceed in this order:

1. Lock down identity and scope.
2. Make timetable the source of truth for all attendance actions.
3. Narrow face matching candidates by authenticated identity and section.
4. Make history and analytics views read only scoped records.
5. Add verified-sample learning instead of blind retraining.
6. Keep realtime as a notification layer, not as the source of truth.

## 10 Claude prompts

### Prompt 1

Audit the current Flutter, web dashboard, and FastAPI architecture in the listed files above. Produce a concrete system design that makes timetable, history, analytics, and live camera all derive from the same attendance model. Focus on tiering the solution into presentation, application, domain, persistence, realtime, and security layers, and explain which layer owns which rule.

### Prompt 2

Design the timetable-aware live camera flow. The app should know the logged-in user, fetch that user’s section scope, load the current day’s timetable, and only allow period choices that are valid for the current time window. Show how this should work in `attendance_app/lib/screens/attendance/live_camera_screen.dart`, `attendance_app/lib/screens/attendance/attendance_screen.dart`, `web-dashboard/src/components/LiveCamera.tsx`, `web-dashboard/src/pages/AttendancePage.tsx`, `attendance_backend/api/attendance.py`, and `attendance_backend/api/timetable.py`.

### Prompt 3

Design the dashboard so it maps attendance by day and by period instead of showing generic totals. Explain the data model needed for `attendance_app/lib/providers/dashboard_provider.dart`, `attendance_app/lib/services/dashboard_service.dart`, `web-dashboard/src/pages/AttendanceAnalyticsPage.tsx`, `web-dashboard/src/pages/RoleLandingPage.tsx`, `web-dashboard/src/hooks/useAttendanceAnalytics.ts`, and `attendance_backend/api/admin.py`.

### Prompt 4

Redesign the history experience to be self-only for students and scope-limited for teachers. The response should explain how `attendance_app/lib/screens/history/history_screen.dart`, `attendance_app/lib/screens/history/enhanced_history_screen.dart`, `web-dashboard/src/pages/HistoryPage.tsx`, `attendance_backend/api/student.py`, `attendance_backend/api/teacher.py`, and `attendance_backend/database/attendance_repository.py` must enforce privacy and pagination.

### Prompt 5

Design privacy-aware analytics. Student analytics should show only personal data, teacher analytics only assigned sections, and admin analytics system-wide data. Use `web-dashboard/src/pages/AttendanceAnalyticsPage.tsx`, `web-dashboard/src/hooks/useAttendanceAnalytics.ts`, `attendance_app/lib/screens/student/student_dashboard_screen.dart`, `attendance_app/lib/screens/admin/admin_dashboard_screen.dart`, `attendance_backend/api/admin.py`, and `attendance_backend/api/student.py` as the target files.

### Prompt 6

Redesign face recognition so the search space is narrowed by identity context. If the logged-in user is a student, the system should match only that user’s registered embeddings in self-verification mode; if the user is a teacher, the system should match only the enrolled students in the active section. Explain how this should be implemented in `attendance_backend/services/realtime_service.py`, `attendance_backend/models/`, `attendance_backend/api/attendance.py`, `attendance_app/lib/services/api_service.dart`, `web-dashboard/src/services/api.ts`, and the live camera UIs.

### Prompt 7

Design a safe learning loop where the system improves from verified detections only. Do not retrain from raw guesses. Instead, store confirmed embeddings or verified samples, apply quality checks, and update the searchable index in batches. Map this to `attendance_backend/models/`, `attendance_backend/database/attendance_repository.py`, `attendance_backend/services/attendance_service.py`, and any future training pipeline under `attendance_backend/scripts/` or `attendance_backend/weights/`.

### Prompt 8

Define the backend authorization contract. Explain how login should return role, section scope, and dashboard target; how JWT or session context should be validated; and how every attendance/history/analytics request should be rejected if it breaks scope. Use `attendance_backend/api/auth.py`, `attendance_backend/decorators/auth_decorators.py`, `attendance_backend/services/auth_service.py`, `attendance_backend/config/constants.py`, `web-dashboard/src/utils/roles.ts`, and `attendance_app/lib/providers/auth_provider.dart`.

### Prompt 9

Design the realtime update model. The backend should broadcast scoped events only, and the frontend should fall back to polling when realtime is unavailable. Explain the contract for `attendance_backend/api/websocket.py`, `attendance_backend/services/realtime_service.py`, `attendance_backend/api/attendance.py`, `web-dashboard/src/hooks/useAttendanceHooks.ts`, `web-dashboard/src/pages/HistoryPage.tsx`, and `web-dashboard/src/pages/AttendancePage.tsx`.

### Prompt 10

Produce an implementation roadmap with phases, acceptance criteria, and file-by-file change order. The roadmap should separate quick wins from structural changes, and it should state exactly which files are edited first in `attendance_backend/`, `attendance_app/lib/`, and `web-dashboard/src/`. Make the roadmap safe for incremental rollout so the current system keeps working while the new architecture is introduced.

## Suggested rollout order

1. Backend scope and auth rules.
2. Timetable-driven attendance selection.
3. Self-only history and scoped analytics.
4. Identity-aware face search.
5. Verified-sample learning loop.
6. Realtime fan-out and fallback polling.

## Acceptance criteria

- A student can only see their own attendance history and personal analytics.
- A teacher can only act on assigned sections and valid timetable periods.
- Live camera only offers periods that are valid for the current session and time.
- The face search candidate set is narrowed before recognition.
- Learning only happens from verified outcomes.
- Dashboard, history, and analytics all read from the same scope rules.

## Notes for Claude

Do not propose changes that rely on frontend-only hiding. Every privacy and scope rule must be enforced in the backend. If a route or page is kept for compatibility, mark it as legacy and explain whether it should be migrated or removed.

- Broadcast attendance changes to section subscribers.
- Add WebSocket and SSE subscription endpoints.
- Add client-side fallback polling using cached section snapshots.
- Files to update next:
	- `attendance_backend/services/realtime_service.py`
	- `attendance_backend/api/websocket.py`
	- `attendance_backend/api/teacher.py`
	- `attendance_backend/api/student.py`

#### Phase 4, Week 4: Audit Logging and Security Hardening

- Write immutable audit rows for all attendance mutations.
- Apply rate limiting and request-body sanitization.
- Validate admin-only access for section management.
- Add tests for denial paths and error handling.
- Files to update last:
	- `attendance_backend/services/audit_services.py`
	- `attendance_backend/middleware/audit_middleware.py`
	- `attendance_backend/utils/rate_limiter.py`
	- `attendance_backend/api/admin.py`
	- `attendance_backend/api/teacher.py`
	- `attendance_backend/api/student.py`

### File-by-File Modification Order

1. `attendance_backend/main.py` - register middleware and startup services.
2. `attendance_backend/config/constants.py` - role matrix, limits, and route settings.
3. `attendance_backend/services/auth_service.py` - JWT claims, role helpers, section scope.
4. `attendance_backend/decorators/auth_decorators.py` - role and resource guards.
5. `attendance_backend/middleware/auth_middleware.py` - decode tokens and attach user context.
6. `attendance_backend/middleware/permission_middleware.py` - inject query filters and enforce route roles.
7. `attendance_backend/middleware/audit_middleware.py` - log mutating requests.
8. `attendance_backend/utils/rate_limiter.py` - per-role request throttling.
9. `attendance_backend/database/firebase_client.py` - section-first query support.
10. `attendance_backend/database/attendance_repository.py` - role-aware attendance access.
11. `attendance_backend/database/timetable_repository.py` - period detection and window queries.
12. `attendance_backend/api/sections.py` - manage courses, sections, enrollments, and assignments.
13. `attendance_backend/api/teacher.py` - section-scoped attendance and dashboard access.
14. `attendance_backend/api/student.py` - own-record filtering and realtime token access.
15. `attendance_backend/api/admin.py` - admin-only management and analytics.
16. `attendance_backend/api/websocket.py` - realtime subscriptions and broadcast integration.
17. `attendance_backend/services/realtime_service.py` - websocket/SSE fan-out and cache invalidation.
18. `attendance_backend/services/audit_services.py` - write immutable audit records.
19. `attendance_backend/schemas/` - request and response validation for all role-specific flows.
20. `attendance_backend/tests/` and `attendance_backend/scripts/` - isolate permissions, realtime, and audit behavior.

### Firestore Collections

- `users` - roles, permissions, and section assignment.
- `courses` - course catalog.
- `sections` - section metadata and capacity.
- `enrollments` - student-to-section mapping.
- `course_assignments` - teacher-to-section mapping.
- `timetable` - section-scoped period schedule.
- `attendance` - attendance rows with `section_id` context.
- `audit_logs` - immutable security and attendance history.

### Success Criteria

- Admin can manage users, sections, and timetable.
- Teachers can mark attendance only for assigned sections and only during valid periods.
- Students can see only their own attendance and analytics.
- All attendance changes are audited.
- Realtime updates work for everyone viewing the same section.
- The frontend remains unchanged because filtering is enforced on the backend.
