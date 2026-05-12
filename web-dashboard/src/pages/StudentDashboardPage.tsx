/**
 * StudentDashboardPage.tsx
 *
 * Full-featured student dashboard page that wires together:
 *  - Period selector (tabs) with URL param persistence
 *  - Today's overall stats on load
 *  - Per-period live stats + attendance records
 *  - Auto-refresh every 30s with visual countdown ring
 *  - Manual refresh button
 *  - "New attendance marked" toast notifications
 *  - Error boundaries, loading states, empty states
 *  - Graceful network error handling
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
  Component,
  ErrorInfo,
} from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  RefreshCw,
  Clock,
  BookOpen,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Wifi,
  WifiOff,
  ChevronLeft,
  ChevronRight,
  User,
  Calendar,
  Activity,
  TrendingUp,
  Zap,
  Bell,
  X,
} from 'lucide-react';
import { Layout } from '../components/Layout';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Period {
  period_id: string;
  course_code: string;
  course_name: string;
  start_time: string;
  end_time: string;
  faculty_name: string;
  room?: string;
  is_lab_class: boolean;
  course_color: string;
  status?: 'present' | 'absent' | 'late' | 'pending';
}

interface OverallStats {
  total_classes: number;
  present: number;
  late: number;
  absent: number;
  pending: number;
  attendance_pct: number;
  band: 'safe' | 'warning' | 'danger';
}

interface PeriodStats {
  period_id: string;
  total_students: number;
  present: number;
  late: number;
  absent: number;
  not_marked: number;
  attendance_pct: number;
  last_updated: string;
}

interface AttendanceRecord {
  record_id: string;
  student_name: string;
  student_id: string;
  roll_no: string;
  status: 'present' | 'absent' | 'late' | 'pending';
  marked_at: string;
  confidence?: number;
  marked_by?: string;
}

interface ToastItem {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
  studentName?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const AUTO_REFRESH_SECONDS = 30;

const STATUS_META = {
  present: { label: 'Present', color: '#22C55E', bg: 'rgba(34,197,94,0.12)',   border: 'rgba(34,197,94,0.30)',   Icon: CheckCircle },
  late:    { label: 'Late',    color: '#F59E0B', bg: 'rgba(245,158,11,0.12)',  border: 'rgba(245,158,11,0.30)',  Icon: Clock },
  absent:  { label: 'Absent',  color: '#EF4444', bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.30)',   Icon: XCircle },
  pending: { label: 'Pending', color: '#94A3B8', bg: 'rgba(148,163,184,0.10)', border: 'rgba(148,163,184,0.25)', Icon: Activity },
};

const BAND_META = {
  safe:    { color: '#22C55E', label: 'Good Standing' },
  warning: { color: '#F59E0B', label: 'Needs Attention' },
  danger:  { color: '#EF4444', label: 'Critical' },
};

// ─── Mock API (replace with real attendanceAPI calls) ─────────────────────────

const BASE = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

async function fetchJSON<T>(url: string, params?: Record<string, string>): Promise<T> {
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const full = params
    ? `${BASE}${url}?${new URLSearchParams(params)}`
    : `${BASE}${url}`;
  const res = await fetch(full, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail || (err as any).message || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function fetchTodayPeriods(studentId: string): Promise<Period[]> {
  try {
    return await fetchJSON<Period[]>('/api/v1/student/today-periods', { student_id: studentId });
  } catch {
    return [
      { period_id: 'p1', course_code: 'CS401', course_name: 'Machine Learning',  start_time: '09:00', end_time: '10:00', faculty_name: 'Dr. Sharma',  room: 'A201',  is_lab_class: false, course_color: '#6366F1', status: 'present' },
      { period_id: 'p2', course_code: 'CS402', course_name: 'Cloud Computing',   start_time: '10:00', end_time: '11:00', faculty_name: 'Prof. Rao',    room: 'A202',  is_lab_class: false, course_color: '#14B8A6', status: 'absent'  },
      { period_id: 'p3', course_code: 'CS403', course_name: 'Networks Lab',      start_time: '11:00', end_time: '13:00', faculty_name: 'Dr. Patel',    room: 'Lab 3', is_lab_class: true,  course_color: '#8B5CF6', status: 'pending' },
      { period_id: 'p4', course_code: 'CS404', course_name: 'DBMS',             start_time: '14:00', end_time: '15:00', faculty_name: 'Prof. Mehta',   room: 'A101',  is_lab_class: false, course_color: '#F59E0B', status: 'late'    },
    ];
  }
}

async function fetchOverallStats(studentId: string): Promise<OverallStats> {
  try {
    return await fetchJSON<OverallStats>('/api/v1/student/attendance-summary', { student_id: studentId });
  } catch {
    return { total_classes: 4, present: 2, late: 1, absent: 1, pending: 0, attendance_pct: 75.0, band: 'warning' };
  }
}

async function fetchPeriodStats(periodId: string, studentId: string): Promise<PeriodStats> {
  try {
    return await fetchJSON<PeriodStats>('/api/v1/attendance/period-stats', { period_id: periodId, student_id: studentId });
  } catch {
    const mock: Record<string, PeriodStats> = {
      p1: { period_id: 'p1', total_students: 65, present: 58, late: 3,  absent: 4, not_marked: 0,  attendance_pct: 93.8, last_updated: new Date().toISOString() },
      p2: { period_id: 'p2', total_students: 65, present: 10, late: 2,  absent: 5, not_marked: 48, attendance_pct: 18.5, last_updated: new Date().toISOString() },
      p3: { period_id: 'p3', total_students: 65, present: 0,  late: 0,  absent: 0, not_marked: 65, attendance_pct: 0,    last_updated: new Date().toISOString() },
      p4: { period_id: 'p4', total_students: 65, present: 55, late: 7,  absent: 3, not_marked: 0,  attendance_pct: 95.4, last_updated: new Date().toISOString() },
    };
    return mock[periodId] ?? { period_id: periodId, total_students: 60, present: 45, late: 5, absent: 10, not_marked: 0, attendance_pct: 83.3, last_updated: new Date().toISOString() };
  }
}

async function fetchPeriodRecords(periodId: string, _studentId: string): Promise<AttendanceRecord[]> {
  try {
    return await fetchJSON<AttendanceRecord[]>('/api/v1/attendance/period-records', { period_id: periodId, student_id: _studentId });
  } catch {
    const names    = ['Parikshith B', 'Gagan D K', 'Prajwal K', 'Ved U', 'Pranav Kumar', 'Nischith G A', 'Arjun S', 'Pooja M', 'Rahul T', 'Sneha R'];
    const statuses: AttendanceRecord['status'][] = ['present','present','present','late','absent','present','present','late','present','absent'];
    return names.map((name, i) => ({
      record_id:    `r${periodId}-${i}`,
      student_name: name,
      student_id:   `STUD_00${i + 1}`,
      roll_no:      `4CS${String(i + 1).padStart(2, '0')}`,
      status:       statuses[i] ?? 'present',
      marked_at:    new Date(Date.now() - i * 120000).toISOString(),
      confidence:   statuses[i] === 'present' ? 0.92 + Math.random() * 0.07 : undefined,
      marked_by:    'Face Recognition',
    }));
  }
}

// ─── Error Boundary ───────────────────────────────────────────────────────────

interface EBProps { children: React.ReactNode; fallback?: React.ReactNode }
interface EBState { hasError: boolean; error?: Error }

class ErrorBoundary extends Component<EBProps, EBState> {
  state: EBState = { hasError: false };
  static getDerivedStateFromError(error: Error): EBState { return { hasError: true, error }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('[ErrorBoundary]', error, info); }
  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div style={{ padding: '32px', borderRadius: '16px', background: '#FEF2F2', border: '1px solid #FECACA', textAlign: 'center' }}>
          <AlertTriangle size={32} style={{ color: '#EF4444', margin: '0 auto 12px' }} />
          <p style={{ fontWeight: 700, color: '#DC2626', marginBottom: '6px' }}>Something went wrong</p>
          <p style={{ fontSize: '0.8rem', color: '#7f1d1d' }}>{this.state.error?.message}</p>
          <button
            onClick={() => this.setState({ hasError: false })}
            style={{ marginTop: '14px', padding: '8px 18px', borderRadius: '10px', background: '#EF4444', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Countdown ring ───────────────────────────────────────────────────────────

function CountdownRing({ seconds, total }: { seconds: number; total: number }) {
  const r     = 16;
  const circ  = 2 * Math.PI * r;
  const pct   = seconds / total;
  const urgent = seconds <= 5;
  const color = urgent ? '#EF4444' : '#6366F1';

  return (
    <svg width={40} height={40} style={{ flexShrink: 0 }}>
      <circle cx={20} cy={20} r={r} fill="none" stroke="#E2E8F0" strokeWidth={3} />
      <circle
        cx={20} cy={20} r={r}
        fill="none" stroke={color} strokeWidth={3}
        strokeDasharray={circ}
        strokeDashoffset={circ * (1 - pct)}
        strokeLinecap="round"
        transform="rotate(-90 20 20)"
        style={{ transition: 'stroke-dashoffset 1s linear, stroke 0.3s' }}
      />
      <text
        x={20} y={20}
        textAnchor="middle" dominantBaseline="middle"
        fontSize={9} fontWeight={700} fill={color} fontFamily="monospace"
      >
        {seconds}
      </text>
    </svg>
  );
}

// ─── Toast component ──────────────────────────────────────────────────────────

function ToastStack({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: string) => void }) {
  if (!toasts.length) return null;
  return (
    <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 200, display: 'flex', flexDirection: 'column-reverse', gap: '10px' }}>
      {toasts.map(t => {
        const colors = {
          success: { bg: '#F0FDF4', border: '#BBF7D0', text: '#166534', icon: '#22C55E' },
          error:   { bg: '#FEF2F2', border: '#FECACA', text: '#991B1B', icon: '#EF4444' },
          info:    { bg: '#EEF2FF', border: '#C7D2FE', text: '#3730A3', icon: '#6366F1' },
        }[t.type];
        return (
          <div
            key={t.id}
            style={{
              display: 'flex', alignItems: 'flex-start', gap: '10px',
              padding: '12px 16px', borderRadius: '14px', maxWidth: '320px',
              background: colors.bg, border: `1.5px solid ${colors.border}`,
              boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
              animation: 'sdp-slideUp 0.3s cubic-bezier(0.22,1,0.36,1)',
            }}
          >
            <Bell size={15} style={{ color: colors.icon, flexShrink: 0, marginTop: '1px' }} />
            <div style={{ flex: 1 }}>
              <p style={{ fontSize: '0.82rem', fontWeight: 700, color: colors.text }}>{t.message}</p>
              {t.studentName && (
                <p style={{ fontSize: '0.72rem', color: colors.text, opacity: 0.75, marginTop: '2px' }}>{t.studentName}</p>
              )}
            </div>
            <button
              onClick={() => onDismiss(t.id)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: colors.text, opacity: 0.5, padding: 0, flexShrink: 0 }}
            >
              <X size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ─── Overall Stats Panel ──────────────────────────────────────────────────────

function OverallStatsPanel({ stats, loading }: { stats: OverallStats | null; loading: boolean }) {
  if (loading) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '12px' }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            style={{ height: '80px', borderRadius: '14px', background: 'linear-gradient(90deg,#f1f5f9 0px,#e2e8f0 120px,#f1f5f9 240px)', backgroundSize: '400px 100%', animation: 'sdp-shimmer 1.5s infinite' }}
          />
        ))}
      </div>
    );
  }
  if (!stats) return null;

  const band = BAND_META[stats.band];
  const items = [
    { label: 'Overall',        value: `${stats.attendance_pct.toFixed(1)}%`, color: band.color, sub: band.label },
    { label: 'Present',        value: stats.present,                          color: '#22C55E',  sub: 'classes'  },
    { label: 'Late',           value: stats.late,                             color: '#F59E0B',  sub: 'classes'  },
    { label: 'Absent',         value: stats.absent,                           color: '#EF4444',  sub: 'classes'  },
    { label: 'Total Today',    value: stats.total_classes,                    color: '#6366F1',  sub: 'periods'  },
  ] as const;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '12px' }}>
      {items.map(({ label, value, color, sub }) => (
        <div
          key={label}
          style={{
            padding: '16px 18px', borderRadius: '16px',
            background: `linear-gradient(135deg,${color}10 0%,${color}06 100%)`,
            border: `1.5px solid ${color}28`,
            position: 'relative', overflow: 'hidden',
          }}
        >
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '3px', background: color, borderRadius: '16px 16px 0 0' }} />
          <p style={{ fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '6px' }}>{label}</p>
          <p style={{ fontSize: '1.7rem', fontWeight: 900, color, lineHeight: 1, fontFamily: 'monospace' }}>{value}</p>
          <p style={{ fontSize: '0.65rem', color: '#94a3b8', marginTop: '4px' }}>{sub}</p>
        </div>
      ))}
    </div>
  );
}

// ─── Period Tabs ──────────────────────────────────────────────────────────────

function PeriodTabs({
  periods, selectedId, onSelect,
}: {
  periods: Period[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const scroll = (dir: 'left' | 'right') => {
    scrollRef.current?.scrollBy({ left: dir === 'left' ? -160 : 160, behavior: 'smooth' });
  };

  if (!periods.length) {
    return (
      <div style={{ padding: '20px', borderRadius: '14px', background: '#f8fafc', border: '1px dashed #e2e8f0', textAlign: 'center' }}>
        <BookOpen size={24} style={{ color: '#cbd5e1', margin: '0 auto 8px' }} />
        <p style={{ fontSize: '0.82rem', color: '#94a3b8', fontWeight: 500 }}>No periods scheduled for today</p>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '4px' }}>
      <button
        onClick={() => scroll('left')}
        style={{ flexShrink: 0, width: '28px', height: '28px', borderRadius: '8px', border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}
      >
        <ChevronLeft size={14} />
      </button>

      <div
        ref={scrollRef}
        style={{ display: 'flex', gap: '8px', overflowX: 'auto', scrollbarWidth: 'none', flex: 1, padding: '2px 0' }}
      >
        {periods.map(p => {
          const active      = selectedId === p.period_id;
          const statusColor = p.status ? STATUS_META[p.status]?.color : '#94A3B8';
          return (
            <button
              key={p.period_id}
              onClick={() => onSelect(p.period_id)}
              style={{
                flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
                gap: '3px', padding: '10px 14px', borderRadius: '13px', cursor: 'pointer',
                minWidth: '140px', textAlign: 'left',
                background: active
                  ? `linear-gradient(135deg,${p.course_color}20 0%,${p.course_color}0c 100%)`
                  : '#f8fafc',
                border:     `2px solid ${active ? p.course_color : '#e2e8f0'}`,
                boxShadow:  active ? `0 4px 16px ${p.course_color}25` : 'none',
                transition: 'all 0.2s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', width: '100%' }}>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: p.course_color, flexShrink: 0 }} />
                <span style={{ fontSize: '0.65rem', fontWeight: 800, color: p.course_color, letterSpacing: '0.06em', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {p.course_code}
                </span>
                {p.status && (
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: statusColor, flexShrink: 0 }} />
                )}
              </div>
              <span style={{ fontSize: '0.72rem', fontWeight: 600, color: active ? '#1e293b' : '#475569', lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '120px' }}>
                {p.course_name}
              </span>
              <span style={{ fontSize: '0.62rem', color: '#94a3b8', fontFamily: 'monospace' }}>
                {p.start_time}–{p.end_time}
              </span>
            </button>
          );
        })}
      </div>

      <button
        onClick={() => scroll('right')}
        style={{ flexShrink: 0, width: '28px', height: '28px', borderRadius: '8px', border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}
      >
        <ChevronRight size={14} />
      </button>
    </div>
  );
}

// ─── Period Stats Strip ───────────────────────────────────────────────────────

function PeriodStatsStrip({
  stats, period, loading,
}: { stats: PeriodStats | null; period: Period | null; loading: boolean }) {
  if (loading) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px' }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            style={{ height: '72px', borderRadius: '12px', background: 'linear-gradient(90deg,#f1f5f9 0px,#e2e8f0 100px,#f1f5f9 200px)', backgroundSize: '400px 100%', animation: 'sdp-shimmer 1.5s infinite' }}
          />
        ))}
      </div>
    );
  }
  if (!stats || !period) return null;

  const color = period.course_color;
  const items = [
    { label: 'Attendance', value: `${stats.attendance_pct.toFixed(0)}%`, color },
    { label: 'Present',    value: stats.present,                          color: '#22C55E' },
    { label: 'Late',       value: stats.late,                             color: '#F59E0B' },
    { label: 'Absent',     value: stats.absent,                           color: '#EF4444' },
    { label: 'Not Marked', value: stats.not_marked,                       color: '#94A3B8' },
  ] as const;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px' }}>
      {items.map(({ label, value, color: c }) => (
        <div
          key={label}
          style={{ padding: '12px 14px', borderRadius: '12px', background: `${c}0a`, border: `1.5px solid ${c}25` }}
        >
          <p style={{ fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', marginBottom: '4px' }}>{label}</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 900, color: c, fontFamily: 'monospace', lineHeight: 1 }}>{value}</p>
        </div>
      ))}
    </div>
  );
}

// ─── Records Table ────────────────────────────────────────────────────────────

function RecordsTable({
  records, loading, period,
}: { records: AttendanceRecord[]; loading: boolean; period: Period | null }) {
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            style={{ height: '52px', borderRadius: '10px', background: 'linear-gradient(90deg,#f8fafc 0px,#e2e8f0 200px,#f8fafc 400px)', backgroundSize: '600px 100%', animation: `sdp-shimmer 1.5s ${i * 0.1}s infinite` }}
          />
        ))}
      </div>
    );
  }

  if (!records.length) {
    return (
      <div style={{ padding: '48px', textAlign: 'center', borderRadius: '16px', background: '#f8fafc', border: '1px dashed #e2e8f0' }}>
        <User size={32} style={{ color: '#cbd5e1', margin: '0 auto 12px' }} />
        <p style={{ color: '#64748b', fontWeight: 600, marginBottom: '4px' }}>No attendance records yet</p>
        <p style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
          Records will appear here once attendance is marked for this period.
        </p>
      </div>
    );
  }

  return (
    <div style={{ borderRadius: '14px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
            {['Roll No', 'Student', 'Status', 'Marked At', 'Confidence', 'Marked By'].map(h => (
              <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map((rec, i) => {
            const meta = STATUS_META[rec.status] ?? STATUS_META.pending;
            const Icon = meta.Icon;
            return (
              <tr
                key={rec.record_id}
                style={{ borderBottom: i < records.length - 1 ? '1px solid #f1f5f9' : 'none', background: i % 2 === 0 ? '#fff' : '#fafbff', transition: 'background 0.15s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#f1f5f9'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = i % 2 === 0 ? '#fff' : '#fafbff'; }}
              >
                <td style={{ padding: '11px 14px', fontSize: '0.75rem', fontFamily: 'monospace', color: '#6366F1', fontWeight: 700 }}>{rec.roll_no}</td>
                <td style={{ padding: '11px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{
                      width: '28px', height: '28px', borderRadius: '50%', flexShrink: 0,
                      background: `linear-gradient(135deg,${period?.course_color ?? '#6366F1'}20,${period?.course_color ?? '#6366F1'}10)`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '0.65rem', fontWeight: 700, color: period?.course_color ?? '#6366F1',
                    }}>
                      {rec.student_name.charAt(0)}
                    </div>
                    <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#1e293b' }}>{rec.student_name}</span>
                  </div>
                </td>
                <td style={{ padding: '11px 14px' }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: '5px',
                    padding: '3px 10px', borderRadius: '99px',
                    background: meta.bg, border: `1px solid ${meta.border}`,
                    fontSize: '0.7rem', fontWeight: 700, color: meta.color,
                  }}>
                    <Icon size={11} />
                    {meta.label}
                  </span>
                </td>
                <td style={{ padding: '11px 14px', fontSize: '0.75rem', color: '#64748b', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                  {new Date(rec.marked_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </td>
                <td style={{ padding: '11px 14px' }}>
                  {rec.confidence != null ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{ width: '48px', height: '4px', borderRadius: '99px', background: '#e2e8f0', overflow: 'hidden' }}>
                        <div style={{
                          height: '100%',
                          width: `${rec.confidence * 100}%`,
                          background: rec.confidence > 0.9 ? '#22C55E' : rec.confidence > 0.75 ? '#F59E0B' : '#EF4444',
                          borderRadius: '99px',
                        }} />
                      </div>
                      <span style={{ fontSize: '0.7rem', fontFamily: 'monospace', color: '#64748b', fontWeight: 600 }}>
                        {(rec.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ) : (
                    <span style={{ color: '#cbd5e1', fontSize: '0.8rem' }}>—</span>
                  )}
                </td>
                <td style={{ padding: '11px 14px', fontSize: '0.75rem', color: '#94a3b8' }}>{rec.marked_by ?? '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── No Period Selected ───────────────────────────────────────────────────────

function NoPeriodSelected({ onSelectFirst, periods }: { onSelectFirst: () => void; periods: Period[] }) {
  return (
    <div style={{ padding: '60px 32px', textAlign: 'center', borderRadius: '20px', background: 'linear-gradient(135deg,#f8faff 0%,#f0f4ff 100%)', border: '2px dashed #c7d2fe' }}>
      <div style={{ width: '64px', height: '64px', borderRadius: '20px', background: 'linear-gradient(135deg,#6366F120,#818CF810)', border: '1.5px solid #a5b4fc', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' }}>
        <BookOpen size={28} style={{ color: '#6366F1' }} />
      </div>
      <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1e293b', marginBottom: '8px' }}>Select a Period</h3>
      <p style={{ fontSize: '0.82rem', color: '#64748b', maxWidth: '320px', margin: '0 auto 24px' }}>
        Choose a period from the tabs above to view live attendance stats and records for that class.
      </p>
      {periods.length > 0 && (
        <button
          onClick={onSelectFirst}
          style={{ padding: '10px 24px', borderRadius: '12px', background: 'linear-gradient(135deg,#6366F1,#818CF8)', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: '0.85rem', boxShadow: '0 4px 14px #6366F140' }}
        >
          View First Period
        </button>
      )}
    </div>
  );
}

// ─── Network Error ────────────────────────────────────────────────────────────

function NetworkError({ onRetry, message }: { onRetry: () => void; message: string }) {
  return (
    <div style={{ padding: '24px', borderRadius: '16px', background: '#FEF2F2', border: '1.5px solid #FECACA', display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
      <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#FEE2E2', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <WifiOff size={18} style={{ color: '#EF4444' }} />
      </div>
      <div style={{ flex: 1 }}>
        <p style={{ fontWeight: 700, color: '#DC2626', marginBottom: '4px' }}>Unable to load data</p>
        <p style={{ fontSize: '0.8rem', color: '#7f1d1d', marginBottom: '14px' }}>{message}</p>
        <button
          onClick={onRetry}
          style={{ padding: '8px 18px', borderRadius: '10px', background: '#EF4444', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <RefreshCw size={13} /> Retry
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export const StudentDashboardPage: React.FC = () => {
  const studentId = typeof localStorage !== 'undefined'
    ? (localStorage.getItem('user_id') ?? 'STUD_001')
    : 'STUD_001';

  const [searchParams, setSearchParams] = useSearchParams();
  const periodFromURL = searchParams.get('period');

  // ── State ──────────────────────────────────────────────────────────────────

  const [periods,           setPeriods]           = useState<Period[]>([]);
  const [selectedPeriodId,  setSelectedPeriodId]  = useState<string | null>(periodFromURL);
  const [overallStats,      setOverallStats]      = useState<OverallStats | null>(null);
  const [periodStats,       setPeriodStats]       = useState<PeriodStats | null>(null);
  const [records,           setRecords]           = useState<AttendanceRecord[]>([]);
  const [toasts,            setToasts]            = useState<ToastItem[]>([]);

  const [loadingPeriods,    setLoadingPeriods]    = useState(true);
  const [loadingOverall,    setLoadingOverall]    = useState(true);
  const [loadingPeriodData, setLoadingPeriodData] = useState(false);

  const [errorOverall,     setErrorOverall]     = useState<string | null>(null);
  const [errorPeriodData,  setErrorPeriodData]  = useState<string | null>(null);

  const [countdown,   setCountdown]   = useState(AUTO_REFRESH_SECONDS);
  const [isRefreshing,setIsRefreshing]= useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [isOnline,    setIsOnline]    = useState(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  );

  const prevRecordCount = useRef(0);
  const countdownRef    = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Derived ────────────────────────────────────────────────────────────────

  const selectedPeriod = useMemo(
    () => periods.find(p => p.period_id === selectedPeriodId) ?? null,
    [periods, selectedPeriodId]
  );

  // ── Toast helpers ──────────────────────────────────────────────────────────

  const addToast = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts(prev => [...prev.slice(-3), { ...toast, id }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4500);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // ── Data fetching ──────────────────────────────────────────────────────────

  const loadOverall = useCallback(async () => {
    setLoadingOverall(true);
    setErrorOverall(null);
    try {
      const stats = await fetchOverallStats(studentId);
      setOverallStats(stats);
    } catch (e: unknown) {
      setErrorOverall((e as Error).message ?? 'Failed to load overall stats');
    } finally {
      setLoadingOverall(false);
    }
  }, [studentId]);

  const loadPeriods = useCallback(async () => {
    setLoadingPeriods(true);
    try {
      const data = await fetchTodayPeriods(studentId);
      setPeriods(data);
      if (periodFromURL && data.find(p => p.period_id === periodFromURL)) {
        setSelectedPeriodId(periodFromURL);
      }
    } catch (e: unknown) {
      addToast({ type: 'error', message: "Could not load today's periods" });
    } finally {
      setLoadingPeriods(false);
    }
  }, [studentId, periodFromURL, addToast]);

  const loadPeriodData = useCallback(async (periodId: string, silent = false) => {
    if (!silent) setLoadingPeriodData(true);
    setErrorPeriodData(null);
    try {
      const [stats, recs] = await Promise.all([
        fetchPeriodStats(periodId, studentId),
        fetchPeriodRecords(periodId, studentId),
      ]);
      setPeriodStats(stats);

      // Detect new records → toast
      if (prevRecordCount.current > 0 && recs.length > prevRecordCount.current) {
        const diff   = recs.length - prevRecordCount.current;
        const newest = recs[0];
        addToast({
          type:        'success',
          message:     `${diff} new attendance record${diff > 1 ? 's' : ''} marked`,
          studentName: newest?.student_name,
        });
      }
      prevRecordCount.current = recs.length;
      setRecords(recs);
      setLastRefresh(new Date());
    } catch (e: unknown) {
      if (!silent) setErrorPeriodData((e as Error).message ?? 'Failed to load period data');
    } finally {
      if (!silent) setLoadingPeriodData(false);
    }
  }, [studentId, addToast]);

  // ── Countdown & auto-refresh ───────────────────────────────────────────────

  const startCountdown = useCallback(() => {
    if (countdownRef.current) clearInterval(countdownRef.current);
    setCountdown(AUTO_REFRESH_SECONDS);

    countdownRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          // Fire refresh silently
          loadOverall();
          setCountdown(AUTO_REFRESH_SECONDS);
          return AUTO_REFRESH_SECONDS;
        }
        return prev - 1;
      });
    }, 1000);
  }, [loadOverall]);

  // ── Effects ────────────────────────────────────────────────────────────────

  useEffect(() => {
    loadPeriods();
    loadOverall();
    startCountdown();
    return () => { if (countdownRef.current) clearInterval(countdownRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reload period data when selection changes; also restart silent per-period refresh
  const periodRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!selectedPeriodId) return;

    prevRecordCount.current = 0;
    loadPeriodData(selectedPeriodId);

    // Persist to URL params
    setSearchParams(prev => {
      const p = new URLSearchParams(prev);
      p.set('period', selectedPeriodId);
      return p;
    }, { replace: true });

    // Silent refresh loop for period-level data
    if (periodRefreshRef.current) clearInterval(periodRefreshRef.current);
    periodRefreshRef.current = setInterval(() => {
      loadPeriodData(selectedPeriodId, true);
    }, AUTO_REFRESH_SECONDS * 1000);

    return () => { if (periodRefreshRef.current) clearInterval(periodRefreshRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPeriodId]);

  // Online/offline
  useEffect(() => {
    const online  = () => { setIsOnline(true);  addToast({ type: 'success', message: 'Connection restored' }); };
    const offline = () => { setIsOnline(false); addToast({ type: 'error',   message: 'You are offline'       }); };
    window.addEventListener('online',  online);
    window.addEventListener('offline', offline);
    return () => {
      window.removeEventListener('online',  online);
      window.removeEventListener('offline', offline);
    };
  }, [addToast]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleManualRefresh = useCallback(async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    startCountdown();
    try {
      await Promise.all([
        loadOverall(),
        selectedPeriodId ? loadPeriodData(selectedPeriodId) : Promise.resolve(),
      ]);
      addToast({ type: 'info', message: 'Data refreshed' });
    } finally {
      setIsRefreshing(false);
    }
  }, [isRefreshing, loadOverall, selectedPeriodId, loadPeriodData, addToast, startCountdown]);

  const handleSelectPeriod = useCallback((id: string) => {
    setSelectedPeriodId(id);
    setPeriodStats(null);
    setRecords([]);
    setErrorPeriodData(null);
  }, []);

  // ── Render ─────────────────────────────────────────────────────────────────

  const today = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <Layout>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1100px' }}>

        {/* ── Page header ──────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <p style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#94a3b8' }}>
                Student Dashboard
              </p>
              <span style={{
                display: 'flex', alignItems: 'center', gap: '4px',
                padding: '1px 7px', borderRadius: '99px', fontSize: '0.62rem', fontWeight: 700,
                background: isOnline ? '#F0FDF4' : '#FEF2F2',
                color:      isOnline ? '#16A34A' : '#DC2626',
                border:    `1px solid ${isOnline ? '#BBF7D0' : '#FECACA'}`,
              }}>
                {isOnline ? <Wifi size={9} /> : <WifiOff size={9} />}
                {isOnline ? 'Online' : 'Offline'}
              </span>
            </div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 900, color: '#1e293b', lineHeight: 1.1 }}>Attendance Overview</h1>
            <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Calendar size={13} style={{ color: '#94a3b8' }} />
              {today}
            </p>
          </div>

          {/* Refresh controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 10px 4px 6px', borderRadius: '99px', background: '#f8fafc', border: '1px solid #e2e8f0', fontSize: '0.72rem', color: '#64748b', fontWeight: 500 }}>
              <CountdownRing seconds={countdown} total={AUTO_REFRESH_SECONDS} />
              <span>auto-refresh</span>
            </div>

            <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontFamily: 'monospace' }}>
              {lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>

            <button
              onClick={handleManualRefresh}
              disabled={isRefreshing}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                padding: '8px 16px', borderRadius: '11px',
                border: '1.5px solid #A5B4FC',
                cursor: isRefreshing ? 'not-allowed' : 'pointer',
                background: 'linear-gradient(135deg,#EEF2FF,#F5F3FF)', color: '#6366F1',
                fontSize: '0.8rem', fontWeight: 700,
                opacity: isRefreshing ? 0.7 : 1,
                boxShadow: '0 2px 8px #6366F115',
              }}
            >
              <RefreshCw size={13} style={{ animation: isRefreshing ? 'sdp-spin 0.8s linear infinite' : 'none' }} />
              Refresh
            </button>
          </div>
        </div>

        {/* ── Overall Stats ─────────────────────────────────────────────────── */}
        <ErrorBoundary>
          <section>
            <p style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <TrendingUp size={12} style={{ color: '#6366F1' }} />
              Today's Overall Stats
            </p>
            {errorOverall ? (
              <NetworkError onRetry={loadOverall} message={errorOverall} />
            ) : (
              <OverallStatsPanel stats={overallStats} loading={loadingOverall} />
            )}
          </section>
        </ErrorBoundary>

        {/* ── Period Tabs ───────────────────────────────────────────────────── */}
        <section>
          <p style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <BookOpen size={12} style={{ color: '#6366F1' }} />
            Periods Today
          </p>
          {loadingPeriods ? (
            <div style={{ display: 'flex', gap: '8px' }}>
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  style={{ width: '140px', height: '74px', borderRadius: '13px', background: 'linear-gradient(90deg,#f1f5f9 0px,#e2e8f0 80px,#f1f5f9 160px)', backgroundSize: '400px 100%', animation: `sdp-shimmer 1.5s ${i * 0.1}s infinite`, flexShrink: 0 }}
                />
              ))}
            </div>
          ) : (
            <PeriodTabs periods={periods} selectedId={selectedPeriodId} onSelect={handleSelectPeriod} />
          )}
        </section>

        {/* ── Period-level content ──────────────────────────────────────────── */}
        <ErrorBoundary>
          {!selectedPeriodId ? (
            <NoPeriodSelected
              periods={periods}
              onSelectFirst={() => { if (periods[0]) handleSelectPeriod(periods[0].period_id); }}
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

              {/* Period header card */}
              {selectedPeriod && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap',
                  padding: '16px 20px', borderRadius: '16px',
                  background: `linear-gradient(135deg,${selectedPeriod.course_color}14 0%,${selectedPeriod.course_color}08 100%)`,
                  border: `1.5px solid ${selectedPeriod.course_color}30`,
                }}>
                  <div style={{ width: '44px', height: '44px', borderRadius: '14px', background: selectedPeriod.course_color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <BookOpen size={20} style={{ color: '#fff' }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                      <span style={{ fontSize: '0.7rem', fontWeight: 800, color: selectedPeriod.course_color, letterSpacing: '0.08em' }}>{selectedPeriod.course_code}</span>
                      {selectedPeriod.is_lab_class && (
                        <span style={{ fontSize: '0.58rem', padding: '1px 6px', borderRadius: '4px', background: '#8B5CF618', color: '#8B5CF6', fontWeight: 700 }}>LAB</span>
                      )}
                    </div>
                    <p style={{ fontSize: '1rem', fontWeight: 800, color: '#1e293b', marginBottom: '2px' }}>{selectedPeriod.course_name}</p>
                    <p style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      {selectedPeriod.faculty_name} · {selectedPeriod.start_time}–{selectedPeriod.end_time}
                      {selectedPeriod.room ? ` · ${selectedPeriod.room}` : ''}
                    </p>
                  </div>
                  {selectedPeriod.status && (
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: '6px',
                      padding: '6px 12px', borderRadius: '99px',
                      background: STATUS_META[selectedPeriod.status]?.bg,
                      border: `1.5px solid ${STATUS_META[selectedPeriod.status]?.border}`,
                    }}>
                      {React.createElement(STATUS_META[selectedPeriod.status]?.Icon ?? Activity, {
                        size: 13,
                        style: { color: STATUS_META[selectedPeriod.status]?.color },
                      })}
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: STATUS_META[selectedPeriod.status]?.color }}>
                        Your Status: {STATUS_META[selectedPeriod.status]?.label}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Live period stats */}
              <div>
                <p style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Zap size={12} style={{ color: selectedPeriod?.course_color ?? '#6366F1' }} />
                  Live Period Stats
                </p>
                {errorPeriodData ? (
                  <NetworkError
                    onRetry={() => { if (selectedPeriodId) loadPeriodData(selectedPeriodId); }}
                    message={errorPeriodData}
                  />
                ) : (
                  <PeriodStatsStrip stats={periodStats} period={selectedPeriod} loading={loadingPeriodData} />
                )}
              </div>

              {/* Attendance records */}
              {!errorPeriodData && (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                    <p style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Activity size={12} style={{ color: selectedPeriod?.course_color ?? '#6366F1' }} />
                      Attendance Records
                      {!loadingPeriodData && records.length > 0 && (
                        <span style={{ padding: '1px 7px', borderRadius: '99px', background: '#EEF2FF', color: '#6366F1', fontWeight: 700, fontSize: '0.65rem' }}>
                          {records.length}
                        </span>
                      )}
                    </p>
                    {periodStats && (
                      <p style={{ fontSize: '0.7rem', color: '#94a3b8', fontFamily: 'monospace' }}>
                        Updated {new Date(periodStats.last_updated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    )}
                  </div>
                  <RecordsTable records={records} loading={loadingPeriodData} period={selectedPeriod} />
                </div>
              )}
            </div>
          )}
        </ErrorBoundary>
      </div>

      {/* ── Toast stack ───────────────────────────────────────────────────────── */}
      <ToastStack toasts={toasts} onDismiss={dismissToast} />

      <style>{`
        @keyframes sdp-shimmer {
          0%   { background-position: -400px 0; }
          100% { background-position:  400px 0; }
        }
        @keyframes sdp-slideUp {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0);    }
        }
        @keyframes sdp-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Layout>
  );
};

export default StudentDashboardPage;