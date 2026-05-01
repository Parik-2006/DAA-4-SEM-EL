import React, { useState, useRef } from 'react';
import { Upload, Loader, X, ShieldCheck, User, Check } from 'lucide-react';
import { attendanceAPI, DetectFaceResponse, ConfirmAttendanceResponse } from '@/services/api';
import { Card } from './UI';

interface UploadPhotoProps {
  onAttendanceMarked: (data: any) => void;
  onProcessing: (isProcessing: boolean) => void;
  isLoading: boolean;
}

// ── Confirmation Modal (reused cream aesthetic) ────────────────────────────────

interface ConfirmationModalProps {
  detection: DetectFaceResponse;
  previewSrc: string | null;
  onConfirm: () => void;
  onDeny: () => void;
  isSaving: boolean;
}

const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  detection,
  previewSrc,
  onConfirm,
  onDeny,
  isSaving,
}) => {
  const confidencePct = Math.round((detection.confidence ?? 0) * 100);
  const barColor =
    confidencePct >= 85 ? '#4ade80' : confidencePct >= 70 ? '#fbbf24' : '#f87171';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(30,20,10,0.55)', backdropFilter: 'blur(4px)' }}
    >
      <div
        className="relative w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden"
        style={{
          background: 'linear-gradient(160deg, #fdf6ee 0%, #fef9f3 60%, #fff8f0 100%)',
          border: '1.5px solid #e8d9c4',
          animation: 'modalIn 0.28s cubic-bezier(0.34,1.56,0.64,1)',
        }}
      >
        {/* Top accent */}
        <div style={{ height: 4, background: 'linear-gradient(90deg, #c8a97e, #e2c49a, #c8a97e)' }} />

        <div className="p-7">
          {/* Photo preview or avatar */}
          <div className="flex justify-center mb-5">
            <div className="relative">
              {previewSrc ? (
                <img
                  src={previewSrc}
                  alt="Uploaded"
                  className="w-20 h-20 rounded-full object-cover shadow-md"
                  style={{ border: '3px solid #d4b896' }}
                />
              ) : (
                <div
                  className="w-20 h-20 rounded-full flex items-center justify-center shadow-md"
                  style={{ background: 'linear-gradient(135deg, #e8d5b8, #f5e6d0)' }}
                >
                  <User size={36} style={{ color: '#8b6840' }} />
                </div>
              )}
              <div
                className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full flex items-center justify-center shadow"
                style={{ background: '#4ade80' }}
              >
                <Check size={14} color="white" strokeWidth={3} />
              </div>
            </div>
          </div>

          <h2
            className="text-center font-bold mb-1"
            style={{ fontSize: 20, color: '#3d2b1a', letterSpacing: '-0.3px' }}
          >
            Face Identified
          </h2>
          <p className="text-center mb-5" style={{ color: '#7a5c3e', fontSize: 14 }}>
            Please confirm this is you before marking attendance.
          </p>

          {/* Student info */}
          <div
            className="rounded-xl p-4 mb-5"
            style={{ background: 'rgba(200,169,126,0.13)', border: '1px solid #d4b896' }}
          >
            <p className="text-center font-bold mb-0.5" style={{ fontSize: 22, color: '#2d1f0f' }}>
              {detection.student_name}
            </p>
            <p className="text-center text-sm mb-3" style={{ color: '#7a5c3e' }}>
              ID: {detection.student_id}
            </p>

            {/* Confidence */}
            <div>
              <div className="flex justify-between mb-1" style={{ fontSize: 11, color: '#9a7a5a' }}>
                <span>Match confidence</span>
                <span style={{ fontWeight: 700, color: barColor }}>{confidencePct}%</span>
              </div>
              <div className="rounded-full overflow-hidden" style={{ height: 6, background: '#e8d5b8' }}>
                <div
                  className="h-full rounded-full"
                  style={{ width: `${confidencePct}%`, background: `linear-gradient(90deg, ${barColor}99, ${barColor})` }}
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
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
                <><Loader size={16} className="animate-spin" />Saving…</>
              ) : (
                <><ShieldCheck size={17} />Yes, that's me</>
              )}
            </button>
          </div>
        </div>

        <p className="text-center pb-4 px-6" style={{ fontSize: 11, color: '#b89a7a' }}>
          If this isn't you, tap "Not me" to cancel — no record will be saved.
        </p>
      </div>

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
    style={{ animation: 'fadeOutFlash 2.2s ease forwards' }}
  >
    <div
      className="rounded-2xl px-10 py-8 shadow-2xl flex flex-col items-center gap-3"
      style={{
        background: 'linear-gradient(135deg, #fdf6ee, #fff8f0)',
        border: '1.5px solid #c8a97e',
        animation: 'popInFlash 0.35s cubic-bezier(0.34,1.56,0.64,1)',
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
      @keyframes popInFlash {
        from { opacity: 0; transform: scale(0.7); }
        to   { opacity: 1; transform: scale(1); }
      }
      @keyframes fadeOutFlash {
        0%,60% { opacity: 1; }
        100%    { opacity: 0; }
      }
    `}</style>
  </div>
);

// ── Main UploadPhoto component ─────────────────────────────────────────────────

export const UploadPhoto: React.FC<UploadPhotoProps> = ({
  onAttendanceMarked,
  onProcessing,
  isLoading,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Step 1 result — awaiting user confirmation
  const [pendingDetection, setPendingDetection] = useState<DetectFaceResponse | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Success flash
  const [successName, setSuccessName] = useState<string | null>(null);

  // ── File selection ─────────────────────────────────────────────────────────

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!['image/jpeg', 'image/jpg', 'image/png'].includes(file.type)) {
      setError('Please select a JPG or PNG image.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10 MB.');
      return;
    }

    setSelectedFile(file);
    setError(null);
    setPendingDetection(null);

    const reader = new FileReader();
    reader.onload = (ev) => setPreview(ev.target?.result as string);
    reader.readAsDataURL(file);
  };

  const clearSelection = () => {
    setSelectedFile(null);
    setPreview(null);
    setError(null);
    setPendingDetection(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Step 1: detect face only ───────────────────────────────────────────────

  const handleDetect = async () => {
    if (!selectedFile) { setError('Please select a photo first.'); return; }

    setError(null);
    onProcessing(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      // Step 1 — identify, no DB write
      const result: DetectFaceResponse = await attendanceAPI.detectFaceOnly(formData);

      if (result.matched) {
        // Show confirmation modal
        setPendingDetection(result);
      } else {
        setError(result.message || 'No matching face found. Please try a different photo.');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to process image.';
      setError(msg);
    } finally {
      onProcessing(false);
    }
  };

  // ── Step 2: user confirmed ─────────────────────────────────────────────────

  const handleConfirm = async () => {
    if (!pendingDetection) return;
    setIsSaving(true);
    try {
      const confirmation: ConfirmAttendanceResponse = await attendanceAPI.confirmAttendance(
        pendingDetection.student_id!,
        pendingDetection.confidence ?? 0
      );

      setPendingDetection(null);
      setSuccessName(confirmation.student_name);

      onAttendanceMarked({
        status: 'success',
        message: confirmation.message,
        student_name: confirmation.student_name,
        student_id: confirmation.student_id,
        confidence: confirmation.confidence,
        record_id: confirmation.record_id,
      });

      // Clear selection after short delay
      setTimeout(() => {
        clearSelection();
        setSuccessName(null);
      }, 2400);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Failed to save attendance.';
      setPendingDetection(null);
      setError(`Save failed: ${msg}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeny = () => {
    // User says it's not them — dismiss, no record written
    setPendingDetection(null);
    setError('Identification cancelled. Please try with a different photo or contact admin.');
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
      {pendingDetection && (
        <ConfirmationModal
          detection={pendingDetection}
          previewSrc={preview}
          onConfirm={handleConfirm}
          onDeny={handleDeny}
          isSaving={isSaving}
        />
      )}

      {successName && <SuccessFlash name={successName} />}

      <Card>
        <div className="space-y-4">

          {/* Drop zone */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="rounded-xl p-8 text-center cursor-pointer transition-all"
            style={{
              border: '2px dashed #c8a97e',
              background: preview ? 'transparent' : 'rgba(200,169,126,0.06)',
            }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files?.[0];
              if (file) {
                const synth = { target: { files: [file] } } as any;
                handleFileSelect(synth);
              }
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png"
              onChange={handleFileSelect}
              className="hidden"
            />

            {preview ? (
              <div className="flex flex-col items-center gap-2">
                <img
                  src={preview}
                  alt="Preview"
                  className="max-h-56 rounded-xl object-contain shadow-md"
                  style={{ border: '1.5px solid #d4b896' }}
                />
                <p className="text-sm font-medium" style={{ color: '#7a5c3e' }}>
                  {selectedFile?.name}
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div
                  className="w-16 h-16 rounded-full flex items-center justify-center"
                  style={{ background: 'rgba(200,169,126,0.15)' }}
                >
                  <Upload size={28} style={{ color: '#c8a97e' }} />
                </div>
                <div>
                  <p className="font-semibold" style={{ color: '#5a3e28' }}>
                    Click to upload or drag & drop
                  </p>
                  <p className="text-sm mt-1" style={{ color: '#9a7a5a' }}>
                    JPG or PNG — max 10 MB
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div
              className="flex items-start gap-2 rounded-lg p-3 text-sm"
              style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid #fca5a5', color: '#b91c1c' }}
            >
              <X size={16} className="flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            {selectedFile ? (
              <>
                {/* Detect button (Step 1) */}
                <button
                  onClick={handleDetect}
                  disabled={isLoading}
                  className="flex-1 flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95 shadow-md"
                  style={{
                    padding: '12px 0',
                    background: isLoading ? '#a0856a' : 'linear-gradient(135deg, #b8864e, #c8a97e)',
                    color: '#fff',
                    border: 'none',
                    fontSize: 15,
                    cursor: isLoading ? 'not-allowed' : 'pointer',
                  }}
                >
                  {isLoading ? (
                    <><Loader className="animate-spin" size={18} />Analysing…</>
                  ) : (
                    <><ShieldCheck size={18} />Identify Face</>
                  )}
                </button>

                {/* Clear */}
                <button
                  onClick={clearSelection}
                  disabled={isLoading}
                  className="flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95"
                  style={{
                    padding: '12px 20px',
                    background: 'rgba(200,169,126,0.15)',
                    border: '1.5px solid #c8a97e',
                    color: '#7a5c3e',
                    fontSize: 15,
                    cursor: isLoading ? 'not-allowed' : 'pointer',
                    opacity: isLoading ? 0.5 : 1,
                  }}
                >
                  <X size={16} />
                  Clear
                </button>
              </>
            ) : (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full flex items-center justify-center gap-2 rounded-xl font-semibold transition-all active:scale-95"
                style={{
                  padding: '12px 0',
                  background: 'rgba(200,169,126,0.15)',
                  border: '1.5px solid #c8a97e',
                  color: '#7a5c3e',
                  fontSize: 15,
                }}
              >
                <Upload size={18} />
                Select Photo
              </button>
            )}
          </div>

          {/* Info */}
          <div
            className="rounded-lg p-4 text-sm"
            style={{ background: 'rgba(200,169,126,0.08)', border: '1px solid #d4b896', color: '#7a5c3e' }}
          >
            <p className="font-semibold mb-1" style={{ color: '#5a3e28' }}>
              Two-step photo check-in
            </p>
            <ul className="space-y-1 text-xs">
              <li>✓ Upload a clear, well-lit photo of your face</li>
              <li>✓ Click <strong>Identify Face</strong> — the system analyses the photo</li>
              <li>✓ A confirmation dialog shows the matched name</li>
              <li>✓ Tap <strong>"Yes, that's me"</strong> to officially save attendance</li>
              <li>✓ Tap <strong>"Not me"</strong> to cancel — nothing is recorded</li>
            </ul>
          </div>
        </div>
      </Card>
    </>
  );
};

export default UploadPhoto;
