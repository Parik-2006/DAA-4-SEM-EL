import React, { useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle,
  Clock,
  Loader2,
  Lock,
  PencilLine,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
  Undo2,
  Wifi,
} from 'lucide-react';

import { attendanceAPI, type BulkManualAttendanceResponse } from '../services/api';
import { getStoredRole } from '../utils/roles';
import {
  useManualAttendance,
  type ManualStatus,
} from '../hooks/useAttendanceHooks';

export interface TeacherPeriod {
  period_id: string;
  class_id: string;
  course_id: string;
  course_code: string;
  course_name: string;
  start_time: string;
  end_time: string;
  faculty_name?: string;
  room?: string;
  is_lab_class?: boolean;
  course_color?: string;
}

export interface AttendanceEntry {
  student_id: string;
  status: ManualStatus;
  notes?: string;
  last_saved_at?: string | null;
  record_id?: string;
}

export type AttendanceStatus = ManualStatus;

interface TeacherStudent {
  student_id: string;
  roll_no: string;
  name: string;
  photo_url?: string;
}

interface AttendanceSheetProps {
  period: TeacherPeriod;
  markedBy: string;
  students: TeacherStudent[];
  onSaved?: (entries: AttendanceEntry[]) => void;
}

const STATUS_META = {
  present: { label: 'Present', color: '#16a34a', bg: '#f0fdf4' },
  late: { label: 'Late', color: '#d97706', bg: '#fffbeb' },
  absent: { label: 'Absent', color: '#dc2626', bg: '#fef2f2' },
  not_marked: { label: 'Not marked', color: '#64748b', bg: '#f8fafc' },
} as const;

