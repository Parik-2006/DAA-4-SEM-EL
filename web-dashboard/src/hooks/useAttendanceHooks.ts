/**
 * useAttendanceHooks.ts
 *
 * Unified attendance hooks — merges the manual-marking system with the
 * enterprise period-summary / roster / class-periods hooks.
 *
 * EXPORTS
 * ───────────────────────────────────────────────────────────────────────────
 * useTimetable              — weekly timetable with 5-min in-memory cache
 * usePeriodDetection        — poll current-period endpoint (30s default)
 * useStudentAttendance      — paginated history + summary + dashboard + warnings
 * useManualAttendance       — teacher manual marking with optimistic UI + undo
 * usePeriodAttendanceSummary— live 5s polling of scanned/missing per period
 * useClassRoster            — full class roster from API
 * useClassPeriods           — periods for a class on a given date
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import {
  attendanceAPI,
  ManualAttendancePayload,
  BulkManualAttendancePayload,
  BulkManualAttendanceResponse,
  ManualAttendanceResponse,
} from '../services/api';

// ─────────────────────────────────────────────────────────────────────────────
// Auth token resolution
// Supports both localStorage (legacy) and sessionStorage (enterprise).
// SESSION_TOKEN_KEY is imported lazily so the file compiles even when the
// auth service hasn't added that export yet.
// ─────────────────────────────────────────────────────────────────────────────

let _sessionKey = 'auth_token';
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const mod = require('../services/firebase/auth.service');
  if (mod?.SESSION_TOKEN_KEY) _sessionKey = mod.SESSION_TOKEN_KEY;
} catch { /* use fallback */ }

