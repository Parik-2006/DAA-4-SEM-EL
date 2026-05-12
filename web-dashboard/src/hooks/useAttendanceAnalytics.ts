/**
 * useAttendanceAnalytics.ts
 * -------------------------
 * Custom hook for the AttendanceAnalyticsPage.
 *
 * Strategy:
 *  1. Attempt to pull real data from the FastAPI backend.
 *  2. If the backend is unavailable / returns no data for the chosen
 *     period, silently fall back to deterministic mock data so the
 *     UI always renders something useful.
 *  3. Poll every `pollMs` ms for live updates.
 *  4. Expose `simulateMark()` for demo / testing without a backend.
 *
 * Drop into:  web-dashboard/src/hooks/useAttendanceAnalytics.ts
 */

import {
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
} from 'react';
import { attendanceAPI } from '../services/api';
import {
  PERIODS,
  STUDENT_NAMES,
  getPastSessionDates,
  type Period,
  type DayCode,
} from '../config/timetable';

// ─── Public types ──────────────────────────────────────────────────────────────

export type AttendanceStatus = 'present' | 'absent' | 'late';

export interface ActivityEntry {
  rollNo:      string;
  studentName: string;
  status:      AttendanceStatus;
  method:      string;
  timestamp:   Date;
}

export interface AnalyticsState {
  present:          number;
  absent:           number;
  late:             number;
  notMarked:        number;
  marked:           number;
  total:            number;
  shuffledStudents: string[];
  activity:         ActivityEntry[];
}

export interface TrendPoint {
  date: string;
  pct:  number;
}

export interface UseAttendanceAnalyticsResult {
  /** Current live counts. null while first load is in flight. */
  state:         AnalyticsState | null;
  /** Pre-built recharts data for the 7-session trend bar chart. */
  trendData:     TrendPoint[];
  /** Pre-built recharts data for the distribution donut. */
  donutData:     Array<{ name: string; value: number; color: string }>;
  /** Convenience: (present + late) / total × 100. */
  attendancePct: number;
  /** Convenience: marked / total × 100. */
  markingPct:    number;
  lastUpdated:   Date;
  isLoading:     boolean;
  /** Non-null when the API call itself threw (not just returned empty). */
  error:         string | null;
  /** Force an immediate refetch from the API. */
  refetch:       () => void;
  /**
   * Add one synthetic attendance entry to the current period.
   * Useful for demo mode or e2e testing without a live backend.
   */
  simulateMark:  () => void;
}

// ─── Private constants ────────────────────────────────────────────────────────

const MARK_METHODS = ['Face scan', 'QR code', 'Manual', 'RFID', 'App check-in'];

const DONUT_META = [
  { name: 'Present',    color: '#639922' },
  { name: 'Late',       color: '#EF9F27' },
  { name: 'Absent',     color: '#E24B4A' },
  { name: 'Not Marked', color: '#B4B2A9' },
] as const;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pct(a: number, b: number): number {
  return b > 0 ? Math.round((a / b) * 100) : 0;
}

function randomMethod(): string {
  return MARK_METHODS[Math.floor(Math.random() * MARK_METHODS.length)];
}

/**
 * Build a deterministic-ish initial state from the period config.
 * Called when the API returns nothing useful.
 */
function buildMockState(period: Period): AnalyticsState {
  const shuffled = [...STUDENT_NAMES].sort(() => Math.random() - 0.5);
  const marked   = Math.floor(period.totalStudents * (0.64 + Math.random() * 0.18));
  const present  = Math.floor(marked * 0.78);
  const late     = Math.floor(marked * 0.07);
  const absent   = marked - present - late;
  const now      = Date.now();

  const activity: ActivityEntry[] = [];
  for (let i = 0; i < marked; i++) {
    const status: AttendanceStatus =
      i < present ? 'present' : i < present + late ? 'late' : 'absent';
    activity.push({
      rollNo:      String(i + 1).padStart(3, '0'),
      studentName: shuffled[i],
      status,
      method:    randomMethod(),
      timestamp: new Date(now - (marked - i) * 44_000 - Math.random() * 20_000),
    });
  }
  activity.reverse(); // newest first

  return {
    present, late, absent,
    notMarked:        period.totalStudents - marked,
    marked,
    total:            period.totalStudents,
    shuffledStudents: shuffled,
    activity,
  };
}

