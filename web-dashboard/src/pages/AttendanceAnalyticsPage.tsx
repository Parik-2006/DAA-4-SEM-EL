/**
 * AttendanceAnalyticsPage.tsx
 * ----------------------------
 * Real-time attendance analytics for CSE 4C Section C.
 * Drop into:  web-dashboard/src/pages/AttendanceAnalyticsPage.tsx
 *
 * Dependencies already in package.json:
 *   recharts, lucide-react, axios, react-router-dom
 *
 * New file needed:
 *   web-dashboard/src/config/timetable.ts  (provided separately)
 */

import React, {
  useState,
  useMemo,
} from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RTooltip,
  CartesianGrid,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  RefreshCw,
  Search,
  Download,
  Clock,
  Users,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Activity,
  TrendingUp,
  Beaker,
  Mail,
} from 'lucide-react';
import { Layout } from '../components';
import {
  PERIODS,
  SECTION_INFO,
  getPastSessionDates,
  getPeriodsByDay,
  getPeriodById,
  type Period,
} from '../config/timetable';
import { useAttendanceAnalytics } from '../hooks/useAttendanceAnalytics';

// ─── Types ────────────────────────────────────────────────────────────────────

type AttendanceStatus = 'present' | 'absent' | 'late';

interface ActivityEntry {
  rollNo: string;
  studentName: string;
  status: AttendanceStatus;
  method: string;
  timestamp: Date;
}

