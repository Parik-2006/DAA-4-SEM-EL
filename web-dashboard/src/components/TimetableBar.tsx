import React from 'react';
import { Clock, CheckCircle2, CalendarDays, Lock, PlayCircle, ArrowRight } from 'lucide-react';
import type { PeriodInfo, AttendanceWindowInfo } from '@/services/api';

interface TimetableBarProps {
  periods: PeriodInfo[];
  selectedPeriodId?: string | null;
  onSelectPeriod: (period: PeriodInfo) => void;
  windowInfo?: AttendanceWindowInfo | null;
}

function toMinutes(value: string): number {
  const [hours, minutes] = value.split(':').map(Number);
  return hours * 60 + minutes;
}

function getPeriodPhase(period: PeriodInfo): 'active' | 'upcoming' | 'past' {
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();
  const startMinutes = toMinutes(period.start_time);
  const endMinutes = toMinutes(period.end_time);

  if (currentMinutes >= endMinutes) return 'past';
  if (currentMinutes >= startMinutes) return 'active';
  return 'upcoming';
}

export const TimetableBar: React.FC<TimetableBarProps> = ({
  periods,
  selectedPeriodId,
  onSelectPeriod,
  windowInfo,
}) => {
  const activeLabel = windowInfo?.message ?? windowInfo?.phase ?? 'Today';

  return (
    <div className="rounded-3xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50 px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
            <CalendarDays size={14} />
            Timetable
          </div>
          <h2 className="mt-2 text-xl font-black text-slate-900">{activeLabel}</h2>
          <p className="mt-1 text-sm text-slate-500">
            Pick the period that matches the current class window. Past periods are kept visible for reference.
          </p>
        </div>

        {windowInfo?.phase && (
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 shadow-sm">
            {windowInfo.phase === 'locked' ? <Lock size={14} className="text-red-600" /> : <PlayCircle size={14} className="text-emerald-600" />}
            <span className="capitalize">{windowInfo.phase}</span>
          </div>
        )}
      </div>

      <div className="grid gap-3 px-6 py-5 md:grid-cols-2 xl:grid-cols-3">
        {periods.map((period) => {
          const phase = getPeriodPhase(period);
          const selected = selectedPeriodId === period.period_id;
          const phaseStyles =
            phase === 'active'
              ? { bg: '#ecfdf5', text: '#166534', border: '#bbf7d0' }
              : phase === 'upcoming'
              ? { bg: '#fffbeb', text: '#92400e', border: '#fde68a' }
              : { bg: '#f8fafc', text: '#64748b', border: '#e2e8f0' };

          return (
            <button
              key={period.period_id}
              type="button"
              onClick={() => onSelectPeriod(period)}
              className="rounded-2xl border p-4 text-left transition hover:-translate-y-0.5"
              style={{
                borderColor: selected ? '#4f46e5' : phaseStyles.border,
                background: selected ? 'rgba(79,70,229,0.06)' : '#fff',
                boxShadow: selected ? '0 12px 30px rgba(79,70,229,0.10)' : '0 2px 10px rgba(15,23,42,0.04)',
              }}
            >
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <p className="text-[0.65rem] font-black uppercase tracking-[0.16em] text-slate-400">
                    {period.course_code}
                  </p>
                  <h3 className="mt-1 text-sm font-bold text-slate-900">{period.course_name}</h3>
                </div>
                <div
                  className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[0.65rem] font-bold uppercase tracking-[0.12em]"
                  style={{ background: phaseStyles.bg, color: phaseStyles.text }}
                >
                  {phase === 'active' ? <CheckCircle2 size={12} /> : phase === 'past' ? <Lock size={12} /> : <ArrowRight size={12} />}
                  {phase}
                </div>
              </div>

              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Clock size={14} />
                {period.start_time} - {period.end_time}
              </div>

              <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                <span>{period.faculty_name ?? 'Faculty'}</span>
                <span>{period.room ?? 'Room not set'}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default TimetableBar;
