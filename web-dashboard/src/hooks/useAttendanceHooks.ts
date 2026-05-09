/**
 * useAttendanceHooks.ts
 *
 * Unified attendance hooks — merges the student-facing hooks, manual-marking
 * system, enterprise period-summary / roster / class-periods hooks,
 * period-aware analytics (period-analytics + weekly-audit), and
 * admin/teacher role-aware history + filter-dropdown helpers.
 *
 * EXPORTS
 * ───────────────────────────────────────────────────────────────────────────
 * useTimetable                 — weekly timetable with 5-min in-memory cache
 * useCSE4CTimetableLocal       — local/seeded timetable with remote fallback
 * usePeriodDetection           — poll current-period endpoint (30s default)
 * useStudentAttendance         — paginated history + summary + dashboard + warnings
 * useAttendanceByPeriod        — per-period slots for a given day (seeded data)
 * useManualAttendance          — teacher manual marking with optimistic UI + undo
 * usePeriodAttendanceSummary   — live 5s polling of scanned/missing per period
 * useClassRoster               — full class roster from API
 * useClassPeriods              — periods for a class on a given date
 * usePeriodAnalytics           — granular per-period analytics with optional polling
 * useWeeklyAudit               — 5-day audit window: all periods × all enrolled students
 * useAdminHistory              — role-aware paginated history for admin/teacher views
 * useClassesAndPeriods         — class list + lazy period loader for filter dropdowns
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { getAuthToken } from '../services/firebase/auth.service';
import {
  attendanceAPI,
  ManualAttendancePayload,
  BulkManualAttendancePayload,
  BulkManualAttendanceResponse,
  ManualAttendanceResponse,
  AdminHistoryFilters,
  PaginatedAdminHistory,
  ClassInfo,
  PeriodInfo,
} from '../services/api';

// ─────────────────────────────────────────────────────────────────────────────
// Re-export enterprise API types so consumers only need one import
// ─────────────────────────────────────────────────────────────────────────────

export type {
  PeriodSummary,
  PeriodStudentRecord,
  ClassRosterStudent,
  ClassPeriod,
  AdminHistoryFilters,
  PaginatedAdminHistory,
  ClassInfo,
  PeriodInfo,
} from '../services/api';

import type { PeriodSummary, PeriodStudentRecord, ClassRosterStudent, ClassPeriod } from '../services/api';

// ─────────────────────────────────────────────────────────────────────────────
// Seeded Timetable (UG CSE 4C, section C)
// ─────────────────────────────────────────────────────────────────────────────

export const CSE4C_META = {
  class_id: 'ug-cse-4c-sec-c',
  display: 'UG CSE 4C',
  semester: 4,
  term: 'Even',
  batch: '2023-24',
  room: 'CSE-CC203',
};

export interface SeedPeriod {
  period_id: string;
  day: string;
  start_time: string; // HH:MM
  end_time: string;   // HH:MM
  course_code: string;
  course_name: string;
  course_color: string;
  is_lab_class?: boolean;
  room?: string;
  faculty_name?: string;
}

export const SEEDED_TIMETABLE: SeedPeriod[] = [
  // Monday
  { period_id: 'm-1', day: 'Monday',    start_time: '09:00', end_time: '10:00', course_code: 'IOT',      course_name: 'Internet of Things',               course_color: '#6366F1', room: 'CSE-CC203' },
  { period_id: 'm-2', day: 'Monday',    start_time: '10:00', end_time: '11:00', course_code: 'DAA',      course_name: 'Design and Analysis of Algorithms', course_color: '#EF4444', room: 'CSE-CC203' },
  { period_id: 'm-3', day: 'Monday',    start_time: '11:30', end_time: '12:30', course_code: 'DMS',      course_name: 'Data Management Systems',           course_color: '#F59E0B', room: 'CSE-CC203' },
  { period_id: 'm-4', day: 'Monday',    start_time: '12:30', end_time: '13:30', course_code: 'CN',       course_name: 'Computer Networks',                 course_color: '#22C55E', room: 'CSE-CC203' },
  { period_id: 'm-5', day: 'Monday',    start_time: '14:30', end_time: '16:30', course_code: 'BASK',     course_name: 'Basket Course',                     course_color: '#8B5CF6', room: 'CSE-CC203' },
  // Tuesday
  { period_id: 't-1', day: 'Tuesday',   start_time: '09:00', end_time: '10:00', course_code: 'DAA',      course_name: 'Design and Analysis of Algorithms', course_color: '#EF4444', room: 'CSE-CC203' },
  { period_id: 't-2', day: 'Tuesday',   start_time: '10:00', end_time: '11:00', course_code: 'BASK',     course_name: 'Basket Course',                     course_color: '#8B5CF6', room: 'CSE-CC203' },
  { period_id: 't-3', day: 'Tuesday',   start_time: '11:30', end_time: '12:30', course_code: 'CN',       course_name: 'Computer Networks',                 course_color: '#22C55E', room: 'CSE-CC203' },
  { period_id: 't-4', day: 'Tuesday',   start_time: '12:30', end_time: '13:30', course_code: 'IOT',      course_name: 'Internet of Things',                course_color: '#6366F1', room: 'CSE-CC203' },
  { period_id: 't-5', day: 'Tuesday',   start_time: '14:30', end_time: '16:30', course_code: 'AEC',      course_name: 'AEC Course',                        course_color: '#06B6D4', room: 'CSE-CC203' },
  // Wednesday
  { period_id: 'w-1', day: 'Wednesday', start_time: '09:00', end_time: '10:00', course_code: 'DMS',      course_name: 'Data Management Systems',           course_color: '#F59E0B', room: 'CSE-CC203' },
  { period_id: 'w-2', day: 'Wednesday', start_time: '10:00', end_time: '11:00', course_code: 'CN',       course_name: 'Computer Networks',                 course_color: '#22C55E', room: 'CSE-CC203' },
  { period_id: 'w-3', day: 'Wednesday', start_time: '11:30', end_time: '12:30', course_code: 'IOT',      course_name: 'Internet of Things',                course_color: '#6366F1', room: 'CSE-CC203' },
  { period_id: 'w-4', day: 'Wednesday', start_time: '12:30', end_time: '13:30', course_code: 'EL',       course_name: 'Engineering Lab',                   course_color: '#F97316', room: 'CSE-CC203' },
  { period_id: 'w-5', day: 'Wednesday', start_time: '14:30', end_time: '16:30', course_code: 'BRIDGE',   course_name: 'Bridge Course Maths',               course_color: '#10B981', room: 'CSE-CC203' },
  // Thursday
  { period_id: 'th-1', day: 'Thursday', start_time: '09:00', end_time: '11:00', course_code: 'IOT-LAB',  course_name: 'IOT Lab',                           course_color: '#6366F1', is_lab_class: true, room: 'CSE-LAB1' },
  { period_id: 'th-2', day: 'Thursday', start_time: '11:30', end_time: '12:30', course_code: 'UHV',      course_name: 'UHV',                               course_color: '#FB7185', room: 'CSE-CC203' },
  { period_id: 'th-3', day: 'Thursday', start_time: '12:30', end_time: '13:30', course_code: 'DMS*',     course_name: 'Data Management Systems',           course_color: '#F59E0B', room: 'CSE-CC203' },
  // Friday
  { period_id: 'f-1', day: 'Friday',    start_time: '09:00', end_time: '11:00', course_code: 'DAA-LAB',  course_name: 'DAA Lab',                           course_color: '#EF4444', is_lab_class: true, room: 'CSE-LAB2' },
  { period_id: 'f-2', day: 'Friday',    start_time: '11:30', end_time: '12:30', course_code: 'UHV',      course_name: 'UHV',                               course_color: '#FB7185', room: 'CSE-CC203' },
  { period_id: 'f-3', day: 'Friday',    start_time: '12:30', end_time: '13:30', course_code: 'DMS',      course_name: 'Data Management Systems',           course_color: '#F59E0B', room: 'CSE-CC203' },
  { period_id: 'f-4', day: 'Friday',    start_time: '14:30', end_time: '15:30', course_code: 'DAA',      course_name: 'Design and Analysis of Algorithms', course_color: '#EF4444', room: 'CSE-CC203' },
  { period_id: 'f-5', day: 'Friday',    start_time: '15:30', end_time: '16:30', course_code: 'COUNS',    course_name: 'Counselling',                       course_color: '#64748B', room: 'CSE-CC203' },
  // Saturday (empty)
];

function buildCoursesFromSeed(): Record<string, { name: string; color: string }> {
  const all: Record<string, { name: string; color: string }> = {};
  SEEDED_TIMETABLE.forEach((p) => {
    all[p.course_code] = { name: p.course_name, color: p.course_color };
  });
  return all;
}

function buildSeededDays(): TimetableDay {
  const days: TimetableDay = {};
  SEEDED_TIMETABLE.forEach((p) => {
    if (!days[p.day]) days[p.day] = [];
    days[p.day].push({
      period_id:   p.period_id,
      start_time:  p.start_time,
      end_time:    p.end_time,
      course_code: p.course_code,
      course_name: p.course_name,
      faculty_id:  '',
      faculty_name: p.faculty_name ?? '',
      is_lab_class: Boolean(p.is_lab_class),
      room:         p.room,
      course_color: p.course_color,
    });
  });
  const sortByTime = (a: PeriodCard, b: PeriodCard) => {
    const [ah, am] = a.start_time.split(':').map(Number);
    const [bh, bm] = b.start_time.split(':').map(Number);
    return ah * 60 + am - (bh * 60 + bm);
  };
  Object.keys(days).forEach((d) => days[d].sort(sortByTime));
  return days;
}

// ─────────────────────────────────────────────────────────────────────────────
// Auth token resolution
// Session-based auth only.
// ─────────────────────────────────────────────────────────────────────────────

const _sessionKey = 'auth_token';

async function getSessionAuthToken(): Promise<string | null> {
  try {
    return await getAuthToken();
  } catch {
    return sessionStorage.getItem(_sessionKey);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const TIMETABLE_TTL_MS = 5 * 60 * 1000;

// ─────────────────────────────────────────────────────────────────────────────
// Shared fetch helper  (GET only — mutations go through attendanceAPI)
// ─────────────────────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  params?: Record<string, string | number | undefined>
): Promise<T> {
  const token = await getSessionAuthToken();
  const response = await axios.get<T>(`${BASE}${path}`, {
    params,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    timeout: 15000,
  });
  return response.data;
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared types
// ─────────────────────────────────────────────────────────────────────────────

export interface PeriodCard {
  period_id: string;
  start_time: string;
  end_time: string;
  duration_minutes?: number;
  course_code: string;
  course_name: string;
  /** Present when used in a manual-marking context. */
  course_id?: string;
  faculty_id: string;
  faculty_name: string;
  is_lab_class: boolean;
  room?: string;
  course_color: string;
  // dashboard-only
  status?: 'present' | 'absent' | 'late' | 'pending';
  status_color?: string;
  is_active?: boolean;
  countdown_seconds?: number;
}

