import { useCallback, useEffect, useMemo, useState } from 'react';
import dashboardService from '../services/dashboardService';
import type {
  AttendanceMatrixResponse,
  AttendanceRoleSummaryResponse,
} from '../types/analytics';

export function useAttendanceMatrix(classId?: string, weekStart?: string) {
  const [data, setData] = useState<AttendanceMatrixResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMatrix = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await dashboardService.getAttendanceMatrix({ classId, weekStart });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load attendance matrix');
    } finally {
      setIsLoading(false);
    }
  }, [classId, weekStart]);

  useEffect(() => {
    void fetchMatrix();
  }, [fetchMatrix]);

  const rows = useMemo(() => data?.rows ?? [], [data]);

  return {
    data,
    rows,
    isLoading,
    error,
    refetch: fetchMatrix,
  };
}

export function useRoleSummary(enabled = true) {
  const [data, setData] = useState<AttendanceRoleSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    if (!enabled) {
      setData(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const result = await dashboardService.getRoleSummary();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load role summary');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSummary();
  }, [fetchSummary]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchSummary,
  };
}
