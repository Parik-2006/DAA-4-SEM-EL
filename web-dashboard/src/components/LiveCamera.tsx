import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  Play, StopCircle, Loader, AlertCircle, Camera,
  Check, X, ShieldCheck, User, RefreshCw, AlertTriangle,
} from 'lucide-react';
import { attendanceAPI, DetectFaceResponse, ConfirmAttendanceResponse, AttendanceWindowInfo, CandidateSuggestion } from '@/services/api';
import { Card } from './UI';

// ── Constants ──────────────────────────────────────────────────────────────────
const MAX_CONSECUTIVE_FAILURES = 5;

// ── Types ──────────────────────────────────────────────────────────────────────
interface LiveCameraProps {
  onAttendanceMarked: (data: any) => void;
  onProcessing: (isProcessing: boolean) => void;
  isLoading: boolean;
  /** Called whenever the consecutive failure count changes — lets the parent
   *  page react (e.g. update a sidebar status card) without prop-drilling. */
  onConsecutiveFailures?: (count: number) => void;
  /** When true, the component will start the camera automatically on mount */
  autoStart?: boolean;
  /** Optional student id to hint the detection flow (passed as query param) */
  targetStudentId?: string | null;
  /** Optional timetable period id to scope detection/confirmation */
  periodId?: string | null;
}

// ── Confirmation Modal ─────────────────────────────────────────────────────────

interface ConfirmationModalProps {
  detection: DetectFaceResponse;
  onConfirm: () => void;
  onDeny: () => void;
  isSaving: boolean;
}

interface CandidatePromptModalProps {
  suggestions: CandidateSuggestion[];
  onSelect: (candidate: CandidateSuggestion) => void;
  onDismiss: () => void;
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(30,20,10,0.55)', backdropFilter: 'blur(4px)' }}
    >
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
            Are you {detection.student_name}?
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
              No, not me
            </button>

