// ── Student components ─────────────────────────────────────────────────────────
export { TimetableView }     from './TimetableView';
export { AttendanceHistory } from './AttendanceHistory';
export { StatsCard }         from './StatsCard';

// ── Teacher components ────────────────────────────────────────────────────────
export { AttendanceSheet }   from './AttendanceSheet';
export type { TeacherPeriod, AttendanceEntry, AttendanceStatus } from './AttendanceSheet';

// ── Admin components ──────────────────────────────────────────────────────────
export {
  AdminDashboard,
  CIEManagement,
  FileUploadForm,
  ReportsPage,
} from './AdminComponents';
export type { AdminKPIs, CIERecord, UploadMode, ReportData } from './AdminComponents';

// ── Shared components ─────────────────────────────────────────────────────────
export { Layout } from './Layout';
export { LiveCamera } from './LiveCamera';
export { UploadPhoto } from './UploadPhoto';
export { AttendanceRecordCard } from './Cards';
export { Table } from './Cards';

// ── UI Components ─────────────────────────────────────────────────────────────
export * from './UI';

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
