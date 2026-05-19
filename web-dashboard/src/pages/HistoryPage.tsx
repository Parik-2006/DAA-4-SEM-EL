/**
 * HistoryPage.tsx
 *
 * Role-aware attendance history page.
 *
 * • admin / teacher  → AdminHistoryPage with full filter panel (class, period,
 *                      date range, status, search, auto-refresh) powered by
 *                      useAdminHistory + useClassesAndPeriods.
 * • student          → StudentHistoryView — strict self-only view reading
 *                      identity from sessionStorage, styled with CSS design
 *                      tokens.
 *
 * Role is resolved via getStoredRole() (utils/roles).
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Layout } from '../components/Layout';
import { AttendanceHistory, AdminHistoryTable } from '../components/AttendanceHistory';
import { useAdminHistory, useClassesAndPeriods } from '../hooks/useAttendanceHooks';
import { useContiniousAttendancePolling } from '../hooks/useAttendanceRefresh';
import { getStoredAssignedSections, getSessionToken } from '../services/firebase/auth.service';
import { getStoredRole } from '../utils/roles';
import ChannelBadge from '../components/ChannelBadge';
import useTeacherRealtime from '../hooks/useTeacherRealtime';
import type { AttendanceRecord } from '../services/api';
import {
  Calendar, SlidersHorizontal, RefreshCw, X, Clock,
  BookOpen, Users, Activity,
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

const inputSx: React.CSSProperties = {
  padding: '8px 12px',
  borderRadius: 10,
  fontSize: '0.8rem',
  border: '1.5px solid #e2e8f0',
  background: '#fff',
  color: '#1e293b',
  outline: 'none',
  width: '100%',
};

const POLL_INTERVAL_OPTIONS = [
  { label: 'Off',   value: 0       },
  { label: '10 s',  value: 10_000  },
  { label: '30 s',  value: 30_000  },
  { label: '1 min', value: 60_000  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Admin filter state
// ─────────────────────────────────────────────────────────────────────────────

interface AdminFiltersState {
  classId:      string;
  periodId:     string;
  date:         string;
  startDate:    string;
  endDate:      string;
  status:       string;
  search:       string;
  page:         number;
  pollInterval: number;
}

const DEFAULT_ADMIN_FILTERS: AdminFiltersState = {
  classId:      '',
  periodId:     '',
  date:         todayISO(),
  startDate:    '',
  endDate:      '',
  status:       '',
  search:       '',
  page:         1,
  pollInterval: 0,
};

// ─────────────────────────────────────────────────────────────────────────────
// AdminFilterPanel
// ─────────────────────────────────────────────────────────────────────────────

function AdminFilterPanel({
  filters,
  onChange,
  allowedClassIds = [],
}: {
  filters: AdminFiltersState;
  onChange: (patch: Partial<AdminFiltersState>) => void;
  allowedClassIds?: string[];
}) {
  const { classes, periods, classesLoading, periodsLoading, loadPeriods } =
    useClassesAndPeriods();

  const visibleClasses = allowedClassIds.length
    ? classes.filter(c => allowedClassIds.includes(c.class_id))
    : classes;

  // Reload periods whenever class or date changes
  useEffect(() => {
    if (filters.classId) {
      loadPeriods(filters.classId, filters.date || undefined);
    }
  }, [filters.classId, filters.date, loadPeriods]);

  const handleClass = (classId: string) => onChange({ classId, periodId: '', page: 1 });

  const hasFilters =
    filters.classId || filters.periodId || filters.status || filters.search ||
    filters.startDate || filters.endDate ||
    (filters.date && filters.date !== todayISO());

  const clearAll = () =>
    onChange({ ...DEFAULT_ADMIN_FILTERS, date: todayISO(), pollInterval: filters.pollInterval });

  return (
    <div
      style={{
        display: 'flex', flexDirection: 'column', gap: 16,
        padding: 20, borderRadius: 16,
        background: '#F8FAFC', border: '1px solid #E2E8F0',
        animation: 'fadeIn 0.2s ease',
      }}
    >
      {/* Row 1: class + period + date */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12 }}>
        {/* Class */}
        <div>
          <label htmlFor="history-filter-class" style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>
            <Users size={10} style={{ display: 'inline', marginRight: 4 }} />
            Class / Section
          </label>
          <select
            id="history-filter-class"
            name="classId"
            value={filters.classId}
            onChange={e => handleClass(e.target.value)}
            style={inputSx}
            disabled={classesLoading}
          >
            {allowedClassIds.length === 0 && <option value="">All Classes</option>}
            {visibleClasses.map(c => (
              <option key={c.class_id} value={c.class_id}>
                {c.class_name}{c.section ? ` (${c.section})` : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Period */}
        <div>
          <label htmlFor="history-filter-period" style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>
            <Clock size={10} style={{ display: 'inline', marginRight: 4 }} />
            Period / Hour
          </label>
          <select
            id="history-filter-period"
            name="periodId"
            value={filters.periodId}
            onChange={e => onChange({ periodId: e.target.value, page: 1 })}
            style={inputSx}
            disabled={!filters.classId || periodsLoading}
          >
            <option value="">All Periods</option>
            {periods.map(p => (
              <option key={p.period_id} value={p.period_id}>
                {p.start_time}–{p.end_time} · {p.course_code}
              </option>
            ))}
          </select>
          {!filters.classId && (
            <p style={{ fontSize: '0.62rem', color: '#94a3b8', marginTop: 3 }}>Select a class first</p>
          )}
        </div>

        {/* Specific date */}
        <div>
          <label htmlFor="history-filter-date" style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>
            <Calendar size={10} style={{ display: 'inline', marginRight: 4 }} />
            Date
          </label>
          <input
            id="history-filter-date"
            name="date"
            type="date"
            value={filters.date}
            onChange={e => onChange({ date: e.target.value, startDate: '', endDate: '', page: 1 })}
            style={inputSx}
          />
        </div>
      </div>

      {/* Row 2: date range + status + search */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12 }}>
        <div>
          <label htmlFor="history-filter-start-date" style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>
            From (range)
          </label>
          <input
            id="history-filter-start-date"
            name="startDate"
            type="date"
            value={filters.startDate}
            onChange={e => onChange({ startDate: e.target.value, date: '', page: 1 })}
            style={inputSx}
          />
        </div>
        <div>
          <label htmlFor="history-filter-end-date" style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>
            To (range)
          </label>
          <input
            id="history-filter-end-date"
            name="endDate"
            type="date"
            value={filters.endDate}
            onChange={e => onChange({ endDate: e.target.value, date: '', page: 1 })}
            style={inputSx}
          />
        </div>
        <div>
          <label htmlFor="history-filter-status" style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>
            Status
          </label>
          <select
            id="history-filter-status"
            name="status"
            value={filters.status}
            onChange={e => onChange({ status: e.target.value, page: 1 })}
            style={inputSx}
          >
            <option value="">All Statuses</option>
            <option value="present">Present</option>
            <option value="absent">Absent</option>
            <option value="late">Late</option>
            <option value="pending">Pending</option>
          </select>
        </div>
        <div>
          <label htmlFor="history-filter-search" style={{ fontSize: '0.65rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }}>
            Search student
          </label>
          <input
            id="history-filter-search"
            name="search"
            value={filters.search}
            onChange={e => onChange({ search: e.target.value, page: 1 })}
            placeholder="Name or ID…"
            style={inputSx}
          />
        </div>
      </div>

      {/* Row 3: auto-refresh + clear */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Activity size={13} style={{ color: '#6366F1' }} />
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Auto-refresh:</span>
          {POLL_INTERVAL_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => onChange({ pollInterval: opt.value })}
              style={{
                padding: '4px 10px', borderRadius: 8, fontSize: '0.72rem', fontWeight: 600,
                cursor: 'pointer',
                background: filters.pollInterval === opt.value ? '#6366F1' : '#f1f5f9',
                color:      filters.pollInterval === opt.value ? '#fff'    : '#64748b',
                border:     `1px solid ${filters.pollInterval === opt.value ? '#6366F1' : '#e2e8f0'}`,
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {hasFilters && (
          <button
            onClick={clearAll}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', borderRadius: 9, fontSize: '0.75rem', fontWeight: 600,
              cursor: 'pointer', background: '#FEF2F2', color: '#DC2626', border: '1px solid #FECACA',
            }}
          >
            <X size={12} />Clear All Filters
          </button>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// AttendanceRow  (staff live stream — from existing file, design-token styled)
// ─────────────────────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, { bg: string; color: string }> = {
  present: { bg: 'rgba(107,138,113,0.12)', color: 'var(--sage)'  },
  late:    { bg: 'rgba(176,128,48,0.12)',  color: '#9B7030'      },
  absent:  { bg: 'rgba(193,123,91,0.12)', color: 'var(--terra)'  },
  excused: { bg: 'rgba(106,130,168,0.12)', color: '#5A72A0'      },
};

const AttendanceRow: React.FC<{ record: AttendanceRecord }> = ({ record }) => {
  const [hovered, setHovered] = useState(false);
  const sStyle = STATUS_STYLES[record.status] ?? STATUS_STYLES.present;

  return (
    <tr
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        borderBottom: '1px solid rgba(190,160,118,0.10)',
        background:   hovered ? 'rgba(155,122,58,0.04)' : 'transparent',
        transition:   'background 0.15s ease',
      }}
    >
      {/* Student name */}
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
            style={{ background: 'rgba(155,122,58,0.12)', color: 'var(--gold)' }}
          >
            {record.student_name?.charAt(0).toUpperCase() ?? '?'}
          </div>
          <span className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
            {record.student_name}
          </span>
        </div>
      </td>

      {/* Student ID */}
      <td className="px-6 py-4">
        <span className="text-sm font-mono" style={{ color: 'var(--whisper)' }}>
          {record.student_id}
        </span>
      </td>

      {/* Course */}
      <td className="px-6 py-4">
        <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--muted)' }}>
          <BookOpen size={14} style={{ color: 'var(--whisper)', flexShrink: 0 }} />
          <span>{record.course_name || '—'}</span>
        </div>
      </td>

      {/* Time */}
      <td className="px-6 py-4">
        <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--muted)' }}>
          <Clock size={14} style={{ color: 'var(--whisper)', flexShrink: 0 }} />
          <span>
            {record.marked_at
              ? new Date(record.marked_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : '—'}
          </span>
        </div>
      </td>

      {/* Status badge */}
      <td className="px-6 py-4">
        <span
          className="px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider"
          style={{ background: sStyle.bg, color: sStyle.color }}
        >
          {record.status}
        </span>
      </td>
    </tr>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// AdminHistoryPage  (full filter panel + AdminHistoryTable from doc 4)
// ─────────────────────────────────────────────────────────────────────────────

function AdminHistoryPage({ allowedClassIds = [] }: { allowedClassIds?: string[] }) {
  const role = getStoredRole();
  const teacherScoped = role === 'teacher';
  const realtimeClientId = sessionStorage.getItem('user_id') || '';
  const realtimeToken = getSessionToken();
  const { totalUnread } = useTeacherRealtime({
    clientId: realtimeClientId,
    token: realtimeToken ?? undefined,
  });
  const [filters, setFilters] = useState<AdminFiltersState>({
    ...DEFAULT_ADMIN_FILTERS,
    date: todayISO(),
    classId: teacherScoped && allowedClassIds.length > 0 ? allowedClassIds[0] : '',
  });
  const [showFilters, setShowFilters] = useState(true);

  useEffect(() => {
    if (!teacherScoped) return;
    if (allowedClassIds.length === 0) return;
    if (filters.classId) return;
    setFilters(prev => ({ ...prev, classId: allowedClassIds[0], periodId: '' }));
  }, [teacherScoped, allowedClassIds, filters.classId]);

  const mergeFilters = useCallback((patch: Partial<AdminFiltersState>) => {
    setFilters(prev => ({ ...prev, ...patch }));
  }, []);

  const { data, loading, error, refetch } = useAdminHistory({
    classId:        filters.classId   || undefined,
    periodId:       filters.periodId  || undefined,
    date:           filters.date      || undefined,
    startDate:      filters.startDate || undefined,
    endDate:        filters.endDate   || undefined,
    status:         filters.status    || undefined,
    search:         filters.search    || undefined,
    page:           filters.page,
    limit:          50,
    pollIntervalMs: filters.pollInterval,
    enabled:        !teacherScoped || Boolean(filters.classId),
  });

  useEffect(() => {
    const handler = () => {
      // immediate refresh when attendance is marked elsewhere
      refetch();
    };
    window.addEventListener('attendance:marked', handler);
    return () => window.removeEventListener('attendance:marked', handler);
  }, [refetch]);

  const activeFilterCount = [
    filters.classId, filters.periodId, filters.status, filters.search,
    filters.startDate, filters.endDate,
    filters.date && filters.date !== todayISO() ? filters.date : '',
  ].filter(Boolean).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <p style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#94a3b8', marginBottom: 3 }}>
            Attendance Management
          </p>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 900, color: '#1e293b', fontFamily: 'Fraunces, Georgia, serif' }}>
            History & Audit Log
          </h1>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Live indicator */}
          {filters.pollInterval > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 99, background: '#F0FDF4', border: '1px solid #BBF7D0' }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#22C55E', animation: 'pulse 1.5s infinite' }} />
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#16A34A' }}>
                Live · every {filters.pollInterval / 1000}s
              </span>
            </div>
          )}

          {/* Manual refresh */}
          <button
            onClick={refetch}
            disabled={loading}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 14px', borderRadius: 10, fontSize: '0.8rem', fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              background: '#f8fafc', color: '#64748b', border: '1.5px solid #e2e8f0',
              opacity: loading ? 0.7 : 1,
            }}
          >
            <RefreshCw size={14} style={{ animation: loading ? 'spin 0.8s linear infinite' : 'none' }} />
            Refresh
          </button>

          {/* Realtime badge (staff only) */}
          {role !== 'student' && <ChannelBadge count={totalUnread} />}

          {/* Filter toggle */}
          <button
            onClick={() => setShowFilters(v => !v)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 14px', borderRadius: 10, fontSize: '0.8rem', fontWeight: 600,
              cursor: 'pointer',
              background: showFilters || activeFilterCount > 0 ? '#EEF2FF' : '#f8fafc',
              color:      showFilters || activeFilterCount > 0 ? '#6366F1' : '#64748b',
              border:     `1.5px solid ${showFilters || activeFilterCount > 0 ? '#A5B4FC' : '#e2e8f0'}`,
            }}
          >
            <SlidersHorizontal size={14} />
            Filters
            {activeFilterCount > 0 && (
              <span style={{ background: '#6366F1', color: '#fff', borderRadius: 99, padding: '1px 6px', fontSize: '0.65rem', fontWeight: 700 }}>
                {activeFilterCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* ── Active filter chips ── */}
      {(filters.date || filters.classId || filters.periodId) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {filters.date && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 99, background: '#EEF2FF', border: '1px solid #A5B4FC', fontSize: '0.75rem', fontWeight: 700, color: '#6366F1' }}>
              <Calendar size={12} />
              {filters.date === todayISO() ? 'Today' : filters.date}
              {filters.date !== todayISO() && (
                <button onClick={() => mergeFilters({ date: todayISO() })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6366F1', padding: 0, marginLeft: 2 }}>
                  <X size={10} />
                </button>
              )}
            </div>
          )}
          {filters.classId && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 99, background: '#F5F3FF', border: '1px solid #C4B5FD', fontSize: '0.75rem', fontWeight: 700, color: '#7C3AED' }}>
              <Users size={12} />
              {filters.classId}
              {!teacherScoped && (
                <button onClick={() => mergeFilters({ classId: '', periodId: '' })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7C3AED', padding: 0, marginLeft: 2 }}>
                  <X size={10} />
                </button>
              )}
            </div>
          )}
          {filters.periodId && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 99, background: '#ECFDF5', border: '1px solid #6EE7B7', fontSize: '0.75rem', fontWeight: 700, color: '#059669' }}>
              <Clock size={12} />
              {filters.periodId}
              <button onClick={() => mergeFilters({ periodId: '' })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#059669', padding: 0, marginLeft: 2 }}>
                <X size={10} />
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Filter panel ── */}
      {showFilters && (
          <AdminFilterPanel filters={filters} onChange={mergeFilters} allowedClassIds={allowedClassIds} />
      )}

      {/* ── Table ── */}
      <AdminHistoryTable
        records={data?.records ?? []}
        loading={loading}
        error={error}
        page={filters.page}
        totalPages={data?.total_pages ?? 1}
        total={data?.total ?? 0}
        stats={data?.stats}
        onPage={p => mergeFilters({ page: p })}
        onRetry={refetch}
      />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// StaffHistoryView  (real-time stream for faculty/admin — from existing file)
