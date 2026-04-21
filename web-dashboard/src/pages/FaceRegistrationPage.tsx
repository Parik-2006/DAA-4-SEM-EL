import { useState } from 'react';
import axios from 'axios';
import { User, Upload, Camera, Check, X } from 'lucide-react';

export default function FaceRegistrationPage() {
  const [students, setStudents] = useState<any[]>([]);
  const [selectedStudent, setSelectedStudent] = useState('');
  const [webcamActive, setWebcamActive] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setPreview(event.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleWebcamCapture = async () => {
    const video = document.querySelector('video') as HTMLVideoElement;
    if (!video) return;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0);
      setPreview(canvas.toDataURL('image/jpeg'));
    }
  };

  const handleRegister = async () => {
    if (!selectedStudent || !preview) {
      setMessage('Please select student and capture/upload image');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(
        'http://localhost:8000/api/v1/admin/register-face',
        {
          student_id: selectedStudent,
          face_image_base64: preview.split(',')[1],
        }
      );

      if (response.data.success) {
        setMessage('✅ Face registered successfully!');
        setPreview(null);
        setSelectedStudent('');
      }
    } catch (error: any) {
      setMessage(`❌ Error: ${error.response?.data?.detail || 'Registration failed'}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <User className="w-8 h-8 text-blue-600" />
        <h1 className="text-3xl font-bold">Face Registration</h1>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Camera Section */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Camera className="w-5 h-5" />
            Webcam Capture
          </h2>

          {webcamActive && (
            <div className="relative mb-4 flex justify-center items-center bg-gray-900 rounded h-64">
              <video autoPlay playsInline className="h-full rounded" id="webcam" />
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-48 h-64 border-2 border-green-500 rounded-lg opacity-50" />
              </div>
            </div>
          )}

          <button
            onClick={() => setWebcamActive(!webcamActive)}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 mb-2"
          >
            {webcamActive ? 'Stop Camera' : 'Start Camera'}
          </button>

          {webcamActive && (
            <button
              onClick={handleWebcamCapture}
              className="w-full px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              Capture Photo
            </button>
          )}
        </div>

        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Upload className="w-5 h-5" />
            File Upload
          </h2>

          <input
            type="file"
            accept="image/*"
            onChange={handleFileUpload}
            className="block w-full px-4 py-2 border rounded cursor-pointer"
          />
        </div>
      </div>

      {/* Preview */}
      {preview && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-bold mb-4">Image Preview</h3>
          <div className="relative h-64 bg-gray-100 rounded flex items-center justify-center">
            <img src={preview} alt="Preview" className="max-h-60 max-w-full rounded" />
          </div>
        </div>
      )}

      {/* Student Selection */}
      <div className="bg-white rounded-lg shadow p-6">
        <label className="block text-sm font-medium mb-2">Select Student</label>
        <input
          type="text"
          placeholder="Enter Student ID"
          value={selectedStudent}
          onChange={(e) => setSelectedStudent(e.target.value)}
          className="w-full px-3 py-2 border rounded"
        />
      </div>

      {/* Message */}
      {message && (
        <div className={`p-4 rounded ${message.includes('✅') ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {message}
        </div>
      )}

      {/* Register Button */}
      <button
        onClick={handleRegister}
        disabled={loading || !preview || !selectedStudent}
        className="w-full px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-bold"
      >
        {loading ? 'Registering...' : 'Register Face'}
      </button>
    </div>
  );
}
