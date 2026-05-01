// ── Student components ─────────────────────────────────────────────────────────
export { StudentDashboard }  from './student/StudentDashboard';
export { TimetableView }     from './student/TimetableView';
export { AttendanceHistory } from './student/AttendanceHistory';
export { StatsCard }         from './student/StatsCard';

// ── Teacher components ────────────────────────────────────────────────────────
export { TeacherDashboard }  from './teacher/TeacherDashboard';
export { AttendanceSheet }   from './teacher/AttendanceSheet';
export type { TeacherPeriod, AttendanceEntry, AttendanceStatus } from './teacher/AttendanceSheet';

// ── Admin components ──────────────────────────────────────────────────────────
export {
  AdminDashboard,
  CIEManagement,
  FileUploadForm,
  ReportsPage,
} from './admin/AdminComponents';
export type { AdminKPIs, CIERecord, UploadMode, ReportData } from './admin/AdminComponents';

// ── Hooks ─────────────────────────────────────────────────────────────────────
export {
  useTimetable,
  usePeriodDetection,
  useStudentAttendance,
} from '../hooks/useAttendanceHooks';
export type {
  PeriodCard,
  TimetableData,
  TimetableDay,
  ActivePeriod,
  AttendanceRecord,
  PaginatedHistory,
  AttendanceSummary,
  CourseAttendanceStat,
  DashboardData,
} from '../hooks/useAttendanceHooks';
