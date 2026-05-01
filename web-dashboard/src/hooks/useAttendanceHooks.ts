/**
 * Custom hooks for the enhanced attendance system.
 *
 * useTimetable()        — fetch & cache weekly timetable for a student/class
 * usePeriodDetection()  — poll current-period endpoint every 30s
 * useStudentAttendance() — fetch attendance data with caching & filters
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';

const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

// ── Shared helpers ─────────────────────────────────────────────────────────────

async function apiFetch<T>(url: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const token = localStorage.getItem('auth_token');
  const response = await axios.get<T>(`${BASE}${url}`, {
    params,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    timeout: 15000,
  });
  return response.data;
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface PeriodCard {
  period_id: string;
  start_time: string;
  end_time: string;
  duration_minutes?: number;
  course_code: string;
  course_name: string;
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

// ── useTimetable ───────────────────────────────────────────────────────────────

interface UseTimetableOptions {
  studentId: string;
  enabled?: boolean;
}

interface UseTimetableResult {
  data: TimetableData | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

// Simple in-memory cache: key → { data, fetchedAt }
const timetableCache = new Map<string, { data: TimetableData; fetchedAt: number }>();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

export function useTimetable({ studentId, enabled = true }: UseTimetableOptions): UseTimetableResult {
  const [data, setData] = useState<TimetableData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTimetable = useCallback(async () => {
    if (!studentId || !enabled) return;

    // Check cache first
    const cached = timetableCache.get(studentId);
    if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) {
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
      const msg = axios.isAxiosError(err)
        ? err.response?.data?.detail || err.message
        : 'Failed to load timetable';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [studentId, enabled]);

  useEffect(() => {
    fetchTimetable();
  }, [fetchTimetable]);

  return { data, loading, error, refetch: fetchTimetable };
}

// ── usePeriodDetection ─────────────────────────────────────────────────────────

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
      const msg = axios.isAxiosError(err)
        ? err.response?.data?.detail || err.message
        : 'Period detection failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [classId, enabled]);

  useEffect(() => {
    if (!enabled) return;
    setLoading(true);
    checkPeriod();
    intervalRef.current = setInterval(checkPeriod, pollIntervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [checkPeriod, enabled, pollIntervalMs]);

  return { activePeriod, loading, error, lastChecked };
}

// ── useStudentAttendance ───────────────────────────────────────────────────────

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
      const msg = axios.isAxiosError(err)
        ? err.response?.data?.detail || err.message
        : 'Failed to load attendance data';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [studentId, enabled, page, pageSize, courseId, startDate, endDate]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { history, summary, dashboard, warnings, loading, error, refetch: fetchAll };
}
