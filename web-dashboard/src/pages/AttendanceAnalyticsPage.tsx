/**
 * AttendanceAnalyticsPage.tsx
 * ════════════════════════════════════════════════════════════════════════════
 * Prompt 5: Privacy-aware role-gated analytics page.
 *
 * Each role sees a completely isolated view with NO shared UI patterns that
 * could leak data. Students see personal trends. Teachers see section summaries.
 * Admins see institution-wide analytics with drill-down capability.
 *
 * Architecture: Role check on mount → conditional render of role-specific view.
 * No data is shared between views. Identity locking happens server-side;
 * client enforces at the hook level (defense-in-depth).
 */

import React, { useState } from 'react';
import { Layout } from '../components';
import { getStoredRole } from '../utils/roles';
import { getStoredAssignedSections } from '../services/firebase/auth.service';
import {
  useStudentAnalytics,
  useTeacherAnalytics,
  useAdminAnalytics,
  useAdminStudentDrillDown,
  type StudentAnalytics,
  type SectionAnalytics,
  type AdminOverview,
  type AdminStudentDrillDown,
} from '../hooks/useAttendanceAnalytics';
import {
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  BarChart3,
  RefreshCw,
  Users,
} from 'lucide-react';

// ════════════════════════════════════════════════════════════════════════════
// Student View
// ════════════════════════════════════════════════════════════════════════════

const StudentAnalyticsView: React.FC = () => {
  const [days, setDays] = useState(30);
  const { data, isLoading, error, refetch } = useStudentAnalytics({
    days,
    enabled: true,
  });

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64 gap-3 text-gray-400">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-500" />
          <span>Loading your analytics…</span>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <div className="max-w-2xl mx-auto pt-8 pb-12">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
            {error}
          </div>
        </div>
      </Layout>
    );
  }

  if (!data) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64 text-gray-400">
          No data available
        </div>
      </Layout>
    );
  }

  const overallBandColor = {
    safe: { bg: '#EAF3DE', text: '#27500A', icon: '#639922' },
    warning: { bg: '#FAEEDA', text: '#633806', icon: '#EF9F27' },
    danger: { bg: '#FCEBEB', text: '#791F1F', icon: '#E24B4A' },
  }[data.overall.band];

  const averageTrend = data.trend.length > 0
    ? Math.round(
        data.trend.reduce((sum, point) => sum + (point.rate ?? 0), 0) / data.trend.length
      )
    : 0;

  return (
    <Layout>
      <div className="max-w-6xl mx-auto space-y-6 pb-12">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 mb-2">
                Personal analytics
              </p>
              <h1 className="text-3xl font-black text-slate-900">
                Attendance Analytics
              </h1>
              <p className="mt-2 text-sm text-slate-500">
                {data.days}-day summary · Last updated {new Date(data.generated_at).toLocaleString()}
              </p>
            </div>

            <div className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">
              <BarChart3 size={12} />
              Self-only view
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <label className="text-sm font-medium text-slate-600">Period:</label>
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value))}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={60}>Last 60 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-slate-800"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:col-span-2 lg:col-span-2">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Overall attendance</p>
                <p className="mt-3 text-5xl font-black" style={{ color: overallBandColor.text }}>
                  {data.overall.percentage}%
                </p>
              </div>
              <div className="rounded-2xl p-3" style={{ background: `${overallBandColor.icon}20` }}>
                <TrendingUp size={24} style={{ color: overallBandColor.icon }} />
              </div>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Present</p>
                <p className="mt-1 text-lg font-bold text-slate-900">{data.overall.present}</p>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Late</p>
                <p className="mt-1 text-lg font-bold text-slate-900">{data.overall.late}</p>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Absent</p>
                <p className="mt-1 text-lg font-bold text-slate-900">{data.overall.absent}</p>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
              <span className="font-medium text-slate-500">Status</span>
              <span className="font-semibold text-slate-900">
                {data.overall.band === 'safe' && 'Safe (≥85%)'}
                {data.overall.band === 'warning' && 'Warning (75–85%)'}
                {data.overall.band === 'danger' && 'Danger (<75%)'}
              </span>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Current streak</p>
            <p className="mt-3 text-4xl font-black text-indigo-600">{data.streak.current_present_streak}</p>
            <p className="mt-2 text-sm text-slate-500">consecutive days present</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Longest streak</p>
            <p className="mt-3 text-4xl font-black text-violet-600">{data.streak.longest_streak}</p>
            <p className="mt-2 text-sm text-slate-500">best achievement</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Trend average</p>
            <p className="mt-3 text-4xl font-black text-emerald-600">{averageTrend}%</p>
            <p className="mt-2 text-sm text-slate-500">across the selected period</p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Attendance Trend</h2>
              <p className="text-sm text-slate-500">Daily attendance rate over the selected range.</p>
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-4 py-3 text-left font-semibold text-slate-500">Date</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">Present</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">Late</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">Absent</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-500">Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.trend.map((point, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-slate-700">{point.date}</td>
                    <td className="px-4 py-3 text-right text-slate-700">{point.present}</td>
                    <td className="px-4 py-3 text-right text-slate-700">{point.late}</td>
                    <td className="px-4 py-3 text-right text-slate-700">{point.absent}</td>
                    <td className="px-4 py-3 text-right font-semibold">
                      <span
                        className="inline-block rounded-full px-2.5 py-0.5 text-xs font-mono"
                        style={{
                          background: point.rate === null
                            ? '#F8FAFC'
                            : point.rate >= 85
                              ? '#EAF3DE'
                              : point.rate >= 75
                                ? '#FAEEDA'
                                : '#FCEBEB',
                          color: point.rate === null
                            ? '#64748b'
                            : point.rate >= 85
                              ? '#27500A'
                              : point.rate >= 75
                                ? '#633806'
                                : '#791F1F',
                        }}
                      >
                        {point.rate !== null ? `${Math.round(point.rate)}%` : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  );
};