function initials(name: string) {
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function timeLabel(value?: string | null) {
  if (!value) return 'Not saved';
  try {
    return new Date(value).toLocaleString([], {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  } catch {
    return value;
  }
}

function statusIcon(status: keyof typeof STATUS_META) {
  switch (status) {
    case 'present':
      return <CheckCircle size={14} />;
    case 'late':
      return <Clock size={14} />;
    case 'absent':
      return <Trash2 size={14} />;
    default:
      return <RefreshCw size={14} />;
  }
}

export const AttendanceSheet: React.FC<AttendanceSheetProps> = ({ period, markedBy, students, onSaved }) => {
  const [lockError, setLockError] = useState<string | null>(null);
  const [isLocking, setIsLocking] = useState(false);

  const {
    roster,
    setStatus,
    setNotes,
    saveOne,
    saveAll,
    markAllPresent,
    markAllAbsent,
    undo,
    canUndo,
    saving,
    lastSaveResult,
    saveErrors,
    isDirty,
    lastSavedAt,
    loading,
    loadError,
  } = useManualAttendance({
    classId: period.class_id,
    periodId: period.period_id,
    courseId: period.course_id,
    markedBy,
    initialRoster: students,
    preloadExisting: true,
  });

  const summary = useMemo(() => {
    const present = roster.filter((entry) => entry.status === 'present').length;
    const late = roster.filter((entry) => entry.status === 'late').length;
    const absent = roster.filter((entry) => entry.status === 'absent').length;
    const unmarked = roster.filter((entry) => entry.status === 'not_marked').length;
    const saved = roster.filter((entry) => entry.last_saved_at).length;
    return { present, late, absent, unmarked, saved, total: roster.length };
  }, [roster]);

  const navigate = useNavigate();

  const navigateToFace = (studentId: string) => {
    // include student id as query param so the Face page can focus on it if needed
    navigate(`/face?student=${encodeURIComponent(studentId)}`);
  };

  const handleChangeStatus = useCallback(
    async (studentId: string, status: 'present' | 'late' | 'absent') => {
      setStatus(studentId, status);
      try {
        await saveOne(studentId);
      } catch {
        // saveErrors is already populated by the hook
      }
    },
    [setStatus, saveOne]
  );

  const handleSaveAll = useCallback(async () => {
    try {
      const result: BulkManualAttendanceResponse | null = await saveAll();
      if (result) {
        onSaved?.(
          roster.map((entry) => ({
            student_id: entry.student_id,
            status: entry.status,
            notes: entry.notes,
            last_saved_at: entry.last_saved_at,
            record_id: entry.record_id,
          }))
        );
      }
    } catch (err) {
      setLockError(err instanceof Error ? err.message : 'Failed to save attendance');
    }
  }, [saveAll, onSaved, roster]);

  const handleLockSession = useCallback(async () => {
    setLockError(null);
    setIsLocking(true);
    try {
      const result = await saveAll();
      if (!result) return;

      const missingIds = roster
        .filter((entry) => entry.status === 'not_marked')
        .map((entry) => entry.student_id);

      await attendanceAPI.lockPeriodSession(period.period_id, period.class_id, missingIds, undefined);
      onSaved?.(
        roster.map((entry) => ({
          student_id: entry.student_id,
          status: entry.status,
          notes: entry.notes,
          last_saved_at: entry.last_saved_at,
          record_id: entry.record_id,
        }))
      );
    } catch (err) {
      setLockError(err instanceof Error ? err.message : 'Failed to lock session');
    } finally {
      setIsLocking(false);
    }
  }, [period.class_id, period.period_id, roster, saveAll, onSaved]);

  const unsavedCount = roster.filter((entry) => entry.status !== 'not_marked' && !entry.last_saved_at).length;

  return (
    <div className="rounded-3xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="border-b border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50 px-6 py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              <span>{period.course_code}</span>
              <span>•</span>
              <span>{period.faculty_name ?? 'Faculty'}</span>
              {period.is_lab_class && (
                <span className="rounded-full bg-violet-100 px-2 py-0.5 text-violet-700">Lab</span>
              )}
            </div>
            <h2 className="mt-2 text-2xl font-black text-slate-900">{period.course_name}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {period.start_time} - {period.end_time} • {period.room ?? 'Room not set'}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={undo}
              disabled={!canUndo}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Undo2 size={15} />
              Undo
            </button>
            <button
              type="button"
              onClick={handleSaveAll}
              disabled={saving || loading}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
              Save All
            </button>
            <button
              type="button"
              onClick={handleLockSession}
              disabled={saving || loading || isLocking}
              className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLocking ? <Loader2 size={15} className="animate-spin" /> : <Lock size={15} />}
              Save & Lock Session
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-3 border-b border-slate-200 bg-slate-50 px-6 py-4 md:grid-cols-4">
        {[
          { label: 'Present', value: summary.present, color: '#16a34a' },
          { label: 'Late', value: summary.late, color: '#d97706' },
          { label: 'Absent', value: summary.absent, color: '#dc2626' },
          { label: 'Not marked', value: summary.unmarked, color: '#64748b' },
        ].map((item) => (
          <div key={item.label} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{item.label}</p>
            <p className="mt-1 text-2xl font-black" style={{ color: item.color }}>
              {item.value}
            </p>
          </div>
        ))}
      </div>

      <div className="px-6 py-4">
        {loading && (
          <div className="mb-4 flex items-center gap-2 rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-medium text-indigo-700">
            <Loader2 size={16} className="animate-spin" />
            Loading existing attendance for this period...
          </div>
        )}

        {loadError && (
          <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
            {loadError}
          </div>
        )}

        {lockError && (
          <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800">
            {lockError}
          </div>
        )}

        {isDirty && (
          <div className="mb-4 flex items-center gap-2 rounded-2xl border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm font-medium text-yellow-800">
            <Sparkles size={15} />
            Unsaved changes remain in this roster.
          </div>
        )}

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={markAllPresent}
            className="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700"
          >
            <CheckCircle size={15} />
            Mark all present
          </button>
          <button
            type="button"
            onClick={markAllAbsent}
            className="inline-flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-700"
          >
            <Trash2 size={15} />
            Mark all absent
          </button>
          <div className="ml-auto inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-500">
            <Wifi size={13} className="text-emerald-500" />
            {summary.saved}/{summary.total} saved
          </div>
        </div>

        <div className="overflow-hidden rounded-3xl border border-slate-200">
          <div className="grid grid-cols-[1.3fr_0.9fr_0.9fr_0.7fr] border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
            <div>Student</div>
            <div>Status</div>
            <div>Saved At</div>
            <div>Quick</div>
          </div>

          <div className="divide-y divide-slate-100 bg-white">
            {roster.map((entry) => {
              const saved = Boolean(entry.last_saved_at);
              const error = saveErrors[entry.student_id];
              const status = entry.status;
              const meta = STATUS_META[status as keyof typeof STATUS_META] ?? STATUS_META.not_marked;

              return (
                <div key={entry.student_id} className="grid grid-cols-1 gap-4 px-4 py-4 lg:grid-cols-[1.3fr_0.9fr_0.9fr_0.7fr] lg:items-center">
                  <div className="flex items-start gap-3">
                    {entry.photo_url ? (
                      <img src={entry.photo_url} alt={entry.name} className="h-11 w-11 rounded-full object-cover ring-2 ring-slate-100" />
                    ) : (
                      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-indigo-100 text-sm font-black text-indigo-700">
                        {initials(entry.name)}
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate font-semibold text-slate-900">{entry.name}</p>
                        {saved && <ShieldCheck size={14} className="text-emerald-600" />}
                      </div>
                      <p className="text-xs text-slate-500">Roll No. {entry.roll_no}</p>
                      {error && <p className="mt-1 text-xs font-medium text-red-600">{error}</p>}
                      {entry.notes && <p className="mt-1 text-xs text-slate-500">{entry.notes}</p>}
                    </div>
                  </div>

                  <div>
                    <select
                      value={status}
                      onChange={(event) => {
                        const nextStatus = event.target.value as 'present' | 'late' | 'absent' | 'not_marked';
                        setStatus(entry.student_id, nextStatus);
                        if (nextStatus !== 'not_marked') {
                          void saveOne(entry.student_id);
                        }
                      }}
                      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                    >
                      {Object.entries(STATUS_META).map(([key, value]) => (
                        <option key={key} value={key}>
                          {value.label}
                        </option>
                      ))}
                    </select>
                    <div className="mt-2 inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-semibold" style={{ background: meta.bg, color: meta.color }}>
                      {statusIcon(status as keyof typeof STATUS_META)}
                      {meta.label}
                    </div>
                  </div>

                  <div className="text-sm text-slate-600">
                    <div className="flex items-center gap-2 font-medium">
                      {saved ? <Wifi size={14} className="text-emerald-600" /> : <Clock size={14} className="text-slate-400" />}
                      {timeLabel(entry.last_saved_at)}
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{saved ? 'Confirmed on server' : 'Waiting to be saved'}</p>
                  </div>

                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    {(['present', 'late', 'absent'] as const).map((quickStatus) => {
                      const handleQuick = () => {
                        // If a student clicks the 'present' quick button on their own row,
                        // open the live camera page instead of immediately marking present.
                        try {
                          const role = getStoredRole();
                          const currentUser = sessionStorage.getItem('user_id') ?? '';
                          if (quickStatus === 'present' && role === 'student' && currentUser === entry.student_id) {
                            navigateToFace(entry.student_id);
                            return;
                          }
                        } catch {
                          // fallthrough to default behaviour
                        }

                        void handleChangeStatus(entry.student_id, quickStatus);
                      };

                      return (
                        <button
                          key={quickStatus}
                          type="button"
                          onClick={handleQuick}
                          className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5"
                          title={`Mark ${STATUS_META[quickStatus].label}`}
                        >
                          {quickStatus === 'present' && <CheckCircle size={16} className="text-emerald-600" />}
                          {quickStatus === 'late' && <Clock size={16} className="text-amber-600" />}
                          {quickStatus === 'absent' && <Trash2 size={16} className="text-red-600" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 font-semibold text-slate-600">
            <PencilLine size={13} />
            Quick actions write immediately
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 font-semibold text-slate-600">
            <Clock size={13} />
            Last bulk save: {timeLabel(lastSavedAt)}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 font-semibold text-slate-600">
            <RefreshCw size={13} />
            Unsaved rows: {unsavedCount}
          </span>
        </div>

        {lastSaveResult && (
          <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            Bulk save completed: {lastSaveResult.saved ?? 0} saved, {lastSaveResult.errors?.length ?? 0} errors.
          </div>
        )}
      </div>
    </div>
  );
};

export default AttendanceSheet;
