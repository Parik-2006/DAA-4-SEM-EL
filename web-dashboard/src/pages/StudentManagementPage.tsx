import { useState, useEffect } from 'react';
import axios from 'axios';
import { Users, Plus, Edit, Trash2, Search } from 'lucide-react';

interface Student {
  user_id: string;
  name: string;
  email: string;
  role: string;
  courses?: string[];
}

export default function StudentManagementPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingStudent, setEditingStudent] = useState<Student | null>(null);
  const [formData, setFormData] = useState({ name: '', email: '', courses: '' });

  useEffect(() => {
    fetchStudents();
  }, []);

  const fetchStudents = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/v1/admin/students');
      setStudents(response.data);
    } catch (error) {
      console.error('Failed to fetch students:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingStudent(null);
    setFormData({ name: '', email: '', courses: '' });
    setShowModal(true);
  };

  const handleEdit = (student: Student) => {
    setEditingStudent(student);
    setFormData({
      name: student.name,
      email: student.email,
      courses: student.courses?.join(',') || '',
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    try {
      if (editingStudent) {
        await axios.put(`http://localhost:8000/api/v1/admin/students/${editingStudent.user_id}`, {
          name: formData.name,
          email: formData.email,
          courses: formData.courses.split(',').map((c) => c.trim()),
        });
      } else {
        await axios.post('http://localhost:8000/api/v1/admin/students', {
          name: formData.name,
          email: formData.email,
          courses: formData.courses.split(',').map((c) => c.trim()),
        });
      }
      fetchStudents();
      setShowModal(false);
    } catch (error) {
      alert('Failed to save student');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure?')) return;
    try {
      await axios.delete(`http://localhost:8000/api/v1/admin/students/${id}`);
      fetchStudents();
    } catch (error) {
      alert('Failed to delete student');
    }
  };

  const filteredStudents = students.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.email.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold">Student Management</h1>
        </div>
        <button
          onClick={handleAdd}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Student
        </button>
      </div>

      <div className="bg-white rounded-lg shadow p-4 flex items-center gap-2">
        <Search className="w-5 h-5 text-gray-400" />
        <input
          type="text"
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 outline-none"
        />
      </div>

      <div className="bg-white rounded-lg shadow overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left">Name</th>
              <th className="px-4 py-3 text-left">Email</th>
              <th className="px-4 py-3 text-left">Student ID</th>
              <th className="px-4 py-3 text-left">Courses</th>
              <th className="px-4 py-3 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredStudents.map((student) => (
              <tr key={student.user_id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-3 font-semibold">{student.name}</td>
                <td className="px-4 py-3">{student.email}</td>
                <td className="px-4 py-3 text-gray-600">{student.user_id}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
                    {student.courses?.length || 0} courses
                  </span>
                </td>
                <td className="px-4 py-3 flex gap-2">
                  <button
                    onClick={() => handleEdit(student)}
                    className="p-2 text-blue-600 hover:bg-blue-100 rounded"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(student.user_id)}
                    className="p-2 text-red-600 hover:bg-red-100 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold mb-4">
              {editingStudent ? 'Edit Student' : 'Add Student'}
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Courses (comma-separated)</label>
                <input
                  type="text"
                  value={formData.courses}
                  onChange={(e) => setFormData({ ...formData, courses: e.target.value })}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="COURSE001, COURSE002"
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
