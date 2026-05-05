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
    presentStudentIds: [] as string[],
  });

  useEffect(() => {
    // Fetch dashboard stats
    const fetchStats = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/v1/admin/attendance/today');
        const data = await response.json();
        
        if (data && !data.error) {
          setStats({
            totalClasses: 1, 
            totalStudents: data.totalStudents || 70,
            attendanceToday: data.attendanceRate || 0,
            pendingRecords: data.pendingRecords || 0,
            presentStudentIds: data.presentStudentIds || [],
          });
        }
      } catch (error) {
        console.error('Error fetching stats:', error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, []);

  const realStudents = [
    { id: 'STUD_001', name: 'Parikshith B Bilchode' },
    { id: 'STUD_002', name: 'Gagan D K' },
    { id: 'STUD_003', name: 'Prajwal K' },
    { id: 'STUD_004', name: 'Ved U' },
    { id: 'STUD_005', name: 'Pranav Kumar M' },
    { id: 'STUD_006', name: 'Nischith G A' },
  ];

  const missingStudents = [
    ...realStudents.filter(s => !stats.presentStudentIds.includes(s.id)),
    ...Array.from(
      { length: Math.max(0, stats.pendingRecords - realStudents.filter(s => !stats.presentStudentIds.includes(s.id)).length) },
      (_, i) => ({
        id: `STU${(realStudents.length + 1 + i).toString().padStart(3, '0')}`,
        name: `Student ${realStudents.length + 1 + i}`,
      })
    ),
  ];

  return (
    <Layout>
      {!isHealthy && (
        <SystemAlert
          type="warning"
          message="Backend service is offline. Some features may not work."
        />
      )}

      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-800">Dashboard</h1>
          <div className="text-sm text-gray-500 font-medium">
            Class: CSE A 4TH SEM
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 shadow-sm">
            <p className="text-gray-600 text-sm font-semibold mb-1">Total Classes</p>
            <p className="text-3xl font-bold text-blue-600">{stats.totalClasses}</p>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 shadow-sm">
            <p className="text-gray-600 text-sm font-semibold mb-1">Total Students</p>
            <p className="text-3xl font-bold text-green-600">{stats.totalStudents}</p>
          </div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 shadow-sm">
            <p className="text-gray-600 text-sm font-semibold mb-1">Attendance Today</p>
            <p className="text-3xl font-bold text-yellow-600">{stats.attendanceToday}%</p>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 shadow-sm">
            <p className="text-gray-600 text-sm font-semibold mb-1">Pending Records</p>
            <p className="text-3xl font-bold text-red-600">{stats.pendingRecords}</p>
          </div>
        </div>

        {stats.pendingRecords > 0 && (
          <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
            <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
              <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
              Missing Students ({stats.pendingRecords})
            </h2>
            <div className="flex flex-wrap gap-2">
              {missingStudents.map((student) => (
                <div
                  key={student.id}
                  className="px-3 py-2 bg-gray-100 text-gray-700 rounded-md text-xs border border-gray-200 flex flex-col"
                >
                  <span className="font-bold">{student.name}</span>
                  <span className="text-[10px] font-mono opacity-60">{student.id}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};
