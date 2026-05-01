/**
 * TeacherDashboard.tsx
 *
 * Teacher-facing dashboard with:
 *  - Today's class schedule as a vertical timeline
 *  - Current period highlighted with live countdown
 *  - Quick navigation to AttendanceSheet per period
 *  - Real-time period detection polling
 */

import React, { useState } from 'react';
import {
  Clock, BookOpen, Users, ChevronRight, Activity,
  Calendar, CheckCircle, MapPin, Beaker, Bell, Wifi, WifiOff
} from 'lucide-react';
import { usePeriodDetection } from '../../hooks/useAttendanceHooks';

// ── Types ──────────────────────────────────────────────────────────────────────

export interface TeacherPeriod {
  period_id: string;
  start_time: string;
  end_time: string;
  duration_minutes?: number;
  course_code: string;
  course_name: string;
  class_id: string;
  class_name?: string;
  section?: string;
  room?: string;
  is_lab_class: boolean;
  course_color: string;
  enrolled_count?: number;
  marked_count?: number;
  is_completed?: boolean;
}

interface TeacherDashboardProps {
  facultyId: string;
  facultyName: string;
  classId: string;
  todayPeriods: TeacherPeriod[];
  onOpenSheet?: (period: TeacherPeriod) => void;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function toMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}

function nowMinutes(): number {
  const n = new Date();
  return n.getHours() * 60 + n.getMinutes();
}

function periodState(p: TeacherPeriod): 'past' | 'active' | 'upcoming' {
  const now = nowMinutes();
  const start = toMinutes(p.start_time);
  const end   = toMinutes(p.end_time);
  if (now >= end)   return 'past';
  if (now >= start) return 'active';
  return 'upcoming';
}

function minsUntilStart(p: TeacherPeriod): number {
  return Math.max(0, toMinutes(p.start_time) - nowMinutes());
}

function minsRemaining(p: TeacherPeriod): number {
  return Math.max(0, toMinutes(p.end_time) - nowMinutes());
}

