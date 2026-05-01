import React, { useState, useEffect } from 'react';
import { Layout } from '../components';

const StudentManagementPage: React.FC = () => {
  const [students, setStudents] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    // Fetch students
    fetchStudents();
  }, []);

  const fetchStudents = async () => {
    try {
      // API call
      setStudents([]);
    } catch (error) {
      console.error('Error fetching students:', error);
    }
  };

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-800">Student Management</h1>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Add Student
          </button>
        </div>

        {showForm && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Add New Student</h2>
            {/* Form fields here */}
          </div>
        )}

        <div className="bg-white rounded-lg shadow-md p-6">
          <table className="w-full text-left">
            <thead className="bg-gray-100 border-b">
              <tr>
                <th className="px-4 py-2">Student ID</th>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {students.map((student) => (
                <tr key={student.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-2">{student.id}</td>
                  <td className="px-4 py-2">{student.name}</td>
                  <td className="px-4 py-2">{student.email}</td>
                  <td className="px-4 py-2 space-x-2">
                    <button className="text-blue-600 hover:text-blue-800">
                      Edit
                    </button>
                    <button className="text-red-600 hover:text-red-800">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
};

export default StudentManagementPage;
