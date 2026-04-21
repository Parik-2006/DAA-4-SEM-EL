import React, { useEffect, useState, useRef } from 'react';
import { RefreshCw, Users, TrendingUp } from 'lucide-react';
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
  const [courseFilter, setCourseFilter] = useState<string>('');
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

  // Fetch initial data
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
        setError(
          err instanceof Error ? err.message : 'Failed to fetch initial data'
        );
        setSystemRunning(false);
      }
    };

    fetchInitialData();
  }, []);

  // Polling mechanism
  useEffect(() => {
    if (!isPolling) return;

    const pollInterval = setInterval(fetchAttendanceData, 5000);
    pollingIntervalRef.current = pollInterval;

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [isPolling, selectedCourse]);

  const fetchAttendanceData = async () => {
    try {
      const [records, stats] = await Promise.all([
        attendanceAPI.getLiveAttendance(selectedCourse || undefined),
        attendanceAPI.getAttendanceStats(selectedCourse || undefined),
      ]);

      setLiveRecords(records);
      setStats(stats);
      setLastSyncTime(new Date());
      setError(null);

      // Check system health
      try {
        const health = await attendanceAPI.healthCheck();
        setSystemRunning(health);
      } catch {
        setSystemRunning(false);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch attendance data'
      );
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
    setCourseFilter(courseId);
  };

  return (
    <Layout systemRunning={systemRunning} lastSyncTime={lastSyncTime}>
      <div className="space-y-8">
        {/* System Alert */}
        {(error || !systemRunning) && (
          <SystemAlert systemRunning={systemRunning} error={error} />
        )}

        {/* Header with Controls */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-600 mt-1">
              Real-time attendance monitoring and statistics
            </p>
          </div>
          <Button
            onClick={handleRefresh}
            isLoading={isRefreshing}
            variant="primary"
          >
            <RefreshCw size={20} />
            Refresh Now
          </Button>
        </div>

        {/* Statistics Grid */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Present"
              value={stats.total_present}
              color="success"
              icon={<Users size={24} />}
            />
            <StatCard
              label="Late"
              value={stats.total_late}
              color="warning"
              icon={<TrendingUp size={24} />}
            />
            <StatCard
              label="Absent"
              value={stats.total_absent}
              color="danger"
              icon={<Users size={24} />}
            />
            <StatCard
              label="Excused"
              value={stats.total_excused}
              color="info"
              icon={<Users size={24} />}
            />
          </div>
        )}

        {/* Filters */}
        <Card>
          <div className="flex items-center gap-3 pb-6 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-700">
              Filter by Course:
            </span>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => handleCourseFilter('all')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  !selectedCourse
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                All Courses
              </button>
              {courses.map((course) => (
                <button
                  key={course.id}
                  onClick={() => handleCourseFilter(course.id)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    selectedCourse === course.id
                      ? 'bg-indigo-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {course.code} - {course.name}
                </button>
              ))}
            </div>
          </div>
        </Card>

        {/* Live Attendance List */}
        <Card>
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900">
                Live Check-ins
              </h2>
              <p className="text-sm text-gray-500">
                {liveRecords.length} students marked attendance
              </p>
            </div>
            <div
              className={`w-3 h-3 rounded-full animate-pulse ${
                systemRunning ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
          </div>

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {liveRecords.length === 0 ? (
              <div className="text-center py-12">
                <Users className="mx-auto text-gray-300 mb-2" size={40} />
                <p className="text-gray-500">No attendance records yet</p>
              </div>
            ) : (
              liveRecords.map((record, idx) => (
                <AttendanceRecordCard key={idx} record={record} />
              ))
            )}
          </div>
        </Card>

        {/* Additional Info */}
        <Card className="bg-gradient-to-br from-indigo-50 to-purple-50 border-indigo-100">
          <div className="flex items-start gap-4">
            <div className="flex-1">
              <h3 className="font-bold text-gray-900 mb-2">
                Real-time Monitoring Active
              </h3>
              <p className="text-sm text-gray-700">
                The dashboard automatically refreshes every 5 seconds to show
                live attendance data. This connection will continue even while
                the camera system is actively scanning faces.
              </p>
              <ul className="mt-3 text-sm text-gray-700 space-y-1">
                <li>✓ Auto-refresh every 5 seconds</li>
                <li>✓ Face confidence scores displayed</li>
                <li>✓ Course-based filtering available</li>
              </ul>
            </div>
          </div>
        </Card>
      </div>
    </Layout>
  );
};