// Used as a lightweight fallback when AdminHistoryTable is unavailable or
// the user wants the live-stream view without filters.
// ─────────────────────────────────────────────────────────────────────────────

const StaffHistoryView: React.FC = () => {
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [isLoading, setLoading] = useState(true);

  const fetchRecords = useCallback(async () => {
    try {
      const { attendanceAPI } = await import('../services/api');
      const data = await attendanceAPI.getLiveAttendance(undefined, 100);
      setRecords(data);
    } catch (err) {
      console.error('Error fetching attendance history:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecords();
    const interval = setInterval(fetchRecords, 10_000);
    const handler = () => void fetchRecords();
    window.addEventListener('attendance:updated', handler);
    return () => {
      clearInterval(interval);
      window.removeEventListener('attendance:updated', handler);
    };
  }, [fetchRecords]);

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)' }}
    >
      {/* Sub-header */}
      <div
        className="p-6 flex justify-between items-center"
        style={{ borderBottom: '1px solid rgba(190,160,118,0.18)', background: 'rgba(155,122,58,0.04)' }}
      >
        <h2 className="text-base font-bold" style={{ color: 'var(--ink)' }}>
          Real-time Attendance Stream
        </h2>
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ background: 'var(--sage)' }} />
            <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: 'var(--sage)' }} />
          </span>
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--sage)' }}>
            Live
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(190,160,118,0.18)', background: 'rgba(155,122,58,0.03)' }}>
              {['Student', 'Student ID', 'Period / Subject', 'Time', 'Status'].map(h => (
                <th key={h} className="px-6 py-4 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--whisper)' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-full border-[3px] border-t-transparent animate-spin"
                      style={{ borderColor: 'rgba(155,122,58,0.25)', borderTopColor: 'var(--gold)' }}
                    />
                    <p className="text-sm" style={{ color: 'var(--whisper)' }}>Loading history…</p>
                  </div>
                </td>
              </tr>
            ) : records.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center">
                  <p className="text-sm" style={{ color: 'var(--whisper)' }}>
                    No attendance records found for today.
                  </p>
                </td>
              </tr>
            ) : (
              records.map(record => <AttendanceRow key={record.id} record={record} />)
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// StudentHistoryView  (strict self-only, sessionStorage identity, CSS vars)
// ─────────────────────────────────────────────────────────────────────────────

const StudentHistoryView: React.FC = () => {
  // Identity MUST come from authenticated session — never localStorage
  const studentId = sessionStorage.getItem('user_id') ?? '';

  if (!studentId) {
    return (
      <div
        className="flex items-center justify-center py-20 rounded-2xl"
        style={{ background: 'rgba(193,123,91,0.06)', border: '1px dashed rgba(193,123,91,0.28)' }}
      >
        <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>
          Unable to load history — student session not found.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 mb-2">
              My Records
            </p>
            <h1 className="text-3xl font-black text-slate-900">
              Attendance History
            </h1>
            <p className="mt-2 text-sm text-slate-500 max-w-2xl">
              A complete view of your attendance records, styled like the staff dashboard but locked to your own account.
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">
            <Clock size={12} />
            {new Date().toLocaleDateString('en-IN', {
              weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
            })}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <AttendanceHistory studentId={studentId} />
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Root export
// ─────────────────────────────────────────────────────────────────────────────

export const HistoryPage: React.FC = () => {
  const role = getStoredRole();
  const assignedSections = role === 'teacher' ? getStoredAssignedSections() : [];

  return (
    <Layout>
      <div className="space-y-0">
        {role === 'student' ? (
          <StudentHistoryView />
        ) : (
          // admin/teacher get the full filter-driven AdminHistoryPage;
          // StaffHistoryView is available as a sub-section within it.
          <AdminHistoryPage allowedClassIds={assignedSections} />
        )}
      </div>

      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes pulse   { 0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(34,197,94,0.5);}50%{opacity:0.8;box-shadow:0 0 0 5px rgba(34,197,94,0);} }
        @keyframes fadeIn  { from{opacity:0;transform:translateY(-8px);}to{opacity:1;transform:none;} }
      `}</style>
    </Layout>
  );
};

export default HistoryPage;