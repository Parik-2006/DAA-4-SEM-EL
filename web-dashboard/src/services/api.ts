/// <reference types="vite/client" />

import axios, { AxiosError, AxiosInstance } from 'axios';
import { 
  withRetry, 
  waitForHealthy, 
  isRetryableError,
  RetryConfig 
} from '../utils/retry-handler';

const apiClient: AxiosInstance = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, ''),
  timeout: parseInt(import.meta.env.VITE_API_TIMEOUT || '15000'),
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Track retry attempts
let retryAttemptCount = 0;

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  console.log(`[API Request] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
  return config;
});

apiClient.interceptors.response.use(
  (response) => {
    retryAttemptCount = 0;
    console.log(`[API Response] ${response.status} ${response.config.url}`);
    return response;
  },
  (error: AxiosError) => {
    const status = error.response?.status;
    const message = 
      error.response?.data?.detail || 
      error.response?.data?.message || 
      error.message || 
      'Unknown error';

    console.error(`[API Error] ${status || 'Network'} - ${error.config?.url}: ${message}`);

    // Handle authentication errors
    if (status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
      return Promise.reject(error);
    }

    // Handle client errors (4xx) - don't retry except for specific cases
    if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) {
      console.error(`[API] Client error ${status} - not retrying:`, message);
      return Promise.reject(error);
    }

    // Retryable errors
    if (isRetryableError(error)) {
      retryAttemptCount++;
      console.warn(`[API] Retryable error detected. Attempt: ${retryAttemptCount}`);
    }

    return Promise.reject(error);
  }
);

// ── Types ──────────────────────────────────────────────────────────────────────

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

/**
 * Response from the detect-face-only endpoint (Step 1).
 * No attendance record has been saved yet.
 */
export interface DetectFaceResponse {
  matched: boolean;
  message: string;
  student_name?: string;
  student_id?: string;
  confidence?: number;
  record_id?: string;
  timestamp?: string;
}

/**
 * Response from the confirm-attendance endpoint (Step 2).
 * The attendance record has been persisted to the database.
 */
export interface ConfirmAttendanceResponse {
  success: boolean;
  record_id: string;
  student_id: string;
  student_name: string;
  confidence: number;
  timestamp: string;
  message: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function toArray<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    for (const key of ['records', 'students', 'courses', 'data', 'items']) {
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
    return { matched: false, message: detail };
  }

  if (isRetryableError(err)) {
    return {
      matched: false,
      message: `Backend is starting up. Please wait a moment and try again.`,
    };
  }

  return {
    matched: false,
    message: `Server error (${status ?? 'network'}): ${detail}. Check backend logs.`,
  };
}

// ── API class ──────────────────────────────────────────────────────────────────

class AttendanceAPI {
  private retryConfig: RetryConfig = {
    maxRetries: 5,
    initialDelayMs: 500,
    maxDelayMs: 10000,
    backoffMultiplier: 2,
    retryableStatusCodes: [408, 429, 500, 502, 503, 504],
    onRetry: (attempt, error, delayMs) => {
      console.warn(
        `[AttendanceAPI] Retry attempt ${attempt} in ${delayMs}ms`,
        error.message
      );
    },
  };

  // ── Two-step attendance flow ──────────────────────────────────────────────

  /**
   * Step 1 — Detect and identify a face WITHOUT saving to the database.
   *
   * Sends a multipart/form-data POST to `/detect-face-only`.
   * The FormData must have a field named "file" (JPEG/PNG Blob).
   *
   * Returns a DetectFaceResponse. If matched, the caller should display a
   * confirmation dialog and then call `confirmAttendance()` on approval.
   */
  async detectFaceOnly(formData: FormData): Promise<DetectFaceResponse> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post<DetectFaceResponse>(
            '/api/v1/attendance/detect-face-only',
            formData,
            {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 25000,
            }
          );
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err: unknown) {
      console.error('[detectFaceOnly] Failed after retries:', err);
      return buildDetectError(err);
    }
  }

  /**
   * Step 2 — Persist the attendance record after the user has confirmed identity.
   *
   * Sends a JSON POST to `/confirm-attendance` with the student_id and
   * confidence score returned from `detectFaceOnly`.
   *
   * Call this ONLY after the user clicks "Yes" in the confirmation dialog.
   */
  async confirmAttendance(
    studentId: string,
    confidence: number
  ): Promise<ConfirmAttendanceResponse> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post<ConfirmAttendanceResponse>(
            '/api/v1/attendance/confirm-attendance',
            { student_id: studentId, confidence },
            { timeout: 15000 }
          );
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err: unknown) {
      console.error('[confirmAttendance] Failed after retries:', err);
      throw err;
    }
  }

  // ── Legacy single-step (used by UploadPhoto fallback) ────────────────────

  /**
   * @deprecated Use detectFaceOnly + confirmAttendance for the two-step flow.
   * Kept for legacy integrations that call the old detect-face endpoint.
   */
  async detectAndMarkAttendance(formData: FormData): Promise<DetectFaceResponse> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post<DetectFaceResponse>(
            '/api/v1/attendance/detect-face',
            formData,
            {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 25000,
            }
          );
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err: unknown) {
      console.error('[detectAndMarkAttendance] Failed after retries:', err);
      return buildDetectError(err);
    }
  }

  // ── Data fetching ─────────────────────────────────────────────────────────

  async getLiveAttendance(courseId?: string, limit = 50): Promise<AttendanceRecord[]> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.get('/api/v1/attendance/attendance', {
            params: { ...(courseId ? { student_id: courseId } : {}), limit },
          });
          return toArray<Record<string, unknown>>(response.data).map(normaliseRecord);
        },
        this.retryConfig
      );
    } catch (err) {
      console.error('[getLiveAttendance] Error:', err);
      return [];
    }
  }

  async getAttendanceStats(courseId?: string, date?: string): Promise<AttendanceStats> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.get('/api/v1/attendance/stats', {
            params: { ...(courseId ? { course_id: courseId } : {}), ...(date ? { date } : {}) },
          });
          const d = response.data as Record<string, unknown>;
          return {
            total_present: Number(d.total_present ?? d.present_today ?? 0),
            total_late: Number(d.total_late ?? d.late_today ?? 0),
            total_absent: Number(d.total_absent ?? d.absent_today ?? 0),
            total_excused: Number(d.total_excused ?? 0),
            last_updated: String(d.last_updated ?? new Date().toISOString()),
          };
        },
        this.retryConfig
      );
    } catch (err) {
      console.error('[getAttendanceStats] Error:', err);
      return {
        total_present: 0,
        total_late: 0,
        total_absent: 0,
        total_excused: 0,
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
      return await withRetry(
        async () => {
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
        },
        this.retryConfig
      );
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
      return await withRetry(
        async () => {
          const response = await apiClient.get('/api/v1/attendance/attendance/daily-report', {
            params: { ...(startDate ? { date: startDate } : {}) },
          });
          const d = response.data as Record<string, unknown>;
          return {
            total_records: Number(d.total_records ?? 0),
            unique_students: Number(d.unique_students ?? 0),
          };
        },
        this.retryConfig
      );
    } catch (err) {
      console.error('[getAttendanceSummary] Error:', err);
      return {};
    }
  }

  async getStudents(courseId?: string): Promise<Student[]> {
    try {
      return await withRetry(
        async () => {
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
        },
        this.retryConfig
      );
    } catch (err) {
      console.error('[getStudents] Error:', err);
      return [];
    }
  }

  async getCourses(): Promise<Course[]> {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.get('/api/v1/courses');
          return toArray<Record<string, unknown>>(response.data).map((c) => ({
            id: String(c.id ?? ''),
            code: String(c.code ?? ''),
            name: String(c.name ?? ''),
            instructor: String(c.instructor ?? c.teacher_name ?? ''),
            students_count: Number(c.students_count ?? c.total_students ?? 0),
          }));
        },
        this.retryConfig
      );
    } catch (err) {
      console.error('[getCourses] Error:', err);
      return [];
    }
  }

  async registerStudentFace(studentId: string, faceImageBase64: string) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post('/api/v1/admin/register-face', {
            student_id: studentId,
            face_image_base64: faceImageBase64,
          });
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[registerStudentFace] Error:', err);
      throw err;
    }
  }

  async generateQRCode() {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post('/api/v1/qr/generate', {});
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[generateQRCode] Error:', err);
      throw err;
    }
  }

  async validateQRToken(token: string) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.get(`/api/v1/qr/validate/${token}`);
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[validateQRToken] Error:', err);
      throw err;
    }
  }

  async scanQRCode(token: string, studentId: string) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post('/api/v1/qr/scan', {
            token,
            student_id: studentId,
          });
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[scanQRCode] Error:', err);
      throw err;
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await apiClient.get('/api/v1/attendance/health');
      return response.status === 200;
    } catch (err) {
      console.warn('[healthCheck] Backend not ready:', err);
      return false;
    }
  }

  /**
   * Wait for backend to be healthy before proceeding
   * Useful for initialization/startup
   */
  async waitForBackend(maxRetries = 30): Promise<void> {
    console.log('[AttendanceAPI] Waiting for backend to be healthy...');
    await waitForHealthy(
      () => this.healthCheck(),
      {
        maxRetries,
        initialDelayMs: 1000,
        maxDelayMs: 5000,
        backoffMultiplier: 1.5,
      }
    );
  }

  // ── Admin helpers ──────────────────────────────────────────────────────────

  async getAllStudents(page = 1, limit = 50) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.get('/api/v1/attendance/students', {
            params: { limit, offset: (page - 1) * limit },
          });
          return toArray(response.data);
        },
        this.retryConfig
      );
    } catch (err) {
      console.error('[getAllStudents] Error:', err);
      return [];
    }
  }

  async createStudent(name: string, email: string, courses: string[]) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post('/api/v1/admin/students', {
            name,
            email,
            courses,
          });
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[createStudent] Error:', err);
      throw err;
    }
  }

  async updateStudent(studentId: string, name: string, email: string, courses: string[]) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.put(`/api/v1/admin/students/${studentId}`, {
            name,
            email,
            courses,
          });
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[updateStudent] Error:', err);
      throw err;
    }
  }

  async deleteStudent(studentId: string) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.delete(`/api/v1/admin/students/${studentId}`);
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[deleteStudent] Error:', err);
      throw err;
    }
  }

  async batchImportStudents(students: unknown[]) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post('/api/v1/admin/batch-import', { students });
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 2 }
      );
    } catch (err) {
      console.error('[batchImportStudents] Error:', err);
      throw err;
    }
  }

  async getAllCourses(page = 1, limit = 50) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.get('/api/v1/admin/courses', { params: { page, limit } });
          return toArray(response.data);
        },
        this.retryConfig
      );
    } catch (err) {
      console.error('[getAllCourses] Error:', err);
      return [];
    }
  }

  async createCourse(name: string, code: string, schedule: string, room: string) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.post('/api/v1/admin/courses', {
            name,
            code,
            schedule,
            room,
          });
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[createCourse] Error:', err);
      throw err;
    }
  }

  async updateCourse(courseId: string, name: string, code: string, schedule: string, room: string) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.put(`/api/v1/admin/courses/${courseId}`, {
            name,
            code,
            schedule,
            room,
          });
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[updateCourse] Error:', err);
      throw err;
    }
  }

  async toggleCourse(courseId: string, active: boolean) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.patch(`/api/v1/admin/courses/${courseId}`, {
            active,
          });
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[toggleCourse] Error:', err);
      throw err;
    }
  }

  async deleteCourse(courseId: string) {
    try {
      return await withRetry(
        async () => {
          const response = await apiClient.delete(`/api/v1/admin/courses/${courseId}`);
          return response.data;
        },
        { ...this.retryConfig, maxRetries: 3 }
      );
    } catch (err) {
      console.error('[deleteCourse] Error:', err);
      throw err;
    }
  }
}

export const attendanceAPI = new AttendanceAPI();
export default apiClient;
