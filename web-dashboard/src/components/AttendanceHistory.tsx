/**
 * AttendanceHistory.tsx
 *
 * Paginated attendance history table with:
 *  - Date range filter
 *  - Course filter
 *  - Status filter
 *  - Colour-coded status badges
 *  - Marked-by faculty name
 *  - CSV export
 */

import React, { useState, useMemo } from 'react';
import {
  Search, Filter, Download, ChevronLeft, ChevronRight,
  CheckCircle, XCircle, Clock, Activity, X, SlidersHorizontal
} from 'lucide-react';
import { useStudentAttendance, type CourseAttendanceStat } from '../../hooks/useAttendanceHooks';

// ── Types & constants ──────────────────────────────────────────────────────────

const STATUS_META = {
  present: { label: 'Present', hex: '#22C55E', bg: '#F0FDF4', icon: CheckCircle },
  absent:  { label: 'Absent',  hex: '#EF4444', bg: '#FEF2F2', icon: XCircle },
  late:    { label: 'Late',    hex: '#F59E0B', bg: '#FFFBEB', icon: Clock },
  pending: { label: 'Pending', hex: '#94A3B8', bg: '#F8FAFC', icon: Activity },
};

// ── Status badge ───────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status as keyof typeof STATUS_META] ?? STATUS_META.pending;
  const Icon = meta.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      padding: '3px 10px', borderRadius: '99px',
      background: meta.bg, color: meta.hex,
      fontSize: '0.72rem', fontWeight: 700,
      border: `1px solid ${meta.hex}30`,
    }}>
      <Icon size={11} />
      {meta.label}
    </span>
  );
}

// ── Stats strip at top ─────────────────────────────────────────────────────────

