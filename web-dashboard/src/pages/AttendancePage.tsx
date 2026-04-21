import React, { useState } from 'react';
import { Camera, Upload, AlertCircle, CheckCircle } from 'lucide-react';
import { Layout, Card, Button, SystemAlert } from '@/components';
import { LiveCameraComponent } from '../components/LiveCamera';
import { UploadPhotoComponent } from '../components/UploadPhoto';

type AttendanceMode = 'live' | 'upload';

interface AttendanceResult {
  status: 'success' | 'error' | 'pending';
  message: string;
  student_name?: string;
  student_id?: string;
  confidence?: number;
}

export const AttendancePage: React.FC = () => {
  const [mode, setMode] = useState<AttendanceMode>('live');
  const [result, setResult] = useState<AttendanceResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleAttendanceMarked = (data: AttendanceResult) => {
    setResult(data);
    setIsLoading(false);
    
    // Auto-clear success message after 3 seconds
    if (data.status === 'success') {
      setTimeout(() => setResult(null), 3000);
    }
  };

  const handleProcessing = (isProcessing: boolean) => {
    setIsLoading(isProcessing);
  };

  const clearResult = () => {
    setResult(null);
  };

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900">Mark Attendance</h1>
          <div className="text-sm text-gray-600">
            {new Date().toLocaleDateString()}
          </div>
        </div>

        {/* Mode Selector */}
        <Card>
          <div className="flex gap-4">
            <button
              onClick={() => { setMode('live'); clearResult(); }}
              className={`flex-1 py-3 px-4 rounded-lg flex items-center justify-center gap-2 font-medium transition-all ${
                mode === 'live'
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <Camera size={20} />
              Live Camera Detection
            </button>
            <button
              onClick={() => { setMode('upload'); clearResult(); }}
              className={`flex-1 py-3 px-4 rounded-lg flex items-center justify-center gap-2 font-medium transition-all ${
                mode === 'upload'
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <Upload size={20} />
              Upload Photo
            </button>
          </div>
        </Card>

        {/* Status Messages */}
        {result && (
          <div
            className={`p-4 rounded-lg flex items-start gap-3 ${
              result.status === 'success'
                ? 'bg-green-50 border border-green-200'
                : result.status === 'error'
                ? 'bg-red-50 border border-red-200'
                : 'bg-yellow-50 border border-yellow-200'
            }`}
          >
            {result.status === 'success' ? (
              <CheckCircle className="text-green-600 flex-shrink-0" size={20} />
            ) : (
              <AlertCircle
                className={`flex-shrink-0 ${
                  result.status === 'error' ? 'text-red-600' : 'text-yellow-600'
                }`}
                size={20}
              />
            )}
            <div className="flex-1">
              <h3
                className={`font-semibold ${
                  result.status === 'success'
                    ? 'text-green-900'
                    : result.status === 'error'
                    ? 'text-red-900'
                    : 'text-yellow-900'
                }`}
              >
                {result.status === 'success' ? 'Attendance Marked' : result.status === 'error' ? 'Error' : 'Processing'}
              </h3>
              <p
                className={`text-sm mt-1 ${
                  result.status === 'success'
                    ? 'text-green-800'
                    : result.status === 'error'
                    ? 'text-red-800'
                    : 'text-yellow-800'
                }`}
              >
                {result.message}
              </p>
              {result.student_name && (
                <div className="mt-2 text-sm font-medium">
                  <p className={result.status === 'success' ? 'text-green-800' : 'text-gray-800'}>
                    Student: {result.student_name}
                  </p>
                  {result.confidence && (
                    <p className={result.status === 'success' ? 'text-green-800' : 'text-gray-800'}>
                      Confidence: {(result.confidence * 100).toFixed(1)}%
                    </p>
                  )}
                </div>
              )}
            </div>
            <button
              onClick={clearResult}
              className="text-gray-500 hover:text-gray-700 flex-shrink-0"
            >
              ✕
            </button>
          </div>
        )}

        {/* Content Area */}
        <div>
          {mode === 'live' ? (
            <LiveCameraComponent
              onAttendanceMarked={handleAttendanceMarked}
              onProcessing={handleProcessing}
              isLoading={isLoading}
            />
          ) : (
            <UploadPhotoComponent
              onAttendanceMarked={handleAttendanceMarked}
              onProcessing={handleProcessing}
              isLoading={isLoading}
            />
          )}
        </div>

        {/* Instructions */}
        <Card className="bg-blue-50 border border-blue-200">
          <h3 className="font-semibold text-blue-900 mb-2">
            {mode === 'live' ? '📹 Live Camera Instructions' : '📸 Upload Photo Instructions'}
          </h3>
          <ul className="text-sm text-blue-800 space-y-1">
            {mode === 'live' ? (
              <>
                <li>✓ Allow camera permission when prompted</li>
                <li>✓ Position your face clearly in the camera frame</li>
                <li>✓ Face will be detected automatically</li>
                <li>✓ Attendance marked instantly upon detection</li>
                <li>✓ Ensure good lighting for best results</li>
              </>
            ) : (
              <>
                <li>✓ Select a photo containing your face</li>
                <li>✓ Supported formats: JPG, PNG, JPEG</li>
                <li>✓ Max file size: 10MB</li>
                <li>✓ Click "Mark Attendance" to process</li>
                <li>✓ Ensure face is clearly visible</li>
              </>
            )}
          </ul>
        </Card>
      </div>
    </Layout>
  );
};
