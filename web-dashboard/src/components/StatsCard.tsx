/**
 * StatsCard.tsx
 *
 * Reusable attendance stats card with:
 *  - Circular progress ring
 *  - Linear progress bar
 *  - Band colour coding (safe/warning/danger)
 *  - Warning badge if below 75%
 *  - Course breakdown rows
 */

import React from 'react';
import { AlertTriangle, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { CourseAttendanceStat, AttendanceSummary } from '../hooks/useAttendanceHooks';

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
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const stroke = circ * (1 - Math.min(100, pct) / 100);

  return (
    <svg width={size} height={size} style={{ flexShrink: 0 }}>
      {/* Track */}
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={6} />
      {/* 75% danger marker */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke="#F59E0B44" strokeWidth={2}
        strokeDasharray={`${circ * 0.01} ${circ * 0.99}`}
        strokeDashoffset={circ * 0.25}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      {/* Progress arc */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke={color} strokeWidth={6}
        strokeDasharray={circ}
        strokeDashoffset={stroke}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 1s ease' }}
      />
      {/* Percentage text */}
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
      display: 'flex', alignItems: 'center', gap: '12px',
      padding: '10px 14px', borderRadius: '12px',
      background: `${color}08`,
      border: `1px solid ${color}22`,
    }}>
      {/* Color dot */}
      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: stat.color, flexShrink: 0 }} />

      {/* Names */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1e293b' }}>{stat.course_code}</span>
          {stat.is_critical && (
            <span style={{ fontSize: '0.6rem', padding: '1px 5px', borderRadius: '4px', background: '#FEF2F2', color: '#DC2626', fontWeight: 700 }}>CRITICAL</span>
          )}
        </div>
        <p style={{ fontSize: '0.68rem', color: '#94a3b8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{stat.course_name}</p>
      </div>

      {/* Mini bar */}
      <div style={{ width: '70px', flexShrink: 0 }}>
        <div style={{ height: '5px', borderRadius: '99px', background: '#e2e8f0', overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${Math.min(100, stat.percentage)}%`, background: color, borderRadius: '99px', transition: 'width 0.8s ease' }} />
        </div>
        <p style={{ fontSize: '0.65rem', textAlign: 'right', marginTop: '2px', color, fontWeight: 700 }}>
          {stat.percentage.toFixed(0)}%
        </p>
      </div>

      {/* Trend icon */}
      <TrendIcon size={14} style={{ color, flexShrink: 0 }} />

      {/* Counts */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <p style={{ fontSize: '0.65rem', color: '#94a3b8' }}>
          {stat.present + stat.late}/{stat.total}
        </p>
      </div>
    </div>
  );
}

// ── Main StatsCard ─────────────────────────────────────────────────────────────

interface StatsCardProps {
  summary: AttendanceSummary;
  compact?: boolean;
}

export const StatsCard: React.FC<StatsCardProps> = ({ summary, compact = false }) => {
  const { overall, course_breakdown, has_critical, critical_courses } = summary;
  const color = bandColor(overall.band);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Overall header card */}
      <div style={{
        borderRadius: '20px',
        background: `linear-gradient(135deg, ${color}12 0%, ${color}06 100%)`,
        border: `2px solid ${color}30`,
        padding: '20px 24px',
        display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap',
      }}>
        {/* Circle */}
        <CircleProgress pct={overall.percentage} color={color} size={compact ? 72 : 88} />

        {/* Text */}
        <div style={{ flex: 1, minWidth: '160px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span style={{
              fontSize: '0.65rem', fontWeight: 700, padding: '2px 10px', borderRadius: '99px',
              background: `${color}20`, color, letterSpacing: '0.08em',
            }}>
              {bandLabel(overall.band).toUpperCase()}
            </span>
          </div>
          <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '10px' }}>Overall attendance rate</p>

          {/* Mini stat grid */}
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            {[
              { label: 'Present', val: overall.present, color: '#22C55E' },
              { label: 'Late', val: overall.late, color: '#F59E0B' },
              { label: 'Absent', val: overall.absent, color: '#EF4444' },
              { label: 'Total', val: overall.total, color: '#6366F1' },
            ].map(({ label, val, color: c }) => (
              <div key={label}>
                <p style={{ fontSize: '1.1rem', fontWeight: 800, color: c, lineHeight: 1 }}>{val}</p>
                <p style={{ fontSize: '0.62rem', color: '#94a3b8', marginTop: '2px' }}>{label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Warning badge */}
        {overall.band !== 'safe' && (
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: '8px',
            padding: '10px 14px', borderRadius: '12px',
            background: overall.band === 'danger' ? '#FEF2F2' : '#FFFBEB',
            border: `1px solid ${overall.band === 'danger' ? '#FECACA' : '#FDE68A'}`,
            maxWidth: '220px',
          }}>
            <AlertTriangle size={14} style={{ color, flexShrink: 0, marginTop: '1px' }} />
            <p style={{ fontSize: '0.72rem', color: overall.band === 'danger' ? '#DC2626' : '#92400E', lineHeight: 1.4 }}>
              {overall.band === 'danger'
                ? `Below 75% — attend ${critical_courses[0]?.required_consecutive_to_reach_75 ?? 0} more classes to recover`
                : 'Between 75–85% — maintain regular attendance'}
            </p>
          </div>
        )}
      </div>

      {/* Course breakdown */}
      {!compact && course_breakdown.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <p style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Course Breakdown
          </p>
          {course_breakdown.map(stat => (
            <CourseRow key={stat.course_code} stat={stat} />
          ))}
        </div>
      )}

      {/* Critical warning box */}
      {has_critical && !compact && (
        <div style={{
          borderRadius: '14px', padding: '14px 18px',
          background: 'linear-gradient(135deg, #FEF2F2 0%, #FFF5F5 100%)',
          border: '1.5px solid #FECACA',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <AlertTriangle size={16} style={{ color: '#EF4444' }} />
            <p style={{ fontSize: '0.85rem', fontWeight: 700, color: '#DC2626' }}>Critical Warning</p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {critical_courses.map(c => (
              <div key={c.course_code} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', borderRadius: '8px', background: '#FEF2F2' }}>
                <div>
                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1e293b' }}>{c.course_code}</span>
                  <span style={{ fontSize: '0.72rem', color: '#94a3b8', marginLeft: '6px' }}>{c.course_name}</span>
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
        </div>
      )}
    </div>
  );
};

export default StatsCard;
