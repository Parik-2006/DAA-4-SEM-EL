import React, { useRef, useState, useEffect } from 'react';
import { Play, StopCircle, Loader } from 'lucide-react';
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
  const [isStreamActive, setIsStreamActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const detectionIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Start camera
  const startCamera = async () => {
    try {
      setCameraError(null);
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        setStream(mediaStream);
        setIsStreamActive(true);

        // Start auto-detection
        startAutoDetection();
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to access camera';
      setCameraError(errorMsg);
      onAttendanceMarked({
        status: 'error',
        message: errorMsg,
      });
    }
  };

  // Stop camera
  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
      setIsStreamActive(false);

      if (detectionIntervalRef.current) {
        clearInterval(detectionIntervalRef.current);
      }
    }
  };

  // Auto-detection every 2 seconds
  const startAutoDetection = () => {
    detectionIntervalRef.current = setInterval(async () => {
      if (!videoRef.current || !canvasRef.current) return;

      try {
        // Draw video frame to canvas
        const ctx = canvasRef.current.getContext('2d');
        if (!ctx) return;

        canvasRef.current.width = videoRef.current.videoWidth;
        canvasRef.current.height = videoRef.current.videoHeight;
        ctx.drawImage(videoRef.current, 0, 0);

        // Convert canvas to blob
        canvasRef.current.toBlob(async (blob) => {
          if (!blob) return;

          try {
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

              // Stop camera after successful detection
              stopCamera();
            }
          } catch (err) {
            // Silently continue detection, don't show error on every failed frame
            console.log('Detection frame processed');
          } finally {
            onProcessing(false);
          }
        }, 'image/jpeg', 0.8);
      } catch (err) {
        console.error('Auto-detection error:', err);
      }
    }, 2000); // Every 2 seconds
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  return (
    <Card>
      <div className="space-y-4">
        {/* Camera Feed */}
        <div className="relative bg-black rounded-lg overflow-hidden">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            className="w-full aspect-video object-cover"
          />
          <canvas ref={canvasRef} className="hidden" />

          {/* Loading Overlay */}
          {isLoading && (
            <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <Loader className="animate-spin text-white" size={32} />
                <p className="text-white text-sm">Processing frame...</p>
              </div>
            </div>
          )}

          {/* Status Indicator */}
          {isStreamActive && (
            <div className="absolute top-4 right-4 flex items-center gap-2 bg-red-600 text-white px-3 py-1 rounded-full text-sm font-medium">
              <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
              LIVE
            </div>
          )}
        </div>

        {/* Error Message */}
        {cameraError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-800 text-sm">
            {cameraError}
          </div>
        )}

        {/* Controls */}
        <div className="flex gap-3">
          {!isStreamActive ? (
            <Button
              onClick={startCamera}
              className="flex-1 bg-green-600 hover:bg-green-700"
              disabled={isLoading}
            >
              <Play size={18} className="mr-2" />
              Start Camera
            </Button>
          ) : (
            <Button
              onClick={stopCamera}
              className="flex-1 bg-red-600 hover:bg-red-700"
              disabled={isLoading}
            >
              <StopCircle size={18} className="mr-2" />
              Stop Camera
            </Button>
          )}
        </div>

        {/* Info */}
        <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-700">
          <p className="font-medium mb-1">Auto-Detection Active</p>
          <p>Face will be detected automatically every 2 seconds. Keep your face visible in the camera frame.</p>
        </div>
      </div>
    </Card>
  );
};
