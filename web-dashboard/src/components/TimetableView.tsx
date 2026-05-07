// src/components/TimetableView.tsx

/**
 * FINAL MERGED VERSION
 *
 * Combines:
 * ✅ Real UG CSE 4C seeded timetable
 * ✅ Offline-safe local architecture
 * ✅ Loading + retry support
 * ✅ Day filtering
 * ✅ Today highlighting
 * ✅ Faculty + room metadata
 * ✅ Lab indicators
 * ✅ Compact period reference
 * ✅ Production-ready timetable UI
 */

import React, {
  useMemo,
  useState,
} from 'react';

import {
  BookOpen,
  Clock,
  MapPin,
  User,
} from 'lucide-react';

import {
  useCSE4CTimetableLocal,
  SEEDED_TIMETABLE,
  CSE4C_META,
  type PeriodCard,
} from '../hooks/useAttendanceHooks';

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const DAYS = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

const TODAY_IDX = (() => {
  const d = new Date().getDay();
  return d === 0 ? -1 : d - 1;
})();

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

function toMinutes(
  t: string
): number {

  const [h, m] =
    t
      .split(':')
      .map(Number);

  return h * 60 + m;
}

function minutesToLabel(
  m: number
): string {

  const h =
    Math.floor(m / 60);

  const min =
    m % 60;

  const ampm =
    h < 12
      ? 'AM'
      : 'PM';

  const h12 =
    h === 0
      ? 12
      : h > 12
      ? h - 12
      : h;

  return `${h12}:${min
    .toString()
    .padStart(2, '0')} ${ampm}`;
}

// ─────────────────────────────────────────────────────────────
// Period Block
// ─────────────────────────────────────────────────────────────

