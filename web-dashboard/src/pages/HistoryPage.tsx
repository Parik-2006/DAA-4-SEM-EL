import React, { useState, useEffect } from 'react';
import { Search, ChevronLeft, ChevronRight, Download } from 'lucide-react';
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

  const { systemRunning, lastSyncTime, error, courses } = useDashboardStore();

  useEffect(() => {
    fetchHistory();
  }, [currentPage, selectedCourse]);

  const fetchHistory = async () => {
    setIsLoading(true);
    try {
      const data = await attendanceAPI.getAttendanceHistory(
        selectedCourse || undefined,
        startDate || undefined,
        endDate || undefined,
        currentPage,
        30
      );
      setHistoryData(data);
      // Calculate total pages based on data length
      setTotalPages(Math.ceil(data.length / 30) || 1);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
    setIsLoading(false);
  };

  const handleSearch = () => {
    setCurrentPage(1);
    fetchHistory();
  };

  const handleExportCSV = () => {
    if (historyData.length === 0) return;

    const headers = ['Student Name', 'Student ID', 'Course', 'Date', 'Status', 'Confidence'];
    const csv = [
      headers.join(','),
      ...historyData.map((record) =>
        [
          record.student_name,
          record.student_id,
          record.course_name,
          new Date(record.marked_at).toLocaleString(),
          record.status,
          record.confidence ? `${(record.confidence * 100).toFixed(0)}%` : 'N/A',
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
    const matches_student =
      record.student_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      record.student_id.toLowerCase().includes(searchTerm.toLowerCase());

    return matches_student;
  });

  const statusConfig = {
    present: 'success',
    late: 'warning',
    absent: 'danger',
    excused: 'info',
  } as const;

  const tableColumns = [
    {
      key: 'student_name',
      label: 'Student Name',
      width: 'w-1/4',
    },
    {
      key: 'student_id',
      label: 'ID',
      width: 'w-1/6',
    },
    {
      key: 'course_name',
      label: 'Course',
      width: 'w-1/4',
    },
    {
      key: 'marked_at',
      label: 'Date & Time',
      render: (value: string) =>
        new Date(value).toLocaleString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }),
    },
    {
      key: 'status',
      label: 'Status',
      render: (value: string) => (
        <Badge variant={statusConfig[value as keyof typeof statusConfig] || 'gray'}>
          {value.charAt(0).toUpperCase() + value.slice(1)}
        </Badge>
      ),
    },
    {
      key: 'confidence',
      label: 'Confidence',
      render: (value: number | undefined) =>
        value ? `${(value * 100).toFixed(0)}%` : 'N/A',
    },
  ];

  return (
    <Layout systemRunning={systemRunning} lastSyncTime={lastSyncTime}>
      <div className="space-y-8">
        {/* System Alert */}
        {!systemRunning && (
          <SystemAlert systemRunning={systemRunning} error={error} />
        )}

        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Attendance History</h1>
          <p className="text-gray-600 mt-1">
            Search and filter attendance records
          </p>
        </div>

        {/* Filters Card */}
        <Card>
          <div className="space-y-6">
            <h3 className="font-semibold text-gray-900">Filters</h3>

            {/* Search Bar */}
            <div className="relative">
              <Search
                className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
                size={20}
              />
              <input
                type="text"
                placeholder="Search by student name or ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>

            {/* Course Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Course
              </label>
              <select
                value={selectedCourse}
                onChange={(e) => {
                  setSelectedCourse(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="">All Courses</option>
                {courses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.code} - {course.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Date Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Start Date
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  End Date
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4 border-t border-gray-100">
              <Button onClick={handleSearch} variant="primary">
                Search
              </Button>
              <Button
                onClick={handleExportCSV}
                variant="secondary"
                disabled={filteredData.length === 0}
              >
                <Download size={20} />
                Export CSV
              </Button>
            </div>
          </div>
        </Card>

        {/* Results Table */}
        <Card>
          <div className="mb-6">
            <h3 className="font-semibold text-gray-900">
              Results ({filteredData.length} records)
            </h3>
          </div>

          <Table
            data={filteredData}
            columns={tableColumns}
            isLoading={isLoading}
            emptyMessage="No attendance records found"
          />

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-6 border-t border-gray-100">
              <p className="text-sm text-gray-600">
                Page {currentPage} of {totalPages}
              </p>
              <div className="flex gap-2">
                <Button
                  onClick={() =>
                    setCurrentPage(Math.max(1, currentPage - 1))
                  }
                  variant="secondary"
                  size="sm"
                  disabled={currentPage === 1}
                >
                  <ChevronLeft size={18} />
                </Button>
                <Button
                  onClick={() =>
                    setCurrentPage(Math.min(totalPages, currentPage + 1))
                  }
                  variant="secondary"
                  size="sm"
                  disabled={currentPage === totalPages}
                >
                  <ChevronRight size={18} />
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </Layout>
  );
};
