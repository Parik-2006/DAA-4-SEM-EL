/// <reference types="vite/client" />

import axios, { AxiosError, AxiosInstance } from 'axios';

const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: parseInt(import.meta.env.VITE_API_TIMEOUT || '15000'),
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// Add request interceptor for authentication
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Add response interceptor for error handling
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

class AttendanceAPI {
  // Live Attendance
  async getLiveAttendance(courseId?: string, limit = 50) {
    const response = await apiClient.get<AttendanceRecord[]>('/api/v1/attendance/live', {
      params: { course_id: courseId, limit },
    });
    return response.data;
  }

  // Statistics
  async getAttendanceStats(courseId?: string, date?: string) {
    const response = await apiClient.get<AttendanceStats>('/api/v1/attendance/stats', {
      params: { course_id: courseId, date },
    });
    return response.data;
  }

  // History
  async getAttendanceHistory(
    courseId?: string,
    startDate?: string,
    endDate?: string,
    page = 1,
    limit = 30
  ) {
    const response = await apiClient.get<AttendanceRecord[]>('/api/v1/attendance/history', {
      params: {
        course_id: courseId,
        start_date: startDate,
        end_date: endDate,
        page,
        limit,
      },
    });
    return response.data;
  }

  // Summary
  async getAttendanceSummary(courseId?: string, startDate?: string, endDate?: string) {
    const response = await apiClient.get<Record<string, number>>('/api/v1/attendance/summary', {
      params: {
        course_id: courseId,
        start_date: startDate,
        end_date: endDate,
      },
    });
    return response.data;
  }

  // Students
  async getStudents(courseId?: string) {
    const response = await apiClient.get<Student[]>('/api/v1/students', {
      params: { course_id: courseId },
    });
    return response.data;
  }

  // Courses
  async getCourses() {
    const response = await apiClient.get<Course[]>('/api/v1/courses');
    return response.data;
  }

  // Detect and mark attendance
  async detectAndMarkAttendance(formData: FormData) {
    const response = await apiClient.post<{
      matched: boolean;
      message: string;
      student_name?: string;
      student_id?: string;
      confidence?: number;
    }>('/api/v1/attendance/detect', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  // Face Registration
  async registerStudentFace(studentId: string, faceImageBase64: string) {
    const response = await apiClient.post('/api/v1/admin/register-face', {
      student_id: studentId,
      face_image_base64: faceImageBase64,
    });
    return response.data;
  }

  // QR Code Attendance
  async generateQRCode() {
    const response = await apiClient.post('/api/v1/qr/generate', {});
    return response.data;
  }

  async validateQRToken(token: string) {
    const response = await apiClient.get(`/api/v1/qr/validate/${token}`);
    return response.data;
  }

  async scanQRCode(token: string, studentId: string) {
    const response = await apiClient.post('/api/v1/qr/scan', {
      token,
      student_id: studentId,
    });
    return response.data;
  }

  async getQRStatistics() {
    const response = await apiClient.get('/api/v1/qr/stats');
    return response.data;
  }

  // Student Management
  async getAllStudents(page = 1, limit = 50) {
    const response = await apiClient.get('/api/v1/admin/students', {
      params: { page, limit },
    });
    return response.data;
  }

  async getStudent(studentId: string) {
    const response = await apiClient.get(`/api/v1/admin/students/${studentId}`);
    return response.data;
  }

  async createStudent(name: string, email: string, courses: string[]) {
    const response = await apiClient.post('/api/v1/admin/students', {
      name,
      email,
      courses,
    });
    return response.data;
  }

  async updateStudent(studentId: string, name: string, email: string, courses: string[]) {
    const response = await apiClient.put(`/api/v1/admin/students/${studentId}`, {
      name,
      email,
      courses,
    });
    return response.data;
  }

  async deleteStudent(studentId: string) {
    const response = await apiClient.delete(`/api/v1/admin/students/${studentId}`);
    return response.data;
  }

  async batchImportStudents(students: any[]) {
    const response = await apiClient.post('/api/v1/admin/batch-import', {
      students,
    });
    return response.data;
  }

  // Course Management
  async getAllCourses(page = 1, limit = 50) {
    const response = await apiClient.get('/api/v1/admin/courses', {
      params: { page, limit },
    });
    return response.data;
  }

  async getCourseById(courseId: string) {
    const response = await apiClient.get(`/api/v1/admin/courses/${courseId}`);
    return response.data;
  }

  async createCourse(name: string, code: string, schedule: string, room: string) {
    const response = await apiClient.post('/api/v1/admin/courses', {
      name,
      code,
      schedule,
      room,
    });
    return response.data;
  }

  async updateCourse(courseId: string, name: string, code: string, schedule: string, room: string) {
    const response = await apiClient.put(`/api/v1/admin/courses/${courseId}`, {
      name,
      code,
      schedule,
      room,
    });
    return response.data;
  }

  async toggleCourse(courseId: string, active: boolean) {
    const response = await apiClient.patch(`/api/v1/admin/courses/${courseId}`, {
      active,
    });
    return response.data;
  }

  async deleteCourse(courseId: string) {
    const response = await apiClient.delete(`/api/v1/admin/courses/${courseId}`);
    return response.data;
  }

  async getEnrolledStudents(courseId: string) {
    const response = await apiClient.get(`/api/v1/admin/courses/${courseId}/enrolled-students`);
    return response.data;
  }

  async enrollStudent(courseId: string, studentId: string) {
    const response = await apiClient.post(`/api/v1/admin/courses/${courseId}/enroll/${studentId}`, {});
    return response.data;
  }

  async unenrollStudent(courseId: string, studentId: string) {
    const response = await apiClient.delete(`/api/v1/admin/courses/${courseId}/unenroll/${studentId}`);
    return response.data;
  }

  // Health check
  async healthCheck() {
    try {
      const response = await apiClient.get('/api/v1/health');
      return response.status === 200;
    } catch {
      return false;
    }
  }
}

export const attendanceAPI = new AttendanceAPI();
export default apiClient;