export interface TimetableDay {
  [dayName: string]: PeriodCard[];
}

export interface TimetableData {
  class_id?: string;
  days: TimetableDay;
  all_courses: Record<string, { name: string; color: string }>;
}

export interface ActivePeriod {
  is_active: boolean;
  period?: PeriodCard;
  checked_at: string;
  message: string;
}

export interface AttendanceRecord {
  date: string;
  time?: string;
  timestamp?: string;
  course_code?: string;
  course_name?: string;
  status: 'present' | 'absent' | 'late' | 'pending';
  status_color: string;
  confidence?: number;
  camera_id?: string;
  marked_by?: string;
  marked_by_name?: string;
  track_id?: number;
  metadata?: Record<string, unknown>;
}

export interface PaginatedHistory {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  records: AttendanceRecord[];
}

export interface AttendanceSummary {
  overall: {
    percentage: number;
    present: number;
    late: number;
    absent: number;
    total: number;
    band: 'safe' | 'warning' | 'danger';
    color: string;
  };
  course_breakdown: CourseAttendanceStat[];
  has_critical: boolean;
  critical_courses: CourseAttendanceStat[];
}

export interface CourseAttendanceStat {
  course_code: string;
  course_name: string;
  color: string;
  percentage: number;
  present: number;
  late: number;
  absent: number;
  total: number;
  band: 'safe' | 'warning' | 'danger';
  band_color: string;
  required_consecutive_to_reach_75: number;
  is_critical: boolean;
}

