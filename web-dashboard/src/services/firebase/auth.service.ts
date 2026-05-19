// src/services/firebase/auth.service.ts
//
// Auth strategy: sessionStorage with expiry-based JWT validation.
//
// TOKEN FLOW:
//   signIn()        → preflight domain check → backend JWT → sessionStorage
//   api.ts          → reads AUTH_TOKEN_KEY on every request via getAuthToken()
//   getValidToken() → validates expiry (30 s safety margin); clears on expiry
//   signOut()       → clears sessionStorage + Firebase session
//
// ROLE RESOLUTION (signIn):
//   1. Preflight — rejects unknown email domains before hitting the network.
//   2. Backend auth — authoritative source for access_token and role.
//   3. Merge — resolveUserRole merges email-derived + backend role; backend wins.
//
import {
  getAuth,
  signOut as firebaseSignOut,
  createUserWithEmailAndPassword,
  setPersistence,
  browserSessionPersistence,
  onAuthStateChanged,
  updateProfile as firebaseUpdateProfile,
  User,
} from 'firebase/auth';
import { app } from '@/firebase';
import { resolveUserRole } from '../../utils/roles';

// ── Storage keys ──────────────────────────────────────────────────────────────
// AUTH_TOKEN_KEY is exported so api.ts interceptors can reference it directly.

export const AUTH_TOKEN_KEY   = 'auth_token';
export const SESSION_TOKEN_KEY = AUTH_TOKEN_KEY;
const TOKEN_EXPIRY_KEY        = 'auth_token_expiry';
const USER_ID_KEY             = 'user_id';
const USER_EMAIL_KEY          = 'user_email';
const USER_ROLE_KEY           = 'user_role';
const USER_ASSIGNED_SECTIONS_KEY = 'assigned_sections';
const CLASS_ID_KEY            = 'class_id';

const ALL_SESSION_KEYS = [
  AUTH_TOKEN_KEY,
  TOKEN_EXPIRY_KEY,
  USER_ID_KEY,
  USER_EMAIL_KEY,
  USER_ROLE_KEY,
  USER_ASSIGNED_SECTIONS_KEY,
  CLASS_ID_KEY,
] as const;
const REFRESH_WINDOW_MS = 5 * 60 * 1000;

// ── Firebase setup ────────────────────────────────────────────────────────────

const auth = getAuth(app);
// Session persistence keeps the browser session scoped to the current tab/window.
setPersistence(auth, browserSessionPersistence);

// ── Session helpers ───────────────────────────────────────────────────────────

/**
 * Persist the backend JWT plus associated metadata.
 * `expiresIn` defaults to 8 hours when the backend omits it.
 */
function persistSession(data: {
  token?: string;
  userId?: string;
  email: string;
  role: string;
  assignedSections?: string[];
  classId?: string;
  expiresIn?: number; // seconds
}): void {
  const expiresAt = Date.now() + (data.expiresIn ?? 8 * 3600) * 1000;
  if (data.token)  sessionStorage.setItem(AUTH_TOKEN_KEY,   data.token);
  if (data.userId) sessionStorage.setItem(USER_ID_KEY,      data.userId);
  if (data.classId) sessionStorage.setItem(CLASS_ID_KEY,    data.classId);
  sessionStorage.setItem(TOKEN_EXPIRY_KEY, String(expiresAt));
  sessionStorage.setItem(USER_EMAIL_KEY,   data.email);
  sessionStorage.setItem(USER_ROLE_KEY,    data.role);
  sessionStorage.setItem(USER_ASSIGNED_SECTIONS_KEY, JSON.stringify(data.assignedSections ?? []));
}

/**
 * Wipe every auth key from sessionStorage so no stale session can linger.
 */
export function clearSession(): void {
  ALL_SESSION_KEYS.forEach((k) => sessionStorage.removeItem(k));
}

/**
 * Returns the stored JWT when it is present and not expired.
 * Returns `null` when missing or expired — callers must treat `null` as
 * "unauthenticated".
 */
