// src/pages/AttendancePage.tsx

import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
} from 'react';

import { Layout } from '../components';
import {
  AttendanceSheet,
  TeacherPeriod,
} from '../components/AttendanceSheet';

import { attendanceAPI } from '../services/api';

import {
  BookOpen,
  Clock,
  Users,
  ChevronRight,
  AlertCircle,
  CheckCircle,
  Loader,
  RefreshCw,
  Calendar,
  Layers,
  Wifi,
  Beaker,
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const CLASS_OPTIONS = [
  {
    id: 'CSE-A-4SEM',
    label: 'CSE A — 4th Sem',
  },

  {
    id: 'CSE-B-4SEM',
    label: 'CSE B — 4th Sem',
  },

  {
    id: 'CSE-C-4SEM',
    label: 'CSE C — 4th Sem',
  },
];

const COURSE_COLORS = [
  '#6366F1',
  '#22C55E',
  '#F59E0B',
  '#EF4444',
  '#8B5CF6',
  '#14B8A6',
];

// ─────────────────────────────────────────────────────────────
// Static fallback roster
// ─────────────────────────────────────────────────────────────

const STATIC_STUDENTS: Record<
  string,
  Array<{
    student_id: string;
    roll_no: string;
    name: string;
  }>
> = {
  'CSE-A-4SEM': [
    {
      student_id:
        'STUD_001',
      roll_no: '4CS01',
      name:
        'Parikshith B Bilchode',
    },

    {
      student_id:
        'STUD_002',
      roll_no: '4CS02',
      name: 'Gagan D K',
    },

    {
      student_id:
        'STUD_003',
      roll_no: '4CS03',
      name: 'Prajwal K',
    },

    {
      student_id:
        'STUD_004',
      roll_no: '4CS04',
      name: 'Ved U',
    },

    {
      student_id:
        'STUD_005',
      roll_no: '4CS05',
      name:
        'Pranav Kumar M',
    },

    {
      student_id:
        'STUD_006',
      roll_no: '4CS06',
      name:
        'Nischith G A',
    },
  ],

  'CSE-B-4SEM': [
    {
      student_id:
        'STUD_007',
      roll_no: '4CS07',
      name:
        'Arjun Sharma',
    },

    {
      student_id:
        'STUD_008',
      roll_no: '4CS08',
      name:
        'Divya Nair',
    },
  ],

  'CSE-C-4SEM': [
    {
      student_id:
        'STUD_010',
      roll_no: '4CS10',
      name:
        'Sneha Patil',
    },
  ],
};

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

function todayISO() {
  return new Date()
    .toISOString()
    .slice(0, 10);
}

function nowMinutes() {
  const d = new Date();

  return (
    d.getHours() * 60 +
    d.getMinutes()
  );
}

function toMinutes(
  t: string
) {
  const [h, m] = t
    .split(':')
    .map(Number);

  return h * 60 + m;
}

function getPeriodState(
  start: string,
  end: string
) {
  const now =
    nowMinutes();

  const s =
    toMinutes(start);

  const e =
    toMinutes(end);

  if (now >= e)
    return 'past';

  if (now >= s)
    return 'active';

  return 'upcoming';
}

function formatTime(
  t: string
) {
  const [h, m] = t
    .split(':')
    .map(Number);

  const ampm =
    h >= 12
      ? 'PM'
      : 'AM';

  const hr =
    h > 12
      ? h - 12
      : h;

  return `${hr}:${m
    .toString()
    .padStart(
      2,
      '0'
    )} ${ampm}`;
}

// ─────────────────────────────────────────────────────────────
// Build Periods
// ─────────────────────────────────────────────────────────────

function buildPeriodOptions(
  classId: string
): TeacherPeriod[] {

  const courses = [
    {
      course_id:
        'CS401',

      course_code:
        'CS401',

      course_name:
        'Design & Analysis of Algorithms',
    },

    {
      course_id:
        'CS402',

      course_code:
        'CS402',

      course_name:
        'Operating Systems',
    },

    {
      course_id:
        'CS403',

      course_code:
        'CS403',

      course_name:
        'Computer Networks',
    },

    {
      course_id:
        'CS404',

      course_code:
        'CS404',

      course_name:
        'Database Management Systems',
    },

    {
      course_id:
        'CS405',

      course_code:
        'CS405',

      course_name:
        'Software Engineering',
    },
  ];

  const slots = [
    {
      hour: 1,
      start: '08:30',
      end: '09:30',
    },

    {
      hour: 2,
      start: '09:30',
      end: '10:30',
    },

    {
      hour: 3,
      start: '10:45',
      end: '11:45',
    },

    {
      hour: 4,
      start: '11:45',
      end: '12:45',
    },

    {
      hour: 5,
      start: '13:30',
      end: '14:30',
    },

    {
      hour: 6,
      start: '14:30',
      end: '15:30',
    },
  ];

  return slots.map(
    (
      slot,
      idx
    ) => ({
      period_id: `${classId}-P${slot.hour}`,

      class_id:
        classId,

      ...courses[
        idx %
          courses.length
      ],

      start_time:
        slot.start,

      end_time:
        slot.end,

      course_color:
        COURSE_COLORS[
          idx %
            COURSE_COLORS.length
        ],

      faculty_name:
        'Faculty',

      room: `LH-${
        idx + 1
      }`,

      is_lab_class:
        idx === 4,
    })
  );
}

// ─────────────────────────────────────────────────────────────
// Period Card
// ─────────────────────────────────────────────────────────────

interface PeriodCardProps {
  period: TeacherPeriod;

  selected: boolean;

  onClick: () => void;
}

function PeriodCard({
  period,
  selected,
  onClick,
}: PeriodCardProps) {

  const state =
    getPeriodState(
      period.start_time,
      period.end_time
    );

  const color =
    period.course_color ??
    '#6366F1';

  return (
    <button
      onClick={onClick}
      style={{
        textAlign:
          'left',

        borderRadius:
          16,

        padding: 16,

        border: `2px solid ${
          selected
            ? color
            : state ===
              'active'
            ? color
            : '#e2e8f0'
        }`,

        background:
          selected
            ? `${color}15`
            : '#fff',

        cursor:
          'pointer',

        transition:
          'all .15s ease',

        boxShadow:
          selected
            ? `0 8px 20px ${color}20`
            : '0 2px 6px rgba(0,0,0,.04)',
      }}
    >
      <div
        style={{
          display: 'flex',

          justifyContent:
            'space-between',

          marginBottom: 10,
        }}
      >
        <div
          style={{
            width: 38,

            height: 38,

            borderRadius:
              12,

            background:
              `${color}18`,

            display: 'flex',

            alignItems:
              'center',

            justifyContent:
              'center',
          }}
        >
          {period.is_lab_class ? (
            <Beaker
              size={17}
              style={{
                color,
              }}
            />
          ) : (
            <BookOpen
              size={17}
              style={{
                color,
              }}
            />
          )}
        </div>

        {state ===
          'active' && (
          <div
            style={{
              padding:
                '3px 8px',

              borderRadius:
                99,

              background:
                '#EEF2FF',

              color:
                '#4338CA',

              fontSize:
                '0.58rem',

              fontWeight: 700,
            }}
          >
            NOW
          </div>
        )}
      </div>

      <p
        style={{
          fontSize:
            '0.68rem',

          color,

          fontWeight: 800,

          letterSpacing:
            '0.08em',

          marginBottom: 5,
        }}
      >
        {
          period.course_code
        }
      </p>

      <h3
        style={{
          fontSize:
            '0.85rem',

          fontWeight: 700,

          color:
            '#1e293b',

          marginBottom: 8,
        }}
      >
        {
          period.course_name
        }
      </h3>

      <div
        style={{
          display: 'flex',

          alignItems:
            'center',

          gap: 5,

          fontSize:
            '0.7rem',

          color:
            '#64748b',
        }}
      >
        <Clock size={11} />

        {formatTime(
          period.start_time
        )}{' '}
        –
        {formatTime(
          period.end_time
        )}
      </div>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────

export const AttendancePage: React.FC =
  () => {

    const [
      step,
      setStep,
    ] = useState<
      | 'class'
      | 'period'
      | 'sheet'
    >('class');

    const [
      selectedClass,
      setSelectedClass,
    ] = useState('');

    const [
      selectedPeriod,
      setSelectedPeriod,
    ] =
      useState<TeacherPeriod | null>(
        null
      );

    const [
      students,
      setStudents,
    ] = useState<any[]>(
      []
    );

    const [
      loadingStudents,
      setLoadingStudents,
    ] =
      useState(false);

    const [
      studentsError,
      setStudentsError,
    ] = useState<
      string | null
    >(null);

    const [
      savedCount,
      setSavedCount,
    ] = useState<
      number | null
    >(null);

    const markedBy =
      localStorage.getItem(
        'user_id'
      ) ??
      localStorage.getItem(
        'user_email'
      ) ??
      'unknown';

    const periods =
      useMemo(
        () =>
          selectedClass
            ? buildPeriodOptions(
                selectedClass
              )
            : [],
        [selectedClass]
      );

    // refresh tick

    const [
      tick,
      setTick,
    ] = useState(
      Date.now()
    );

    useEffect(() => {

      const id =
        setInterval(
          () =>
            setTick(
              Date.now()
            ),
          30000
        );

      return () =>
        clearInterval(id);

    }, []);

    // load students

    const loadStudents =
      useCallback(
        async (
          classId: string
        ) => {

          setLoadingStudents(
            true
          );

          setStudentsError(
            null
          );

          try {

            const fetched =
              await attendanceAPI.getStudents(
                classId
              );

            if (
              fetched.length >
              0
            ) {

              setStudents(
                fetched.map(
                  (
                    s: any
                  ) => ({
                    student_id:
                      s.student_id ||
                      s.id,

                    roll_no:
                      s.roll_no ||
                      s.student_id,

                    name:
                      s.name,

                    photo_url:
                      s.avatar_url,
                  })
                )
              );

            } else {

              setStudents(
                STATIC_STUDENTS[
                  classId
                ] || []
              );
            }

          } catch {

            setStudentsError(
              'Using fallback student roster'
            );

            setStudents(
              STATIC_STUDENTS[
                classId
              ] || []
            );

          } finally {

            setLoadingStudents(
              false
            );
          }
        },
        []
      );

    useEffect(() => {

      if (
        selectedClass
      ) {
        loadStudents(
          selectedClass
        );
      }

    }, [
      selectedClass,
      loadStudents,
    ]);

    // handlers

    const handleClassSelect =
      (
        classId: string
      ) => {

        setSelectedClass(
          classId
        );

        setSelectedPeriod(
          null
        );

        setSavedCount(
          null
        );

        setStep(
          'period'
        );
      };

    const handlePeriodSelect =
      (
        p: TeacherPeriod
      ) => {

        setSelectedPeriod(
          p
        );

        setStep(
          'sheet'
        );
      };

    const handleSaved =
      (
        entries: any[]
      ) => {

        setSavedCount(
          entries.filter(
            (
              e
            ) =>
              e.status !==
              'not_marked'
          ).length
        );
      };

    const reset = () => {

      setSelectedClass(
        ''
      );

      setSelectedPeriod(
        null
      );

      setSavedCount(
        null
      );

      setStep(
        'class'
      );
    };

    const classLabel =
      CLASS_OPTIONS.find(
        (c) =>
          c.id ===
          selectedClass
      )?.label ??
      selectedClass;

    const activeCount =
      periods.filter(
        (p) =>
          getPeriodState(
            p.start_time,
            p.end_time
          ) ===
          'active'
      ).length;

    const upcomingCount =
      periods.filter(
        (p) =>
          getPeriodState(
            p.start_time,
            p.end_time
          ) ===
          'upcoming'
      ).length;

    const pastCount =
      periods.filter(
        (p) =>
          getPeriodState(
            p.start_time,
            p.end_time
          ) ===
          'past'
      ).length;

    return (
      <Layout>
        <div
          style={{
            maxWidth:
              1200,

            margin:
              '0 auto',

            display: 'flex',

            flexDirection:
              'column',

            gap: 22,
          }}
        >

          {/* Header */}

          <div
            style={{
              display: 'flex',

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
                    '0.65rem',

                  letterSpacing:
                    '0.14em',

                  fontWeight: 700,

                  color:
                    '#94a3b8',

                  textTransform:
                    'uppercase',

                  marginBottom: 5,
                }}
              >
                Teacher Portal
              </p>

              <h1
                style={{
                  fontSize:
                    '2rem',

                  fontWeight: 900,

                  color:
                    '#1e293b',
                }}
              >
                Mark Attendance
              </h1>

              <p
                style={{
                  marginTop: 6,

                  fontSize:
                    '0.82rem',

                  color:
                    '#64748b',
                }}
              >
                Hybrid realtime
                attendance with
                manual teacher
                overrides
              </p>
            </div>

            <div
              style={{
                display: 'flex',

                alignItems:
                  'center',

                gap: 7,

                padding:
                  '10px 14px',

                borderRadius:
                  14,

                background:
                  '#F0FDF4',

                border:
                  '1px solid #BBF7D0',

                height:
                  'fit-content',
              }}
            >
              <Wifi
                size={14}
                style={{
                  color:
                    '#22C55E',
                }}
              />

              <span
                style={{
                  fontSize:
                    '0.72rem',

                  fontWeight: 700,

                  color:
                    '#166534',
                }}
              >
                Live Sync
              </span>
            </div>
          </div>

          {/* Breadcrumb */}

          <div
            style={{
              display: 'flex',

              alignItems:
                'center',

              gap: 7,

              flexWrap:
                'wrap',
            }}
          >
            {[
              {
                label:
                  'Class',
                done:
                  step !==
                  'class',
              },

              {
                label:
                  'Period',
                done:
                  step ===
                  'sheet',
              },

              {
                label:
                  'Roster',
                done:
                  savedCount !==
                  null,
              },
            ].map(
              (
                s,
                idx
              ) => (
                <React.Fragment
                  key={
                    s.label
                  }
                >
                  {idx >
                    0 && (
                    <ChevronRight
                      size={
                        12
                      }
                      style={{
                        color:
                          '#cbd5e1',
                      }}
                    />
                  )}

                  <div
                    style={{
                      padding:
                        '4px 10px',

                      borderRadius:
                        99,

                      background:
                        s.done
                          ? '#F0FDF4'
                          : '#EEF2FF',

                      color:
                        s.done
                          ? '#166534'
                          : '#4338CA',

                      fontSize:
                        '0.72rem',

                      fontWeight: 700,
                    }}
                  >
                    {
                      s.label
                    }
                  </div>
                </React.Fragment>
              )
            )}
          </div>

          {/* Stats */}

          {selectedClass &&
            periods.length >
              0 && (
              <div
                style={{
                  display:
                    'flex',

                  gap: 10,

                  flexWrap:
                    'wrap',
                }}
              >
                {[
                  {
                    label:
                      'Total',

                    val:
                      periods.length,

                    bg:
                      '#EEF2FF',

                    hex:
                      '#6366F1',
                  },

                  {
                    label:
                      'Active',

                    val:
                      activeCount,

                    bg:
                      '#F0FDF4',

                    hex:
                      '#22C55E',
                  },

                  {
                    label:
                      'Upcoming',

                    val:
                      upcomingCount,

                    bg:
                      '#FFFBEB',

                    hex:
                      '#F59E0B',
                  },

                  {
                    label:
                      'Completed',

                    val:
                      pastCount,

                    bg:
                      '#F8FAFC',

                    hex:
                      '#94A3B8',
                  },
                ].map(
                  (
                    item
                  ) => (
                    <div
                      key={
                        item.label
                      }
                      style={{
                        padding:
                          '10px 14px',

                        borderRadius:
                          14,

                        background:
                          item.bg,

                        border: `1px solid ${item.hex}25`,
                      }}
                    >
                      <p
                        style={{
                          fontSize:
                            '1.1rem',

                          fontWeight: 900,

                          color:
                            item.hex,
                        }}
                      >
                        {
                          item.val
                        }
                      </p>

                      <p
                        style={{
                          fontSize:
                            '0.64rem',

                          color:
                            '#94a3b8',
                        }}
                      >
                        {
                          item.label
                        }
                      </p>
                    </div>
                  )
                )}
              </div>
            )}

          {/* Class Selection */}

          {step ===
            'class' && (
            <div
              style={{
                display:
                  'grid',

                gridTemplateColumns:
                  'repeat(auto-fit,minmax(240px,1fr))',

                gap: 14,
              }}
            >
              {CLASS_OPTIONS.map(
                (
                  cls
                ) => (
                  <button
                    key={
                      cls.id
                    }
                    onClick={() =>
                      handleClassSelect(
                        cls.id
                      )
                    }
                    style={{
                      borderRadius:
                        18,

                      padding:
                        '20px',

                      border:
                        '2px solid #e2e8f0',

                      background:
                        '#fff',

                      textAlign:
                        'left',

                      cursor:
                        'pointer',
                    }}
                  >
                    <div
                      style={{
                        width:
                          42,

                        height:
                          42,

                        borderRadius:
                          12,

                        background:
                          '#EEF2FF',

                        display:
                          'flex',

                        alignItems:
                          'center',

                        justifyContent:
                          'center',

                        marginBottom:
                          14,
                      }}
                    >
                      <Users
                        size={
                          20
                        }
                        style={{
                          color:
                            '#6366F1',
                        }}
                      />
                    </div>

                    <h3
                      style={{
                        fontSize:
                          '0.92rem',

                        fontWeight: 800,

                        color:
                          '#1e293b',
                      }}
                    >
                      {
                        cls.label
                      }
                    </h3>

                    <p
                      style={{
                        fontSize:
                          '0.7rem',

                        color:
                          '#94a3b8',

                        marginTop: 4,
                      }}
                    >
                      {
                        STATIC_STUDENTS[
                          cls.id
                        ]
                          ?.length
                      }{' '}
                      students
                    </p>
                  </button>
                )
              )}
            </div>
          )}

          {/* Period Selection */}

          {step ===
            'period' && (
            <div
              style={{
                display:
                  'flex',

                flexDirection:
                  'column',

                gap: 16,
              }}
            >

              {loadingStudents && (
                <div
                  style={{
                    display:
                      'flex',

                    alignItems:
                      'center',

                    gap: 8,

                    padding:
                      '10px 14px',

                    borderRadius:
                      12,

                    background:
                      '#EEF2FF',

                    color:
                      '#4338CA',
                  }}
                >
                  <Loader
                    size={14}
                    style={{
                      animation:
                        'spin .8s linear infinite',
                    }}
                  />

                  Loading
                  students...
                </div>
              )}

              {studentsError && (
                <div
                  style={{
                    display:
                      'flex',

                    alignItems:
                      'center',

                    gap: 8,

                    padding:
                      '10px 14px',

                    borderRadius:
                      12,

                    background:
                      '#FFFBEB',

                    color:
                      '#92400E',
                  }}
                >
                  <AlertCircle
                    size={14}
                  />

                  {
                    studentsError
                  }
                </div>
              )}

              <div
                style={{
                  display:
                    'grid',

                  gridTemplateColumns:
                    'repeat(auto-fit,minmax(240px,1fr))',

                  gap: 14,
                }}
              >
                {periods.map(
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
                        selectedPeriod?.period_id ===
                        p.period_id
                      }
                      onClick={() =>
                        handlePeriodSelect(
                          p
                        )
                      }
                    />
                  )
                )}
              </div>
            </div>
          )}

          {/* Sheet */}

          {step ===
            'sheet' &&
            selectedPeriod && (
              <div
                style={{
                  display:
                    'flex',

                  flexDirection:
                    'column',

                  gap: 14,
                }}
              >

                <div
                  style={{
                    display:
                      'flex',

                    alignItems:
                      'center',

                    justifyContent:
                      'space-between',

                    flexWrap:
                      'wrap',

                    gap: 12,

                    padding:
                      '14px 18px',

                    borderRadius:
                      16,

                    background:
                      '#F8FAFF',

                    border:
                      '1px solid #C7D2FE',
                  }}
                >
                  <div>
                    <p
                      style={{
                        fontSize:
                          '0.64rem',

                        fontWeight: 700,

                        color:
                          '#6366F1',

                        letterSpacing:
                          '0.08em',

                        textTransform:
                          'uppercase',
                      }}
                    >
                      {
                        classLabel
                      }
                    </p>

                    <h3
                      style={{
                        fontSize:
                          '0.95rem',

                        fontWeight: 800,

                        color:
                          '#1e293b',

                        marginTop: 3,
                      }}
                    >
                      {
                        selectedPeriod.course_code
                      }{' '}
                      —{' '}
                      {
                        selectedPeriod.course_name
                      }
                    </h3>
                  </div>

                  <div
                    style={{
                      display:
                        'flex',

                      gap: 14,

                      flexWrap:
                        'wrap',
                    }}
                  >
                    <div
                      style={{
                        display:
                          'flex',

                        alignItems:
                          'center',

                        gap: 5,

                        fontSize:
                          '0.75rem',

                        color:
                          '#64748b',
                      }}
                    >
                      <Clock
                        size={
                          13
                        }
                      />

                      {
                        selectedPeriod.start_time
                      }
                      –
                      {
                        selectedPeriod.end_time
                      }
                    </div>

                    <div
                      style={{
                        display:
                          'flex',

                        alignItems:
                          'center',

                        gap: 5,

                        fontSize:
                          '0.75rem',

                        color:
                          '#64748b',
                      }}
                    >
                      <Users
                        size={
                          13
                        }
                      />

                      {
                        students.length
                      }{' '}
                      students
                    </div>
                  </div>
                </div>

                {savedCount !==
                  null && (
                  <div
                    style={{
                      display:
                        'flex',

                      alignItems:
                        'center',

                      gap: 8,

                      padding:
                        '12px 16px',

                      borderRadius:
                        12,

                      background:
                        '#F0FDF4',

                      border:
                        '1px solid #BBF7D0',
                    }}
                  >
                    <CheckCircle
                      size={15}
                      style={{
                        color:
                          '#22C55E',
                      }}
                    />

                    <span
                      style={{
                        fontSize:
                          '0.8rem',

                        fontWeight: 700,

                        color:
                          '#166534',
                      }}
                    >
                      Session
                      saved —
                      {
                        savedCount
                      }{' '}
                      attendance
                      records
                      committed
                    </span>
                  </div>
                )}

                <AttendanceSheet
                  period={
                    selectedPeriod
                  }
                  markedBy={
                    markedBy
                  }
                  students={
                    students
                  }
                  onSaved={
                    handleSaved
                  }
                />
              </div>
            )}

          {/* Reset */}

          {step !==
            'class' && (
            <button
              onClick={reset}
              style={{
                alignSelf:
                  'flex-start',

                display:
                  'flex',

                alignItems:
                  'center',

                gap: 6,

                padding:
                  '10px 14px',

                borderRadius:
                  12,

                background:
                  '#fff',

                border:
                  '1.5px solid #e2e8f0',

                color:
                  '#64748b',

                cursor:
                  'pointer',

                fontWeight: 600,
              }}
            >
              <RefreshCw
                size={13}
              />

              Start Over
            </button>
          )}
        </div>

        <style>{`
          @keyframes spin {
            to {
              transform: rotate(360deg);
            }
          }
        `}</style>
      </Layout>
    );
  };

export default AttendancePage;