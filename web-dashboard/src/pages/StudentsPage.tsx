import React, { useState, useEffect } from 'react';
import { Search, Mail, Book } from 'lucide-react';
import { useDashboardStore } from '@/store';
import { attendanceAPI, Student } from '@/services/api';
import { Layout, SystemAlert, Card, Button, Badge, Table } from '@/components';

export const StudentsPage: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [allStudents, setAllStudents] = useState<Student[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>('');

  const { systemRunning, lastSyncTime, error, courses } = useDashboardStore();

  useEffect(() => {
    fetchStudents();
  }, [selectedCourse]);

  const fetchStudents = async () => {
    setIsLoading(true);
    try {
      const data = await attendanceAPI.getStudents(
        selectedCourse || undefined
      );
      setAllStudents(data);
    } catch (err) {
      console.error('Failed to fetch students:', err);
    }
    setIsLoading(false);
  };

  const filteredStudents = allStudents.filter((student) => {
    const searchLower = searchTerm.toLowerCase();
    return (
      student.name.toLowerCase().includes(searchLower) ||
      student.student_id.toLowerCase().includes(searchLower) ||
      student.email.toLowerCase().includes(searchLower)
    );
  });

  const tableColumns = [
    {
      key: 'student_id' as keyof Student,
      label: 'Student ID',
      width: 'w-1/6',
    },
    {
      key: 'name' as keyof Student,
      label: 'Name',
      width: 'w-1/4',
      render: (value: string, row: Student) => (
        <div className="flex items-center gap-3">
          {row.avatar_url ? (
            <img
              src={row.avatar_url}
              alt={value}
              className="w-10 h-10 rounded-full object-cover"
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-400 to-purple-600 flex items-center justify-center text-white font-semibold text-sm">
              {value.charAt(0).toUpperCase()}
            </div>
          )}
          <div>
            <p className="font-medium text-gray-900">{value}</p>
            <p className="text-xs text-gray-500">{row.email}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'department' as keyof Student,
      label: 'Department',
      width: 'w-1/5',
    },
    {
      key: 'semester' as keyof Student,
      label: 'Semester',
      render: (value: string | undefined) =>
        value ? (
          <Badge variant="info" size="sm">
            Sem {value}
          </Badge>
        ) : (
          <span className="text-gray-400">-</span>
        ),
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
          <h1 className="text-3xl font-bold text-gray-900">Students</h1>
          <p className="text-gray-600 mt-1">
            Manage and view all registered students
          </p>
        </div>

        {/* Search and Filter Card */}
        <Card>
          <div className="space-y-4">
            {/* Search Bar */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Search
              </label>
              <div className="relative">
                <Search
                  className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
                  size={20}
                />
                <input
                  type="text"
                  placeholder="Search by name, ID, or email..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Course Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Filter by Course
              </label>
              <select
                value={selectedCourse}
                onChange={(e) => setSelectedCourse(e.target.value)}
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
          </div>
        </Card>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <div className="text-center">
              <p className="text-sm text-gray-600 mb-1">Total Students</p>
              <p className="text-3xl font-bold text-indigo-600">
                {allStudents.length}
              </p>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <p className="text-sm text-gray-600 mb-1">Filtered Results</p>
              <p className="text-3xl font-bold text-purple-600">
                {filteredStudents.length}
              </p>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <p className="text-sm text-gray-600 mb-1">With Avatars</p>
              <p className="text-3xl font-bold text-green-600">
                {allStudents.filter((s) => s.avatar_url).length}
              </p>
            </div>
          </Card>
        </div>

        {/* Students Table */}
        <Card>
          <div className="mb-6">
            <h3 className="font-semibold text-gray-900">
              Student List ({filteredStudents.length} of {allStudents.length})
            </h3>
          </div>

          <Table
            data={filteredStudents}
            columns={tableColumns}
            isLoading={isLoading}
            emptyMessage="No students found matching your criteria"
          />
        </Card>

        {/* Info Box */}
        <Card className="bg-blue-50 border-blue-200">
          <div className="flex gap-4">
            <Mail className="text-blue-600 flex-shrink-0" size={24} />
            <div>
              <h3 className="font-semibold text-gray-900 mb-1">
                Student Management
              </h3>
              <p className="text-sm text-gray-700">
                This view displays all registered students in the system. Filter
                by course to see students enrolled in specific classes. Students
                with avatars have completed face registration for biometric
                attendance.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </Layout>
  );
};