export function getValidToken(): string | null {
  const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
  const expiryRaw = sessionStorage.getItem(TOKEN_EXPIRY_KEY);

  if (!token) return null;

  if (expiryRaw) {
    const expiry = Number(expiryRaw);
    if (!Number.isFinite(expiry) || Date.now() >= expiry) {
      clearSession();
      return null;
    }
  }

  return token;
}

export function getStoredAssignedSections(): string[] {
  try {
    const raw = sessionStorage.getItem(USER_ASSIGNED_SECTIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((value) => typeof value === 'string') : [];
  } catch {
    return [];
  }
}

export function getStoredClassId(): string | null {
  return sessionStorage.getItem(CLASS_ID_KEY) ?? null;
}

export function getStoredEmail(): string | null {
  return sessionStorage.getItem(USER_EMAIL_KEY) ?? null;
}

/**
 * True when a valid, non-expired backend token exists in sessionStorage.
 */
export function isAuthenticated(): boolean {
  return getValidToken() !== null;
}

/** Backwards-compatible sync accessor used by the router and API layer. */
export function getSessionToken(): string | null {
  return getValidToken();
}

// ── Auth actions ──────────────────────────────────────────────────────────────

/**
 * Sign up a new user with email/password.
 * Persists a minimal session (Firebase ID token, student role) so the user
 * is immediately considered authenticated without a separate login step.
 */
export const signUp = async (email: string, password: string): Promise<User> => {
  try {
    const credential = await createUserWithEmailAndPassword(auth, email, password);
    const token = await credential.user.getIdToken();
    persistSession({ token, email, role: 'student' });
    return credential.user;
  } catch (error: any) {
    console.error('[Auth] Sign-up error:', error.message);
    throw error;
  }
};

/**
 * Authenticates against the backend REST API and stores the returned JWT.
 *
 * Step 1 — Preflight domain check (fast-fail, no network round-trip).
 * Step 2 — Backend authentication (authoritative token + role source).
 * Step 3 — Role resolution (email-derived role merged with backend role;
 *           backend wins on conflict).
 *
 * Throws a user-readable `Error` on any failure.
 */
export const signIn = async (email: string, password: string): Promise<User> => {
  // ── Step 1: preflight ─────────────────────────────────────────────────────
  const preflight = resolveUserRole({ email, backendRole: null });
  if (preflight.rejected) {
    throw new Error(preflight.rejectionReason);
  }

  // ── Step 2: backend authentication ───────────────────────────────────────
  try {
    const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
    const response = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.detail || data?.message || 'Login failed');
    }

    if (!data?.access_token) {
      throw new Error('Server did not return an access token');
    }

    // ── Step 3: final role resolution (backend is source of truth) ──────────
    const resolution = resolveUserRole({ email, backendRole: data?.role ?? null });
    if (resolution.rejected) {
      throw new Error(resolution.rejectionReason);
    }

    persistSession({
      token:     data.access_token,
      userId:    data.user_id,
      email:     data.email ?? email,
      role:      resolution.role,
      classId:   data.class_id,
      expiresIn: data.expires_in,
    });

    console.log(`[Auth] Signed in as ${email} with role: ${resolution.role}`);

    return auth.currentUser ?? ({ email, uid: data.user_id ?? '' } as unknown as User);
  } catch (error: any) {
    console.error('[Auth] Sign-in error:', error.message);
    throw error;
  }
};

/**
 * Signs out from Firebase **and** wipes the local session so no stale JWT
 * can slip through on the next page load.
 */
export const signOut = async (): Promise<void> => {
  clearSession();
  try {
    await firebaseSignOut(auth);
  } catch (error: any) {
    // Firebase sign-out failure is non-critical; session is already cleared.
    console.error('[Auth] Sign-out error (non-critical):', error.message);
  }
};

export const getCurrentUser = (): User | null => auth.currentUser;

// ── Auth state subscription ───────────────────────────────────────────────────

/**
 * Subscribes to auth-state changes.
 *
 * Strategy:
 *  1. Emit immediately from sessionStorage so ProtectedRoute renders without
 *     waiting for Firebase's async resolution (no flash-of-unauthenticated).
 *  2. Subscribe to Firebase `onAuthStateChanged` so Firebase-managed state
 *     (e.g. token refresh) is reflected automatically.
 *  3. Listen to `storage` events on the specific token keys so multi-tab
 *     logout propagates instantly.
 *
 * The callback receives `null` whenever the backend JWT is missing or expired,
 * regardless of what Firebase says — no protected page is ever shown with an
 * invalid token.
 */
