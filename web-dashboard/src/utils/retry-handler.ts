import { AxiosError } from 'axios';

/**
 * Configuration for retry behavior
 */
export interface RetryConfig {
  maxRetries?: number;
  initialDelayMs?: number;
  maxDelayMs?: number;
  backoffMultiplier?: number;
  retryableStatusCodes?: number[];
  onRetry?: (attempt: number, error: Error, delayMs: number) => void;
}

/**
 * Custom error class for API errors
 */
export class APIError extends Error {
  constructor(
    public statusCode: number | undefined,
    public originalError: Error,
    message: string
  ) {
    super(message);
    this.name = 'APIError';
  }
}

/**
 * Determines if an error is retryable
 */
export function isRetryableError(error: any, retryableStatusCodes?: number[]): boolean {
  const defaultRetryableCodes = [408, 429, 500, 502, 503, 504]; // ECONNREFUSED fallback
  const codes = retryableStatusCodes || defaultRetryableCodes;

  // Network errors (connection refused, timeout, etc.)
  if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND' || error.code === 'ETIMEDOUT') {
    return true;
  }

  // Axios error with response
  if (error.response?.status && codes.includes(error.response.status)) {
    return true;
  }

  // Request timeout (no response)
  if (error.code === 'ECONNABORTED') {
    return true;
  }

  return false;
}

/**
 * Calculate exponential backoff delay with jitter
 */
export function calculateBackoffDelay(
  attempt: number,
  initialDelayMs: number = 500,
  maxDelayMs: number = 10000,
  multiplier: number = 2
): number {
  const exponentialDelay = Math.min(
    initialDelayMs * Math.pow(multiplier, attempt - 1),
    maxDelayMs
  );

  // Add jitter: random value between 0-25% of the delay
  const jitter = exponentialDelay * (Math.random() * 0.25);
  return Math.floor(exponentialDelay + jitter);
}

/**
 * Retry a promise-returning function with exponential backoff
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  config: RetryConfig = {}
): Promise<T> {
  const {
    maxRetries = 5,
    initialDelayMs = 500,
    maxDelayMs = 10000,
    backoffMultiplier = 2,
    retryableStatusCodes = [408, 429, 500, 502, 503, 504],
    onRetry,
  } = config;

  let lastError: Error | undefined;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      if (attempt >= maxRetries) {
        break;
      }

      if (!isRetryableError(error, retryableStatusCodes)) {
        throw error;
      }

      const delayMs = calculateBackoffDelay(
        attempt,
        initialDelayMs,
        maxDelayMs,
        backoffMultiplier
      );

      if (onRetry) {
        onRetry(attempt, lastError, delayMs);
      }

      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }

  throw lastError || new Error('Max retries exceeded');
}

/**
 * Wait for backend to be healthy with retries
 */
export async function waitForHealthy(
  healthCheckFn: () => Promise<boolean>,
  config: RetryConfig = {}
): Promise<void> {
  const {
    maxRetries = 10,
    initialDelayMs = 1000,
    maxDelayMs = 5000,
    backoffMultiplier = 1.5,
    onRetry,
  } = config;

  let lastError: Error | undefined;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const isHealthy = await healthCheckFn();
      if (isHealthy) {
        console.log(`[Health Check] Backend is healthy after ${attempt} attempt(s)`);
        return;
      }
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
    }

    if (attempt >= maxRetries) {
      console.warn(
        `[Health Check] Backend still not healthy after ${maxRetries} attempts. Proceeding anyway...`
      );
      return;
    }

    const delayMs = calculateBackoffDelay(
      attempt,
      initialDelayMs,
      maxDelayMs,
      backoffMultiplier
    );

    if (onRetry) {
      onRetry(attempt, lastError || new Error('Health check failed'), delayMs);
    }

    console.log(
      `[Health Check] Attempt ${attempt}/${maxRetries} - retrying in ${delayMs}ms...`
    );
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
}

/**
 * Wrap an axios interceptor with retry logic
 */
export function createRetryInterceptor(config: RetryConfig = {}) {
  return async (error: any) => {
    if (!isRetryableError(error, config.retryableStatusCodes)) {
      return Promise.reject(error);
    }

    const originalRequest = error.config;
    originalRequest.__retryCount = (originalRequest.__retryCount || 0) + 1;

    if (originalRequest.__retryCount > (config.maxRetries || 5)) {
      return Promise.reject(error);
    }

    const delayMs = calculateBackoffDelay(
      originalRequest.__retryCount,
      config.initialDelayMs,
      config.maxDelayMs,
      config.backoffMultiplier
    );

    console.log(
      `[Retry] Attempt ${originalRequest.__retryCount} for ${originalRequest.method?.toUpperCase()} ${originalRequest.url} in ${delayMs}ms`
    );

    if (config.onRetry) {
      config.onRetry(originalRequest.__retryCount, error, delayMs);
    }

    await new Promise((resolve) => setTimeout(resolve, delayMs));
    return Promise.resolve(originalRequest);
  };
}