function fmt12(t: string): string {
  const [h, m] = t.split(':').map(Number);
  const ampm = h < 12 ? 'AM' : 'PM';
  const h12  = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${m.toString().padStart(2, '0')} ${ampm}`;
}

// ── Countdown hook ─────────────────────────────────────────────────────────────

function useInterval(cb: () => void, delay: number) {
  React.useEffect(() => {
    const id = setInterval(cb, delay);
    return () => clearInterval(id);
  }, [cb, delay]);
}

// ── Period timeline card ───────────────────────────────────────────────────────

interface PeriodCardProps {
  period: TeacherPeriod;
  state: 'past' | 'active' | 'upcoming';
  isFirst: boolean;
  isLast: boolean;
  onOpen?: () => void;
}

function PeriodTimelineCard({ period, state, isFirst, isLast, onOpen }: PeriodCardProps) {
  const [tick, setTick] = useState(0);
  useInterval(() => setTick(t => t + 1), 30_000);

  const isDone    = state === 'past';
  const isActive  = state === 'active';
  const isUpcoming = state === 'upcoming';

  const borderColor  = isActive ? period.course_color : isDone ? '#e2e8f0' : '#c7d2fe';
  const dotColor     = isActive ? period.course_color : isDone ? '#94a3b8' : '#a5b4fc';
  const cardBg       = isActive
    ? `linear-gradient(135deg, ${period.course_color}18 0%, ${period.course_color}08 100%)`
    : isDone ? '#f8fafc' : '#fff';
  const opacity = isDone ? 0.65 : 1;

  const markedRatio = period.enrolled_count
    ? `${period.marked_count ?? 0}/${period.enrolled_count}`
    : null;
  const allMarked = period.enrolled_count && period.marked_count === period.enrolled_count;

  return (
    <div style={{ display: 'flex', gap: '0', opacity }}>
      {/* Timeline spine */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '32px', flexShrink: 0 }}>
        {/* Top connector */}
        <div style={{ width: '2px', flex: isFirst ? '0 0 16px' : '0 0 8px', background: isFirst ? 'transparent' : '#e2e8f0' }} />
        {/* Dot */}
        <div style={{
          width: isActive ? '14px' : '10px', height: isActive ? '14px' : '10px',
          borderRadius: '50%', background: dotColor, flexShrink: 0,
          boxShadow: isActive ? `0 0 0 4px ${period.course_color}30` : 'none',
          transition: 'all 0.3s',
          zIndex: 1,
        }}>
          {isDone && <CheckCircle size={10} style={{ color: '#94a3b8', margin: '0px' }} />}
        </div>
        {/* Bottom connector */}
        <div style={{ width: '2px', flex: isLast ? '0 0 8px' : 1, background: isLast ? 'transparent' : '#e2e8f0' }} />
      </div>

      {/* Card */}
      <div style={{ flex: 1, paddingBottom: isLast ? '0' : '12px', paddingTop: '2px' }}>
        <div style={{
          borderRadius: '16px',
          border: `2px solid ${borderColor}`,
          background: cardBg,
          padding: '14px 16px',
          transition: 'all 0.2s',
          boxShadow: isActive ? `0 6px 24px ${period.course_color}25` : '0 1px 4px rgba(0,0,0,0.04)',
          cursor: onOpen ? 'pointer' : 'default',
        }}
          onClick={onOpen}
          onMouseEnter={e => { if (onOpen) (e.currentTarget as HTMLElement).style.transform = 'translateX(3px)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.transform = 'none'; }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
            {/* Left info */}
            <div style={{ flex: 1, minWidth: 0 }}>
              {/* Time row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', fontFamily: 'monospace' }}>
                  {fmt12(period.start_time)} – {fmt12(period.end_time)}
                </span>
                {period.duration_minutes && (
                  <span style={{ fontSize: '0.65rem', color: '#c4cdd6', fontFamily: 'monospace' }}>
                    ({period.duration_minutes}m)
                  </span>
                )}
                {isActive && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.62rem', padding: '2px 7px', borderRadius: '99px', background: period.course_color + '20', color: period.course_color, fontWeight: 700, letterSpacing: '0.06em' }}>
                    <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: period.course_color, animation: 'pulse 1.5s infinite' }} />
                    LIVE
                  </span>
                )}
                {isUpcoming && minsUntilStart(period) <= 15 && (
                  <span style={{ fontSize: '0.62rem', padding: '2px 7px', borderRadius: '99px', background: '#EEF2FF', color: '#6366F1', fontWeight: 700 }}>
                    in {minsUntilStart(period)}m
                  </span>
                )}
              </div>

              {/* Course name */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <div style={{
                  width: '28px', height: '28px', borderRadius: '8px', flexShrink: 0,
                  background: period.course_color + '22', display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {period.is_lab_class
                    ? <Beaker size={14} style={{ color: period.course_color }} />
                    : <BookOpen size={14} style={{ color: period.course_color }} />
                  }
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.72rem', fontWeight: 800, color: period.course_color, letterSpacing: '0.06em' }}>
                      {period.course_code}
                    </span>
                    {period.is_lab_class && (
                      <span style={{ fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px', background: '#8B5CF615', color: '#8B5CF6', fontWeight: 700 }}>LAB</span>
                    )}
                  </div>
                  <p style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1e293b', lineHeight: 1.2 }}>{period.course_name}</p>
                </div>
              </div>

              {/* Meta row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
                {period.class_id && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#64748b' }}>
                    <Users size={11} />
                    {period.class_name ?? period.class_id}
                    {period.section && ` · ${period.section}`}
                  </span>
                )}
                {period.room && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: '#94a3b8' }}>
                    <MapPin size={11} /> {period.room}
                  </span>
                )}
                {markedRatio && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', color: allMarked ? '#22C55E' : '#F59E0B', fontWeight: allMarked ? 700 : 500 }}>
                    <CheckCircle size={11} /> {markedRatio} marked
                  </span>
                )}
              </div>
            </div>

            {/* Right actions */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px', flexShrink: 0 }}>
              {/* Progress of marking */}
              {period.enrolled_count && period.enrolled_count > 0 && (
                <div style={{ width: '90px', textAlign: 'right' }}>
                  <p style={{ fontSize: '0.62rem', color: '#94a3b8', marginBottom: '3px' }}>
                    {Math.round(((period.marked_count ?? 0) / period.enrolled_count) * 100)}% marked
                  </p>
                  <div style={{ height: '4px', borderRadius: '99px', background: '#e2e8f0', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${Math.round(((period.marked_count ?? 0) / period.enrolled_count) * 100)}%`,
                      background: allMarked ? '#22C55E' : period.course_color,
                      borderRadius: '99px', transition: 'width 0.6s ease',
                    }} />
                  </div>
                </div>
              )}

              {/* Action button */}
              {(isActive || isUpcoming || isDone) && onOpen && (
                <button
                  onClick={e => { e.stopPropagation(); onOpen(); }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '5px',
                    padding: '6px 12px', borderRadius: '10px', fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer',
                    background: isActive
                      ? `linear-gradient(135deg, ${period.course_color} 0%, ${period.course_color}cc 100%)`
                      : '#EEF2FF',
                    color: isActive ? '#fff' : '#6366F1',
                    border: isActive ? 'none' : '1.5px solid #A5B4FC',
                    boxShadow: isActive ? `0 3px 10px ${period.course_color}40` : 'none',
                  }}
                >
                  {isDone ? 'Review' : 'Take Attendance'}
                  <ChevronRight size={13} />
                </button>
              )}

              {/* Countdown for active */}
              {isActive && (
                <p style={{ fontSize: '0.7rem', fontWeight: 700, color: period.course_color, fontFamily: 'monospace' }}>
                  {minsRemaining(period)}m left
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Compact KPI strip ──────────────────────────────────────────────────────────

function KPIStrip({ periods }: { periods: TeacherPeriod[] }) {
  const total     = periods.length;
  const completed = periods.filter(p => periodState(p) === 'past' || p.is_completed).length;
  const active    = periods.filter(p => periodState(p) === 'active').length;
  const upcoming  = periods.filter(p => periodState(p) === 'upcoming').length;
  const totalStudents = periods.reduce((a, p) => a + (p.enrolled_count ?? 0), 0);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '10px' }}>
      {[
        { label: 'Total Periods', val: total, hex: '#6366F1', bg: '#EEF2FF' },
        { label: 'Completed',     val: completed, hex: '#22C55E', bg: '#F0FDF4' },
        { label: 'Active Now',    val: active,    hex: '#F59E0B', bg: '#FFFBEB' },
        { label: 'Upcoming',      val: upcoming,  hex: '#94A3B8', bg: '#F8FAFC' },
        { label: 'Total Students',val: totalStudents, hex: '#8B5CF6', bg: '#F5F3FF' },
      ].map(({ label, val, hex, bg }) => (
        <div key={label} style={{ padding: '12px 14px', borderRadius: '14px', background: bg, border: `1px solid ${hex}25` }}>
          <p style={{ fontSize: '1.4rem', fontWeight: 900, color: hex, lineHeight: 1 }}>{val}</p>
          <p style={{ fontSize: '0.65rem', color: '#94a3b8', marginTop: '3px', fontWeight: 500 }}>{label}</p>
        </div>
      ))}
    </div>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────────

export const TeacherDashboard: React.FC<TeacherDashboardProps> = ({
  facultyId,
  facultyName,
  classId,
  todayPeriods,
  onOpenSheet,
}) => {
  const [tick, setTick] = useState(0);
  useInterval(() => setTick(t => t + 1), 60_000); // refresh every minute

  const { activePeriod, lastChecked, error: periodErr } = usePeriodDetection({
    classId,
    enabled: !!classId,
    pollIntervalMs: 30_000,
  });

  const sorted = [...todayPeriods].sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time));
  const today  = new Date();
  const dateStr = today.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p style={{ fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '4px' }}>
            Teacher Portal
          </p>
          <h1 style={{ fontSize: '1.7rem', fontWeight: 900, color: '#1e293b', lineHeight: 1.1 }}>
            Welcome, {facultyName.split(' ')[0]}
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '5px' }}>
            <Calendar size={13} style={{ color: '#94a3b8' }} />
            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>{dateStr}</p>
          </div>
        </div>

        {/* Sync badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '6px 12px', borderRadius: '99px',
          background: lastChecked ? '#F0FDF4' : '#FEF2F2',
          border: `1px solid ${lastChecked ? '#BBF7D0' : '#FECACA'}`,
        }}>
          {lastChecked ? <Wifi size={12} style={{ color: '#22C55E' }} /> : <WifiOff size={12} style={{ color: '#EF4444' }} />}
          <span style={{ fontSize: '0.65rem', fontWeight: 600, color: lastChecked ? '#16A34A' : '#DC2626' }}>
            {lastChecked
              ? `Period check: ${lastChecked.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}`
              : 'Period detection offline'}
          </span>
        </div>
      </div>

      {/* Active period banner */}
      {activePeriod?.is_active && activePeriod.period && (
        <div style={{
          borderRadius: '18px',
          background: `linear-gradient(135deg, ${activePeriod.period.course_color}22 0%, ${activePeriod.period.course_color}0c 100%)`,
          border: `2px solid ${activePeriod.period.course_color}50`,
          padding: '16px 20px',
          display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap',
        }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '14px', flexShrink: 0,
            background: activePeriod.period.course_color,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Activity size={22} style={{ color: '#fff' }} />
          </div>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: activePeriod.period.course_color, marginBottom: '2px' }}>
              Currently Teaching
            </p>
            <p style={{ fontSize: '1rem', fontWeight: 800, color: '#1e293b' }}>{activePeriod.period.course_name}</p>
            <p style={{ fontSize: '0.75rem', color: '#64748b' }}>{activePeriod.message}</p>
          </div>
          {onOpenSheet && sorted.find(p => p.period_id === activePeriod.period?.period_id) && (
            <button
              onClick={() => {
                const found = sorted.find(p => p.period_id === activePeriod.period?.period_id);
                if (found) onOpenSheet(found);
              }}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px', padding: '10px 18px',
                borderRadius: '12px', fontSize: '0.82rem', fontWeight: 700, cursor: 'pointer',
                background: activePeriod.period.course_color, color: '#fff', border: 'none',
                boxShadow: `0 4px 14px ${activePeriod.period.course_color}50`,
              }}
            >
              Take Attendance <ChevronRight size={14} />
            </button>
          )}
        </div>
      )}

      {/* KPI strip */}
      <KPIStrip periods={sorted} />

      {/* Timeline */}
      <div>
        <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Clock size={16} style={{ color: '#6366F1' }} />
          Today's Schedule
        </h2>

        {sorted.length === 0 ? (
          <div style={{ padding: '48px', textAlign: 'center', borderRadius: '16px', background: '#f8fafc', border: '1px dashed #e2e8f0' }}>
            <Calendar size={32} style={{ color: '#cbd5e1', margin: '0 auto 12px' }} />
            <p style={{ color: '#94a3b8', fontWeight: 500 }}>No classes scheduled for today</p>
          </div>
        ) : (
          <div style={{ paddingLeft: '8px' }}>
            {sorted.map((period, i) => (
              <PeriodTimelineCard
                key={period.period_id}
                period={period}
                state={periodState(period)}
                isFirst={i === 0}
                isLast={i === sorted.length - 1}
                onOpen={onOpenSheet ? () => onOpenSheet(period) : undefined}
              />
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes spin  { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default TeacherDashboard;
