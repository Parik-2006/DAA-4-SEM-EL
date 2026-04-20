// src/services/firebase/auth.service.ts
import {
  getAuth,
  signInWithEmailAndPassword,
  signOutUser,
  createUserWithEmailAndPassword,
  setPersistence,
  browserLocalPersistence,
  onAuthStateChanged,
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
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const token = await userCredential.user.getIdToken();
    localStorage.setItem('auth_token', token);
    return userCredential.user;
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
    await signOutUser(auth);
    localStorage.removeItem('auth_token');
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
  return onAuthStateChanged(auth, callback);
};

/**
 * Get auth token
 */
export const getAuthToken = async (): Promise<string> => {
  const user = auth.currentUser;
  if (!user) throw new Error('User not authenticated');
  return user.getIdToken();
};

export default auth;
