/// <reference types="vite/client" />

import axios, { AxiosError, AxiosInstance } from 'axios';

const apiClient: AxiosInstance = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, ''),
  timeout: parseInt(import.meta.env.VITE_API_TIMEOUT || '15000'),
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Auth token injection
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 401 handler
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
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

// ── Detect-face response ──────────────────────────────────────────────────────
export interface DetectFaceResponse {
  matched: boolean;
  message: string;
  student_name?: string;
  student_id?: string;
  confidence?: number;
  record_id?: string;
  timestamp?: string;
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

// ── API class ──────────────────────────────────────────────────────────────────

class AttendanceAPI {
  async getLiveAttendance(courseId?: string, limit = 50): Promise<AttendanceRecord[]> {
    try {
      const response = await apiClient.get('/api/v1/attendance/attendance', {
        params: { ...(courseId ? { student_id: courseId } : {}), limit },
      });
      return toArray<Record<string, unknown>>(response.data).map(normaliseRecord);
    } catch {
      return [];
    }
  }

  async getAttendanceStats(courseId?: string, date?: string): Promise<AttendanceStats> {
    try {
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
    } catch {
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
    } catch {
      return [];
    }
  }

  async getAttendanceSummary(
    courseId?: string,
    startDate?: string,
    endDate?: string
  ): Promise<Record<string, number>> {
    try {
      const response = await apiClient.get('/api/v1/attendance/attendance/daily-report', {
        params: { ...(startDate ? { date: startDate } : {}) },
      });
      const d = response.data as Record<string, unknown>;
      return {
        total_records: Number(d.total_records ?? 0),
        unique_students: Number(d.unique_students ?? 0),
      };
    } catch {
      return {};
    }
  }

  async getStudents(courseId?: string): Promise<Student[]> {
    try {
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
    } catch {
      return [];
    }
  }

  async getCourses(): Promise<Course[]> {
    try {
      const response = await apiClient.get('/api/v1/courses');
      return toArray<Record<string, unknown>>(response.data).map((c) => ({
        id: String(c.id ?? ''),
        code: String(c.code ?? ''),
        name: String(c.name ?? ''),
        instructor: String(c.instructor ?? c.teacher_name ?? ''),
        students_count: Number(c.students_count ?? c.total_students ?? 0),
      }));
    } catch {
      return [];
    }
  }

  /**
   * Detect face in uploaded image/frame and mark attendance.
   * Sends multipart/form-data POST to /api/v1/attendance/detect-face.
   * FormData MUST contain a field named "file" (JPEG/PNG Blob).
   *
   * Returns a DetectFaceResponse regardless of match outcome so callers can
   * surface both "matched" and "not matched" states to the user.
   */
  async detectAndMarkAttendance(formData: FormData): Promise<DetectFaceResponse> {
    try {
      const response = await apiClient.post<DetectFaceResponse>(
        '/api/v1/attendance/detect-face',
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 25000, // face recognition can be slow on first load
        }
      );
      return response.data;
    } catch (err: unknown) {
      const axiosErr = err as AxiosError<{ detail?: string; message?: string }>;
      const status = axiosErr.response?.status;
      const detail =
        axiosErr.response?.data?.detail ||
        axiosErr.response?.data?.message ||
        axiosErr.message ||
        'Unknown error';

      // 4xx from backend → face not recognised, no network issue
      if (status && status >= 400 && status < 500) {
        return {
          matched: false,
          message: detail,
        };
      }

      // Network / 5xx → propagate as structured error
      return {
        matched: false,
        message: `Server error (${status ?? 'network'}): ${detail}. Check backend logs.`,
      };
    }
  }

  // NOTE: _detectViaBase64 / mark-mobile fallback intentionally removed.
  // Sending large base64 blobs as URL query parameters causes 414 Request-URI
  // Too Long errors, leaks image data in server logs, and breaks URL length
  // limits in proxies. Use the multipart detect-face endpoint exclusively.

  async registerStudentFace(studentId: string, faceImageBase64: string) {
    const response = await apiClient.post('/api/v1/admin/register-face', {
      student_id: studentId,
      face_image_base64: faceImageBase64,
    });
    return response.data;
  }

  async generateQRCode() {
    const response = await apiClient.post('/api/v1/qr/generate', {});
    return response.data;
  }

  async validateQRToken(token: string) {
    const response = await apiClient.get(`/api/v1/qr/validate/${token}`);
    return response.data;
  }

  async scanQRCode(token: string, studentId: string) {
    const response = await apiClient.post('/api/v1/qr/scan', { token, student_id: studentId });
    return response.data;
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await apiClient.get('/api/v1/attendance/health');
      return response.status === 200;
    } catch {
      return false;
    }
  }

  // ── Admin helpers ──────────────────────────────────────────────────────────

  async getAllStudents(page = 1, limit = 50) {
    const response = await apiClient.get('/api/v1/attendance/students', {
      params: { limit, offset: (page - 1) * limit },
    });
    return toArray(response.data);
  }

  async createStudent(name: string, email: string, courses: string[]) {
    const response = await apiClient.post('/api/v1/admin/students', { name, email, courses });
    return response.data;
  }

  async updateStudent(studentId: string, name: string, email: string, courses: string[]) {
    const response = await apiClient.put(`/api/v1/admin/students/${studentId}`, { name, email, courses });
    return response.data;
  }

  async deleteStudent(studentId: string) {
    const response = await apiClient.delete(`/api/v1/admin/students/${studentId}`);
    return response.data;
  }

  async batchImportStudents(students: unknown[]) {
    const response = await apiClient.post('/api/v1/admin/batch-import', { students });
    return response.data;
  }

  async getAllCourses(page = 1, limit = 50) {
    const response = await apiClient.get('/api/v1/admin/courses', { params: { page, limit } });
    return toArray(response.data);
  }

  async createCourse(name: string, code: string, schedule: string, room: string) {
    const response = await apiClient.post('/api/v1/admin/courses', { name, code, schedule, room });
    return response.data;
  }

  async updateCourse(courseId: string, name: string, code: string, schedule: string, room: string) {
    const response = await apiClient.put(`/api/v1/admin/courses/${courseId}`, { name, code, schedule, room });
    return response.data;
  }

  async toggleCourse(courseId: string, active: boolean) {
    const response = await apiClient.patch(`/api/v1/admin/courses/${courseId}`, { active });
    return response.data;
  }

  async deleteCourse(courseId: string) {
    const response = await apiClient.delete(`/api/v1/admin/courses/${courseId}`);
    return response.data;
  }
}

export const attendanceAPI = new AttendanceAPI();
export default apiClient;
