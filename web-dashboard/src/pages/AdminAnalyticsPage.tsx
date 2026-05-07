import React, { useEffect, useState } from 'react';

import { Layout } from '../components';
import { attendanceAPI } from '../services/api';

function MetricCard({ label, value, helper }: { label: string; value: string | number; helper?: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
      {helper && <p className="mt-2 text-sm text-slate-500">{helper}</p>}
    </div>
  );
}

const AdminAnalyticsPage: React.FC = () => {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const result = await attendanceAPI.getAdminAnalyticsOverview();
        if (!cancelled) {
          setData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load analytics overview');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  const breakdown = (data?.today_breakdown && typeof data.today_breakdown === 'object')
    ? data.today_breakdown as Record<string, unknown>
    : {};

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Admin analytics</p>
          <h1 className="text-3xl font-bold text-slate-900">System Overview</h1>
          <p className="mt-1 text-sm text-slate-500">Attendance and section-level summary for the current day.</p>
        </div>

        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
            Loading analytics...
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            {error}
          </div>
        )}

        {data && !loading && !error && (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-4">
              <MetricCard label="Students" value={Number(data.total_students ?? 0)} />
              <MetricCard label="Sections" value={Number(data.total_sections ?? 0)} />
              <MetricCard label="Attendance" value={`${Number(data.overall_attendance_rate ?? 0).toFixed(1)}%`} />
              <MetricCard label="Active Now" value={Number(data.active_periods_now ?? 0)} />
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Present" value={Number(breakdown.present ?? 0)} />
              <MetricCard label="Late" value={Number(breakdown.late ?? 0)} />
              <MetricCard label="Absent" value={Number(breakdown.absent ?? 0)} />
              <MetricCard label="Pending" value={Number(breakdown.pending ?? 0)} />
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm font-semibold text-slate-900">Today&apos;s breakdown</p>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                <div className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Total Expected</p>
                  <p className="mt-2 text-2xl font-bold text-slate-900">{Number(breakdown.total_expected ?? 0)}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Total Marked</p>
                  <p className="mt-2 text-2xl font-bold text-slate-900">{Number(breakdown.total_marked ?? 0)}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Present</p>
                  <p className="mt-2 text-2xl font-bold text-slate-900">{Number(breakdown.present ?? 0)}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Late</p>
                  <p className="mt-2 text-2xl font-bold text-slate-900">{Number(breakdown.late ?? 0)}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Absent</p>
                  <p className="mt-2 text-2xl font-bold text-slate-900">{Number(breakdown.absent ?? 0)}</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AdminAnalyticsPage;
