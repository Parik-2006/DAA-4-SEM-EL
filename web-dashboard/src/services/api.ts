/// <reference types="vite/client" />

import axios, { AxiosError, AxiosInstance } from 'axios';
import { withRetry, isRetryableError, RetryConfig } from '../utils/retry-handler';
import { SESSION_TOKEN_KEY } from './firebase/auth.service';
import { resolveUserRole } from '../utils/roles';

// ─────────────────────────────────────────────────────────────────────────────
// Axios Client
// ─────────────────────────────────────────────────────────────────────────────

export const apiClient: AxiosInstance = axios.create({
  baseURL: (
    import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  ).replace(/\/$/, ''),
  timeout: parseInt(import.meta.env.VITE_API_TIMEOUT || '15000'),
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
  validateStatus: () => true,
  maxRedirects: 5,
});

let retryAttemptCount = 0;

// ─────────────────────────────────────────────────────────────────────────────
// Request Interceptor
// ─────────────────────────────────────────────────────────────────────────────

apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(SESSION_TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  console.log(`[API Request] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
  return config;
});

// ─────────────────────────────────────────────────────────────────────────────
// Response Interceptor
// ─────────────────────────────────────────────────────────────────────────────

apiClient.interceptors.response.use(
  (response) => {
    retryAttemptCount = 0;

    if (response.status >= 400) {
      const status = response.status;
      const message =
        response.data?.detail ||
        response.data?.message ||
        response.statusText ||
        'Unknown error';

      console.error(`[API Error] ${status} - ${response.config?.url}: ${message}`);

      if (status === 401) {
        sessionStorage.removeItem(SESSION_TOKEN_KEY);
        window.location.replace('/login');
        return Promise.reject(
          new axios.AxiosError(message, String(status), response.config, response.request, response)
        );
      }

      return Promise.reject(
        new axios.AxiosError(message, String(status), response.config, response.request, response)
      );
    }

    console.log(`[API Response] ${response.status} ${response.config?.url}`);
    return response;
  },

  (error: AxiosError) => {
    const status = error.response?.status;
    const message =
      (error.response?.data as any)?.detail ||
      (error.response?.data as any)?.message ||
      error.message ||
      'Unknown error';

    console.error(`[API Error] ${status || 'Network'} - ${error.config?.url}: ${message}`);

    if (status === 401) {
      sessionStorage.removeItem(SESSION_TOKEN_KEY);
      window.location.replace('/login');
    }

    if (isRetryableError(error)) {
      retryAttemptCount++;
      console.warn(`[API] Retryable error detected. Attempt: ${retryAttemptCount}`);
    }

    return Promise.reject(error);
  }
);

// ─────────────────────────────────────────────────────────────────────────────
// Core Types
// ─────────────────────────────────────────────────────────────────────────────

export interface AttendanceRecord {
  id: string;
  student_name: string;
  student_id: string;
  course_name: string;
  marked_at: string;
  status: 'present' | 'late' | 'absent' | 'excused';
  avatar_url?: string;
  confidence?: number;
}

export interface AttendanceStats {
  total_present: number;
  total_late: number;
  total_absent: number;
  total_excused: number;
  last_updated: string;
}

export interface Student {
  id: string;
  name: string;
  student_id: string;
  email: string;
  department: string;
  semester?: string;
  avatar_url?: string;
}

export interface Course {
  id: string;
  code: string;
  name: string;
  instructor: string;
  students_count: number;
}

export interface DetectFaceResponse {
  matched: boolean;
  message: string;
  student_name?: string;
  student_id?: string;
  confidence?: number;
  record_id?: string;
  timestamp?: string;
}

export interface ConfirmAttendanceResponse {
  success: boolean;
  record_id: string;
  student_id: string;
  student_name: string;
  confidence: number;
  timestamp: string;
  message: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Period Attendance Model
// ─────────────────────────────────────────────────────────────────────────────

export interface PeriodStudentRecord {
  record_id?: string;
  student_id: string;
  student_name: string;
  roll_no: string;
  avatar_url?: string;
  status: 'present' | 'late' | 'absent' | 'not_scanned';
  scan_timestamp?: string;
  marked_at?: string;
  marked_by: 'camera' | 'manual' | string;
  confidence?: number;
}

export interface PeriodSummary {
  period_id: string;
  class_id: string;
  course_code: string;
  course_name: string;
  faculty_name?: string;
  room?: string;
  date: string;
  start_time: string;
  end_time: string;
  is_locked: boolean;
  total_enrolled: number;
  present_count: number;
  late_count: number;
  absent_count: number;
  not_scanned_count: number;
  students: PeriodStudentRecord[];
}

export interface ClassRosterStudent {
  student_id: string;
  name: string;
  roll_no: string;
  avatar_url?: string;
  class_id: string;
  email?: string;
}

export interface ClassPeriod {
  period_id: string;
  class_id: string;
  course_code: string;
  course_name: string;
  start_time: string;
  end_time: string;
  faculty_name?: string;
  room?: string;
  is_lab_class?: boolean;
  course_color?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Manual Attendance Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Payload for teacher's manual attendance marking.
 * `marked_by` should be the authenticated faculty's user ID.
 * `audit_source` is always "manual_teacher" so backend can distinguish
 * manual entries from face-recognition ones.
 */
export interface ManualAttendancePayload {
  student_id: string;
  status: 'present' | 'late' | 'absent' | 'excused';
  class_id: string;
  period_id: string;
  course_id: string;
  marked_by: string;
  notes?: string;
  /** ISO-8601 timestamp of when the teacher clicked save. */
  client_timestamp: string;
  audit_source: 'manual_teacher';
  metadata?: Record<string, unknown>;
}

/** Server response after a successful manual mark. */
export interface ManualAttendanceResponse {
  success: boolean;
  record_id: string;
  student_id: string;
  student_name: string;
  status: 'present' | 'late' | 'absent' | 'excused';
  period_id: string;
  course_id: string;
  marked_by: string;
  server_timestamp: string;
  client_timestamp: string;
  audit_source: 'manual_teacher';
  message: string;
}

/** Bulk payload for saving an entire roster in one request. */
export interface BulkManualAttendancePayload {
  class_id: string;
  period_id: string;
  course_id: string;
  marked_by: string;
  client_timestamp: string;
  audit_source: 'manual_teacher';
  entries: Array<{
    student_id: string;
    status: 'present' | 'late' | 'absent' | 'excused' | 'not_marked';
    notes?: string;
  }>;
  metadata?: Record<string, unknown>;
}

export interface BulkManualAttendanceResponse {
  success: boolean;
  saved: number;
  skipped: number;
  failed: number;
  errors: Array<{ student_id: string; reason: string }>;
  period_id: string;
  server_timestamp: string;
  message: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function toArray<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    for (const key of ['records', 'students', 'courses', 'data', 'items', 'periods']) {
      const val = (data as Record<string, unknown>)[key];
      if (Array.isArray(val)) return val as T[];
    }
  }
  return [];
}

function normaliseRecord(r: Record<string, unknown>): AttendanceRecord {
  return {
    id: String(r.record_id ?? r.id ?? ''),
    student_name: String(r.student_name ?? r.name ?? 'Unknown'),
    student_id: String(r.student_id ?? ''),
    course_name: String(r.course_name ?? r.course_id ?? ''),
    marked_at: String(r.timestamp ?? r.marked_at ?? new Date().toISOString()),
    status: (['present', 'late', 'absent', 'excused'].includes(String(r.status))
      ? r.status
      : 'present') as AttendanceRecord['status'],
    avatar_url: r.avatar_url ? String(r.avatar_url) : undefined,
    confidence: r.confidence != null ? Number(r.confidence) : undefined,
  };
}

function normalisePeriodStudent(r: Record<string, unknown>): PeriodStudentRecord {
  const status = String(r.status ?? 'not_scanned');
  return {
    record_id: r.record_id ? String(r.record_id) : undefined,
    student_id: String(r.student_id ?? ''),
    student_name: String(r.student_name ?? r.name ?? 'Unknown'),
    roll_no: String(r.roll_no ?? r.roll_number ?? r.student_id ?? ''),
    avatar_url: r.avatar_url ? String(r.avatar_url) : undefined,
    status: (['present', 'late', 'absent', 'not_scanned'].includes(status)
      ? status
      : 'not_scanned') as PeriodStudentRecord['status'],
    scan_timestamp: r.scan_timestamp ? String(r.scan_timestamp) : undefined,
    marked_at: r.marked_at ? String(r.marked_at) : undefined,
    marked_by:
      r.marked_by === 'camera' ? 'camera'
      : r.marked_by === 'manual' ? 'manual'
      : String(r.marked_by ?? 'manual'),
    confidence: r.confidence != null ? Number(r.confidence) : undefined,
  };
}

function buildDetectError(err: unknown): DetectFaceResponse {
  const axiosErr = err as AxiosError<{ detail?: string; message?: string }>;
  const status = axiosErr.response?.status;
  const detail =
    axiosErr.response?.data?.detail ||
    axiosErr.response?.data?.message ||
    axiosErr.message ||
    'Unknown error';

  console.error('[DetectError]', { status, detail, code: axiosErr.code });

  if (status && status >= 400 && status < 500) return { matched: false, message: detail };
  if (isRetryableError(err)) return { matched: false, message: 'Backend is starting up. Please wait a moment and try again.' };
  return { matched: false, message: `Server error (${status ?? 'network'}): ${detail}. Check backend logs.` };
}

// ─────────────────────────────────────────────────────────────────────────────
// AttendanceAPI
// ─────────────────────────────────────────────────────────────────────────────

class AttendanceAPI {
  private retryConfig: RetryConfig = {
    maxRetries: 5,
    initialDelayMs: 500,
    maxDelayMs: 10000,
    backoffMultiplier: 2,
    retryableStatusCodes: [408, 429, 500, 502, 503, 504],
    onRetry: (attempt, error, delayMs) => {
      console.warn(`[AttendanceAPI] Retry ${attempt} in ${delayMs}ms`, error.message);
    },
  };

  // ── Auth ────────────────────────────────────────────────────────────────────

  resolveLoginResponse(email: string, data: Record<string, unknown>): string {
    const resolution = resolveUserRole({
      email,
      backendRole: (data?.role as string | undefined) ?? null,
    });

    if (resolution.rejected) throw new Error(resolution.rejectionReason);

    if (data?.access_token) {
      sessionStorage.setItem(SESSION_TOKEN_KEY, String(data.access_token));
    }
    if (data?.user_id) {
      sessionStorage.setItem('user_id', String(data.user_id));
    }

    sessionStorage.setItem('user_email', email);
    sessionStorage.setItem('user_role', resolution.role);

    return resolution.role;
  }

  // ── Face Detection ──────────────────────────────────────────────────────────

  async detectFaceOnly(formData: FormData): Promise<DetectFaceResponse> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post<DetectFaceResponse>(
            '/api/v1/attendance/detect-face-only',
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 25000 }
          );
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[detectFaceOnly] Failed after retries:', err);
      return buildDetectError(err);
    }
  }

  async confirmAttendance(studentId: string, confidence: number): Promise<ConfirmAttendanceResponse> {
    return await withRetry(
      async () => {
        const response = await apiClient.post<ConfirmAttendanceResponse>(
          '/api/v1/attendance/confirm-attendance',
          { student_id: studentId, confidence }
        );
        return response.data;
      },
      { ...this.retryConfig, maxRetries: 3 }
    );
  }

  /** @deprecated Use detectFaceOnly + confirmAttendance */
  async detectAndMarkAttendance(formData: FormData): Promise<DetectFaceResponse> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post<DetectFaceResponse>(
            '/api/v1/attendance/detect-face',
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 25000 }
          );
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[detectAndMarkAttendance] Failed after retries:', err);
      return buildDetectError(err);
    }
  }

  // ── Period Attendance ───────────────────────────────────────────────────────

  async getPeriodSummary(
    periodId: string,
    classId: string,
    date?: string
  ): Promise<PeriodSummary | null> {
    const targetDate = date ?? new Date().toISOString().slice(0, 10);
    try {
      return await withRetry(async () => {
        const response = await apiClient.get(
          `/api/v1/attendance/period/${periodId}/summary`,
          { params: { class_id: classId, date: targetDate } }
        );
        const d = response.data as Record<string, unknown>;
        const rawStudents = toArray<Record<string, unknown>>(d.students ?? d.records ?? []);
        return {
          period_id: String(d.period_id ?? periodId),
          class_id: String(d.class_id ?? classId),
          course_code: String(d.course_code ?? ''),
          course_name: String(d.course_name ?? ''),
          faculty_name: d.faculty_name ? String(d.faculty_name) : undefined,
          room: d.room ? String(d.room) : undefined,
          date: String(d.date ?? targetDate),
          start_time: String(d.start_time ?? ''),
          end_time: String(d.end_time ?? ''),
          is_locked: Boolean(d.is_locked ?? false),
          total_enrolled: Number(d.total_enrolled ?? rawStudents.length),
          present_count: Number(d.present_count ?? 0),
          late_count: Number(d.late_count ?? 0),
          absent_count: Number(d.absent_count ?? 0),
          not_scanned_count: Number(d.not_scanned_count ?? 0),
          students: rawStudents.map(normalisePeriodStudent),
        };
      }, this.retryConfig);
    } catch {
      return null;
    }
  }

  async markPeriodStudentAttendance(
    periodId: string,
    classId: string,
    studentId: string,
    status: 'present' | 'late' | 'absent',
    date?: string
  ): Promise<void> {
    const targetDate = date ?? new Date().toISOString().slice(0, 10);
    await withRetry(
      async () => {
        await apiClient.post(`/api/v1/attendance/period/${periodId}/mark`, {
          class_id: classId,
          student_id: studentId,
          status,
          date: targetDate,
          marked_by: 'manual',
        });
      },
      { ...this.retryConfig, maxRetries: 3 }
    );
  }

  async lockPeriodSession(
    periodId: string,
    classId: string,
    absentStudentIds: string[],
    date?: string
  ): Promise<void> {
    const targetDate = date ?? new Date().toISOString().slice(0, 10);
    await withRetry(
      async () => {
        await apiClient.post(`/api/v1/attendance/period/${periodId}/lock`, {
          class_id: classId,
          date: targetDate,
          absent_student_ids: absentStudentIds,
        });
      },
      { ...this.retryConfig, maxRetries: 3 }
    );
  }

  async getClassPeriods(classId: string, date: string): Promise<ClassPeriod[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/timetable/periods', {
          params: { class_id: classId, date },
        });
        return toArray<Record<string, unknown>>(response.data).map((p) => ({
          period_id: String(p.period_id ?? p.id ?? ''),
          class_id: String(p.class_id ?? classId),
          course_code: String(p.course_code ?? ''),
          course_name: String(p.course_name ?? ''),
          start_time: String(p.start_time ?? ''),
          end_time: String(p.end_time ?? ''),
          faculty_name: p.faculty_name ? String(p.faculty_name) : undefined,
          room: p.room ? String(p.room) : undefined,
          is_lab_class: Boolean(p.is_lab_class ?? false),
          course_color: p.course_color ? String(p.course_color) : '#6366F1',
        }));
      }, this.retryConfig);
    } catch {
      return [];
    }
  }

  /**
   * Fetch full timetable for a class. Returns an object with days mapped to periods
   * and a simple course palette. If the backend doesn't provide the endpoint
   * or it fails, the caller should handle fallback to seeded timetable.
   */
  async getClassTimetable(classId: string): Promise<{ class_id: string; days: Record<string, ClassPeriod[]>; courses: Record<string, { name: string; color: string }> } | null> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/timetable/class', { params: { class_id: classId } });
        const data = response.data as Record<string, unknown>;

        // Expecting { class_id, days: { Monday: [...periods] }, courses: { CODE: { name, color } } }
        const daysRaw = (data.days ?? {}) as Record<string, unknown[]>;
        const days: Record<string, ClassPeriod[]> = {};

        Object.entries(daysRaw).forEach(([day, arr]) => {
          days[day] = toArray<Record<string, unknown>>(arr).map((p) => ({
            period_id: String(p.period_id ?? p.id ?? ''),
            class_id: String(p.class_id ?? classId),
            course_code: String(p.course_code ?? ''),
            course_name: String(p.course_name ?? ''),
            start_time: String(p.start_time ?? ''),
            end_time: String(p.end_time ?? ''),
            faculty_name: p.faculty_name ? String(p.faculty_name) : undefined,
            room: p.room ? String(p.room) : undefined,
            is_lab_class: Boolean(p.is_lab_class ?? false),
            course_color: p.course_color ? String(p.course_color) : '#6366F1',
          }));
        });

        const courses = (data.courses ?? {}) as Record<string, { name?: string; color?: string }>;
        const palette: Record<string, { name: string; color: string }> = {};
        Object.entries(courses).forEach(([code, info]) => {
          palette[code] = { name: info?.name ?? code, color: info?.color ?? '#6366F1' };
        });

        return {
          class_id: String(data.class_id ?? classId),
          days,
          courses: palette,
        };
      }, this.retryConfig);
    } catch (err) {
      console.warn('[getClassTimetable] could not fetch timetable:', err instanceof Error ? err.message : err);
      return null;
    }
  }

  async getClassRoster(classId: string): Promise<ClassRosterStudent[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/students', {
          params: { class_id: classId, limit: 1000 },
        });
        return toArray<Record<string, unknown>>(response.data).map((s) => ({
          student_id: String(s.student_id ?? s.id ?? ''),
          name: String(s.name ?? ''),
          roll_no: String(s.roll_no ?? s.roll_number ?? ''),
          avatar_url: s.avatar_url ? String(s.avatar_url) : undefined,
          class_id: String(s.class_id ?? classId),
          email: s.email ? String(s.email) : undefined,
        }));
      }, this.retryConfig);
    } catch {
      return [];
    }
  }

  // ── Manual Teacher Attendance ───────────────────────────────────────────────

  /**
   * Mark a single student's attendance manually (teacher action).
   *
   * Falls back gracefully: if the dedicated endpoint is missing (404/405), the
   * method retries against the legacy `/mark-attendance` endpoint.
   */
  async markAttendanceManual(payload: ManualAttendancePayload): Promise<ManualAttendanceResponse> {
    return withRetry(
      async () => {
        try {
          const response = await apiClient.post<ManualAttendanceResponse>(
            '/api/v1/attendance/mark-manual',
            payload,
            { timeout: 15000 }
          );
          return response.data;
        } catch (primaryErr: unknown) {
          const axiosErr = primaryErr as AxiosError;
          if (axiosErr.response?.status === 404 || axiosErr.response?.status === 405) {
            console.warn('[markAttendanceManual] Dedicated endpoint missing — falling back to /mark-attendance');
            const fallbackResponse = await apiClient.post(
              '/api/v1/attendance/mark-attendance',
              {
                student_id: payload.student_id,
                status: payload.status,
                camera_id: 'manual_teacher',
                metadata: {
                  class_id: payload.class_id,
                  period_id: payload.period_id,
                  course_id: payload.course_id,
                  marked_by: payload.marked_by,
                  notes: payload.notes,
                  client_timestamp: payload.client_timestamp,
                  audit_source: payload.audit_source,
                  ...payload.metadata,
                },
              },
              { timeout: 15000 }
            );
            const d = fallbackResponse.data as Record<string, unknown>;
            return {
              success: true,
              record_id: String(d.record_id ?? d.id ?? ''),
              student_id: payload.student_id,
              student_name: String(d.student_name ?? ''),
              status: payload.status,
              period_id: payload.period_id,
              course_id: payload.course_id,
              marked_by: payload.marked_by,
              server_timestamp: String(d.timestamp ?? new Date().toISOString()),
              client_timestamp: payload.client_timestamp,
              audit_source: 'manual_teacher',
              message: 'Attendance marked successfully (legacy endpoint)',
            } satisfies ManualAttendanceResponse;
          }
          throw primaryErr;
        }
      },
      { ...this.retryConfig, maxRetries: 3 }
    );
  }

  /**
   * Save an entire class roster in one request.
   * Falls back to sequential `markAttendanceManual` calls if the bulk endpoint
   * is unavailable (404/405).
   */
  async markAttendanceBulk(payload: BulkManualAttendancePayload): Promise<BulkManualAttendanceResponse> {
    return withRetry(
      async () => {
        try {
          const response = await apiClient.post<BulkManualAttendanceResponse>(
            '/api/v1/attendance/mark-manual-bulk',
            payload,
            { timeout: 30000 }
          );
          return response.data;
        } catch (primaryErr: unknown) {
          const axiosErr = primaryErr as AxiosError;
          if (axiosErr.response?.status === 404 || axiosErr.response?.status === 405) {
            console.warn('[markAttendanceBulk] Bulk endpoint missing — falling back to individual saves');
            const results = await Promise.allSettled(
              payload.entries
                .filter((e) => e.status !== 'not_marked')
                .map((entry) =>
                  this.markAttendanceManual({
                    student_id: entry.student_id,
                    status: entry.status as ManualAttendancePayload['status'],
                    class_id: payload.class_id,
                    period_id: payload.period_id,
                    course_id: payload.course_id,
                    marked_by: payload.marked_by,
                    notes: entry.notes,
                    client_timestamp: payload.client_timestamp,
                    audit_source: 'manual_teacher',
                    metadata: payload.metadata,
                  })
                )
            );
            const saved = results.filter((r) => r.status === 'fulfilled').length;
            const failed = results.filter((r) => r.status === 'rejected').length;
            const errors = results
              .map((r, i) =>
                r.status === 'rejected'
                  ? { student_id: payload.entries[i].student_id, reason: (r as PromiseRejectedResult).reason?.message ?? 'Unknown' }
                  : null
              )
              .filter(Boolean) as BulkManualAttendanceResponse['errors'];
            return {
              success: failed === 0,
              saved,
              skipped: payload.entries.filter((e) => e.status === 'not_marked').length,
              failed,
              errors,
              period_id: payload.period_id,
              server_timestamp: new Date().toISOString(),
              message: `Saved ${saved} records${failed > 0 ? `, ${failed} failed` : ''}`,
            };
          }
          throw primaryErr;
        }
      },
      { ...this.retryConfig, maxRetries: 2 }
    );
  }

  // ── Data Fetching ───────────────────────────────────────────────────────────

  async getAttendanceRecords(date: string, classId?: string): Promise<{ data: AttendanceRecord[] }> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/records', {
          params: { date, ...(classId ? { class_id: classId } : {}) },
        });
        return { data: toArray<Record<string, unknown>>(response.data).map(normaliseRecord) };
      }, this.retryConfig);
    } catch {
      return { data: [] };
    }
  }

  async getPeriodAttendance(periodId: string, classId: string): Promise<AttendanceRecord[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/period', {
          params: { period_id: periodId, class_id: classId },
        });
        return toArray<Record<string, unknown>>(response.data).map(normaliseRecord);
      }, this.retryConfig);
    } catch (err) {
      console.error('[getPeriodAttendance] Error:', err);
      return [];
    }
  }

  async getLiveAttendance(courseId?: string, limit = 50): Promise<AttendanceRecord[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/attendance', {
          params: { ...(courseId ? { student_id: courseId } : {}), limit },
        });
        return toArray<Record<string, unknown>>(response.data).map(normaliseRecord);
      }, this.retryConfig);
    } catch (err) {
      console.error('[getLiveAttendance] Error:', err);
      return [];
    }
  }

  async getAttendanceStats(courseId?: string, date?: string): Promise<AttendanceStats> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/stats', {
          params: {
            ...(courseId ? { course_id: courseId } : {}),
            ...(date ? { date } : {}),
          },
        });
        const d = response.data as Record<string, unknown>;
        return {
          total_present: Number(d.total_present ?? d.present_today ?? 0),
          total_late: Number(d.total_late ?? d.late_today ?? 0),
          total_absent: Number(d.total_absent ?? d.absent_today ?? 0),
          total_excused: Number(d.total_excused ?? 0),
          last_updated: String(d.last_updated ?? new Date().toISOString()),
        };
      }, this.retryConfig);
    } catch (err) {
      console.error('[getAttendanceStats] Error:', err);
      return { total_present: 0, total_late: 0, total_absent: 0, total_excused: 0, last_updated: new Date().toISOString() };
    }
  }

  async getAttendanceHistory(
    courseId?: string,
    startDate?: string,
    endDate?: string,
    page = 1,
    limit = 30
  ): Promise<AttendanceRecord[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/attendance', {
          params: {
            ...(courseId ? { student_id: courseId } : {}),
            ...(startDate ? { date_from: startDate } : {}),
            ...(endDate ? { date_to: endDate } : {}),
            limit,
            offset: (page - 1) * limit,
          },
        });
        return toArray<Record<string, unknown>>(response.data).map(normaliseRecord);
      }, this.retryConfig);
    } catch (err) {
      console.error('[getAttendanceHistory] Error:', err);
      return [];
    }
  }

  async getAttendanceSummary(
    courseId?: string,
    startDate?: string,
    endDate?: string
  ): Promise<Record<string, number>> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/attendance/daily-report', {
          params: { ...(startDate ? { date: startDate } : {}) },
        });
        const d = response.data as Record<string, unknown>;
        return {
          total_records: Number(d.total_records ?? 0),
          unique_students: Number(d.unique_students ?? 0),
        };
      }, this.retryConfig);
    } catch (err) {
      console.error('[getAttendanceSummary] Error:', err);
      return {};
    }
  }

  async getStudents(courseId?: string): Promise<Student[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/students', {
          params: { ...(courseId ? { course_id: courseId } : {}), limit: 1000 },
        });
        return toArray<Record<string, unknown>>(response.data).map((s) => ({
          id: String(s.student_id ?? s.id ?? ''),
          name: String(s.name ?? ''),
          student_id: String(s.student_id ?? ''),
          email: String(s.email ?? ''),
          department: String(s.department ?? ''),
          semester: s.semester ? String(s.semester) : undefined,
          avatar_url: s.avatar_url ? String(s.avatar_url) : undefined,
        }));
      }, this.retryConfig);
    } catch (err) {
      console.error('[getStudents] Error:', err);
      return [];
    }
  }

  async getCourses(): Promise<Course[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/courses');
        return toArray<Record<string, unknown>>(response.data).map((c) => ({
          id: String(c.id ?? ''),
          code: String(c.code ?? ''),
          name: String(c.name ?? ''),
          instructor: String(c.instructor ?? c.teacher_name ?? ''),
          students_count: Number(c.students_count ?? c.total_students ?? 0),
        }));
      }, this.retryConfig);
    } catch (err) {
      console.error('[getCourses] Error:', err);
      return [];
    }
  }

  // ── Admin ───────────────────────────────────────────────────────────────────

  async getAdminAttendanceToday(): Promise<Record<string, unknown>> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/admin/attendance/today');
        return response.data as Record<string, unknown>;
      }, this.retryConfig);
    } catch (err) {
      console.error('[getAdminAttendanceToday] Error:', err);
      return {};
    }
  }

  async getAllStudents(page = 1, limit = 50): Promise<unknown[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/students', {
          params: { limit, offset: (page - 1) * limit },
        });
        return toArray(response.data);
      }, this.retryConfig);
    } catch (err) {
      console.error('[getAllStudents] Error:', err);
      return [];
    }
  }

  async createStudent(name: string, email: string, courses: string[]): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.post('/api/v1/admin/students', { name, email, courses });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  async updateStudent(studentId: string, name: string, email: string, courses: string[]): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.put(`/api/v1/admin/students/${studentId}`, { name, email, courses });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  async deleteStudent(studentId: string): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.delete(`/api/v1/admin/students/${studentId}`);
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  async batchImportStudents(students: unknown[]): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.post('/api/v1/admin/batch-import', { students });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 2 });
  }

  async getAllCourses(page = 1, limit = 50): Promise<unknown[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/admin/courses', { params: { page, limit } });
        return toArray(response.data);
      }, this.retryConfig);
    } catch (err) {
      console.error('[getAllCourses] Error:', err);
      return [];
    }
  }

  async createCourse(name: string, code: string, schedule: string, room: string): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.post('/api/v1/admin/courses', { name, code, schedule, room });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  async updateCourse(courseId: string, name: string, code: string, schedule: string, room: string): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.put(`/api/v1/admin/courses/${courseId}`, { name, code, schedule, room });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  async toggleCourse(courseId: string, active: boolean): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.patch(`/api/v1/admin/courses/${courseId}`, { active });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  async deleteCourse(courseId: string): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.delete(`/api/v1/admin/courses/${courseId}`);
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  // ── Face Registration ───────────────────────────────────────────────────────

  async registerStudentFace(studentId: string, faceImageBase64: string): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.post('/api/v1/admin/register-face', {
        student_id: studentId,
        face_image_base64: faceImageBase64,
      });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  // ── QR Code ─────────────────────────────────────────────────────────────────

  async generateQRCode(): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.post('/api/v1/qr/generate', {});
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  async validateQRToken(token: string): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.get(`/api/v1/qr/validate/${token}`);
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  async scanQRCode(token: string, studentId: string): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.post('/api/v1/qr/scan', { token, student_id: studentId });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  // ── Health ───────────────────────────────────────────────────────────────────

  async healthCheck(): Promise<boolean> {
    try {
      const response = await apiClient.get('/api/v1/attendance/health');
      return response.status === 200;
    } catch (err) {
      console.warn('[healthCheck] Backend not healthy:', err instanceof Error ? err.message : err);
      return false;
    }
  }

  async waitForBackend(maxRetries = 30): Promise<void> {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        if (await this.healthCheck()) {
          console.log(`[AttendanceAPI] ✓ Backend healthy (attempt ${attempt})`);
          return;
        }
      } catch { /* continue */ }
      if (attempt < maxRetries) {
        const delayMs = Math.min(1000 * Math.pow(1.5, attempt - 1), 5000);
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }
    console.warn(`[AttendanceAPI] Backend still not healthy after ${maxRetries} attempts. Proceeding anyway...`);
  }
}

export const attendanceAPI = new AttendanceAPI();
export default apiClient;