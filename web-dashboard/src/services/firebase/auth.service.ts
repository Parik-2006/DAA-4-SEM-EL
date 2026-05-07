// src/services/firebase/auth.service.ts
import {
  getAuth,
  signOut as firebaseSignOut,
  createUserWithEmailAndPassword,
  setPersistence,
  browserLocalPersistence,
  onAuthStateChanged,
  updateProfile as firebaseUpdateProfile,
  User,
} from 'firebase/auth';
import { app } from '@/firebase';

const auth = getAuth(app);

// Set persistence to LOCAL (survives page refresh)
setPersistence(auth, browserLocalPersistence);

/**
 * Sign up a new user
 */
export const signUp = async (email: string, password: string) => {
  try {
    const userCredential = await createUserWithEmailAndPassword(
      auth,
      email,
      password
    );
    const token = await userCredential.user.getIdToken();
    localStorage.setItem('auth_token', token);
    return userCredential.user;
  } catch (error: any) {
    console.error('Sign-up error:', error.message);
    throw error;
  }
};

/**
 * Sign in user with email and password
 */
export const signIn = async (email: string, password: string) => {
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.detail || data?.message || 'Login failed');
    }

    if (data?.access_token) {
      localStorage.setItem('auth_token', data.access_token);
    }
    if (data?.user_id) {
      localStorage.setItem('user_id', data.user_id);
    }
    if (data?.role) {
      localStorage.setItem('user_role', data.role);
    }
    localStorage.setItem('user_email', email);

    return (auth.currentUser ?? ({ email } as User));
  } catch (error: any) {
    console.error('Sign-in error:', error.message);
    throw error;
  }
};

/**
 * Sign out current user
 */
export const signOut = async () => {
  try {
    await firebaseSignOut(auth);
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_email');
    localStorage.removeItem('user_role');
  } catch (error: any) {
    console.error('Sign-out error:', error.message);
    throw error;
  }
};

/**
 * Get current user
 */
export const getCurrentUser = (): User | null => {
  return auth.currentUser;
};

/**
 * Listen to auth state changes
 */
export const onAuthChange = (callback: (user: User | null) => void) => {
  const emitFromLocalToken = () => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      callback({ email: localStorage.getItem('user_email') } as User);
      return;
    }
    callback(null);
  };

  emitFromLocalToken();

  const unsubscribeFirebase = onAuthStateChanged(auth, (user) => {
    if (user) {
      callback(user);
      return;
    }
    emitFromLocalToken();
  });

  const onStorageChange = () => emitFromLocalToken();
  window.addEventListener('storage', onStorageChange);

  return () => {
    unsubscribeFirebase();
    window.removeEventListener('storage', onStorageChange);
  };
};

/**
 * Get auth token
 */
export const getAuthToken = async (): Promise<string> => {
  const backendToken = localStorage.getItem('auth_token');
  if (backendToken) return backendToken;

  const user = auth.currentUser;
  if (!user) throw new Error('User not authenticated');
  return user.getIdToken();
};

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
          photoURL: data.photoUrl 
        });
      }
    },
    get currentUser() { return auth.currentUser; },
    getIdToken: async () => {
      return getAuthToken();
    }
  })
};

export default auth;