export interface DashboardData {
  today_date: string;
  day_name: string;
  active_period?: PeriodCard;
  periods_today: PeriodCard[];
  summary: {
    total: number;
    present: number;
    absent: number;
    late: number;
    pending: number;
  };
  overall_attendance: {
    percentage: number;
    present: number;
    late: number;
    absent: number;
    total: number;
    band: string;
    color: string;
  };
}

// ─── Teacher manual-marking types ─────────────────────────────────────────────

export type ManualStatus = 'present' | 'late' | 'absent' | 'excused' | 'not_marked';

export interface RosterEntry {
  student_id: string;
  roll_no: string;
  name: string;
  photo_url?: string;
  status: ManualStatus;
  /** True while an individual quick-save is in flight for this student. */
  saving?: boolean;
  /** ISO timestamp of last confirmed server write. */
  last_saved_at?: string;
  record_id?: string;
  notes?: string;
}

export interface UseManualAttendanceOptions {
  classId: string;
  periodId: string;
  courseId: string;
  /** Authenticated faculty user ID — stored in every audit record. */
  markedBy: string;
  initialRoster?: Array<{
    student_id: string;
    roll_no: string;
    name: string;
    photo_url?: string;
  }>;
  /**
   * When true (default), existing period records are fetched on mount and
   * merged into the local roster so the teacher sees the current state.
   */
  preloadExisting?: boolean;
}

export interface UseManualAttendanceResult {
  roster: RosterEntry[];
  setStatus: (studentId: string, status: ManualStatus) => void;
  setNotes: (studentId: string, notes: string) => void;
  /** Immediately persist one student — used by quick-mark buttons. */
  saveOne: (studentId: string) => Promise<void>;
  /** Bulk-save the entire roster in one request. */
  saveAll: () => Promise<BulkManualAttendanceResponse | null>;
  markAllPresent: () => void;
  markAllAbsent: () => void;
  /** Single-level undo for bulk mark-all. */
  undo: () => void;
  canUndo: boolean;
  /** True while saveAll is in flight. */
  saving: boolean;
  lastSaveResult: BulkManualAttendanceResponse | null;
  saveErrors: Record<string, string>;
  /** True when any non-not_marked entry has no confirmed last_saved_at. */
  isDirty: boolean;
  lastSavedAt: string | null;
  loading: boolean;
  loadError: string | null;
}

// ─── Period-aware analytics types ─────────────────────────────────────────────

/**
 * A single student's audit entry for one period.
 * status = 'not_marked' when no scan record exists for that period window.
 */
export interface PeriodAuditEntry {
  student_id: string;
  student_name: string;
  roll_no?: string;
  avatar_url?: string;
  status: 'present' | 'absent' | 'late' | 'not_marked';
  /** ISO timestamp of the scan event, if any */
  scanned_at?: string;
  marked_by_name?: string;
  confidence?: number;
  camera_id?: string;
}

/**
 * Full analytics snapshot for one period on one date.
 * The backend endpoint is /api/v1/attendance/period-analytics.
 */
export interface PeriodAnalytics {
  period_id: string;
  course_code: string;
  course_name: string;
  faculty_name?: string;
  date: string;           // YYYY-MM-DD
  start_time: string;     // HH:MM
  end_time: string;
  total_enrolled: number;
  present: number;
  late: number;
  absent: number;
  not_marked: number;
  /** (present + late) / total_enrolled × 100 */
  attendance_pct: number;
  audit_entries: PeriodAuditEntry[];
}

/** Per-day rollup used in the 5-day audit window. */
export interface WeeklyAuditDay {
  date: string;       // YYYY-MM-DD
  day_name: string;
  is_today: boolean;
  periods: PeriodAnalytics[];
  day_total: {
    present: number;
    absent: number;
    late: number;
    not_marked: number;
    total: number;
  };
}

/** Full 5-day audit window returned by /api/v1/attendance/weekly-audit. */
export interface WeeklyAuditWindow {
  class_id: string;
  start_date: string;
  end_date: string;
  days: WeeklyAuditDay[];
}

