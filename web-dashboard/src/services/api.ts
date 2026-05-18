/// <reference types="vite/client" />

import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { withRetry, isRetryableError, RetryConfig } from '../utils/retry-handler';
import { getAuthToken, clearSession, SESSION_TOKEN_KEY } from './firebase/auth.service';
import { resolveUserRole, getStoredRole } from '../utils/roles';

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

// ─────────────────────────────────────────────────────────────────────────────
// Auth Redirect Helper
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Wipes the session and sends the browser to /login.
 * Idempotent — safe to call multiple times; subsequent calls while a redirect
 * is already in progress are suppressed.
 */
let redirectingToLogin = false;
function forceLogin(reason: string): void {
  if (redirectingToLogin) return;
  redirectingToLogin = true;
  console.warn(`[API] Forcing re-login: ${reason}`);
  clearSession();
  window.location.replace('/login');
}

// ─────────────────────────────────────────────────────────────────────────────
// Request Interceptor — Attach JWT via Firebase getValidToken
// ─────────────────────────────────────────────────────────────────────────────

apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const url = config.url ?? '';
    const isPublic =
      url.includes('/health') ||
      url.includes('/auth/login') ||
      url.includes('/auth/register');

    if (!isPublic) {
      const token = await getAuthToken();
      config.headers = config.headers ?? {};
      config.headers.Authorization = `Bearer ${token}`;
    }

    console.log(
      `[API →] ${config.method?.toUpperCase()} ${config.baseURL ?? ''}${config.url}`
    );
    return config;
  },
  (error) => Promise.reject(error)
);

// ─────────────────────────────────────────────────────────────────────────────
// Response Interceptor
// ─────────────────────────────────────────────────────────────────────────────