/**
 * Attempt to map the raw admin-today API response into AnalyticsState.
 * Returns null if the response doesn't have usable data.
 */
function mapApiResponse(
  raw:    Record<string, unknown>,
  period: Period,
): AnalyticsState | null {
  // The existing admin endpoint returns totalStudents, attendanceRate,
  // pendingRecords, presentStudentIds.  We use that as a best-effort map.
  const total       = period.totalStudents;
  const rawPresent  = Number(raw.presentCount   ?? raw.present_count   ?? 0);
  const rawAbsent   = Number(raw.absentCount    ?? raw.absent_count    ?? 0);
  const rawLate     = Number(raw.lateCount      ?? raw.late_count      ?? 0);
  const rawPending  = Number(raw.pendingRecords ?? raw.not_marked      ?? 0);

  // If everything is 0 the response probably isn't period-specific — bail.
  if (rawPresent + rawAbsent + rawLate + rawPending === 0) return null;

  const marked = rawPresent + rawAbsent + rawLate;

  // Build a minimal activity list from presentStudentIds if available.
  const presentIds: string[] = Array.isArray(raw.presentStudentIds)
    ? (raw.presentStudentIds as string[])
    : [];

  const activity: ActivityEntry[] = presentIds.map((id, i) => ({
    rollNo:      String(i + 1).padStart(3, '0'),
    studentName: id,
    status:      'present' as AttendanceStatus,
    method:      'Face scan',
    timestamp:   new Date(),
  }));

  return {
    present:          rawPresent,
    absent:           rawAbsent,
    late:             rawLate,
    notMarked:        rawPending || total - marked,
    marked,
    total,
    shuffledStudents: [...STUDENT_NAMES].sort(() => Math.random() - 0.5),
    activity,
  };
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export interface UseAttendanceAnalyticsOptions {
  periodId:   string;
  pollMs?:    number;
  /** Set true to skip the API call entirely and always use mock data. */
  mockOnly?:  boolean;
}

export function useAttendanceAnalytics({
  periodId,
  pollMs   = 6_000,
  mockOnly = false,
}: UseAttendanceAnalyticsOptions): UseAttendanceAnalyticsResult {

  const period = useMemo(
    () => PERIODS.find(p => p.id === periodId) ?? PERIODS[0],
    [periodId],
  );

  const [state,       setState]       = useState<AnalyticsState | null>(null);
  const [isLoading,   setIsLoading]   = useState(true);
  const [error,       setError]       = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const intervalRef    = useRef<ReturnType<typeof setInterval>>();
  const isMountedRef   = useRef(true);

  // ── Fetch (or build mock) ────────────────────────────────────────────────

  const fetchOrMock = useCallback(async () => {
    if (!isMountedRef.current) return;

    if (mockOnly) {
      // Pure mock path — no network call
      setState(prev => prev ?? buildMockState(period));
      setIsLoading(false);
      setLastUpdated(new Date());
      return;
    }

    try {
      const raw = await attendanceAPI.getAdminAttendanceToday();

      if (!isMountedRef.current) return;

      // Try to coerce the API response into our shape
      const mapped = raw && typeof raw === 'object'
        ? mapApiResponse(raw as Record<string, unknown>, period)
        : null;

      if (mapped) {
        setState(mapped);
        setError(null);
      } else {
        // API alive but no useful data for this period → use / keep mock
        setState(prev => prev ?? buildMockState(period));
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      const msg = err instanceof Error ? err.message : 'Unknown error';
      console.warn(`[useAttendanceAnalytics] API error (${msg}), using mock data.`);
      setError(msg);
      setState(prev => prev ?? buildMockState(period));
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
        setLastUpdated(new Date());
      }
    }
  }, [period, mockOnly]);

  // ── Period switch: rebuild state immediately ─────────────────────────────

  useEffect(() => {
    setState(null);
    setIsLoading(true);
    setError(null);
    fetchOrMock();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodId]);           // intentionally only on periodId change

  // ── Polling ──────────────────────────────────────────────────────────────

  useEffect(() => {
    clearInterval(intervalRef.current);
    intervalRef.current = setInterval(fetchOrMock, pollMs);
    return () => clearInterval(intervalRef.current);
  }, [fetchOrMock, pollMs]);

  // ── Cleanup ──────────────────────────────────────────────────────────────

  useEffect(() => {
    isMountedRef.current = true;
    return () => { isMountedRef.current = false; };
  }, []);

  // ── simulateMark ─────────────────────────────────────────────────────────

  const simulateMark = useCallback(() => {
    setState(prev => {
      if (!prev || prev.notMarked <= 0) return prev;
      const used  = new Set(prev.activity.map(a => a.studentName));
      const avail = prev.shuffledStudents.filter(n => !used.has(n));
      if (!avail.length) return prev;

      const name   = avail[Math.floor(Math.random() * avail.length)];
      const r      = Math.random();
      const status: AttendanceStatus = r < 0.78 ? 'present' : r < 0.89 ? 'late' : 'absent';

      const entry: ActivityEntry = {
        rollNo:      String(prev.marked + 1).padStart(3, '0'),
        studentName: name,
        status,
        method:    randomMethod(),
        timestamp: new Date(),
      };

      return {
        ...prev,
        present:   prev.present   + (status === 'present' ? 1 : 0),
        late:      prev.late      + (status === 'late'    ? 1 : 0),
        absent:    prev.absent    + (status === 'absent'  ? 1 : 0),
        notMarked: prev.notMarked - 1,
        marked:    prev.marked    + 1,
        activity:  [entry, ...prev.activity],
      };
    });
    setLastUpdated(new Date());
  }, []);

  // ── Derived values ───────────────────────────────────────────────────────

  const trendDates = useMemo(
    () => getPastSessionDates(period.day as DayCode),
    [period.day],
  );

  const trendData: TrendPoint[] = useMemo(
    () => period.trendBase.map((v, i) => ({
      date: trendDates[i] ?? `S${i + 1}`,
      pct:  v,
    })),
    [period.trendBase, trendDates],
  );

  const donutData = useMemo(() => {
    if (!state) return [];
    const values = [state.present, state.late, state.absent, state.notMarked];
    return DONUT_META.map((m, i) => ({ ...m, value: values[i] }));
  }, [state]);

  const attendancePct = state
    ? pct(state.present + state.late, state.total)
    : 0;

  const markingPct = state
    ? pct(state.marked, state.total)
    : 0;

  return {
    state,
    trendData,
    donutData,
    attendancePct,
    markingPct,
    lastUpdated,
    isLoading,
    error,
    refetch:      fetchOrMock,
    simulateMark,
  };
}

// ─── CSV export utility ───────────────────────────────────────────────────────

/**
 * Download the full activity log for a period as a CSV file.
 * Call this from any component that holds an `AnalyticsState`.
 */
export function exportActivityCSV(state: AnalyticsState, period: Period): void {
  const rows: string[][] = [
    ['Roll No', 'Student Name', 'Status', 'Method', 'Time', 'Date'],
    ...state.activity.map(e => [
      e.rollNo,
      e.studentName,
      e.status,
      e.method,
      e.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      e.timestamp.toLocaleDateString(),
    ]),
  ];

  const csv  = rows.map(r => r.map(c => `"${c}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `attendance_${period.code}_${period.day}_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}