            {/* Yes */}
            <button
              onClick={onConfirm}
              disabled={isSaving}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95 shadow-md"
              style={{
                padding: '12px 0',
                background: isSaving ? '#a0856a' : 'linear-gradient(135deg, #b8864e, #c8a97e)',
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
                  Yes, it's me
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

      <style>{`
        @keyframes modalIn {
          from { opacity: 0; transform: scale(0.88) translateY(16px); }
          to   { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  );
};

const CandidatePromptModal: React.FC<CandidatePromptModalProps> = ({
  suggestions,
  onSelect,
  onDismiss,
  isSaving,
}) => (
  <div
    className="fixed inset-0 z-50 flex items-center justify-center p-4"
    style={{ backgroundColor: 'rgba(18,24,38,0.62)', backdropFilter: 'blur(5px)' }}
  >
    <div
      className="relative w-full max-w-md rounded-2xl shadow-2xl overflow-hidden"
      style={{
        background: 'linear-gradient(160deg, #ffffff 0%, #f8fbff 60%, #eff6ff 100%)',
        border: '1.5px solid #bfdbfe',
      }}
    >
      <div style={{ height: 4, background: 'linear-gradient(90deg, #2563eb, #60a5fa, #2563eb)' }} />
      <div className="p-6">
        <h2 className="text-center font-bold mb-2" style={{ fontSize: 20, color: '#12315a' }}>
          Who is this?
        </h2>
        <p className="text-center mb-4" style={{ color: '#334155', fontSize: 14 }}>
          I found a few likely matches. Pick the correct person to mark attendance.
        </p>
        <div className="flex flex-col gap-3">
          {suggestions.map((candidate) => {
            const pct = Math.round(candidate.confidence * 100);
            return (
              <button
                key={candidate.student_id}
                disabled={isSaving}
                onClick={() => onSelect(candidate)}
                className="rounded-xl px-4 py-3 text-left transition-all active:scale-[0.99]"
                style={{
                  background: '#ffffff',
                  border: '1px solid #dbeafe',
                  boxShadow: '0 6px 18px rgba(37,99,235,0.06)',
                  cursor: isSaving ? 'not-allowed' : 'pointer',
                  opacity: isSaving ? 0.7 : 1,
                }}
              >
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p style={{ fontWeight: 700, color: '#0f172a' }}>{candidate.student_name}</p>
                    <p style={{ fontSize: 12, color: '#64748b' }}>ID: {candidate.student_id}</p>
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#2563eb' }}>{pct}%</div>
                </div>
              </button>
            );
          })}
        </div>
        <div className="mt-4 flex gap-3">
          <button
            onClick={onDismiss}
            className="flex-1 rounded-xl py-3 font-semibold"
            style={{ background: '#e2e8f0', color: '#334155', border: 'none' }}
          >
            None of these
          </button>
        </div>
      </div>
    </div>
  </div>
);

// ── Hard Stop Modal ────────────────────────────────────────────────────────────

interface HardStopModalProps {
  failureCount: number;
  lastMessage: string;
  onReset: () => void;
}

const HardStopModal: React.FC<HardStopModalProps> = ({ failureCount, lastMessage, onReset }) => (
  <div
    className="fixed inset-0 z-50 flex items-center justify-center p-4"
    style={{ backgroundColor: 'rgba(30,10,10,0.65)', backdropFilter: 'blur(6px)' }}
  >
    <div
      className="relative w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden"
      style={{
        background: 'linear-gradient(160deg, #fff8f6 0%, #fef2ee 60%, #fff5f2 100%)',
        border: '1.5px solid #fecaca',
        animation: 'modalIn 0.32s cubic-bezier(0.34,1.56,0.64,1)',
      }}
    >
      {/* Top danger stripe */}
      <div style={{ height: 4, background: 'linear-gradient(90deg, #ef4444, #f87171, #ef4444)' }} />

      <div className="p-7">
        {/* Icon */}
        <div className="flex justify-center mb-5">
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center shadow-md"
            style={{ background: 'linear-gradient(135deg, #fee2e2, #fecaca)' }}
          >
            <AlertTriangle size={36} style={{ color: '#dc2626' }} />
          </div>
        </div>

        <h2
          className="text-center font-bold mb-2"
          style={{ fontSize: 20, color: '#7f1d1d', letterSpacing: '-0.3px' }}
        >
          Face Not Detected
        </h2>

        <p className="text-center mb-3" style={{ color: '#b91c1c', fontSize: 14, lineHeight: 1.5 }}>
          Sorry, we couldn't detect your face after{' '}
          <strong>{failureCount} consecutive attempts</strong>. Please check the
          tips below and try again.
        </p>

        {/* Last error detail */}
        {lastMessage && (
          <div
            className="rounded-xl p-3 mb-4"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #fca5a5' }}
          >
            <p style={{ fontSize: 12, color: '#b91c1c', textAlign: 'center' }}>{lastMessage}</p>
          </div>
        )}

        {/* Tips */}
        <div
          className="rounded-xl p-4 mb-5"
          style={{ background: 'rgba(239,68,68,0.05)', border: '1px solid #fecaca' }}
        >
          <p
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: '#991b1b',
              marginBottom: 8,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
            }}
          >
            Tips to improve detection
          </p>
          <ul
            style={{
              fontSize: 12,
              color: '#b91c1c',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
              listStyle: 'none',
              padding: 0,
              margin: 0,
            }}
          >
            <li>✓ Move to a well-lit area facing a light source</li>
            <li>✓ Remove glasses, hats, or face coverings if possible</li>
            <li>✓ Centre your face fully in the camera frame</li>
            <li>✓ Avoid strong backlighting (e.g. window behind you)</li>
            <li>✓ Hold still during each scan (~2.5 s)</li>
          </ul>
        </div>

        {/* Retry action */}
        <button
          onClick={onReset}
          className="w-full flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95 shadow-md"
          style={{
            padding: '13px 0',
            background: 'linear-gradient(135deg, #ef4444, #dc2626)',
            border: 'none',
            color: '#fff',
            fontSize: 15,
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={17} />
          Try Again
        </button>
      </div>

      <style>{`
        @keyframes modalIn {
          from { opacity: 0; transform: scale(0.88) translateY(16px); }
          to   { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  </div>
);

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

// ── Failure dot indicator ──────────────────────────────────────────────────────
// `dark` = true when rendered on the dark camera overlay (white inactive dots);
// false = rendered on white/light backgrounds (grey inactive dots).

const FailureDots: React.FC<{ count: number; max: number; dark?: boolean }> = ({
  count,
  max,
  dark = false,
}) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
    {Array.from({ length: max }).map((_, i) => (
      <div
        key={i}
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: i < count
            ? '#ef4444'
            : dark ? 'rgba(255,255,255,0.35)' : '#e2e8f0',
          transition: 'background 0.3s ease',
          boxShadow: i < count ? '0 0 0 2px rgba(239,68,68,0.40)' : 'none',
        }}
      />
    ))}
    <span
      style={{
        fontSize: 11,
        color: dark ? '#fff' : '#b91c1c',
        marginLeft: 4,
        fontWeight: 600,
        opacity: dark ? 0.85 : 1,
      }}
    >
      {count}/{max}
    </span>
  </div>
);

// ── Main LiveCamera component ──────────────────────────────────────────────────

export const LiveCamera: React.FC<LiveCameraProps> = ({
  onAttendanceMarked,
  onProcessing,
  isLoading,
  onConsecutiveFailures,
  autoStart,
  targetStudentId,
  periodId,
}) => {
  const videoRef    = useRef<HTMLVideoElement>(null);
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const streamRef   = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const processingRef       = useRef(false);
  const pausedForConfirmRef = useRef(false);

  // Ref keeps the setInterval closure in sync with the current count;
  // the mirrored state drives the UI.
  const consecutiveFailuresRef = useRef(0);

  const [cameraState, setCameraState]         = useState<'idle' | 'requesting' | 'active' | 'error'>('idle');
  const [cameraError, setCameraError]         = useState<string | null>(null);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [availableCameras, setAvailableCameras] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [frameCount, setFrameCount]           = useState(0);

  // Inline status banner
  const [lastFeedback, setLastFeedback] = useState<string | null>(null);
  const [feedbackType, setFeedbackType] = useState<'info' | 'warn' | 'error'>('info');

  // Failure / hard-stop state
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);
  const [showHardStop, setShowHardStop]   = useState(false);
  const [hardStopMessage, setHardStopMessage] = useState('');

  // Confirmation modal
  const [pendingDetection, setPendingDetection] = useState<DetectFaceResponse | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Success flash
  const [successName, setSuccessName] = useState<string | null>(null);
  const [candidateCount, setCandidateCount] = useState<number | null>(null);
  const [candidateIds, setCandidateIds] = useState<string[] | null>(null);
  const [candidateSuggestions, setCandidateSuggestions] = useState<CandidateSuggestion[] | null>(null);
  const [rejectedCandidateIds, setRejectedCandidateIds] = useState<string[]>([]);
  const [windowInfo, setWindowInfo] = useState<AttendanceWindowInfo | null>(null);

  // ── Keep ref in sync; notify parent ───────────────────────────────────────

  useEffect(() => {
    consecutiveFailuresRef.current = consecutiveFailures;
    onConsecutiveFailures?.(consecutiveFailures);
  }, [consecutiveFailures, onConsecutiveFailures]);

  // ── Cleanup on unmount ────────────────────────────────────────────────────

  useEffect(() => () => stopCamera(), []);

  useEffect(() => {
    let alive = true;

    const loadCandidateScope = async () => {
      const info = await attendanceAPI.getAttendanceCandidates(periodId ?? undefined);
      if (!alive) return;
      setCandidateCount(info?.count ?? null);
      setCandidateIds(info?.candidate_student_ids ?? null);
    };

    void loadCandidateScope();

    return () => {
      alive = false;
    };
  }, [periodId]);

  // ── Stop camera ───────────────────────────────────────────────────────────

  const stopCamera = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    processingRef.current = false;
    pausedForConfirmRef.current = false;
    setCameraState('idle');
    setFrameCount(0);
    setLastFeedback(null);
    setWindowInfo(null);
    // Preserved from existing: always zero the streak on camera stop so a
    // manual stop doesn't carry stale failures into the next session.
    consecutiveFailuresRef.current = 0;
  }, []);

  // ── Reset after hard stop — user explicitly retries ───────────────────────

  const resetForRetry = useCallback(() => {
    consecutiveFailuresRef.current = 0;
    setConsecutiveFailures(0);
    setShowHardStop(false);
    setHardStopMessage('');
    setLastFeedback(null);
    // Stop the camera so the user deliberately presses Start Camera again,
    // giving a moment to adjust lighting / position before retrying.
    stopCamera();
  }, [stopCamera]);

  // ── Record one failure; trigger hard stop when threshold is reached ───────

  const recordFailure = useCallback(
    (message: string) => {
      const next = consecutiveFailuresRef.current + 1;
      consecutiveFailuresRef.current = next;
      setConsecutiveFailures(next);

      if (next >= MAX_CONSECUTIVE_FAILURES) {
        setHardStopMessage(message);
        setShowHardStop(true);
        stopCamera();
      }
    },
    [stopCamera],
  );

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
      const videoConstraints: any = selectedDeviceId
        ? { deviceId: { exact: selectedDeviceId } }
        : { facingMode: 'user', width: { ideal: 1280, min: 640 }, height: { ideal: 720, min: 480 } };

      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: videoConstraints,
        audio: false,
      });
      streamRef.current = mediaStream;

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await new Promise<void>(res => {
          const v = videoRef.current!;
          v.onloadedmetadata = () => res();
          setTimeout(res, 3000);
        });
        await videoRef.current.play().catch(() => {});
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
        // Try to enumerate devices to offer an explicit choice
        try { await enumerateCameras(); } catch (_) {}
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

  const enumerateCameras = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return [];
    try {
      const list = await navigator.mediaDevices.enumerateDevices();
      const cams = list.filter(d => d.kind === 'videoinput');
      setAvailableCameras(cams);
      if (cams.length === 1) setSelectedDeviceId(cams[0].deviceId);
      return cams;
    } catch (e) {
      console.error('enumerateDevices failed', e);
      return [];
    }
  };

  // Auto-start camera when requested by parent (e.g. student clicked Live Camera)
  useEffect(() => {
    if (autoStart) {
      // small delay so the page layout settles before requesting permission
      const t = setTimeout(() => { void startCamera(); }, 220);
      return () => clearTimeout(t);
    }
    // no-op when not requested
    return;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [/* intentionally empty */]);

  // ── Frame capture ──────────────────────────────────────────────────────────

  const captureFrame = (): Promise<Blob | null> =>
    new Promise(resolve => {
      const video  = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.videoWidth === 0) { resolve(null); return; }
      canvas.width  = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) { resolve(null); return; }
      ctx.drawImage(video, 0, 0);
      canvas.toBlob(resolve, 'image/jpeg', 0.85);
    });

  // ── Detection loop ─────────────────────────────────────────────────────────

  const startDetectionLoop = () => {
    intervalRef.current = setInterval(async () => {
      // Pause while confirmation dialog is open or another frame is in-flight
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

        // Step 1: identify only — does NOT write to the DB
        const result: DetectFaceResponse = await attendanceAPI.detectFaceOnly(
          formData,
          targetStudentId
            ? {
                scope_mode: 'self_verify',
                student_id: targetStudentId,
                period_id: periodId ?? undefined,
                candidate_student_ids: candidateIds ?? undefined,
                exclude_student_ids: rejectedCandidateIds.length > 0 ? rejectedCandidateIds : undefined,
              }
            : {
                scope_mode: 'section_roster',
                period_id: periodId ?? undefined,
                candidate_student_ids: candidateIds ?? undefined,
                exclude_student_ids: rejectedCandidateIds.length > 0 ? rejectedCandidateIds : undefined,
              },
        );
        if (result.window) {
          setWindowInfo(result.window);
        }

        setCandidateSuggestions(result.suggested_candidates ?? null);

        if (result.matched) {
          // ── SUCCESS: reset counter, pause loop, show confirmation ──────
          consecutiveFailuresRef.current = 0;
          setConsecutiveFailures(0);
          pausedForConfirmRef.current = true;
          setLastFeedback(null);
          setPendingDetection(result);
          setCandidateSuggestions(null);
        } else {
          // ── FAILURE: classify message, update feedback ─────────────────
          const msg = result.message || 'No matching face found.';
          const isNoFace    = msg.toLowerCase().includes('no face') || msg.toLowerCase().includes('not detected');
          const isNoEmb     = msg.toLowerCase().includes('not registered') || msg.toLowerCase().includes('no face profile');
          const isServerErr = msg.toLowerCase().includes('server error') || msg.toLowerCase().includes('model not loaded');

          if (isServerErr) {
            setFeedbackType('error');
            setLastFeedback(`⚠️ ${msg}`);
          } else if (isNoEmb) {
            setFeedbackType('error');
            setLastFeedback('❌ No face profile registered. Ask admin to register your face.');
          } else if (isNoFace) {
            setFeedbackType('info');
            // Only show the "centre your face" hint while retries remain
            const preview = consecutiveFailuresRef.current + 1;
            if (preview < MAX_CONSECUTIVE_FAILURES) {
              setLastFeedback('👁 Centre your face in the frame…');
            }
          } else {
            setFeedbackType('warn');
            setLastFeedback(`🔍 ${msg}`);
          }

          if (result.window?.is_locked || result.window?.phase === 'locked') {
            setLastFeedback(result.window.message ?? 'Attendance window is locked.');
            stopCamera();
            return;
          }

          if (result.suggested_candidates?.length) {
            setCandidateSuggestions(result.suggested_candidates);
            pausedForConfirmRef.current = true;
            setLastFeedback('🤔 Not certain. Please pick who this is.');
            return;
          }

          // All failure subtypes count toward the hard-stop threshold
          recordFailure(msg);
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Unexpected camera error.';
        setFeedbackType('error');
        setLastFeedback(`❌ ${message}`);
        recordFailure(message);
      } finally {
        processingRef.current = false;
        onProcessing(false);
      }
    }, 2500);
  };

  // ── Confirmation: user says "Yes, it's me" ────────────────────────────────

  const handleConfirm = async () => {
    if (!pendingDetection) return;
    setIsSaving(true);
      try {
      const learningFrame = await captureFrame();

      // Step 2: persist to database
      const confirmation: ConfirmAttendanceResponse =
        await attendanceAPI.confirmAttendance(
          pendingDetection.student_id!,
          pendingDetection.confidence ?? 0,
          periodId ?? undefined,
          learningFrame ?? undefined,
        );

      setPendingDetection(null);
      setSuccessName(confirmation.student_name);

      // Full reset on confirmed success
      consecutiveFailuresRef.current = 0;
      setConsecutiveFailures(0);

      onAttendanceMarked({
        status:       'success',
        message:      confirmation.message,
        student_name: confirmation.student_name,
        student_id:   confirmation.student_id,
        confidence:   confirmation.confidence,
        record_id:    confirmation.record_id,
      });

      stopCamera();
      setTimeout(() => setSuccessName(null), 2400);
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail ?? err?.message ?? 'Failed to save attendance.';
      // 423 Locked — attendance window closed or not allowed
      if (status === 423) {
        setPendingDetection(null);
        pausedForConfirmRef.current = false;
        setFeedbackType('error');
        setLastFeedback(`⛔ Attendance window closed: ${detail}`);
        stopCamera();
      } else {
        const msg = detail;
        setPendingDetection(null);
        pausedForConfirmRef.current = false;
        setFeedbackType('error');
        setLastFeedback(`❌ Save failed: ${msg}`);
      }
    } finally {
      setIsSaving(false);
    }
  };

  // ── Confirmation: user says "No, not me" ──────────────────────────────────

  const handleDeny = (studentIdToBlock?: string, extraBlocks?: string[]) => {
    const blocked = [studentIdToBlock, ...(extraBlocks ?? [])].filter(Boolean) as string[];
    if (blocked.length > 0) {
      setRejectedCandidateIds((prev) => Array.from(new Set([...prev, ...blocked])));
    }
    setPendingDetection(null);
    setCandidateSuggestions(null);
    pausedForConfirmRef.current = false;
    setFeedbackType('info');
    setLastFeedback('🔄 Scanning resumed — please look at the camera.');
    // Preserved from existing: denying a confirmed match is NOT a detection
    // failure — the system found the right person. Reset rather than increment.
    consecutiveFailuresRef.current = 0;
    setConsecutiveFailures(0);
  };

  const handleCandidateSelect = async (candidate: CandidateSuggestion) => {
    if (!candidate) return;
    setIsSaving(true);
    try {
      const confirmation = await attendanceAPI.confirmAttendance(
        candidate.student_id,
        candidate.confidence,
        periodId ?? undefined,
        await captureFrame() ?? undefined,
      );

      setCandidateSuggestions(null);
      setSuccessName(confirmation.student_name);
      consecutiveFailuresRef.current = 0;
      setConsecutiveFailures(0);

      onAttendanceMarked({
        status: 'success',
        message: confirmation.message,
        student_name: confirmation.student_name,
        student_id: confirmation.student_id,
        confidence: confirmation.confidence,
        record_id: confirmation.record_id,
      });

      stopCamera();
      setTimeout(() => setSuccessName(null), 2400);
    } finally {
      setIsSaving(false);
    }
  };

  // ── Derived render flags ───────────────────────────────────────────────────

  const isActive     = cameraState === 'active';
  const isRequesting = cameraState === 'requesting';
  // nearLimit: failures are accumulating but hard stop has not yet fired
  const nearLimit    = consecutiveFailures > 0 && consecutiveFailures < MAX_CONSECUTIVE_FAILURES;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
      {/* ── Modals — rendered above the card ─────────────────────────────── */}
      {pendingDetection && (
        <ConfirmationModal
          detection={pendingDetection}
          onConfirm={handleConfirm}
          onDeny={() => handleDeny(pendingDetection.student_id)}
          isSaving={isSaving}
        />
      )}

      {!pendingDetection && candidateSuggestions && candidateSuggestions.length > 0 && (
        <CandidatePromptModal
          suggestions={candidateSuggestions}
          onSelect={handleCandidateSelect}
          onDismiss={() => handleDeny(undefined, candidateSuggestions.map((c) => c.student_id))}
          isSaving={isSaving}
        />
      )}

      {showHardStop && (
        <HardStopModal
          failureCount={MAX_CONSECUTIVE_FAILURES}
          lastMessage={hardStopMessage}
          onReset={resetForRetry}
        />
      )}

      {successName && <SuccessFlash name={successName} />}

      <Card>
        <div className="space-y-4">

          {/* ── Camera viewport ───────────────────────────────────────────── */}
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

            {/* Idle / requesting placeholder */}
            {!isActive && (
              <div
                className="absolute inset-0 flex flex-col items-center justify-center gap-4"
                style={{ color: '#7a5c3e' }}
              >
                <div
                  className="w-20 h-20 rounded-full flex items-center justify-center"
                  style={{ background: 'rgba(200,169,126,0.15)' }}
                >
                  <Camera size={36} style={{ color: '#c8a97e' }} />
                </div>
                <p className="text-sm font-medium" style={{ color: '#9a7a5a' }}>
                  {isRequesting ? 'Requesting camera access…' : 'Camera is off'}
                </p>
              </div>
            )}

            {/* Processing overlay */}
            {isLoading && isActive && (
              <div
                className="absolute inset-0 flex items-center justify-center"
                style={{ background: 'rgba(0,0,0,0.38)' }}
              >
                <div className="flex flex-col items-center gap-2">
                  <Loader className="animate-spin text-amber-300" size={32} />
                  <p className="text-white text-sm font-medium">Detecting face…</p>
                </div>
              </div>
            )}

            {/* Paused-for-confirm overlay */}
            {pendingDetection && isActive && (
              <div
                className="absolute inset-0 flex items-center justify-center"
                style={{ background: 'rgba(0,0,0,0.55)' }}
              >
                <p className="text-white text-sm font-semibold tracking-wide">
                  ⏸ Paused — awaiting confirmation
                </p>
              </div>
            )}

            {/* LIVE badge */}
            {isActive && !pendingDetection && (
              <div
                className="absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold shadow"
                style={{ background: '#dc2626', color: '#fff' }}
              >
                <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
                LIVE
              </div>
            )}

            {/* Frame counter */}
            {isActive && frameCount > 0 && (
              <div
                className="absolute bottom-3 left-3 rounded px-2 py-1 text-xs"
                style={{ background: 'rgba(0,0,0,0.5)', color: '#e8d5b8' }}
              >
                {frameCount} frames scanned
              </div>
            )}

            {/* Failure dot progress — camera overlay, shown only when near limit */}
            {isActive && nearLimit && (
              <div
                className="absolute bottom-3 right-3 rounded-lg px-3 py-1.5"
                style={{ background: 'rgba(220,38,38,0.80)', backdropFilter: 'blur(4px)' }}
              >
                <FailureDots count={consecutiveFailures} max={MAX_CONSECUTIVE_FAILURES} dark />
              </div>
            )}
          </div>

          {/* ── Warning strip — shown while failures accumulate ────────────── */}
          {nearLimit && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 14px',
                borderRadius: 12,
                background: 'rgba(239,68,68,0.08)',
                border: '1px solid rgba(239,68,68,0.30)',
                animation: 'fadeSlideIn 0.25s ease',
              }}
            >
              <AlertTriangle size={15} style={{ color: '#dc2626', flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 13, fontWeight: 700, color: '#b91c1c' }}>
                  {MAX_CONSECUTIVE_FAILURES - consecutiveFailures} attempt
                  {MAX_CONSECUTIVE_FAILURES - consecutiveFailures !== 1 ? 's' : ''} remaining
                </p>
                <p style={{ fontSize: 11, color: '#dc2626', marginTop: 1 }}>
                  Ensure your face is well-lit and centred in the frame.
                </p>
              </div>
              <FailureDots count={consecutiveFailures} max={MAX_CONSECUTIVE_FAILURES} />
            </div>
          )}

          {/* ── Inline feedback banner ────────────────────────────────────── */}
          {/* Preserved from existing: shown whenever active + feedback exists,
              but hidden during confirmation dialog or the warning strip so the
              UI doesn't double-up on red messages. */}
          {isActive && (lastFeedback || windowInfo?.message) && !pendingDetection && !nearLimit && (
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium"
              style={{
                background:
                  feedbackType === 'error' ? 'rgba(239,68,68,0.09)'
                    : feedbackType === 'warn' ? 'rgba(251,191,36,0.09)'
                      : 'rgba(200,169,126,0.12)',
                border: `1px solid ${
                  feedbackType === 'error' ? '#fca5a5'
                    : feedbackType === 'warn' ? '#fde68a'
                      : '#d4b896'
                }`,
                color:
                  feedbackType === 'error' ? '#b91c1c'
                    : feedbackType === 'warn' ? '#92400e'
                      : '#7a5c3e',
              }}
            >
              <span className="flex-1">{lastFeedback ?? windowInfo?.message}</span>
              {frameCount > 0 && (
                <span className="text-xs opacity-50 ml-2 flex-shrink-0">
                  frame {frameCount}
                </span>
              )}
            </div>
          )}

          {candidateCount !== null && (
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-500 shadow-sm">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              Candidate pool: {candidateCount}
            </div>
          )}

          {/* ── Camera permission / hardware error ───────────────────────── */}
          {cameraError && (
            <div
              className="flex items-start gap-3 rounded-lg p-4"
              style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid #fca5a5' }}
            >
              <AlertCircle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800">Camera Error</p>
                <p className="text-sm text-red-700 mt-0.5">{cameraError}</p>
                {permissionDenied && (
                  <p className="text-xs text-red-600 mt-2">
                    💡 In Chrome: click the camera icon in the address bar → Allow. Then refresh.
                  </p>
                )}
                {/* Camera device diagnostics and selection */}
                <div style={{ marginTop: 10 }}>
                  {availableCameras.length > 0 ? (
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6 }}>
                      <select
                        value={selectedDeviceId ?? ''}
                        onChange={(e) => setSelectedDeviceId(e.target.value || null)}
                        className="rounded px-2 py-1"
                      >
                        <option value="">Default camera</option>
                        {availableCameras.map(c => (
                          <option key={c.deviceId} value={c.deviceId}>{c.label || c.deviceId}</option>
                        ))}
                      </select>
                      <button
                        onClick={async () => { setCameraError(null); await startCamera(); }}
                        className="rounded px-3 py-1 bg-amber-500 text-white"
                      >Use selected</button>
                    </div>
                  ) : (
                    <div style={{ marginTop: 8 }}>
                      <button
                        onClick={async () => { await enumerateCameras(); }}
                        className="rounded px-3 py-1 bg-slate-200 text-slate-800"
                      >Detect cameras</button>
                      <p className="text-xs text-red-600 mt-2">If no cameras are detected, ensure hardware is connected and not blocked by another app.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── Controls ─────────────────────────────────────────────────── */}
          <div className="flex gap-3">
            {!isActive ? (
              <button
                onClick={startCamera}
                disabled={isRequesting || isLoading}
                className="flex-1 flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95"
                style={{
                  padding: '12px 0',
                  background:
                    isRequesting || isLoading
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

          {/* ── Info box ─────────────────────────────────────────────────── */}
          <div
            className="rounded-lg p-4 text-sm"
            style={{ background: 'rgba(200,169,126,0.1)', border: '1px solid #d4b896', color: '#7a5c3e' }}
          >
            <p className="font-semibold mb-1" style={{ color: '#5a3e28' }}>
              How two-step check-in works
            </p>
            <ul className="space-y-1 text-xs">
              <li>✓ Click <strong>Start Camera</strong> and allow browser permission</li>
              <li>✓ Position your face clearly — scanned every ~2.5 s</li>
              <li>✓ When your face is recognised, a confirmation dialog appears</li>
              <li>✓ Tap <strong>"Yes, it's me"</strong> to officially record attendance</li>
              <li>✓ Tap <strong>"No, not me"</strong> to cancel and scan again</li>
              <li style={{ color: '#b91c1c' }}>
                ⚠ Scanning stops automatically after {MAX_CONSECUTIVE_FAILURES} failed
                consecutive attempts
              </li>
            </ul>
          </div>
        </div>

        <style>{`
          @keyframes fadeSlideIn {
            from { opacity: 0; transform: translateY(-6px); }
            to   { opacity: 1; transform: none; }
          }
        `}</style>
      </Card>
    </>
  );
};

export default LiveCamera;