apiClient.interceptors.response.use(
  (response) => {
    console.log(`[API ←] ${response.status} ${response.config?.url}`);

    if (response.status >= 400) {
      const msg =
        response.data?.detail ||
        response.data?.message ||
        response.statusText ||
        'Request failed';

      if (response.status === 401) {
        forceLogin('401 received from server');
      }

      return Promise.reject(
        new axios.AxiosError(
          msg,
          String(response.status),
          response.config,
          response.request,
          response
        )
      );
    }

    return response;
  },
  (error: AxiosError) => {
    if (axios.isCancel(error)) return Promise.reject(error);

    const status = error.response?.status;
    const msg =
      (error.response?.data as Record<string, unknown>)?.detail ||
      (error.response?.data as Record<string, unknown>)?.message ||
      error.message ||
      'Unknown error';

    console.error(`[API ✕] ${status ?? 'Network'} — ${error.config?.url}: ${msg}`);

    if (status === 401) {
      forceLogin('401 on error path');
      return Promise.reject(error);
    }

    if (status === 403) {
      console.warn('[API] 403 Forbidden — insufficient permissions');
    }

    if (isRetryableError(error)) {
      console.warn('[API] Retryable error detected');
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

/** Response from detect-face-only endpoint (Step 1). No record saved yet. */
export interface DetectFaceResponse {
  matched: boolean;
  message: string;
  student_name?: string;
  student_id?: string;
  confidence?: number;
  record_id?: string;
  timestamp?: string;
  window?: AttendanceWindowInfo | null;
  suggested_candidates?: CandidateSuggestion[];
}

export interface CandidateSuggestion {
  student_id: string;
  student_name: string;
  confidence: number;
}

/** Response from confirm-attendance endpoint (Step 2). Record persisted. */
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
// Admin / Role-Aware Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * A single attendance record as seen by admin/teacher — includes
 * class, period, method, manual-override flag, and who marked it.
 */
export interface AdminAttendanceRecord {
  record_id: string;
  student_id: string;
  student_name: string;
  roll_no?: string;
  class_id?: string;
  class_name?: string;
  course_code?: string;
  course_name?: string;
  /** period_id from the timetable */
  period_id?: string;
  /** Formatted as "HH:MM–HH:MM", e.g. "09:00–10:00" */
  period_time?: string;
  date: string;
  /** Time portion only, e.g. "09:43" */
  time?: string;
  status: 'present' | 'absent' | 'late' | 'pending';
  marked_by?: string;
  marked_by_name?: string;
  method?: 'face_recognition' | 'manual' | 'qr_code' | 'auto';
  /** 0–1 face-recognition confidence score */
  confidence?: number;
  /** True when a teacher/admin manually changed the status */
  is_manual_override?: boolean;
  override_reason?: string;
}

export interface PaginatedAdminHistory {
  records: AdminAttendanceRecord[];
  total: number;
  page: number;
  total_pages: number;
  stats?: {
    present: number;
    absent: number;
    late: number;
    total: number;
    /** 0–100 percentage */
    rate: number;
  };
}

export interface ClassInfo {
  class_id: string;
  class_name: string;
  section?: string;
  semester?: string;
  department?: string;
}

export interface PeriodInfo {
  period_id: string;
  start_time: string;
  end_time: string;
  course_code: string;
  course_name: string;
  class_id: string;
  day_of_week?: string;
  faculty_name?: string;
  room?: string;
  is_lab_class?: boolean;
  course_color?: string;
}

export interface AttendanceWindowInfo {
  period_id?: string;
  phase?: string;
  message?: string;
  start_time?: string;
  end_time?: string;
  grace_minutes_left?: number;
  remaining_minutes?: number;
  is_open?: boolean;
  is_locked?: boolean;
}

/** Scope parameters sent with every face-detection request. Derived from auth context. */
export interface FaceDetectScopeParams {
  scope_mode: 'self_verify' | 'section_roster';
  student_id?: string;
  section_id?: string;
  period_id?: string;
  candidate_student_ids?: string[];
  exclude_student_ids?: string[];
}

export interface AttendanceCandidatesResponse {
  candidate_student_ids: string[] | null;
  count: number | null;
}

export interface AdminHistoryFilters {
  classId?: string;
  periodId?: string;
  /** ISO date e.g. "2025-05-08". Mutually exclusive with startDate/endDate. */
  date?: string;
  startDate?: string;
  endDate?: string;
  status?: string;
  /** Free-text search on student name or ID */
  search?: string;
  page?: number;
  limit?: number;
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
  /** ISO-8601 timestamp of when the teacher clicked save */
  client_timestamp: string;
  audit_source: 'manual_teacher';
  metadata?: Record<string, unknown>;
}

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
// Analytics Types
// ─────────────────────────────────────────────────────────────────────────────

export interface AnalyticsPeriodRecord {
  student_id: string;
  student_name: string;
  status: 'present' | 'absent' | 'late';
  method: string;
  timestamp: string;
}

export interface AnalyticsPeriodSummary {
  present: number;
  absent: number;
  late: number;
  not_marked: number;
  total: number;
}

export interface AnalyticsPeriodResponse {
  records: AnalyticsPeriodRecord[];
  summary: AnalyticsPeriodSummary;
  period: { course_code: string; day: string; date: string };
}

export interface AnalyticsSectionSummaryItem {
  course_code: string;
  course_name: string;
  day: string;
  time: string;
  present: number;
  absent: number;
  late: number;
  not_marked: number;
  total: number;
  percentage: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal Helpers
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

function normaliseAdminRecord(r: Record<string, unknown>): AdminAttendanceRecord {
  const periodTime = r.period_time
    ? String(r.period_time)
    : r.start_time && r.end_time
    ? `${r.start_time}–${r.end_time}`
    : undefined;

  const rawTimestamp = String(r.timestamp ?? r.marked_at ?? '');
  const timeFromTimestamp =
    rawTimestamp.length >= 16 ? rawTimestamp.slice(11, 16) : undefined;

  const rawMethod = String(r.method ?? r.detection_method ?? '');
  const validMethods = ['face_recognition', 'manual', 'qr_code', 'auto'];

  return {
    record_id: String(r.record_id ?? r.id ?? ''),
    student_id: String(r.student_id ?? ''),
    student_name: String(r.student_name ?? r.name ?? 'Unknown'),
    roll_no: r.roll_no ? String(r.roll_no) : undefined,
    class_id: r.class_id ? String(r.class_id) : undefined,
    class_name: r.class_name ? String(r.class_name) : undefined,
    course_code: r.course_code ? String(r.course_code) : undefined,
    course_name: r.course_name ? String(r.course_name) : undefined,
    period_id: r.period_id ? String(r.period_id) : undefined,
    period_time: periodTime,
    date: String(r.date ?? rawTimestamp.slice(0, 10) ?? ''),
    time: r.time ? String(r.time) : timeFromTimestamp,
    status: (['present', 'absent', 'late', 'pending'].includes(String(r.status))
      ? r.status
      : 'present') as AdminAttendanceRecord['status'],
    marked_by: r.marked_by ? String(r.marked_by) : undefined,
    marked_by_name: r.marked_by_name
      ? String(r.marked_by_name)
      : r.marked_by
      ? String(r.marked_by)
      : undefined,
    method: validMethods.includes(rawMethod)
      ? (rawMethod as AdminAttendanceRecord['method'])
      : undefined,
    confidence: r.confidence != null ? Number(r.confidence) : undefined,
    is_manual_override:
      r.is_manual_override != null ? Boolean(r.is_manual_override) : undefined,
    override_reason: r.override_reason ? String(r.override_reason) : undefined,
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

  if (status && status >= 400 && status < 500) {
    return { matched: false, message: String(detail) };
  }
  if (isRetryableError(err)) {
    return { matched: false, message: 'Backend is starting up. Please wait a moment and try again.' };
  }
  return {
    matched: false,
    message: `Server error (${status ?? 'network'}): ${detail}. Check backend logs.`,
  };
}

function publishAttendanceUpdated(): void {
  try {
    const payload = String(Date.now());
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('attendance_last_updated', payload);
      window.dispatchEvent(new CustomEvent('attendance:updated', { detail: { timestamp: payload } }));
    }
  } catch (error) {
    console.warn('[AttendanceAPI] Could not publish attendance update:', error);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// AttendanceAPI
// ─────────────────────────────────────────────────────────────────────────────

class AttendanceAPI {
  private retryConfig: RetryConfig = {
    maxRetries: 5,
    initialDelayMs: 500,
    maxDelayMs: 10_000,
    backoffMultiplier: 2,
    retryableStatusCodes: [408, 429, 500, 502, 503, 504],
    onRetry: (attempt, error, delayMs) => {
      console.warn(`[AttendanceAPI] Retry ${attempt} in ${delayMs}ms — ${error.message}`);
    },
  };

  // ── Auth ────────────────────────────────────────────────────────────────────

  /**
   * Resolves the user's role from a login response, stores the session token,
   * and returns the resolved role string.
   */
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
    sessionStorage.setItem('assigned_sections', JSON.stringify(Array.isArray(data?.assigned_sections) ? data.assigned_sections : []));

    return resolution.role;
  }

  // ── Two-Step Attendance Flow ────────────────────────────────────────────────

  async detectFaceOnly(
    formData: FormData,
    scope: FaceDetectScopeParams
  ): Promise<DetectFaceResponse> {
    // Build query string from scope params — backend reads them as Query params
    const params = new URLSearchParams();
    params.set('scope_mode', scope.scope_mode);
    if (scope.student_id) params.set('student_id', scope.student_id);
    if (scope.section_id) params.set('section_id', scope.section_id);
    if (scope.period_id)  params.set('period_id',  scope.period_id);
    if (scope.candidate_student_ids?.length) {
      params.set('candidate_student_ids', scope.candidate_student_ids.join(','));
    }
    if (scope.exclude_student_ids?.length) {
      params.set('exclude_student_ids', scope.exclude_student_ids.join(','));
    }

    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post<DetectFaceResponse>(
            `/api/v1/attendance/detect-face-only?${params.toString()}`,
            formData,
            {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 25_000,
            }
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

  async confirmAttendance(
    studentId: string,
    confidence: number,
    periodId?: string,
    frame?: Blob | File | null,
  ): Promise<ConfirmAttendanceResponse> {
    const response = await withRetry(
      async () => {
        const body = new FormData();
        body.append('student_id', studentId);
        body.append('confidence', String(confidence));
        if (periodId) body.append('period_id', periodId);
        if (frame) {
          const fileName = frame instanceof File ? frame.name : 'confirmed_frame.jpg';
          body.append('frame', frame, fileName);
        }
        const response = await apiClient.post<ConfirmAttendanceResponse>(
          '/api/v1/attendance/confirm-attendance',
          body,
          { timeout: 25_000, headers: { 'Content-Type': 'multipart/form-data' } }
        );
        return response.data;
      },
      { ...this.retryConfig, maxRetries: 3 }
    );
    publishAttendanceUpdated();
    return response;
  }

  async getAttendanceCandidates(periodId?: string): Promise<AttendanceCandidatesResponse | null> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/candidates', {
          params: { ...(periodId ? { period_id: periodId } : {}) },
        });
        const data = response.data as Record<string, unknown>;
        const candidatesRaw = data.candidate_student_ids;
        return {
          candidate_student_ids: Array.isArray(candidatesRaw)
            ? candidatesRaw.map((value) => String(value))
            : null,
          count: data.count != null ? Number(data.count) : null,
        };
      }, this.retryConfig);
    } catch (err) {
      console.error('[getAttendanceCandidates] Error:', err);
      return null;
    }
  }

  async getWindowStatus(periodId: string): Promise<AttendanceWindowInfo | null> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/window-status', {
          params: { period_id: periodId },
        });
        return response.data as AttendanceWindowInfo;
      }, this.retryConfig);
    } catch (err) {
      console.warn('[getWindowStatus] Error:', err);
      return null;
    }
  }

  /** @deprecated Use detectFaceOnly + confirmAttendance for the two-step flow. */
  async detectAndMarkAttendance(formData: FormData): Promise<DetectFaceResponse> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post<DetectFaceResponse>(
            '/api/v1/attendance/detect-face',
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 25_000 }
          );
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
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
   * Fetch full timetable for a class. Returns days mapped to periods and a
   * course colour palette. Returns null on failure; caller handles fallback.
   */
  async getClassTimetable(classId: string): Promise<{
    class_id: string;
    days: Record<string, ClassPeriod[]>;
    courses: Record<string, { name: string; color: string }>;
  } | null> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/timetable/class', {
          params: { class_id: classId },
        });
        const data = response.data as Record<string, unknown>;
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

        const coursesRaw = (data.courses ?? {}) as Record<
          string,
          { name?: string; color?: string }
        >;
        const palette: Record<string, { name: string; color: string }> = {};
        Object.entries(coursesRaw).forEach(([code, info]) => {
          palette[code] = { name: info?.name ?? code, color: info?.color ?? '#6366F1' };
        });

        return { class_id: String(data.class_id ?? classId), days, courses: palette };
      }, this.retryConfig);
    } catch (err) {
      console.warn(
        '[getClassTimetable] Failed:',
        err instanceof Error ? err.message : err
      );
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
   * Falls back to the legacy `/mark-attendance` endpoint on 404/405.
   */
  async markAttendanceManual(
    payload: ManualAttendancePayload
  ): Promise<ManualAttendanceResponse> {
    return withRetry(
      async () => {
        try {
          const response = await apiClient.post<ManualAttendanceResponse>(
            '/api/v1/attendance/mark-manual',
            payload,
            { timeout: 15_000 }
          );
          return response.data;
        } catch (primaryErr: unknown) {
          const axiosErr = primaryErr as AxiosError;
          if (
            axiosErr.response?.status === 404 ||
            axiosErr.response?.status === 405
          ) {
            console.warn(
              '[markAttendanceManual] Dedicated endpoint missing — falling back to /mark-attendance'
            );
            const fallback = await apiClient.post(
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
              { timeout: 15_000 }
            );
            const d = fallback.data as Record<string, unknown>;
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
   * Falls back to sequential `markAttendanceManual` calls on 404/405.
   */
  async markAttendanceBulk(
    payload: BulkManualAttendancePayload
  ): Promise<BulkManualAttendanceResponse> {
    return withRetry(
      async () => {
        try {
          const response = await apiClient.post<BulkManualAttendanceResponse>(
            '/api/v1/attendance/mark-manual-bulk',
            payload,
            { timeout: 30_000 }
          );
          return response.data;
        } catch (primaryErr: unknown) {
          const axiosErr = primaryErr as AxiosError;
          if (
            axiosErr.response?.status === 404 ||
            axiosErr.response?.status === 405
          ) {
            console.warn(
              '[markAttendanceBulk] Bulk endpoint missing — falling back to individual saves'
            );
            const toSave = payload.entries.filter((e) => e.status !== 'not_marked');
            const results = await Promise.allSettled(
              toSave.map((entry) =>
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
                  ? {
                      student_id: toSave[i].student_id,
                      reason:
                        (r as PromiseRejectedResult).reason?.message ?? 'Unknown',
                    }
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
      return {
        total_present: 0, total_late: 0, total_absent: 0, total_excused: 0,
        last_updated: new Date().toISOString(),
      };
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
        const response = await apiClient.get(
          '/api/v1/attendance/attendance/daily-report',
          { params: { ...(startDate ? { date: startDate } : {}) } }
        );
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

  async getAttendanceRecords(
    date?: string,
    classId?: string
  ): Promise<{ data: AttendanceRecord[]; total: number }> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/attendance/records', {
          params: {
            ...(date ? { date } : {}),
            ...(classId ? { class_id: classId } : {}),
            limit: 200,
          },
        });
        const raw = response.data;
        const arr = toArray<Record<string, unknown>>(raw).map(normaliseRecord);
        return {
          data: arr,
          total: Array.isArray(raw)
            ? raw.length
            : Number((raw as Record<string, unknown>)?.total ?? arr.length),
        };
      }, this.retryConfig);
    } catch {
      // Graceful fallback to live attendance
      const records = await this.getLiveAttendance(undefined, 100);
      return { data: records, total: records.length };
    }
  }

  /**
   * Fetch attendance records for a specific timetable period and class.
   * Uses the period/{periodId}/summary endpoint path.
   *
   * For analytics-style queries by course_code + day, use
   * `getAnalyticsPeriodAttendance` instead.
   */
  async getPeriodAttendance(
    periodId: string,
    classId: string
  ): Promise<AttendanceRecord[]> {
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

  // ── Admin / Teacher History ─────────────────────────────────────────────────

  /**
   * Paginated, filterable attendance history for admin and teacher roles.
   * Supports filtering by class, period, date (single or range), status, and
   * free-text search.
   */
  async getAdminHistory(filters: AdminHistoryFilters): Promise<PaginatedAdminHistory> {
    const {
      classId, periodId, date, startDate, endDate,
      status, search, page = 1, limit = 50,
    } = filters;
    const role = getStoredRole();

    try {
      return await withRetry(async () => {
        if (role === 'teacher') {
          // Teachers must always query the scoped teacher endpoint.
          if (!classId) {
            return {
              records: [],
              total: 0,
              page,
              total_pages: 1,
            };
          }

          const teacherResponse = await apiClient.get('/api/v1/teacher/attendance/history', {
            params: {
              class_id: classId,
              ...(date ? { start_date: date, end_date: date } : {}),
              ...(startDate ? { start_date: startDate } : {}),
              ...(endDate ? { end_date: endDate } : {}),
              page,
              page_size: limit,
            },
          });

          const td = teacherResponse.data as Record<string, unknown>;
          const teacherRecords = toArray<Record<string, unknown>>(
            (td.records ?? td.data ?? td) as unknown
          );

          return {
            records: teacherRecords.map(normaliseAdminRecord),
            total: Number(td.total ?? teacherRecords.length),
            page: Number(td.page ?? page),
            total_pages: Number(td.total_pages ?? (Math.ceil(teacherRecords.length / limit) || 1)),
          };
        }

        const response = await apiClient.get('/api/v1/admin/attendance/history', {
          params: {
            ...(classId   ? { class_id:   classId   } : {}),
            ...(periodId  ? { period_id:  periodId  } : {}),
            ...(date      ? { date                   } : {}),
            ...(startDate ? { start_date: startDate } : {}),
            ...(endDate   ? { end_date:   endDate   } : {}),
            ...(status    ? { status                 } : {}),
            ...(search    ? { search                 } : {}),
            page,
            limit,
          },
        });
        const d = response.data as Record<string, unknown>;
        const rawRecords = toArray<Record<string, unknown>>(
          (d.records ?? d.data ?? d) as unknown
        );
        const total = Number(d.total ?? rawRecords.length);
        const totalPages = Number(d.total_pages ?? Math.ceil(total / limit));
        const stats = d.stats as Record<string, unknown> | undefined;

        return {
          records: rawRecords.map(normaliseAdminRecord),
          total,
          page: Number(d.page ?? page),
          total_pages: totalPages,
          stats: stats
            ? {
                present: Number(stats.present ?? 0),
                absent:  Number(stats.absent  ?? 0),
                late:    Number(stats.late    ?? 0),
                total:   Number(stats.total   ?? 0),
                rate:    Number(stats.rate ?? stats.attendance_rate ?? 0),
              }
            : undefined,
        };
      }, this.retryConfig);
    } catch (err) {
          console.error('[getAdminHistory] Scoped history fetch failed:', err);
          return { records: [], total: 0, page: 1, total_pages: 1 };
    }
  }

      async getTeacherAvailablePeriods(date?: string): Promise<PeriodInfo[]> {
        try {
          return await withRetry(async () => {
            const response = await apiClient.get('/api/v1/teacher/available-periods', {
              params: {
                ...(date ? { date } : {}),
              },
            });
            const payload = response.data as Record<string, unknown>;
            const rows = toArray<Record<string, unknown>>(payload.available_periods ?? payload.periods ?? []);
            return rows.map((p) => ({
              period_id: String(p.period_id ?? p.id ?? ''),
              start_time: String(p.start_time ?? ''),
              end_time: String(p.end_time ?? ''),
              course_code: String(p.course_code ?? ''),
              course_name: String(p.course_name ?? ''),
              class_id: String(p.class_id ?? p.section_id ?? ''),
              day_of_week: p.day_of_week ? String(p.day_of_week) : undefined,
              faculty_name: p.faculty_name ? String(p.faculty_name) : undefined,
              room: p.room ? String(p.room) : undefined,
              is_lab_class: Boolean(p.is_lab_class ?? false),
              course_color: p.course_color ? String(p.course_color) : undefined,
            }));
          }, this.retryConfig);
        } catch (err) {
          console.error('[getTeacherAvailablePeriods] Error:', err);
          return [];
        }
      }

  /**
   * Returns the list of classes/sections visible to the current user.
   * Admin sees all; teacher sees only their assigned classes.
   */
  async getClasses(): Promise<ClassInfo[]> {
    try {
      return await withRetry(async () => {
        const role = getStoredRole();
        let response;

        if (role === 'teacher') {
          response = await apiClient.get('/api/v1/timetable/classes');
        } else {
          response = await apiClient.get('/api/v1/admin/classes');
          if (response.status === 404 || response.status === 403) {
            response = await apiClient.get('/api/v1/timetable/classes');
          }
        }
        return toArray<Record<string, unknown>>(response.data).map((c) => ({
          class_id: String(c.class_id ?? c.id ?? ''),
          class_name: String(c.class_name ?? c.name ?? ''),
          section: c.section ? String(c.section) : undefined,
          semester: c.semester ? String(c.semester) : undefined,
          department: c.department ? String(c.department) : undefined,
        }));
      }, this.retryConfig);
    } catch (err) {
      console.error('[getClasses] Error:', err);
      return [];
    }
  }

  /**
   * Returns timetable periods for a given class, optionally filtered
   * to a specific date (returns only periods scheduled on that day of week).
   */
  async getPeriodsByClass(classId: string, date?: string): Promise<PeriodInfo[]> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/timetable/periods', {
          params: { class_id: classId, ...(date ? { date } : {}) },
        });
        return toArray<Record<string, unknown>>(response.data).map((p) => ({
          period_id: String(p.period_id ?? p.id ?? ''),
          start_time: String(p.start_time ?? ''),
          end_time: String(p.end_time ?? ''),
          course_code: String(p.course_code ?? ''),
          course_name: String(p.course_name ?? ''),
          class_id: String(p.class_id ?? classId),
          day_of_week: p.day_of_week ? String(p.day_of_week) : undefined,
        }));
      }, this.retryConfig);
    } catch (err) {
      console.error('[getPeriodsByClass] Error:', err);
      return [];
    }
  }

  // ── Admin Helpers ───────────────────────────────────────────────────────────

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

  async getAdminAnalyticsOverview(): Promise<Record<string, unknown>> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/admin/analytics/overview');
        return response.data as Record<string, unknown>;
      }, this.retryConfig);
    } catch (err) {
      console.error('[getAdminAnalyticsOverview] Error:', err);
      return {};
    }
  }

  async getTeacherDashboard(facultyId: string, date?: string): Promise<Record<string, unknown>> {
    try {
      return await withRetry(async () => {
        const response = await apiClient.get('/api/v1/teacher/dashboard', {
          params: {
            faculty_id: facultyId,
            ...(date ? { date } : {}),
          },
        });
        return response.data as Record<string, unknown>;
      }, this.retryConfig);
    } catch (err) {
      console.error('[getTeacherDashboard] Error:', err);
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

  async updateStudent(
    studentId: string, name: string, email: string, courses: string[]
  ): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.put(`/api/v1/admin/students/${studentId}`, {
        name, email, courses,
      });
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
        const response = await apiClient.get('/api/v1/admin/courses', {
          params: { page, limit },
        });
        return toArray(response.data);
      }, this.retryConfig);
    } catch (err) {
      console.error('[getAllCourses] Error:', err);
      return [];
    }
  }

  async createCourse(
    name: string, code: string, schedule: string, room: string
  ): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.post('/api/v1/admin/courses', { name, code, schedule, room });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  async updateCourse(
    courseId: string, name: string, code: string, schedule: string, room: string
  ): Promise<unknown> {
    return withRetry(async () => {
      const response = await apiClient.put(`/api/v1/admin/courses/${courseId}`, {
        name, code, schedule, room,
      });
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

  // ── Analytics ───────────────────────────────────────────────────────────────

  /**
   * Period-scoped attendance records for the analytics page.
   * Queries by course_code + day (day of week), unlike `getPeriodAttendance`
   * which queries by period_id + class_id.
   *
   * GET /api/v1/attendance/period
   * Query: course_code, day, date (ISO YYYY-MM-DD), limit
   */
  async getAnalyticsPeriodAttendance(
    courseCode: string,
    day: string,
    date?: string,
    limit = 100,
  ): Promise<AnalyticsPeriodResponse> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.get('/api/v1/attendance/period', {
            params: {
              course_code: courseCode,
              day,
              ...(date ? { date } : {}),
              limit,
            },
          });
          return response.data;
        },
        this.retryConfig,
      );
    } catch (err) {
      console.error('[getAnalyticsPeriodAttendance] Error:', err);
      return {
        records: [],
        summary: { present: 0, absent: 0, late: 0, not_marked: 0, total: 0 },
        period: { course_code: courseCode, day, date: date ?? '' },
      };
    }
  }

  /**
   * Per-course 7-session attendance trend for sparkline charts.
   *
   * GET /api/v1/attendance/trend
   * Query: course_code, day, sessions (default 7)
   */
  async getCourseTrend(
    courseCode: string,
    day: string,
    sessions = 7,
  ): Promise<Array<{ date: string; percentage: number }>> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.get('/api/v1/attendance/trend', {
            params: { course_code: courseCode, day, sessions },
          });
          const data = response.data;
          if (Array.isArray(data)) return data;
          if (Array.isArray(data?.trend)) return data.trend;
          return [];
        },
        this.retryConfig,
      );
    } catch (err) {
      console.error('[getCourseTrend] Error:', err);
      return [];
    }
  }

  /**
   * Mark attendance for one student in a period (admin / manual override).
   *
   * POST /api/v1/attendance/period/mark
   * Body: { student_id, course_code, day, status, method, date? }
   */
  async markPeriodAttendance(params: {
    studentId: string;
    courseCode: string;
    day: string;
    status: 'present' | 'absent' | 'late';
    method?: string;
    date?: string;
  }): Promise<{ success: boolean; record_id: string; message: string }> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post('/api/v1/attendance/period/mark', {
            student_id: params.studentId,
            course_code: params.courseCode,
            day: params.day,
            status: params.status,
            method: params.method ?? 'Manual',
            ...(params.date ? { date: params.date } : {}),
          });
          const data = response.data;
          publishAttendanceUpdated();
          return data;
        },
        { ...this.retryConfig, maxRetries: 3 },
      );
    } catch (err) {
      console.error('[markPeriodAttendance] Error:', err);
      throw err;
    }
  }

  /**
   * Bulk-update all student statuses for a period in a single request.
   *
   * POST /api/v1/attendance/period/bulk
   * Body: { course_code, day, date?, entries: [{student_id, status}] }
   */
  async bulkMarkPeriod(params: {
    courseCode: string;
    day: string;
    date?: string;
    entries: Array<{ studentId: string; status: 'present' | 'absent' | 'late' }>;
  }): Promise<{ success: number; failed: number; errors?: string[] }> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post('/api/v1/attendance/period/bulk', {
            course_code: params.courseCode,
            day: params.day,
            ...(params.date ? { date: params.date } : {}),
            entries: params.entries.map((e) => ({
              student_id: e.studentId,
              status: e.status,
            })),
          });
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 2 },
      );
    } catch (err) {
      console.error('[bulkMarkPeriod] Error:', err);
      throw err;
    }
  }

  /**
   * Section-wide attendance summary — all courses for one day.
   *
   * GET /api/v1/attendance/section-summary
   * Query: section (e.g. "C"), date (ISO)
   */
  async getSectionSummary(
    section: string,
    date?: string,
  ): Promise<AnalyticsSectionSummaryItem[]> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.get('/api/v1/attendance/section-summary', {
            params: {
              section,
              ...(date ? { date } : {}),
            },
          });
          const data = response.data;
          return Array.isArray(data)         ? data
               : Array.isArray(data?.items)  ? data.items
               : [];
        },
        this.retryConfig,
      );
    } catch (err) {
      console.error('[getSectionSummary] Error:', err);
      return [];
    }
  }

  /**
   * Export full period attendance as a server-generated CSV blob.
   *
   * GET /api/v1/attendance/export/period
   */
  async exportPeriodCSV(
    courseCode: string,
    day: string,
    date?: string,
  ): Promise<Blob> {
    const response = await apiClient.get('/api/v1/attendance/export/period', {
      params: { course_code: courseCode, day, ...(date ? { date } : {}) },
      responseType: 'blob',
    });
    return response.data as Blob;
  }

  // ── Face Registration ───────────────────────────────────────────────────────

  async registerStudentFace(
    studentId: string, faceImageBase64: string
  ): Promise<unknown> {
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
      const response = await apiClient.post('/api/v1/qr/scan', {
        token, student_id: studentId,
      });
      return response.data;
    }, { ...this.retryConfig, maxRetries: 3 });
  }

  // ── Health Check ─────────────────────────────────────────────────────────────

  /**
   * Calls the health endpoint via plain fetch so it is never intercepted by
   * the auth layer — health checks must work even when logged out.
   */
  async healthCheck(): Promise<boolean> {
    try {
      const baseUrl = (
        import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
      ).replace(/\/$/, '');
      const res = await fetch(`${baseUrl}/api/v1/attendance/health`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal: AbortSignal.timeout(5_000),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  /**
   * Polls the health endpoint until it responds or `maxAttempts` is reached.
   * Resolves silently rather than throwing — the app proceeds and surfaces
   * errors in normal API calls.
   */
  async waitForBackend(maxAttempts = 30): Promise<void> {
    for (let i = 1; i <= maxAttempts; i++) {
      const ok = await this.healthCheck();
      if (ok) {
        console.log(`[API] Backend healthy (attempt ${i})`);
        return;
      }
      if (i < maxAttempts) {
        const delay = Math.min(1_000 * Math.pow(1.4, i - 1), 5_000);
        await new Promise((r) => setTimeout(r, delay));
      }
    }
    console.warn('[API] Backend did not become healthy; proceeding anyway.');
  }
}

export const attendanceAPI = new AttendanceAPI();
export const timetableAPI = {
  async getTodayPeriods(classId: string): Promise<PeriodInfo[]> {
    const periods = await attendanceAPI.getTeacherAvailablePeriods(new Date().toISOString().slice(0, 10));
    return periods.filter((p) => p.class_id === classId);
  },
};
export default apiClient;