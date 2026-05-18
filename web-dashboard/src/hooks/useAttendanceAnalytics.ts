/**
 * hooks/useAttendanceAnalytics.ts
 * ────────────────────────────────────────────────────────────────────────────
 * Prompt 5: Privacy-aware analytics hooks with role-gated data access.
 *
 * Each hook enforces its role locally (defense-in-depth) even though the
 * server validates on every request. Hooks must NEVER accept role as a prop —
 * role is read from the JWT context only.
 *
 * - useStudentAnalytics: Own attendance trend + overall + streaks (student only)
 * - useTeacherAnalytics: Section breakdown for assigned classes (teacher only)
 * - useAdminAnalytics: Institution-wide overview + trends + drill-down (admin only)
 * - useAdminStudentDrillDown: Admin-only drill-down for any student (admin only)
 */

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../services/api';
import { getStoredRole } from '../utils/roles';

// ════════════════════════════════════════════════════════════════════════════
// Type definitions
// ════════════════════════════════════════════════════════════════════════════

export interface TrendPoint {
  date: string;
  present: number;
  late: number;
  absent: number;
  rate: number | null;
}

export interface OverallSummary {
  percentage: number;
  present: number;
  late: number;
  absent: number;
  total: number;
  band: 'safe' | 'warning' | 'danger';
  color: string;
}

export interface StudentAnalytics {
  student_id: string;
  days: number;
  trend: TrendPoint[];
  overall: OverallSummary;
  streak: {
    current_present_streak: number;
    longest_streak: number;
  };
  generated_at: string;
}

export interface SectionAnalytics {
  class_id: string;
  date: string;
  present: number;
  late: number;
  absent: number;
  not_marked: number;
  total_students: number;
  attendance_rate: number;
  band: 'safe' | 'warning' | 'danger';
  generated_at: string;
}

export interface TeacherTrendPoint {
  date: string;
  present: number;
  late: number;
  absent: number;
  total_marked: number;
  rate: number;
}

export interface AdminOverview {
  days: number;
  total_students: number;
  trend: TeacherTrendPoint[];
  generated_at: string;
}

export interface StudentDrillDownCourse {
  course_id: string;
  rate: number;
  present: number;
  late: number;
  absent: number;
}

export interface AdminStudentDrillDown {
  student_id: string;
  student_name: string;
  class_id: string;
  date_range: {
    start: string | null;
    end: string | null;
  };
  overall: OverallSummary;
  course_breakdown: StudentDrillDownCourse[];
  generated_at: string;
}

export interface UseDataState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

// ════════════════════════════════════════════════════════════════════════════
// useStudentAnalytics: Personal trend, overall, and streaks
// ════════════════════════════════════════════════════════════════════════════

interface UseStudentAnalyticsProps {
  days?: number;
  enabled?: boolean;
}

