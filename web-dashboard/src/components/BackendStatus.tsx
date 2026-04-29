import React from 'react';

interface BackendLoadingScreenProps {
  message?: string;
  showProgress?: boolean;
}

/**
 * Loading screen shown while waiting for backend to be ready
 */
export const BackendLoadingScreen: React.FC<BackendLoadingScreenProps> = ({
  message = 'Starting services...',
  showProgress = true,
}) => {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center">
        <div className="mb-6">
          <div className="inline-flex items-center justify-center">
            <div className="relative w-16 h-16">
              {/* Animated spinner */}
              <div className="absolute inset-0 rounded-full border-4 border-blue-100"></div>
              <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-600 border-r-blue-600 animate-spin"></div>
            </div>
          </div>
        </div>
        <h1 className="text-2xl font-bold text-gray-800 mb-2">Smart Attendance</h1>
        <p className="text-gray-600 mb-4">{message}</p>
        {showProgress && (
          <div className="w-64 mx-auto">
            <div className="bg-gray-200 rounded-full h-2 overflow-hidden">
              <div className="bg-blue-600 h-full rounded-full w-1/3 animate-pulse"></div>
            </div>
            <p className="text-xs text-gray-500 mt-2">Please wait, this may take a few moments...</p>
          </div>
        )}
      </div>
    </div>
  );
};

interface BackendErrorScreenProps {
  error?: string;
  onRetry?: () => void;
}

/**
 * Error screen shown if backend cannot be reached
 */
export const BackendErrorScreen: React.FC<BackendErrorScreenProps> = ({
  error = 'Unable to connect to the server',
  onRetry,
}) => {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-red-50 to-orange-100">
      <div className="text-center max-w-md">
        <div className="mb-6">
          <div className="text-6xl text-red-600 mb-4">⚠️</div>
        </div>
        <h1 className="text-2xl font-bold text-gray-800 mb-2">Connection Error</h1>
        <p className="text-gray-600 mb-6">{error}</p>
        <div className="space-y-2">
          <p className="text-sm text-gray-500">Things you can try:</p>
          <ul className="text-left text-sm text-gray-600 space-y-1 pl-4">
            <li>✓ Ensure the backend server is running</li>
            <li>✓ Check your internet connection</li>
            <li>✓ Check the server logs for errors</li>
            <li>✓ Wait a few moments and try again</li>
          </ul>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-6 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Retry Connection
          </button>
        )}
      </div>
    </div>
  );
};
