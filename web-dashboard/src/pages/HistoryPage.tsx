// src/pages/HistoryPage.tsx

import React, {
  useState,
  useEffect,
} from 'react';

import {
  Layout,
} from '../components/Layout';

import {
  AttendanceHistory,
} from '../components/AttendanceHistory';

import {
  attendanceAPI,
  type AttendanceRecord,
} from '../services/api';

import {
  getStoredRole,
} from '../utils/roles';

import {
  Clock,
  Calendar,
  BookOpen,
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
// StudentHistoryView
// STRICT SELF-ONLY VIEW
//
// Students NEVER receive class-wide records.
// Student identity comes ONLY from authenticated session storage.
// ─────────────────────────────────────────────────────────────────────────────

const StudentHistoryView: React.FC =
  () => {

    const studentId =
      sessionStorage.getItem(
        'user_id'
      ) ?? '';

    if (!studentId) {

      return (
        <div
          className="flex items-center justify-center py-20 rounded-2xl"
          style={{
            background:
              'rgba(193,123,91,0.06)',

            border:
              '1px dashed rgba(193,123,91,0.28)',
          }}
        >
          <p
            className="text-sm font-medium"
            style={{
              color:
                'var(--muted)',
            }}
          >
            Unable to load history —
            student session not found.
          </p>
        </div>
      );
    }

    return (
      <div className="space-y-6">

        {/* HEADER */}

        <div className="flex items-start justify-between gap-4 flex-wrap">

          <div>

            <p
              className="text-[10px] font-bold tracking-[0.14em] uppercase mb-1"
              style={{
                color:
                  'var(--whisper)',
              }}
            >
              My Records
            </p>

            <h1
              className="text-3xl font-bold"
              style={{
                fontFamily:
                  'Fraunces, serif',

                color:
                  'var(--ink)',
              }}
            >
              Attendance History
            </h1>

            <p
              className="text-sm mt-1"
              style={{
                color:
                  'var(--muted)',
              }}
            >
              Your personal attendance
              across all enrolled
              courses.
            </p>
          </div>

          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold"
            style={{
              background:
                'rgba(155,122,58,0.10)',

              border:
                '1px solid rgba(155,122,58,0.22)',

              color:
                'var(--gold)',
            }}
          >
            <Clock size={12} />

            {new Date().toLocaleDateString(
              'en-IN',
              {
                weekday:
                  'long',

                day:
                  'numeric',

                month:
                  'long',

                year:
                  'numeric',
              }
            )}
          </div>
        </div>

        {/* SELF-ONLY HISTORY */}

        <AttendanceHistory
          studentId={
            studentId
          }
        />
      </div>
    );
  };

// ─────────────────────────────────────────────────────────────────────────────
// StaffHistoryView
//
// Faculty/Admin operational real-time stream.
// Students NEVER reach this component.
// ─────────────────────────────────────────────────────────────────────────────

const StaffHistoryView: React.FC =
  () => {

    const [
      records,
      setRecords,
    ] = useState<
      AttendanceRecord[]
    >([]);

    const [
      isLoading,
      setLoading,
    ] = useState(true);

    const fetchRecords =
      async () => {

        try {

          const data =
            await attendanceAPI.getLiveAttendance(
              undefined,
              100
            );

          setRecords(data);

        } catch (
          err
        ) {

          console.error(
            'Error fetching attendance history:',
            err
          );

        } finally {

          setLoading(
            false
          );
        }
      };

    useEffect(() => {

      fetchRecords();

      const interval =
        setInterval(
          fetchRecords,
          10000
        );

      return () =>
        clearInterval(
          interval
        );

    }, []);

    return (
      <div className="space-y-6">

        {/* HEADER */}

        <div className="flex justify-between items-center flex-wrap gap-4">

          <h1
            className="text-3xl font-bold"
            style={{
              fontFamily:
                'Fraunces, serif',

              color:
                'var(--ink)',
            }}
          >
            Attendance History
          </h1>

          <div
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
            style={{
              background:
                'var(--glass-bg)',

              border:
                '1px solid var(--glass-border)',

              color:
                'var(--muted)',
            }}
          >
            <Calendar
              size={18}
              style={{
                color:
                  'var(--gold)',
              }}
            />

            {new Date().toLocaleDateString(
              'en-US',
              {
                weekday:
                  'long',

                year:
                  'numeric',

                month:
                  'long',

                day:
                  'numeric',
              }
            )}
          </div>
        </div>

        {/* STREAM */}

        <div
          className="rounded-2xl overflow-hidden"
          style={{
            background:
              'var(--glass-bg)',

            border:
              '1px solid var(--glass-border)',
          }}
        >

          {/* HEADER */}

          <div
            className="p-6 flex justify-between items-center"
            style={{
              borderBottom:
                '1px solid rgba(190,160,118,0.18)',

              background:
                'rgba(155,122,58,0.04)',
            }}
          >
            <h2
              className="text-base font-bold"
              style={{
                color:
                  'var(--ink)',
              }}
            >
              Real-time Attendance Stream
            </h2>

            <div className="flex items-center gap-2">

              <span className="relative flex h-2 w-2">

                <span
                  className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                  style={{
                    background:
                      'var(--sage)',
                  }}
                />

                <span
                  className="relative inline-flex rounded-full h-2 w-2"
                  style={{
                    background:
                      'var(--sage)',
                  }}
                />
              </span>

              <span
                className="text-xs font-semibold uppercase tracking-wider"
                style={{
                  color:
                    'var(--sage)',
                }}
              >
                Live
              </span>
            </div>
          </div>

          {/* TABLE */}

          <div className="overflow-x-auto">

            <table className="w-full text-left">

              <thead>

                <tr
                  style={{
                    borderBottom:
                      '1px solid rgba(190,160,118,0.18)',

                    background:
                      'rgba(155,122,58,0.03)',
                  }}
                >
                  {[
                    'Student',
                    'Student ID',
                    'Period / Subject',
                    'Time',
                    'Status',
                  ].map(
                    (
                      h
                    ) => (
                      <th
                        key={
                          h
                        }
                        className="px-6 py-4 text-xs font-semibold uppercase tracking-wider"
                        style={{
                          color:
                            'var(--whisper)',
                        }}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>

              <tbody>

                {isLoading ? (

                  <tr>

                    <td
                      colSpan={5}
                      className="px-6 py-12 text-center"
                    >

                      <div className="flex flex-col items-center gap-3">

                        <div
                          className="w-8 h-8 rounded-full border-[3px] border-t-transparent animate-spin"
                          style={{
                            borderColor:
                              'rgba(155,122,58,0.25)',

                            borderTopColor:
                              'var(--gold)',
                          }}
                        />

                        <p
                          className="text-sm"
                          style={{
                            color:
                              'var(--whisper)',
                          }}
                        >
                          Loading history…
                        </p>
                      </div>
                    </td>
                  </tr>

                ) : records.length ===
                  0 ? (

                  <tr>

                    <td
                      colSpan={5}
                      className="px-6 py-12 text-center"
                    >
                      <p
                        className="text-sm"
                        style={{
                          color:
                            'var(--whisper)',
                        }}
                      >
                        No attendance records found for today.
                      </p>
                    </td>
                  </tr>

                ) : (

                  records.map(
                    (
                      record
                    ) => (
                      <AttendanceRow
                        key={
                          record.id
                        }
                        record={
                          record
                        }
                      />
                    )
                  )
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

// ─────────────────────────────────────────────────────────────────────────────
// Attendance Row
// ─────────────────────────────────────────────────────────────────────────────

const AttendanceRow: React.FC<{
  record: AttendanceRecord;
}> = ({
  record,
}) => {

  const [
    hovered,
    setHovered,
  ] = useState(false);

  const statusStyles:
    Record<
      string,
      {
        bg: string;

        color: string;
      }
    > = {

    present: {
      bg:
        'rgba(107,138,113,0.12)',

      color:
        'var(--sage)',
    },

    late: {
      bg:
        'rgba(176,128,48,0.12)',

      color:
        '#9B7030',
    },

    absent: {
      bg:
        'rgba(193,123,91,0.12)',

      color:
        'var(--terra)',
    },

    excused: {
      bg:
        'rgba(106,130,168,0.12)',

      color:
        '#5A72A0',
    },
  };

  const sStyle =
    statusStyles[
      record.status
    ] ??
    statusStyles.present;

  return (
    <tr
      onMouseEnter={() =>
        setHovered(
          true
        )
      }
      onMouseLeave={() =>
        setHovered(
          false
        )
      }
      style={{
        borderBottom:
          '1px solid rgba(190,160,118,0.10)',

        background:
          hovered
            ? 'rgba(155,122,58,0.04)'
            : 'transparent',

        transition:
          'background 0.15s ease',
      }}
    >

      {/* STUDENT */}

      <td className="px-6 py-4">

        <div className="flex items-center gap-3">

          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
            style={{
              background:
                'rgba(155,122,58,0.12)',

              color:
                'var(--gold)',
            }}
          >
            {record.student_name
              .charAt(
                0
              )
              .toUpperCase()}
          </div>

          <span
            className="text-sm font-semibold"
            style={{
              color:
                'var(--ink)',
            }}
          >
            {
              record.student_name
            }
          </span>
        </div>
      </td>

      {/* STUDENT ID */}

      <td className="px-6 py-4">

        <span
          className="text-sm font-mono"
          style={{
            color:
              'var(--whisper)',
          }}
        >
          {
            record.student_id
          }
        </span>
      </td>

      {/* COURSE */}

      <td className="px-6 py-4">

        <div
          className="flex items-center gap-2 text-sm"
          style={{
            color:
              'var(--muted)',
          }}
        >
          <BookOpen
            size={14}
            style={{
              color:
                'var(--whisper)',

              flexShrink: 0,
            }}
          />

          <span>
            {record.course_name ||
              '—'}
          </span>
        </div>
      </td>

      {/* TIME */}

      <td className="px-6 py-4">

        <div
          className="flex items-center gap-2 text-sm"
          style={{
            color:
              'var(--muted)',
          }}
        >
          <Clock
            size={14}
            style={{
              color:
                'var(--whisper)',

              flexShrink: 0,
            }}
          />

          <span>
            {new Date(
              record.marked_at
            ).toLocaleTimeString(
              [],
              {
                hour:
                  '2-digit',

                minute:
                  '2-digit',
              }
            )}
          </span>
        </div>
      </td>

      {/* STATUS */}

      <td className="px-6 py-4">

        <span
          className="px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider"
          style={{
            background:
              sStyle.bg,

            color:
              sStyle.color,
          }}
        >
          {
            record.status
          }
        </span>
      </td>
    </tr>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export const HistoryPage: React.FC =
  () => {

    const role =
      getStoredRole();

    return (
      <Layout>

        {role ===
        'student' ? (
          <StudentHistoryView />
        ) : (
          <StaffHistoryView />
        )}

      </Layout>
    );
  };

export default HistoryPage;