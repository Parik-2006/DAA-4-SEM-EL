import React, {
  useState,
  useCallback,
  useMemo,
  useEffect,
} from 'react';
import { useSearchParams } from 'react-router-dom';

import {
  Layout,
  LiveCamera,
} from '../components';
import { getCurrentUser } from '../services/firebase/auth.service';
import {
  useAttendanceEligibility,
  usePostMarkRefresh,
} from '../hooks/useAttendanceRefresh';

import {
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Camera,
  Loader2,
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────

const MAX_CONSECUTIVE_FAILURES = 5;

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

interface AttendanceResponse {
  status?: 'success' | 'error';
  message?: string;

  student_name?: string;
  student_id?: string;

  confidence?: number;
}

// ─────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────

const FaceRegistrationPage: React.FC = () => {

  // ─────────────────────────────────────────────────────────
  // State
  // ─────────────────────────────────────────────────────────

  const [isProcessing, setIsProcessing] =
    useState(false);

  const [attendanceData, setAttendanceData] =
    useState<AttendanceResponse | null>(null);

  const [consecutiveFailures, setConsecutiveFailures] =
    useState(0);

  // ─────────────────────────────────────────────────────────
  // Callbacks
  // ─────────────────────────────────────────────────────────

  const handleAttendanceMarked = useCallback(
    (data: AttendanceResponse) => {

      setAttendanceData(data);

      // Reset failure counter after success
      if (data?.status === 'success') {
        setConsecutiveFailures(0);
        // Trigger auto-refresh of pages after marking
        triggerPostMarkRefresh();
      }
    },
    [triggerPostMarkRefresh]
  );

  const handleConsecutiveFailures = useCallback(
    (count: number) => {
      setConsecutiveFailures(count);
    },
    []
  );

  // Eligibility check: is current time within a scheduled period?
  const eligibility = useAttendanceEligibility();

  // Auto-refresh after marking attendance
  const triggerPostMarkRefresh = usePostMarkRefresh(() => {
    // Optional: trigger any dashboard refresh here
    eligibility.refetch();
  });

  // Read optional query param to auto-start camera for a particular student
  const [searchParams] = useSearchParams();
  const targetStudent =
    searchParams.get('student') ??
    sessionStorage.getItem('user_id') ??
    getCurrentUser()?.uid ??
    null;

  // ─────────────────────────────────────────────────────────
  // Derived State
  // ─────────────────────────────────────────────────────────

  const hasHardStopped = useMemo(
    () =>
      consecutiveFailures >=
      MAX_CONSECUTIVE_FAILURES,
    [consecutiveFailures]
  );

  const nearLimit = useMemo(
    () =>
      consecutiveFailures > 0 &&
      consecutiveFailures <
        MAX_CONSECUTIVE_FAILURES,
    [consecutiveFailures]
  );

  const isSuccess = useMemo(
    () => attendanceData?.status === 'success',
    [attendanceData]
  );

  const remainingAttempts = useMemo(
    () =>
      MAX_CONSECUTIVE_FAILURES -
      consecutiveFailures,
    [consecutiveFailures]
  );

  // ─────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────

  return (
    <Layout>
      <div className="max-w-6xl mx-auto space-y-6">

        {/* ───────────────── HEADER ───────────────── */}

        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">

          <div>
            <h1 className="text-3xl font-bold text-gray-800">
              Face Registration & Detection
            </h1>

            <p className="text-sm text-gray-500 mt-1">
              Real-time facial recognition attendance system
            </p>
          </div>

          {/* STATUS BADGE */}

          <div
            className="px-4 py-2 rounded-full text-sm font-bold shadow-sm border w-fit"
            style={
              hasHardStopped
                ? {
                    background: '#FEF2F2',
                    color: '#dc2626',
                    borderColor: '#fca5a5',
                  }
                : isSuccess
                ? {
                    background: '#F0FDF4',
                    color: '#16a34a',
                    borderColor: '#86efac',
                  }
                : isProcessing
                ? {
                    background: '#EFF6FF',
                    color: '#2563eb',
                    borderColor: '#93c5fd',
                  }
                : {
                    background: '#EEF2FF',
                    color: '#4f46e5',
                    borderColor: '#a5b4fc',
                  }
            }
          >
            <div className="flex items-center gap-2">

              {isProcessing && (
                <Loader2
                  size={14}
                  className="animate-spin"
                />
              )}

              {hasHardStopped
                ? '⛔ Detection Stopped'
                : isSuccess
                ? '✅ Attendance Marked'
                : isProcessing
                ? 'Scanning Face...'
                : '● Live Mode'}
            </div>
          </div>
        </div>

        {/* ───────────────── MAIN GRID ───────────────── */}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* CAMERA */}

          <div className="lg:col-span-2">

            {!eligibility.isEligible && (
              <div
                className="p-6 rounded-2xl border-2 text-center mb-6"
                style={{
                  background: '#FEF2F2',
                  borderColor: '#fca5a5',
                  color: '#dc2626',
                }}
              >
                <p className="font-bold text-lg mb-2">⏰ Outside Attendance Window</p>
                <p className="text-sm mb-4">{eligibility.reason}</p>
                {eligibility.nextPeriod && (
                  <p className="text-sm font-semibold">
                    Next class: {eligibility.nextPeriod.course_code} at {eligibility.nextPeriod.start_time}
                  </p>
                )}
              </div>
            )}

            {eligibility.isEligible && (
              <div
                className="p-4 rounded-xl border mb-6"
                style={{
                  background: '#F0FDF4',
                  borderColor: '#86efac',
                  color: '#166534',
                }}
              >
                <p className="font-semibold text-sm">
                  ✓ Active class: {eligibility.currentPeriod?.course_code} ({eligibility.currentPeriod?.start_time}–{eligibility.currentPeriod?.end_time})
                </p>
              </div>
            )}

            <LiveCamera
              onAttendanceMarked={
                handleAttendanceMarked
              }
              onProcessing={setIsProcessing}
              isLoading={isProcessing}
              onConsecutiveFailures={
                handleConsecutiveFailures
              }
              autoStart={!!targetStudent && eligibility.isEligible}
              targetStudentId={targetStudent}
            />
          </div>

          {/* SIDEBAR */}

          <div className="space-y-5">

            {/* ───────────────── STATUS CARD ───────────────── */}

            <div className="bg-white rounded-2xl shadow-md p-6 border border-gray-100">

              <h2 className="text-lg font-bold text-gray-800 mb-5 flex items-center gap-2">

                <div className="w-2 h-6 bg-indigo-500 rounded-full" />

                Detection Status
              </h2>

              {/* SUCCESS */}

              {isSuccess && attendanceData && (

                <div
                  className="p-4 rounded-xl border"
                  style={{
                    background: '#F0FDF4',
                    borderColor: '#86efac',
                    color: '#166534',
                  }}
                >

                  <div className="flex items-center gap-2 mb-3">

                    <CheckCircle
                      size={18}
                      style={{ color: '#16a34a' }}
                    />

                    <p className="font-bold">
                      Detection Successful
                    </p>
                  </div>

                  <p className="text-sm mb-4">
                    {attendanceData.message}
                  </p>

                  <div
                    className="pt-4 border-t"
                    style={{
                      borderColor: '#bbf7d0',
                    }}
                  >

                    <div className="space-y-3">

                      <div>
                        <p className="text-xs uppercase font-semibold tracking-wider text-green-700">
                          Student Name
                        </p>

                        <p className="text-xl font-bold">
                          {attendanceData.student_name}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs uppercase font-semibold tracking-wider text-green-700">
                          Student ID
                        </p>

                        <p className="font-semibold">
                          {attendanceData.student_id}
                        </p>
                      </div>

                      {attendanceData.confidence !=
                        null && (
                        <div>
                          <p className="text-xs uppercase font-semibold tracking-wider text-green-700">
                            Confidence Score
                          </p>

                          <p className="font-semibold">
                            {(
                              attendanceData.confidence *
                              100
                            ).toFixed(1)}
                            %
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* HARD STOP */}

              {hasHardStopped && !isSuccess && (

                <div
                  className="p-4 rounded-xl border"
                  style={{
                    background: '#FEF2F2',
                    borderColor: '#fca5a5',
                    color: '#991b1b',
                  }}
                >

                  <div className="flex items-center gap-2 mb-3">

                    <AlertTriangle
                      size={18}
                      style={{ color: '#dc2626' }}
                    />

                    <p className="font-bold">
                      Detection Failed
                    </p>
                  </div>

                  <p className="text-sm leading-relaxed">
                    Face detection stopped after{' '}
                    <strong>
                      {MAX_CONSECUTIVE_FAILURES}
                    </strong>{' '}
                    failed attempts.
                  </p>

                  <div
                    className="mt-4 pt-4 border-t flex items-start gap-2"
                    style={{
                      borderColor: '#fecaca',
                    }}
                  >

                    <RefreshCw
                      size={14}
                      className="mt-0.5"
                    />

                    <p className="text-xs leading-relaxed">
                      Use{' '}
                      <strong>
                        Try Again
                      </strong>{' '}
                      or restart the camera to
                      continue scanning.
                    </p>
                  </div>
                </div>
              )}

              {/* WARNING */}

              {nearLimit && !isSuccess && (

                <div
                  className="p-4 rounded-xl border"
                  style={{
                    background: '#FFFBEB',
                    borderColor: '#FCD34D',
                    color: '#92400E',
                  }}
                >

                  <div className="flex items-center gap-2 mb-3">

                    <AlertTriangle
                      size={18}
                      style={{ color: '#d97706' }}
                    />

                    <p className="font-bold">
                      {remainingAttempts} attempt
                      {remainingAttempts !== 1
                        ? 's'
                        : ''}{' '}
                      remaining
                    </p>
                  </div>

                  {/* ATTEMPT DOTS */}

                  <div className="flex gap-2 mb-4">

                    {Array.from({
                      length:
                        MAX_CONSECUTIVE_FAILURES,
                    }).map((_, index) => (

                      <div
                        key={index}
                        className="w-3 h-3 rounded-full transition-all"
                        style={{
                          background:
                            index <
                            consecutiveFailures
                              ? '#ef4444'
                              : '#d1d5db',
                        }}
                      />
                    ))}
                  </div>

                  <p className="text-xs leading-relaxed">
                    Improve lighting and ensure
                    your face is clearly visible.
                  </p>
                </div>
              )}

              {/* IDLE */}

              {!isSuccess &&
                !nearLimit &&
                !hasHardStopped && (

                <div className="text-center py-10 text-gray-400">

                  <Camera
                    size={40}
                    className="mx-auto mb-4"
                  />

                  <p className="text-sm font-medium">
                    Waiting for face detection...
                  </p>

                  <p className="text-xs mt-2 text-gray-300">
                    Start the camera to begin
                    scanning
                  </p>
                </div>
              )}
            </div>

            {/* ───────────────── ATTEMPT HISTORY ───────────────── */}

            {consecutiveFailures > 0 &&
              !isSuccess && (

              <div
                className="rounded-2xl p-5 border"
                style={{
                  background: '#FFF7ED',
                  borderColor: '#FED7AA',
                }}
              >

                <p
                  className="text-xs uppercase tracking-wider font-bold mb-3"
                  style={{ color: '#c2410c' }}
                >
                  Scan Attempts
                </p>

                <div className="flex items-center gap-3">

                  <div className="flex gap-1.5">

                    {Array.from({
                      length:
                        MAX_CONSECUTIVE_FAILURES,
                    }).map((_, i) => (

                      <div
                        key={i}
                        className="w-6 h-6 rounded-md flex items-center justify-center"
                        style={{
                          background:
                            i <
                            consecutiveFailures
                              ? '#ef4444'
                              : '#e5e7eb',
                        }}
                      >
                        {i <
                          consecutiveFailures && (
                          <span className="text-white text-[10px] font-bold">
                            ✕
                          </span>
                        )}
                      </div>
                    ))}
                  </div>

                  <span
                    className="text-xs font-semibold"
                    style={{ color: '#c2410c' }}
                  >
                    {consecutiveFailures}/
                    {MAX_CONSECUTIVE_FAILURES}{' '}
                    failed
                  </span>
                </div>
              </div>
            )}

            {/* ───────────────── INSTRUCTIONS ───────────────── */}

            <div className="bg-gradient-to-br from-indigo-600 to-blue-700 rounded-2xl shadow-lg p-6 text-white">

              <h3 className="font-bold mb-4">
                Instructions
              </h3>

              <ul className="text-xs space-y-3 opacity-95">

                <li className="flex gap-2">
                  <span className="font-bold">
                    1.
                  </span>

                  <span>
                    Click "Start Camera" to
                    begin scanning.
                  </span>
                </li>

                <li className="flex gap-2">
                  <span className="font-bold">
                    2.
                  </span>

                  <span>
                    Position your face clearly
                    inside the frame.
                  </span>
                </li>

                <li className="flex gap-2">
                  <span className="font-bold">
                    3.
                  </span>

                  <span>
                    The system scans every ~2.5
                    seconds automatically.
                  </span>
                </li>

                <li className="flex gap-2">
                  <span className="font-bold">
                    4.
                  </span>

                  <span>
                    Confirm your identity in
                    the popup modal.
                  </span>
                </li>

                <li className="flex gap-2 opacity-80">
                  <span className="font-bold">
                    ⚠
                  </span>

                  <span>
                    Detection stops after{' '}
                    {
                      MAX_CONSECUTIVE_FAILURES
                    }{' '}
                    failed attempts.
                  </span>
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