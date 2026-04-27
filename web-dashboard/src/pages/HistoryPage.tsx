import React, { useState, useEffect } from 'react';
import { Search, ChevronLeft, ChevronRight, Download, SlidersHorizontal, X } from 'lucide-react';
import { useDashboardStore } from '@/store';
import { attendanceAPI } from '@/services/api';
import { Layout, SystemAlert, Card, Button, Table, Badge } from '@/components';

export const HistoryPage: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [historyData, setHistoryData] = useState<any[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>('');
  const [filtersExpanded, setFiltersExpanded] = useState(false);

  const { systemRunning, lastSyncTime, error, courses } = useDashboardStore();

  useEffect(() => { fetchHistory(); }, [currentPage, selectedCourse]);

  const fetchHistory = async () => {
    setIsLoading(true);
    try {
      const data = await attendanceAPI.getAttendanceHistory(
        selectedCourse || undefined,
        startDate || undefined,
        endDate || undefined,
        currentPage,
        30,
      );
      setHistoryData(data);
      setTotalPages(Math.ceil(data.length / 30) || 1);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
    setIsLoading(false);
  };

  const handleSearch = () => { setCurrentPage(1); fetchHistory(); };

  const handleExportCSV = () => {
    if (historyData.length === 0) return;
    const headers = ['Student Name', 'Student ID', 'Course', 'Date', 'Status', 'Confidence'];
    const csv = [
      headers.join(','),
      ...historyData.map((r) =>
        [
          r.student_name,
          r.student_id,
          r.course_name,
          new Date(r.marked_at).toLocaleString(),
          r.status,
          r.confidence ? `${(r.confidence * 100).toFixed(0)}%` : 'N/A',
        ].join(',')
      ),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `attendance-history-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  const filteredData = historyData.filter((record) => {
    const q = searchTerm.toLowerCase();
    return (
      record.student_name.toLowerCase().includes(q) ||
      record.student_id.toLowerCase().includes(q)
    );
  });

  const statusVariant: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'gray'> = {
    present: 'success',
    late: 'warning',
    absent: 'danger',
    excused: 'info',
  };

  const tableColumns = [
    {
      key: 'student_name' as const,
      label: 'Student',
      render: (value: string, row: any) => (
        <div className="flex items-center gap-2.5">
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%)' }}
          >
            {value.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--ink)' }}>{value}</p>
            <p className="text-[11px] font-mono" style={{ color: 'var(--whisper)' }}>{row.student_id}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'course_name' as const,
      label: 'Course',
      render: (value: string) => (
        <span className="text-xs" style={{ color: 'var(--muted)' }}>{value}</span>
      ),
    },
    {
      key: 'marked_at' as const,
      label: 'Date & Time',
      render: (value: string) => (
        <span
          className="text-xs font-mono"
          style={{ color: 'var(--muted)' }}
        >
          {new Date(value).toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
          })}
        </span>
      ),
    },
    {
      key: 'status' as const,
      label: 'Status',
      render: (value: string) => (
        <Badge variant={statusVariant[value] ?? 'gray'} size="sm">
          {value.charAt(0).toUpperCase() + value.slice(1)}
        </Badge>
      ),
    },
    {
      key: 'confidence' as const,
      label: 'Confidence',
      render: (value: number | undefined) => value ? (
        <span
          className="text-xs font-mono px-2 py-0.5 rounded-full"
          style={{
            background: 'rgba(155,122,58,0.08)',
            color: 'var(--gold)',
            border: '1px solid rgba(155,122,58,0.15)',
          }}
        >
          {(value * 100).toFixed(0)}%
        </span>
      ) : (
        <span style={{ color: 'var(--cream-400)', fontSize: '0.75rem' }}>—</span>
      ),
    },
  ];

  const hasActiveFilters = searchTerm || startDate || endDate || selectedCourse;

  return (
    <Layout systemRunning={systemRunning} lastSyncTime={lastSyncTime}>
      <div className="space-y-7">

        {!systemRunning && <SystemAlert systemRunning={systemRunning} error={error} />}

        {/* ── Page Header ───────────────────────────────────────────────────── */}
        <div className="flex items-end justify-between animate-fade-in-up">
          <div>
            <p className="text-xs font-semibold tracking-widest uppercase mb-1" style={{ color: 'var(--whisper)' }}>
              Records
            </p>
            <h1
              className="text-3xl font-medium leading-none"
              style={{ fontFamily: 'Fraunces, serif', color: 'var(--ink)' }}
            >
              Attendance History
            </h1>
          </div>
          <Button
            onClick={handleExportCSV}
            variant="secondary"
            size="sm"
            disabled={filteredData.length === 0}
          >
            <Download size={13} />
            Export CSV
          </Button>
        </div>

        {/* ── Search + Filter Card ──────────────────────────────────────────── */}
        <Card className="!p-5 animate-fade-in-up">
          {/* Search row */}
          <div className="flex gap-3">
            {/* Search input */}
            <div className="relative flex-1">
              <Search
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                style={{ color: 'var(--whisper)' }}
              />
              <input
                type="text"
                placeholder="Search by name or student ID…"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                style={{
                  width: '100%',
                  paddingLeft: '36px',
                  paddingRight: searchTerm ? '36px' : '14px',
                  paddingTop: '9px',
                  paddingBottom: '9px',
                  fontSize: '0.8125rem',
                  background: 'rgba(155,122,58,0.04)',
                  border: '1px solid rgba(155,122,58,0.16)',
                  borderRadius: '12px',
                  color: 'var(--ink)',
                }}
              />
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                  style={{ color: 'var(--whisper)' }}
                >
                  <X size={13} />
                </button>
              )}
            </div>

            {/* Filter toggle */}
            <button
              onClick={() => setFiltersExpanded(!filtersExpanded)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl btn-press text-sm font-medium transition-all"
              style={{
                background: filtersExpanded || hasActiveFilters
                  ? 'linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%)'
                  : 'rgba(155,122,58,0.08)',
                color: filtersExpanded || hasActiveFilters ? '#fff' : 'var(--muted)',
                border: `1px solid ${filtersExpanded || hasActiveFilters ? 'rgba(155,122,58,0.40)' : 'rgba(155,122,58,0.15)'}`,
                boxShadow: filtersExpanded || hasActiveFilters ? '0 2px 10px rgba(155,122,58,0.22)' : 'none',
              }}
            >
              <SlidersHorizontal size={14} />
              Filters
              {hasActiveFilters && (
                <span
                  className="w-4 h-4 rounded-full text-[10px] font-bold flex items-center justify-center flex-shrink-0"
                  style={{ background: 'rgba(255,255,255,0.25)' }}
                >
                  ●
                </span>
              )}
            </button>

            <Button onClick={handleSearch} variant="primary" size="sm">Search</Button>
          </div>

          {/* Expanded filters */}
          {filtersExpanded && (
            <div className="mt-4 pt-4 animate-fade-in-up" style={{ borderTop: '1px solid rgba(155,122,58,0.12)' }}>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Course */}
                <div>
                  <label
                    className="block text-[11px] font-semibold tracking-widest uppercase mb-1.5"
                    style={{ color: 'var(--whisper)' }}
                  >
                    Course
                  </label>
                  <select
                    value={selectedCourse}
                    onChange={(e) => { setSelectedCourse(e.target.value); setCurrentPage(1); }}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      fontSize: '0.8125rem',
                      background: 'rgba(155,122,58,0.04)',
                      border: '1px solid rgba(155,122,58,0.16)',
                      borderRadius: '10px',
                      color: 'var(--ink)',
                      appearance: 'none',
                    }}
                  >
                    <option value="">All Courses</option>
                    {courses.map((course) => (
                      <option key={course.id} value={course.id}>
                        {course.code} — {course.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Start date */}
                <div>
                  <label
                    className="block text-[11px] font-semibold tracking-widest uppercase mb-1.5"
                    style={{ color: 'var(--whisper)' }}
                  >
                    From
                  </label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      fontSize: '0.8125rem',
                      background: 'rgba(155,122,58,0.04)',
                      border: '1px solid rgba(155,122,58,0.16)',
                      borderRadius: '10px',
                      color: startDate ? 'var(--ink)' : 'var(--whisper)',
                    }}
                  />
                </div>

                {/* End date */}
                <div>
                  <label
                    className="block text-[11px] font-semibold tracking-widest uppercase mb-1.5"
                    style={{ color: 'var(--whisper)' }}
                  >
                    To
                  </label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      fontSize: '0.8125rem',
                      background: 'rgba(155,122,58,0.04)',
                      border: '1px solid rgba(155,122,58,0.16)',
                      borderRadius: '10px',
                      color: endDate ? 'var(--ink)' : 'var(--whisper)',
                    }}
                  />
                </div>
              </div>

              {/* Clear filters */}
              {hasActiveFilters && (
                <button
                  onClick={() => {
                    setSearchTerm('');
                    setStartDate('');
                    setEndDate('');
                    setSelectedCourse('');
                    setCurrentPage(1);
                  }}
                  className="mt-3 text-xs font-medium btn-press"
                  style={{ color: 'var(--terra)', textDecoration: 'underline', textDecorationStyle: 'dotted' }}
                >
                  Clear all filters
                </button>
              )}
            </div>
          )}
        </Card>

        {/* ── Results Table Card ─────────────────────────────────────────────── */}
        <Card className="animate-fade-in-up">
          {/* Table header */}
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2
                className="text-base font-semibold leading-none"
                style={{ fontFamily: 'Fraunces, serif', color: 'var(--ink)' }}
              >
                Records
              </h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--whisper)' }}>
                {filteredData.length} {filteredData.length === 1 ? 'entry' : 'entries'} found
              </p>
            </div>

            {/* Summary pills */}
            <div className="hidden md:flex items-center gap-2">
              {(
                [
                  { status: 'present', label: 'Present', color: 'var(--sage)', bg: 'rgba(107,138,113,0.10)' },
                  { status: 'late', label: 'Late', color: '#9B7030', bg: 'rgba(176,128,48,0.10)' },
                  { status: 'absent', label: 'Absent', color: 'var(--terra)', bg: 'rgba(193,123,91,0.10)' },
                ] as const
              ).map(({ status, label, color, bg }) => {
                const count = filteredData.filter((r) => r.status === status).length;
                return (
                  <div
                    key={status}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-full"
                    style={{ background: bg, border: `1px solid ${bg.replace('0.10)', '0.22)')}` }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
                    <span className="text-[11px] font-mono font-medium" style={{ color }}>{count}</span>
                    <span className="text-[11px]" style={{ color: 'var(--whisper)' }}>{label}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="tac-divider mb-4" />

          <Table
            data={filteredData}
            columns={tableColumns}
            isLoading={isLoading}
            emptyMessage="No attendance records found"
          />

          {/* Pagination */}
          {totalPages > 1 && (
            <div
              className="flex items-center justify-between mt-6 pt-5"
              style={{ borderTop: '1px solid rgba(190,160,118,0.16)' }}
            >
              <p className="text-xs" style={{ color: 'var(--whisper)' }}>
                Page <span style={{ color: 'var(--gold)', fontWeight: 600 }}>{currentPage}</span> of {totalPages}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                  disabled={currentPage === 1}
                  className="w-8 h-8 rounded-xl flex items-center justify-center btn-press transition-all disabled:opacity-40"
                  style={{
                    background: 'rgba(155,122,58,0.08)',
                    border: '1px solid rgba(155,122,58,0.16)',
                    color: 'var(--muted)',
                  }}
                >
                  <ChevronLeft size={14} />
                </button>

                {/* Page numbers */}
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const page = Math.max(1, Math.min(currentPage - 2, totalPages - 4)) + i;
                  if (page > totalPages) return null;
                  const active = page === currentPage;
                  return (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className="w-8 h-8 rounded-xl flex items-center justify-center btn-press text-xs font-medium transition-all"
                      style={{
                        background: active
                          ? 'linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%)'
                          : 'rgba(155,122,58,0.08)',
                        color: active ? '#fff' : 'var(--muted)',
                        border: `1px solid ${active ? 'rgba(155,122,58,0.40)' : 'rgba(155,122,58,0.16)'}`,
                        boxShadow: active ? '0 2px 8px rgba(155,122,58,0.25)' : 'none',
                      }}
                    >
                      {page}
                    </button>
                  );
                })}

                <button
                  onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                  disabled={currentPage === totalPages}
                  className="w-8 h-8 rounded-xl flex items-center justify-center btn-press transition-all disabled:opacity-40"
                  style={{
                    background: 'rgba(155,122,58,0.08)',
                    border: '1px solid rgba(155,122,58,0.16)',
                    color: 'var(--muted)',
                  }}
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </Layout>
  );
};
