import { useState, useEffect } from 'react';
import axios from 'axios';
import { BookOpen, Plus, Edit, Trash2, Users } from 'lucide-react';

interface Course {
  id: string;
  name: string;
  code: string;
  schedule: string;
  room: string;
  enrolled_students: number;
  active: boolean;
}

export default function CourseManagementPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingCourse, setEditingCourse] = useState<Course | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    schedule: '',
    room: '',
  });

  useEffect(() => {
    fetchCourses();
  }, []);

  const fetchCourses = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/v1/admin/courses');
      setCourses(response.data);
    } catch (error) {
      console.error('Failed to fetch courses:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingCourse(null);
    setFormData({ name: '', code: '', schedule: '', room: '' });
    setShowModal(true);
  };

  const handleEdit = (course: Course) => {
    setEditingCourse(course);
    setFormData({
      name: course.name,
      code: course.code,
      schedule: course.schedule,
      room: course.room,
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    try {
      if (editingCourse) {
        await axios.put(`http://localhost:8000/api/v1/admin/courses/${editingCourse.id}`, formData);
      } else {
        await axios.post('http://localhost:8000/api/v1/admin/courses', formData);
      }
      fetchCourses();
      setShowModal(false);
    } catch (error) {
      alert('Failed to save course');
    }
  };

  const handleToggle = async (id: string, active: boolean) => {
    try {
      await axios.patch(`http://localhost:8000/api/v1/admin/courses/${id}`, { active: !active });
      fetchCourses();
    } catch (error) {
      alert('Failed to update course');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure?')) return;
    try {
      await axios.delete(`http://localhost:8000/api/v1/admin/courses/${id}`);
      fetchCourses();
    } catch (error) {
      alert('Failed to delete course');
    }
  };

  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BookOpen className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold">Course Management</h1>
        </div>
        <button
          onClick={handleAdd}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Course
        </button>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {courses.map((course) => (
          <div key={course.id} className="bg-white rounded-lg shadow p-6">
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="text-sm text-gray-500">{course.code}</p>
                <h3 className="text-xl font-bold">{course.name}</h3>
              </div>
              <span
                className={`px-3 py-1 rounded text-xs font-semibold ${
                  course.active
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-700'
                }`}
              >
                {course.active ? 'Active' : 'Inactive'}
              </span>
            </div>

            <div className="space-y-2 mb-4 text-sm text-gray-600">
              <p>📅 {course.schedule}</p>
              <p>📍 {course.room}</p>
              <p className="flex items-center gap-2">
                <Users className="w-4 h-4" />
                {course.enrolled_students} students enrolled
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => handleEdit(course)}
                className="flex-1 p-2 text-blue-600 hover:bg-blue-50 rounded flex items-center justify-center gap-2"
              >
                <Edit className="w-4 h-4" />
                Edit
              </button>
              <button
                onClick={() => handleToggle(course.id, course.active)}
                className="flex-1 p-2 text-orange-600 hover:bg-orange-50 rounded"
              >
                {course.active ? 'Disable' : 'Enable'}
              </button>
              <button
                onClick={() => handleDelete(course.id)}
                className="flex-1 p-2 text-red-600 hover:bg-red-50 rounded flex items-center justify-center gap-2"
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold mb-4">
              {editingCourse ? 'Edit Course' : 'Add Course'}
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Course Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Course Code</label>
                <input
                  type="text"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Schedule</label>
                <input
                  type="text"
                  value={formData.schedule}
                  onChange={(e) => setFormData({ ...formData, schedule: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="Mon-Wed 10:00 AM"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Room</label>
                <input
                  type="text"
                  value={formData.room}
                  onChange={(e) => setFormData({ ...formData, room: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="Room 101"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowModal(false)}
                className="flex-1 px-4 py-2 border rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
