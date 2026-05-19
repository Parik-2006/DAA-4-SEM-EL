import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Layout } from '../components/Layout';
import { PeriodStatsCard, AuditTrailList } from '../components/StatsCard';
import { useBackendHealthMonitor } from '../hooks/useBackendHealth';
import { useContiniousAttendancePolling } from '../hooks/useAttendanceRefresh';
import {
  CSE4C_META,
  useAttendanceByPeriod,
  useClassesAndPeriods,
  useWeeklyAudit,
} from '../hooks/useAttendanceHooks';
import type { PeriodAnalytics, PeriodAuditEntry } from '../hooks/useAttendanceHooks';
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  WifiOff,
} from 'lucide-react';

const PERIOD_COLORS = ['#6366F1', '#14B8A6', '#F59E0B', '#EF4444', '#8B5CF6', '#22C55E'];

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function getMondayOf(date: Date): Date {
  const copy = new Date(date);
  const day = copy.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + diff);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function get5DayWindow(pivot: Date): Date[] {
  const monday = getMondayOf(pivot);
  return Array.from({ length: 5 }, (_, index) => {
    const date = new Date(monday);
    date.setDate(monday.getDate() + index);
    return date;
  });
}

function dayName(date: Date): string {
  return date.toLocaleDateString('en-US', { weekday: 'long' });
}

function mapStatus(status: string): PeriodAuditEntry['status'] {
  if (status === 'present' || status === 'late' || status === 'absent') return status;
  return 'not_marked';
}

