/**
 * AttendanceHistory.tsx
 *
 * Role-aware attendance history component.
 *
 * Student view   — paginated personal records with date / course / status filters,
 *                  course-breakdown strip, and CSV export.
 * Admin / Teacher — rich table with class, period, method (face / manual / QR),
 *                  manual-override badge, marked-by, confidence score, and stats strip.
 */

import React, { useState, useMemo } from 'react';
import {
  Search, Filter, Download, ChevronLeft, ChevronRight,
  CheckCircle, XCircle, Clock, Activity, X, SlidersHorizontal,
  Camera, Edit3, QrCode, Zap, ShieldAlert, User,
} from 'lucide-react';
import { useStudentAttendance, type CourseAttendanceStat } from '../hooks/useAttendanceHooks';
import type { AdminAttendanceRecord } from '../services/api';

// ── Shared constants ───────────────────────────────────────────────────────────

const STATUS_META = {
  present: { label: 'Present', hex: '#22C55E', bg: '#F0FDF4', icon: CheckCircle },
  absent:  { label: 'Absent',  hex: '#EF4444', bg: '#FEF2F2', icon: XCircle },
  late:    { label: 'Late',    hex: '#F59E0B', bg: '#FFFBEB', icon: Clock },
  pending: { label: 'Pending', hex: '#94A3B8', bg: '#F8FAFC', icon: Activity },
};

const METHOD_META: Record<string, { label: string; hex: string; bg: string; Icon: React.FC<any> }> = {
  face_recognition: { label: 'Face ID', hex: '#6366F1', bg: '#EEF2FF', Icon: Camera },
  manual:           { label: 'Manual',  hex: '#F59E0B', bg: '#FFFBEB', Icon: Edit3  },
  qr_code:          { label: 'QR Code', hex: '#8B5CF6', bg: '#F5F3FF', Icon: QrCode },
  auto:             { label: 'Auto',    hex: '#14B8A6', bg: '#F0FDFA', Icon: Zap    },
};

// ── Shared input style ─────────────────────────────────────────────────────────

const inputSx: React.CSSProperties = {
  padding: '8px 12px', borderRadius: 10, fontSize: '0.8rem',
  border: '1.5px solid #e2e8f0', background: '#fff', color: '#1e293b',
  outline: 'none', width: '100%',
};

// ── Shared small components ────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status as keyof typeof STATUS_META] ?? STATUS_META.pending;
  const Icon = meta.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 99,
      background: meta.bg, color: meta.hex,
      fontSize: '0.72rem', fontWeight: 700,
      border: `1px solid ${meta.hex}30`,
    }}>
      <Icon size={11} />{meta.label}
    </span>
  );
}

function MethodBadge({ method }: { method?: string }) {
  if (!method) return <span style={{ color: '#cbd5e1', fontSize: '0.72rem' }}>—</span>;
  const m = METHOD_META[method] ?? { label: method, hex: '#94a3b8', bg: '#F8FAFC', Icon: Activity };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 8px', borderRadius: 99,
      background: m.bg, color: m.hex,
      fontSize: '0.68rem', fontWeight: 700,
      border: `1px solid ${m.hex}28`,
    }}>
      <m.Icon size={10} />{m.label}
    </span>
  );
}

function OverrideBadge() {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      padding: '2px 7px', borderRadius: 99,
      background: '#FEF3C7', color: '#92400E',
      fontSize: '0.63rem', fontWeight: 700,
      border: '1px solid #FDE68A',
    }}>
      <ShieldAlert size={9} />Override
    </span>
  );
}

// ── Course breakdown strip (student summary) ───────────────────────────────────

