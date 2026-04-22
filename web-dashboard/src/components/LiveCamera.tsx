import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Play, StopCircle, Loader, AlertCircle, Camera } from 'lucide-react';
import { attendanceAPI } from '@/services/api';
import { Card, Button } from '@/components';

interface LiveCameraProps {
  onAttendanceMarked: (data: any) => void;
  onProcessing: (isProcessing: boolean) => void;
  isLoading: boolean;
}

export const LiveCameraComponent: React.FC<LiveCameraProps> = ({
  onAttendanceMarked,
  onProcessing,
  isLoading,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectionIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const processingRef = useRef(false);

  const [cameraState, setCameraState] = useState<'idle' | 'requesting' | 'active' | 'error'>('idle');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [frameCount, setFrameCount] = useState(0);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  const stopCamera = useCallback(() => {
    if (detectionIntervalRef.current) {
      clearInterval(detectionIntervalRef.current);
      detectionIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    processingRef.current = false;
    setCameraState('idle');
    setFrameCount(0);
  }, []);

  const startCamera = async () => {
    setCameraError(null);
    setPermissionDenied(false);
    setCameraState('requesting');

    // Check if getUserMedia is available
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError('Camera API is not available. Please use a modern browser (Chrome, Firefox, Edge) over HTTPS or localhost.');
      setCameraState('error');
      return;
    }

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 1280, min: 640 },
          height: { ideal: 720, min: 480 },
        },
        audio: false,
      });

      streamRef.current = mediaStream;

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        // Wait for video to be ready
        await new Promise<void>((resolve, reject) => {
          if (!videoRef.current) { reject(new Error('No video element')); return; }
          videoRef.current.onloadedmetadata = () => resolve();
          videoRef.current.onerror = () => reject(new Error('Video element error'));
          setTimeout(() => resolve(), 3000); // fallback timeout
        });
        await videoRef.current.play().catch(() => {/* autoplay may fail silently */ });
      }

      setCameraState('active');
      startAutoDetection();

    } catch (err: any) {
      const name = err?.name || '';
      let message = 'Failed to access camera.';

      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        message = 'Camera permission denied. Please allow camera access in your browser settings and try again.';
        setPermissionDenied(true);
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        message = 'No camera found. Please connect a camera and try again.';
      } else if (name === 'NotReadableError' || name === 'TrackStartError') {
        message = 'Camera is already in use by another application. Please close other apps using the camera.';
      } else if (name === 'OverconstrainedError') {
        // Retry with looser constraints
        try {
          const fallbackStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          streamRef.current = fallbackStream;
          if (videoRef.current) {
            videoRef.current.srcObject = fallbackStream;
            await videoRef.current.play().catch(() => { });
          }
          setCameraState('active');
          startAutoDetection();
          return;
        } catch {
          message = 'Camera constraints not supported. Try a different browser.';
        }
      } else if (err?.message) {
        message = `Camera error: ${err.message}`;
      }

      setCameraError(message);
      setCameraState('error');
      stopCamera();
    }
  };

  const captureFrame = (): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.videoWidth === 0) {
        resolve(null);
        return;
      }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) { resolve(null); return; }
      ctx.drawImage(video, 0, 0);
      canvas.toBlob(resolve, 'image/jpeg', 0.85);
    });
  };

  const startAutoDetection = () => {
    detectionIntervalRef.current = setInterval(async () => {
      if (processingRef.current) return;

      const blob = await captureFrame();
      if (!blob) return;

      setFrameCount((c) => c + 1);

      try {
        processingRef.current = true;
        onProcessing(true);

        const formData = new FormData();
        formData.append('file', blob, 'frame.jpg');

        const result = await attendanceAPI.detectAndMarkAttendance(formData);

        if (result.matched) {
          onAttendanceMarked({
            status: 'success',
            message: `Attendance marked for ${result.student_name}`,
            student_name: result.student_name,
            student_id: result.student_id,
            confidence: result.confidence,
          });
          stopCamera();
        }
      } catch (err: any) {
        // Silently skip detection errors (face not found, etc.)
        // Only report real network/server errors
        if (err?.response?.status && err.response.status >= 500) {
          onAttendanceMarked({
            status: 'error',
            message: 'Server error during face detection. Please try again.',
          });
        }
      } finally {
        processingRef.current = false;
        onProcessing(false);
      }
    }, 2500);
  };

  const isActive = cameraState === 'active';
  const isRequesting = cameraState === 'requesting';

  return (
    <Card>
      <div className="space-y-4">
        {/* Camera Feed */}
        <div className="relative bg-gray-900 rounded-xl overflow-hidden" style={{ minHeight: '320px' }}>
          {/* Video element — always in DOM so ref is stable */}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={`w-full aspect-video object-cover ${isActive ? 'block' : 'hidden'}`}
            style={{ transform: 'scaleX(-1)' }} /* Mirror for selfie */
          />
          <canvas ref={canvasRef} className="hidden" />

          {/* Placeholder when camera off */}
          {!isActive && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 gap-4">
              <div className="w-20 h-20 rounded-full bg-gray-800 flex items-center justify-center">
                <Camera size={36} className="text-gray-500" />
              </div>
              <p className="text-sm font-medium text-gray-500">
                {isRequesting ? 'Requesting camera access…' : 'Camera is off'}
              </p>
            </div>
          )}

          {/* Processing overlay */}
          {isLoading && isActive && (
            <div className="absolute inset-0 bg-black bg-opacity-40 flex items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <Loader className="animate-spin text-white" size={32} />
                <p className="text-white text-sm font-medium">Detecting face…</p>
              </div>
            </div>
          )}

          {/* LIVE badge */}
          {isActive && (
            <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-red-600 text-white px-2.5 py-1 rounded-full text-xs font-semibold shadow">
              <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
              LIVE
            </div>
          )}

          {/* Frame counter */}
          {isActive && frameCount > 0 && (
            <div className="absolute bottom-3 left-3 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded">
              Scanned {frameCount} frames
            </div>
          )}
        </div>

        {/* Error Message */}
        {cameraError && (
          <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-lg p-4">
            <AlertCircle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-red-800 font-medium">Camera Error</p>
              <p className="text-sm text-red-700 mt-0.5">{cameraError}</p>
              {permissionDenied && (
                <p className="text-xs text-red-600 mt-2">
                  💡 In Chrome: click the camera icon in the address bar → Allow. Then refresh and try again.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="flex gap-3">
          {!isActive ? (
            <button
              onClick={startCamera}
              disabled={isRequesting || isLoading}
              className="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white rounded-lg font-semibold transition-colors"
            >
              {isRequesting ? (
                <>
                  <Loader size={18} className="animate-spin" />
                  Requesting permission…
                </>
              ) : (
                <>
                  <Play size={18} />
                  Start Camera
                </>
              )}
            </button>
          ) : (
            <button
              onClick={stopCamera}
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-red-600 hover:bg-red-700 disabled:bg-red-400 text-white rounded-lg font-semibold transition-colors"
            >
              <StopCircle size={18} />
              Stop Camera
            </button>
          )}
        </div>

        {/* Info */}
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 text-sm text-blue-800">
          <p className="font-semibold mb-1">How it works</p>
          <ul className="space-y-1 text-xs text-blue-700">
            <li>✓ Click <strong>Start Camera</strong> and allow browser permission</li>
            <li>✓ Position your face clearly in the frame (good lighting helps)</li>
            <li>✓ Face is scanned automatically every ~2.5 seconds</li>
            <li>✓ Attendance is marked when a registered face is detected</li>
          </ul>
        </div>
      </div>
    </Card>
  );
};
