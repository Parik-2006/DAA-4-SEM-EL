import React, { useState, useEffect } from 'react';
import { Layout } from '../components';

const CourseManagementPage: React.FC = () => {
  const [courses, setCourses] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    // Fetch courses
    fetchCourses();
  }, []);

  const fetchCourses = async () => {
    try {
      // API call
      setCourses([]);
    } catch (error) {
      console.error('Error fetching courses:', error);
    }
  };

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-800">Course Management</h1>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Add Course
          </button>
        </div>

        {showForm && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">Add New Course</h2>
            {/* Form fields here */}
          </div>
        )}

        <div className="bg-white rounded-lg shadow-md p-6">
          <table className="w-full text-left">
            <thead className="bg-gray-100 border-b">
              <tr>
                <th className="px-4 py-2">Course Code</th>
                <th className="px-4 py-2">Course Name</th>
                <th className="px-4 py-2">Faculty</th>
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {courses.map((course) => (
                <tr key={course.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-2">{course.code}</td>
                  <td className="px-4 py-2">{course.name}</td>
                  <td className="px-4 py-2">{course.faculty}</td>
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

export default CourseManagementPage;