function getAuthToken(): string | null {
  return (
    sessionStorage.getItem(_sessionKey) ||
    localStorage.getItem('auth_token') ||
    null
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Re-export enterprise API types so consumers only need one import
// ─────────────────────────────────────────────────────────────────────────────

export type {
  PeriodSummary,
  PeriodStudentRecord,
  ClassRosterStudent,
  ClassPeriod,
} from '../services/api';

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const TIMETABLE_TTL_MS = 5 * 60 * 1000;

// ─────────────────────────────────────────────────────────────────────────────
// Shared fetch helper  (GET only — mutations go through attendanceAPI)
// ─────────────────────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  params?: Record<string, string | number | undefined>
): Promise<T> {
  const token = getAuthToken();
  const response = await axios.get<T>(`${BASE}${path}`, {
    params,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    timeout: 15000,
  });
  return response.data;
}

// ─────────────────────────────────────────────────────────────────────────────
// Student-facing shared types
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

// ─────────────────────────────────────────────────────────────────────────────
// Teacher manual-marking types
// ─────────────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────────
// useTimetable
// ─────────────────────────────────────────────────────────────────────────────

const timetableCache = new Map<string, { data: TimetableData; fetchedAt: number }>();

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
  const [history, setHistory] = useState<PaginatedHistory | null>(null);
  const [summary, setSummary] = useState<AttendanceSummary | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [warnings, setWarnings] = useState<UseStudentAttendanceResult['warnings']>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
          ...(courseId ? { course_id: courseId } : {}),
          ...(startDate ? { start_date: startDate } : {}),
          ...(endDate ? { end_date: endDate } : {}),
        }),
        apiFetch<AttendanceSummary>('/api/v1/student/attendance-summary', {
          student_id: studentId,
        }),
        apiFetch<DashboardData>('/api/v1/student/dashboard', {
          student_id: studentId,
        }),
        apiFetch<UseStudentAttendanceResult['warnings']>('/api/v1/student/warnings', {
          student_id: studentId,
        }),
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
    (
      src: Array<{
        student_id: string;
        roll_no: string;
        name: string;
        photo_url?: string;
      }>
    ): RosterEntry[] => src.map((s) => ({ ...s, status: 'not_marked' as ManualStatus })),
    []
  );

  const [roster, setRoster] = useState<RosterEntry[]>(() => buildRoster(initialRoster));
  const [undoSnapshot, setUndoSnapshot] = useState<RosterEntry[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [lastSaveResult, setLastSaveResult] = useState<BulkManualAttendanceResponse | null>(null);
  const [saveErrors, setSaveErrors] = useState<Record<string, string>>({});
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Rebuild when initialRoster identity changes (e.g. teacher selects new class)
  useEffect(() => {
    setRoster(buildRoster(initialRoster));
    setUndoSnapshot(null);
    setSaveErrors({});
    setLastSaveResult(null);
    setLastSavedAt(null);
  }, [initialRoster, buildRoster]);

  // Pre-fill roster with any records already saved for this period (face-scan
  // or a previous manual session).
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
              (r) =>
                (r as unknown as Record<string, unknown>).student_id === entry.student_id
            );
            if (!found) return entry;
            const mappedStatus: ManualStatus = (
              ['present', 'late', 'absent', 'excused'] as const
            ).includes(found.status as ManualStatus)
              ? (found.status as ManualStatus)
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

  // ── Local mutations ────────────────────────────────────────────────────────

  const setStatus = useCallback((studentId: string, status: ManualStatus) => {
    setRoster((prev) =>
      prev.map((e) => (e.student_id === studentId ? { ...e, status } : e))
    );
    setSaveErrors((prev) => {
      const n = { ...prev };
      delete n[studentId];
      return n;
    });
  }, []);

  const setNotes = useCallback((studentId: string, notes: string) => {
    setRoster((prev) =>
      prev.map((e) => (e.student_id === studentId ? { ...e, notes } : e))
    );
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

  // ── Network: save one ──────────────────────────────────────────────────────

  const saveOne = useCallback(
    async (studentId: string) => {
      const entry = roster.find((e) => e.student_id === studentId);
      if (!entry || entry.status === 'not_marked') return;

      // Optimistic spinner
      setRoster((prev) =>
        prev.map((e) => (e.student_id === studentId ? { ...e, saving: true } : e))
      );
      setSaveErrors((prev) => {
        const n = { ...prev };
        delete n[studentId];
        return n;
      });

      const payload: ManualAttendancePayload = {
        student_id: studentId,
        status: entry.status as ManualAttendancePayload['status'],
        class_id: classId,
        period_id: periodId,
        course_id: courseId,
        marked_by: markedBy,
        notes: entry.notes,
        client_timestamp: new Date().toISOString(),
        audit_source: 'manual_teacher',
        metadata: { roll_no: entry.roll_no },
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
    },
    [roster, classId, periodId, courseId, markedBy]
  );

  // ── Network: save all ──────────────────────────────────────────────────────

  const saveAll = useCallback(async (): Promise<BulkManualAttendanceResponse | null> => {
    const toSave = roster.filter((e) => e.status !== 'not_marked');
    if (toSave.length === 0) return null;

    setSaving(true);
    setSaveErrors({});

    const payload: BulkManualAttendancePayload = {
      class_id: classId,
      period_id: periodId,
      course_id: courseId,
      marked_by: markedBy,
      client_timestamp: new Date().toISOString(),
      audit_source: 'manual_teacher',
      entries: roster.map((e) => ({
        student_id: e.student_id,
        status: e.status,
        notes: e.notes,
      })),
      metadata: { total_roster: roster.length, marked_count: toSave.length },
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
        result.errors.forEach(({ student_id, reason }) => {
          errs[student_id] = reason;
        });
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
    roster,
    setStatus,
    setNotes,
    saveOne,
    saveAll,
    markAllPresent,
    markAllAbsent,
    undo,
    canUndo: undoSnapshot !== null,
    saving,
    lastSaveResult,
    saveErrors,
    isDirty,
    lastSavedAt,
    loading,
    loadError,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// usePeriodAttendanceSummary  (enterprise — live polling of scanned/missing)
// ─────────────────────────────────────────────────────────────────────────────

// These types come from api.ts; the import at top re-exports them for consumers.
import type { PeriodSummary, PeriodStudentRecord } from '../services/api';

interface UsePeriodAttendanceSummaryOptions {
  periodId: string;
  classId: string;
  date?: string;
  pollIntervalMs?: number;
  enabled?: boolean;
}

interface PeriodAttendanceSummaryResult {
  summary: PeriodSummary | null;
  /** Students who have been scanned or manually marked. */
  scannedStudents: PeriodStudentRecord[];
  /** Students who have not yet been marked. */
  missingStudents: PeriodStudentRecord[];
  /** scannedStudents sorted newest-first by scan/marked timestamp. */
  recentScans: PeriodStudentRecord[];
  loading: boolean;
  error: string | null;
  /**
   * Optimistically marks one student, then immediately re-fetches from the
   * server to confirm. Rolls back the optimistic state on failure.
   */
  markStudent: (
    studentId: string,
    status: 'present' | 'late' | 'absent'
  ) => Promise<void>;
  refetch: () => void;
  /** Seconds elapsed since the last successful poll. */
  secondsSinceSync: number;
}

export function usePeriodAttendanceSummary({
  periodId,
  classId,
  date,
  pollIntervalMs = 5000,
  enabled = true,
}: UsePeriodAttendanceSummaryOptions): PeriodAttendanceSummaryResult {

  const [summary, setSummary] = useState<PeriodSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSyncAt, setLastSyncAt] = useState<number | null>(null);
  const [secondsSinceSync, setSecondsSinceSync] = useState(0);
  const [pendingOverrides, setPendingOverrides] = useState<
    Record<string, PeriodStudentRecord['status']>
  >({});

  const pollerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch ────────────────────────────────────────────────────────────────

  const fetchSummary = useCallback(async () => {
    if (!periodId || !classId || !enabled) return;
    try {
      const result = await attendanceAPI.getPeriodSummary(periodId, classId, date);
      if (result) {
        setSummary(result);
        setError(null);
        setLastSyncAt(Date.now());
        setSecondsSinceSync(0);
        // Drop overrides the server has now confirmed
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

  // Polling
  useEffect(() => {
    if (!enabled) return;
    setLoading(true);
    fetchSummary();
    pollerRef.current = setInterval(fetchSummary, pollIntervalMs);
    return () => { if (pollerRef.current) clearInterval(pollerRef.current); };
  }, [fetchSummary, enabled, pollIntervalMs]);

  // Sync-age ticker — counts up every second so the UI can display "Synced Xs ago"
  useEffect(() => {
    tickerRef.current = setInterval(() => {
      if (lastSyncAt !== null) {
        setSecondsSinceSync(Math.floor((Date.now() - lastSyncAt) / 1000));
      }
    }, 1000);
    return () => { if (tickerRef.current) clearInterval(tickerRef.current); };
  }, [lastSyncAt]);

  // ── Merge optimistic overrides into server data ────────────────────────

  const mergedStudents = (summary?.students ?? []).map((student) => {
    const override = pendingOverrides[student.student_id];
    if (!override) return student;
    return {
      ...student,
      status: override,
      marked_by: 'manual',
      marked_at: new Date().toISOString(),
    };
  });

  const scannedStudents = mergedStudents.filter((s) => s.status !== 'not_scanned');
  const missingStudents = mergedStudents.filter((s) => s.status === 'not_scanned');
  const recentScans = [...scannedStudents].sort((a, b) => {
    const ta = a.scan_timestamp ?? a.marked_at ?? '';
    const tb = b.scan_timestamp ?? b.marked_at ?? '';
    return tb.localeCompare(ta);
  });

  // ── markStudent (optimistic) ───────────────────────────────────────────

  const markStudent = useCallback(
    async (studentId: string, status: 'present' | 'late' | 'absent') => {
      // Apply optimistic override immediately
      setPendingOverrides((prev) => ({ ...prev, [studentId]: status }));
      try {
        await attendanceAPI.markPeriodStudentAttendance(
          periodId,
          classId,
          studentId,
          status,
          date
        );
        await fetchSummary();
      } catch (err) {
        // Roll back on failure
        setPendingOverrides((prev) => {
          const next = { ...prev };
          delete next[studentId];
          return next;
        });
        throw err;
      }
    },
    [periodId, classId, date, fetchSummary]
  );

  return {
    summary,
    scannedStudents,
    missingStudents,
    recentScans,
    loading,
    error,
    markStudent,
    refetch: fetchSummary,
    secondsSinceSync,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// useClassRoster
// ─────────────────────────────────────────────────────────────────────────────

import type { ClassRosterStudent } from '../services/api';

interface UseClassRosterResult {
  roster: ClassRosterStudent[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useClassRoster(classId: string, enabled = true): UseClassRosterResult {
  const [roster, setRoster] = useState<ClassRosterStudent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

import type { ClassPeriod } from '../services/api';

interface UseClassPeriodsResult {
  periods: ClassPeriod[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useClassPeriods(
  classId: string,
  date: string,
  enabled = true
): UseClassPeriodsResult {
  const [periods, setPeriods] = useState<ClassPeriod[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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