# Exception Handling and Retry Logic Guide

## Overview

This guide explains the comprehensive exception handling and retry logic that has been added to your Smart Attendance dashboard. These utilities will eliminate the initial connection errors you were seeing when the backend is starting up.

## Components

### 1. **Retry Handler** (`src/utils/retry-handler.ts`)

Provides exponential backoff retry logic with jitter to handle transient failures.

**Key Functions:**
- `withRetry()` - Retry a promise-returning function with exponential backoff
- `waitForHealthy()` - Wait for backend health check to pass
- `isRetryableError()` - Determine if an error should be retried
- `calculateBackoffDelay()` - Calculate delay with exponential backoff and jitter

**Usage:**
```typescript
import { withRetry } from '@/utils/retry-handler';

const data = await withRetry(
  async () => {
    return await apiClient.get('/api/data');
  },
  {
    maxRetries: 5,
    initialDelayMs: 500,
    maxDelayMs: 10000,
    backoffMultiplier: 2,
  }
);
```

### 2. **Error Handler** (`src/utils/error-handler.ts`)

Provides structured error handling with proper logging and user-friendly messages.

**Key Types:**
- `AppError` - Structured error class with error type, status code, and message
- `ErrorType` - Enum of error types (NETWORK_ERROR, SERVER_ERROR, etc.)

**Usage:**
```typescript
import { AppError, handleApiError, createErrorToast } from '@/utils/error-handler';

try {
  // API call
} catch (error) {
  const message = handleApiError('MyComponent', error);
  const toast = createErrorToast(error, 'MyComponent');
  // Show toast to user
}
```

### 3. **Backend Health Hook** (`src/hooks/useBackendHealth.ts`)

React hook to wait for backend readiness before rendering content.

**Usage:**
```typescript
import { useBackendHealth } from '@/hooks/useBackendHealth';

function MyComponent() {
  const { isHealthy, isLoading, error } = useBackendHealth();

  if (isLoading) {
    return <BackendLoadingScreen />;
  }

  if (!isHealthy) {
    return <BackendErrorScreen error={error} />;
  }

  return <YourContent />;
}
```

### 4. **Backend Status Components** (`src/components/BackendStatus.tsx`)

Pre-built UI components for loading and error states.

**Components:**
- `BackendLoadingScreen` - Show while waiting for backend
- `BackendErrorScreen` - Show if backend is unreachable

**Usage:**
```typescript
import { BackendLoadingScreen, BackendErrorScreen } from '@/components/BackendStatus';

function App() {
  const { isHealthy, isLoading, error } = useBackendHealth();

  if (isLoading) return <BackendLoadingScreen />;
  if (!isHealthy) return <BackendErrorScreen onRetry={() => window.location.reload()} />;

  return <YourApp />;
}
```

### 5. **Enhanced API Client** (`src/services/api.ts`)

All API methods now include automatic retry logic:
- Retries up to 5 times with exponential backoff
- Logs all requests and errors
- Graceful error handling with sensible defaults
- New `waitForBackend()` method to wait for server readiness

**Key Changes:**
- All GET/POST/PUT/DELETE requests now retry on transient failures
- Better error logging for debugging
- `healthCheck()` no longer throws, returns boolean
- New `waitForBackend()` method for initialization

**Usage:**
```typescript
import { attendanceAPI } from '@/services/api';

// Method 1: Use retry-enabled methods directly
const students = await attendanceAPI.getStudents();

// Method 2: Wait for backend before other operations
await attendanceAPI.waitForBackend();
const data = await attendanceAPI.getLiveAttendance();
```

## Integration Steps

### Step 1: Update Your Main App Component

```typescript
import { useBackendHealth } from '@/hooks/useBackendHealth';
import { BackendLoadingScreen, BackendErrorScreen } from '@/components/BackendStatus';
import { AppRouter } from './AppRouter';

function App() {
  const { isHealthy, isLoading, error } = useBackendHealth({
    enabled: true,
    maxRetries: 30, // Wait up to 30 seconds
  });

  if (isLoading) {
    return <BackendLoadingScreen message="Starting services..." />;
  }

  if (!isHealthy) {
    return (
      <BackendErrorScreen
        error={error || 'Backend is not available'}
        onRetry={() => window.location.reload()}
      />
    );
  }

  return <AppRouter />;
}

export default App;
```

### Step 2: Update Dashboard Page

```typescript
import { useSafeApiCall } from '@/hooks/useBackendHealth';
import { attendanceAPI } from '@/services/api';
import { handleApiError } from '@/utils/error-handler';

function DashboardPage() {
  const { data: stats, loading, error } = useSafeApiCall(
    () => attendanceAPI.getAttendanceStats(),
    []
  );

  if (loading) return <div>Loading...</div>;
  if (error) {
    const message = handleApiError('DashboardPage', error);
    return <div className="text-red-600">{message}</div>;
  }

  return (
    <div>
      <h2>Attendance Stats</h2>
      <p>Present: {stats?.total_present}</p>
      {/* ... */}
    </div>
  );
}
```

