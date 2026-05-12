/**
 * pages/index.ts  (updated)
 * -------------------------
 * Replace:  web-dashboard/src/pages/index.ts
 *
 * Added:  AttendanceAnalyticsPage export
 */

export { LoginPage }               from './LoginPage';
export { DashboardPage }           from './DashboardPage';
export { ProfilePage }             from './ProfilePage';
export { AttendancePage }          from './AttendancePage';
export { HistoryPage }             from './HistoryPage';

// ── NEW ──────────────────────────────────────────────────────────────────────
export { default as AttendanceAnalyticsPage } from './AttendanceAnalyticsPage.tsx';

// ── Admin pages ───────────────────────────────────────────────────────────────
export { default as FaceRegistrationPage }  from './FaceRegistrationPage';
export { default as QRCodePage }            from './QRCodePage';
export { default as BatchImportPage }       from './BatchImportPage';
export { default as StudentManagementPage } from './StudentManagementPage';
export { default as CourseManagementPage }  from './CourseManagementPage';

// ── Role-specific dashboards ──────────────────────────────────────────────────
export { StudentDashboard } from './StudentDashboard';
export { TeacherDashboard } from './TeacherDashboard';