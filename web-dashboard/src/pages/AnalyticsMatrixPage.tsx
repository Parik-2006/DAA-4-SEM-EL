import React, { useEffect, useMemo, useState } from 'react';
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Users,
  Clock3,
  AlertTriangle,
} from 'lucide-react';

import { Layout } from '../components';
import { useClassesAndPeriods } from '../hooks/useAttendanceHooks';
import { useAttendanceMatrix } from '../hooks/useAttendanceMatrix';

function formatDateLabel(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}

function formatWeekStart(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

function getMonday(value: Date): string {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  const offset = (date.getDay() + 6) % 7;
  date.setDate(date.getDate() - offset);
  return date.toISOString().slice(0, 10);
}

function shiftWeek(weekStart: string, deltaDays: number): string {
  const date = new Date(`${weekStart}T00:00:00`);
  date.setDate(date.getDate() + deltaDays);
  return date.toISOString().slice(0, 10);
}

function toStringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function toNumberValue(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() && !Number.isNaN(Number(value))) return Number(value);
  return 0;
}

function getClassId(item: Record<string, unknown>): string {
  return toStringValue(item.class_id ?? item.id ?? item.classId ?? item.section_id ?? item.sectionId, '');
}

function getClassName(item: Record<string, unknown>): string {
  const classId = getClassId(item);
  return toStringValue(
    item.name ?? item.class_name ?? item.section_name ?? item.display ?? item.section_label,
    classId || 'Untitled class',
  );
}

const metricCards = [
  { key: 'students', label: 'Students', icon: Users },
  { key: 'periods', label: 'Periods', icon: CalendarDays },
  { key: 'rate', label: 'Attendance rate', icon: TrendingUp },
  { key: 'pending', label: 'Pending', icon: Clock3 },
] as const;

const statusStyles: Record<string, { bg: string; border: string; text: string }> = {
  no_class: { bg: '#F7F7F5', border: '#D7D3CC', text: '#7B7167' },
  upcoming: { bg: '#EEF4FF', border: '#86A3FF', text: '#2444B5' },
  in_progress: { bg: '#E7F7EC', border: '#58B76F', text: '#1E6C35' },
  complete: { bg: '#FAF3DD', border: '#E3B34A', text: '#816009' },
};