// ════════════════════════════════════════════════════════════════════════════
// Teacher View
// ════════════════════════════════════════════════════════════════════════════

const TeacherAnalyticsView: React.FC = () => {
  const assignedSections = getStoredAssignedSections();
  const [selectedClass, setSelectedClass] = useState<string>('');
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const { data, isLoading, error, refetch } = useTeacherAnalytics(
    selectedClass
      ? {
          classId: selectedClass,
          date: selectedDate,
          enabled: true,
        }
      : {
          classId: '',
          enabled: false,
        }
  );

  if (!selectedClass) {
    return (
      <Layout>
        <div className="max-w-2xl mx-auto pt-12 pb-12">
          <h1 className="text-2xl font-bold text-gray-800 mb-6">Section Analytics</h1>
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Select a section:
            </label>
            {assignedSections.length === 0 && (
              <p className="text-sm text-gray-500">No assigned sections found for your account.</p>
            )}
            <div className="space-y-2">
              {assignedSections.map((cls) => (
                <button
                  key={cls}
                  onClick={() => setSelectedClass(cls)}
                  className="w-full text-left px-4 py-3 border border-gray-200 rounded-lg hover:bg-indigo-50 hover:border-indigo-300 transition-colors"
                >
                  {cls}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Layout>
    );
  }

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64 gap-3 text-gray-400">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-500" />
          <span>Loading section analytics…</span>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <div className="max-w-2xl mx-auto pt-8 pb-12">
          <button
            onClick={() => setSelectedClass('')}
            className="mb-4 text-indigo-600 hover:text-indigo-700 text-sm font-medium"
          >
            ← Back to sections
          </button>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
            {error}
          </div>
        </div>
      </Layout>
    );
  }

  if (!data) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64 text-gray-400">
          No data available
        </div>
      </Layout>
    );
  }

  const bandColor = {
    safe: { bg: '#EAF3DE', text: '#27500A', icon: '#639922' },
    warning: { bg: '#FAEEDA', text: '#633806', icon: '#EF9F27' },
    danger: { bg: '#FCEBEB', text: '#791F1F', icon: '#E24B4A' },
  }[data.band];

  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-6 pb-12">
        <button
          onClick={() => setSelectedClass('')}
          className="text-indigo-600 hover:text-indigo-700 text-sm font-medium mb-4"
        >
          ← Change section
        </button>

        <div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">{selectedClass} Analytics</h1>
          <p className="text-gray-500">{data.total_students} enrolled students</p>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-gray-600">Date:</label>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        {/* Overall rate card */}
        <div
          className="rounded-lg p-6 border-2"
          style={{ background: bandColor.bg, borderColor: bandColor.icon }}
        >
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-sm font-medium text-gray-500 mb-2">Attendance Rate</p>
              <p className="text-5xl font-bold" style={{ color: bandColor.text }}>
                {Math.round(data.attendance_rate)}%
              </p>
            </div>
            <div
              className="p-3 rounded-lg"
              style={{ background: bandColor.icon + '20' }}
            >
              <BarChart3 size={24} style={{ color: bandColor.icon }} />
            </div>
          </div>
          <div className="grid grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-500 mb-1">Present</p>
              <p className="text-lg font-semibold text-gray-800">{data.present}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Late</p>
              <p className="text-lg font-semibold text-gray-800">{data.late}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Absent</p>
              <p className="text-lg font-semibold text-gray-800">{data.absent}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Not Marked</p>
              <p className="text-lg font-semibold text-gray-800">{data.not_marked}</p>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