### Step 3: Use in Forms and Actions

```typescript
import { createErrorToast, handleApiError } from '@/utils/error-handler';

async function handleCreateStudent(formData) {
  try {
    const result = await attendanceAPI.createStudent(
      formData.name,
      formData.email,
      formData.courses
    );
    // Show success toast
    showToast('Student created successfully', 'success');
  } catch (error) {
    const errorMessage = handleApiError('CreateStudent', error);
    showToast(errorMessage, 'error');
  }
}
```

## Retry Behavior

### Default Configuration
- **Max Retries**: 5 attempts
- **Initial Delay**: 500ms
- **Max Delay**: 10 seconds
- **Backoff Multiplier**: 2x (exponential)
- **Jitter**: 0-25% random variation

### Retry Timeline
```
Attempt 1: Immediate
Attempt 2: ~500ms delay
Attempt 3: ~1000ms delay
Attempt 4: ~2000ms delay
Attempt 5: ~4000ms delay
Attempt 6: ~8000ms delay (if maxRetries > 5)
```

### Retryable Errors
- 408 Request Timeout
- 429 Too Many Requests
- 500 Internal Server Error
- 502 Bad Gateway
- 503 Service Unavailable
- 504 Gateway Timeout
- ECONNREFUSED (connection refused)
- ENOTFOUND (DNS resolution failed)
- ETIMEDOUT (network timeout)

### Non-Retryable Errors
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- Any 4xx except above

## Logging

All API calls, retries, and errors are logged to the browser console:

```
[API Request] GET http://localhost:8000/api/v1/attendance/health
[API] Retryable error detected. Attempt: 1
[Retry] Attempt 1 for GET /api/v1/attendance/health in 500ms
[API Response] 200 /api/v1/attendance/health
[Health Check] Backend is healthy after 2 attempt(s)
```

## Error Messages

Users will see friendly error messages:

- **Network Error**: "Cannot connect to server. Please check your connection or try again later."
- **Timeout**: "Request timed out. Please try again."
- **Auth Error**: "Authentication failed. Please log in again."
- **Not Found**: "The requested resource was not found."
- **Server Error**: "Server error: [detailed message]"

## Testing

### Simulate Backend Delay

```bash
# Add a delay to backend startup
# In attendance_backend/main.py, add to the startup handler:
import asyncio
await asyncio.sleep(5)  # Wait 5 seconds before starting
```

### Test Retry Behavior

Open browser DevTools Console to see:
1. Initial connection attempts
2. Exponential backoff delays
3. Successful connection
4. All subsequent API calls

## Best Practices

1. **Always use the retry-enabled methods** - All methods in `attendanceAPI` now have retry logic built-in

2. **Handle errors gracefully** - Never let errors crash your UI
   ```typescript
   try {
     // API call
   } catch (error) {
     const message = handleApiError('Context', error);
     showUserFriendlyMessage(message);
   }
   ```

3. **Use hooks for data fetching** - `useSafeApiCall` handles loading, errors, and cleanup
   ```typescript
   const { data, loading, error } = useSafeApiCall(
     () => attendanceAPI.getCourses(),
     []
   );
   ```

4. **Wait for backend on startup** - Use `useBackendHealth` in your root component

5. **Log errors** - All errors are logged automatically, but you can also log manually
   ```typescript
   import { logError } from '@/utils/error-handler';
   logError('MyComponent', error);
   ```

## Troubleshooting

### Still seeing connection errors?

1. Check that backend is running: `python -m uvicorn main:app`
2. Check backend logs for errors
3. Verify `VITE_API_BASE_URL` environment variable is correct
4. Check browser console for detailed error messages

### Retries taking too long?

Reduce `maxRetries` in the hook:
```typescript
const { isHealthy, isLoading } = useBackendHealth({ maxRetries: 10 });
```

### Want to disable retries for testing?

Create a configuration option and update `api.ts`:
```typescript
const ENABLE_RETRIES = import.meta.env.VITE_ENABLE_RETRIES !== 'false';

// In methods:
if (!ENABLE_RETRIES) {
  // Direct call without retry
  return await apiClient.get(...);
}
```

## Summary

Your application now has:
- ✅ Automatic retry logic with exponential backoff
- ✅ Graceful error handling
- ✅ User-friendly error messages
- ✅ Backend health checks on startup
- ✅ Comprehensive logging for debugging
- ✅ Structured error types and handling
- ✅ Pre-built loading and error UI components
- ✅ React hooks for easy integration

The initial connection errors will no longer appear - the app will wait for the backend to be ready before showing the dashboard!