const MetricCard: React.FC<{ label: string; value: string | number; icon: React.ComponentType<{ className?: string }> }> = ({
  label,
  value,
  icon: Icon,
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</p>
        <div className="mt-3 text-3xl font-semibold text-slate-900">{value}</div>
      </div>
      <div className="rounded-xl bg-slate-900 p-2 text-white">
        <Icon className="h-4 w-4" />
      </div>
    </div>
  </div>
);

const CellBadge: React.FC<{
  status: string;
  title: string;
  subtitle: string;
  rate: number;
}> = ({ status, title, subtitle, rate }) => {
  const palette = statusStyles[status] ?? statusStyles.no_class;
  return (
    <div
      className="min-h-[120px] rounded-2xl border p-3 transition-transform duration-200 hover:-translate-y-0.5"
      style={{ background: palette.bg, borderColor: palette.border }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold" style={{ color: palette.text }}>{title}</p>
          <p className="mt-1 text-xs" style={{ color: palette.text, opacity: 0.8 }}>{subtitle}</p>
        </div>
        <span className="rounded-full bg-white/70 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: palette.text }}>
          {status.replace('_', ' ')}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs font-medium" style={{ color: palette.text }}>
        <div className="rounded-xl bg-white/70 px-2 py-1">Rate {rate}%</div>
        <div className="rounded-xl bg-white/70 px-2 py-1">Live {status === 'in_progress' ? 'Yes' : 'No'}</div>
      </div>
    </div>
  );
};

export const AnalyticsMatrixPage: React.FC = () => {
  const { classes } = useClassesAndPeriods();
  const [selectedClassId, setSelectedClassId] = useState('');
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));

  useEffect(() => {
    if (!selectedClassId && classes.length > 0) {
      const firstClass = classes[0] as unknown as Record<string, unknown>;
      setSelectedClassId(getClassId(firstClass));
    }
  }, [classes, selectedClassId]);

  const selectedClass = useMemo(() => {
    const found = classes.find((item) => getClassId(item as unknown as Record<string, unknown>) === selectedClassId);
    return (found as Record<string, unknown> | undefined) ?? null;
  }, [classes, selectedClassId]);

  const { data, rows, isLoading, error, refetch } = useAttendanceMatrix(selectedClassId || undefined, weekStart);

  useEffect(() => {
    if (!selectedClassId && data?.class_id) {
      setSelectedClassId(data.class_id);
    }
  }, [data?.class_id, selectedClassId]);

  const summary = data?.summary;
  const periodSlots = data?.period_slots ?? [];

  const summaryValues = useMemo(() => [
    { label: 'Students', value: summary?.total_students ?? 0, icon: Users },
    { label: 'Periods', value: summary?.total_periods ?? 0, icon: CalendarDays },
    { label: 'Attendance rate', value: `${summary?.attendance_rate ?? 0}%`, icon: TrendingUp },
    { label: 'Pending', value: summary?.pending ?? 0, icon: Clock3 },
  ], [summary]);

  const classOptions = useMemo(() => classes.map((item) => {
    const classItem = item as unknown as Record<string, unknown>;
    const classId = getClassId(classItem);
    return {
      id: classId,
      label: getClassName(classItem),
    };
  }).filter((item) => item.id), [classes]);

  return (
    <Layout>
      <div className="space-y-6 pb-10">
        <div className="rounded-[2rem] border border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-6 py-6 text-white shadow-xl">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-slate-200">
                <Sparkles className="h-3.5 w-3.5" />
                Analytics Matrix
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Day × period attendance grid
              </h1>
              <p className="mt-3 max-w-xl text-sm text-slate-300">
                Review a full teaching week for one class at a time, with period slots, live status, and totals in a single grid.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setWeekStart((current) => shiftWeek(current, -7))}
                className="rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-sm font-medium text-white transition hover:bg-white/15"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <div className="rounded-xl border border-white/15 bg-white/10 px-4 py-2 text-sm text-slate-100">
                {formatWeekStart(weekStart)}
              </div>
              <button
                type="button"
                onClick={() => setWeekStart((current) => shiftWeek(current, 7))}
                className="rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-sm font-medium text-white transition hover:bg-white/15"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl bg-white/10 p-4 backdrop-blur">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-300">Class</p>
              <select
                value={selectedClassId}
                onChange={(event) => setSelectedClassId(event.target.value)}
                className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-white outline-none"
              >
                {classOptions.length === 0 && <option value="">Loading classes...</option>}
                {classOptions.map((item) => (
                  <option key={item.id} value={item.id} className="text-slate-900">
                    {item.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="rounded-2xl bg-white/10 p-4 backdrop-blur sm:col-span-2 xl:col-span-3">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-300">Current selection</p>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-100">
                <span className="rounded-full bg-white/10 px-3 py-1">{selectedClass ? getClassName(selectedClass) : data?.class_name || 'Select a class'}</span>
                <span className="rounded-full bg-white/10 px-3 py-1">Week starting {formatWeekStart(weekStart)}</span>
                {data?.section_label ? <span className="rounded-full bg-white/10 px-3 py-1">Section {data.section_label}</span> : null}
                {data?.semester ? <span className="rounded-full bg-white/10 px-3 py-1">Semester {data.semester}</span> : null}
              </div>
            </div>
          </div>
        </div>

        {error ? (
          <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="text-sm font-semibold">Matrix request failed</p>
              <p className="text-sm">{error}</p>
            </div>
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {summaryValues.map((item) => (
            <MetricCard key={item.label} label={item.label} value={item.value} icon={item.icon} />
          ))}
        </div>

        <div className="rounded-[1.75rem] border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Weekly matrix</h2>
              <p className="text-sm text-slate-500">Columns are period slots, rows are days. Status updates follow the live timetable clock.</p>
            </div>
            <button
              type="button"
              onClick={refetch}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>

          {isLoading ? (
            <div className="flex min-h-[280px] items-center justify-center text-slate-500">
              <div className="flex items-center gap-3">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900" />
                Loading matrix...
              </div>
            </div>
          ) : rows.length === 0 ? (
            <div className="flex min-h-[240px] flex-col items-center justify-center gap-3 text-slate-500">
              <CalendarDays className="h-8 w-8" />
              <p>No matrix data is available for this class yet.</p>
            </div>
          ) : (
            <div className="overflow-auto pt-4">
              <div className="min-w-[960px] space-y-4">
                <div className="grid gap-3" style={{ gridTemplateColumns: `220px repeat(${periodSlots.length || 1}, minmax(220px, 1fr))` }}>
                  <div className="rounded-2xl bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Day
                  </div>
                  {periodSlots.map((slot) => (
                    <div key={slot.slot_key} className="rounded-2xl bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      <div>{slot.label}</div>
                    </div>
                  ))}
                </div>

                {rows.map((row) => (
                  <div key={row.date} className="grid gap-3" style={{ gridTemplateColumns: `220px repeat(${periodSlots.length || 1}, minmax(220px, 1fr))` }}>
                    <div className="rounded-2xl border border-slate-200 bg-slate-950 px-4 py-4 text-white">
                      <p className="text-sm font-semibold">{row.day_name}</p>
                      <p className="mt-1 text-xs text-slate-300">{formatDateLabel(row.date)}</p>
                      <div className="mt-4 grid grid-cols-2 gap-2 text-[11px] text-slate-200">
                        <span className="rounded-lg bg-white/10 px-2 py-1">Marked {row.totals.marked}</span>
                        <span className="rounded-lg bg-white/10 px-2 py-1">Rate {row.totals.attendance_rate}%</span>
                      </div>
                    </div>

                    {row.cells.map((cell) => (
                      <CellBadge
                        key={`${row.date}-${cell.slot_key}`}
                        status={cell.status}
                        title={cell.period?.course_code || 'No class'}
                        subtitle={cell.period ? `${cell.period.course_name}${cell.period.room ? ` · ${cell.period.room}` : ''}` : 'No scheduled period'}
                        rate={cell.attendance_rate}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {summary ? (
          <div className="rounded-[1.75rem] border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold text-slate-900">Week totals</h3>
                <p className="mt-1 text-sm text-slate-500">Aggregated from all scheduled periods in the selected class.</p>
              </div>
              <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                Updated {new Date(data?.generated_at ?? Date.now()).toLocaleString()}
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Present" value={summary.present} icon={Users} />
              <MetricCard label="Late" value={summary.late} icon={Clock3} />
              <MetricCard label="Absent" value={summary.absent} icon={AlertTriangle} />
              <MetricCard label="Attendance rate" value={`${summary.attendance_rate}%`} icon={TrendingUp} />
            </div>
          </div>
        ) : null}
      </div>
    </Layout>
  );
};

export default AnalyticsMatrixPage;