/** Per-period attendance slot used by DashboardPage. */
export interface PeriodAttendanceSlot {
  period: SeedPeriod;
  present: number;
  late: number;
  absent: number;
  pending: number;
  total_students: number;
  records: AttendanceRecord[];
  is_active: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Timetable cache
// ─────────────────────────────────────────────────────────────────────────────

const timetableCache = new Map<string, { data: TimetableData; fetchedAt: number }>();

// ─────────────────────────────────────────────────────────────────────────────
// useTimetable  (student-facing, with in-memory cache)
// ─────────────────────────────────────────────────────────────────────────────

interface UseTimetableOptions { studentId: string; enabled?: boolean }
interface UseTimetableResult {
  data: TimetableData | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useTimetable({ studentId, enabled = true }: UseTimetableOptions): UseTimetableResult {
  const [data, setData] = useState<TimetableData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTimetable = useCallback(async () => {
    if (!studentId || !enabled) return;
    const cached = timetableCache.get(studentId);
    if (cached && Date.now() - cached.fetchedAt < TIMETABLE_TTL_MS) {
      setData(cached.data);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<TimetableData>('/api/v1/student/timetable', {
        student_id: studentId,
      });
      timetableCache.set(studentId, { data: result, fetchedAt: Date.now() });
      setData(result);
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? err.message)
          : 'Failed to load timetable'
      );
    } finally {
      setLoading(false);
    }
  }, [studentId, enabled]);

  useEffect(() => { fetchTimetable(); }, [fetchTimetable]);
  return { data, loading, error, refetch: fetchTimetable };
}

// ─────────────────────────────────────────────────────────────────────────────
// useCSE4CTimetableLocal  (local/seeded timetable with remote fallback)
// ─────────────────────────────────────────────────────────────────────────────

export function useCSE4CTimetableLocal(classId: string = CSE4C_META.class_id) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState<TimetableDay>({});
  const [all_courses, setAllCourses] = useState<Record<string, { name: string; color: string }>>(
    buildCoursesFromSeed()
  );
  const [source, setSource] = useState<'remote' | 'seeded'>('seeded');

  const fetchLocal = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const remote = await attendanceAPI.getClassTimetable(classId);
      if (remote) {
        const mapped: TimetableDay = {};
        Object.entries(remote.days).forEach(([day, arr]) => {
          mapped[day] = arr.map((p) => ({
            period_id:    p.period_id,
            start_time:   p.start_time,
            end_time:     p.end_time,
            course_code:  p.course_code,
            course_name:  p.course_name,
            faculty_id:   '',
            faculty_name: p.faculty_name ?? '',
            is_lab_class: Boolean(p.is_lab_class ?? false),
            room:         p.room,
            course_color: p.course_color ?? '#6366F1',
          }));
        });
        setDays(mapped);
        setAllCourses(remote.courses ?? buildCoursesFromSeed());
        setSource('remote');
      } else {
        setDays(buildSeededDays());
        setAllCourses(buildCoursesFromSeed());
        setSource('seeded');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load timetable');
      setDays(buildSeededDays());
      setAllCourses(buildCoursesFromSeed());
      setSource('seeded');
    } finally {
      setLoading(false);
    }
  }, [classId]);

  useEffect(() => { fetchLocal(); }, [fetchLocal]);
  return { loading, error, days, all_courses, source, refetch: fetchLocal };
}

// ─────────────────────────────────────────────────────────────────────────────
// useAttendanceByPeriod  — per-period slots for a given day (DashboardPage)
// ─────────────────────────────────────────────────────────────────────────────

export function useAttendanceByPeriod({
  day,
  date,
  classId = CSE4C_META.class_id,
  enabled = true,
}: {
  day: string;
  date?: string;
  classId?: string;
  enabled?: boolean;
}) {
  const [slots, setSlots] = useState<PeriodAttendanceSlot[]>([]);
  const [loading, setLoading] = useState(false);

  const isActive = (p: SeedPeriod): boolean => {
    const now = new Date();
    const [sh, sm] = p.start_time.split(':').map(Number);
    const [eh, em] = p.end_time.split(':').map(Number);
    const start = new Date(); start.setHours(sh, sm, 0, 0);
    const end   = new Date(); end.setHours(eh, em, 0, 0);
    return now >= start && now < end;
  };

  const fetch = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const now = new Date();
      const todayKey = date ?? now.toISOString().slice(0, 10);
      const periods = SEEDED_TIMETABLE.filter((p) => p.day === day).sort((a, b) => {
        const [ah, am] = a.start_time.split(':').map(Number);
        const [bh, bm] = b.start_time.split(':').map(Number);
        return ah * 60 + am - (bh * 60 + bm);
      });

      const results: PeriodAttendanceSlot[] = [];
      for (const p of periods) {
        let summary = null as any;
        try {
          summary = await attendanceAPI.getPeriodSummary(p.period_id, classId, todayKey);
        } catch {
          summary = null;
        }

        if (summary) {
          results.push({
            period: p,
            present: summary.present_count,
            late:    summary.late_count,
            absent:  summary.absent_count,
            pending: summary.not_scanned_count,
            total_students: summary.total_enrolled,
            records: summary.students.map((s: any) => ({
              date:         summary.date,
              time:         s.scan_timestamp ?? s.marked_at,
              status:       s.status as any,
              course_code:  summary.course_code,
              course_name:  summary.course_name,
              timestamp:    s.scan_timestamp ?? s.marked_at,
              student_id:   s.student_id,
              student_name: s.student_name,
              status_color: '',
            })),
            is_active: isActive(p),
          });
        } else {
          results.push({
            period: p,
            present: 0, late: 0, absent: 0,
            pending: 70, total_students: 70,
            records: [],
            is_active: isActive(p),
          });
        }
      }
      setSlots(results);
    } finally {
      setLoading(false);
    }
  }, [day, date, classId, enabled]);

  useEffect(() => { fetch(); }, [fetch]);
  return { slots, loading, refetch: fetch };
}

// ─────────────────────────────────────────────────────────────────────────────
// usePeriodDetection
// ─────────────────────────────────────────────────────────────────────────────

