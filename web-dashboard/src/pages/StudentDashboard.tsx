/**
 * StudentDashboard.tsx
 *
 * Enhanced student-facing dashboard with:
 *  - Today's timetable as large color-coded status cards
 *  - Active period with live countdown
 *  - Overall attendance stats with warning badges
 *  - Quick-access links to history and timetable
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Clock, BookOpen, AlertTriangle, CheckCircle, XCircle,
  Activity, TrendingUp, Calendar, ChevronRight, Wifi, WifiOff
} from 'lucide-react';
import { useStudentAttendance, usePeriodDetection, type PeriodCard } from '../hooks/useAttendanceHooks';

// ── Helpers ────────────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
  present: { label: 'Present', hex: '#22C55E', bg: 'rgba(34,197,94,0.12)', border: 'rgba(34,197,94,0.30)', icon: CheckCircle },
  absent:  { label: 'Absent',  hex: '#EF4444', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.30)',  icon: XCircle },
  late:    { label: 'Late',    hex: '#F59E0B', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.30)', icon: Clock },
  pending: { label: 'Pending', hex: '#94A3B8', bg: 'rgba(148,163,184,0.10)',border: 'rgba(148,163,184,0.25)',icon: Activity },
};

function formatCountdown(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s.toString().padStart(2, '0')}s`;
  return `${s}s`;
}

// ── Countdown hook ─────────────────────────────────────────────────────────────

function useCountdown(initialSeconds: number | undefined) {
  const [secs, setSecs] = useState(initialSeconds ?? 0);
  useEffect(() => {
    setSecs(initialSeconds ?? 0);
  }, [initialSeconds]);
  useEffect(() => {
    if (!secs) return;
    const id = setInterval(() => setSecs(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [secs]);
  return secs;
}

// ── Period Card ────────────────────────────────────────────────────────────────

function PeriodStatusCard({ period, isActive }: { period: PeriodCard; isActive: boolean }) {
  const status = (period.status as keyof typeof STATUS_CONFIG) ?? 'pending';
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  const Icon = cfg.icon;
  const countdown = useCountdown(isActive ? period.countdown_seconds : undefined);

  return (
    <div
      style={{
        borderRadius: '16px',
        border: `2px solid ${isActive ? period.course_color : cfg.border}`,
        background: isActive
          ? `linear-gradient(135deg, ${period.course_color}18 0%, ${cfg.bg} 100%)`
          : cfg.bg,
        padding: '18px 20px',
        position: 'relative',
        overflow: 'hidden',
        transition: 'all 0.3s ease',
        boxShadow: isActive ? `0 8px 32px ${period.course_color}30` : '0 2px 8px rgba(0,0,0,0.06)',
      }}
    >
      {/* Course color stripe */}
      <div style={{
        position: 'absolute', top: 0, left: 0, width: '4px', height: '100%',
        background: period.course_color, borderRadius: '16px 0 0 16px',
      }} />

      {isActive && (
        <div style={{
          position: 'absolute', top: '12px', right: '12px',
          background: '#EF4444', color: '#fff', fontSize: '0.6rem',
          fontWeight: 700, letterSpacing: '0.1em', padding: '2px 8px',
          borderRadius: '99px', display: 'flex', alignItems: 'center', gap: '4px',
        }}>
          <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#fff', animation: 'pulse 1.5s infinite' }} />
          LIVE
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', paddingLeft: '12px' }}>
        <div style={{
          width: '42px', height: '42px', borderRadius: '12px', flexShrink: 0,
          background: period.course_color + '22', display: 'flex', alignItems: 'center',
          justifyContent: 'center',
        }}>
          <BookOpen size={20} style={{ color: period.course_color }} />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: period.course_color }}>
              {period.course_code}
            </span>
            {period.is_lab_class && (
              <span style={{ fontSize: '0.6rem', padding: '1px 6px', borderRadius: '99px', background: '#8B5CF622', color: '#8B5CF6', fontWeight: 600 }}>LAB</span>
            )}
          </div>
          <p style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', marginBottom: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {period.course_name}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.75rem', color: '#64748b' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={12} />
              {period.start_time} – {period.end_time}
            </span>
            <span>{period.faculty_name}</span>
            {period.room && <span>📍 {period.room}</span>}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px', flexShrink: 0 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '4px 10px', borderRadius: '99px',
            background: cfg.bg, border: `1px solid ${cfg.border}`,
          }}>
            <Icon size={12} style={{ color: cfg.hex }} />
            <span style={{ fontSize: '0.7rem', fontWeight: 700, color: cfg.hex }}>{cfg.label}</span>
          </div>
          {isActive && countdown > 0 && (
            <div style={{ textAlign: 'right' }}>
              <p style={{ fontSize: '0.6rem', color: '#94a3b8', marginBottom: '1px' }}>ends in</p>
              <p style={{ fontSize: '1rem', fontWeight: 800, color: period.course_color, fontFamily: 'monospace' }}>
                {formatCountdown(countdown)}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Stats card ─────────────────────────────────────────────────────────────────

function OverallStatsCard({ overall }: { overall: ReturnType<typeof useStudentAttendance>['summary'] extends null ? never : ReturnType<typeof useStudentAttendance>['summary']['overall'] }) {
  const pct = overall.percentage;
  const band = overall.band;
  const color = band === 'safe' ? '#22C55E' : band === 'warning' ? '#F59E0B' : '#EF4444';

  return (
    <div style={{
      borderRadius: '20px',
      background: `linear-gradient(135deg, ${color}10 0%, ${color}06 100%)`,
      border: `1.5px solid ${color}30`,
      padding: '24px',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div>
          <p style={{ fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '6px' }}>
            Overall Attendance
          </p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
            <span style={{ fontSize: '2.8rem', fontWeight: 900, color, lineHeight: 1, fontFamily: 'monospace' }}>
              {pct.toFixed(1)}
            </span>
            <span style={{ fontSize: '1.4rem', fontWeight: 700, color: color + 'aa' }}>%</span>
          </div>
        </div>
        <div style={{
          width: '56px', height: '56px', borderRadius: '16px',
          background: color + '18', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <TrendingUp size={26} style={{ color }} />
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ position: 'relative', marginBottom: '16px' }}>
        <div style={{ height: '10px', borderRadius: '99px', background: '#e2e8f0', overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: '99px',
            width: `${Math.min(100, pct)}%`,
            background: `linear-gradient(90deg, ${color}80 0%, ${color} 100%)`,
            transition: 'width 1s ease',
          }} />
        </div>
        {/* 75% marker */}
        <div style={{
          position: 'absolute', left: '75%', top: '-4px',
          width: '2px', height: '18px', background: '#94a3b8', borderRadius: '1px',
        }} />
        <span style={{ position: 'absolute', left: 'calc(75% + 4px)', top: '-2px', fontSize: '0.6rem', color: '#94a3b8', fontWeight: 600 }}>75%</span>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
        {[
          { label: 'Present', val: overall.present + overall.late, hex: '#22C55E' },
          { label: 'Absent', val: overall.absent, hex: '#EF4444' },
          { label: 'Total', val: overall.total, hex: '#6366F1' },
        ].map(({ label, val, hex }) => (
          <div key={label} style={{ textAlign: 'center', padding: '10px', borderRadius: '12px', background: '#ffffff60' }}>
            <p style={{ fontSize: '1.2rem', fontWeight: 800, color: hex, lineHeight: 1 }}>{val}</p>
            <p style={{ fontSize: '0.65rem', color: '#94a3b8', marginTop: '3px', fontWeight: 500 }}>{label}</p>
          </div>
        ))}
      </div>

      {band !== 'safe' && (
        <div style={{
          marginTop: '14px', display: 'flex', alignItems: 'center', gap: '8px',
          padding: '10px 14px', borderRadius: '12px',
          background: band === 'danger' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
          border: `1px solid ${band === 'danger' ? 'rgba(239,68,68,0.25)' : 'rgba(245,158,11,0.25)'}`,
        }}>
          <AlertTriangle size={14} style={{ color: band === 'danger' ? '#EF4444' : '#F59E0B', flexShrink: 0 }} />
          <p style={{ fontSize: '0.72rem', color: band === 'danger' ? '#DC2626' : '#B45309', fontWeight: 600 }}>
            {band === 'danger' ? '⚠ Below 75% threshold — risk of debarment' : 'Attendance between 75–85% — attend regularly'}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

interface StudentDashboardProps {
  studentId: string;
  classId?: string;
  onNavigate?: (page: 'timetable' | 'history' | 'warnings') => void;
}

export const StudentDashboard: React.FC<StudentDashboardProps> = ({
  studentId,
  classId,
  onNavigate,
}) => {
  const { dashboard, summary, warnings, loading, error, refetch } = useStudentAttendance({
    studentId,
    enabled: !!studentId,
  });

  const { activePeriod, lastChecked, error: periodError } = usePeriodDetection({
    classId: classId ?? '',
    enabled: !!classId,
  });

  const now = new Date();
  const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '320px', flexDirection: 'column', gap: '14px' }}>
      <div style={{ width: '36px', height: '36px', border: '3px solid #e2e8f0', borderTopColor: '#6366F1', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Loading your dashboard…</p>
    </div>
  );

  if (error) return (
    <div style={{ padding: '24px', borderRadius: '16px', background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', display: 'flex', alignItems: 'center', gap: '10px' }}>
      <AlertTriangle size={18} />
      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{error}</span>
      <button onClick={refetch} style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#6366F1', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer' }}>Retry</button>
    </div>
  );

  const periods = dashboard?.periods_today ?? [];
  const activeP = dashboard?.active_period;
  const summary_counts = dashboard?.summary ?? { total: 0, present: 0, absent: 0, late: 0, pending: 0 };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <p style={{ fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '4px' }}>
            Student Portal
          </p>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#1e293b', lineHeight: 1.1 }}>
            {dashboard?.day_name ?? 'Today'}'s Overview
          </h1>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '4px' }}>
            {dashboard?.today_date} · {timeStr}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '99px', background: lastChecked ? '#f0fdf4' : '#fef2f2', border: `1px solid ${lastChecked ? '#bbf7d0' : '#fecaca'}` }}>
          {lastChecked ? <Wifi size={12} style={{ color: '#22c55e' }} /> : <WifiOff size={12} style={{ color: '#ef4444' }} />}
          <span style={{ fontSize: '0.65rem', fontWeight: 600, color: lastChecked ? '#16a34a' : '#dc2626' }}>
            {lastChecked ? `Synced ${lastChecked.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : 'Offline'}
          </span>
        </div>
      </div>

      {/* Summary pills */}
      {periods.length > 0 && (
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {Object.entries(summary_counts).filter(([k]) => k !== 'total').map(([key, val]) => {
            const cfg = STATUS_CONFIG[key as keyof typeof STATUS_CONFIG];
            if (!cfg || val === 0) return null;
            return (
              <div key={key} style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '5px 12px', borderRadius: '99px',
                background: cfg.bg, border: `1px solid ${cfg.border}`,
              }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: cfg.hex }} />
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: cfg.hex }}>{val} {cfg.label}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Active period banner */}
      {activeP && (
        <div style={{
          borderRadius: '16px', padding: '16px 20px',
          background: `linear-gradient(135deg, ${activeP.course_color}20 0%, ${activeP.course_color}08 100%)`,
          border: `2px solid ${activeP.course_color}50`,
          display: 'flex', alignItems: 'center', gap: '14px',
        }}>
          <div style={{
            width: '44px', height: '44px', borderRadius: '12px', flexShrink: 0,
            background: activeP.course_color, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Activity size={22} style={{ color: '#fff' }} />
          </div>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: activeP.course_color, marginBottom: '2px' }}>
              Now In Session
            </p>
            <p style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b' }}>{activeP.course_name}</p>
            <p style={{ fontSize: '0.75rem', color: '#64748b' }}>{activeP.faculty_name} · {activeP.start_time} – {activeP.end_time}</p>
          </div>
          {activeP.countdown_seconds != null && (
            <div style={{ textAlign: 'right' }}>
              <p style={{ fontSize: '0.6rem', color: '#94a3b8' }}>Ends in</p>
              <CountdownDisplay seconds={activeP.countdown_seconds} color={activeP.course_color} />
            </div>
          )}
        </div>
      )}

      {/* Today's periods */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Calendar size={16} style={{ color: '#6366F1' }} />
            Today's Classes
          </h2>
          {onNavigate && (
            <button
              onClick={() => onNavigate('timetable')}
              style={{ fontSize: '0.75rem', color: '#6366F1', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              Full Week <ChevronRight size={14} />
            </button>
          )}
        </div>

        {periods.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', borderRadius: '16px', background: '#f8fafc', border: '1px dashed #e2e8f0' }}>
            <Calendar size={32} style={{ color: '#cbd5e1', margin: '0 auto 12px' }} />
            <p style={{ color: '#94a3b8', fontSize: '0.85rem', fontWeight: 500 }}>No classes scheduled for today</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {periods.map((p) => (
              <PeriodStatusCard key={p.period_id} period={p} isActive={!!(activeP?.period_id === p.period_id)} />
            ))}
          </div>
        )}
      </div>

      {/* Overall stats */}
      {summary?.overall && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={16} style={{ color: '#6366F1' }} />
              Attendance Stats
            </h2>
            {onNavigate && (
              <button
                onClick={() => onNavigate('history')}
                style={{ fontSize: '0.75rem', color: '#6366F1', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                View History <ChevronRight size={14} />
              </button>
            )}
          </div>
          <OverallStatsCard overall={summary.overall} />
        </div>
      )}

      {/* Warnings */}
      {warnings?.has_critical_warning && (
        <div style={{
          borderRadius: '16px', padding: '16px 20px',
          background: 'rgba(239,68,68,0.06)', border: '1.5px solid rgba(239,68,68,0.25)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
            <AlertTriangle size={18} style={{ color: '#EF4444' }} />
            <p style={{ fontSize: '0.9rem', fontWeight: 700, color: '#DC2626' }}>Critical Attendance Warning</p>
          </div>
          {warnings.messages.map((msg, i) => (
            <p key={i} style={{ fontSize: '0.8rem', color: '#7f1d1d', marginBottom: '6px', paddingLeft: '28px', lineHeight: 1.5 }}>{msg}</p>
          ))}
          {onNavigate && (
            <button
              onClick={() => onNavigate('warnings')}
              style={{ marginLeft: '28px', marginTop: '8px', fontSize: '0.8rem', color: '#DC2626', fontWeight: 700, background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
            >
              View details →
            </button>
          )}
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
      `}</style>
    </div>
  );
};

// ── Countdown display sub-component ───────────────────────────────────────────

function CountdownDisplay({ seconds: initial, color }: { seconds: number; color: string }) {
  const secs = useCountdown(initial);
  return (
    <p style={{ fontSize: '1.1rem', fontWeight: 900, color, fontFamily: 'monospace' }}>
      {formatCountdown(secs)}
    </p>
  );
}

export default StudentDashboard;
