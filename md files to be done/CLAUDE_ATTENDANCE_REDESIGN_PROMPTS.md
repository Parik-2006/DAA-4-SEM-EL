# Claude Prompts for Smart Attendance Redesign

Use these prompts one at a time. Each prompt is written to keep the system aligned with the current Flutter, FastAPI, and web-dashboard codebase while moving toward a timetable-aware, privacy-aware architecture.

## File map for reference

- `attendance_app/lib/main.dart`
- `attendance_app/lib/router/app_router.dart`
- `attendance_app/lib/screens/home_screen.dart`
- `attendance_app/lib/screens/profile_screen.dart`
- `attendance_app/lib/screens/login_screen.dart`
- `attendance_app/lib/screens/home/home_screen.dart`
- `attendance_app/lib/screens/profile/profile_screen.dart`
- `attendance_app/lib/screens/auth/login_screen.dart`
- `attendance_app/lib/screens/attendance/attendance_screen.dart`
- `attendance_app/lib/screens/attendance/live_camera_screen.dart`
- `attendance_app/lib/screens/attendance/qr_scan_screen.dart`
- `attendance_app/lib/screens/history/history_screen.dart`
- `attendance_app/lib/screens/history/enhanced_history_screen.dart`
- `attendance_app/lib/screens/student/student_dashboard_screen.dart`
- `attendance_app/lib/screens/admin/admin_dashboard_screen.dart`
- `attendance_app/lib/screens/shell/main_shell.dart`
- `attendance_app/lib/providers/auth_provider.dart`
- `attendance_app/lib/providers/attendance_provider.dart`
- `attendance_app/lib/providers/dashboard_provider.dart`
- `attendance_app/lib/services/api_service.dart`
- `attendance_app/lib/services/api_client.dart`
- `attendance_app/lib/services/attendance_service.dart`
- `attendance_app/lib/services/dashboard_service.dart`
- `attendance_app/lib/models/attendance_model.dart`
- `attendance_app/lib/models/dashboard_model.dart`
- `attendance_app/lib/models/user_model.dart`

- `web-dashboard/src/main.tsx`
- `web-dashboard/src/App.tsx`
- `web-dashboard/src/AppRouter.tsx`
- `web-dashboard/src/pages/AttendancePage.tsx`
- `web-dashboard/src/pages/HistoryPage.tsx`
- `web-dashboard/src/pages/AttendanceAnalyticsPage.tsx`
- `web-dashboard/src/pages/StudentDashboardPage.tsx`
- `web-dashboard/src/pages/RoleLandingPage.tsx`
- `web-dashboard/src/components/LiveCamera.tsx`
- `web-dashboard/src/components/AttendanceSheet.tsx`
- `web-dashboard/src/hooks/useAttendanceHooks.ts`
- `web-dashboard/src/hooks/useAttendanceAnalytics.ts`
- `web-dashboard/src/services/api.ts`
- `web-dashboard/src/utils/roles.ts`
- `web-dashboard/src/config/timetable.ts`

- `attendance_backend/main.py`
- `attendance_backend/api/auth.py`
- `attendance_backend/api/attendance.py`
- `attendance_backend/api/attendance_secured.py`
- `attendance_backend/api/student.py`
- `attendance_backend/api/student_secured.py`
- `attendance_backend/api/teacher.py`
- `attendance_backend/api/teacher_secured.py`
- `attendance_backend/api/admin.py`
- `attendance_backend/api/admin_secured.py`
- `attendance_backend/api/sections.py`
- `attendance_backend/api/courses.py`
- `attendance_backend/api/timetable.py`
- `attendance_backend/api/websocket.py`
- `attendance_backend/database/firebase_client.py`
- `attendance_backend/database/attendance_repository.py`
- `attendance_backend/database/timetable_repository.py`
- `attendance_backend/database/student_repository.py`
- `attendance_backend/database/user_repository.py`
- `attendance_backend/services/auth_service.py`
- `attendance_backend/services/attendance_service.py`
- `attendance_backend/services/realtime_service.py`
- `attendance_backend/services/period_detection_service.py`
- `attendance_backend/services/attendance_lock_service.py`
- `attendance_backend/services/audit_services.py`
- `attendance_backend/decorators/auth_decorators.py`
- `attendance_backend/config/constants.py`
- `attendance_backend/schemas/`
- `attendance_backend/models/`

## Prompt 1

