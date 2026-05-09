import React, { useEffect, useState } from 'react';
import { isAuthenticated } from '../services/firebase/auth.service';

// ── Types ─────────────────────────────────────────────────────────────────────

interface BackendLoadingScreenProps {
  message?: string;
  showProgress?: boolean;
}

interface BackendErrorScreenProps {
  error?: string;
  /** Whether the error is specifically a missing/expired auth token. */
  isAuthError?: boolean;
  onRetry?: () => void;
}

// ── BackendLoadingScreen ──────────────────────────────────────────────────────

/**
 * Shown while the app is waiting for the backend to become healthy.
 * Also performs a local auth pre-check: if the user is not authenticated
 * at render time, it redirects to /login immediately instead of waiting.
 */
export const BackendLoadingScreen: React.FC<BackendLoadingScreenProps> = ({
  message = 'Starting services…',
  showProgress = true,
}) => {
  useEffect(() => {
    // If there is no valid token there is nothing useful to show — redirect
    // immediately so the user is not left looking at a spinner forever.
    if (!isAuthenticated()) {
      window.location.replace('/login');
    }
  }, []);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%)',
        fontFamily: 'DM Sans, system-ui, sans-serif',
      }}
    >
      <div style={{ textAlign: 'center', maxWidth: 360, padding: '0 24px' }}>
        {/* Spinner */}
        <div
          style={{
            position: 'relative',
            width: 64,
            height: 64,
            margin: '0 auto 28px',
          }}
        >
          {/* Static track */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              border: '4px solid #C7D2FE',
            }}
          />
          {/* Spinning arc */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              border: '4px solid transparent',
              borderTopColor: '#6366F1',
              borderRightColor: '#6366F1',
              animation: 'spin 0.9s linear infinite',
            }}
          />
        </div>

        <h1
          style={{
            fontSize: '1.5rem',
            fontWeight: 800,
            color: '#1e1b4b',
            marginBottom: 8,
          }}
        >
          AttendMate
        </h1>

        <p style={{ fontSize: '0.9rem', color: '#4338ca', marginBottom: 20 }}>
          {message}
        </p>

        {showProgress && (
          <div>
            <div
              style={{
                width: 240,
                margin: '0 auto',
                height: 6,
                borderRadius: 99,
                background: '#C7D2FE',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  borderRadius: 99,
                  background: 'linear-gradient(90deg, #6366F1, #818CF8)',
                  animation: 'progress-pulse 1.8s ease-in-out infinite',
                }}
              />
            </div>
            <p
              style={{
                fontSize: '0.75rem',
                color: '#6366F1',
                marginTop: 10,
                opacity: 0.7,
              }}
            >
              Please wait — this may take a few moments…
            </p>
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes progress-pulse {
          0%   { width: 15%; opacity: 1; }
          50%  { width: 65%; opacity: 0.85; }
          100% { width: 15%; opacity: 1; }
        }
      `}</style>
    </div>
  );
};

// ── BackendErrorScreen ────────────────────────────────────────────────────────

/**
 * Shown when the backend cannot be reached, OR when the session has expired.
 *
 * When `isAuthError` is true the component renders a session-expiry message
 * with a "Go to Login" CTA instead of the generic connection-error checklist.
 */
export const BackendErrorScreen: React.FC<BackendErrorScreenProps> = ({
  error = 'Unable to connect to the server.',
  isAuthError = false,
  onRetry,
}) => {
  // Detect whether this is effectively an auth problem even if the caller
  // didn't pass isAuthError explicitly.
  const authProblem =
    isAuthError ||
    !isAuthenticated() ||
    error.toLowerCase().includes('token') ||
    error.toLowerCase().includes('log in') ||
    error.toLowerCase().includes('unauthori');

  if (authProblem) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%)',
          fontFamily: 'DM Sans, system-ui, sans-serif',
        }}
      >
        <div
          style={{
            textAlign: 'center',
            maxWidth: 380,
            padding: '40px 28px',
            background: '#fff',
            borderRadius: 24,
            boxShadow: '0 20px 60px rgba(0,0,0,0.12)',
            border: '1px solid #FDE68A',
          }}
        >
          <div
            style={{
              fontSize: 52,
              marginBottom: 16,
              lineHeight: 1,
            }}
          >
            🔑
          </div>
          <h2
            style={{
              fontSize: '1.4rem',
              fontWeight: 800,
              color: '#92400E',
              marginBottom: 10,
            }}
          >
            Session Expired
          </h2>
          <p
            style={{
              fontSize: '0.875rem',
              color: '#78350F',
              marginBottom: 24,
              lineHeight: 1.6,
            }}
          >
            Your session has expired or is no longer valid. Please log in again
            to continue.
          </p>
          <button
            onClick={() => window.location.replace('/login')}
            style={{
              width: '100%',
              padding: '12px 0',
              borderRadius: 12,
              border: 'none',
              background: 'linear-gradient(135deg, #D97706, #F59E0B)',
              color: '#fff',
              fontSize: '0.95rem',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(217,119,6,0.35)',
            }}
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  // ── Generic backend-down screen ─────────────────────────────────────────────
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #FFF1F2 0%, #FFE4E6 100%)',
        fontFamily: 'DM Sans, system-ui, sans-serif',
      }}
    >
      <div
        style={{
          textAlign: 'center',
          maxWidth: 420,
          padding: '40px 28px',
          background: '#fff',
          borderRadius: 24,
          boxShadow: '0 20px 60px rgba(0,0,0,0.10)',
          border: '1px solid #FECACA',
        }}
      >
        <div style={{ fontSize: 52, marginBottom: 16, lineHeight: 1 }}>⚠️</div>

        <h2
          style={{
            fontSize: '1.4rem',
            fontWeight: 800,
            color: '#7F1D1D',
            marginBottom: 10,
          }}
        >
          Connection Error
        </h2>

        <p
          style={{
            fontSize: '0.875rem',
            color: '#991B1B',
            marginBottom: 24,
            lineHeight: 1.6,
          }}
        >
          {error}
        </p>

        {/* Checklist */}
        <ul
          style={{
            textAlign: 'left',
            fontSize: '0.82rem',
            color: '#B91C1C',
            lineHeight: 1.8,
            marginBottom: 24,
            paddingLeft: 0,
            listStyle: 'none',
          }}
        >
          {[
            'Ensure the backend server is running',
            'Check your internet connection',
            'Review the server logs for errors',
            'Wait a few seconds and try again',
          ].map((tip) => (
            <li key={tip} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <span style={{ color: '#F87171', flexShrink: 0 }}>✓</span>
              {tip}
            </li>
          ))}
        </ul>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
          {onRetry && (
            <button
              onClick={onRetry}
              style={{
                padding: '10px 22px',
                borderRadius: 11,
                border: 'none',
                background: 'linear-gradient(135deg, #EF4444, #F87171)',
                color: '#fff',
                fontSize: '0.88rem',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 4px 12px rgba(239,68,68,0.3)',
              }}
            >
              Retry Connection
            </button>
          )}
          <button
            onClick={() => window.location.replace('/login')}
            style={{
              padding: '10px 22px',
              borderRadius: 11,
              border: '1.5px solid #FECACA',
              background: '#fff',
              color: '#DC2626',
              fontSize: '0.88rem',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Go to Login
          </button>
        </div>
      </div>
    </div>
  );
};