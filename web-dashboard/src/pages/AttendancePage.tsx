import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { BookOpen, Calendar, ChevronLeft, Clock, Loader, RefreshCw, Users, Wifi, AlertCircle, CheckCircle } from 'lucide-react';

import { Layout, AttendanceSheet, LiveCamera, TimetableBar, type TeacherPeriod } from '../components';
import { attendanceAPI, timetableAPI, type PeriodInfo } from '../services/api';
import { getStoredAssignedSections } from '../services/firebase/auth.service';

const STATIC_STUDENTS: Record<string, Array<{ student_id: string; roll_no: string; name: string }>> = {
  'CSE-A-4SEM': [
    { student_id: 'STUD_001', roll_no: '4CS01', name: 'Parikshith B Bilchode' },
    { student_id: 'STUD_002', roll_no: '4CS02', name: 'Gagan D K' },
    { student_id: 'STUD_003', roll_no: '4CS03', name: 'Prajwal K' },
    { student_id: 'STUD_004', roll_no: '4CS04', name: 'Ved U' },
    { student_id: 'STUD_005', roll_no: '4CS05', name: 'Pranav Kumar M' },
    { student_id: 'STUD_006', roll_no: '4CS06', name: 'Nischith G A' },
  ],
  'CSE-B-4SEM': [
    { student_id: 'STUD_007', roll_no: '4CS07', name: 'Yohith N' },
    { student_id: 'STUD_008', roll_no: '4CS08', name: 'Mahesh Raju N' },
  ],
  'CSE-C-4SEM': [
    { student_id: 'STUD_010', roll_no: '4CS10', name: 'Sneha Patil' },
  ],
};

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function getPeriodState(start: string, end: string): 'active' | 'upcoming' | 'past' {
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();
  const [startHours, startMinutes] = start.split(':').map(Number);
  const [endHours, endMinutes] = end.split(':').map(Number);
  const startTotal = startHours * 60 + startMinutes;
  const endTotal = endHours * 60 + endMinutes;

  if (currentMinutes >= endTotal) return 'past';
  if (currentMinutes >= startTotal) return 'active';
  return 'upcoming';
}

function mapPeriod(period: PeriodInfo): TeacherPeriod {
  return {
    period_id: period.period_id,
    class_id: period.class_id,
    course_id: period.course_code,
    course_code: period.course_code,
    course_name: period.course_name,
    start_time: period.start_time,
    end_time: period.end_time,
    faculty_name: 'Faculty',
    room: 'Room not set',
    course_color: '#6366F1',
    is_lab_class: false,
  };
}

