import React, { useState, useEffect } from 'react';
import { Layout } from '../components';

export const HistoryPage: React.FC = () => {
  const [history, setHistory] = useState<any[]>([]);
  const [filters, setFilters] = useState({
    startDate: '',
    endDate: '',
    studentId: '',
  });

  useEffect(() => {
    fetchHistory();
  }, [filters]);

  const fetchHistory = async () => {
    try {
      // API call with filters
      setHistory([]);
    } catch (error) {
      console.error('Error fetching history:', error);
    }
  };

  return (
    <Layout>
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-800">Attendance History</h1>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div>
              <label className="block text-gray-700 font-semibold mb-2">
                Start Date
              </label>
              <input
                type="date"
                value={filters.startDate}
                onChange={(e) =>
                  setFilters({ ...filters, startDate: e.target.value })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-gray-700 font-semibold mb-2">
                End Date
              </label>
              <input
                type="date"
                value={filters.endDate}
                onChange={(e) =>
                  setFilters({ ...filters, endDate: e.target.value })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-gray-700 font-semibold mb-2">
                Student ID
              </label>
              <input
                type="text"
                value={filters.studentId}
                onChange={(e) =>
                  setFilters({ ...filters, studentId: e.target.value })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-gray-100 border-b">
                <tr>
                  <th className="px-4 py-2">Date</th>
                  <th className="px-4 py-2">Student ID</th>
                  <th className="px-4 py-2">Class</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map((record, idx) => (
                  <tr key={idx} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-2">{record.date}</td>
                    <td className="px-4 py-2">{record.studentId}</td>
                    <td className="px-4 py-2">{record.class}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`px-3 py-1 rounded text-sm font-semibold ${
                          record.status === 'present'
                            ? 'bg-green-100 text-green-800'
                            : record.status === 'absent'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}
                      >
                        {record.status}
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
