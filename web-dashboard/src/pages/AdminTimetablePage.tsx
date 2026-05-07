import React, { useEffect, useMemo, useState } from 'react';

import { Layout } from '../components';
import { attendanceAPI } from '../services/api';

function toStringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function normalizeDays(days: unknown): Array<{ day: string; periods: Array<Record<string, unknown>> }> {
  if (!days || typeof days !== 'object') return [];

  return Object.entries(days as Record<string, unknown>).map(([day, value]) => ({
    day,
    periods: Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object') : [],
  }));
}

const AdminTimetablePage: React.FC = () => {
  const [classId, setClassId] = useState('');
  const [inputValue, setInputValue] = useState('');
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialClassId = params.get('class_id') ?? params.get('classId') ?? '';
    setClassId(initialClassId);
    setInputValue(initialClassId);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (!classId) {
        setData(null);
        setError(null);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const result = await attendanceAPI.getClassTimetable(classId);
        if (!cancelled) {
          setData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load class timetable');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [classId]);

  const days = useMemo(() => normalizeDays(data?.days), [data]);
  const courses = (data?.all_courses && typeof data.all_courses === 'object') ? data.all_courses as Record<string, { name?: string; color?: string }> : {};

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Admin timetable view</p>
            <h1 className="text-3xl font-bold text-slate-900">Class Timetable</h1>
            <p className="mt-1 text-sm text-slate-500">Open any class timetable by class ID.</p>
          </div>

          <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Enter class ID"
              className="w-56 border-0 bg-transparent text-sm outline-none"
            />
            <button
              onClick={() => setClassId(inputValue.trim())}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700"
            >
              Load
            </button>
          </div>
        </div>

        {!classId && (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-500">
            Enter a class ID to view timetable details.
          </div>
        )}

        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
            Loading timetable...
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            {error}
          </div>
        )}

        {data && !loading && !error && (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Class</p>
                <p className="mt-2 text-lg font-bold text-slate-900">{toStringValue(data.class_id, classId)}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Days</p>
                <p className="mt-2 text-lg font-bold text-slate-900">{days.length}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Courses</p>
                <p className="mt-2 text-lg font-bold text-slate-900">{Object.keys(courses).length}</p>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {days.map(({ day, periods }) => (
                <div key={day} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold text-slate-900">{day}</h2>
                    <span className="text-xs font-semibold text-slate-400">{periods.length} periods</span>
                  </div>
                  <div className="mt-4 space-y-3">
                    {periods.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
                        No periods scheduled.
                      </div>
                    ) : (
                      periods.map((period, index) => (
                        <div key={`${day}-${index}`} className="rounded-xl border border-slate-200 p-4">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">
                                {toStringValue(period.course_code, 'COURSE')} - {toStringValue(period.course_name, 'Untitled course')}
                              </p>
                              <p className="text-xs text-slate-500">
                                {toStringValue(period.start_time)} - {toStringValue(period.end_time)}
                              </p>
                            </div>
                            <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-600">
                              {toStringValue(period.class_id, classId)}
                            </span>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
                            {period.room && <span>Room: {String(period.room)}</span>}
                            {period.faculty_name && <span>Faculty: {String(period.faculty_name)}</span>}
                            {period.period_type && <span>Type: {String(period.period_type)}</span>}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AdminTimetablePage;