function CourseBreakdownStrip({ courses }: { courses: CourseAttendanceStat[] }) {
  return (
    <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '4px' }}>
      {courses.map(c => (
        <div key={c.course_code} style={{
          flexShrink: 0, minWidth: '140px', borderRadius: '14px', padding: '12px 14px',
          background: `${c.band_color}0e`, border: `1.5px solid ${c.band_color}30`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 800, color: c.color, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{c.course_code}</span>
            <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 7px', borderRadius: '99px', background: `${c.band_color}20`, color: c.band_color }}>
              {c.percentage.toFixed(0)}%
            </span>
          </div>
          <div style={{ height: '5px', borderRadius: '99px', background: '#e2e8f0', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${Math.min(100, c.percentage)}%`, background: c.band_color, borderRadius: '99px', transition: 'width 0.6s ease' }} />
          </div>
          <p style={{ fontSize: '0.62rem', color: '#94a3b8', marginTop: '5px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.course_name}</p>
        </div>
      ))}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

interface AttendanceHistoryProps {
  studentId: string;
  availableCourses?: Array<{ code: string; name: string }>;
}

export const AttendanceHistory: React.FC<AttendanceHistoryProps> = ({
  studentId,
  availableCourses = [],
}) => {
  const [page, setPage]             = useState(1);
  const [pageSize]                  = useState(20);
  const [courseFilter, setCourse]   = useState('');
  const [startDate, setStart]       = useState('');
  const [endDate, setEnd]           = useState('');
  const [statusFilter, setStatus]   = useState('');
  const [search, setSearch]         = useState('');
  const [showFilters, setShowFilt]  = useState(false);

  const { history, summary, loading, error, refetch } = useStudentAttendance({
    studentId,
    page,
    pageSize,
    courseId: courseFilter || undefined,
    startDate: startDate || undefined,
    endDate: endDate || undefined,
    enabled: !!studentId,
  });

  const records = useMemo(() => {
    if (!history?.records) return [];
    let r = history.records;
    if (statusFilter) r = r.filter(rec => rec.status === statusFilter);
    if (search) {
      const q = search.toLowerCase();
      r = r.filter(rec =>
        rec.course_code?.toLowerCase().includes(q) ||
        rec.course_name?.toLowerCase().includes(q) ||
        rec.marked_by_name?.toLowerCase().includes(q) ||
        rec.date?.includes(q)
      );
    }
    return r;
  }, [history?.records, statusFilter, search]);

  const hasFilters = courseFilter || startDate || endDate || statusFilter || search;

  const clearFilters = () => {
    setCourse(''); setStart(''); setEnd(''); setStatus(''); setSearch('');
    setPage(1);
  };

  const exportCSV = () => {
    if (!records.length) return;
    const headers = ['Date', 'Course', 'Status', 'Marked By', 'Time', 'Confidence'];
    const rows = records.map(r => [
      r.date, r.course_name ?? '', r.status,
      r.marked_by_name ?? '', r.time ?? '',
      r.confidence != null ? `${(r.confidence * 100).toFixed(0)}%` : '',
    ]);
    const csv = [headers, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `attendance-${studentId}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const inputStyle: React.CSSProperties = {
    padding: '8px 12px', borderRadius: '10px', fontSize: '0.8rem',
    border: '1.5px solid #e2e8f0', background: '#fff', color: '#1e293b',
    outline: 'none', width: '100%',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* Course stats strip */}
      {summary?.course_breakdown && summary.course_breakdown.length > 0 && (
        <CourseBreakdownStrip courses={summary.course_breakdown} />
      )}

      {/* Controls bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        {/* Search */}
        <div style={{ position: 'relative', flex: 1, minWidth: '200px' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search by course, faculty, date…"
            style={{ ...inputStyle, paddingLeft: '32px', paddingRight: search ? '32px' : '12px' }}
          />
          {search && (
            <button onClick={() => setSearch('')} style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
              <X size={13} />
            </button>
          )}
        </div>

        {/* Filters toggle */}
        <button
          onClick={() => setShowFilt(!showFilters)}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px',
            borderRadius: '10px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer',
            background: showFilters || hasFilters ? '#EEF2FF' : '#f8fafc',
            color: showFilters || hasFilters ? '#6366F1' : '#64748b',
            border: `1.5px solid ${showFilters || hasFilters ? '#A5B4FC' : '#e2e8f0'}`,
          }}
        >
          <SlidersHorizontal size={14} />
          Filters {hasFilters && <span style={{ background: '#6366F1', color: '#fff', borderRadius: '99px', padding: '0 5px', fontSize: '0.65rem' }}>●</span>}
        </button>

        {/* Export */}
        <button
          onClick={exportCSV}
          disabled={records.length === 0}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px',
            borderRadius: '10px', fontSize: '0.8rem', fontWeight: 600, cursor: records.length ? 'pointer' : 'not-allowed',
            background: '#f8fafc', color: '#64748b', border: '1.5px solid #e2e8f0',
            opacity: records.length ? 1 : 0.5,
          }}
        >
          <Download size={14} /> Export
        </button>
      </div>

      {/* Expanded filters */}
      {showFilters && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '12px', padding: '16px', borderRadius: '14px',
          background: '#f8fafc', border: '1px solid #e2e8f0',
          animation: 'fadeIn 0.2s ease',
        }}>
          {/* Course */}
          <div>
            <label style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: '5px' }}>Course</label>
            <select value={courseFilter} onChange={e => { setCourse(e.target.value); setPage(1); }} style={inputStyle}>
              <option value="">All Courses</option>
              {availableCourses.map(c => (
                <option key={c.code} value={c.code}>{c.code} — {c.name}</option>
              ))}
            </select>
          </div>

          {/* Status */}
          <div>
            <label style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: '5px' }}>Status</label>
            <select value={statusFilter} onChange={e => { setStatus(e.target.value); setPage(1); }} style={inputStyle}>
              <option value="">All Statuses</option>
              {Object.entries(STATUS_META).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>

          {/* Start date */}
          <div>
            <label style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: '5px' }}>From</label>
            <input type="date" value={startDate} onChange={e => { setStart(e.target.value); setPage(1); }} style={inputStyle} />
          </div>

          {/* End date */}
          <div>
            <label style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: '5px' }}>To</label>
            <input type="date" value={endDate} onChange={e => { setEnd(e.target.value); setPage(1); }} style={inputStyle} />
          </div>

          {/* Clear */}
          {hasFilters && (
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={clearFilters} style={{ ...inputStyle, width: 'auto', color: '#EF4444', fontWeight: 600, cursor: 'pointer', background: '#fff', border: '1.5px solid #FECACA' }}>
                Clear All
              </button>
            </div>
          )}
        </div>
      )}

      {/* Summary counts */}
      {history && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 2px' }}>
          <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
            Showing <strong style={{ color: '#1e293b' }}>{records.length}</strong> of{' '}
            <strong style={{ color: '#1e293b' }}>{history.total}</strong> records
          </p>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
            Page {history.page} of {history.total_pages}
          </p>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
          <div style={{ width: '32px', height: '32px', border: '3px solid #e2e8f0', borderTopColor: '#6366F1', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      ) : error ? (
        <div style={{ padding: '20px', borderRadius: '12px', background: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', display: 'flex', gap: '10px', alignItems: 'center' }}>
          <span style={{ fontSize: '0.85rem' }}>{error}</span>
          <button onClick={refetch} style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#6366F1', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer' }}>Retry</button>
        </div>
      ) : records.length === 0 ? (
        <div style={{ padding: '48px', textAlign: 'center', borderRadius: '16px', background: '#f8fafc', border: '1px dashed #e2e8f0' }}>
          <Filter size={32} style={{ color: '#cbd5e1', margin: '0 auto 12px' }} />
          <p style={{ color: '#94a3b8', fontWeight: 500 }}>No records match your filters</p>
        </div>
      ) : (
        <div style={{ borderRadius: '14px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                {['Date', 'Course', 'Status', 'Marked By', 'Time', 'Confidence'].map(h => (
                  <th key={h} style={{
                    padding: '10px 14px', textAlign: 'left',
                    fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em',
                    textTransform: 'uppercase', color: '#94a3b8',
                    whiteSpace: 'nowrap',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((rec, i) => (
                <tr
                  key={`${rec.date}-${rec.course_code}-${i}`}
                  style={{
                    borderBottom: i < records.length - 1 ? '1px solid #f1f5f9' : 'none',
                    background: i % 2 === 0 ? '#fff' : '#fafbff',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#f1f5f9')}
                  onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? '#fff' : '#fafbff')}
                >
                  <td style={{ padding: '10px 14px', fontSize: '0.8rem', color: '#334155', fontWeight: 600, whiteSpace: 'nowrap' }}>
                    {rec.date}
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <div>
                      <p style={{ fontSize: '0.8rem', fontWeight: 700, color: '#1e293b' }}>{rec.course_code}</p>
                      <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '1px' }}>{rec.course_name}</p>
                    </div>
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <StatusBadge status={rec.status} />
                  </td>
                  <td style={{ padding: '10px 14px', fontSize: '0.78rem', color: '#64748b' }}>
                    {rec.marked_by_name ?? rec.marked_by ?? '—'}
                  </td>
                  <td style={{ padding: '10px 14px', fontSize: '0.75rem', color: '#94a3b8', fontFamily: 'monospace' }}>
                    {rec.time ?? rec.timestamp?.slice(11, 16) ?? '—'}
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    {rec.confidence != null ? (
                      <span style={{ fontSize: '0.72rem', fontFamily: 'monospace', padding: '2px 8px', borderRadius: '6px', background: '#f1f5f9', color: '#475569', fontWeight: 600 }}>
                        {(rec.confidence * 100).toFixed(0)}%
                      </span>
                    ) : <span style={{ color: '#cbd5e1' }}>—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {history && history.total_pages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              width: '34px', height: '34px', borderRadius: '10px', border: '1.5px solid #e2e8f0',
              background: page === 1 ? '#f8fafc' : '#fff', cursor: page === 1 ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              opacity: page === 1 ? 0.4 : 1,
            }}
          >
            <ChevronLeft size={16} style={{ color: '#64748b' }} />
          </button>

          {Array.from({ length: Math.min(7, history.total_pages) }, (_, i) => {
            const pg = Math.max(1, Math.min(page - 3, history.total_pages - 6)) + i;
            if (pg > history.total_pages) return null;
            const active = pg === page;
            return (
              <button
                key={pg}
                onClick={() => setPage(pg)}
                style={{
                  width: '34px', height: '34px', borderRadius: '10px', fontSize: '0.8rem', fontWeight: 600,
                  border: `1.5px solid ${active ? '#6366F1' : '#e2e8f0'}`,
                  background: active ? '#6366F1' : '#fff',
                  color: active ? '#fff' : '#64748b',
                  cursor: 'pointer',
                }}
              >
                {pg}
              </button>
            );
          })}

          <button
            onClick={() => setPage(p => Math.min(history.total_pages, p + 1))}
            disabled={page === history.total_pages}
            style={{
              width: '34px', height: '34px', borderRadius: '10px', border: '1.5px solid #e2e8f0',
              background: page === history.total_pages ? '#f8fafc' : '#fff',
              cursor: page === history.total_pages ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              opacity: page === history.total_pages ? 0.4 : 1,
            }}
          >
            <ChevronRight size={16} style={{ color: '#64748b' }} />
          </button>
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
      `}</style>
    </div>
  );
};

export default AttendanceHistory;
