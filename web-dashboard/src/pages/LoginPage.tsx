// src/pages/LoginPage.tsx
//
// Login is the only public entry point.
// Uses backend API (POST /api/v1/auth/login) for authentication.
//
import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { signIn, clearSession } from '../services/firebase/auth.service';
import { getStoredRole, resolveRoleFromEmail, LOGIN_EMAIL_POLICY_MESSAGE } from '../utils/roles';

// Minimal field-level validation messages
type FieldError = { email?: string; password?: string; general?: string };

export const LoginPage: React.FC = () => {
  const navigate  = useNavigate();
  const location  = useLocation();

  // Role-aware redirect: admin/teacher → /dashboard, student → /attendance
  const getRedirectPath = (): string => {
    const role = getStoredRole();
    if (role === 'student') return '/dashboard';
    if (role === 'admin' || role === 'teacher') return '/dashboard';
    return '/login'; // Fallback
  };

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [errors,   setErrors]   = useState<FieldError>({});
  const [loading,  setLoading]  = useState(false);
  const [showPw,   setShowPw]   = useState(false);

  // Purge stale session data on mount
  useEffect(() => {
    clearSession();
  }, []);

  // ── Client-side validation ─────────────────────────────────────────────────
  const validate = (): boolean => {
    const e: FieldError = {};
    if (!email.trim())                               e.email    = 'Email is required.';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = 'Enter a valid email address.';
    else if (resolveRoleFromEmail(email) === null)  e.email    = LOGIN_EMAIL_POLICY_MESSAGE;
    if (!password)                                   e.password = 'Password is required.';
    else if (password.length < 6)                   e.password = 'Password must be at least 6 characters.';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    if (!validate()) return;

    setLoading(true);
    try {
      await signIn(email.trim().toLowerCase(), password);
      // Get role-appropriate redirect path after sign-in (role now in sessionStorage)
      const from = (location.state as { from?: string } | null)?.from;
      const redirectPath = from || getRedirectPath();
      navigate(redirectPath, { replace: true });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Login failed. Please check your credentials.';
      setErrors({ general: message });
    } finally {
      setLoading(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        background: 'linear-gradient(135deg, #2A1F12 0%, #503C22 40%, #7A5D35 100%)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '420px',
          background: 'rgba(254,252,248,0.95)',
          backdropFilter: 'blur(16px)',
          borderRadius: '24px',
          padding: '40px 36px',
          boxShadow: '0 32px 80px rgba(0,0,0,0.35)',
          border: '1px solid rgba(190,160,118,0.30)',
        }}
      >
        {/* Logo / wordmark */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div
            style={{
              width: '52px',
              height: '52px',
              borderRadius: '16px',
              background: 'linear-gradient(135deg, #9B7A3A 0%, #C8A86A 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 14px',
              boxShadow: '0 4px 14px rgba(155,122,58,0.40)',
            }}
          >
            <span
              style={{
                color: '#fff',
                fontSize: '1.4rem',
                fontWeight: 900,
                fontFamily: 'Fraunces, Georgia, serif',
              }}
            >
              A
            </span>
          </div>
          <h1
            style={{
              fontSize: '1.5rem',
              fontWeight: 800,
              color: '#2A1F12',
              fontFamily: 'Fraunces, Georgia, serif',
              marginBottom: '4px',
            }}
          >
            AttendMate
          </h1>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
            Sign in to your account to continue
          </p>
        </div>

        {/* General error */}
        {errors.general && (
          <div
            role="alert"
            style={{
              padding: '12px 16px',
              borderRadius: '12px',
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.25)',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
            }}
          >
            <span style={{ fontSize: '1rem', flexShrink: 0 }}>⚠️</span>
            <p style={{ fontSize: '0.82rem', color: '#DC2626', lineHeight: 1.45 }}>
              {errors.general}
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          {/* Email */}
          <div style={{ marginBottom: '16px' }}>
            <label
              htmlFor="email"
              style={{
                display: 'block',
                fontSize: '0.75rem',
                fontWeight: 700,
                color: '#64748b',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                marginBottom: '6px',
              }}
            >
              Email address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="username email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setErrors((p) => ({ ...p, email: undefined })); }}
              placeholder="you@example.com"
              disabled={loading}
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? 'email-error' : undefined}
              style={{
                width: '100%',
                padding: '11px 14px',
                borderRadius: '12px',
                border: `1.5px solid ${errors.email ? '#EF4444' : '#E2E8F0'}`,
                background: '#FEFCF8',
                fontSize: '0.9rem',
                color: '#1e293b',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color 0.2s, box-shadow 0.2s',
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = '#9B7A3A'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(155,122,58,0.12)'; }}
              onBlur={(e)  => { e.currentTarget.style.borderColor = errors.email ? '#EF4444' : '#E2E8F0'; e.currentTarget.style.boxShadow = 'none'; }}
            />
            {errors.email && (
              <p id="email-error" style={{ fontSize: '0.72rem', color: '#DC2626', marginTop: '4px' }}>
                {errors.email}
              </p>
            )}
          </div>

          {/* Password */}
          <div style={{ marginBottom: '24px' }}>
            <label
              htmlFor="password"
              style={{
                display: 'block',
                fontSize: '0.75rem',
                fontWeight: 700,
                color: '#64748b',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                marginBottom: '6px',
              }}
            >
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id="password"
                name="password"
                type={showPw ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: undefined })); }}
                placeholder="••••••••"
                disabled={loading}
                aria-invalid={!!errors.password}
                aria-describedby={errors.password ? 'pw-error' : undefined}
                style={{
                  width: '100%',
                  padding: '11px 44px 11px 14px',
                  borderRadius: '12px',
                  border: `1.5px solid ${errors.password ? '#EF4444' : '#E2E8F0'}`,
                  background: '#FEFCF8',
                  fontSize: '0.9rem',
                  color: '#1e293b',
                  outline: 'none',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.2s, box-shadow 0.2s',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = '#9B7A3A'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(155,122,58,0.12)'; }}
                onBlur={(e)  => { e.currentTarget.style.borderColor = errors.password ? '#EF4444' : '#E2E8F0'; e.currentTarget.style.boxShadow = 'none'; }}
              />
              <button
                type="button"
                onClick={() => setShowPw((v) => !v)}
                tabIndex={-1}
                aria-label={showPw ? 'Hide password' : 'Show password'}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#94a3b8',
                  fontSize: '1rem',
                  lineHeight: 1,
                  padding: '4px',
                }}
              >
                {showPw ? '🙈' : '👁'}
              </button>
            </div>
            {errors.password && (
              <p id="pw-error" style={{ fontSize: '0.72rem', color: '#DC2626', marginTop: '4px' }}>
                {errors.password}
              </p>
            )}
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '13px',
              borderRadius: '14px',
              border: 'none',
              background: loading
                ? 'rgba(155,122,58,0.5)'
                : 'linear-gradient(135deg, #9B7A3A 0%, #C8A86A 100%)',
              color: '#fff',
              fontSize: '0.95rem',
              fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: loading ? 'none' : '0 4px 14px rgba(155,122,58,0.35)',
              transition: 'all 0.2s',
            }}
          >
            {loading && (
              <span
                style={{
                  width: '16px',
                  height: '16px',
                  border: '2px solid rgba(255,255,255,0.4)',
                  borderTopColor: '#fff',
                  borderRadius: '50%',
                  display: 'inline-block',
                  animation: 'spin 0.7s linear infinite',
                }}
              />
            )}
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        {/* Session notice */}
        <p
          style={{
            fontSize: '0.68rem',
            color: '#b0956e',
            textAlign: 'center',
            marginTop: '20px',
            lineHeight: 1.5,
          }}
        >
          🔒 Session-only access — you will be signed out when you close this tab.
        </p>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

// ── Firebase error → human message ────────────────────────────────────────────

function mapFirebaseError(err: unknown): string {
  if (typeof err !== 'object' || err === null) return 'Sign-in failed. Please try again.';
  const code = (err as { code?: string }).code ?? '';
  const map: Record<string, string> = {
    'auth/user-not-found':         'No account found with that email address.',
    'auth/wrong-password':         'Incorrect password. Please try again.',
    'auth/invalid-credential':     'Invalid email or password.',
    'auth/invalid-email':          'Please enter a valid email address.',
    'auth/user-disabled':          'This account has been disabled. Contact your administrator.',
    'auth/too-many-requests':      'Too many failed attempts. Please wait a few minutes and try again.',
    'auth/network-request-failed': 'Network error. Check your connection and try again.',
    'auth/operation-not-allowed':  'Sign-in is not enabled. Contact your administrator.',
  };
  return map[code] ?? 'Sign-in failed. Please check your credentials and try again.';
}
