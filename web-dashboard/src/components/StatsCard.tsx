/**
 * StatsCard.tsx
 *
 * Contains:
 *  - StatsCard          — original overall student attendance stats
 *  - PeriodStatsCard    — period-level breakdown: present / absent / late / not_marked
 *  - AuditTrailList     — filterable, searchable table of per-student scan events
 */

import React from 'react';
import {
  AlertTriangle, TrendingUp, TrendingDown, Minus,
  CheckCircle, XCircle, Clock, Activity,
  Search, Download, SlidersHorizontal, X,
} from 'lucide-react';
import type { CourseAttendanceStat, AttendanceSummary, PeriodAnalytics, PeriodAuditEntry } from '../hooks/useAttendanceHooks';

// ── Helpers ────────────────────────────────────────────────────────────────────

function bandColor(band: string): string {
  if (band === 'safe') return '#22C55E';
  if (band === 'warning') return '#F59E0B';
  return '#EF4444';
}

function bandLabel(band: string): string {
  if (band === 'safe') return 'Good Standing';
  if (band === 'warning') return 'Needs Attention';
  return 'Critical';
}

// ── Circular progress ring ─────────────────────────────────────────────────────

function CircleProgress({ pct, color, size = 80 }: { pct: number; color: string; size?: number }) {
  const r     = (size - 10) / 2;
  const circ  = 2 * Math.PI * r;
  const stroke = circ * (1 - Math.min(100, pct) / 100);

  return (
    <svg width={size} height={size} style={{ flexShrink: 0 }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={6} />
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke="#F59E0B44" strokeWidth={2}
        strokeDasharray={`${circ * 0.01} ${circ * 0.99}`}
        strokeDashoffset={circ * 0.25}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke={color} strokeWidth={6}
        strokeDasharray={circ}
        strokeDashoffset={stroke}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 1s ease' }}
      />
      <text x={size / 2} y={size / 2 + 1} textAnchor="middle" dominantBaseline="middle"
        fill={color} fontSize={size * 0.2} fontWeight="900" fontFamily="monospace">
        {pct.toFixed(0)}%
      </text>
    </svg>
  );
}

// ── Course row ─────────────────────────────────────────────────────────────────

function CourseRow({ stat }: { stat: CourseAttendanceStat }) {
  const color = stat.band_color;
  const TrendIcon = stat.percentage >= 85 ? TrendingUp : stat.percentage >= 75 ? Minus : TrendingDown;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '10px 14px', borderRadius: 12,
      background: `${color}08`, border: `1px solid ${color}22`,
    }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: stat.color, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1e293b' }}>{stat.course_code}</span>
          {stat.is_critical && (
            <span style={{ fontSize: '0.6rem', padding: '1px 5px', borderRadius: 4, background: '#FEF2F2', color: '#DC2626', fontWeight: 700 }}>CRITICAL</span>
          )}
        </div>
        <p style={{ fontSize: '0.68rem', color: '#94a3b8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{stat.course_name}</p>
      </div>
      <div style={{ width: 70, flexShrink: 0 }}>
        <div style={{ height: 5, borderRadius: 99, background: '#e2e8f0', overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${Math.min(100, stat.percentage)}%`, background: color, borderRadius: 99, transition: 'width 0.8s ease' }} />
        </div>
        <p style={{ fontSize: '0.65rem', textAlign: 'right', marginTop: 2, color, fontWeight: 700 }}>
          {stat.percentage.toFixed(0)}%
        </p>
      </div>
      <TrendIcon size={14} style={{ color, flexShrink: 0 }} />
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <p style={{ fontSize: '0.65rem', color: '#94a3b8' }}>
          {stat.present + stat.late}/{stat.total}
        </p>
      </div>
    </div>
  );
}

// ── StatsCard (original) ───────────────────────────────────────────────────────

interface StatsCardProps {
  summary: AttendanceSummary;
  compact?: boolean;
}

export const StatsCard: React.FC<StatsCardProps> = ({ summary, compact = false }) => {
  const { overall, course_breakdown, has_critical, critical_courses } = summary;
  const color = bandColor(overall.band);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{
        borderRadius: 20,
        background: `linear-gradient(135deg, ${color}12 0%, ${color}06 100%)`,
        border: `2px solid ${color}30`,
        padding: '20px 24px',
        display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap',
      }}>
        <CircleProgress pct={overall.percentage} color={color} size={compact ? 72 : 88} />
        <div style={{ flex: 1, minWidth: 160 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 10px', borderRadius: 99, background: `${color}20`, color, letterSpacing: '0.08em' }}>
              {bandLabel(overall.band).toUpperCase()}
            </span>
          </div>
          <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: 10 }}>Overall attendance rate</p>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {[
              { label: 'Present', val: overall.present, color: '#22C55E' },
              { label: 'Late',    val: overall.late,    color: '#F59E0B' },
              { label: 'Absent',  val: overall.absent,  color: '#EF4444' },
              { label: 'Total',   val: overall.total,   color: '#6366F1' },
            ].map(({ label, val, color: c }) => (
              <div key={label}>
                <p style={{ fontSize: '1.1rem', fontWeight: 800, color: c, lineHeight: 1 }}>{val}</p>
                <p style={{ fontSize: '0.62rem', color: '#94a3b8', marginTop: 2 }}>{label}</p>
              </div>
            ))}
          </div>
        </div>
        {overall.band !== 'safe' && (
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 14px', borderRadius: 12,
            background: overall.band === 'danger' ? '#FEF2F2' : '#FFFBEB',
            border: `1px solid ${overall.band === 'danger' ? '#FECACA' : '#FDE68A'}`,
            maxWidth: 220,
          }}>
            <AlertTriangle size={14} style={{ color, flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: '0.72rem', color: overall.band === 'danger' ? '#DC2626' : '#92400E', lineHeight: 1.4 }}>
              {overall.band === 'danger'
                ? `Below 75% — attend ${critical_courses[0]?.required_consecutive_to_reach_75 ?? 0} more classes to recover`
                : 'Between 75–85% — maintain regular attendance'}
            </p>
          </div>
        )}
      </div>

      {!compact && course_breakdown.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <p style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Course Breakdown
          </p>
          {course_breakdown.map(stat => <CourseRow key={stat.course_code} stat={stat} />)}
        </div>
      )}

      {has_critical && !compact && (
        <div style={{ borderRadius: 14, padding: '14px 18px', background: 'linear-gradient(135deg, #FEF2F2 0%, #FFF5F5 100%)', border: '1.5px solid #FECACA' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <AlertTriangle size={16} style={{ color: '#EF4444' }} />
            <p style={{ fontSize: '0.85rem', fontWeight: 700, color: '#DC2626' }}>Critical Warning</p>
          </div>
          {critical_courses.map(c => (
            <div key={c.course_code} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', borderRadius: 8, background: '#FEF2F2' }}>
              <div>
                <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1e293b' }}>{c.course_code}</span>
                <span style={{ fontSize: '0.72rem', color: '#94a3b8', marginLeft: 6 }}>{c.course_name}</span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <p style={{ fontSize: '0.8rem', fontWeight: 800, color: '#EF4444' }}>{c.percentage.toFixed(1)}%</p>
                {c.required_consecutive_to_reach_75 > 0 && (
                  <p style={{ fontSize: '0.62rem', color: '#94a3b8' }}>Need {c.required_consecutive_to_reach_75} more</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default StatsCard;

// ─────────────────────────────────────────────────────────────────────────────
// PeriodStatsCard — period-level present / absent / late / not_marked breakdown
// ─────────────────────────────────────────────────────────────────────────────

interface PeriodStatsCardProps {
  analytics: PeriodAnalytics;
  periodColor: string;
}

export const PeriodStatsCard: React.FC<PeriodStatsCardProps> = ({ analytics, periodColor }) => {
  const {
    present, late, absent, not_marked,
    total_enrolled, attendance_pct,
    course_code, course_name, faculty_name,
    start_time, end_time,
  } = analytics;

  const pct      = Math.round(attendance_pct);
  const pctColor = pct >= 75 ? '#22C55E' : pct >= 50 ? '#F59E0B' : '#EF4444';

  const tiles = [
    { label: 'Present',    value: present,    color: '#22C55E', bg: '#F0FDF4', icon: CheckCircle },
    { label: 'Absent',     value: absent,     color: '#EF4444', bg: '#FEF2F2', icon: XCircle   },
    { label: 'Late',       value: late,       color: '#F59E0B', bg: '#FFFBEB', icon: Clock      },
    { label: 'Not Marked', value: not_marked, color: '#94A3B8', bg: '#F8FAFC', icon: Activity   },
  ];

  return (
    <div style={{
      borderRadius: 18,
      border: `2px solid ${periodColor}35`,
      background: `linear-gradient(135deg, ${periodColor}12 0%, ${periodColor}05 100%)`,
      padding: '20px 24px',
    }}>
      {/* Period header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
            <span style={{
              fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.1em',
              textTransform: 'uppercase', color: periodColor,
            }}>
              {course_code}
            </span>
            <span style={{ fontSize: '0.62rem', fontFamily: 'DM Mono, monospace', color: '#94a3b8' }}>
              {start_time}–{end_time}
            </span>
          </div>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#1e293b', marginBottom: 3 }}>
            {course_name}
          </h3>
          {faculty_name && (
            <p style={{ fontSize: '0.72rem', color: '#64748b' }}>{faculty_name}</p>
          )}
        </div>

        {/* Overall percentage bubble */}
        <div style={{
          textAlign: 'center', padding: '10px 20px', borderRadius: 14,
          background: `${pctColor}12`, border: `1.5px solid ${pctColor}30`,
        }}>
          <p style={{
            fontSize: '2rem', fontWeight: 900, color: pctColor,
            lineHeight: 1, fontFamily: 'DM Mono, monospace',
          }}>
            {pct}%
          </p>
          <p style={{ fontSize: '0.6rem', color: '#94a3b8', marginTop: 3 }}>
            of {total_enrolled} enrolled
          </p>
        </div>
      </div>

      {/* Stat tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 18 }}>
        {tiles.map(({ label, value, color, bg, icon: Icon }) => (
          <div key={label} style={{
            padding: '14px 10px', borderRadius: 14, background: bg,
            border: `1.5px solid ${color}22`, textAlign: 'center',
          }}>
            <Icon size={16} style={{ color, margin: '0 auto 6px', display: 'block' }} />
            <p style={{ fontSize: '1.8rem', fontWeight: 900, color, lineHeight: 1, fontFamily: 'DM Mono, monospace' }}>
              {value}
            </p>
            <p style={{ fontSize: '0.6rem', color: '#94a3b8', marginTop: 5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              {label}
            </p>
          </div>
        ))}
      </div>

      {/* Stacked breakdown bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Attendance breakdown</span>
          <span style={{ fontSize: '0.65rem', fontFamily: 'DM Mono, monospace', color: '#64748b' }}>
            {present + late} of {total_enrolled} attended
          </span>
        </div>

        {/* Segmented bar: present | late | absent | not_marked */}
        <div style={{ height: 10, borderRadius: 99, background: '#e2e8f0', overflow: 'hidden', display: 'flex' }}>
          {total_enrolled > 0 && (
            <>
              <div style={{ width: `${(present    / total_enrolled) * 100}%`, background: '#22C55E', transition: 'width 0.7s ease' }} />
              <div style={{ width: `${(late       / total_enrolled) * 100}%`, background: '#F59E0B', transition: 'width 0.7s ease' }} />
              <div style={{ width: `${(absent     / total_enrolled) * 100}%`, background: '#EF4444', transition: 'width 0.7s ease' }} />
              <div style={{ width: `${(not_marked / total_enrolled) * 100}%`, background: '#CBD5E1', transition: 'width 0.7s ease' }} />
            </>
          )}
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 14, marginTop: 8, flexWrap: 'wrap' }}>
          {[
            { color: '#22C55E', label: 'Present'    },
            { color: '#F59E0B', label: 'Late'       },
            { color: '#EF4444', label: 'Absent'     },
            { color: '#CBD5E1', label: 'Not marked' },
          ].map(({ color, label }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }} />
              <span style={{ fontSize: '0.62rem', color: '#94a3b8' }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// AuditTrailList — filterable, searchable per-student scan audit table
// ─────────────────────────────────────────────────────────────────────────────

type StatusKey = 'present' | 'absent' | 'late' | 'not_marked';

const STATUS_META: Record<StatusKey, { label: string; dot: string; bg: string; text: string }> = {
  present:    { label: 'Present',    dot: '#22C55E', bg: '#F0FDF4', text: '#16A34A' },
  absent:     { label: 'Absent',     dot: '#EF4444', bg: '#FEF2F2', text: '#DC2626' },
  late:       { label: 'Late',       dot: '#F59E0B', bg: '#FFFBEB', text: '#92400E' },
  not_marked: { label: 'Not Marked', dot: '#94A3B8', bg: '#F8FAFC', text: '#64748B' },
};

interface AuditTrailListProps {
  entries: PeriodAuditEntry[];
  periodColor: string;
}

export const AuditTrailList: React.FC<AuditTrailListProps> = ({ entries, periodColor }) => {
  const [activeFilter, setActiveFilter] = React.useState<'all' | StatusKey>('all');
  const [search, setSearch]             = React.useState('');

  const counts = React.useMemo(() => ({
    present:    entries.filter(e => e.status === 'present').length,
    absent:     entries.filter(e => e.status === 'absent').length,
    late:       entries.filter(e => e.status === 'late').length,
    not_marked: entries.filter(e => e.status === 'not_marked').length,
  }), [entries]);

  const filtered = React.useMemo(() => {
    let list = activeFilter === 'all' ? entries : entries.filter(e => e.status === activeFilter);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(e =>
        e.student_name.toLowerCase().includes(q) ||
        (e.roll_no ?? '').toLowerCase().includes(q) ||
        e.student_id.toLowerCase().includes(q)
      );
    }
    // Sort scanned entries first (ascending by scan time), then not_marked
    return [...list].sort((a, b) => {
      if (a.scanned_at && b.scanned_at)
        return new Date(a.scanned_at).getTime() - new Date(b.scanned_at).getTime();
      if (a.scanned_at)  return -1;
      if (b.scanned_at)  return  1;
      return a.student_name.localeCompare(b.student_name);
    });
  }, [entries, activeFilter, search]);

  const exportCSV = () => {
    if (!filtered.length) return;
    const hdr  = ['Roll No', 'Name', 'Status', 'Scanned At', 'Confidence'];
    const rows = filtered.map(e => [
      e.roll_no ?? '',
      e.student_name,
      e.status,
      e.scanned_at
        ? new Date(e.scanned_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
        : '',
      e.confidence != null ? `${(e.confidence * 100).toFixed(0)}%` : '',
    ]);
    const csv  = [hdr, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `audit-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  return (
    <div style={{ borderRadius: 18, border: '1px solid #E2E8F0', overflow: 'hidden', background: '#fff' }}>

      {/* Header */}
      <div style={{
        padding: '14px 20px', borderBottom: '1px solid #F1F5F9',
        background: '#F8FAFC', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', flexWrap: 'wrap', gap: 10,
      }}>
        <div>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#1e293b', marginBottom: 2 }}>
            Scan Audit Trail
          </h3>
          <p style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
            {entries.filter(e => e.scanned_at).length} of {entries.length} students scanned
            {entries.filter(e => e.status === 'not_marked').length > 0 && (
              <span style={{ color: '#EF4444', fontWeight: 600 }}>
                {' '}· {entries.filter(e => e.status === 'not_marked').length} not yet marked
              </span>
            )}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {/* Status filter pills */}
          {(['all', 'present', 'late', 'absent', 'not_marked'] as const).map(f => {
            const meta  = f !== 'all' ? STATUS_META[f] : null;
            const count = f === 'all' ? entries.length : counts[f];
            const active = activeFilter === f;
            return (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                style={{
                  padding: '4px 10px', borderRadius: 99, fontSize: '0.68rem', fontWeight: 600,
                  cursor: 'pointer',
                  background: active ? (meta?.bg ?? `${periodColor}15`) : '#F1F5F9',
                  color: active ? (meta?.text ?? '#1e293b') : '#64748b',
                  border: `1px solid ${active ? (meta?.dot ?? periodColor) + '50' : 'transparent'}`,
                }}
              >
                {f === 'all' ? 'All' : f === 'not_marked' ? 'Unmarked' : f.charAt(0).toUpperCase() + f.slice(1)}
                {' '}({count})
              </button>
            );
          })}

          {/* Search */}
          <div style={{ position: 'relative' }}>
            <Search size={12} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Name / roll no…"
              style={{ paddingLeft: 26, paddingRight: search ? 26 : 10, padding: '6px 10px 6px 26px', borderRadius: 8, border: '1.5px solid #E2E8F0', fontSize: '0.75rem', color: '#1e293b', outline: 'none', width: 148 }}
            />
            {search && (
              <button onClick={() => setSearch('')} style={{ position: 'absolute', right: 7, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: 0 }}>
                <X size={11} />
              </button>
            )}
          </div>

          {/* Export */}
          <button
            onClick={exportCSV}
            disabled={filtered.length === 0}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', borderRadius: 8, background: '#F1F5F9', border: '1px solid #E2E8F0', cursor: filtered.length ? 'pointer' : 'not-allowed', fontSize: '0.72rem', color: '#64748b', opacity: filtered.length ? 1 : 0.4 }}
          >
            <Download size={12} /> Export
          </button>
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#FAFBFF', borderBottom: '2px solid #E2E8F0' }}>
              {['Roll No', 'Student Name', 'Status', 'Scanned At', 'Confidence', 'Marked By'].map(h => (
                <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: '36px', textAlign: 'center', color: '#94a3b8', fontSize: '0.82rem' }}>
                  No records match the current filter
                </td>
              </tr>
            ) : (
              filtered.map((entry, i) => {
                const meta      = STATUS_META[entry.status];
                const scanTime  = entry.scanned_at
                  ? new Date(entry.scanned_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
                  : null;
                const confPct   = entry.confidence != null
                  ? `${(entry.confidence * 100).toFixed(0)}%`
                  : null;
                const confNum   = entry.confidence != null ? entry.confidence * 100 : null;

                return (
                  <tr
                    key={entry.student_id}
                    style={{ borderBottom: '1px solid #F1F5F9', background: i % 2 === 0 ? '#fff' : '#FAFBFF', transition: 'background 0.12s' }}
                    onMouseEnter={ev => (ev.currentTarget.style.background = '#F1F5F9')}
                    onMouseLeave={ev => (ev.currentTarget.style.background = i % 2 === 0 ? '#fff' : '#FAFBFF')}
                  >
                    {/* Roll no */}
                    <td style={{ padding: '10px 14px', fontFamily: 'DM Mono, monospace', fontWeight: 700, color: '#6366F1', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                      {entry.roll_no ?? '—'}
                    </td>

                    {/* Name */}
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: '#1e293b', fontSize: '0.82rem' }}>
                      {entry.student_name}
                    </td>

                    {/* Status badge */}
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 5,
                        padding: '3px 10px', borderRadius: 99,
                        background: meta.bg, border: `1px solid ${meta.dot}30`,
                        fontSize: '0.7rem', fontWeight: 700, color: meta.text,
                        whiteSpace: 'nowrap',
                      }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: meta.dot, flexShrink: 0 }} />
                        {meta.label}
                      </span>
                    </td>

                    {/* Scan time */}
                    <td style={{ padding: '10px 14px', fontFamily: 'DM Mono, monospace', fontSize: '0.78rem', color: scanTime ? '#334155' : '#CBD5E1', whiteSpace: 'nowrap' }}>
                      {scanTime ?? '—'}
                    </td>

                    {/* Confidence */}
                    <td style={{ padding: '10px 14px' }}>
                      {confPct && confNum != null ? (
                        <span style={{
                          padding: '2px 8px', borderRadius: 6, fontFamily: 'DM Mono, monospace',
                          fontSize: '0.72rem', fontWeight: 700,
                          background: confNum >= 90 ? '#F0FDF4' : confNum >= 75 ? '#FFFBEB' : '#FEF2F2',
                          color:      confNum >= 90 ? '#16A34A' : confNum >= 75 ? '#92400E' : '#DC2626',
                        }}>
                          {confPct}
                        </span>
                      ) : (
                        <span style={{ color: '#E2E8F0', fontSize: '0.75rem' }}>—</span>
                      )}
                    </td>

                    {/* Marked by */}
                    <td style={{ padding: '10px 14px', fontSize: '0.75rem', color: '#94a3b8' }}>
                      {entry.marked_by_name ?? (entry.scanned_at ? 'Camera' : '—')}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Footer summary */}
      {filtered.length > 0 && (
        <div style={{ padding: '10px 20px', borderTop: '1px solid #F1F5F9', background: '#FAFBFF', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          {Object.entries(STATUS_META).map(([key, meta]) => {
            const n = counts[key as StatusKey];
            if (n === 0) return null;
            return (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: meta.dot }} />
                <span style={{ fontSize: '0.68rem', color: '#64748b' }}>
                  <strong style={{ color: meta.text }}>{n}</strong> {meta.label.toLowerCase()}
                </span>
              </div>
            );
          })}
          <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: '#94a3b8' }}>
            Showing {filtered.length} of {entries.length}
          </span>
        </div>
      )}
    </div>
  );
};