export const AttendancePage: React.FC = () => {
  const assignedSections = useMemo(() => getStoredAssignedSections(), []);
  const classOptions = useMemo(
    () => assignedSections.map((id) => ({ id, label: id })),
    [assignedSections]
  );
  const [selectedClass, setSelectedClass] = useState('');
  const [students, setStudents] = useState<Array<{ student_id: string; roll_no: string; name: string; photo_url?: string }>>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [studentsError, setStudentsError] = useState<string | null>(null);

  const [periods, setPeriods] = useState<TeacherPeriod[]>([]);
  const [periodsLoading, setPeriodsLoading] = useState(false);
  const [periodsError, setPeriodsError] = useState<string | null>(null);
  const [selectedPeriodId, setSelectedPeriodId] = useState<string | null>(null);

  const [savedCount, setSavedCount] = useState<number | null>(null);
  const [liveStatus, setLiveStatus] = useState<'idle' | 'processing' | 'ready'>('idle');

  const markedBy = localStorage.getItem('user_id') ?? localStorage.getItem('user_email') ?? 'unknown';

  const classLabel = useMemo(
    () => classOptions.find((item) => item.id === selectedClass)?.label ?? selectedClass,
    [classOptions, selectedClass],
  );

  const selectedPeriod = useMemo(
    () => periods.find((period) => period.period_id === selectedPeriodId) ?? null,
    [periods, selectedPeriodId],
  );

  const activeCount = useMemo(() => periods.filter((period) => getPeriodState(period.start_time, period.end_time) === 'active').length, [periods]);
  const upcomingCount = useMemo(() => periods.filter((period) => getPeriodState(period.start_time, period.end_time) === 'upcoming').length, [periods]);
  const pastCount = useMemo(() => periods.filter((period) => getPeriodState(period.start_time, period.end_time) === 'past').length, [periods]);

  const loadStudents = useCallback(async (classId: string) => {
    setLoadingStudents(true);
    setStudentsError(null);

    try {
      const fetched = await attendanceAPI.getStudents(classId);
      if (fetched.length > 0) {
        setStudents(
          fetched.map((student: any) => ({
            student_id: student.student_id || student.id,
            roll_no: student.roll_no || student.student_id,
            name: student.name,
            photo_url: student.avatar_url,
          })),
        );
      } else {
        setStudents(STATIC_STUDENTS[classId] ?? []);
      }
    } catch {
      setStudentsError('Using fallback student roster');
      setStudents(STATIC_STUDENTS[classId] ?? []);
    } finally {
      setLoadingStudents(false);
    }
  }, []);

  const loadPeriods = useCallback(async (classId: string) => {
    setPeriodsLoading(true);
    setPeriodsError(null);

    try {
      const result = await timetableAPI.getTodayPeriods(classId);
      const mapped = result.map(mapPeriod);
      setPeriods(mapped);
      setSelectedPeriodId((current) => {
        if (current && mapped.some((period) => period.period_id === current)) {
          return current;
        }
        const active = mapped.find((period) => getPeriodState(period.start_time, period.end_time) === 'active');
        return active?.period_id ?? mapped[0]?.period_id ?? null;
      });
    } catch {
      setPeriodsError('Could not load today\'s timetable. Using empty schedule.');
      setPeriods([]);
      setSelectedPeriodId(null);
    } finally {
      setPeriodsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedClass) return;

    void loadStudents(selectedClass);
    void loadPeriods(selectedClass);

    const intervalId = window.setInterval(() => {
      void loadPeriods(selectedClass);
    }, 60_000);

    return () => window.clearInterval(intervalId);
  }, [selectedClass, loadPeriods, loadStudents]);

  useEffect(() => {
    if (!selectedPeriodId && periods.length > 0) {
      const active = periods.find((period) => getPeriodState(period.start_time, period.end_time) === 'active');
      setSelectedPeriodId(active?.period_id ?? periods[0].period_id);
    }
  }, [periods, selectedPeriodId]);

  const handleClassSelect = (classId: string) => {
    setSelectedClass(classId);
    setSavedCount(null);
    setSelectedPeriodId(null);
  };

  const handleSaved = (entries: Array<{ status: string }>) => {
    setSavedCount(entries.filter((entry) => entry.status !== 'not_marked').length);
  };

  const reset = () => {
    setSelectedClass('');
    setSavedCount(null);
    setSelectedPeriodId(null);
    setPeriods([]);
    setStudents([]);
    setStudentsError(null);
    setPeriodsError(null);
  };

  return (
    <Layout>
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">Teacher Portal</p>
            <h1 className="mt-2 text-3xl font-black text-slate-900">Mark Attendance</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-500">
              Timetable-aware attendance with live camera check-in and manual roster overrides.
            </p>
          </div>

          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700">
            <Wifi size={14} />
            Live Sync
          </div>
        </div>

        {!selectedClass ? (
          <div className="grid gap-4 md:grid-cols-3">
            {classOptions.map((cls) => (
              <button
                key={cls.id}
                type="button"
                onClick={() => handleClassSelect(cls.id)}
                className="rounded-3xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                  <Users size={20} />
                </div>
                <h2 className="text-lg font-bold text-slate-900">{cls.label}</h2>
                <p className="mt-2 text-sm text-slate-500">Open today\'s timetable and begin attendance for this class.</p>
              </button>
            ))}
            {classOptions.length === 0 && (
              <div className="rounded-3xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
                No assigned sections found for this account.
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={reset}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 shadow-sm"
              >
                <ChevronLeft size={15} />
                Change class
              </button>
              <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-500 shadow-sm">
                <Calendar size={13} />
                {classLabel}
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-500 shadow-sm">
                <Clock size={13} />
                {todayISO()}
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-4">
              {[
                { label: 'Total', value: periods.length, tone: '#6366F1', bg: '#EEF2FF' },
                { label: 'Active', value: activeCount, tone: '#16a34a', bg: '#F0FDF4' },
                { label: 'Upcoming', value: upcomingCount, tone: '#d97706', bg: '#FFFBEB' },
                { label: 'Completed', value: pastCount, tone: '#64748b', bg: '#F8FAFC' },
              ].map((item) => (
                <div key={item.label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm" style={{ background: item.bg }}>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{item.label}</p>
                  <p className="mt-1 text-2xl font-black" style={{ color: item.tone }}>
                    {item.value}
                  </p>
                </div>
              ))}
            </div>

            {periodsLoading && (
              <div className="flex items-center gap-2 rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-medium text-indigo-700">
                <Loader size={16} className="animate-spin" />
                Loading today\'s timetable...
              </div>
            )}

            {periodsError && (
              <div className="flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
                <AlertCircle size={16} />
                {periodsError}
              </div>
            )}

            {studentsError && (
              <div className="flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
                <AlertCircle size={16} />
                {studentsError}
              </div>
            )}

            <TimetableBar
              periods={periods}
              selectedPeriodId={selectedPeriodId}
              onSelectPeriod={(period) => setSelectedPeriodId(period.period_id)}
            />

            {selectedPeriod && (
              <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                <div className="space-y-4">
                  <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-500">Current period</p>
                        <h2 className="mt-2 text-2xl font-black text-slate-900">{selectedPeriod.course_name}</h2>
                        <p className="mt-1 text-sm text-slate-500">
                          {selectedPeriod.course_code} • {selectedPeriod.start_time} - {selectedPeriod.end_time}
                        </p>
                      </div>
                      <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-500">
                        <BookOpen size={13} />
                        {students.length} students
                      </div>
                    </div>
                  </div>

                  <LiveCamera
                    periodId={selectedPeriod.period_id}
                    onAttendanceMarked={(data) => {
                      if (data?.status === 'success') {
                        setLiveStatus('ready');
                      }
                    }}
                    onProcessing={(isProcessing) => setLiveStatus(isProcessing ? 'processing' : 'idle')}
                    isLoading={liveStatus === 'processing'}
                    autoStart={false}
                  />
                </div>

                <div className="space-y-4">
                  {savedCount !== null && (
                    <div className="flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
                      <CheckCircle size={16} />
                      Session saved - {savedCount} attendance records committed.
                    </div>
                  )}

                  <AttendanceSheet
                    period={selectedPeriod}
                    markedBy={markedBy}
                    students={students}
                    onSaved={handleSaved}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {selectedClass && !selectedPeriod && !periodsLoading && (
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
            No period is currently available for today. Refresh after the timetable is published.
          </div>
        )}

        {selectedClass && (
          <button
            type="button"
            onClick={() => void loadPeriods(selectedClass)}
            className="inline-flex w-fit items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 shadow-sm"
          >
            <RefreshCw size={14} />
            Refresh timetable
          </button>
        )}
      </div>
    </Layout>
  );
};

export default AttendancePage;
