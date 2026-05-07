// src/pages/DashboardPage.tsx

import React, {
  useState,
  useEffect,
  useMemo,
} from 'react';

import {
  Layout,
  SystemAlert,
} from '../components';

import {
  useBackendHealth,
} from '../hooks/useBackendHealth';

import {
  attendanceAPI,
} from '../services/api';

import {
  SEEDED_TIMETABLE,
  CSE4C_META,
  SeedPeriod,
  useCSE4CTimetableLocal,
  useAttendanceByPeriod,
  PeriodAttendanceSlot,
} from '../hooks/useAttendanceHooks';

import {
  Users,
  BookOpen,
  CheckCircle,
  Clock,
  XCircle,
  Activity,
  RefreshCw,
  Wifi,
  FlaskConical,
  GraduationCap,
  CalendarDays,
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

const DAYS = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

function todayName(): string {

  return new Date()
    .toLocaleDateString(
      'en-US',
      {
        weekday:
          'long',
      }
    );
}

function toMinutes(
  t: string
): number {

  const [h, m] =
    t.split(':')
      .map(Number);

  return h * 60 + m;
}

function nowMinutes(): number {

  const d = new Date();

  return (
    d.getHours() *
      60 +
    d.getMinutes()
  );
}

function fmt12(
  t: string
): string {

  const [h, m] =
    t.split(':')
      .map(Number);

  const ampm =
    h >= 12
      ? 'PM'
      : 'AM';

  const hr =
    h > 12
      ? h - 12
      : h === 0
      ? 12
      : h;

  return `${hr}:${m
    .toString()
    .padStart(
      2,
      '0'
    )} ${ampm}`;
}

// ─────────────────────────────────────────────────────────────
// Stat Tile
// ─────────────────────────────────────────────────────────────

function StatTile({
  label,
  value,
  color,
  bg,
  Icon,
}: {
  label: string;

  value:
    | number
    | string;

  color: string;

  bg: string;

  Icon: React.FC<{
    size?: number;
    style?: React.CSSProperties;
  }>;
}) {

  return (
    <div
      style={{
        borderRadius:
          18,

        padding:
          '18px 20px',

        background:
          bg,

        border: `1.5px solid ${color}25`,

        display:
          'flex',

        alignItems:
          'center',

        gap: 14,
      }}
    >
      <div
        style={{
          width: 48,

          height: 48,

          borderRadius:
            14,

          background:
            `${color}20`,

          display:
            'flex',

          alignItems:
            'center',

          justifyContent:
            'center',

          flexShrink: 0,
        }}
      >
        <Icon
          size={22}
          style={{
            color,
          }}
        />
      </div>

      <div>
        <p
          style={{
            fontSize:
              '0.66rem',

            letterSpacing:
              '0.1em',

            textTransform:
              'uppercase',

            color:
              '#94a3b8',

            fontWeight: 700,

            marginBottom: 4,
          }}
        >
          {label}
        </p>

        <p
          style={{
            fontSize:
              '1.6rem',

            fontWeight: 900,

            color,

            lineHeight: 1,
          }}
        >
          {value}
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Period Card
// ─────────────────────────────────────────────────────────────

function PeriodCard({
  period,
  selected,
  onClick,
}: {
  period: SeedPeriod;

  selected: boolean;

  onClick: () => void;
}) {

  const now =
    nowMinutes();

  const isActive =
    now >=
      toMinutes(
        period.start_time
      ) &&
    now <
      toMinutes(
        period.end_time
      );

  return (
    <button
      onClick={onClick}
      style={{
        width: '100%',

        padding:
          '14px 16px',

        borderRadius:
          16,

        border: `2px solid ${
          selected
            ? period.course_color
            : isActive
            ? `${period.course_color}50`
            : '#e2e8f0'
        }`,

        background:
          selected
            ? `${period.course_color}18`
            : isActive
            ? `${period.course_color}08`
            : '#fff',

        textAlign:
          'left',

        cursor:
          'pointer',

        transition:
          'all .2s ease',
      }}
    >
      <div
        style={{
          display:
            'flex',

          justifyContent:
            'space-between',

          gap: 10,
        }}
      >
        <div
          style={{
            display:
              'flex',

            gap: 12,

            flex: 1,
          }}
        >
          <div
            style={{
              width: 38,

              height: 38,

              borderRadius:
                12,

              background:
                `${period.course_color}20`,

              display:
                'flex',

              alignItems:
                'center',

              justifyContent:
                'center',

              flexShrink: 0,
            }}
          >
            {period.is_lab_class ? (
              <FlaskConical
                size={16}
                style={{
                  color:
                    period.course_color,
                }}
              />
            ) : (
              <BookOpen
                size={16}
                style={{
                  color:
                    period.course_color,
                }}
              />
            )}
          </div>

          <div
            style={{
              flex: 1,
            }}
          >
            <div
              style={{
                display:
                  'flex',

                alignItems:
                  'center',

                gap: 6,

                marginBottom: 4,

                flexWrap:
                  'wrap',
              }}
            >
              <span
                style={{
                  fontSize:
                    '0.68rem',

                  fontWeight: 800,

                  color:
                    period.course_color,

                  letterSpacing:
                    '0.08em',
                }}
              >
                {
                  period.course_code
                }
              </span>

              {period.is_lab_class && (
                <span
                  style={{
                    fontSize:
                      '0.55rem',

                    padding:
                      '2px 5px',

                    borderRadius:
                      5,

                    background:
                      '#8B5CF615',

                    color:
                      '#8B5CF6',

                    fontWeight: 700,
                  }}
                >
                  LAB
                </span>
              )}

              {isActive && (
                <span
                  style={{
                    display:
                      'flex',

                    alignItems:
                      'center',

                    gap: 4,

                    padding:
                      '2px 7px',

                    borderRadius:
                      99,

                    background:
                      '#EF444420',

                    color:
                      '#EF4444',

                    fontSize:
                      '0.55rem',

                    fontWeight: 700,
                  }}
                >
                  <span
                    style={{
                      width: 5,

                      height: 5,

                      borderRadius:
                        '50%',

                      background:
                        '#EF4444',

                      animation:
                        'pulse 1.5s infinite',
                    }}
                  />

                  LIVE
                </span>
              )}
            </div>

            <p
              style={{
                fontSize:
                  '0.82rem',

                fontWeight: 700,

                color:
                  '#1e293b',

                marginBottom: 5,
              }}
            >
              {
                period.course_name
              }
            </p>

            <p
              style={{
                fontSize:
                  '0.68rem',

                color:
                  '#64748b',
              }}
            >
              {fmt12(
                period.start_time
              )}{' '}
              –{' '}
              {fmt12(
                period.end_time
              )}
            </p>
          </div>
        </div>
      </div>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────
// Attendance Table
// ─────────────────────────────────────────────────────────────

function AttendanceTable({
  slot,
}: {
  slot:
    | PeriodAttendanceSlot
    | null;
}) {

  if (!slot) {
    return (
      <div
        style={{
          minHeight: 260,

          borderRadius:
            18,

          border:
            '1px dashed #e2e8f0',

          display:
            'flex',

          alignItems:
            'center',

          justifyContent:
            'center',

          background:
            '#f8fafc',
        }}
      >
        <div
          style={{
            textAlign:
              'center',
          }}
        >
          <BookOpen
            size={36}
            style={{
              color:
                '#cbd5e1',

              margin:
                '0 auto 12px',
            }}
          />

          <p
            style={{
              color:
                '#94a3b8',

              fontSize:
                '0.85rem',
            }}
          >
            Select a
            timetable slot
          </p>
        </div>
      </div>
    );
  }

  const pct =
    slot.total_students >
    0
      ? Math.round(
          ((slot.present +
            slot.late) /
            slot.total_students) *
            100
        )
      : 0;

  return (
    <div
      style={{
        display:
          'flex',

        flexDirection:
          'column',

        gap: 18,
      }}
    >

      {/* Header */}

      <div
        style={{
          padding:
            '20px',

          borderRadius:
            18,

          background: `linear-gradient(135deg, ${slot.period.course_color}18 0%, ${slot.period.course_color}08 100%)`,

          border: `2px solid ${slot.period.course_color}40`,
        }}
      >
        <div
          style={{
            display:
              'flex',

            justifyContent:
              'space-between',

            gap: 20,

            flexWrap:
              'wrap',
          }}
        >
          <div>
            <div
              style={{
                display:
                  'flex',

                alignItems:
                  'center',

                gap: 8,

                marginBottom: 4,

                flexWrap:
                  'wrap',
              }}
            >
              <span
                style={{
                  fontSize:
                    '0.7rem',

                  fontWeight: 800,

                  color:
                    slot.period.course_color,

                  letterSpacing:
                    '0.08em',

                  textTransform:
                    'uppercase',
                }}
              >
                {
                  slot.period.course_code
                }
              </span>

              {slot.is_active && (
                <span
                  style={{
                    display:
                      'flex',

                    alignItems:
                      'center',

                    gap: 4,

                    padding:
                      '2px 7px',

                    borderRadius:
                      99,

                    background:
                      '#EF444420',

                    color:
                      '#EF4444',

                    fontSize:
                      '0.58rem',

                    fontWeight: 700,
                  }}
                >
                  <span
                    style={{
                      width: 5,

                      height: 5,

                      borderRadius:
                        '50%',

                      background:
                        '#EF4444',
                    }}
                  />

                  LIVE
                </span>
              )}
            </div>

            <h3
              style={{
                fontSize:
                  '1.1rem',

                fontWeight: 900,

                color:
                  '#1e293b',

                marginBottom: 5,
              }}
            >
              {
                slot.period.course_name
              }
            </h3>

            <p
              style={{
                fontSize:
                  '0.78rem',

                color:
                  '#64748b',
              }}
            >
              {fmt12(
                slot.period.start_time
              )}{' '}
              –{' '}
              {fmt12(
                slot.period.end_time
              )}{' '}
              ·{' '}
              {
                slot.period.room
              }
            </p>
          </div>

          <div
            style={{
              textAlign:
                'center',
            }}
          >
            <p
              style={{
                fontSize:
                  '2rem',

                fontWeight: 900,

                color:
                  pct >= 75
                    ? '#22C55E'
                    : '#EF4444',
              }}
            >
              {pct}%
            </p>

            <p
              style={{
                fontSize:
                  '0.65rem',

                color:
                  '#94a3b8',

                textTransform:
                  'uppercase',

                letterSpacing:
                  '0.08em',
              }}
            >
              Attendance
            </p>
          </div>
        </div>
      </div>

      {/* Stats */}

      <div
        style={{
          display:
            'grid',

          gridTemplateColumns:
            'repeat(4,1fr)',

          gap: 10,
        }}
      >
        {[
          {
            label:
              'Present',

            val:
              slot.present,

            color:
              '#22C55E',
          },

          {
            label:
              'Late',

            val:
              slot.late,

            color:
              '#F59E0B',
          },

          {
            label:
              'Absent',

            val:
              slot.absent,

            color:
              '#EF4444',
          },

          {
            label:
              'Pending',

            val:
              slot.pending,

            color:
              '#94A3B8',
          },
        ].map(
          (s) => (
            <div
              key={
                s.label
              }
              style={{
                padding:
                  '12px',

                borderRadius:
                  14,

                textAlign:
                  'center',

                background:
                  `${s.color}10`,

                border: `1.5px solid ${s.color}25`,
              }}
            >
              <p
                style={{
                  fontSize:
                    '1.2rem',

                  fontWeight: 900,

                  color:
                    s.color,
                }}
              >
                {s.val}
              </p>

              <p
                style={{
                  fontSize:
                    '0.65rem',

                  color:
                    '#94a3b8',
                }}
              >
                {s.label}
              </p>
            </div>
          )
        )}
      </div>

      {/* Table */}

      <div
        style={{
          borderRadius:
            16,

          overflow:
            'hidden',

          border:
            '1px solid #e2e8f0',
        }}
      >
        <table
          style={{
            width:
              '100%',

            borderCollapse:
              'collapse',
          }}
        >
          <thead>
            <tr
              style={{
                background:
                  '#f8fafc',

                borderBottom:
                  '2px solid #e2e8f0',
              }}
            >
              {[
                'Student',
                'Status',
                'Confidence',
              ].map(
                (
                  h
                ) => (
                  <th
                    key={
                      h
                    }
                    style={{
                      padding:
                        '10px 14px',

                      textAlign:
                        'left',

                      fontSize:
                        '0.65rem',

                      fontWeight: 700,

                      color:
                        '#94a3b8',

                      textTransform:
                        'uppercase',

                      letterSpacing:
                        '0.08em',
                    }}
                  >
                    {h}
                  </th>
                )
              )}
            </tr>
          </thead>

          <tbody>
            {slot.records.map(
              (
                rec,
                idx
              ) => (
                <tr
                  key={
                    rec.student_id
                  }
                  style={{
                    borderBottom:
                      '1px solid #f1f5f9',

                    background:
                      idx %
                        2 ===
                      0
                        ? '#fff'
                        : '#fafbff',
                  }}
                >
                  <td
                    style={{
                      padding:
                        '10px 14px',
                    }}
                  >
                    <div
                      style={{
                        display:
                          'flex',

                        flexDirection:
                          'column',
                      }}
                    >
                      <span
                        style={{
                          fontSize:
                            '0.82rem',

                          fontWeight: 700,

                          color:
                            '#1e293b',
                        }}
                      >
                        {
                          rec.student_name
                        }
                      </span>

                      <span
                        style={{
                          fontSize:
                            '0.68rem',

                          color:
                            '#94a3b8',

                          fontFamily:
                            'monospace',
                        }}
                      >
                        {
                          rec.student_id
                        }
                      </span>
                    </div>
                  </td>

                  <td
                    style={{
                      padding:
                        '10px 14px',
                    }}
                  >
                    <span
                      style={{
                        display:
                          'inline-flex',

                        alignItems:
                          'center',

                        gap: 5,

                        padding:
                          '4px 10px',

                        borderRadius:
                          99,

                        background:
                          rec.status ===
                          'present'
                            ? '#F0FDF4'
                            : rec.status ===
                              'late'
                            ? '#FFFBEB'
                            : rec.status ===
                              'absent'
                            ? '#FEF2F2'
                            : '#F8FAFC',

                        color:
                          rec.status ===
                          'present'
                            ? '#16A34A'
                            : rec.status ===
                              'late'
                            ? '#D97706'
                            : rec.status ===
                              'absent'
                            ? '#DC2626'
                            : '#64748b',

                        fontSize:
                          '0.7rem',

                        fontWeight: 700,
                      }}
                    >
                      {
                        rec.status
                      }
                    </span>
                  </td>

                  <td
                    style={{
                      padding:
                        '10px 14px',

                      fontSize:
                        '0.72rem',

                      color:
                        '#94a3b8',

                      fontFamily:
                        'monospace',
                    }}
                  >
                    {rec.confidence !=
                    null
                      ? `${Math.round(
                          rec.confidence *
                            100
                        )}%`
                      : '—'}
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Dashboard
// ─────────────────────────────────────────────────────────────

export const DashboardPage: React.FC =
  () => {

    const {
      isHealthy,
    } =
      useBackendHealth();

    const [
      selectedDay,
      setSelectedDay,
    ] = useState(
      todayName()
    );

      const [selectedClassId, setSelectedClassId] = useState<string>(CSE4C_META.class_id);

    const [
      selectedPeriodId,
      setSelectedPeriodId,
    ] = useState<
      string | null
    >(null);

    const [
      globalStats,
      setGlobalStats,
    ] = useState({
      totalStudents:
        70,

      attendanceToday:
        0,

      presentCount:
        0,

      pendingRecords:
        70,
    });

    // timetable periods

    const timetable = useCSE4CTimetableLocal(selectedClassId);

    const dayPeriods = useMemo(() => {
      const list = (timetable.days?.[selectedDay] ?? SEEDED_TIMETABLE.filter((p) => p.day === selectedDay).map((sp) => ({
        period_id: sp.period_id,
        start_time: sp.start_time,
        end_time: sp.end_time,
        course_code: sp.course_code,
        course_name: sp.course_name,
        faculty_id: '',
        faculty_name: sp.faculty_name ?? '',
        is_lab_class: Boolean(sp.is_lab_class),
        room: sp.room,
        course_color: sp.course_color,
      })));

      return list.sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time));
    }, [selectedDay, timetable.days]);

    const timetableSource = timetable.source ?? 'seeded';

    // auto select

    useEffect(() => {

      if (
        dayPeriods.length ===
        0
      ) {
        setSelectedPeriodId(
          null
        );

        return;
      }

      const now =
        nowMinutes();

      const active =
        dayPeriods.find(
          (
            p
          ) =>
            now >=
              toMinutes(
                p.start_time
              ) &&
            now <
              toMinutes(
                p.end_time
              )
        );

      setSelectedPeriodId(
        (
          active ??
          dayPeriods[0]
        ).period_id
      );

    }, [dayPeriods]);

    // attendance hook

    const {
      slots,
      loading:
        slotsLoading,
      refetch:
        refetchSlots,
    } =
      useAttendanceByPeriod({
        day: selectedDay,
        date: new Date().toISOString().split('T')[0],
        classId: selectedClassId,
        enabled: true,
      });

    const selectedSlot =
      slots.find(
        (
          s
        ) =>
          s.period
            .period_id ===
          selectedPeriodId
      ) ?? null;

    // stats polling

    useEffect(() => {

      const fetch =
        async () => {

          try {

            const data =
              await attendanceAPI.getAdminAttendanceToday();

            if (
              data &&
              !data.error
            ) {

              const total =
                Number(
                  data.totalStudents ||
                    70
                );

              const present =
                Number(
                  data.presentCount ||
                    0
                );

              setGlobalStats({
                totalStudents:
                  total,

                presentCount:
                  present,

                attendanceToday:
                  total > 0
                    ? Math.round(
                        (present /
                          total) *
                          100
                      )
                    : 0,

                pendingRecords:
                  total -
                  present,
              });
            }

          } catch {}
        };

      fetch();

      const id =
        setInterval(
          fetch,
          15000
        );

      return () =>
        clearInterval(
          id
        );

    }, []);

    return (
      <Layout>
        {!isHealthy && (
          <SystemAlert
            type="warning"
            message="Backend offline — showing seeded UG CSE 4C timetable."
          />
        )}

        <div
          style={{
            display:
              'flex',

            flexDirection:
              'column',

            gap: 24,
          }}
        >

          {/* Header */}

          <div
            style={{
              display:
                'flex',

              justifyContent:
                'space-between',

              flexWrap:
                'wrap',

              gap: 14,
            }}
          >
            <div>
              <p
                style={{
                  fontSize:
                    '0.66rem',

                  fontWeight: 700,

                  color:
                    '#94a3b8',

                  letterSpacing:
                    '0.12em',

                  textTransform:
                    'uppercase',

                  marginBottom: 4,
                }}
              >
                Timetable Dashboard
              </p>

              <h1
                style={{
                  fontSize:
                    '1.8rem',

                  fontWeight: 900,

                  color:
                    '#1e293b',
                }}
              >
                {
                  CSE4C_META.display
                }
              </h1>

              <p
                style={{
                  fontSize:
                    '0.78rem',

                  color:
                    '#64748b',

                  marginTop: 4,
                }}
              >
                Semester{' '}
                {
                  CSE4C_META.semester
                }{' '}
                ·{' '}
                {
                  CSE4C_META.term
                }{' '}
                · Room{' '}
                {
                  CSE4C_META.room
                }
              </p>
            </div>

            <button
              onClick={
                refetchSlots
              }
              style={{
                display:
                  'flex',

                alignItems:
                  'center',

                gap: 7,

                padding:
                  '10px 16px',

                borderRadius:
                  12,

                background:
                  '#fff',

                border:
                  '1.5px solid #e2e8f0',

                cursor:
                  'pointer',

                color:
                  '#64748b',

                fontWeight: 600,
              }}
            >
              <RefreshCw
                size={14}
              />

              Refresh
            </button>
          </div>

          {/* Global Stats */}

          <div
            style={{
              display:
                'grid',

              gridTemplateColumns:
                'repeat(auto-fit,minmax(180px,1fr))',

              gap: 12,
            }}
          >
            <StatTile
              label="Students"
              value={
                globalStats.totalStudents
              }
              color="#6366F1"
              bg="#EEF2FF"
              Icon={Users}
            />

            <StatTile
              label="Present"
              value={
                globalStats.presentCount
              }
              color="#22C55E"
              bg="#F0FDF4"
              Icon={
                CheckCircle
              }
            />

            <StatTile
              label="Attendance %"
              value={`${globalStats.attendanceToday}%`}
              color="#F59E0B"
              bg="#FFFBEB"
              Icon={Activity}
            />

            <StatTile
              label="Pending"
              value={
                globalStats.pendingRecords
              }
              color="#EF4444"
              bg="#FEF2F2"
              Icon={XCircle}
            />
          </div>

          {/* Main Grid */}

          <div
            style={{
              display:
                'grid',

              gridTemplateColumns:
                '320px 1fr',

              gap: 20,

              alignItems:
                'start',
            }}
          >

            {/* Sidebar */}

            <div
              style={{
                display:
                  'flex',

                flexDirection:
                  'column',

                gap: 16,
              }}
            >

              {/* Class Selector */}

              <div
                style={{
                  borderRadius: 18,
                  border: '1px solid #e2e8f0',
                  background: '#fff',
                  padding: 12,
                }}
              >
                <p style={{ fontSize: '0.66rem', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
                  Select Class
                </p>

                <select
                  value={selectedClassId}
                  onChange={(e) => setSelectedClassId(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid #e2e8f0' }}
                >
                  <option value={CSE4C_META.class_id}>{CSE4C_META.display} · Sec C</option>
                </select>
                <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
                  <div style={{ fontSize: '0.65rem', color: '#64748b' }}>Timetable:</div>
                  <div style={{ fontSize: '0.68rem', fontWeight: 800, padding: '4px 8px', borderRadius: 999, background: timetableSource === 'remote' ? '#ECFDF5' : '#F8FAFC', color: timetableSource === 'remote' ? '#16A34A' : '#64748b', border: `1px solid ${timetableSource === 'remote' ? '#10B98133' : '#e2e8f0'}` }}>{timetableSource === 'remote' ? 'Remote' : 'Seeded'}</div>
                </div>
              </div>

              {/* Day Picker */}

              <div
                style={{
                  borderRadius:
                    18,

                  border:
                    '1px solid #e2e8f0',

                  background:
                    '#fff',

                  padding:
                    '16px',
                }}
              >
                <p
                  style={{
                    fontSize:
                      '0.66rem',

                    color:
                      '#94a3b8',

                    fontWeight: 700,

                    textTransform:
                      'uppercase',

                    letterSpacing:
                      '0.1em',

                    marginBottom: 10,
                  }}
                >
                  Select Day
                </p>

                <div
                  style={{
                    display:
                      'flex',

                    flexDirection:
                      'column',

                    gap: 6,
                  }}
                >
                  {DAYS.map(
                    (
                      day
                    ) => {

                      const count =
                        SEEDED_TIMETABLE.filter(
                          (
                            p
                          ) =>
                            p.day ===
                            day
                        )
                          .length;

                      const selected =
                        day ===
                        selectedDay;

                      return (
                        <button
                          key={
                            day
                          }
                          onClick={() =>
                            setSelectedDay(
                              day
                            )
                          }
                          style={{
                            display:
                              'flex',

                            justifyContent:
                              'space-between',

                            alignItems:
                              'center',

                            padding:
                              '9px 12px',

                            borderRadius:
                              10,

                            border:
                              'none',

                            cursor:
                              'pointer',

                            background:
                              selected
                                ? 'linear-gradient(135deg,#6366F1 0%,#818CF8 100%)'
                                : '#fff',

                            color:
                              selected
                                ? '#fff'
                                : '#475569',

                            fontWeight:
                              selected
                                ? 700
                                : 500,
                          }}
                        >
                          <span>
                            {
                              day
                            }
                          </span>

                          <span
                            style={{
                              fontSize:
                                '0.62rem',

                              padding:
                                '2px 7px',

                              borderRadius:
                                99,

                              background:
                                selected
                                  ? 'rgba(255,255,255,0.2)'
                                  : '#f1f5f9',
                            }}
                          >
                            {
                              count
                            }
                            P
                          </span>
                        </button>
                      );
                    }
                  )}
                </div>
              </div>

              {/* Periods */}

              <div
                style={{
                  borderRadius:
                    18,

                  border:
                    '1px solid #e2e8f0',

                  background:
                    '#fff',

                  padding:
                    '16px',

                  display:
                    'flex',

                  flexDirection:
                    'column',

                  gap: 10,
                }}
              >
                <p
                  style={{
                    fontSize:
                      '0.66rem',

                    color:
                      '#94a3b8',

                    fontWeight: 700,

                    textTransform:
                      'uppercase',

                    letterSpacing:
                      '0.1em',
                  }}
                >
                  {selectedDay}{' '}
                  Schedule
                </p>

                {dayPeriods.length ===
                0 ? (
                  <div
                    style={{
                      padding:
                        '24px',

                      textAlign:
                        'center',

                      color:
                        '#94a3b8',
                    }}
                  >
                    No periods
                    scheduled
                  </div>
                ) : (
                  dayPeriods.map(
                    (
                      p
                    ) => (
                      <PeriodCard
                        key={
                          p.period_id
                        }
                        period={
                          p
                        }
                        selected={
                          p.period_id ===
                          selectedPeriodId
                        }
                        onClick={() =>
                          setSelectedPeriodId(
                            p.period_id
                          )
                        }
                      />
                    )
                  )
                )}
              </div>
            </div>

            {/* Main Panel */}

            <div
              style={{
                borderRadius:
                  20,

                border:
                  '1px solid #e2e8f0',

                background:
                  '#fff',

                padding:
                  '22px',

                minHeight:
                  500,
              }}
            >
              {slotsLoading ? (
                <div
                  style={{
                    minHeight:
                      400,

                    display:
                      'flex',

                    alignItems:
                      'center',

                    justifyContent:
                      'center',
                  }}
                >
                  <div
                    style={{
                      width: 38,

                      height: 38,

                      border:
                        '3px solid #e2e8f0',

                      borderTopColor:
                        '#6366F1',

                      borderRadius:
                        '50%',

                      animation:
                        'spin .8s linear infinite',
                    }}
                  />
                </div>
              ) : (
                <AttendanceTable
                  slot={
                    selectedSlot
                  }
                />
              )}
            </div>
          </div>
        </div>

        <style>{`
          @keyframes spin {
            to {
              transform: rotate(360deg);
            }
          }

          @keyframes pulse {
            0%,100% {
              opacity: 1;
            }

            50% {
              opacity: 0.4;
            }
          }
        `}</style>
      </Layout>
    );
  };

export default DashboardPage;