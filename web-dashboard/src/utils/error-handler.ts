import { AxiosError } from 'axios';

/**
 * Types of errors that can occur in the application
 */
export enum ErrorType {
  NETWORK_ERROR = 'NETWORK_ERROR',
  SERVER_ERROR = 'SERVER_ERROR',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR',
  NOT_FOUND = 'NOT_FOUND',
  TIMEOUT = 'TIMEOUT',
  UNKNOWN = 'UNKNOWN',
}

/**
 * Structured error class for consistent error handling
 */
export class AppError extends Error {
  constructor(
    public type: ErrorType,
    public statusCode: number | undefined,
    message: string,
    public originalError?: Error
  ) {
    super(message);
    this.name = 'AppError';
  }

  static fromAxiosError(error: AxiosError): AppError {
    const status = error.response?.status;
    const detail =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'Unknown error';

    if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
      return new AppError(
        ErrorType.NETWORK_ERROR,
        status,
        'Cannot connect to server. Please check your connection or try again later.',
        error
      );
    }

    if (error.code === 'ECONNABORTED') {
      return new AppError(
        ErrorType.TIMEOUT,
        status,
        'Request timed out. Please try again.',
        error
      );
    }

    if (status === 401 || status === 403) {
      return new AppError(
        ErrorType.AUTHENTICATION_ERROR,
        status,
        'Authentication failed. Please log in again.',
        error
      );
    }

    if (status === 404) {
      return new AppError(
        ErrorType.NOT_FOUND,
        status,
        'The requested resource was not found.',
        error
      );
    }

    if (status && status >= 400 && status < 500) {
      return new AppError(
        ErrorType.VALIDATION_ERROR,
        status,
        String(detail),
        error
      );
    }

    if (status && status >= 500) {
      return new AppError(
        ErrorType.SERVER_ERROR,
        status,
        `Server error: ${detail}`,
        error
      );
    }

    return new AppError(ErrorType.UNKNOWN, status, String(detail), error);
  }
}

/**
 * Format error message for user display
 */
export function formatErrorMessage(error: unknown): string {
  if (error instanceof AppError) {
    return error.message;
  }

  if (error instanceof AxiosError) {
    const appError = AppError.fromAxiosError(error);
    return appError.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'An unexpected error occurred. Please try again.';
}

/**
 * Log error for debugging
 */
export function logError(context: string, error: unknown): void {
  const timestamp = new Date().toISOString();

  if (error instanceof AppError) {
    console.error(`[${timestamp}] [${context}] ${error.type}:`, {
      message: error.message,
      statusCode: error.statusCode,
      originalError: error.originalError?.message,
    });
  } else if (error instanceof AxiosError) {
    console.error(`[${timestamp}] [${context}] Axios Error:`, {
      status: error.response?.status,
      message: error.message,
      url: error.config?.url,
    });
  } else if (error instanceof Error) {
    console.error(`[${timestamp}] [${context}]:`, error.message);
  } else {
    console.error(`[${timestamp}] [${context}]:`, error);
  }
}

/**
 * Handle API errors with proper logging and user-friendly messages
 */
export function handleApiError(context: string, error: unknown): string {
  logError(context, error);
  return formatErrorMessage(error);
}

/**
 * Create a user-friendly toast message from an error
 */
export interface ToastOptions {
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function createErrorToast(
  error: unknown,
  context: string
): { message: string; type: 'error' | 'warning'; options?: ToastOptions } {
  const message = handleApiError(context, error);

  if (error instanceof AppError) {
    switch (error.type) {
      case ErrorType.NETWORK_ERROR:
        return {
          message,
          type: 'error',
          options: {
            duration: 5000,
            action: {
              label: 'Retry',
              onClick: () => window.location.reload(),
            },
          },
        };
      case ErrorType.TIMEOUT:
        return {
          message,
          type: 'warning',
          options: { duration: 3000 },
        };
      case ErrorType.AUTHENTICATION_ERROR:
        return {
          message,
          type: 'error',
          options: {
            action: {
              label: 'Login',
              onClick: () => {
                window.location.href = '/login';
              },
            },
          },
        };
      default:
        return {
          message,
          type: 'error',
          options: { duration: 3000 },
        };
    }
  }

  return {
    message,
    type: 'error',
    options: { duration: 3000 },
  };
}
