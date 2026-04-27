import React, { useState } from 'react';
import { Camera, Upload, AlertCircle, CheckCircle, Sparkles } from 'lucide-react';
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
    if (data.status === 'success') {
      setTimeout(() => setResult(null), 5000);
    }
  };

  const handleProcessing = (isProcessing: boolean) => setIsLoading(isProcessing);
  const clearResult = () => setResult(null);

  return (
    <Layout>
      <div className="space-y-7 max-w-2xl mx-auto">

        {/* ── Page Header ───────────────────────────────────────────────────── */}
        <div className="animate-fade-in-up">
          <p
            className="text-xs font-semibold tracking-widest uppercase mb-1"
            style={{ color: 'var(--whisper)' }}
          >
            Biometric Check-in
          </p>
          <div className="flex items-end justify-between">
            <h1
              className="text-3xl font-medium leading-none"
              style={{ fontFamily: 'Fraunces, serif', color: 'var(--ink)' }}
            >
              Mark Attendance
            </h1>
            <span className="text-xs" style={{ color: 'var(--whisper)' }}>
              {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
            </span>
          </div>
        </div>

        {/* ── Mode Selector ─────────────────────────────────────────────────── */}
        <Card className="!p-2 animate-fade-in-up">
          <div
            className="relative grid grid-cols-2 rounded-xl overflow-hidden"
            style={{ background: 'rgba(155,122,58,0.06)', padding: '3px', gap: '3px' }}
          >
            {/* Animated pill indicator */}
            <div
              className="absolute top-[3px] bottom-[3px] rounded-[10px] transition-all duration-300 ease-out"
              style={{
                width: 'calc(50% - 4.5px)',
                left: mode === 'live' ? '3px' : 'calc(50% + 1.5px)',
                background: 'linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%)',
                boxShadow: '0 2px 12px rgba(155,122,58,0.30)',
              }}
            />

            {([
              { id: 'live' as const, label: 'Live Camera', icon: <Camera size={15} /> },
              { id: 'upload' as const, label: 'Upload Photo', icon: <Upload size={15} /> },
            ] as const).map(({ id, label, icon }) => {
              const active = mode === id;
              return (
                <button
                  key={id}
                  onClick={() => { setMode(id); clearResult(); }}
                  className="relative z-10 flex items-center justify-center gap-2 py-2.5 rounded-[10px] btn-press transition-all duration-200"
                  style={{
                    fontSize: '0.8125rem',
                    fontWeight: active ? 600 : 500,
                    color: active ? '#fff' : 'var(--muted)',
                  }}
                >
                  {icon}
                  {label}
                </button>
              );
            })}
          </div>
        </Card>

        {/* ── Result Banner ─────────────────────────────────────────────────── */}
        {result && (
          <div
            className="rounded-2xl px-5 py-4 animate-scale-in"
            style={{
              background: result.status === 'success'
                ? 'rgba(107,138,113,0.10)'
                : result.status === 'error'
                  ? 'rgba(193,123,91,0.10)'
                  : 'rgba(155,122,58,0.10)',
              border: `1px solid ${result.status === 'success'
                ? 'rgba(107,138,113,0.25)'
                : result.status === 'error'
                  ? 'rgba(193,123,91,0.25)'
                  : 'rgba(155,122,58,0.25)'}`,
            }}
          >
            <div className="flex items-start gap-3">
              {/* Icon */}
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{
                  background: result.status === 'success'
                    ? 'rgba(107,138,113,0.15)'
                    : result.status === 'error'
                      ? 'rgba(193,123,91,0.15)'
                      : 'rgba(155,122,58,0.15)',
                }}
              >
                {result.status === 'success' ? (
                  <CheckCircle size={17} style={{ color: 'var(--sage)' }} />
                ) : (
                  <AlertCircle
                    size={17}
                    style={{ color: result.status === 'error' ? 'var(--terra)' : 'var(--gold)' }}
                  />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p
                  className="text-sm font-semibold"
                  style={{
                    color: result.status === 'success' ? 'var(--sage)'
                      : result.status === 'error' ? 'var(--terra)' : 'var(--gold)',
                    fontFamily: 'Fraunces, serif',
                  }}
                >
                  {result.status === 'success' ? 'Attendance Recorded'
                    : result.status === 'error' ? 'Recognition Failed'
                      : 'Processing…'}
                </p>
                <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--muted)' }}>
                  {result.message}
                </p>

                {result.student_name && (
                  <div className="mt-2 flex items-center gap-3">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-bold"
                      style={{ background: 'linear-gradient(135deg, var(--gold), var(--gold-light))' }}
                    >
                      {result.student_name.charAt(0)}
                    </div>
                    <div>
                      <span className="text-xs font-semibold" style={{ color: 'var(--ink)' }}>
                        {result.student_name}
                      </span>
                      {result.confidence != null && (
                        <span
                          className="ml-2 text-[11px] font-mono px-1.5 py-0.5 rounded-full"
                          style={{ background: 'rgba(107,138,113,0.12)', color: 'var(--sage)' }}
                        >
                          {(result.confidence * 100).toFixed(1)}% confidence
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Dismiss */}
              <button
                onClick={clearResult}
                className="text-xs flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center btn-press"
                style={{
                  color: 'var(--whisper)',
                  background: 'rgba(155,122,58,0.08)',
                }}
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* ── Camera / Upload Component ──────────────────────────────────────── */}
        <div className="animate-fade-in-up">
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

        {/* ── Instructions Panel ─────────────────────────────────────────────── */}
        <div
          className="rounded-2xl px-6 py-5 animate-fade-in-up"
          style={{
            background: 'linear-gradient(135deg, rgba(155,122,58,0.05) 0%, rgba(107,138,113,0.05) 100%)',
            border: '1px solid rgba(155,122,58,0.13)',
          }}
        >
          <div className="flex items-center gap-2 mb-4">
            <Sparkles size={14} style={{ color: 'var(--gold)' }} />
            <p
              className="text-xs font-semibold tracking-widest uppercase"
              style={{ color: 'var(--gold)' }}
            >
              {mode === 'live' ? 'Camera Instructions' : 'Upload Instructions'}
            </p>
          </div>

          <ul className="space-y-2.5">
            {(mode === 'live'
              ? [
                'Allow camera permission when the browser prompts.',
                'Position your face clearly — centred, well-lit, no heavy backlight.',
                'Face detection runs automatically every 2.5 seconds.',
                'Attendance is marked the moment a registered face is detected.',
              ]
              : [
                'Select a JPEG or PNG photo containing your face.',
                'Maximum file size is 10 MB.',
                'Tap "Mark Attendance" to process and match.',
                'Ensure your face fills a good portion of the frame.',
              ]
            ).map((tip, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span
                  className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-[9px] font-bold"
                  style={{
                    background: 'linear-gradient(135deg, var(--gold), var(--gold-light))',
                    color: '#fff',
                  }}
                >
                  {i + 1}
                </span>
                <span className="text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>{tip}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Layout>
  );
};