function CourseBreakdownStrip({ courses }: { courses: CourseAttendanceStat[] }) {
  return (
    <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4 }}>
      {courses.map(c => (
        <div key={c.course_code} style={{
          flexShrink: 0, minWidth: 140, borderRadius: 14, padding: '12px 14px',
          background: `${c.band_color}0e`, border: `1.5px solid ${c.band_color}30`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 800, color: c.color, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{c.course_code}</span>
            <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 7px', borderRadius: 99, background: `${c.band_color}20`, color: c.band_color }}>
              {c.percentage.toFixed(0)}%
            </span>
          </div>
          <div style={{ height: 5, borderRadius: 99, background: '#e2e8f0', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${Math.min(100, c.percentage)}%`, background: c.band_color, borderRadius: 99, transition: 'width 0.6s ease' }} />
          </div>
          <p style={{ fontSize: '0.62rem', color: '#94a3b8', marginTop: 5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.course_name}</p>
        </div>
      ))}
    </div>
  );
}

// ── Shared pagination bar ──────────────────────────────────────────────────────

function PaginationBar({
  page, totalPages, onPage,
}: { page: number; totalPages: number; onPage: (p: number) => void }) {
  if (totalPages <= 1) return null;

  // Show a sliding window of up to 7 pages centred on the current page
  const windowSize = 7;
  const start = Math.max(1, Math.min(page - Math.floor(windowSize / 2), totalPages - windowSize + 1));
  const end   = Math.min(totalPages, start + windowSize - 1);
  const pages = Array.from({ length: end - start + 1 }, (_, i) => start + i);

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
      <button
        onClick={() => onPage(Math.max(1, page - 1))}
        disabled={page === 1}
        style={{ width: 34, height: 34, borderRadius: 10, border: '1.5px solid #e2e8f0', background: page === 1 ? '#f8fafc' : '#fff', cursor: page === 1 ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: page === 1 ? 0.4 : 1 }}
      >
        <ChevronLeft size={16} style={{ color: '#64748b' }} />
      </button>

      {pages.map(pg => (
        <button key={pg} onClick={() => onPage(pg)}
          style={{ width: 34, height: 34, borderRadius: 10, fontSize: '0.8rem', fontWeight: 600, border: `1.5px solid ${pg === page ? '#6366F1' : '#e2e8f0'}`, background: pg === page ? '#6366F1' : '#fff', color: pg === page ? '#fff' : '#64748b', cursor: 'pointer' }}
        >
          {pg}
        </button>
      ))}

      <button
        onClick={() => onPage(Math.min(totalPages, page + 1))}
        disabled={page === totalPages}
        style={{ width: 34, height: 34, borderRadius: 10, border: '1.5px solid #e2e8f0', background: page === totalPages ? '#f8fafc' : '#fff', cursor: page === totalPages ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: page === totalPages ? 0.4 : 1 }}
      >
        <ChevronRight size={16} style={{ color: '#64748b' }} />
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  STUDENT HISTORY VIEW
// ─────────────────────────────────────────────────────────────────────────────

interface AttendanceHistoryProps {
  studentId: string;
  availableCourses?: Array<{ code: string; name: string }>;
}

export const AttendanceHistory: React.FC<AttendanceHistoryProps> = ({
  studentId, availableCourses = [],
}) => {
  const [page, setPage]           = useState(1);
  const [pageSize]                = useState(20);
  const [courseFilter, setCourse] = useState('');
  const [startDate, setStart]     = useState('');
  const [endDate, setEnd]         = useState('');
  const [statusFilter, setStatus] = useState('');
  const [search, setSearch]       = useState('');
  const [showFilters, setShowFilt]= useState(false);

  const { history, summary, loading, error, refetch } = useStudentAttendance({
    studentId, page, pageSize,
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
    const csv = [headers, ...rows].map(row => row.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `attendance-${studentId}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Course summary strip */}
      {summary?.course_breakdown?.length ? (
        <CourseBreakdownStrip courses={summary.course_breakdown} />
      ) : null}

      {/* Controls bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        {/* Search */}
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search by course, faculty, date…"
            style={{ ...inputSx, paddingLeft: 32, paddingRight: search ? 32 : 12 }}
          />
          {search && (
            <button onClick={() => setSearch('')} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
              <X size={13} />
            </button>
          )}
        </div>

        {/* Filters toggle */}
        <button
          onClick={() => setShowFilt(!showFilters)}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', background: showFilters || hasFilters ? '#EEF2FF' : '#f8fafc', color: showFilters || hasFilters ? '#6366F1' : '#64748b', border: `1.5px solid ${showFilters || hasFilters ? '#A5B4FC' : '#e2e8f0'}` }}
        >
          <SlidersHorizontal size={14} />
          Filters {hasFilters && <span style={{ background: '#6366F1', color: '#fff', borderRadius: 99, padding: '0 5px', fontSize: '0.65rem' }}>●</span>}
        </button>

        {/* Export */}
        <button
          onClick={exportCSV}
          disabled={!records.length}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, fontSize: '0.8rem', fontWeight: 600, cursor: records.length ? 'pointer' : 'not-allowed', background: '#f8fafc', color: '#64748b', border: '1.5px solid #e2e8f0', opacity: records.length ? 1 : 0.5 }}
        >
          <Download size={14} />Export
        </button>
      </div>

      {/* Expanded filters panel */}
      {showFilters && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, padding: 16, borderRadius: 14, background: '#f8fafc', border: '1px solid #e2e8f0', animation: 'fadeIn 0.2s ease' }}>
          <div>
            <label style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>Course</label>
            <select value={courseFilter} onChange={e => { setCourse(e.target.value); setPage(1); }} style={inputSx}>
              <option value="">All Courses</option>
              {availableCourses.map(c => <option key={c.code} value={c.code}>{c.code} — {c.name}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>Status</label>
            <select value={statusFilter} onChange={e => { setStatus(e.target.value); setPage(1); }} style={inputSx}>
              <option value="">All Statuses</option>
              {Object.entries(STATUS_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>From</label>
            <input type="date" value={startDate} onChange={e => { setStart(e.target.value); setPage(1); }} style={inputSx} />
          </div>
          <div>
            <label style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>To</label>
            <input type="date" value={endDate} onChange={e => { setEnd(e.target.value); setPage(1); }} style={inputSx} />
          </div>
          {hasFilters && (
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={clearFilters} style={{ ...inputSx, width: 'auto', color: '#EF4444', fontWeight: 600, cursor: 'pointer', background: '#fff', border: '1.5px solid #FECACA' }}>
                Clear All
              </button>
            </div>
          )}
        </div>
      )}

      {/* Record count */}
      {history && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 2px' }}>
          <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
            Showing <strong style={{ color: '#1e293b' }}>{records.length}</strong> of <strong style={{ color: '#1e293b' }}>{history.total}</strong> records
          </p>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Page {history.page} of {history.total_pages}</p>
        </div>
      )}

      {/* Table / States */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
          <div style={{ width: 32, height: 32, border: '3px solid #e2e8f0', borderTopColor: '#6366F1', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      ) : error ? (
        <div style={{ padding: 20, borderRadius: 12, background: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ fontSize: '0.85rem' }}>{error}</span>
          <button onClick={refetch} style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#6366F1', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer' }}>Retry</button>
        </div>
      ) : records.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', borderRadius: 16, background: '#f8fafc', border: '1px dashed #e2e8f0' }}>
          <Filter size={32} style={{ color: '#cbd5e1', margin: '0 auto 12px' }} />
          <p style={{ color: '#94a3b8', fontWeight: 500 }}>No records match your filters</p>
        </div>
      ) : (
        <div style={{ borderRadius: 14, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                {['Date', 'Course', 'Status', 'Marked By', 'Time', 'Confidence'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((rec, i) => (
                <tr
                  key={`${rec.date}-${rec.course_code}-${i}`}
                  style={{ borderBottom: i < records.length - 1 ? '1px solid #f1f5f9' : 'none', background: i % 2 === 0 ? '#fff' : '#fafbff', transition: 'background 0.15s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#f1f5f9')}
                  onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? '#fff' : '#fafbff')}
                >
                  <td style={{ padding: '10px 14px', fontSize: '0.8rem', color: '#334155', fontWeight: 600, whiteSpace: 'nowrap' }}>{rec.date}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <p style={{ fontSize: '0.8rem', fontWeight: 700, color: '#1e293b' }}>{rec.course_code}</p>
                    <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: 1 }}>{rec.course_name}</p>
                  </td>
                  <td style={{ padding: '10px 14px' }}><StatusBadge status={rec.status} /></td>
                  <td style={{ padding: '10px 14px', fontSize: '0.78rem', color: '#64748b' }}>{rec.marked_by_name ?? rec.marked_by ?? '—'}</td>
                  <td style={{ padding: '10px 14px', fontSize: '0.75rem', color: '#94a3b8', fontFamily: 'monospace' }}>{rec.time ?? rec.timestamp?.slice(11, 16) ?? '—'}</td>
                  <td style={{ padding: '10px 14px' }}>
                    {rec.confidence != null ? (
                      <span style={{ fontSize: '0.72rem', fontFamily: 'monospace', padding: '2px 8px', borderRadius: 6, background: '#f1f5f9', color: '#475569', fontWeight: 600 }}>
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

      <PaginationBar page={page} totalPages={history?.total_pages ?? 1} onPage={setPage} />

      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes fadeIn  { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
      `}</style>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  ADMIN / TEACHER HISTORY TABLE
// ─────────────────────────────────────────────────────────────────────────────

interface AdminHistoryTableProps {
  records: AdminAttendanceRecord[];
  loading: boolean;
  error: string | null;
  page: number;
  totalPages: number;
  total: number;
  stats?: { present: number; absent: number; late: number; total: number; rate: number };
  onPage: (p: number) => void;
  onRetry: () => void;
}

export const AdminHistoryTable: React.FC<AdminHistoryTableProps> = ({
  records, loading, error, page, totalPages, total, stats, onPage, onRetry,
}) => {
  const exportCSV = () => {
    if (!records.length) return;
    const headers = ['Date', 'Time', 'Student ID', 'Student Name', 'Roll No', 'Class', 'Course', 'Period', 'Status', 'Method', 'Override', 'Marked By', 'Confidence'];
    const rows = records.map(r => [
      r.date, r.time ?? '', r.student_id, r.student_name, r.roll_no ?? '',
      r.class_name ?? r.class_id ?? '', r.course_name ?? '', r.period_time ?? '',
      r.status, r.method ?? '', r.is_manual_override ? 'Yes' : 'No',
      r.marked_by_name ?? r.marked_by ?? '',
      r.confidence != null ? `${(r.confidence * 100).toFixed(0)}%` : '',
    ]);
    const csv = [headers, ...rows].map(row => row.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `admin-history-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Stats strip */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 10 }}>
          {([
            { label: 'Present', val: stats.present, hex: '#22C55E', bg: '#F0FDF4' },
            { label: 'Absent',  val: stats.absent,  hex: '#EF4444', bg: '#FEF2F2' },
            { label: 'Late',    val: stats.late,    hex: '#F59E0B', bg: '#FFFBEB' },
            { label: 'Total',   val: stats.total,   hex: '#6366F1', bg: '#EEF2FF' },
            { label: 'Rate',    val: `${stats.rate.toFixed(1)}%`, hex: stats.rate >= 75 ? '#22C55E' : '#EF4444', bg: stats.rate >= 75 ? '#F0FDF4' : '#FEF2F2' },
          ] as const).map(({ label, val, hex, bg }) => (
            <div key={label} style={{ padding: '10px 14px', borderRadius: 12, background: bg, border: `1px solid ${hex}25` }}>
              <p style={{ fontSize: '1.1rem', fontWeight: 800, color: hex, lineHeight: 1, fontFamily: 'monospace' }}>{val}</p>
              <p style={{ fontSize: '0.62rem', color: '#94a3b8', marginTop: 3, fontWeight: 500 }}>{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Export + count */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
          Showing <strong style={{ color: '#1e293b' }}>{records.length}</strong> of <strong style={{ color: '#1e293b' }}>{total}</strong> records
        </p>
        <button
          onClick={exportCSV}
          disabled={!records.length}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 13px', borderRadius: 10, fontSize: '0.78rem', fontWeight: 600, cursor: records.length ? 'pointer' : 'not-allowed', background: '#f8fafc', color: '#64748b', border: '1.5px solid #e2e8f0', opacity: records.length ? 1 : 0.5 }}
        >
          <Download size={13} />Export CSV
        </button>
      </div>

      {/* Table / States */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
          <div style={{ width: 36, height: 36, border: '3px solid #e2e8f0', borderTopColor: '#6366F1', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        </div>
      ) : error ? (
        <div style={{ padding: 20, borderRadius: 12, background: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ fontSize: '0.85rem' }}>{error}</span>
          <button onClick={onRetry} style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#6366F1', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer' }}>Retry</button>
        </div>
      ) : records.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', borderRadius: 16, background: '#f8fafc', border: '1px dashed #e2e8f0' }}>
          <Filter size={32} style={{ color: '#cbd5e1', margin: '0 auto 12px' }} />
          <p style={{ color: '#94a3b8', fontWeight: 500 }}>No records match the selected filters</p>
        </div>
      ) : (
        <div style={{ borderRadius: 14, border: '1px solid #e2e8f0', overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                {['Date / Time', 'Student', 'Class', 'Course / Period', 'Status', 'Method', 'Marked By', 'Confidence'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#94a3b8', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((r, i) => (
                <tr
                  key={r.record_id || i}
                  style={{ borderBottom: i < records.length - 1 ? '1px solid #f1f5f9' : 'none', background: i % 2 === 0 ? '#fff' : '#fafbff', transition: 'background 0.15s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#f1f5f9')}
                  onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? '#fff' : '#fafbff')}
                >
                  {/* Date / Time */}
                  <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
                    <p style={{ fontSize: '0.8rem', fontWeight: 600, color: '#334155' }}>{r.date}</p>
                    {r.time && <p style={{ fontSize: '0.7rem', color: '#94a3b8', fontFamily: 'monospace', marginTop: 1 }}>{r.time}</p>}
                  </td>

                  {/* Student */}
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ width: 30, height: 30, borderRadius: '50%', background: '#EEF2FF', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <User size={14} style={{ color: '#6366F1' }} />
                      </div>
                      <div>
                        <p style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1e293b' }}>{r.student_name}</p>
                        <p style={{ fontSize: '0.68rem', color: '#94a3b8', fontFamily: 'monospace' }}>
                          {r.student_id}{r.roll_no ? ` · ${r.roll_no}` : ''}
                        </p>
                      </div>
                    </div>
                  </td>

                  {/* Class */}
                  <td style={{ padding: '10px 14px', fontSize: '0.78rem', color: '#475569' }}>
                    {r.class_name ?? r.class_id ?? <span style={{ color: '#cbd5e1' }}>—</span>}
                  </td>

                  {/* Course / Period */}
                  <td style={{ padding: '10px 14px' }}>
                    {r.course_code && <p style={{ fontSize: '0.75rem', fontWeight: 700, color: '#6366F1' }}>{r.course_code}</p>}
                    {r.course_name && <p style={{ fontSize: '0.72rem', color: '#64748b' }}>{r.course_name}</p>}
                    {r.period_time && <p style={{ fontSize: '0.67rem', color: '#94a3b8', fontFamily: 'monospace', marginTop: 1 }}>{r.period_time}</p>}
                  </td>

                  {/* Status + override badge */}
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-start' }}>
                      <StatusBadge status={r.status} />
                      {r.is_manual_override && <OverrideBadge />}
                    </div>
                  </td>

                  {/* Method */}
                  <td style={{ padding: '10px 14px' }}><MethodBadge method={r.method} /></td>

                  {/* Marked By + override reason */}
                  <td style={{ padding: '10px 14px', fontSize: '0.78rem', color: '#64748b' }}>
                    {r.marked_by_name ?? r.marked_by ?? <span style={{ color: '#cbd5e1' }}>—</span>}
                    {r.override_reason && (
                      <p style={{ fontSize: '0.65rem', color: '#F59E0B', marginTop: 2, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.override_reason}>
                        ↳ {r.override_reason}
                      </p>
                    )}
                  </td>

                  {/* Confidence */}
                  <td style={{ padding: '10px 14px' }}>
                    {r.confidence != null ? (
                      <div>
                        <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', fontWeight: 700, color: r.confidence >= 0.85 ? '#22C55E' : r.confidence >= 0.70 ? '#F59E0B' : '#EF4444' }}>
                          {(r.confidence * 100).toFixed(0)}%
                        </span>
                        <div style={{ height: 3, borderRadius: 99, background: '#e2e8f0', marginTop: 3, width: 48, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${r.confidence * 100}%`, background: r.confidence >= 0.85 ? '#22C55E' : r.confidence >= 0.70 ? '#F59E0B' : '#EF4444', borderRadius: 99 }} />
                        </div>
                      </div>
                    ) : <span style={{ color: '#cbd5e1', fontSize: '0.72rem' }}>—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <PaginationBar page={page} totalPages={totalPages} onPage={onPage} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default AttendanceHistory;