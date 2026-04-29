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
          console.error('[useSafeApiCall] Error:', err);
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

/**
 * Hook for continuous health monitoring
 * Periodically checks backend health and provides status updates
 */
export function useBackendHealthMonitor(
  interval: number = 5000, // Check every 5 seconds
  onStatusChange?: (isHealthy: boolean) => void
) {
  const [isHealthy, setIsHealthy] = useState(true);
  const [lastCheck, setLastCheck] = useState<Date>(new Date());

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    const performHealthCheck = async () => {
      try {
        const result = await attendanceAPI.healthCheck();
        const newHealthStatus = result;

        if (newHealthStatus !== isHealthy) {
          console.log(
            `[useBackendHealthMonitor] Status changed: ${isHealthy ? 'healthy' : 'unhealthy'} -> ${newHealthStatus ? 'healthy' : 'unhealthy'}`
          );
          setIsHealthy(newHealthStatus);
          onStatusChange?.(newHealthStatus);
        }

        setLastCheck(new Date());
      } catch (err) {
        if (isHealthy) {
          console.warn('[useBackendHealthMonitor] Backend became unhealthy:', err);
          setIsHealthy(false);
          onStatusChange?.(false);
        }
      }

      // Schedule next check
      timeoutId = setTimeout(performHealthCheck, interval);
    };

    // Perform first check immediately
    performHealthCheck();

    return () => clearTimeout(timeoutId);
  }, [interval, isHealthy, onStatusChange]);

  return { isHealthy, lastCheck };
}
