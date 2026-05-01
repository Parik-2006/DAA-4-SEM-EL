/**
 * TimetableView.tsx
 *
 * Full weekly timetable grid with:
 *  - Day columns (Mon–Sat)
 *  - Time rows auto-generated from period data
 *  - Course color coding consistent with dashboard
 *  - Lab indicator, faculty name, room
 *  - Today highlighted
 */

import React, { useMemo, useState } from 'react';
import { BookOpen, Clock, User, MapPin, Beaker, ChevronLeft, ChevronRight } from 'lucide-react';
import { useTimetable, type PeriodCard } from '../../hooks/useAttendanceHooks';

// ── Constants ──────────────────────────────────────────────────────────────────

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const TODAY_IDX = (() => {
  const d = new Date().getDay(); // 0=Sun
  return d === 0 ? -1 : d - 1;  // Mon=0 … Sat=5, Sun=-1
})();

// ── Helpers ────────────────────────────────────────────────────────────────────

function toMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}

function minutesToLabel(m: number): string {
  const h = Math.floor(m / 60);
  const min = m % 60;
  const ampm = h < 12 ? 'AM' : 'PM';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${min.toString().padStart(2, '0')} ${ampm}`;
}

// ── Period block inside grid ───────────────────────────────────────────────────

function PeriodBlock({ period, rowStart, rowSpan }: { period: PeriodCard; rowStart: number; rowSpan: number }) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        gridRowStart: rowStart,
        gridRowEnd: `span ${rowSpan}`,
        borderRadius: '10px',
        background: hovered
          ? `linear-gradient(135deg, ${period.course_color}28 0%, ${period.course_color}18 100%)`
          : `linear-gradient(135deg, ${period.course_color}18 0%, ${period.course_color}0a 100%)`,
        border: `1.5px solid ${hovered ? period.course_color + '60' : period.course_color + '35'}`,
        padding: '8px 10px',
        overflow: 'hidden',
        cursor: 'default',
        transition: 'all 0.2s ease',
        transform: hovered ? 'scale(1.01)' : 'scale(1)',
        boxShadow: hovered ? `0 4px 16px ${period.course_color}25` : 'none',
        position: 'relative',
      }}
    >
      {/* Left accent */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: '3px',
        background: period.course_color, borderRadius: '10px 0 0 10px',
      }} />

      <div style={{ paddingLeft: '6px' }}>
        {/* Course code + lab badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '3px' }}>
          <span style={{
            fontSize: '0.65rem', fontWeight: 800, letterSpacing: '0.08em',
            textTransform: 'uppercase', color: period.course_color,
          }}>
            {period.course_code}
          </span>
          {period.is_lab_class && (
            <span style={{
              fontSize: '0.55rem', padding: '1px 5px', borderRadius: '4px',
              background: '#8B5CF615', color: '#8B5CF6', fontWeight: 700, letterSpacing: '0.05em',
            }}>
              LAB
            </span>
          )}
        </div>

        {/* Course name */}
        <p style={{
          fontSize: '0.75rem', fontWeight: 700, color: '#1e293b', lineHeight: 1.2,
          overflow: 'hidden', display: '-webkit-box',
          WebkitLineClamp: rowSpan > 2 ? 2 : 1, WebkitBoxOrient: 'vertical',
        }}>
          {period.course_name}
        </p>

        {/* Meta info — show more if tall */}
        {rowSpan >= 2 && (
          <div style={{ marginTop: '5px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.65rem', color: '#64748b' }}>
              <User size={10} />
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{period.faculty_name}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.65rem', color: '#94a3b8' }}>
              <Clock size={10} />
              <span>{period.start_time}–{period.end_time}</span>
            </div>
            {period.room && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.65rem', color: '#94a3b8' }}>
                <MapPin size={10} />
                <span>{period.room}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Legend ─────────────────────────────────────────────────────────────────────

function CourseLegend({ courses }: { courses: Record<string, { name: string; color: string }> }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
      {Object.entries(courses).map(([code, meta]) => (
        <div key={code} style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '4px 10px', borderRadius: '99px',
          background: meta.color + '15', border: `1px solid ${meta.color}35`,
        }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: meta.color, flexShrink: 0 }} />
          <span style={{ fontSize: '0.7rem', fontWeight: 600, color: meta.color }}>{code}</span>
          <span style={{ fontSize: '0.65rem', color: '#64748b', maxWidth: '100px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{meta.name}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────────

interface TimetableViewProps {
  studentId: string;
}

export const TimetableView: React.FC<TimetableViewProps> = ({ studentId }) => {
  const { data, loading, error, refetch } = useTimetable({ studentId });
  const [focusDay, setFocusDay] = useState<number | null>(null); // null = show all

  // Build a sorted list of unique time slots (15-min buckets)
  const { timeSlots, gridRows } = useMemo(() => {
    if (!data) return { timeSlots: [], gridRows: new Map<string, number>() };

    let minMin = 24 * 60, maxMin = 0;
    Object.values(data.days).forEach(periods =>
      periods.forEach(p => {
        minMin = Math.min(minMin, toMinutes(p.start_time));
        maxMin = Math.max(maxMin, toMinutes(p.end_time));
      })
    );
    if (minMin >= maxMin) return { timeSlots: [], gridRows: new Map<string, number>() };

    const SLOT = 30; // 30-minute rows
    const slots: string[] = [];
    const rowMap = new Map<string, number>(); // "HH:MM" → 1-based row index
    let row = 1;
    for (let m = minMin; m < maxMin; m += SLOT) {
      const h = Math.floor(m / 60).toString().padStart(2, '0');
      const min = (m % 60).toString().padStart(2, '0');
      const key = `${h}:${min}`;
      slots.push(key);
      rowMap.set(key, row);
      row++;
    }
    return { timeSlots: slots, gridRows: rowMap };
  }, [data]);

  const visibleDays = focusDay !== null ? [DAYS[focusDay]] : DAYS;

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px', gap: '12px' }}>
      <div style={{ width: '32px', height: '32px', border: '3px solid #e2e8f0', borderTopColor: '#6366F1', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Loading timetable…</p>
    </div>
  );

  if (error) return (
    <div style={{ padding: '20px', borderRadius: '14px', background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', display: 'flex', alignItems: 'center', gap: '10px' }}>
      <span style={{ fontSize: '0.85rem' }}>{error}</span>
      <button onClick={refetch} style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#6366F1', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer' }}>Retry</button>
    </div>
  );

  if (!data || timeSlots.length === 0) return (
    <div style={{ padding: '48px', textAlign: 'center', borderRadius: '16px', background: '#f8fafc', border: '1px dashed #e2e8f0' }}>
      <BookOpen size={36} style={{ color: '#cbd5e1', margin: '0 auto 12px' }} />
      <p style={{ color: '#94a3b8', fontWeight: 500 }}>No timetable data available</p>
    </div>
  );

  const SLOT = 30;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#1e293b' }}>Weekly Timetable</h2>
          {data.class_id && (
            <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '3px' }}>Class: {data.class_id}</p>
          )}
        </div>

        {/* Day filter pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <button
            onClick={() => setFocusDay(null)}
            style={{
              padding: '5px 12px', borderRadius: '99px', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
              background: focusDay === null ? '#6366F1' : '#f1f5f9',
              color: focusDay === null ? '#fff' : '#64748b',
              border: `1px solid ${focusDay === null ? '#6366F1' : '#e2e8f0'}`,
            }}
          >
            All
          </button>
          {DAYS.map((d, i) => (
            <button
              key={d}
              onClick={() => setFocusDay(focusDay === i ? null : i)}
              style={{
                padding: '5px 12px', borderRadius: '99px', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
                background: focusDay === i ? '#6366F1' : i === TODAY_IDX ? '#EEF2FF' : '#f1f5f9',
                color: focusDay === i ? '#fff' : i === TODAY_IDX ? '#6366F1' : '#64748b',
                border: `1px solid ${focusDay === i ? '#6366F1' : i === TODAY_IDX ? '#A5B4FC' : '#e2e8f0'}`,
              }}
            >
              {d.slice(0, 3)}
              {i === TODAY_IDX && <span style={{ marginLeft: '4px', fontSize: '0.55rem', verticalAlign: 'super' }}>●</span>}
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}
      <CourseLegend courses={data.all_courses} />

      {/* Grid */}
      <div style={{ overflowX: 'auto', borderRadius: '16px', border: '1px solid #e2e8f0' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: `64px repeat(${visibleDays.length}, minmax(140px, 1fr))`,
          gridTemplateRows: `40px repeat(${timeSlots.length}, 36px)`,
          minWidth: `${64 + visibleDays.length * 140}px`,
        }}>
          {/* Corner */}
          <div style={{ gridColumn: 1, gridRow: 1, background: '#f8fafc', borderBottom: '1px solid #e2e8f0', borderRight: '1px solid #e2e8f0' }} />

          {/* Day headers */}
          {visibleDays.map((day, di) => {
            const origIdx = DAYS.indexOf(day);
            const isToday = origIdx === TODAY_IDX;
            return (
              <div key={day} style={{
                gridColumn: di + 2, gridRow: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: isToday ? '#EEF2FF' : '#f8fafc',
                borderBottom: '1px solid #e2e8f0',
                borderRight: di < visibleDays.length - 1 ? '1px solid #e2e8f0' : 'none',
                borderLeft: isToday ? '2px solid #6366F1' : 'none',
                padding: '0 8px',
              }}>
                <span style={{
                  fontSize: '0.75rem', fontWeight: isToday ? 800 : 600,
                  color: isToday ? '#6366F1' : '#64748b',
                  letterSpacing: '0.05em',
                }}>
                  {day.slice(0, 3).toUpperCase()}
                  {isToday && <span style={{ marginLeft: '4px', fontSize: '0.6rem', color: '#6366F1', verticalAlign: 'text-top' }}>●</span>}
                </span>
              </div>
            );
          })}

          {/* Time labels */}
          {timeSlots.map((slot, si) => (
            <div key={slot} style={{
              gridColumn: 1, gridRow: si + 2,
              display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-end',
              paddingRight: '10px', paddingTop: '4px',
              borderRight: '1px solid #e2e8f0',
              borderBottom: si % 2 === 1 ? '1px dashed #f1f5f9' : 'none',
            }}>
              {si % 2 === 0 && (
                <span style={{ fontSize: '0.6rem', color: '#94a3b8', fontWeight: 600, whiteSpace: 'nowrap' }}>
                  {minutesToLabel(toMinutes(slot))}
                </span>
              )}
            </div>
          ))}

          {/* Background cells */}
          {visibleDays.map((_, di) =>
            timeSlots.map((_, si) => (
              <div key={`bg-${di}-${si}`} style={{
                gridColumn: di + 2, gridRow: si + 2,
                borderRight: di < visibleDays.length - 1 ? '1px solid #f1f5f9' : 'none',
                borderBottom: si % 2 === 1 ? '1px dashed #f1f5f9' : 'none',
                background: DAYS.indexOf(visibleDays[di]) === TODAY_IDX ? '#FAFBFF' : '#ffffff',
              }} />
            ))
          )}

          {/* Period blocks */}
          {visibleDays.map((day, di) => {
            const periods = data.days[day] ?? [];
            return periods.map((p) => {
              const startMin = toMinutes(p.start_time);
              const endMin   = toMinutes(p.end_time);
              const slotStart = toMinutes(timeSlots[0]);
              const rowStart  = Math.floor((startMin - slotStart) / SLOT) + 2;
              const rowSpan   = Math.max(1, Math.round((endMin - startMin) / SLOT));
              return (
                <div key={p.period_id} style={{ gridColumn: di + 2, gridRow: rowStart, padding: '2px', zIndex: 1 }}>
                  <PeriodBlock period={p} rowStart={1} rowSpan={rowSpan} />
                </div>
              );
            });
          })}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default TimetableView;