interface UsePeriodDetectionOptions {
  classId: string;
  pollIntervalMs?: number;
  enabled?: boolean;
}
interface UsePeriodDetectionResult {
  activePeriod: ActivePeriod | null;
  loading: boolean;
  error: string | null;
  lastChecked: Date | null;
}

export function usePeriodDetection({
  classId,
  pollIntervalMs = 30_000,
  enabled = true,
}: UsePeriodDetectionOptions): UsePeriodDetectionResult {
  const [activePeriod, setActivePeriod] = useState<ActivePeriod | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const checkPeriod = useCallback(async () => {
    if (!classId || !enabled) return;
    try {
      const result = await apiFetch<ActivePeriod>('/api/v1/timetable/current-period', {
        class_id: classId,
      });
      setActivePeriod(result);
      setLastChecked(new Date());
      setError(null);
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? err.message)
          : 'Period detection failed'
      );
    } finally {
      setLoading(false);
    }
  }, [classId, enabled]);

  useEffect(() => {
    if (!enabled) return;
    setLoading(true);
    checkPeriod();
    intervalRef.current = setInterval(checkPeriod, pollIntervalMs);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [checkPeriod, enabled, pollIntervalMs]);

  return { activePeriod, loading, error, lastChecked };
}

// ─────────────────────────────────────────────────────────────────────────────
// useStudentAttendance
// ─────────────────────────────────────────────────────────────────────────────

interface UseStudentAttendanceOptions {
  studentId: string;
  page?: number;
  pageSize?: number;
  courseId?: string;
  startDate?: string;
  endDate?: string;
  enabled?: boolean;
}

interface UseStudentAttendanceResult {
  history: PaginatedHistory | null;
  summary: AttendanceSummary | null;
  dashboard: DashboardData | null;
  warnings: {
    has_critical_warning: boolean;
    messages: string[];
    courses: CourseAttendanceStat[];
  } | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useStudentAttendance({
  studentId,
  page = 1,
  pageSize = 20,
  courseId,
  startDate,
  endDate,
  enabled = true,
}: UseStudentAttendanceOptions): UseStudentAttendanceResult {
  const [history, setHistory]   = useState<PaginatedHistory | null>(null);
  const [summary, setSummary]   = useState<AttendanceSummary | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [warnings, setWarnings] = useState<UseStudentAttendanceResult['warnings']>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    if (!studentId || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      const [hist, summ, dash, warn] = await Promise.allSettled([
        apiFetch<PaginatedHistory>('/api/v1/student/attendance-history', {
          student_id: studentId,
          page,
          page_size: pageSize,
          ...(courseId   ? { course_id:   courseId   } : {}),
          ...(startDate  ? { start_date:  startDate  } : {}),
          ...(endDate    ? { end_date:    endDate    } : {}),
        }),
        apiFetch<AttendanceSummary>('/api/v1/student/attendance-summary', { student_id: studentId }),
        apiFetch<DashboardData>('/api/v1/student/dashboard',              { student_id: studentId }),
        apiFetch<UseStudentAttendanceResult['warnings']>('/api/v1/student/warnings', { student_id: studentId }),
      ]);
      if (hist.status === 'fulfilled') setHistory(hist.value);
      if (summ.status === 'fulfilled') setSummary(summ.value);
      if (dash.status === 'fulfilled') setDashboard(dash.value);
      if (warn.status === 'fulfilled') setWarnings(warn.value);
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? err.message)
          : 'Failed to load attendance data'
      );
    } finally {
      setLoading(false);
    }
  }, [studentId, enabled, page, pageSize, courseId, startDate, endDate]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  return { history, summary, dashboard, warnings, loading, error, refetch: fetchAll };
}

// ─────────────────────────────────────────────────────────────────────────────
// useManualAttendance
// ─────────────────────────────────────────────────────────────────────────────

