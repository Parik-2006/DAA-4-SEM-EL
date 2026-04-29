import { useEffect, useState } from 'react';
import { attendanceAPI } from '../services/api';

interface UseBackendHealthOptions {
  enabled?: boolean;
  onHealthy?: () => void;
  onUnhealthy?: () => void;
  maxRetries?: number;
}

/**
 * Hook to wait for backend to be healthy before rendering content
 * Usage:
 *   const { isHealthy, isLoading } = useBackendHealth();
 *   if (isLoading) return <LoadingSpinner />;
 *   if (!isHealthy) return <ErrorMessage />;
 *   return <YourContent />;
 */
export function useBackendHealth(options: UseBackendHealthOptions = {}) {
  const {
    enabled = true,
    onHealthy,
    onUnhealthy,
    maxRetries = 30,
  } = options;

  const [isHealthy, setIsHealthy] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }

    const checkBackendHealth = async () => {
      try {
        setError(null);
        console.log('[useBackendHealth] Starting health check...');
        await attendanceAPI.waitForBackend(maxRetries);
        setIsHealthy(true);
        setIsLoading(false);
        onHealthy?.();
        console.log('[useBackendHealth] Backend is healthy!');
      } catch (err) {
        console.error('[useBackendHealth] Backend health check failed:', err);
        setError('Backend service is not available. Some features may not work.');
        setIsHealthy(false);
        setIsLoading(false);
        onUnhealthy?.();
      }
    };

    checkBackendHealth();
  }, [enabled, maxRetries, onHealthy, onUnhealthy]);

  return { isHealthy, isLoading, error };
}

/**
 * Hook to safely fetch data with automatic retries
 * Handles backend not being ready gracefully
 */
export function useSafeApiCall<T,>(
  apiCall: () => Promise<T>,
  dependencies: any[] = [],
  options: { retryCount?: number } = {}
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let isMounted = true;

    const execute = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await apiCall();
        if (isMounted) {
          setData(result);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    execute();

    return () => {
      isMounted = false;
    };
  }, dependencies);

  return { data, loading, error };
}
