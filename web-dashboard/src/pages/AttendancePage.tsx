import React, { useState } from 'react';
import { Layout } from '../components';

export const AttendancePage: React.FC = () => {
  const [selectedClass, setSelectedClass] = useState('');
  const [attendance, setAttendance] = useState<any[]>([
    { id: '1', studentId: 'STUD_001', name: 'Parikshith B Bilchode', status: 'Pending' },
    { id: '2', studentId: 'STUD_002', name: 'Gagan D K', status: 'Pending' },
    { id: '3', studentId: 'STUD_003', name: 'Prajwal K', status: 'Pending' },
    { id: '4', studentId: 'STUD_004', name: 'Ved U', status: 'Pending' },
    { id: '5', studentId: 'STUD_005', name: 'Pranav Kumar M', status: 'Pending' },
    { id: '6', studentId: 'STUD_006', name: 'Nischith G A', status: 'Pending' },
  ]);

  const handleMarkAttendance = async (studentId: string, status: string) => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/attendance/mark-attendance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: studentId,
          status: status,
          camera_id: 'manual_web',
          metadata: {
            class_id: selectedClass,
            method: 'manual_admin'
          }
        }),
      });

      if (response.ok) {
        setAttendance(prev => prev.map(record => 
          record.studentId === studentId ? { ...record, status } : record
        ));
      }
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
            <option value="CSE-A-4SEM">CSE A 4TH SEM</option>
            <option value="CSE-B-4SEM">CSE B 4TH SEM</option>
            <option value="CSE-C-4SEM">CSE C 4TH SEM</option>
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
