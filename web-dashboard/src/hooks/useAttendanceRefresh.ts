/**
 * useAttendanceRefresh.ts
 *
 * Intelligent refresh + eligibility hook:
 * - Auto-polls dashboard/history data after attendance is marked
 * - Checks if current time is within any student's timetabled periods
 * - Only allows attendance marking during valid time windows
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { apiClient } from '../services/api';
import type { TimetableData } from '../hooks/useAttendanceHooks';

export interface AttendanceEligibility {
  isEligible: boolean;
  reason?: string;
  currentPeriod?: {
    period_id: string;
    course_code: string;
    course_name: string;
    start_time: string;
    end_time: string;
  };
  nextPeriod?: {
    period_id: string;
    course_code: string;
    start_time: string;
  };
}

/**
 * Check if a time HH:MM falls between start and end times (with 5-min grace).
 * Grace allows marking 5 min before period starts.
 */
export function isTimeInWindow(
  now: Date,
  startTime: string,
  endTime: string,
  graceMins = 5
): boolean {
  const nowMins = now.getHours() * 60 + now.getMinutes();
  const [sh, sm] = startTime.split(':').map(Number);
  const [eh, em] = endTime.split(':').map(Number);
  const startMins = sh * 60 + sm - graceMins;
  const endMins = eh * 60 + em + 5; // 5 min after period ends for late arrivals

  return nowMins >= startMins && nowMins <= endMins;
}

/**
 * Get the day name from a date (Monday, Tuesday, etc.)
 */
function getDayName(date: Date): string {
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  return days[date.getDay()];
}

/**
 * Hook: Check current eligibility to mark attendance based on timetable.
 * Returns whether it's within a scheduled period + details.
 */
export function useAttendanceEligibility(): AttendanceEligibility & {
  loading: boolean;
  refetch: () => Promise<void>;
} {
  const [eligibility, setEligibility] = useState<AttendanceEligibility>({ isEligible: false });
  const [loading, setLoading] = useState(false);

  const check = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get<TimetableData>('/api/v1/student/timetable');
      const result = response.data;
      const days = result?.days ?? {};
      const now = new Date();
      const todayName = getDayName(now);
      const todaysPeriods = (days[todayName] ?? []) as Array<{
        period_id: string;
        course_code: string;
        course_name: string;
        start_time: string;
        end_time: string;
      }>;

      if (!todaysPeriods.length) {
        setEligibility({
          isEligible: false,
          reason: `No classes scheduled for ${todayName}`,
        });
        return;
      }

      const activePeriod = todaysPeriods.find((p) =>
        p.start_time && p.end_time && isTimeInWindow(now, p.start_time, p.end_time)
      );

      if (activePeriod) {
        setEligibility({
          isEligible: true,
          currentPeriod: {
            period_id: activePeriod.period_id,
            course_code: activePeriod.course_code,
            course_name: activePeriod.course_name,
            start_time: activePeriod.start_time || '',
            end_time: activePeriod.end_time || '',
          },
        });
        return;
      }

      const sortedPeriods = [...todaysPeriods]
        .filter((p) => p.start_time && p.end_time)
        .sort((a, b) => {
          const aMins = parseInt(a.start_time.split(':')[0]) * 60 + parseInt(a.start_time.split(':')[1]);
          const bMins = parseInt(b.start_time.split(':')[0]) * 60 + parseInt(b.start_time.split(':')[1]);
          return aMins - bMins;
        });

      const nowMins = now.getHours() * 60 + now.getMinutes();
      const upcomingPeriod = sortedPeriods.find((p) => {
        const [h, m] = p.start_time.split(':').map(Number);
        return h * 60 + m > nowMins;
      });

      if (upcomingPeriod) {
        setEligibility({
          isEligible: false,
          reason: `No active class now. Next: ${upcomingPeriod.course_code} at ${upcomingPeriod.start_time}`,
          nextPeriod: {
            period_id: upcomingPeriod.period_id,
            course_code: upcomingPeriod.course_code,
            start_time: upcomingPeriod.start_time || '',
          },
        });
        return;
      }

      setEligibility({
        isEligible: false,
        reason: 'All classes for today have ended',
      });
    } catch (err) {
      console.error('[useAttendanceEligibility] Error:', err);
      setEligibility({
        isEligible: false,
        reason: 'Error checking eligibility',
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void check();
    // Re-check every 30 seconds
    const interval = setInterval(() => void check(), 30_000);
    return () => clearInterval(interval);
  }, [check]);

  return { ...eligibility, loading, refetch: check };
}

/**
 * Hook: Auto-refresh dashboard/history after attendance marking.
 * Polls the given refetch function a few times after marking.
 */
export function usePostMarkRefresh(onMarked?: () => void) {
  const pollerRef = useRef<NodeJS.Timeout | null>(null);
  const markCountRef = useRef(0);

  return useCallback(() => {
    // Called when attendance is marked
    markCountRef.current = 0;

    // Refetch immediately + 3 more times in 2s intervals
    if (onMarked) onMarked();

    try {
      window.dispatchEvent(new CustomEvent('attendance:marked'));
      window.dispatchEvent(new CustomEvent('attendance:updated'));
      window.localStorage.setItem('attendance_last_updated', new Date().toISOString());
    } catch (err) {
      // ignore in non-browser or restricted envs
    }

    pollerRef.current = setInterval(() => {
      markCountRef.current += 1;
      if (onMarked) onMarked();

      if (markCountRef.current >= 3) {
        if (pollerRef.current) clearInterval(pollerRef.current);
        pollerRef.current = null;
      }
    }, 2000);

    return () => {
      if (pollerRef.current) {
        clearInterval(pollerRef.current);
        pollerRef.current = null;
      }
    };
  }, [onMarked]);
}

/**
 * Hook: Enable continuous polling of dashboard/analytics/history pages.
 * Call this to keep data fresh without user interaction.
 */
export function useContiniousAttendancePolling(
  enabled: boolean,
  onRefresh: () => Promise<void>,
  intervalMs = 10_000 // 10s default
) {
  const pollerRef = useRef<NodeJS.Timeout | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<Date | null>(null);

  useEffect(() => {
    if (!enabled) {
      if (pollerRef.current) clearInterval(pollerRef.current);
      return;
    }

    // Fetch immediately
    void onRefresh().then(() => setLastRefreshAt(new Date()));

    // Then poll
    pollerRef.current = setInterval(() => {
      void onRefresh().then(() => setLastRefreshAt(new Date()));
    }, intervalMs);

    return () => {
      if (pollerRef.current) clearInterval(pollerRef.current);
    };
  }, [enabled, onRefresh, intervalMs]);

  return { lastRefreshAt };
}
