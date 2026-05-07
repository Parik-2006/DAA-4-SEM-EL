// src/services/firebase/auth.service.ts
//
// Auth strategy: session-only. All auth data lives in sessionStorage so that
// a page refresh (or new tab) wipes the session and forces re-authentication.
// Firebase persistence is set to SESSION (not LOCAL) for the same reason.
//
// TOKEN FLOW:
//   signIn()  → backend JWT → sessionStorage[SESSION_TOKEN_KEY]
//   api.ts    → reads SESSION_TOKEN_KEY on every request
//   signOut() → clears sessionStorage + Firebase session
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

// ── Shared key used by api.ts request interceptor ─────────────────────────────
export const SESSION_TOKEN_KEY = 'session_auth_token';

const auth = getAuth(app);

// Session-only persistence — cleared when the browser tab closes or refreshes.
setPersistence(auth, browserSessionPersistence);

// ── Internal helpers ──────────────────────────────────────────────────────────

function persistSession(data: {
  token?: string;
  userId?: string;
  email: string;
  role: string;
}) {
  if (data.token)  sessionStorage.setItem(SESSION_TOKEN_KEY, data.token);
  if (data.userId) sessionStorage.setItem('user_id', data.userId);
  sessionStorage.setItem('user_email', data.email);
  sessionStorage.setItem('user_role',  data.role);
}

export function clearSession() {
  sessionStorage.removeItem(SESSION_TOKEN_KEY);
  sessionStorage.removeItem('user_id');
  sessionStorage.removeItem('user_email');
  sessionStorage.removeItem('user_role');
}

export function getSessionToken(): string | null {
  return sessionStorage.getItem(SESSION_TOKEN_KEY);
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Sign up a new user with email/password.
 * Persists the Firebase ID token for the current session.
 */
export const signUp = async (email: string, password: string): Promise<User> => {
  try {
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    const token = await userCredential.user.getIdToken();
    persistSession({ token, email, role: 'student' });
    return userCredential.user;
  } catch (error: any) {
    console.error('[Auth] Sign-up error:', error.message);
    throw error;
  }
};

/**
 * Sign in with email and password.
 *
 * Role resolution order:
 *  1. Frontend preflight — reject completely unknown domains before hitting
 *     the network (fast-fail, no backend round-trip).
 *  2. Backend authentication — the backend is the authoritative source for
 *     the access token and the user's role.
 *  3. Final role resolution — merges the email-derived role with the backend
 *     role; backend wins on conflict. Persists everything to sessionStorage.
 */
export const signIn = async (email: string, password: string): Promise<User> => {
  // ── Step 1: preflight domain check ────────────────────────────────────────
  const preflight = resolveUserRole({ email, backendRole: null });
  if (preflight.rejected) {
    throw new Error(preflight.rejectionReason);
  }

  // ── Step 2: backend authentication ────────────────────────────────────────
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

    // ── Step 3: final role resolution (backend is source of truth) ───────────
    const resolution = resolveUserRole({
      email,
      backendRole: data?.role ?? null,
    });

    if (resolution.rejected) {
      throw new Error(resolution.rejectionReason);
    }

    persistSession({
      token:  data?.access_token,
      userId: data?.user_id,
      email,
      role:   resolution.role,
    });

    console.log(`[Auth] Signed in as ${email} with role: ${resolution.role}`);

    return (auth.currentUser ?? ({ email } as User));
  } catch (error: any) {
    console.error('[Auth] Sign-in error:', error.message);
    throw error;
  }
};

/**
 * Sign out the current user.
 * Clears sessionStorage and the Firebase session.
 */
export const signOut = async (): Promise<void> => {
  try {
    await firebaseSignOut(auth);
    clearSession();
  } catch (error: any) {
    console.error('[Auth] Sign-out error:', error.message);
    throw error;
  }
};

/**
 * Return the currently authenticated Firebase user, or null.
 */
export const getCurrentUser = (): User | null => auth.currentUser;

/**
 * Subscribe to auth state changes.
 *
 * Emits from sessionStorage when Firebase has no active session (e.g. after
 * a soft navigation where sessionStorage survives but Firebase state hasn't
 * re-hydrated yet). Returns an unsubscribe function.
 */
export const onAuthChange = (callback: (user: User | null) => void): (() => void) => {
  const emitFromSession = () => {
    const token = sessionStorage.getItem(SESSION_TOKEN_KEY);
    callback(token
      ? ({ email: sessionStorage.getItem('user_email') } as User)
      : null
    );
  };

  emitFromSession();

  const unsubscribeFirebase = onAuthStateChanged(auth, (user) => {
    if (user) {
      callback(user);
    } else {
      emitFromSession();
    }
  });

  // Keep in sync if another tab clears the session.
  const onStorageChange = () => emitFromSession();
  window.addEventListener('storage', onStorageChange);

  return () => {
    unsubscribeFirebase();
    window.removeEventListener('storage', onStorageChange);
  };
};

/**
 * Retrieve the current auth token.
 * Prefers the backend JWT in sessionStorage; falls back to a fresh Firebase
 * ID token if no backend token is present (e.g. during signUp).
 */
export const getAuthToken = async (): Promise<string> => {
  const sessionToken = sessionStorage.getItem(SESSION_TOKEN_KEY);
  if (sessionToken) return sessionToken;

  const user = auth.currentUser;
  if (!user) throw new Error('User not authenticated');
  return user.getIdToken();
};

// ── Service interface & singleton ─────────────────────────────────────────────

export interface IFirebaseAuthService {
  onAuthChange: (callback: (user: User | null) => void) => import('firebase/auth').Unsubscribe;
  signIn: (data: any) => Promise<User>;
  signUp: (data: any) => Promise<User>;
  updateProfile: (data: any) => Promise<void>;
  currentUser: User | null;
  getIdToken: () => Promise<string>;
}

export const FirebaseAuthService = {
  getInstance: (): IFirebaseAuthService => ({
    onAuthChange,
    signIn: async (data: any) => signIn(data.email, data.password),
    signUp: async (data: any) => {
      const user = await signUp(data.email, data.password);
      if (data.displayName) {
        await firebaseUpdateProfile(user, { displayName: data.displayName });
      }
      return user;
    },
    updateProfile: async (data: any) => {
      const user = auth.currentUser;
      if (user) {
        await firebaseUpdateProfile(user, {
          displayName: data.displayName,
          photoURL:    data.photoUrl,
        });
      }
    },
    get currentUser() { return auth.currentUser; },
    getIdToken: async () => getAuthToken(),
  }),
};

export default auth;