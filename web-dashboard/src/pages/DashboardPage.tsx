import React, { useState, useEffect } from 'react';
import { Layout, SystemAlert } from '../components';
import { useBackendHealth } from '../hooks/useBackendHealth';

export const DashboardPage: React.FC = () => {
  const { isHealthy, lastChecked } = useBackendHealth();
  const [stats, setStats] = useState({
    totalClasses: 0,
    totalStudents: 0,
    attendanceToday: 0,
    pendingRecords: 0,
  });

  useEffect(() => {
    // Fetch dashboard stats
    const fetchStats = async () => {
      try {
        // Add API call here
        setStats({
          totalClasses: 45,
          totalStudents: 1200,
          attendanceToday: 89,
          pendingRecords: 12,
        });
      } catch (error) {
        console.error('Error fetching stats:', error);
      }
    };

    fetchStats();
  }, []);

  return (
    <Layout>
      {!isHealthy && (
        <SystemAlert
          type="warning"
          message="Backend service is offline. Some features may not work."
        />
      )}

      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-800">Dashboard</h1>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <p className="text-gray-600 text-sm font-semibold">Total Classes</p>
            <p className="text-3xl font-bold text-blue-600">{stats.totalClasses}</p>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-6">
            <p className="text-gray-600 text-sm font-semibold">Total Students</p>
            <p className="text-3xl font-bold text-green-600">{stats.totalStudents}</p>
          </div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
            <p className="text-gray-600 text-sm font-semibold">Attendance Today</p>
            <p className="text-3xl font-bold text-yellow-600">{stats.attendanceToday}%</p>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <p className="text-gray-600 text-sm font-semibold">Pending Records</p>
            <p className="text-3xl font-bold text-red-600">{stats.pendingRecords}</p>
          </div>
        </div>
      </div>
    </Layout>
  );
};