export function useManualAttendance({
  classId,
  periodId,
  courseId,
  markedBy,
  initialRoster = [],
  preloadExisting = true,
}: UseManualAttendanceOptions): UseManualAttendanceResult {

  const buildRoster = useCallback(
    (src: Array<{ student_id: string; roll_no: string; name: string; photo_url?: string }>): RosterEntry[] =>
      src.map((s) => ({ ...s, status: 'not_marked' as ManualStatus })),
    []
  );

  const [roster, setRoster]             = useState<RosterEntry[]>(() => buildRoster(initialRoster));
  const [undoSnapshot, setUndoSnapshot] = useState<RosterEntry[] | null>(null);
  const [saving, setSaving]             = useState(false);
  const [lastSaveResult, setLastSaveResult] = useState<BulkManualAttendanceResponse | null>(null);
  const [saveErrors, setSaveErrors]     = useState<Record<string, string>>({});
  const [lastSavedAt, setLastSavedAt]   = useState<string | null>(null);
  const [loading, setLoading]           = useState(false);
  const [loadError, setLoadError]       = useState<string | null>(null);

  // Rebuild when initialRoster identity changes (e.g. teacher selects new class)
  useEffect(() => {
    setRoster(buildRoster(initialRoster));
    setUndoSnapshot(null);
    setSaveErrors({});
    setLastSaveResult(null);
    setLastSavedAt(null);
  }, [initialRoster, buildRoster]);

  // Pre-fill roster with any records already saved for this period
  useEffect(() => {
    if (!preloadExisting || !periodId || !classId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const existing = await attendanceAPI.getPeriodAttendance(periodId, classId);
        if (cancelled || existing.length === 0) return;
        setRoster((prev) =>
          prev.map((entry) => {
            const found = existing.find(
              (r) => (r as unknown as Record<string, unknown>).student_id === entry.student_id
            );
            if (!found) return entry;
            const rawStatus = String(found.status ?? '');
            const validStatuses = new Set(['present', 'late', 'absent', 'excused']);
            const mappedStatus: ManualStatus = validStatuses.has(rawStatus)
              ? (rawStatus as Exclude<ManualStatus, 'not_marked'>)
              : 'not_marked';
            return {
              ...entry,
              status: mappedStatus,
              last_saved_at: found.marked_at,
              record_id: found.id,
            };
          })
        );
      } catch {
        if (!cancelled) setLoadError('Could not load existing attendance for this period.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [periodId, classId, preloadExisting]);

  const setStatus = useCallback((studentId: string, status: ManualStatus) => {
    setRoster((prev) => prev.map((e) => (e.student_id === studentId ? { ...e, status } : e)));
    setSaveErrors((prev) => { const n = { ...prev }; delete n[studentId]; return n; });
  }, []);

  const setNotes = useCallback((studentId: string, notes: string) => {
    setRoster((prev) => prev.map((e) => (e.student_id === studentId ? { ...e, notes } : e)));
  }, []);

  const markAllPresent = useCallback(() => {
    setUndoSnapshot((s) => s ?? roster.map((r) => ({ ...r })));
    setRoster((prev) => prev.map((e) => ({ ...e, status: 'present' as ManualStatus })));
  }, [roster]);

  const markAllAbsent = useCallback(() => {
    setUndoSnapshot((s) => s ?? roster.map((r) => ({ ...r })));
    setRoster((prev) => prev.map((e) => ({ ...e, status: 'absent' as ManualStatus })));
  }, [roster]);

  const undo = useCallback(() => {
    if (!undoSnapshot) return;
    setRoster(undoSnapshot);
    setUndoSnapshot(null);
  }, [undoSnapshot]);

  const saveOne = useCallback(async (studentId: string) => {
    const entry = roster.find((e) => e.student_id === studentId);
    if (!entry || entry.status === 'not_marked') return;

    setRoster((prev) =>
      prev.map((e) => (e.student_id === studentId ? { ...e, saving: true } : e))
    );
    setSaveErrors((prev) => { const n = { ...prev }; delete n[studentId]; return n; });

    const payload: ManualAttendancePayload = {
      student_id:       studentId,
      status:           entry.status as ManualAttendancePayload['status'],
      class_id:         classId,
      period_id:        periodId,
      course_id:        courseId,
      marked_by:        markedBy,
      notes:            entry.notes,
      client_timestamp: new Date().toISOString(),
      audit_source:     'manual_teacher',
      metadata:         { roll_no: entry.roll_no },
    };

    try {
      const result: ManualAttendanceResponse = await attendanceAPI.markAttendanceManual(payload);
      setRoster((prev) =>
        prev.map((e) =>
          e.student_id === studentId
            ? { ...e, saving: false, last_saved_at: result.server_timestamp, record_id: result.record_id }
            : e
        )
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Save failed';
      setSaveErrors((prev) => ({ ...prev, [studentId]: msg }));
      setRoster((prev) =>
        prev.map((e) => (e.student_id === studentId ? { ...e, saving: false } : e))
      );
      throw err;
    }
  }, [roster, classId, periodId, courseId, markedBy]);

  const saveAll = useCallback(async (): Promise<BulkManualAttendanceResponse | null> => {
    const toSave = roster.filter((e) => e.status !== 'not_marked');
    if (toSave.length === 0) return null;

    setSaving(true);
    setSaveErrors({});

    const payload: BulkManualAttendancePayload = {
      class_id:         classId,
      period_id:        periodId,
      course_id:        courseId,
      marked_by:        markedBy,
      client_timestamp: new Date().toISOString(),
      audit_source:     'manual_teacher',
      entries:          roster.map((e) => ({ student_id: e.student_id, status: e.status, notes: e.notes })),
      metadata:         { total_roster: roster.length, marked_count: toSave.length },
    };

    try {
      const result = await attendanceAPI.markAttendanceBulk(payload);
      const savedAt = result.server_timestamp || new Date().toISOString();
      setLastSaveResult(result);
      setLastSavedAt(savedAt);

      const failedIds = new Set(result.errors.map((e) => e.student_id));
      setRoster((prev) =>
        prev.map((e) =>
          e.status !== 'not_marked' && !failedIds.has(e.student_id)
            ? { ...e, last_saved_at: savedAt }
            : e
        )
      );

      if (result.errors.length > 0) {
        const errs: Record<string, string> = {};
        result.errors.forEach(({ student_id, reason }) => { errs[student_id] = reason; });
        setSaveErrors(errs);
      }

      return result;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Bulk save failed';
      if (roster.length > 0) setSaveErrors({ [roster[0].student_id]: msg });
      throw err;
    } finally {
      setSaving(false);
    }
  }, [roster, classId, periodId, courseId, markedBy]);

  const isDirty = roster.some((e) => e.status !== 'not_marked' && !e.last_saved_at);

  return {
    roster, setStatus, setNotes,
    saveOne, saveAll,
    markAllPresent, markAllAbsent,
    undo, canUndo: undoSnapshot !== null,
    saving, lastSaveResult, saveErrors,
    isDirty, lastSavedAt,
    loading, loadError,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// usePeriodAttendanceSummary  (live polling of scanned/missing per period)
// ─────────────────────────────────────────────────────────────────────────────

interface UsePeriodAttendanceSummaryOptions {
  periodId: string;
  classId: string;
  date?: string;
  pollIntervalMs?: number;
  enabled?: boolean;
}

interface PeriodAttendanceSummaryResult {
  summary: PeriodSummary | null;
  scannedStudents: PeriodStudentRecord[];
  missingStudents: PeriodStudentRecord[];
  recentScans: PeriodStudentRecord[];
  loading: boolean;
  error: string | null;
  markStudent: (studentId: string, status: 'present' | 'late' | 'absent') => Promise<void>;
  refetch: () => void;
  secondsSinceSync: number;
}

export function usePeriodAttendanceSummary({
  periodId,
  classId,
  date,
  pollIntervalMs = 5000,
  enabled = true,
}: UsePeriodAttendanceSummaryOptions): PeriodAttendanceSummaryResult {

  const [summary, setSummary]         = useState<PeriodSummary | null>(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [lastSyncAt, setLastSyncAt]   = useState<number | null>(null);
  const [secondsSinceSync, setSecondsSinceSync] = useState(0);
  const [pendingOverrides, setPendingOverrides] = useState<
    Record<string, PeriodStudentRecord['status']>
  >({});

  const pollerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchSummary = useCallback(async () => {
    if (!periodId || !classId || !enabled) return;
    try {
      const result = await attendanceAPI.getPeriodSummary(periodId, classId, date);
      if (result) {
        setSummary(result);
        setError(null);
        setLastSyncAt(Date.now());
        setSecondsSinceSync(0);
        setPendingOverrides((prev) => {
          const next = { ...prev };
          result.students.forEach((s) => {
            if (s.status !== 'not_scanned') delete next[s.student_id];
          });
          return next;
        });
      }
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? err.message)
          : 'Failed to load attendance'
      );
    } finally {
      setLoading(false);
    }
  }, [periodId, classId, date, enabled]);

  useEffect(() => {
    if (!enabled) return;
    setLoading(true);
    fetchSummary();
    pollerRef.current = setInterval(fetchSummary, pollIntervalMs);
    return () => { if (pollerRef.current) clearInterval(pollerRef.current); };
  }, [fetchSummary, enabled, pollIntervalMs]);

  useEffect(() => {
    tickerRef.current = setInterval(() => {
      if (lastSyncAt !== null)
        setSecondsSinceSync(Math.floor((Date.now() - lastSyncAt) / 1000));
    }, 1000);
    return () => { if (tickerRef.current) clearInterval(tickerRef.current); };
  }, [lastSyncAt]);

  const mergedStudents = (summary?.students ?? []).map((student) => {
    const override = pendingOverrides[student.student_id];
    if (!override) return student;
    return { ...student, status: override, marked_by: 'manual', marked_at: new Date().toISOString() };
  });

  const scannedStudents = mergedStudents.filter((s) => s.status !== 'not_scanned');
  const missingStudents = mergedStudents.filter((s) => s.status === 'not_scanned');
  const recentScans = [...scannedStudents].sort((a, b) => {
    const ta = a.scan_timestamp ?? a.marked_at ?? '';
    const tb = b.scan_timestamp ?? b.marked_at ?? '';
    return tb.localeCompare(ta);
  });

  const markStudent = useCallback(async (studentId: string, status: 'present' | 'late' | 'absent') => {
    setPendingOverrides((prev) => ({ ...prev, [studentId]: status }));
    try {
      await attendanceAPI.markPeriodStudentAttendance(periodId, classId, studentId, status, date);
      await fetchSummary();
    } catch (err) {
      setPendingOverrides((prev) => { const next = { ...prev }; delete next[studentId]; return next; });
      throw err;
    }
  }, [periodId, classId, date, fetchSummary]);

  return { summary, scannedStudents, missingStudents, recentScans, loading, error, markStudent, refetch: fetchSummary, secondsSinceSync };
}

// ─────────────────────────────────────────────────────────────────────────────
// useClassRoster
// ─────────────────────────────────────────────────────────────────────────────

interface UseClassRosterResult {
  roster: ClassRosterStudent[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useClassRoster(classId: string, enabled = true): UseClassRosterResult {
  const [roster, setRoster] = useState<ClassRosterStudent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState<string | null>(null);

  const fetchRoster = useCallback(async () => {
    if (!classId || !enabled) return;
    setLoading(true);
    try {
      const data = await attendanceAPI.getClassRoster(classId);
      setRoster(data);
      setError(null);
    } catch {
      setError('Failed to load class roster');
    } finally {
      setLoading(false);
    }
  }, [classId, enabled]);

  useEffect(() => { fetchRoster(); }, [fetchRoster]);
  return { roster, loading, error, refetch: fetchRoster };
}

// ─────────────────────────────────────────────────────────────────────────────
// useClassPeriods
// ─────────────────────────────────────────────────────────────────────────────

interface UseClassPeriodsResult {
  periods: ClassPeriod[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useClassPeriods(classId: string, date: string, enabled = true): UseClassPeriodsResult {
  const [periods, setPeriods] = useState<ClassPeriod[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const fetchPeriods = useCallback(async () => {
    if (!classId || !date || !enabled) return;
    setLoading(true);
    try {
      const data = await attendanceAPI.getClassPeriods(classId, date);
      setPeriods(data);
      setError(null);
    } catch {
      setError('Failed to load class periods');
    } finally {
      setLoading(false);
    }
  }, [classId, date, enabled]);

  useEffect(() => { fetchPeriods(); }, [fetchPeriods]);
  return { periods, loading, error, refetch: fetchPeriods };
}

// ─────────────────────────────────────────────────────────────────────────────
// usePeriodAnalytics
// ─────────────────────────────────────────────────────────────────────────────

interface UsePeriodAnalyticsOptions {
  periodId: string;
  classId: string;
  date: string;      // YYYY-MM-DD
  enabled?: boolean;
  /** Poll interval in ms. Omit for one-shot fetch. */
  pollMs?: number;
}

/**
 * Fetches granular per-period analytics from /api/v1/attendance/period-analytics.
 * Returns present / absent / late / not_marked counts and a per-student audit trail.
 */
export function usePeriodAnalytics({
  periodId,
  classId,
  date,
  enabled = true,
  pollMs,
}: UsePeriodAnalyticsOptions) {
  const [data, setData]       = useState<PeriodAnalytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const timerRef              = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    if (!periodId || !classId || !date || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<PeriodAnalytics>(
        '/api/v1/attendance/period-analytics',
        { period_id: periodId, class_id: classId, date }
      );
      setData(result);
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? err.message)
          : 'Failed to load period analytics'
      );
    } finally {
      setLoading(false);
    }
  }, [periodId, classId, date, enabled]);

  useEffect(() => {
    load();
    if (pollMs) {
      timerRef.current = setInterval(load, pollMs);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [load, pollMs]);

  return { data, loading, error, refetch: load };
}

// ─────────────────────────────────────────────────────────────────────────────
// useWeeklyAudit
// ─────────────────────────────────────────────────────────────────────────────

interface UseWeeklyAuditOptions {
  classId: string;
  startDate: string;   // YYYY-MM-DD  (Monday of the target week)
  endDate: string;     // YYYY-MM-DD  (Friday of the target week)
  enabled?: boolean;
}

/**
 * Fetches the 5-day audit window for a class from /api/v1/attendance/weekly-audit.
 * Each day contains full PeriodAnalytics for every scheduled period, including
 * per-student audit entries so you can see exactly who was scanned when.
 */
export function useWeeklyAudit({
  classId,
  startDate,
  endDate,
  enabled = true,
}: UseWeeklyAuditOptions) {
  const [data, setData]       = useState<WeeklyAuditWindow | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!classId || !startDate || !endDate || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<WeeklyAuditWindow>(
        '/api/v1/attendance/weekly-audit',
        { class_id: classId, start_date: startDate, end_date: endDate }
      );
      setData(result);
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? err.message)
          : 'Failed to load weekly audit data'
      );
    } finally {
      setLoading(false);
    }
  }, [classId, startDate, endDate, enabled]);

  useEffect(() => { load(); }, [load]);
  return { data, loading, error, refetch: load };
}

// ─────────────────────────────────────────────────────────────────────────────
// useAdminHistory  (role-aware paginated history for admin/teacher views)
// ─────────────────────────────────────────────────────────────────────────────

interface UseAdminHistoryOptions extends AdminHistoryFilters {
  enabled?: boolean;
  /** Poll interval in ms. 0 = no polling. Default 0. */
  pollIntervalMs?: number;
}

interface UseAdminHistoryResult {
  data: PaginatedAdminHistory | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Role-aware hook that fetches the admin/teacher history table.
 * Re-fetches automatically whenever any filter option changes.
 * Pass pollIntervalMs > 0 for live-updating views.
 */
export function useAdminHistory({
  enabled = true,
  pollIntervalMs = 0,
  ...filters
}: UseAdminHistoryOptions): UseAdminHistoryResult {
  const [data, setData]       = useState<PaginatedAdminHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Stable serialised key so useCallback re-runs only when filters truly change
  const filterKey = JSON.stringify(filters);

  const fetch = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const result = await attendanceAPI.getAdminHistory(filters);
      setData(result);
    } catch (err) {
      setError(
        axios.isAxiosError(err)
          ? (err.response?.data?.detail ?? err.message)
          : 'Failed to load history'
      );
    } finally {
      setLoading(false);
    }
  // filterKey covers the spread filters; disabling exhaustive-deps is intentional
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey, enabled]);

  useEffect(() => {
    fetch();
    if (pollIntervalMs > 0) {
      intervalRef.current = setInterval(fetch, pollIntervalMs);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetch, pollIntervalMs]);

  return { data, loading, error, refetch: fetch };
}

// ─────────────────────────────────────────────────────────────────────────────
// useClassesAndPeriods  (class list + lazy period loader for filter dropdowns)
// ─────────────────────────────────────────────────────────────────────────────

interface UseClassesAndPeriodsResult {
  classes: ClassInfo[];
  periods: PeriodInfo[];
  classesLoading: boolean;
  periodsLoading: boolean;
  /** Call with a classId (and optional date) to populate `periods`. */
  loadPeriods: (classId: string, date?: string) => void;
}

/**
 * Loads the full class list once on mount.
 * Periods are loaded lazily — call loadPeriods(classId, date?) when the user
 * selects a class so the period dropdown stays in sync.
 */
export function useClassesAndPeriods(): UseClassesAndPeriodsResult {
  const [classes, setClasses]         = useState<ClassInfo[]>([]);
  const [periods, setPeriods]         = useState<PeriodInfo[]>([]);
  const [classesLoading, setClassesL] = useState(false);
  const [periodsLoading, setPeriodsL] = useState(false);

  // Fetch class list once on mount
  useEffect(() => {
    (async () => {
      setClassesL(true);
      try {
        const result = await attendanceAPI.getClasses();
        setClasses(result);
      } catch (err) {
        console.error('[useClassesAndPeriods] Failed to load classes:', err);
      } finally {
        setClassesL(false);
      }
    })();
  }, []);

  const loadPeriods = useCallback(async (classId: string, date?: string) => {
    if (!classId) { setPeriods([]); return; }
    setPeriodsL(true);
    try {
      const result = await attendanceAPI.getPeriodsByClass(classId, date);
      setPeriods(result);
    } catch (err) {
      console.error('[useClassesAndPeriods] Failed to load periods:', err);
      setPeriods([]);
    } finally {
      setPeriodsL(false);
    }
  }, []);

  return { classes, periods, classesLoading, periodsLoading, loadPeriods };
}