export const DashboardPage: React.FC = () => {
  const { isHealthy, lastCheck } = useBackendHealthMonitor(15_000);

  const [pivot, setPivot] = useState<Date>(() => new Date());
  const [selectedDate, setSelectedDate] = useState<Date>(() => new Date());
  const [selectedClassId, setSelectedClassId] = useState<string>(CSE4C_META.class_id);
  const [selectedPeriodId, setSelectedPeriodId] = useState<string>('');

  const weekDays = useMemo(() => get5DayWindow(pivot), [pivot]);
  const selectedDateKey = isoDate(selectedDate);
  const selectedDayName = dayName(selectedDate);
  const weekStart = isoDate(weekDays[0]);
  const weekEnd = isoDate(weekDays[4]);

  const { classes, periods: classPeriods, classesLoading, periodsLoading, loadPeriods } = useClassesAndPeriods();

  useEffect(() => {
    if (selectedClassId) {
      loadPeriods(selectedClassId, selectedDateKey);
    }
  }, [selectedClassId, selectedDateKey, loadPeriods]);

  const {
    data: weeklyAudit,
    loading: weeklyLoading,
    error: weeklyError,
    refetch: refetchWeekly,
  } = useWeeklyAudit({
    classId: selectedClassId,
    startDate: weekStart,
    endDate: weekEnd,
    enabled: !!selectedClassId,
  });

  const {
    slots: dailySlots,
    loading: dailyLoading,
    refetch: refetchDaily,
  } = useAttendanceByPeriod({
    day: selectedDayName,
    date: selectedDateKey,
    classId: selectedClassId,
    enabled: !!selectedClassId,
  });

  const classOptions = classes.length > 0
    ? classes
    : [{ class_id: CSE4C_META.class_id, class_name: CSE4C_META.display, section: 'C' }];

  const buildFallbackAnalytics = useCallback(
    (slot: (typeof dailySlots)[number]): PeriodAnalytics => {
      return {
        period_id: slot.period.period_id,
        course_code: slot.period.course_code,
        course_name: slot.period.course_name,
        date: selectedDateKey,
        start_time: slot.period.start_time,
        end_time: slot.period.end_time,
        total_enrolled: slot.total_students,
        present: slot.present,
        late: slot.late,
        absent: slot.absent,
        not_marked: slot.pending,
        attendance_pct: slot.total_students > 0 ? ((slot.present + slot.late) / slot.total_students) * 100 : 0,
        audit_entries: slot.records.map((record) => {
          const data = record as unknown as Record<string, unknown>;
          return {
            student_id: String(data.student_id ?? ''),
            student_name: String(data.student_name ?? data.name ?? 'Unknown'),
            roll_no: String(data.roll_no ?? data.student_id ?? ''),
            status: mapStatus(String(data.status ?? 'not_marked')),
            scanned_at: String(data.timestamp ?? data.marked_at ?? ''),
            marked_by_name: data.marked_by_name ? String(data.marked_by_name) : undefined,
            confidence: data.confidence != null ? Number(data.confidence) : undefined,
            camera_id: data.camera_id ? String(data.camera_id) : undefined,
          };
        }),
      };
    },
    [selectedDateKey]
  );

  const currentDayWeekly = weeklyAudit?.days.find((day) => day.date === selectedDateKey) ?? null;

  const availablePeriods = useMemo<PeriodAnalytics[]>(() => {
    if (currentDayWeekly?.periods?.length) return currentDayWeekly.periods;
    if (dailySlots.length) return dailySlots.map(buildFallbackAnalytics);
    if (classPeriods.length) {
        return classPeriods.map((period) => ({
          period_id: period.period_id,
          course_code: period.course_code,
          course_name: period.course_name,
          date: selectedDateKey,
          start_time: period.start_time,
          end_time: period.end_time,
          total_enrolled: 0,
          present: 0,
          late: 0,
          absent: 0,
          not_marked: 0,
          attendance_pct: 0,
          audit_entries: [],
        }));
    }
    return [];
  }, [currentDayWeekly, dailySlots, classPeriods, buildFallbackAnalytics, selectedDateKey]);

  useEffect(() => {
    if (!availablePeriods.length) {
      setSelectedPeriodId('');
      return;
    }
    const matched = availablePeriods.find((period) => period.period_id === selectedPeriodId);
    if (!matched) {
      setSelectedPeriodId(availablePeriods[0].period_id);
    }
  }, [availablePeriods, selectedPeriodId]);

  const selectedPeriod = useMemo(() => {
    if (!availablePeriods.length) return null;
    return availablePeriods.find((period) => period.period_id === selectedPeriodId) ?? availablePeriods[0];
  }, [availablePeriods, selectedPeriodId]);

  const selectedPeriodIndex = Math.max(0, availablePeriods.findIndex((period) => period.period_id === selectedPeriod?.period_id));
  const selectedPeriodColor = PERIOD_COLORS[selectedPeriodIndex % PERIOD_COLORS.length];

  const weekSummaries = useMemo(() => weekDays.map((date) => {
    const dateKey = isoDate(date);
    const day = weeklyAudit?.days.find((item) => item.date === dateKey);
    const total = day?.day_total.total ?? 0;
    const present = day?.day_total.present ?? 0;
    const late = day?.day_total.late ?? 0;
    const absent = day?.day_total.absent ?? 0;
    const notMarked = day?.day_total.not_marked ?? 0;

    return {
      date,
      dateKey,
      total,
      present,
      late,
      absent,
      notMarked,
      periodCount: day?.periods.length ?? 0,
      percent: total > 0 ? ((present + late) / total) * 100 : 0,
    };
  }), [weekDays, weeklyAudit]);

  const selectedEntries = selectedPeriod?.audit_entries ?? [];
  const scannedEntries = [...selectedEntries]
    .filter((entry) => !!entry.scanned_at)
    .sort((a, b) => String(b.scanned_at ?? '').localeCompare(String(a.scanned_at ?? '')));
  const missedEntries = selectedEntries.filter((entry) => entry.status === 'not_marked');

  const refreshAll = useCallback(() => {
    refetchWeekly();
    refetchDaily();
    if (selectedClassId) {
      loadPeriods(selectedClassId, selectedDateKey);
    }
  }, [loadPeriods, refetchDaily, refetchWeekly, selectedClassId, selectedDateKey]);

  // Auto-refresh data every 10s while dashboard is visible
  const { lastRefreshAt } = useContiniousAttendancePolling(
    true, // Always enabled while on dashboard
    refreshAll,
    10_000 // Refresh every 10 seconds
  );

  useEffect(() => {
    const handler = () => refreshAll();
    window.addEventListener('attendance:marked', handler);
    return () => window.removeEventListener('attendance:marked', handler);
  }, [refreshAll]);

  const selectedClass = classOptions.find((item) => item.class_id === selectedClassId) ?? classOptions[0];
  const totalPeriodsInWindow = weekSummaries.reduce((sum, day) => sum + day.periodCount, 0);

  return (
    <Layout>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <p style={{ fontSize: '0.66rem', fontWeight: 700, color: '#94a3b8', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4 }}>
              Attendance Audit Dashboard
            </p>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 900, color: '#1e293b', marginBottom: 4 }}>
              Period-aware weekly view
            </h1>
            <p style={{ fontSize: '0.75rem', color: '#64748b' }}>
              {selectedClass?.class_name ?? CSE4C_META.display} · {weekStart} to {weekEnd} · {totalPeriodsInWindow} periods in scope
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <span style={{ fontSize: '0.68rem', color: '#B0956E', fontFamily: 'DM Mono, monospace' }}>
              {lastCheck ? lastCheck.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : 'checking…'}
            </span>
            <button
              onClick={refreshAll}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, background: '#fff', border: '1.5px solid #e2e8f0', cursor: 'pointer', fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}
            >
              <RefreshCw size={13} /> Refresh audit
            </button>
          </div>
        </div>

        {!isHealthy && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 12, background: 'rgba(193,123,91,0.08)', border: '1px solid rgba(193,123,91,0.25)', fontSize: '0.78rem', color: '#C17B5B' }}>
            <WifiOff size={13} /> Backend offline or warming up. Showing cached audit data.
          </div>
        )}

        {weeklyError && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 12, background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.25)', fontSize: '0.78rem', color: '#92400E' }}>
            <AlertTriangle size={13} /> {weeklyError}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
          <div style={{ borderRadius: 18, padding: '16px 18px', background: '#F0FDF4', border: '1px solid #BBF7D0' }}>
            <p style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#16A34A' }}>Present</p>
            <p style={{ fontSize: '1.9rem', fontWeight: 900, color: '#16A34A', lineHeight: 1, marginTop: 6 }}>{selectedPeriod?.present ?? 0}</p>
          </div>
          <div style={{ borderRadius: 18, padding: '16px 18px', background: '#FEF2F2', border: '1px solid #FECACA' }}>
            <p style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#DC2626' }}>Absent</p>
            <p style={{ fontSize: '1.9rem', fontWeight: 900, color: '#DC2626', lineHeight: 1, marginTop: 6 }}>{selectedPeriod?.absent ?? 0}</p>
          </div>
          <div style={{ borderRadius: 18, padding: '16px 18px', background: '#FFFBEB', border: '1px solid #FDE68A' }}>
            <p style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#B45309' }}>Late</p>
            <p style={{ fontSize: '1.9rem', fontWeight: 900, color: '#B45309', lineHeight: 1, marginTop: 6 }}>{selectedPeriod?.late ?? 0}</p>
          </div>
          <div style={{ borderRadius: 18, padding: '16px 18px', background: '#F8FAFC', border: '1px solid #E2E8F0' }}>
            <p style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#64748B' }}>Unmarked</p>
            <p style={{ fontSize: '1.9rem', fontWeight: 900, color: '#64748B', lineHeight: 1, marginTop: 6 }}>{selectedPeriod?.not_marked ?? 0}</p>
          </div>
        </div>

        <div style={{ borderRadius: 18, overflow: 'hidden', background: 'rgba(254,252,248,0.72)', backdropFilter: 'blur(16px)', border: '1px solid rgba(190,160,118,0.28)', boxShadow: '0 4px 24px rgba(80,50,20,0.06)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 18px', borderBottom: '1px solid rgba(190,160,118,0.18)' }}>
            <button
              onClick={() => setPivot((current) => { const next = new Date(current); next.setDate(next.getDate() - 7); return next; })}
              style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '5px 8px', borderRadius: 8, color: '#7A6545', display: 'flex', alignItems: 'center' }}
            >
              <ChevronLeft size={15} />
            </button>
            <div style={{ textAlign: 'center' }}>
              <p style={{ fontSize: '0.78rem', fontWeight: 600, color: '#2A1F12' }}>
                {weekDays[0].toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                {' – '}
                {weekDays[4].toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
              </p>
              <p style={{ fontSize: '0.62rem', color: '#B0956E', marginTop: 1 }}>
                Select a day and period to inspect scans, overrides, and misses
              </p>
            </div>
            <button
              onClick={() => setPivot((current) => { const next = new Date(current); next.setDate(next.getDate() + 7); return next; })}
              style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '5px 8px', borderRadius: 8, color: '#7A6545', display: 'flex', alignItems: 'center' }}
            >
              <ChevronRight size={15} />
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)' }}>
            {weekSummaries.map((day, index) => (
              <button
                key={day.dateKey}
                onClick={() => setSelectedDate(day.date)}
                style={{
                  padding: '14px 8px', textAlign: 'center', border: 'none',
                  borderRight: index === 4 ? 'none' : '1px solid rgba(190,160,118,0.20)',
                  borderBottom: day.dateKey === selectedDateKey ? '2.5px solid #9B7A3A' : '2.5px solid transparent',
                  background: day.dateKey === selectedDateKey ? 'rgba(155,122,58,0.09)' : day.dateKey === isoDate(new Date()) ? 'rgba(155,122,58,0.04)' : 'transparent',
                  cursor: 'pointer', transition: 'background 0.15s',
                }}
              >
                <p style={{ fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: day.dateKey === isoDate(new Date()) ? '#9B7A3A' : '#B0956E', marginBottom: 3 }}>
                  {day.date.toLocaleDateString('en-US', { weekday: 'short' })}
                </p>
                <p style={{ fontSize: '1.15rem', fontWeight: 900, color: day.dateKey === selectedDateKey ? '#9B7A3A' : '#2A1F12', marginBottom: 8, fontFamily: 'Fraunces, Georgia, serif' }}>
                  {day.date.getDate()}
                </p>
                <div style={{ width: 28, height: 4, borderRadius: 99, background: '#E8D5BE', margin: '0 auto 4px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${Math.round(day.percent)}%`, background: day.percent >= 75 ? '#22C55E' : day.percent >= 50 ? '#F59E0B' : '#EF4444', borderRadius: 99 }} />
                </div>
                <p style={{ fontSize: '0.56rem', fontFamily: 'DM Mono, monospace', color: '#B0956E' }}>
                  {Math.round(day.percent)}% · {day.periodCount}P
                </p>
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 20, alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ borderRadius: 18, border: '1px solid #e2e8f0', background: '#fff', padding: 16 }}>
              <label htmlFor="dashboard-class-filter" style={{ fontSize: '0.66rem', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8, display: 'block' }}>
                Class
              </label>
              <select
                id="dashboard-class-filter"
                name="classId"
                value={selectedClassId}
                onChange={(event) => setSelectedClassId(event.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: '0.82rem' }}
                disabled={classesLoading}
              >
                {classOptions.map((item) => (
                  <option key={item.class_id} value={item.class_id}>
                    {item.class_name ?? item.class_id}{item.section ? ` · Sec ${item.section}` : ''}
                  </option>
                ))}
              </select>
              <div style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Audit source:</span>
                <span style={{
                  fontSize: '0.65rem', fontWeight: 800, padding: '3px 8px', borderRadius: 999,
                  background: weeklyAudit?.days?.length ? '#ECFDF5' : '#F8FAFC',
                  color: weeklyAudit?.days?.length ? '#16A34A' : '#64748b',
                  border: `1px solid ${weeklyAudit?.days?.length ? '#10B98133' : '#e2e8f0'}`,
                }}>
                  {weeklyAudit?.days?.length ? 'Weekly audit' : 'Fallback view'}
                </span>
              </div>
            </div>

            <div style={{ borderRadius: 18, border: '1px solid #e2e8f0', background: '#fff', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <label htmlFor="dashboard-period-date" style={{ fontSize: '0.66rem', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                {selectedDayName} periods
              </label>
              <input
                id="dashboard-period-date"
                name="selectedDate"
                type="date"
                value={selectedDateKey}
                onChange={(event) => setSelectedDate(new Date(`${event.target.value}T00:00:00`))}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: '0.82rem' }}
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 440, overflowY: 'auto', paddingRight: 4 }}>
                {availablePeriods.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '0.82rem' }}>
                    {weeklyLoading || dailyLoading || periodsLoading ? 'Loading period audit…' : 'No period data available'}
                  </div>
                ) : (
                  availablePeriods.map((period, index) => {
                    const active = period.period_id === selectedPeriod?.period_id;
                    const color = PERIOD_COLORS[index % PERIOD_COLORS.length];
                    return (
                      <button
                        key={period.period_id}
                        onClick={() => setSelectedPeriodId(period.period_id)}
                        style={{
                          width: '100%', padding: '14px 16px', borderRadius: 16, textAlign: 'left',
                          cursor: 'pointer', transition: 'all .2s ease',
                          border: `2px solid ${active ? color : '#e2e8f0'}`,
                          background: active ? `${color}12` : '#fff',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                          <div>
                            <p style={{ fontSize: '0.68rem', fontWeight: 800, color, letterSpacing: '0.08em' }}>{period.course_code}</p>
                            <p style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1e293b', marginTop: 4 }}>{period.course_name}</p>
                            {period.faculty_name && <p style={{ fontSize: '0.68rem', color: '#64748b', marginTop: 2 }}>{period.faculty_name}</p>}
                            <p style={{ fontSize: '0.66rem', color: '#94a3b8', marginTop: 6, fontFamily: 'DM Mono, monospace' }}>{period.start_time}–{period.end_time}</p>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <p style={{ fontSize: '1.2rem', fontWeight: 900, color }}>{Math.round(period.attendance_pct)}%</p>
                            <p style={{ fontSize: '0.62rem', color: '#94a3b8' }}>{period.present + period.late}/{period.total_enrolled}</p>
                          </div>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {selectedPeriod ? (
              <>
                <PeriodStatsCard analytics={selectedPeriod} periodColor={selectedPeriodColor} />

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div style={{ borderRadius: 18, border: '1px solid #E2E8F0', background: '#fff', padding: 18 }}>
                    <p style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>Who scanned</p>
                    {scannedEntries.length === 0 ? (
                      <p style={{ fontSize: '0.82rem', color: '#94a3b8' }}>No scans recorded in this period yet.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 260, overflowY: 'auto', paddingRight: 4 }}>
                        {scannedEntries.map((entry) => (
                          <div key={`${entry.student_id}-${entry.scanned_at ?? 'scan'}`} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '10px 12px', borderRadius: 12, background: '#F8FAFC', border: '1px solid #E2E8F0' }}>
                            <div>
                              <p style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1e293b' }}>{entry.student_name}</p>
                              <p style={{ fontSize: '0.68rem', color: '#64748b' }}>{entry.roll_no ?? entry.student_id}</p>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                              <p style={{ fontSize: '0.72rem', fontFamily: 'DM Mono, monospace', color: '#475569' }}>
                                {entry.scanned_at ? new Date(entry.scanned_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '—'}
                              </p>
                              <p style={{ fontSize: '0.62rem', color: '#94a3b8' }}>{entry.marked_by_name ?? 'camera'}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div style={{ borderRadius: 18, border: '1px solid #E2E8F0', background: '#fff', padding: 18 }}>
                    <p style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>Missed students</p>
                    {missedEntries.length === 0 ? (
                      <p style={{ fontSize: '0.82rem', color: '#94a3b8' }}>Everyone in this period has been marked.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 260, overflowY: 'auto', paddingRight: 4 }}>
                        {missedEntries.map((entry) => (
                          <div key={`${entry.student_id}-missed`} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '10px 12px', borderRadius: 12, background: '#FEF2F2', border: '1px solid #FECACA' }}>
                            <div>
                              <p style={{ fontSize: '0.82rem', fontWeight: 700, color: '#991B1B' }}>{entry.student_name}</p>
                              <p style={{ fontSize: '0.68rem', color: '#B91C1C' }}>{entry.roll_no ?? entry.student_id}</p>
                            </div>
                            <span style={{ fontSize: '0.65rem', fontWeight: 700, color: '#B91C1C', alignSelf: 'center' }}>not marked</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <AuditTrailList entries={selectedEntries} periodColor={selectedPeriodColor} />
              </>
            ) : (
              <div style={{ borderRadius: 18, border: '1px dashed #E2E8F0', background: '#fff', padding: 32, textAlign: 'center' }}>
                <p style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', marginBottom: 6 }}>No period selected</p>
                <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Select a class, choose a day, then open a period to inspect scans and misses.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default DashboardPage;