// ════════════════════════════════════════════════════════════════════════════
// Admin View
// ════════════════════════════════════════════════════════════════════════════

const AdminAnalyticsView: React.FC = () => {
  const [trendDays, setTrendDays] = useState(7);
  const [drillDownStudentId, setDrillDownStudentId] = useState<string | null>(null);
  const [drillDownStartDate, setDrillDownStartDate] = useState<string>('');
  const [drillDownEndDate, setDrillDownEndDate] = useState<string>('');

  const { data: trendData, isLoading: trendLoading, refetch: refetchTrend } =
    useAdminAnalytics({
      trendDays,
      enabled: true,
    });

  const { data: drillDownData, isLoading: drillDownLoading } = useAdminStudentDrillDown(
    drillDownStudentId,
    {
      startDate: drillDownStartDate,
      endDate: drillDownEndDate,
      enabled: !!drillDownStudentId,
    }
  );

  if (trendLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64 gap-3 text-gray-400">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-500" />
          <span>Loading institution analytics…</span>
        </div>
      </Layout>
    );
  }

  if (!trendData) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64 text-gray-400">
          No data available
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto space-y-6 pb-12">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Institution Analytics</h1>
          <p className="text-gray-500">
            {trendData.days}-day overview · {trendData.total_students} total students · Last
            updated {new Date(trendData.generated_at).toLocaleString()}
          </p>
        </div>

        {/* Days filter */}
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-gray-600">Period:</label>
          <select
            value={trendDays}
            onChange={(e) => setTrendDays(parseInt(e.target.value))}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value={2}>Last 2 days</option>
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button
            onClick={() => refetchTrend()}
            className="flex items-center gap-2 px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="text-xs text-gray-500 font-medium uppercase">Total Students</p>
                <p className="text-2xl font-bold text-gray-800 mt-1">{trendData.total_students}</p>
              </div>
              <Users size={20} className="text-indigo-500" />
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="text-xs text-gray-500 font-medium uppercase">Avg Attendance</p>
                <p className="text-2xl font-bold text-gray-800 mt-1">
                  {trendData.trend.length > 0
                    ? Math.round(
                        trendData.trend.reduce((sum, t) => sum + t.rate, 0) /
                          trendData.trend.length
                      )
                    : 0}
                  %
                </p>
              </div>
              <TrendingUp size={20} className="text-green-500" />
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="text-xs text-gray-500 font-medium uppercase">Period</p>
                <p className="text-2xl font-bold text-gray-800 mt-1">{trendData.days} days</p>
              </div>
              <Clock size={20} className="text-orange-500" />
            </div>
          </div>
        </div>

        {/* Trend table */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Date</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Present</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Late</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Absent</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {trendData.trend.map((point, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-gray-700">{point.date}</td>
                  <td className="px-4 py-3 text-right text-gray-700">{point.present}</td>
                  <td className="px-4 py-3 text-right text-gray-700">{point.late}</td>
                  <td className="px-4 py-3 text-right text-gray-700">{point.absent}</td>
                  <td className="px-4 py-3 text-right font-semibold">
                    <span
                      className="inline-block px-2.5 py-0.5 rounded-full text-xs font-mono"
                      style={{
                        background:
                          point.rate >= 80
                            ? '#EAF3DE'
                            : point.rate >= 70
                              ? '#FAEEDA'
                              : '#FCEBEB',
                        color:
                          point.rate >= 80
                            ? '#27500A'
                            : point.rate >= 70
                              ? '#633806'
                              : '#791F1F',
                      }}
                    >
                      {Math.round(point.rate)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Student drill-down section */}
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Student Drill-Down</h2>
          <div className="flex items-end gap-3 mb-6">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-600 mb-2">
                Student ID:
              </label>
              <input
                type="text"
                placeholder="Enter student ID"
                value={drillDownStudentId || ''}
                onChange={(e) => setDrillDownStudentId(e.target.value || null)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-2">
                Start Date:
              </label>
              <input
                type="date"
                value={drillDownStartDate}
                onChange={(e) => setDrillDownStartDate(e.target.value)}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-2">
                End Date:
              </label>
              <input
                type="date"
                value={drillDownEndDate}
                onChange={(e) => setDrillDownEndDate(e.target.value)}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {drillDownLoading && (
            <div className="flex items-center gap-3 text-gray-500">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-indigo-500" />
              Loading student details…
            </div>
          )}

          {drillDownData && (
            <div className="space-y-4">
              <div className="border-t pt-4">
                <h3 className="font-semibold text-gray-800 mb-3">{drillDownData.student_name}</h3>
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Overall Rate</p>
                    <p className="text-xl font-bold text-gray-800">
                      {drillDownData.overall.percentage}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Present</p>
                    <p className="text-xl font-bold text-gray-800">
                      {drillDownData.overall.present}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Absent</p>
                    <p className="text-xl font-bold text-gray-800">
                      {drillDownData.overall.absent}
                    </p>
                  </div>
                </div>
                {drillDownData.course_breakdown.length > 0 && (
                  <div>
                    <p className="text-sm font-semibold text-gray-700 mb-2">By Course:</p>
                    <div className="space-y-2">
                      {drillDownData.course_breakdown.map((course) => (
                        <div key={course.course_id} className="flex justify-between text-sm">
                          <span>{course.course_id}</span>
                          <span className="font-mono font-semibold">{course.rate}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

// ════════════════════════════════════════════════════════════════════════════
// Main Router
// ════════════════════════════════════════════════════════════════════════════

export const AttendanceAnalyticsPage: React.FC = () => {
  const role = getStoredRole();

  if (!role) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64 text-gray-500">
          Not authenticated
        </div>
      </Layout>
    );
  }

  switch (role) {
    case 'student':
      return <StudentAnalyticsView />;
    case 'teacher':
      return <TeacherAnalyticsView />;
    case 'admin':
      return <AdminAnalyticsView />;
    default:
      return (
        <Layout>
          <div className="flex items-center justify-center h-64 text-gray-500">
            Unknown role
          </div>
        </Layout>
      );
  }
};

export default AttendanceAnalyticsPage;
