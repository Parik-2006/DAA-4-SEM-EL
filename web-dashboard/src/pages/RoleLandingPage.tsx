import React, { useEffect, useMemo, useState } from 'react';

import { Layout } from '../components';
import StudentDashboardPage from './StudentDashboardPage';
import { TeacherDashboard, type TeacherPeriod } from './TeacherDashboard';
import { attendanceAPI } from '../services/api';
import { useRoleSummary } from '../hooks/useAttendanceMatrix';
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
  const roleSummary = useRoleSummary(role === 'admin');

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
    if (roleSummary.isLoading && !roleSummary.data) {
      return <LoadingState label="Loading admin summary..." />;
    }

    if (roleSummary.error) {
      return <ErrorState message={roleSummary.error} />;
    }

    const summary = roleSummary.data;

    return (
      <Layout>
        <div className="space-y-6 pb-8">
          <div className="rounded-[2rem] border border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-6 py-6 text-white shadow-xl">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-300">Admin summary</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">Live role overview</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-300">
              A compact view of today’s attendance, the current active period, and the sections that need attention.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Students</p>
              <div className="mt-3 text-3xl font-semibold text-slate-900">{summary?.student_count ?? 0}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Classes</p>
              <div className="mt-3 text-3xl font-semibold text-slate-900">{summary?.class_count ?? 0}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Attendance rate</p>
              <div className="mt-3 text-3xl font-semibold text-slate-900">{summary?.today_breakdown.attendance_rate ?? 0}%</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Marked</p>
              <div className="mt-3 text-3xl font-semibold text-slate-900">{summary?.today_breakdown.marked ?? 0}</div>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.4fr_0.9fr]">
            <div className="rounded-[1.75rem] border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">Active period</h2>
              {summary?.active_period ? (
                <div className="mt-4 rounded-2xl bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-slate-900">
                    {String((summary.active_period as Record<string, unknown>).course_code ?? 'Unknown course')}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    {String((summary.active_period as Record<string, unknown>).class_id ?? '')}
                    {String((summary.active_period as Record<string, unknown>).room ?? '') ? ` · Room ${String((summary.active_period as Record<string, unknown>).room)}` : ''}
                  </p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-4 text-sm">
                    <div className="rounded-xl bg-white p-3 shadow-sm">Present {String(((summary.active_period as Record<string, unknown>).attendance_stats as Record<string, unknown> | undefined)?.present ?? 0)}</div>
                    <div className="rounded-xl bg-white p-3 shadow-sm">Late {String(((summary.active_period as Record<string, unknown>).attendance_stats as Record<string, unknown> | undefined)?.late ?? 0)}</div>
                    <div className="rounded-xl bg-white p-3 shadow-sm">Pending {String(((summary.active_period as Record<string, unknown>).attendance_stats as Record<string, unknown> | undefined)?.pending ?? 0)}</div>
                    <div className="rounded-xl bg-white p-3 shadow-sm">Rate {String(((summary.active_period as Record<string, unknown>).attendance_stats as Record<string, unknown> | undefined)?.attendance_rate ?? 0)}%</div>
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">No active period is currently reported by the timetable service.</p>
              )}
            </div>

            <div className="rounded-[1.75rem] border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">At-risk sections</h2>
              <div className="mt-4 space-y-3">
                {(summary?.at_risk_sections ?? []).length === 0 ? (
                  <p className="text-sm text-slate-500">No low-attendance sections were flagged today.</p>
                ) : (
                  summary?.at_risk_sections.map((section) => (
                    <div key={section.class_id} className="rounded-2xl bg-slate-50 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{section.class_name || section.class_id}</p>
                          <p className="text-xs text-slate-500">{section.total_students} students · {section.marked} marked</p>
                        </div>
                        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">
                          {section.attendance_rate}%
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </Layout>
    );
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

    return <StudentDashboardPage />;
  }

  return <ErrorState message="Your account role is not recognized." />;
};

export default RoleLandingPage;
