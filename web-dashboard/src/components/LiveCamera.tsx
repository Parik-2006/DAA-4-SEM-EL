import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Play, StopCircle, Loader, AlertCircle, Camera, Check, X, ShieldCheck, User } from 'lucide-react';
import { attendanceAPI, DetectFaceResponse, ConfirmAttendanceResponse } from '@/services/api';
import { Card } from './UI';

interface LiveCameraProps {
  onAttendanceMarked: (data: any) => void;
  onProcessing: (isProcessing: boolean) => void;
  isLoading: boolean;
}

// ── Confirmation Modal ─────────────────────────────────────────────────────────

interface ConfirmationModalProps {
  detection: DetectFaceResponse;
  onConfirm: () => void;
  onDeny: () => void;
  isSaving: boolean;
}

const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  detection,
  onConfirm,
  onDeny,
  isSaving,
}) => {
  const confidencePct = Math.round((detection.confidence ?? 0) * 100);
  const barColor =
    confidencePct >= 85 ? '#4ade80' : confidencePct >= 70 ? '#fbbf24' : '#f87171';

  return (
    /* Backdrop */
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(30,20,10,0.55)', backdropFilter: 'blur(4px)' }}>

      {/* Card */}
      <div
        className="relative w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden"
        style={{
          background: 'linear-gradient(160deg, #fdf6ee 0%, #fef9f3 60%, #fff8f0 100%)',
          border: '1.5px solid #e8d9c4',
          animation: 'modalIn 0.28s cubic-bezier(0.34,1.56,0.64,1)',
        }}
      >
        {/* Top accent stripe */}
        <div style={{ height: 4, background: 'linear-gradient(90deg, #c8a97e, #e2c49a, #c8a97e)' }} />

        <div className="p-7">
          {/* Icon header */}
          <div className="flex justify-center mb-5">
            <div className="relative">
              <div
                className="w-20 h-20 rounded-full flex items-center justify-center shadow-md"
                style={{ background: 'linear-gradient(135deg, #e8d5b8, #f5e6d0)' }}
              >
                <User size={36} style={{ color: '#8b6840' }} />
              </div>
              <div
                className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full flex items-center justify-center shadow"
                style={{ background: '#4ade80' }}
              >
                <Check size={14} color="white" strokeWidth={3} />
              </div>
            </div>
          </div>

          {/* Question */}
          <h2
            className="text-center font-bold mb-1"
            style={{ fontSize: 20, color: '#3d2b1a', letterSpacing: '-0.3px' }}
          >
            Is this you?
          </h2>
          <p className="text-center mb-5" style={{ color: '#7a5c3e', fontSize: 14 }}>
            Please confirm your identity to mark attendance.
          </p>

          {/* Student card */}
          <div
            className="rounded-xl p-4 mb-5"
            style={{ background: 'rgba(200,169,126,0.13)', border: '1px solid #d4b896' }}
          >
            <p
              className="text-center font-bold mb-0.5"
              style={{ fontSize: 22, color: '#2d1f0f' }}
            >
              {detection.student_name}
            </p>
            <p className="text-center text-sm mb-3" style={{ color: '#7a5c3e' }}>
              ID: {detection.student_id}
            </p>

            {/* Confidence bar */}
            <div>
              <div className="flex justify-between mb-1" style={{ fontSize: 11, color: '#9a7a5a' }}>
                <span>Match confidence</span>
                <span style={{ fontWeight: 700, color: barColor }}>{confidencePct}%</span>
              </div>
              <div
                className="rounded-full overflow-hidden"
                style={{ height: 6, background: '#e8d5b8' }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${confidencePct}%`,
                    background: `linear-gradient(90deg, ${barColor}99, ${barColor})`,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-3">
            {/* No */}
            <button
              onClick={onDeny}
              disabled={isSaving}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95"
              style={{
                padding: '12px 0',
                background: 'rgba(200,169,126,0.15)',
                border: '1.5px solid #c8a97e',
                color: '#7a5c3e',
                fontSize: 15,
                cursor: isSaving ? 'not-allowed' : 'pointer',
                opacity: isSaving ? 0.5 : 1,
              }}
            >
              <X size={17} />
              Not me
            </button>

            {/* Yes */}
            <button
              onClick={onConfirm}
              disabled={isSaving}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95 shadow-md"
              style={{
                padding: '12px 0',
                background: isSaving
                  ? '#a0856a'
                  : 'linear-gradient(135deg, #b8864e, #c8a97e)',
                border: 'none',
                color: '#fff',
                fontSize: 15,
                cursor: isSaving ? 'not-allowed' : 'pointer',
              }}
            >
              {isSaving ? (
                <>
                  <Loader size={16} className="animate-spin" />
                  Saving…
                </>
              ) : (
                <>
                  <ShieldCheck size={17} />
                  Yes, that's me
                </>
              )}
            </button>
          </div>
        </div>

        {/* Bottom note */}
        <p className="text-center pb-4 px-6" style={{ fontSize: 11, color: '#b89a7a' }}>
          If this isn't you, tap "Not me" and try again.
        </p>
      </div>

      {/* keyframe injection */}
      <style>{`
        @keyframes modalIn {
          from { opacity: 0; transform: scale(0.88) translateY(16px); }
          to   { opacity: 1; transform: scale(1)    translateY(0);     }
        }
      `}</style>
    </div>
  );
};

// ── Success Flash ──────────────────────────────────────────────────────────────

const SuccessFlash: React.FC<{ name: string }> = ({ name }) => (
  <div
    className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
    style={{ animation: 'fadeOut 2.2s ease forwards' }}
  >
    <div
      className="rounded-2xl px-10 py-8 shadow-2xl flex flex-col items-center gap-3"
      style={{
        background: 'linear-gradient(135deg, #fdf6ee, #fff8f0)',
        border: '1.5px solid #c8a97e',
        animation: 'popIn 0.35s cubic-bezier(0.34,1.56,0.64,1)',
      }}
    >
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center shadow-lg"
        style={{ background: 'linear-gradient(135deg, #4ade80, #22c55e)' }}
      >
        <Check size={32} color="white" strokeWidth={3} />
      </div>
      <p style={{ fontWeight: 700, fontSize: 20, color: '#2d1f0f' }}>Attendance Marked!</p>
      <p style={{ fontSize: 14, color: '#7a5c3e' }}>{name}</p>
    </div>
    <style>{`
      @keyframes popIn {
        from { opacity: 0; transform: scale(0.7); }
        to   { opacity: 1; transform: scale(1); }
      }
      @keyframes fadeOut {
        0%,60% { opacity: 1; }
        100%    { opacity: 0; }
      }
    `}</style>
  </div>
);

// ── Main LiveCamera component ──────────────────────────────────────────────────

export const LiveCameraComponent: React.FC<LiveCameraProps> = ({
  onAttendanceMarked,
  onProcessing,
  isLoading,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const processingRef = useRef(false);
  const pausedForConfirmRef = useRef(false);
  const consecutiveNoFaceRef = useRef(0);

  const [cameraState, setCameraState] = useState<'idle' | 'requesting' | 'active' | 'error'>('idle');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [frameCount, setFrameCount] = useState(0);

  // Inline status banner
  const [lastFeedback, setLastFeedback] = useState<string | null>(null);
  const [feedbackType, setFeedbackType] = useState<'info' | 'warn' | 'error'>('info');

  // Confirmation modal state
  const [pendingDetection, setPendingDetection] = useState<DetectFaceResponse | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Success flash
  const [successName, setSuccessName] = useState<string | null>(null);

  // ── Cleanup ────────────────────────────────────────────────────────────────

  useEffect(() => () => stopCamera(), []);

  const stopCamera = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    processingRef.current = false;
    pausedForConfirmRef.current = false;
    setCameraState('idle');
    setFrameCount(0);
    setLastFeedback(null);
    consecutiveNoFaceRef.current = 0;
  }, []);

  // ── Start camera ───────────────────────────────────────────────────────────

  const startCamera = async () => {
    setCameraError(null);
    setPermissionDenied(false);
    setCameraState('requesting');

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError('Camera API unavailable. Use Chrome/Firefox over HTTPS or localhost.');
      setCameraState('error');
      return;
    }

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280, min: 640 }, height: { ideal: 720, min: 480 } },
        audio: false,
      });
      streamRef.current = mediaStream;

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await new Promise<void>((res) => {
          const v = videoRef.current!;
          v.onloadedmetadata = () => res();
          setTimeout(res, 3000);
        });
        await videoRef.current.play().catch(() => { });
      }

      setCameraState('active');
      startDetectionLoop();
    } catch (err: any) {
      const name = err?.name ?? '';
      let msg = 'Failed to access camera.';
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        msg = 'Camera permission denied. Please allow camera access in your browser settings.';
        setPermissionDenied(true);
      } else if (name === 'NotFoundError') {
        msg = 'No camera found. Please connect a camera and try again.';
      } else if (name === 'NotReadableError') {
        msg = 'Camera is already in use by another application.';
      } else if (err?.message) {
        msg = `Camera error: ${err.message}`;
      }
      setCameraError(msg);
      setCameraState('error');
      stopCamera();
    }
  };

  // ── Frame capture ──────────────────────────────────────────────────────────

  const captureFrame = (): Promise<Blob | null> =>
    new Promise(resolve => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.videoWidth === 0) { resolve(null); return; }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) { resolve(null); return; }
      ctx.drawImage(video, 0, 0);
      canvas.toBlob(resolve, 'image/jpeg', 0.85);
    });

  // ── Detection loop ─────────────────────────────────────────────────────────

  const startDetectionLoop = () => {
    intervalRef.current = setInterval(async () => {
      // Pause scanning while the confirmation dialog is open
      if (processingRef.current || pausedForConfirmRef.current) return;

      const video = videoRef.current;
      if (!video || video.readyState < 2) return;

      const blob = await captureFrame();
      if (!blob) return;

      setFrameCount(c => c + 1);

      try {
        processingRef.current = true;
        onProcessing(true);

        const formData = new FormData();
        formData.append('file', blob, 'frame.jpg');

        // Step 1: identify only — no DB write
        const result: DetectFaceResponse = await attendanceAPI.detectFaceOnly(formData);

        if (result.matched) {
          // Pause loop and show confirmation modal
          pausedForConfirmRef.current = true;
          consecutiveNoFaceRef.current = 0;
          setLastFeedback(null);
          setPendingDetection(result);
        } else {
          // Update inline feedback banner
          consecutiveNoFaceRef.current += 1;
          const msg = result.message || 'No matching face found.';
          const isNoFace = msg.toLowerCase().includes('no face') || msg.toLowerCase().includes('not detected');
          const isNoEmb = msg.toLowerCase().includes('not registered') || msg.toLowerCase().includes('no face profile');
          const isServerErr = msg.toLowerCase().includes('server error') || msg.toLowerCase().includes('model not loaded');

          if (isServerErr) {
            setFeedbackType('error');
            setLastFeedback(`⚠️ ${msg}`);
            if (consecutiveNoFaceRef.current >= 3) {
              onAttendanceMarked({ status: 'error', message: msg });
              stopCamera();
            }
          } else if (isNoEmb) {
            setFeedbackType('error');
            setLastFeedback('❌ No face profile registered. Ask admin to register your face.');
          } else if (isNoFace && consecutiveNoFaceRef.current <= 2) {
            setFeedbackType('info');
            setLastFeedback('👁 Centre your face in the frame…');
          } else if (!isNoFace) {
            setFeedbackType('warn');
            setLastFeedback(`🔍 ${msg}`);
          }
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Unexpected camera error.';
        setFeedbackType('error');
        setLastFeedback(`❌ ${message}`);
      } finally {
        processingRef.current = false;
        onProcessing(false);
      }
    }, 2500);
  };

  // ── Confirmation handlers ──────────────────────────────────────────────────

  const handleConfirm = async () => {
    if (!pendingDetection) return;
    setIsSaving(true);
    try {
      // Step 2: persist to database
      const confirmation: ConfirmAttendanceResponse = await attendanceAPI.confirmAttendance(
        pendingDetection.student_id!,
        pendingDetection.confidence ?? 0
      );

      setPendingDetection(null);
      setSuccessName(confirmation.student_name);

      // Notify parent and stop camera
      onAttendanceMarked({
        status: 'success',
        message: confirmation.message,
        student_name: confirmation.student_name,
        student_id: confirmation.student_id,
        confidence: confirmation.confidence,
        record_id: confirmation.record_id,
      });

      stopCamera();

      // Clear flash after animation
      setTimeout(() => setSuccessName(null), 2400);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Failed to save attendance.';
      setPendingDetection(null);
      pausedForConfirmRef.current = false;
      setFeedbackType('error');
      setLastFeedback(`❌ Save failed: ${msg}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeny = () => {
    setPendingDetection(null);
    pausedForConfirmRef.current = false;
    setFeedbackType('info');
    setLastFeedback('🔄 Scanning resumed — please look at the camera.');
    consecutiveNoFaceRef.current = 0;
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  const isActive = cameraState === 'active';
  const isRequesting = cameraState === 'requesting';

  return (
    <>
      {/* Confirmation modal (portal-style, renders over everything) */}
      {pendingDetection && (
        <ConfirmationModal
          detection={pendingDetection}
          onConfirm={handleConfirm}
          onDeny={handleDeny}
          isSaving={isSaving}
        />
      )}

      {/* Success flash */}
      {successName && <SuccessFlash name={successName} />}

      <Card>
        <div className="space-y-4">

          {/* Camera feed */}
          <div
            className="relative rounded-xl overflow-hidden"
            style={{ minHeight: 320, background: '#1a1208' }}
          >
            <video
              ref={videoRef}
              autoPlay playsInline muted
              className={`w-full aspect-video object-cover ${isActive ? 'block' : 'hidden'}`}
              style={{ transform: 'scaleX(-1)' }}
            />
            <canvas ref={canvasRef} className="hidden" />

            {/* Placeholder */}
            {!isActive && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4"
                style={{ color: '#7a5c3e' }}>
                <div className="w-20 h-20 rounded-full flex items-center justify-center"
                  style={{ background: 'rgba(200,169,126,0.15)' }}>
                  <Camera size={36} style={{ color: '#c8a97e' }} />
                </div>
                <p className="text-sm font-medium" style={{ color: '#9a7a5a' }}>
                  {isRequesting ? 'Requesting camera access…' : 'Camera is off'}
                </p>
              </div>
            )}

            {/* Processing overlay */}
            {isLoading && isActive && (
              <div className="absolute inset-0 flex items-center justify-center"
                style={{ background: 'rgba(0,0,0,0.38)' }}>
                <div className="flex flex-col items-center gap-2">
                  <Loader className="animate-spin text-amber-300" size={32} />
                  <p className="text-white text-sm font-medium">Detecting face…</p>
                </div>
              </div>
            )}

            {/* Paused-for-confirm overlay */}
            {pendingDetection && isActive && (
              <div className="absolute inset-0 flex items-center justify-center"
                style={{ background: 'rgba(0,0,0,0.55)' }}>
                <p className="text-white text-sm font-semibold tracking-wide">
                  ⏸ Paused — awaiting confirmation
                </p>
              </div>
            )}

            {/* LIVE badge */}
            {isActive && !pendingDetection && (
              <div className="absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold shadow"
                style={{ background: '#dc2626', color: '#fff' }}>
                <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
                LIVE
              </div>
            )}

            {/* Frame counter */}
            {isActive && frameCount > 0 && (
              <div className="absolute bottom-3 left-3 rounded px-2 py-1 text-xs"
                style={{ background: 'rgba(0,0,0,0.5)', color: '#e8d5b8' }}>
                {frameCount} frames scanned
              </div>
            )}
          </div>

          {/* Inline feedback banner */}
          {isActive && lastFeedback && !pendingDetection && (
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium"
              style={{
                background:
                  feedbackType === 'error' ? 'rgba(239,68,68,0.09)'
                    : feedbackType === 'warn' ? 'rgba(251,191,36,0.09)'
                      : 'rgba(200,169,126,0.12)',
                border: `1px solid ${feedbackType === 'error' ? '#fca5a5'
                    : feedbackType === 'warn' ? '#fde68a'
                      : '#d4b896'
                  }`,
                color:
                  feedbackType === 'error' ? '#b91c1c'
                    : feedbackType === 'warn' ? '#92400e'
                      : '#7a5c3e',
              }}
            >
              <span className="flex-1">{lastFeedback}</span>
              {frameCount > 0 && (
                <span className="text-xs opacity-50 ml-2 flex-shrink-0">frame {frameCount}</span>
              )}
            </div>
          )}

          {/* Camera error */}
          {cameraError && (
            <div className="flex items-start gap-3 rounded-lg p-4"
              style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid #fca5a5' }}>
              <AlertCircle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800">Camera Error</p>
                <p className="text-sm text-red-700 mt-0.5">{cameraError}</p>
                {permissionDenied && (
                  <p className="text-xs text-red-600 mt-2">
                    💡 In Chrome: click the camera icon in the address bar → Allow. Then refresh.
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
                className="flex-1 flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95"
                style={{
                  padding: '12px 0',
                  background: isRequesting || isLoading
                    ? '#a0856a'
                    : 'linear-gradient(135deg, #b8864e, #c8a97e)',
                  color: '#fff',
                  border: 'none',
                  fontSize: 15,
                  cursor: isRequesting || isLoading ? 'not-allowed' : 'pointer',
                }}
              >
                {isRequesting ? (
                  <><Loader size={18} className="animate-spin" />Requesting permission…</>
                ) : (
                  <><Play size={18} />Start Camera</>
                )}
              </button>
            ) : (
              <button
                onClick={stopCamera}
                disabled={isLoading}
                className="flex-1 flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95"
                style={{
                  padding: '12px 0',
                  background: 'rgba(239,68,68,0.85)',
                  color: '#fff',
                  border: 'none',
                  fontSize: 15,
                  cursor: isLoading ? 'not-allowed' : 'pointer',
                }}
              >
                <StopCircle size={18} />
                Stop Camera
              </button>
            )}
          </div>

          {/* Info box */}
          <div
            className="rounded-lg p-4 text-sm"
            style={{ background: 'rgba(200,169,126,0.1)', border: '1px solid #d4b896', color: '#7a5c3e' }}
          >
            <p className="font-semibold mb-1" style={{ color: '#5a3e28' }}>How two-step check-in works</p>
            <ul className="space-y-1 text-xs">
              <li>✓ Click <strong>Start Camera</strong> and allow browser permission</li>
              <li>✓ Position your face clearly — scanned every ~2.5 s</li>
              <li>✓ When your face is recognised, a confirmation dialog appears</li>
              <li>✓ Tap <strong>"Yes, that's me"</strong> to officially record attendance</li>
              <li>✓ Tap <strong>"Not me"</strong> to cancel and scan again</li>
            </ul>
          </div>
        </div>
      </Card>
    </>
  );
};
