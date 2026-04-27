import React, { useEffect, useState, useRef } from 'react';
import { RefreshCw, Users, TrendingUp, Activity } from 'lucide-react';
import { useDashboardStore } from '@/store';
import { attendanceAPI } from '@/services/api';
import {
  Layout,
  SystemAlert,
  StatCard,
  Card,
  AttendanceRecordCard,
  Button,
} from '@/components';

export const DashboardPage: React.FC = () => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const {
    systemRunning,
    lastSyncTime,
    error,
    liveRecords,
    stats,
    courses,
    selectedCourse,
    isPolling,
    setSystemRunning,
    setLastSyncTime,
    setIsPolling,
    setError,
    setLiveRecords,
    setStats,
    setCourses,
    setSelectedCourse,
  } = useDashboardStore();

  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const [coursesData, healthData] = await Promise.all([
          attendanceAPI.getCourses(),
          attendanceAPI.healthCheck(),
        ]);
        setCourses(coursesData);
        setSystemRunning(healthData);
        await fetchAttendanceData();
        setIsPolling(true);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch initial data');
        setSystemRunning(false);
      }
    };
    fetchInitialData();
  }, []);

  useEffect(() => {
    if (!isPolling) return;
    const pollInterval = setInterval(fetchAttendanceData, 5000);
    pollingIntervalRef.current = pollInterval;
    return () => { if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current); };
  }, [isPolling, selectedCourse]);

  const fetchAttendanceData = async () => {
    try {
      const [records, s] = await Promise.all([
        attendanceAPI.getLiveAttendance(selectedCourse || undefined),
        attendanceAPI.getAttendanceStats(selectedCourse || undefined),
      ]);
      setLiveRecords(records);
      setStats(s);
      setLastSyncTime(new Date());
      setError(null);
      try { const h = await attendanceAPI.healthCheck(); setSystemRunning(h); } catch { setSystemRunning(false); }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch attendance data');
      setSystemRunning(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchAttendanceData();
    setIsRefreshing(false);
  };

  const handleCourseFilter = (courseId: string) => {
    setSelectedCourse(courseId === 'all' ? null : courseId);
  };

  return (
    <Layout systemRunning={systemRunning} lastSyncTime={lastSyncTime}>
      <div className="space-y-7">

        {/* System Alert */}
        {(error || !systemRunning) && (
          <SystemAlert systemRunning={systemRunning} error={error} />
        )}

        {/* ── Page Header ───────────────────────────────────────────────────── */}
        <div className="flex items-end justify-between animate-fade-in-up">
          <div>
            <p
              className="text-xs font-semibold tracking-widest uppercase mb-1"
              style={{ color: 'var(--whisper)' }}
            >
              Overview
            </p>
            <h1
              className="text-3xl font-medium leading-none"
              style={{ fontFamily: 'Fraunces, serif', color: 'var(--ink)' }}
            >
              Attendance Command
            </h1>
          </div>
          <Button
            onClick={handleRefresh}
            isLoading={isRefreshing}
            variant="secondary"
            size="sm"
          >
            <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
            Refresh
          </Button>
        </div>

        {/* ── Stat Cards ────────────────────────────────────────────────────── */}
        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
            <StatCard label="Present" value={stats.total_present} color="success" icon={<Users size={18} />} />
            <StatCard label="Late" value={stats.total_late} color="warning" icon={<TrendingUp size={18} />} />
            <StatCard label="Absent" value={stats.total_absent} color="danger" icon={<Users size={18} />} />
            <StatCard label="Excused" value={stats.total_excused} color="info" icon={<Activity size={18} />} />
          </div>
        )}

        {/* ── Course Filter ─────────────────────────────────────────────────── */}
        <Card className="!p-4 animate-fade-in-up">
          <div className="flex items-center gap-3 flex-wrap">
            <span
              className="text-xs font-semibold tracking-widest uppercase flex-shrink-0"
              style={{ color: 'var(--whisper)' }}
            >
              Filter
            </span>

            <div className="flex gap-2 flex-wrap">
              {[{ id: 'all', label: 'All Courses' }, ...courses.map(c => ({ id: c.id, label: `${c.code} — ${c.name}` }))].map(({ id, label }) => {
                const active = id === 'all' ? !selectedCourse : selectedCourse === id;
                return (
                  <button
                    key={id}
                    onClick={() => handleCourseFilter(id)}
                    className="btn-press text-xs font-medium px-3 py-1.5 rounded-full transition-all duration-200"
                    style={{
                      background: active
                        ? 'linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%)'
                        : 'rgba(155,122,58,0.08)',
                      color: active ? '#fff' : 'var(--muted)',
                      border: active
                        ? '1px solid rgba(155,122,58,0.40)'
                        : '1px solid rgba(155,122,58,0.15)',
                      boxShadow: active ? '0 2px 10px rgba(155,122,58,0.25)' : 'none',
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        </Card>

        {/* ── Live Check-ins ────────────────────────────────────────────────── */}
        <Card className="animate-fade-in-up">
          {/* Card header */}
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: 'rgba(107,138,113,0.12)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Activity size={17} style={{ color: 'var(--sage)' }} />
              </div>
              <div>
                <h2
                  className="text-base font-semibold leading-none"
                  style={{ fontFamily: 'Fraunces, serif', color: 'var(--ink)' }}
                >
                  Live Check-ins
                </h2>
                <p className="text-xs mt-0.5" style={{ color: 'var(--whisper)' }}>
                  {liveRecords.length} {liveRecords.length === 1 ? 'student' : 'students'} marked today
                </p>
              </div>
            </div>

            {/* Live indicator */}
            <div
              className="flex items-center gap-2 px-3 py-1.5 rounded-full"
              style={{
                background: systemRunning ? 'rgba(107,138,113,0.10)' : 'rgba(193,123,91,0.10)',
                border: `1px solid ${systemRunning ? 'rgba(107,138,113,0.22)' : 'rgba(193,123,91,0.22)'}`,
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: systemRunning ? 'var(--sage)' : 'var(--terra)',
                  animation: systemRunning ? 'pulse-gold 2s ease infinite' : 'none',
                }}
              />
              <span className="text-[11px] font-medium" style={{ color: systemRunning ? 'var(--sage)' : 'var(--terra)' }}>
                {systemRunning ? 'Streaming' : 'Offline'}
              </span>
            </div>
          </div>

          <div className="tac-divider mb-4" />

          {/* Records */}
          <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1 stagger-children">
            {liveRecords.length === 0 ? (
              <div style={{ padding: '3rem 0', textAlign: 'center' }}>
                <div
                  style={{
                    width: '48px', height: '48px', borderRadius: '14px',
                    background: 'rgba(155,122,58,0.08)',
                    border: '1px solid rgba(155,122,58,0.15)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '0 auto 12px',
                  }}
                >
                  <Users size={20} style={{ color: 'var(--cream-400)' }} />
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--whisper)', fontWeight: 500 }}>
                  Awaiting check-ins…
                </p>
                <p style={{ fontSize: '0.72rem', color: 'var(--cream-400)', marginTop: '4px' }}>
                  Records will appear here in real time
                </p>
              </div>
            ) : (
              liveRecords.map((record, idx) => (
                <AttendanceRecordCard key={idx} record={record} />
              ))
            )}
          </div>
        </Card>

        {/* ── Info Banner ───────────────────────────────────────────────────── */}
        <div
          className="rounded-2xl px-6 py-5 animate-fade-in-up"
          style={{
            background: 'linear-gradient(135deg, rgba(155,122,58,0.06) 0%, rgba(107,138,113,0.06) 100%)',
            border: '1px solid rgba(155,122,58,0.14)',
          }}
        >
          <div className="flex items-start gap-4">
            <div
              style={{
                width: '32px', height: '32px', borderRadius: '8px', flexShrink: 0,
                background: 'rgba(155,122,58,0.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginTop: '2px',
              }}
            >
              <Activity size={15} style={{ color: 'var(--gold)' }} />
            </div>
            <div>
              <p
                className="text-sm font-semibold mb-1"
                style={{ color: 'var(--ink)', fontFamily: 'Fraunces, serif' }}
              >
                Real-time Monitoring Active
              </p>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>
                Dashboard refreshes automatically every 5 seconds. Face confidence scores and course-based filtering are available above.
              </p>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};
