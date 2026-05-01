import React, { useState } from 'react';
import { Layout } from '../components';

const FaceRegistrationPage: React.FC = () => {
  const [cameraActive, setCameraActive] = useState(false);
  const [photos, setPhotos] = useState<string[]>([]);

  const startCamera = () => {
    setCameraActive(true);
  };

  const capturePhoto = () => {
    // Capture from camera
    console.log('Photo captured');
  };

  const submitFaces = async () => {
    try {
      // Send faces to backend
      console.log('Submitting faces...');
    } catch (error) {
      console.error('Error submitting faces:', error);
    }
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Face Registration</h1>

        <div className="bg-white rounded-lg shadow-md p-6">
          {!cameraActive ? (
            <button
              onClick={startCamera}
              className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 w-full"
            >
              Start Camera
            </button>
          ) : (
            <div className="space-y-4">
              <div className="bg-black rounded-lg h-80 flex items-center justify-center">
                <p className="text-white">Camera Feed</p>
              </div>

              <div className="flex gap-4">
                <button
                  onClick={capturePhoto}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Capture
                </button>
                <button
                  onClick={() => setCameraActive(false)}
                  className="flex-1 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
                >
                  Stop
                </button>
              </div>

              {photos.length > 0 && (
                <button
                  onClick={submitFaces}
                  className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                >
                  Submit {photos.length} Faces
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default FaceRegistrationPage;
