import React, { useEffect, useMemo, useState } from 'react';

import { Layout } from '../components';
import { DashboardPage } from './DashboardPage';
import { TeacherDashboard, type TeacherPeriod } from './TeacherDashboard';
import { attendanceAPI } from '../services/api';
import { getStoredRole } from '../utils/roles';

function toStringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function toNumberValue(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() && !Number.isNaN(Number(value))) return Number(value);
  return undefined;
}

function normalizeTeacherPeriods(schedule: unknown[]): TeacherPeriod[] {
  return schedule.map((item, index) => {
    const period = (item && typeof item === 'object') ? item as Record<string, unknown> : {};
    const attendanceCounts = (period.attendance_counts && typeof period.attendance_counts === 'object')
      ? period.attendance_counts as Record<string, unknown>
      : {};

    return {
      period_id: toStringValue(period.period_id, `period-${index + 1}`),
      start_time: toStringValue(period.start_time),
      end_time: toStringValue(period.end_time),
      duration_minutes: toNumberValue(period.duration_minutes),
      course_code: toStringValue(period.course_code, toStringValue(period.course_id, 'COURSE')),
      course_name: toStringValue(period.course_name, toStringValue(period.course_code, 'Untitled course')),
      class_id: toStringValue(period.class_id),
      class_name: period.class_name != null ? String(period.class_name) : undefined,
      section: period.section != null ? String(period.section) : undefined,
      room: period.room != null ? String(period.room) : undefined,
      is_lab_class: Boolean(period.is_lab_class ?? String(period.period_type ?? '').toLowerCase() === 'lab'),
      course_color: toStringValue(period.course_color, '#6366F1'),
      enrolled_count: toNumberValue(period.enrolled_count),
      marked_count: toNumberValue(period.marked_count) ?? toNumberValue(attendanceCounts.total_marked),
      is_completed: Boolean(period.is_completed ?? attendanceCounts.is_completed ?? false),
    };
  });
}

const LoadingState: React.FC<{ label: string }> = ({ label }) => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="flex flex-col items-center gap-4">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-indigo-600" />
      <p className="text-sm text-slate-500">{label}</p>
    </div>
  </div>
);

const ErrorState: React.FC<{ message: string }> = ({ message }) => (
  <div className="flex items-center justify-center min-h-screen p-6">
    <div className="max-w-md rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
      <p className="text-sm font-semibold">Unable to load dashboard</p>
      <p className="mt-2 text-sm">{message}</p>
    </div>
  </div>
);

export const RoleLandingPage: React.FC = () => {
  const role = getStoredRole();
  const userId = sessionStorage.getItem('user_id') ?? '';
  const userEmail = sessionStorage.getItem('user_email') ?? '';

  const [teacherData, setTeacherData] = useState<Record<string, unknown> | null>(null);
  const [loadingTeacher, setLoadingTeacher] = useState(false);
  const [teacherError, setTeacherError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadTeacherDashboard = async () => {
      if (role !== 'teacher' || !userId) return;

      setLoadingTeacher(true);
      setTeacherError(null);

      try {
        const data = await attendanceAPI.getTeacherDashboard(userId);
        if (!cancelled) {
          setTeacherData(data);
        }
      } catch (error) {
        if (!cancelled) {
          setTeacherError(error instanceof Error ? error.message : 'Failed to load teacher dashboard');
        }
      } finally {
        if (!cancelled) {
          setLoadingTeacher(false);
        }
      }
    };

    void loadTeacherDashboard();

    return () => {
      cancelled = true;
    };
  }, [role, userId]);

  const teacherPeriods = useMemo(() => {
    const schedule = Array.isArray(teacherData?.schedule) ? teacherData?.schedule : [];
    return normalizeTeacherPeriods(schedule as unknown[]);
  }, [teacherData]);

  if (!role) {
    return <ErrorState message="No active role session found. Please sign in again." />;
  }

  if (role === 'admin') {
    return <DashboardPage />;
  }

  if (role === 'teacher') {
    if (!userId) {
      return <ErrorState message="Teacher session is missing an ID. Please sign in again." />;
    }

    if (loadingTeacher && !teacherData) {
      return <LoadingState label="Loading teacher dashboard..." />;
    }

    if (teacherError) {
      return <ErrorState message={teacherError} />;
    }

    const classId =
      toStringValue(teacherData?.active_period && typeof teacherData.active_period === 'object'
        ? (teacherData.active_period as Record<string, unknown>).class_id
        : undefined) ||
      teacherPeriods[0]?.class_id ||
      '';

    const facultyName =
      userEmail.split('@')[0].replace(/[._]+/g, ' ') ||
      'Faculty';

    return (
      <Layout>
        <TeacherDashboard
          facultyId={userId}
          facultyName={facultyName}
          classId={classId}
          todayPeriods={teacherPeriods}
        />
      </Layout>
    );
  }

  if (role === 'student') {
    if (!userId) {
      return <ErrorState message="Student session is missing an ID. Please sign in again." />;
    }

    return (
      <Layout>
        <DashboardPage />
      </Layout>
    );
  }

  return <ErrorState message="Your account role is not recognized." />;
};

export default RoleLandingPage;