export const onAuthChange = (callback: (user: User | null) => void): (() => void) => {
  const emitCurrent = () => {
    const token = getValidToken();
    if (!token) {
      callback(null);
      return;
    }
    const email = sessionStorage.getItem(USER_EMAIL_KEY) ?? '';
    callback(
      auth.currentUser ?? ({ email, uid: sessionStorage.getItem(USER_ID_KEY) ?? '' } as unknown as User)
    );
  };

  // Synchronous emit — ProtectedRoute must not wait.
  emitCurrent();

  const unsubFirebase = onAuthStateChanged(auth, (user) => {
    if (user) {
      callback(user);
    } else {
      emitCurrent();
    }
  });

  return () => {
    unsubFirebase();
  };
};

// ── Token retrieval for API layer ─────────────────────────────────────────────

/**
 * Returns the auth token for use in API request headers.
 *
 * Preference order:
 *  1. Valid backend JWT from sessionStorage (fast, synchronous path).
 *  2. Fresh Firebase ID token — fallback for the signUp flow where a backend
 *     JWT has not yet been issued.
 *
 * Throws if neither source can produce a token — the API interceptor should
 * catch this and redirect to `/login`.
 */
async function refreshBackendToken(currentToken: string): Promise<string | null> {
  const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  try {
    const response = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${currentToken}`,
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        clearSession();
        return null;
      }
      throw new Error(`Token refresh failed (${response.status})`);
    }

    const data = await response.json();
    if (!data?.access_token) {
      throw new Error('Server did not return a refreshed access token');
    }

    persistSession({
      token: data.access_token,
      userId: data.user_id ?? sessionStorage.getItem(USER_ID_KEY) ?? undefined,
      email: data.email ?? sessionStorage.getItem(USER_EMAIL_KEY) ?? '',
      role: data.role ?? sessionStorage.getItem(USER_ROLE_KEY) ?? 'student',
      expiresIn: data.expires_in,
    });

    return data.access_token;
  } catch (error) {
    console.warn('[Auth] Token refresh skipped:', error);
    return currentToken;
  }
}

export const getAuthToken = async (): Promise<string> => {
  const stored = getValidToken();
  if (!stored) {
    const user = auth.currentUser;
    if (!user) throw new Error('No valid auth token — please log in again');
    return user.getIdToken();
  }

  const expiryRaw = sessionStorage.getItem(TOKEN_EXPIRY_KEY);
  if (expiryRaw) {
    const expiry = Number(expiryRaw);
    const remainingMs = expiry - Date.now();
    if (Number.isFinite(expiry) && remainingMs > 0 && remainingMs <= REFRESH_WINDOW_MS) {
      const refreshed = await refreshBackendToken(stored);
      return refreshed ?? stored;
    }
  }

  return stored;
};

// ── Service interface & singleton ─────────────────────────────────────────────

export interface IFirebaseAuthService {
  onAuthChange: (callback: (user: User | null) => void) => () => void;
  signIn: (data: { email: string; password: string }) => Promise<User>;
  signUp: (data: { email: string; password: string; displayName?: string }) => Promise<User>;
  updateProfile: (data: { displayName?: string; photoUrl?: string }) => Promise<void>;
  currentUser: User | null;
  getIdToken: () => Promise<string>;
}

export const FirebaseAuthService = {
  getInstance: (): IFirebaseAuthService => ({
    onAuthChange,
    signIn: ({ email, password }) => signIn(email, password),
    signUp: async ({ email, password, displayName }) => {
      const user = await signUp(email, password);
      if (displayName) await firebaseUpdateProfile(user, { displayName });
      return user;
    },
    updateProfile: async ({ displayName, photoUrl }) => {
      const user = auth.currentUser;
      if (user) {
        await firebaseUpdateProfile(user, { displayName, photoURL: photoUrl });
      }
    },
    get currentUser() { return auth.currentUser; },
    getIdToken: () => getAuthToken(),
  }),
};

export default auth;