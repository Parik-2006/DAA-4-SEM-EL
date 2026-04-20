import axios, { AxiosInstance, AxiosError } from 'axios';
import { FirebaseAuthService } from './firebase/auth.service';

export class ApiClient {
  private static instance: ApiClient;
  private axiosInstance: AxiosInstance;
  private authService: FirebaseAuthService;

  private constructor() {
    this.authService = FirebaseAuthService.getInstance();
    this.axiosInstance = axios.create({
      baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
      timeout: 10000,
    });

    this.setupInterceptors();
  }

  static getInstance(): ApiClient {
    if (!ApiClient.instance) {
      ApiClient.instance = new ApiClient();
    }
    return ApiClient.instance;
  }

  private setupInterceptors(): void {
    // Request interceptor
    this.axiosInstance.interceptors.request.use(
      async (config) => {
        const token = await this.authService.getIdToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.axiosInstance.interceptors.response.use(
      (response) => {
        console.log(`[API] Response: ${response.status}`);
        return response;
      },
      (error: AxiosError) => {
        console.log(`[API] Error: ${error.message}`);
        return Promise.reject(error);
      }
    );
  }

  async healthCheck(): Promise<any> {
    try {
      const response = await this.axiosInstance.get('/health');
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async getStudents(): Promise<any[]> {
    try {
      const response = await this.axiosInstance.get('/api/students');
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async getCourses(): Promise<any[]> {
    try {
      const response = await this.axiosInstance.get('/api/courses');
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async recordAttendance(
    studentId: string,
    courseId: string,
    isPresent: boolean,
    photoUrl?: string
  ): Promise<any> {
    try {
      const response = await this.axiosInstance.post('/api/attendance/record', {
        student_id: studentId,
        course_id: courseId,
        is_present: isPresent,
        photo_url: photoUrl,
        timestamp: new Date().toISOString(),
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async getStatistics(courseId: string): Promise<any> {
    try {
      const response = await this.axiosInstance.get(
        `/api/statistics/${courseId}`
      );
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async uploadFile(file: File, uploadPath: string): Promise<string> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('path', uploadPath);

      const response = await this.axiosInstance.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      return response.data.url;
    } catch (error) {
      throw error;
    }
  }
}