export const useStudentAnalytics = (
  props: UseStudentAnalyticsProps = {},
): UseDataState<StudentAnalytics> => {
  const { days = 30, enabled = true } = props;
  const role = getStoredRole();
  const userId = sessionStorage.getItem('user_id') ?? '';
  const [data, setData] = useState<StudentAnalytics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Local role gate: enforce at hook level (defense-in-depth)
  const isAuthorized = role === 'student' && userId;

  const fetchAnalytics = useCallback(async () => {
    if (!isAuthorized || !enabled) {
      setData(null);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.get<StudentAnalytics>(
        `/api/v1/student/analytics`,
        {
          params: {
            days: Math.max(7, Math.min(180, days)),
          },
        },
      );
      setData(response.data);
    } catch (err: any) {
      const message =
        err.response?.data?.detail ||
        err.message ||
        'Failed to fetch student analytics';
      setError(message);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthorized, enabled, days]);

  useEffect(() => {
    void fetchAnalytics();
  }, [fetchAnalytics]);

  return { data, isLoading, error, refetch: fetchAnalytics };
};

// ════════════════════════════════════════════════════════════════════════════
// useTeacherAnalytics: Section-scoped attendance breakdown
// ════════════════════════════════════════════════════════════════════════════

interface UseTeacherAnalyticsProps {
  classId: string;
  date?: string;
  enabled?: boolean;
}

export const useTeacherAnalytics = (
  props: UseTeacherAnalyticsProps,
): UseDataState<SectionAnalytics> => {
  const { classId, date, enabled = true } = props;
  const role = getStoredRole();
  const [data, setData] = useState<SectionAnalytics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Local role gate: enforce at hook level
  const isAuthorized = (role === 'teacher' || role === 'admin') && !!classId;

  const fetchAnalytics = useCallback(async () => {
    if (!isAuthorized || !enabled) {
      setData(null);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.get<SectionAnalytics>(
        `/api/v1/teacher/analytics/section`,
        {
          params: {
            class_id: classId,
            ...(date && { date }),
          },
        },
      );
      setData(response.data);
    } catch (err: any) {
      const message =
        err.response?.data?.detail ||
        err.message ||
        'Failed to fetch section analytics';
      setError(message);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthorized, enabled, classId, date]);

  useEffect(() => {
    void fetchAnalytics();
  }, [fetchAnalytics]);

  return { data, isLoading, error, refetch: fetchAnalytics };
};

// ════════════════════════════════════════════════════════════════════════════
// useAdminAnalytics: Institution-wide trends
// ════════════════════════════════════════════════════════════════════════════

interface UseAdminAnalyticsProps {
  trendDays?: number;
  enabled?: boolean;
}

export const useAdminAnalytics = (
  props: UseAdminAnalyticsProps = {},
): UseDataState<AdminOverview> => {
  const { trendDays = 7, enabled = true } = props;
  const role = getStoredRole();
  const [data, setData] = useState<AdminOverview | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Local role gate: admin only
  const isAuthorized = role === 'admin';

  const fetchAnalytics = useCallback(async () => {
    if (!isAuthorized || !enabled) {
      setData(null);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.get<AdminOverview>(
        `/api/v1/admin/analytics/trends`,
        {
          params: {
            days: Math.max(2, Math.min(90, trendDays)),
          },
        },
      );
      setData(response.data);
    } catch (err: any) {
      const message =
        err.response?.data?.detail ||
        err.message ||
        'Failed to fetch admin analytics';
      setError(message);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthorized, enabled, trendDays]);

  useEffect(() => {
    void fetchAnalytics();
  }, [fetchAnalytics]);

  return { data, isLoading, error, refetch: fetchAnalytics };
};

// ════════════════════════════════════════════════════════════════════════════
// useAdminStudentDrillDown: Admin drill-down for any student
// ════════════════════════════════════════════════════════════════════════════

interface UseAdminStudentDrillDownProps {
  startDate?: string;
  endDate?: string;
  enabled?: boolean;
}

export const useAdminStudentDrillDown = (
  studentId: string | null | undefined,
  props: UseAdminStudentDrillDownProps = {},
): UseDataState<AdminStudentDrillDown> => {
  const { startDate, endDate, enabled = true } = props;
  const role = getStoredRole();
  const [data, setData] = useState<AdminStudentDrillDown | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Local role gate: admin only
  const isAuthorized = role === 'admin' && !!studentId;

  const fetchAnalytics = useCallback(async () => {
    if (!isAuthorized || !enabled) {
      setData(null);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.get<AdminStudentDrillDown>(
        `/api/v1/admin/analytics/student/${studentId}`,
        {
          params: {
            ...(startDate && { start_date: startDate }),
            ...(endDate && { end_date: endDate }),
          },
        },
      );
      setData(response.data);
    } catch (err: any) {
      const message =
        err.response?.data?.detail ||
        err.message ||
        'Failed to fetch student drill-down';
      setError(message);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthorized, enabled, studentId, startDate, endDate]);

  useEffect(() => {
    void fetchAnalytics();
  }, [fetchAnalytics]);

  return { data, isLoading, error, refetch: fetchAnalytics };
};