function PeriodBlock({
  period,
  rowSpan,
}: {
  period: PeriodCard;
  rowSpan: number;
}) {

  const [
    hovered,
    setHovered,
  ] = useState(false);

  return (
    <div
      onMouseEnter={() =>
        setHovered(true)
      }
      onMouseLeave={() =>
        setHovered(false)
      }
      style={{
        height: '100%',

        borderRadius: 12,

        background:
          hovered
            ? `linear-gradient(135deg, ${period.course_color}28, ${period.course_color}18)`
            : `linear-gradient(135deg, ${period.course_color}18, ${period.course_color}0a)`,

        border: `1.5px solid ${
          hovered
            ? period.course_color + '60'
            : period.course_color + '35'
        }`,

        padding: '8px 10px',

        overflow: 'hidden',

        cursor: 'default',

        transition:
          'all 0.2s ease',

        transform:
          hovered
            ? 'scale(1.01)'
            : 'scale(1)',

        boxShadow:
          hovered
            ? `0 4px 16px ${period.course_color}25`
            : 'none',

        position: 'relative',
      }}
    >

      {/* Accent */}

      <div
        style={{
          position:
            'absolute',

          left: 0,
          top: 0,
          bottom: 0,

          width: 4,

          background:
            period.course_color,

          borderRadius:
            '12px 0 0 12px',
        }}
      />

      <div
        style={{
          paddingLeft: 6,
        }}
      >

        {/* Code */}

        <div
          style={{
            display: 'flex',
            alignItems:
              'center',

            gap: 5,

            marginBottom: 4,
          }}
        >

          <span
            style={{
              fontSize:
                '0.64rem',

              fontWeight: 800,

              letterSpacing:
                '0.08em',

              textTransform:
                'uppercase',

              color:
                period.course_color,
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
                  '0.54rem',

                padding:
                  '1px 5px',

                borderRadius: 4,

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
        </div>

        {/* Name */}

        <p
          style={{
            fontSize:
              '0.75rem',

            fontWeight: 700,

            color:
              '#1e293b',

            lineHeight: 1.2,

            overflow:
              'hidden',

            display:
              '-webkit-box',

            WebkitLineClamp:
              rowSpan >= 3
                ? 2
                : 1,

            WebkitBoxOrient:
              'vertical',
          }}
        >
          {
            period.course_name
          }
        </p>

        {/* Meta */}

        {rowSpan >= 2 && (
          <div
            style={{
              marginTop: 6,

              display: 'flex',

              flexDirection:
                'column',

              gap: 2,
            }}
          >

            {period.faculty_name && (
              <div
                style={{
                  display: 'flex',
                  alignItems:
                    'center',

                  gap: 4,

                  fontSize:
                    '0.62rem',

                  color:
                    '#64748b',
                }}
              >
                <User size={9} />

                <span>
                  {
                    period.faculty_name
                  }
                </span>
              </div>
            )}

            <div
              style={{
                display: 'flex',
                alignItems:
                  'center',

                gap: 4,

                fontSize:
                  '0.62rem',

                color:
                  '#64748b',
              }}
            >
              <Clock size={9} />

              <span>
                {
                  period.start_time
                }
                –
                {
                  period.end_time
                }
              </span>
            </div>

            {period.room && (
              <div
                style={{
                  display: 'flex',
                  alignItems:
                    'center',

                  gap: 4,

                  fontSize:
                    '0.62rem',

                  color:
                    '#94a3b8',
                }}
              >
                <MapPin size={9} />

                <span>
                  {
                    period.room
                  }
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Legend
// ─────────────────────────────────────────────────────────────

function CourseLegend({
  courses,
}: {
  courses: Record<
    string,
    {
      name: string;
      color: string;
    }
  >;
}) {

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
      }}
    >
      {Object.entries(
        courses
      ).map(
        ([
          code,
          meta,
        ]) => (
          <div
            key={code}
            style={{
              display: 'flex',
              alignItems:
                'center',

              gap: 6,

              padding:
                '4px 10px',

              borderRadius: 99,

              background:
                meta.color +
                '15',

              border: `1px solid ${meta.color}35`,
            }}
          >

            <span
              style={{
                width: 8,
                height: 8,

                borderRadius:
                  '50%',

                background:
                  meta.color,
              }}
            />

            <span
              style={{
                fontSize:
                  '0.7rem',

                fontWeight: 700,

                color:
                  meta.color,
              }}
            >
              {code}
            </span>

            <span
              style={{
                fontSize:
                  '0.62rem',

                color:
                  '#64748b',

                maxWidth:
                  120,

                whiteSpace:
                  'nowrap',

                overflow:
                  'hidden',

                textOverflow:
                  'ellipsis',
              }}
            >
              {
                meta.name
              }
            </span>
          </div>
        )
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────

interface TimetableViewProps {
  studentId?: string;
}

export const TimetableView: React.FC<
  TimetableViewProps
> = () => {

  const data =
    useCSE4CTimetableLocal();

  const [
    focusDay,
    setFocusDay,
  ] =
    useState<
      number | null
    >(null);

  // ─────────────────────────────────────────
  // Build Time Grid
  // ─────────────────────────────────────────

  const {
    timeSlots,
  } = useMemo(() => {

    let minMin =
      24 * 60;

    let maxMin = 0;

    SEEDED_TIMETABLE.forEach(
      (
        sp
      ) => {

        minMin =
          Math.min(
            minMin,
            toMinutes(
              sp.start_time
            )
          );

        maxMin =
          Math.max(
            maxMin,
            toMinutes(
              sp.end_time
            )
          );
      }
    );

    if (
      minMin >= maxMin
    ) {

      return {
        timeSlots:
          [] as string[],
      };
    }

    const SLOT = 30;

    const slots: string[] =
      [];

    for (
      let m = minMin;
      m < maxMin;
      m += SLOT
    ) {

      const key =
        `${Math.floor(
          m / 60
        )
          .toString()
          .padStart(
            2,
            '0'
          )}:${(
          m % 60
        )
          .toString()
          .padStart(
            2,
            '0'
          )}`;

      slots.push(key);
    }

    return {
      timeSlots: slots,
    };

  }, []);

  // ─────────────────────────────────────────
  // Loading
  // ─────────────────────────────────────────

  if (
    data.loading
  ) {

    return (
      <div
        style={{
          display: 'flex',

          alignItems:
            'center',

          justifyContent:
            'center',

          minHeight: 220,

          gap: 12,
        }}
      >

        <div
          style={{
            width: 32,
            height: 32,

            border:
              '3px solid #e2e8f0',

            borderTopColor:
              '#6366F1',

            borderRadius:
              '50%',

            animation:
              'spin 0.8s linear infinite',
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
          Loading timetable…
        </p>
      </div>
    );
  }

  // ─────────────────────────────────────────
  // Error
  // ─────────────────────────────────────────

  if (
    data.error
  ) {

    return (
      <div
        style={{
          padding: 20,

          borderRadius: 14,

          background:
            '#fef2f2',

          border:
            '1px solid #fecaca',

          color:
            '#dc2626',

          display: 'flex',

          alignItems:
            'center',

          gap: 10,
        }}
      >

        <span
          style={{
            fontSize:
              '0.85rem',
          }}
        >
          {
            data.error
          }
        </span>

        <button
          onClick={
            data.refetch
          }
          style={{
            marginLeft:
              'auto',

            fontSize:
              '0.8rem',

            color:
              '#6366F1',

            fontWeight: 700,

            background:
              'none',

            border:
              'none',

            cursor:
              'pointer',
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  const SLOT = 30;

  const visibleDays =
    focusDay !== null
      ? [
          DAYS[
            focusDay
          ],
        ]
      : DAYS;

  // ─────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────

  return (
    <div
      style={{
        display: 'flex',
        flexDirection:
          'column',

        gap: 20,
      }}
    >

      {/* Header */}

      <div
        style={{
          display: 'flex',

          alignItems:
            'flex-start',

          justifyContent:
            'space-between',

          flexWrap: 'wrap',

          gap: 12,
        }}
      >

        <div>

          <h2
            style={{
              fontSize:
                '1.3rem',

              fontWeight: 800,

              color:
                '#1e293b',
            }}
          >
            Weekly Timetable
          </h2>

          <p
            style={{
              fontSize:
                '0.75rem',

              color:
                '#94a3b8',

              marginTop: 3,
            }}
          >
            {
              CSE4C_META.display
            }
            {' · '}
            Semester{' '}
            {
              CSE4C_META.semester
            }
            {' · '}
            {
              CSE4C_META.batch
            }
            {' · '}
            Room{' '}
            {
              CSE4C_META.room
            }
          </p>
        </div>

        {/* Filters */}

        <div
          style={{
            display: 'flex',
            gap: 6,
            flexWrap:
              'wrap',
          }}
        >

          <button
            onClick={() =>
              setFocusDay(
                null
              )
            }
            style={{
              padding:
                '5px 12px',

              borderRadius:
                99,

              fontSize:
                '0.72rem',

              fontWeight: 700,

              cursor:
                'pointer',

              background:
                focusDay ===
                null
                  ? '#6366F1'
                  : '#f1f5f9',

              color:
                focusDay ===
                null
                  ? '#fff'
                  : '#64748b',

              border: `1px solid ${
                focusDay ===
                null
                  ? '#6366F1'
                  : '#e2e8f0'
              }`,
            }}
          >
            All
          </button>

          {DAYS.map(
            (
              d,
              i
            ) => {

              const hasPeriods =
                SEEDED_TIMETABLE.some(
                  (
                    sp
                  ) =>
                    sp.day ===
                    d
                );

              return (
                <button
                  key={d}
                  onClick={() =>
                    setFocusDay(
                      focusDay ===
                        i
                        ? null
                        : i
                    )
                  }
                  style={{
                    padding:
                      '5px 12px',

                    borderRadius:
                      99,

                    fontSize:
                      '0.72rem',

                    fontWeight: 700,

                    cursor:
                      'pointer',

                    background:
                      focusDay ===
                      i
                        ? '#6366F1'
                        : i ===
                          TODAY_IDX
                        ? '#EEF2FF'
                        : '#f1f5f9',

                    color:
                      focusDay ===
                      i
                        ? '#fff'
                        : i ===
                          TODAY_IDX
                        ? '#6366F1'
                        : hasPeriods
                        ? '#64748b'
                        : '#cbd5e1',

                    border: `1px solid ${
                      focusDay ===
                      i
                        ? '#6366F1'
                        : i ===
                          TODAY_IDX
                        ? '#A5B4FC'
                        : '#e2e8f0'
                    }`,
                  }}
                >
                  {d.slice(
                    0,
                    3
                  )}
                </button>
              );
            }
          )}
        </div>
      </div>

      {/* Legend */}

      <CourseLegend
        courses={
          data.all_courses
        }
      />

      {/* Grid */}

      {timeSlots.length >
        0 && (
        <div
          style={{
            overflowX:
              'auto',

            borderRadius:
              16,

            border:
              '1px solid #e2e8f0',
          }}
        >

          <div
            style={{
              display:
                'grid',

              gridTemplateColumns: `64px repeat(${visibleDays.length}, minmax(130px, 1fr))`,

              gridTemplateRows: `40px repeat(${timeSlots.length}, 34px)`,

              minWidth: `${
                64 +
                visibleDays.length *
                  130
              }px`,
            }}
          >

            {/* Corner */}

            <div
              style={{
                gridColumn: 1,
                gridRow: 1,

                background:
                  '#f8fafc',

                borderBottom:
                  '1px solid #e2e8f0',

                borderRight:
                  '1px solid #e2e8f0',
              }}
            />

            {/* Headers */}

            {visibleDays.map(
              (
                day,
                di
              ) => {

                const origIdx =
                  DAYS.indexOf(
                    day
                  );

                const isToday =
                  origIdx ===
                  TODAY_IDX;

                return (
                  <div
                    key={day}
                    style={{
                      gridColumn:
                        di + 2,

                      gridRow: 1,

                      display:
                        'flex',

                      alignItems:
                        'center',

                      justifyContent:
                        'center',

                      background:
                        isToday
                          ? '#EEF2FF'
                          : '#f8fafc',

                      borderBottom:
                        '1px solid #e2e8f0',

                      borderRight:
                        di <
                        visibleDays.length -
                          1
                          ? '1px solid #e2e8f0'
                          : 'none',
                    }}
                  >

                    <span
                      style={{
                        fontSize:
                          '0.74rem',

                        fontWeight:
                          isToday
                            ? 800
                            : 700,

                        color:
                          isToday
                            ? '#6366F1'
                            : '#64748b',
                      }}
                    >
                      {day
                        .slice(
                          0,
                          3
                        )
                        .toUpperCase()}
                    </span>
                  </div>
                );
              }
            )}

            {/* Time */}

            {timeSlots.map(
              (
                slot,
                si
              ) => (
                <div
                  key={slot}
                  style={{
                    gridColumn: 1,
                    gridRow:
                      si + 2,

                    display:
                      'flex',

                    alignItems:
                      'flex-start',

                    justifyContent:
                      'flex-end',

                    paddingRight: 10,

                    paddingTop: 4,

                    borderRight:
                      '1px solid #e2e8f0',
                  }}
                >

                  {si % 2 ===
                    0 && (
                    <span
                      style={{
                        fontSize:
                          '0.58rem',

                        color:
                          '#94a3b8',

                        fontWeight: 700,
                      }}
                    >
                      {minutesToLabel(
                        toMinutes(
                          slot
                        )
                      )}
                    </span>
                  )}
                </div>
              )
            )}

            {/* Cells */}

            {visibleDays.map(
              (
                d,
                di
              ) =>
                timeSlots.map(
                  (
                    _,
                    si
                  ) => (
                    <div
                      key={`bg-${di}-${si}`}
                      style={{
                        gridColumn:
                          di + 2,

                        gridRow:
                          si + 2,

                        borderRight:
                          di <
                          visibleDays.length -
                            1
                            ? '1px solid #f1f5f9'
                            : 'none',

                        background:
                          DAYS.indexOf(
                            d
                          ) ===
                          TODAY_IDX
                            ? '#FAFBFF'
                            : '#fff',
                      }}
                    />
                  )
                )
            )}

            {/* Periods */}

            {visibleDays.map(
              (
                day,
                di
              ) => {

                const periods =
                  data.days[
                    day
                  ] ?? [];

                return periods.map(
                  (
                    p
                  ) => {

                    const startMin =
                      toMinutes(
                        p.start_time
                      );

                    const endMin =
                      toMinutes(
                        p.end_time
                      );

                    const slotStart =
                      toMinutes(
                        timeSlots[0]
                      );

                    const rowStart =
                      Math.floor(
                        (
                          startMin -
                          slotStart
                        ) /
                          SLOT
                      ) + 2;

                    const rowSpan =
                      Math.max(
                        1,
                        Math.round(
                          (
                            endMin -
                            startMin
                          ) /
                            SLOT
                        )
                      );

                    return (
                      <div
                        key={
                          p.period_id
                        }
                        style={{
                          gridColumn:
                            di + 2,

                          gridRowStart:
                            rowStart,

                          gridRowEnd: `span ${rowSpan}`,

                          padding: 3,

                          zIndex: 1,
                        }}
                      >
                        <PeriodBlock
                          period={
                            p
                          }
                          rowSpan={
                            rowSpan
                          }
                        />
                      </div>
                    );
                  }
                );
              }
            )}
          </div>
        </div>
      )}

      {/* Period Reference */}

      <div>

        <p
          style={{
            fontSize:
              '0.65rem',

            fontWeight: 800,

            color:
              '#94a3b8',

            textTransform:
              'uppercase',

            letterSpacing:
              '0.1em',

            marginBottom: 12,
          }}
        >
          Period Reference
        </p>

        <div
          style={{
            display: 'grid',

            gridTemplateColumns:
              'repeat(auto-fill, minmax(220px, 1fr))',

            gap: 8,
          }}
        >

          {SEEDED_TIMETABLE.map(
            (
              sp
            ) => (
              <div
                key={
                  sp.period_id
                }
                style={{
                  display: 'flex',

                  alignItems:
                    'center',

                  gap: 10,

                  padding:
                    '10px 12px',

                  borderRadius:
                    12,

                  background: `${sp.course_color}0a`,

                  border: `1px solid ${sp.course_color}25`,
                }}
              >

                <div
                  style={{
                    width: 8,
                    height: 8,

                    borderRadius:
                      '50%',

                    background:
                      sp.course_color,
                  }}
                />

                <div
                  style={{
                    flex: 1,
                    minWidth: 0,
                  }}
                >

                  <div
                    style={{
                      display:
                        'flex',

                      alignItems:
                        'center',

                      gap: 5,

                      marginBottom: 1,
                    }}
                  >

                    <span
                      style={{
                        fontSize:
                          '0.65rem',

                        fontWeight: 800,

                        color:
                          sp.course_color,
                      }}
                    >
                      {
                        sp.course_code
                      }
                    </span>

                    {sp.is_lab_class && (
                      <span
                        style={{
                          fontSize:
                            '0.55rem',

                          padding:
                            '1px 4px',

                          borderRadius: 3,

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
                  </div>

                  <p
                    style={{
                      fontSize:
                        '0.7rem',

                      color:
                        '#64748b',

                      whiteSpace:
                        'nowrap',

                      overflow:
                        'hidden',

                      textOverflow:
                        'ellipsis',
                    }}
                  >
                    {sp.day.slice(
                      0,
                      3
                    )}
                    {' · '}
                    {
                      sp.start_time
                    }
                    –
                    {
                      sp.end_time
                    }
                  </p>
                </div>
              </div>
            )
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
};

export default TimetableView;