interface PeriodState {
  present: number;
  absent: number;
  late: number;
  notMarked: number;
  marked: number;
  total: number;
  shuffledStudents: string[];
  activity: ActivityEntry[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const MARK_METHODS = ['Face scan', 'QR code', 'Manual', 'RFID', 'App check-in'];

const STATUS_STYLE: Record<AttendanceStatus, { bg: string; text: string }> = {
  present:  { bg: '#EAF3DE', text: '#27500A' },
  absent:   { bg: '#FCEBEB', text: '#791F1F' },
  late:     { bg: '#FAEEDA', text: '#633806' },
};

const DONUT_COLORS = ['#639922', '#EF9F27', '#E24B4A', '#B4B2A9'];

const BAR_COLOR = (v: number) =>
  v >= 80 ? '#C0DD97' : v >= 70 ? '#FAC775' : '#F7C1C1';
const BAR_BORDER = (v: number) =>
  v >= 80 ? '#3B6D11' : v >= 70 ? '#854F0B' : '#A32D2D';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pct(a: number, b: number): number {
  return b > 0 ? Math.round((a / b) * 100) : 0;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface KPICardProps {
  label: string;
  value: string | number;
  sub: string;
  accentColor: string;
  textColor: string;
  icon: React.ReactNode;
}

const KPICard: React.FC<KPICardProps> = ({
  label, value, sub, accentColor, textColor, icon,
}) => (
  <div
    className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm relative overflow-hidden"
    style={{ borderLeft: `3px solid ${accentColor}` }}
  >
    <div className="flex items-start justify-between mb-2">
      <p className="text-xs text-gray-400 uppercase tracking-wider font-medium">{label}</p>
      <span className="text-gray-300">{icon}</span>
    </div>
    <p
      className="text-3xl font-medium leading-none tabular-nums"
      style={{ color: textColor, fontFamily: "'DM Mono', 'Courier New', monospace" }}
    >
      {value}
    </p>
    <p className="text-xs text-gray-400 mt-2">{sub}</p>
  </div>
);

interface CustomBarTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
  periodCode: string;
}

const CustomBarTooltip: React.FC<CustomBarTooltipProps> = ({
  active, payload, label, periodCode,
}) => {
  if (!active || !payload?.length) return null;
  const val = payload[0].value;
  return (
    <div className="rounded-lg px-3 py-2 text-xs shadow-lg" style={{ background: '#1e293b' }}>
      <p className="text-gray-400 mb-1">{label}</p>
      <p className="font-bold font-mono" style={{ color: BAR_BORDER(val) }}>
        {periodCode} · {val}%
      </p>
    </div>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────────────

export const AttendanceAnalyticsPage: React.FC = () => {
  // ── State ──────────────────────────────────────────────────────────────────

  const [selectedId, setSelectedId] = useState<string>('fri_lab');
  const [statusFilter, setStatusFilter] = useState('');
  const [methodFilter, setMethodFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // ── Derived ────────────────────────────────────────────────────────────────

  const period = useMemo(() => getPeriodById(selectedId), [selectedId]);
  const {
    state,
    trendData,
    donutData,
    attendancePct,
    markingPct,
    lastUpdated,
    isLoading,
    error,
    refetch,
  } = useAttendanceAnalytics({
    periodId: selectedId,
    pollMs: 6000,
  });

  const filteredActivity = useMemo(() => {
    if (!state) return [];
    return state.activity.filter((e) => {
      if (statusFilter && e.status !== statusFilter) return false;
      if (methodFilter && e.method !== methodFilter) return false;
      if (searchQuery && !e.studentName.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });
  }, [state, statusFilter, methodFilter, searchQuery]);

  const periodsByDay = useMemo(() => getPeriodsByDay(), []);

  // ── Period switch ──────────────────────────────────────────────────────────

  const handlePeriodChange = (id: string) => {
    setSelectedId(id);
    setStatusFilter('');
    setMethodFilter('');
    setSearchQuery('');
  };

  // ── CSV export ─────────────────────────────────────────────────────────────

  const exportCSV = () => {
    if (!state) return;
    const rows = [
      ['Roll No', 'Student Name', 'Status', 'Method', 'Time'],
      ...state.activity.map(e => [
        e.rollNo,
        e.studentName,
        e.status,
        e.method,
        e.timestamp.toLocaleTimeString(),
      ]),
    ];
    const csv  = rows.map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `attendance_${period.code}_${period.day}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  // ── Loading guard ──────────────────────────────────────────────────────────

  if (isLoading || !state) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64 gap-3 text-gray-400">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-500" />
          <span className="text-sm">Initialising dashboard…</span>
        </div>
      </Layout>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────────

  return (
    <Layout>
      <div className="space-y-4 pb-8">

        {/* ── Page header ──────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between flex-wrap gap-3 pt-1">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-widest mb-1 font-medium">
              {SECTION_INFO.college} · {SECTION_INFO.ugLevel} {SECTION_INFO.department} ·{' '}
              {SECTION_INFO.section} · {SECTION_INFO.semType} {SECTION_INFO.batch}
            </p>
            <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-3">
              Attendance Analytics
              <span className="text-sm font-normal text-gray-400">
                Sem {SECTION_INFO.semester} · Sec {SECTION_INFO.sectionLabel} · {SECTION_INFO.classroom}
              </span>
            </h1>
          </div>

          {/* Live badge + timestamp */}
          <div className="flex items-center gap-3 mt-1">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-green-50 border border-green-200 rounded-full">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
              </span>
              <span className="text-xs font-semibold text-green-700">Live</span>
            </div>
            <code className="text-xs text-gray-400 font-mono">
              {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </code>
          </div>
        </div>

        {/* ── Period selector ───────────────────────────────────────────────── */}
        <div className="flex items-center gap-3 flex-wrap">
          <select
            value={selectedId}
            onChange={e => handlePeriodChange(e.target.value)}
            className="flex-1 min-w-[260px] px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
          >
            {Object.entries(periodsByDay).map(([day, periods]) => (
              <optgroup key={day} label={day}>
                {periods.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.day} · {p.time} · {p.subject}{p.isLab ? ' (Lab)' : ''} · {p.code}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>

          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg
                       text-sm font-medium hover:bg-indigo-700 active:scale-95 transition-all"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        {/* ── Course info bar ───────────────────────────────────────────────── */}
        <div className="flex items-center gap-0 bg-gray-50 border border-gray-100 rounded-xl overflow-hidden divide-x divide-gray-100 flex-wrap">
          {[
            {
              icon: <Activity size={13} className="text-indigo-400" />,
              label: 'Course',
              value: period.course,
            },
            {
              icon: <Users size={13} className="text-indigo-400" />,
              label: 'Faculty',
              value: period.faculty,
            },
            {
              icon: <Mail size={13} className="text-indigo-400" />,
              label: 'Email',
              value: period.email,
              mono: true,
            },
            {
              icon: <Clock size={13} className="text-indigo-400" />,
              label: 'Time Slot',
              value: period.time,
              mono: true,
            },
          ].map(item => (
            <div key={item.label} className="px-4 py-3 flex-1 min-w-[160px]">
              <div className="flex items-center gap-1.5 mb-1">
                {item.icon}
                <span className="text-xs text-gray-400 uppercase tracking-wider font-medium">
                  {item.label}
                </span>
              </div>
              <p
                className={`text-sm font-semibold text-gray-800 truncate ${item.mono ? 'font-mono' : ''}`}
              >
                {item.value}
              </p>
            </div>
          ))}

          {/* Course code + lab badge */}
          <div className="px-4 py-3 flex items-center gap-2 flex-shrink-0">
            <code className="text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-lg
                             font-mono font-semibold text-indigo-600 shadow-sm">
              {period.code}
            </code>
            {period.isLab && (
              <span className="text-xs px-2 py-1.5 bg-purple-50 border border-purple-200
                               text-purple-700 rounded-lg font-semibold flex items-center gap-1">
                <Beaker size={11} /> LAB
              </span>
            )}
          </div>
        </div>

        {/* ── Marking-progress bar ──────────────────────────────────────────── */}
        <div>
          <div className="flex justify-between items-center text-xs mb-1.5">
            <span className="text-gray-500 font-medium">
              {state.marked} of {state.total} students marked
            </span>
            <code
              className="font-mono font-semibold"
              style={{
                color: markingPct >= 80 ? '#3B6D11' : markingPct >= 55 ? '#854F0B' : '#A32D2D',
              }}
            >
              {markingPct}%
            </code>
          </div>
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden border border-gray-200">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${markingPct}%`,
                background:
                  markingPct >= 80 ? '#639922' : markingPct >= 55 ? '#EF9F27' : '#E24B4A',
              }}
            />
          </div>
        </div>

        {/* ── KPI Cards ─────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <KPICard
            label="Present"
            value={state.present}
            sub={`${pct(state.present, state.total)}% of class`}
            accentColor="#639922"
            textColor="#3B6D11"
            icon={<CheckCircle size={15} />}
          />
          <KPICard
            label="Absent"
            value={state.absent}
            sub={`${pct(state.absent, state.total)}% of class`}
            accentColor="#E24B4A"
            textColor="#A32D2D"
            icon={<XCircle size={15} />}
          />
          <KPICard
            label="Late"
            value={state.late}
            sub={`${pct(state.late, state.total)}% of class`}
            accentColor="#EF9F27"
            textColor="#854F0B"
            icon={<Clock size={15} />}
          />
          <KPICard
            label="Not Marked"
            value={state.notMarked}
            sub={`${state.notMarked} pending`}
            accentColor="#B4B2A9"
            textColor="#888780"
            icon={<AlertTriangle size={15} />}
          />
          <KPICard
            label="Attendance"
            value={`${attendancePct}%`}
            sub={`of ${state.total} enrolled`}
            accentColor="#1D9E75"
            textColor={attendancePct >= 80 ? '#0F6E56' : attendancePct >= 70 ? '#854F0B' : '#A32D2D'}
            icon={<TrendingUp size={15} />}
          />
        </div>

        {/* ── Charts ────────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

          {/* Trend bar chart */}
          <div className="lg:col-span-3 bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="flex items-start justify-between mb-1">
              <div>
                <p className="text-sm font-semibold text-gray-700">7-session attendance trend</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  Past {period.dayFull}s · {period.code} · {period.subject}
                </p>
              </div>
              <div className="flex gap-3 text-xs text-gray-400 mt-0.5 flex-wrap justify-end">
                {([['#C0DD97', '≥80%'], ['#FAC775', '70–80%'], ['#F7C1C1', '<70%']] as [string, string][]).map(([bg, lb]) => (
                  <span key={lb} className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: bg }} />
                    {lb}
                  </span>
                ))}
              </div>
            </div>

            <ResponsiveContainer width="100%" height={190}>
              <BarChart data={trendData} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(136,135,128,.1)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: '#888780' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  domain={[50, 100]}
                  tick={{ fontSize: 10, fill: '#888780' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={v => `${v}%`}
                />
                <RTooltip
                  content={<CustomBarTooltip periodCode={period.code} />}
                  cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                />
                <Bar dataKey="pct" radius={[3, 3, 0, 0]} maxBarSize={44}>
                  {trendData.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={BAR_COLOR(entry.pct)}
                      stroke={BAR_BORDER(entry.pct)}
                      strokeWidth={1}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Donut distribution */}
          <div className="lg:col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <p className="text-sm font-semibold text-gray-700 mb-1">Current distribution</p>
            <p className="text-xs text-gray-400 mb-3">{period.code} · {state.total} students</p>

            <ResponsiveContainer width="100%" height={148}>
              <PieChart>
                <Pie
                  data={donutData}
                  cx="50%"
                  cy="50%"
                  innerRadius={44}
                  outerRadius={68}
                  paddingAngle={2}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {donutData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} stroke="#fff" strokeWidth={2} />
                  ))}
                </Pie>
                <RTooltip
                  formatter={(value: number, name: string) =>
                    [`${value} (${pct(value, state.total)}%)`, name]
                  }
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="space-y-2.5 mt-2">
              {donutData.map(item => (
                <div key={item.name} className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-xs text-gray-500">
                    <span
                      className="w-2 h-2 rounded-sm flex-shrink-0"
                      style={{ background: item.color }}
                    />
                    {item.name}
                  </span>
                  <span className="text-xs font-mono font-semibold text-gray-800">
                    {item.value}
                    <span className="text-gray-400 font-normal ml-1">
                      {pct(item.value, state.total)}%
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Activity log ──────────────────────────────────────────────────── */}
        <div>
          {/* Filter / search toolbar */}
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <h2 className="text-sm font-semibold text-gray-700">Recent activity</h2>
            <span className="text-xs font-mono text-gray-400">({filteredActivity.length})</span>
            <div className="flex-1" />

            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg bg-white
                         focus:outline-none focus:ring-1 focus:ring-indigo-400 cursor-pointer"
            >
              <option value="">All statuses</option>
              <option value="present">Present</option>
              <option value="absent">Absent</option>
              <option value="late">Late</option>
            </select>

            {/* Method filter */}
            <select
              value={methodFilter}
              onChange={e => setMethodFilter(e.target.value)}
              className="text-xs px-2.5 py-1.5 border border-gray-200 rounded-lg bg-white
                         focus:outline-none focus:ring-1 focus:ring-indigo-400 cursor-pointer"
            >
              <option value="">All methods</option>
              {MARK_METHODS.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>

            {/* Student search */}
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              <input
                type="text"
                placeholder="Search student…"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="text-xs pl-7 pr-3 py-1.5 border border-gray-200 rounded-lg bg-white
                           focus:outline-none focus:ring-1 focus:ring-indigo-400 w-36"
              />
            </div>

            {/* CSV export */}
            <button
              onClick={exportCSV}
              disabled={state.activity.length === 0}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 border border-gray-200
                         rounded-lg bg-white hover:bg-gray-50 text-gray-600 transition-colors
                         disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Download size={12} />
              Export CSV
            </button>
          </div>

          {/* Table */}
          <div className="border border-gray-100 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full border-collapse text-sm" style={{ tableLayout: 'fixed' }}>
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  {[
                    { label: '#',       width: 'w-10'  },
                    { label: 'Student', width: ''      },
                    { label: 'Status',  width: 'w-24'  },
                    { label: 'Method',  width: 'w-28'  },
                    { label: 'Time',    width: 'w-24', align: 'text-right' },
                  ].map(col => (
                    <th
                      key={col.label}
                      className={`px-4 py-2.5 text-left text-xs font-semibold text-gray-400
                                  uppercase tracking-wider ${col.width} ${col.align ?? ''}`}
                    >
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody className="divide-y divide-gray-50">
                {filteredActivity.slice(0, 25).map((entry, i) => (
                  <tr
                    key={i}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-2 text-xs font-mono text-gray-400">
                      {entry.rollNo}
                    </td>
                    <td className="px-4 py-2 font-medium text-gray-800 truncate">
                      {entry.studentName}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className="inline-block text-xs px-2.5 py-0.5 rounded-full font-semibold"
                        style={{
                          background: STATUS_STYLE[entry.status].bg,
                          color:      STATUS_STYLE[entry.status].text,
                        }}
                      >
                        {entry.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500">
                      {entry.method}
                    </td>
                    <td className="px-4 py-2 text-xs font-mono text-gray-400 text-right">
                      {entry.timestamp.toLocaleTimeString([], {
                        hour:   '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>
                  </tr>
                ))}

                {filteredActivity.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-sm text-gray-400">
                      No records match the current filters
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {filteredActivity.length > 25 && (
              <div className="px-4 py-2.5 bg-gray-50 border-t border-gray-100 text-center
                              text-xs text-gray-400 font-mono">
                Showing 25 of {filteredActivity.length} records
                {searchQuery || statusFilter || methodFilter ? ' (filtered)' : ''}
              </div>
            )}
          </div>
        </div>

      </div>
    </Layout>
  );
};

export default AttendanceAnalyticsPage;