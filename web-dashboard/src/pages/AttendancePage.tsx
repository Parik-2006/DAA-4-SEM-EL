import React, { useState } from 'react';
import { Layout } from '../components';

export const AttendancePage: React.FC = () => {
  const [selectedClass, setSelectedClass] = useState('');
  const [attendance, setAttendance] = useState<any[]>([]);

  const handleMarkAttendance = async (studentId: string, status: string) => {
    try {
      // Add API call here
      console.log(`Marked ${studentId} as ${status}`);
    } catch (error) {
      console.error('Error marking attendance:', error);
    }
  };

  return (
    <Layout>
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-800">Mark Attendance</h1>

        <div className="bg-white rounded-lg shadow-md p-6">
          <select
            value={selectedClass}
            onChange={(e) => setSelectedClass(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg mb-6"
          >
            <option value="">Select a class...</option>
            <option value="CS-A-SEM6">CS-A-SEM6</option>
            <option value="CS-B-SEM6">CS-B-SEM6</option>
          </select>

          {selectedClass && (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-gray-100 border-b">
                  <tr>
                    <th className="px-4 py-2">Student ID</th>
                    <th className="px-4 py-2">Name</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {attendance.map((record) => (
                    <tr key={record.id} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-2">{record.studentId}</td>
                      <td className="px-4 py-2">{record.name}</td>
                      <td className="px-4 py-2">{record.status}</td>
                      <td className="px-4 py-2 space-x-2">
                        <button
                          onClick={() =>
                            handleMarkAttendance(record.studentId, 'present')
                          }
                          className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600"
                        >
                          Present
                        </button>
                        <button
                          onClick={() =>
                            handleMarkAttendance(record.studentId, 'absent')
                          }
                          className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
                        >
                          Absent
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};
