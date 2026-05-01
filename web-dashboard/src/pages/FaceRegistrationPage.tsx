import React, { useState } from 'react';
import { Layout, LiveCamera } from '../components';

const FaceRegistrationPage: React.FC = () => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [attendanceData, setAttendanceData] = useState<any>(null);

  const handleAttendanceMarked = (data: any) => {
    setAttendanceData(data);
    console.log('Attendance processed:', data);
  };

  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-800">Face Registration & Detection</h1>
          <div className="px-4 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm font-bold shadow-sm border border-indigo-200">
            Live Mode
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <LiveCamera
              onAttendanceMarked={handleAttendanceMarked}
              onProcessing={setIsProcessing}
              isLoading={isProcessing}
            />
          </div>

          <div className="space-y-6">
            <div className="bg-white rounded-2xl shadow-md p-6 border border-gray-100">
              <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                <div className="w-2 h-6 bg-indigo-500 rounded-full"></div>
                Status
              </h2>
              {attendanceData ? (
                <div className={`p-4 rounded-xl border ${attendanceData.status === 'success' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
                  <p className="font-bold mb-1">{attendanceData.status === 'success' ? 'Detected Successfully' : 'Detection Failed'}</p>
                  <p className="text-sm">{attendanceData.message}</p>
                  {attendanceData.student_name && (
                    <div className="mt-3 pt-3 border-t border-green-200">
                      <p className="text-xs text-green-600 font-semibold uppercase tracking-wider">Student Name</p>
                      <p className="text-lg font-bold">{attendanceData.student_name}</p>
                      <p className="text-xs font-medium opacity-75">ID: {attendanceData.student_id}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-400">
                  <p className="text-sm">Waiting for live capture...</p>
                </div>
              )}
            </div>

            <div className="bg-gradient-to-br from-indigo-600 to-blue-700 rounded-2xl shadow-lg p-6 text-white">
              <h3 className="font-bold mb-2">Instructions</h3>
              <ul className="text-xs space-y-2 opacity-90">
                <li className="flex gap-2">
                  <span className="font-bold">1.</span>
                  <span>Click "Start Camera" to begin live feed.</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-bold">2.</span>
                  <span>Position your face clearly within the frame.</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-bold">3.</span>
                  <span>Wait for the system to detect your face automatically.</span>
                </li>
                <li className="flex gap-2">
                  <span className="font-bold">4.</span>
                  <span>Confirm your identity in the pop-up modal.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default FaceRegistrationPage;
