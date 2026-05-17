import { apiClient } from './api';
import type {
  AttendanceMatrixResponse,
  AttendanceRoleSummaryResponse,
} from '../types/analytics';

export interface AttendanceMatrixQuery {
  classId?: string;
  weekStart?: string;
}

export const dashboardService = {
  async getAttendanceMatrix(query: AttendanceMatrixQuery = {}): Promise<AttendanceMatrixResponse> {
    const response = await apiClient.get('/api/v1/admin/analytics/matrix', {
      params: {
        ...(query.classId ? { class_id: query.classId } : {}),
        ...(query.weekStart ? { week_start: query.weekStart } : {}),
      },
    });
    return response.data as AttendanceMatrixResponse;
  },

  async getRoleSummary(): Promise<AttendanceRoleSummaryResponse> {
    const response = await apiClient.get('/api/v1/admin/analytics/role-summary');
    return response.data as AttendanceRoleSummaryResponse;
  },
};

export default dashboardService;