Audit the current Flutter, web dashboard, and FastAPI architecture in the listed files above. Produce a concrete system design that makes timetable, history, analytics, and live camera all derive from the same attendance model. Focus on tiering the solution into presentation, application, domain, persistence, realtime, and security layers, and explain which layer owns which rule.

## Prompt 2

Design the timetable-aware live camera flow. The app should know the logged-in user, fetch that user’s section scope, load the current day’s timetable, and only allow period choices that are valid for the current time window. Show how this should work in `attendance_app/lib/screens/attendance/live_camera_screen.dart`, `attendance_app/lib/screens/attendance/attendance_screen.dart`, `web-dashboard/src/components/LiveCamera.tsx`, `web-dashboard/src/pages/AttendancePage.tsx`, `attendance_backend/api/attendance.py`, and `attendance_backend/api/timetable.py`.

## Prompt 3

Design the dashboard so it maps attendance by day and by period instead of showing generic totals. Explain the data model needed for `attendance_app/lib/providers/dashboard_provider.dart`, `attendance_app/lib/services/dashboard_service.dart`, `web-dashboard/src/pages/AttendanceAnalyticsPage.tsx`, `web-dashboard/src/pages/RoleLandingPage.tsx`, `web-dashboard/src/hooks/useAttendanceAnalytics.ts`, and `attendance_backend/api/admin.py`.

## Prompt 4

Redesign the history experience to be self-only for students and scope-limited for teachers. The response should explain how `attendance_app/lib/screens/history/history_screen.dart`, `attendance_app/lib/screens/history/enhanced_history_screen.dart`, `web-dashboard/src/pages/HistoryPage.tsx`, `attendance_backend/api/student.py`, `attendance_backend/api/teacher.py`, and `attendance_backend/database/attendance_repository.py` must enforce privacy and pagination.

## Prompt 5

Design privacy-aware analytics. Student analytics should show only personal data, teacher analytics only assigned sections, and admin analytics system-wide data. Use `web-dashboard/src/pages/AttendanceAnalyticsPage.tsx`, `web-dashboard/src/hooks/useAttendanceAnalytics.ts`, `attendance_app/lib/screens/student/student_dashboard_screen.dart`, `attendance_app/lib/screens/admin/admin_dashboard_screen.dart`, `attendance_backend/api/admin.py`, and `attendance_backend/api/student.py` as the target files.

## Prompt 6

Redesign face recognition so the search space is narrowed by identity context. If the logged-in user is a student, the system should match only that user’s registered embeddings in self-verification mode; if the user is a teacher, the system should match only the enrolled students in the active section. Explain how this should be implemented in `attendance_backend/services/realtime_service.py`, `attendance_backend/models/`, `attendance_backend/api/attendance.py`, `attendance_app/lib/services/api_service.dart`, `web-dashboard/src/services/api.ts`, and the live camera UIs.

## Prompt 7

Design a safe learning loop where the system improves from verified detections only. Do not retrain from raw guesses. Instead, store confirmed embeddings or verified samples, apply quality checks, and update the searchable index in batches. Map this to `attendance_backend/models/`, `attendance_backend/database/attendance_repository.py`, `attendance_backend/services/attendance_service.py`, and any future training pipeline under `attendance_backend/scripts/` or `attendance_backend/weights/`.

## Prompt 8

Define the backend authorization contract. Explain how login should return role, section scope, and dashboard target; how JWT or session context should be validated; and how every attendance/history/analytics request should be rejected if it breaks scope. Use `attendance_backend/api/auth.py`, `attendance_backend/decorators/auth_decorators.py`, `attendance_backend/services/auth_service.py`, `attendance_backend/config/constants.py`, `web-dashboard/src/utils/roles.ts`, and `attendance_app/lib/providers/auth_provider.dart`.

## Prompt 9

Design the realtime update model. The backend should broadcast scoped events only, and the frontend should fall back to polling when realtime is unavailable. Explain the contract for `attendance_backend/api/websocket.py`, `attendance_backend/services/realtime_service.py`, `attendance_backend/api/attendance.py`, `web-dashboard/src/hooks/useAttendanceHooks.ts`, `web-dashboard/src/pages/HistoryPage.tsx`, and `web-dashboard/src/pages/AttendancePage.tsx`.

## Prompt 10

Produce an implementation roadmap with phases, acceptance criteria, and file-by-file change order. The roadmap should separate quick wins from structural changes, and it should state exactly which files are edited first in `attendance_backend/`, `attendance_app/lib/`, and `web-dashboard/src/`. Make the roadmap safe for incremental rollout so the current system keeps working while the new architecture is introduced.
