/**
 * AppRouter.tsx  — merged & final
 * ---------------------------------
 * Keeps 100 % of the existing role-based auth system (AuthGate, RoleGate,
 * ROLE_ALLOWED, PublicOnlyRoute, DefaultRedirect, LoadingScreen).
 *
 * Only change vs. the original:
 *   • AdminAnalyticsPage  →  AttendanceAnalyticsPage  (at /analytics)
 *
 * Replace:  web-dashboard/src/AppRouter.tsx
 */

import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

// ── Auth Services ─────────────────────────────────────────────────────────────

import {
  onAuthChange,
  isAuthenticated,
  clearSession,
  getSessionToken,
} from './services/firebase/auth.service';

import {
  getStoredRole as getSessionRole,
  isAdmin    as isSessionAdmin,
  isTeacher  as isSessionTeacher,
  isStudent  as isSessionStudent,
} from './utils/roles';

// ── Pages ─────────────────────────────────────────────────────────────────────

import { LoginPage }               from './pages/LoginPage';
import { ProfilePage }             from './pages/ProfilePage';
import { AttendancePage }          from './pages/AttendancePage';
import { HistoryPage }             from './pages/HistoryPage';
import RoleLandingPage             from './pages/RoleLandingPage';
import FaceRegistrationPage        from './pages/FaceRegistrationPage';
import QRCodePage                  from './pages/QRCodePage';
import BatchImportPage             from './pages/BatchImportPage';
import StudentManagementPage       from './pages/StudentManagementPage';
import CourseManagementPage        from './pages/CourseManagementPage';
import AdminTimetablePage          from './pages/AdminTimetablePage';
import StudentDashboardPage       from './pages/StudentDashboardPage';

// ★ Replaced AdminAnalyticsPage with the new real-time analytics page
import AttendanceAnalyticsPage from './pages/AttendanceAnalyticsPage';

// ── Types ─────────────────────────────────────────────────────────────────────

export type UserRole = 'admin' | 'teacher' | 'student' | null;

// ── Role Helpers ──────────────────────────────────────────────────────────────

export function getStoredRole(): UserRole { return getSessionRole(); }
export function isAdmin()   { return isSessionAdmin(getStoredRole()); }
export function isTeacher() { return isSessionTeacher(getStoredRole()); }
export function isStudent() { return isSessionStudent(getStoredRole()); }

// ── Route Permissions ─────────────────────────────────────────────────────────

const ROLE_ALLOWED: Record<NonNullable<UserRole>, string[]> = {
  admin: [
    '/dashboard', '/attendance', '/face', '/face-registration', '/history',
    '/analytics', '/batch-import', '/student-management', '/qr-attendance',
    '/course-management', '/settings', '/timetable', '/class-views', '/profile', '/student-dashboard',
  ],
  teacher: [
    '/dashboard', '/attendance', '/face', '/face-registration', '/history',
    '/analytics', '/batch-import', '/student-management', '/qr-attendance',
    '/course-management', '/settings', '/timetable', '/class-views', '/profile', '/student-dashboard',
  ],
  student: ['/dashboard', '/face', '/history', '/analytics', '/profile', '/student-dashboard'],
};

function defaultRouteFor(role: UserRole): string {
  switch (role) {
    case 'admin':
    case 'teacher':
    case 'student':
      return '/dashboard';
    default:
      return '/login';
  }
}

function isAllowed(role: UserRole, routePath: string): boolean {
  if (!role) return false;
  return ROLE_ALLOWED[role]?.includes(routePath) ?? false;
}

// ── Loading Screen ────────────────────────────────────────────────────────────

const LoadingScreen: React.FC = () => (
  <div
    style={{
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'center',
      height:         '100vh',
      background:     'var(--cream-100, #FAF6ED)',
    }}
  >
    <div
      style={{
        width:         40,
        height:        40,
        borderRadius:  '50%',
        border:        '3px solid #e2e8f0',
        borderTopColor:'#6366F1',
        animation:     'spin 0.8s linear infinite',
      }}
    />
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
  </div>
);

// ── Role-Aware Page Wrappers ──────────────────────────────────────────────────

/**
 * Students see their own live status dashboard; staff see the admin dashboard.
 */
const RoleDashboard: React.FC = () => <RoleLandingPage />;

/**
 * Students MUST NOT see teacher attendance tools — AttendancePage handles
 * this internally based on the stored role.
 */
const RoleAttendancePage: React.FC = () => <AttendancePage />;

const RoleAnalyticsPage: React.FC = () => {
  return <AttendanceAnalyticsPage />;
};

// ── Auth Gate ─────────────────────────────────────────────────────────────────

/**
 * Two-layer auth check:
 *
 * 1. **Synchronous** — `isAuthenticated()` checks the backend JWT immediately
 *    to avoid any flash of protected content.
 * 2. **Async** — `onAuthChange` subscribes to Firebase + storage events so
 *    the component re-evaluates whenever the session changes in any tab.
 */
const AuthGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authenticated, setAuthenticated] = useState<boolean | null>(() =>
    isAuthenticated() ? true : null,
  );

  useEffect(() => {
    const unsub = onAuthChange((_user: unknown) => {
      const ok = !!getSessionToken();
      if (!ok) clearSession();
      setAuthenticated(ok);
    });
    return unsub;
  }, []);

  if (authenticated === null) return <LoadingScreen />;
  if (!authenticated)         return <Navigate to="/login" replace />;
  return <>{children}</>;
};

// ── Role Gate ─────────────────────────────────────────────────────────────────

/**
 * Prevents deep-linking into routes the current role cannot access.
 * Redirects to the role's default landing page on violation.
 */
const RoleGate: React.FC<{ children: React.ReactNode; routePath: string }> = ({
  children,
  routePath,
}) => {
  const role = getStoredRole();
  if (!isAllowed(role, routePath)) {
    return <Navigate to={defaultRouteFor(role)} replace />;
  }
  return <>{children}</>;
};

// ── Protected Route ───────────────────────────────────────────────────────────

const ProtectedRoute: React.FC<{
  children:  React.ReactNode;
  routePath: string;
}> = ({ children, routePath }) => (
  <AuthGate>
    <RoleGate routePath={routePath}>{children}</RoleGate>
  </AuthGate>
);

// ── Shorthand helper ──────────────────────────────────────────────────────────

const protect = (path: string, el: React.ReactNode) => (
  <ProtectedRoute routePath={path}>{el}</ProtectedRoute>
);

// ── Public-Only Route ─────────────────────────────────────────────────────────

/** Redirects authenticated users away from public pages (e.g. /login). */
const PublicOnlyRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (isAuthenticated()) {
    return <Navigate to={defaultRouteFor(getStoredRole())} replace />;
  }
  return <>{children}</>;
};

// ── Default Redirect ──────────────────────────────────────────────────────────

/** Sends unauthenticated users to /login; authenticated users to their home. */
const DefaultRedirect: React.FC = () => {
  if (!getSessionToken()) return <Navigate to="/login" replace />;
  return <Navigate to={defaultRouteFor(getStoredRole())} replace />;
};

// ── AppRouter ─────────────────────────────────────────────────────────────────

export const AppRouter: React.FC = () => (
  <BrowserRouter
    future={{
      v7_startTransition:   true,
      v7_relativeSplatPath: true,
    }}
  >
    <Routes>

      {/* ── Public ───────────────────────────────────────────────────────── */}

      <Route path="/index.html" element={<Navigate to="/" replace />} />

      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />

      {/* ── Dashboard (role-aware) ────────────────────────────────────────── */}

      <Route
        path="/dashboard"
        element={protect('/dashboard', <RoleDashboard />)}
      />

      {/* ── Attendance (role-aware) ───────────────────────────────────────── */}
      {/*
          Students  → self-only live status
          Teachers / Admins → full attendance tools
      */}

      <Route
        path="/attendance"
        element={protect('/attendance', <RoleAttendancePage />)}
      />

      {/* ── Face Registration / Live Camera ──────────────────────────────── */}

      <Route
        path="/face"
        element={protect('/face', <FaceRegistrationPage />)}
      />

      <Route
        path="/face-registration"
        element={protect('/face-registration', <FaceRegistrationPage />)}
      />

      {/* ── History ──────────────────────────────────────────────────────── */}

      <Route
        path="/history"
        element={protect('/history', <HistoryPage />)}
      />

      {/* /status alias — students reach their own attendance history here */}
      <Route
        path="/status"
        element={protect('/history', <HistoryPage />)}
      />
      {/* ── Student Dashboard ─────────────────────────────────────────────── */}

      <Route
        path="/student-dashboard"
        element={protect('/student-dashboard', <StudentDashboardPage />)}
      />
      {/* ── Profile ──────────────────────────────────────────────────────── */}

      <Route
        path="/profile"
        element={protect('/profile', <ProfilePage />)}
      />

      {/* ── Admin Only ───────────────────────────────────────────────────── */}

      {/*
        /analytics — Real-time per-period attendance analytics.
        Replaces the old AdminAnalyticsPage.
        ROLE_ALLOWED['admin'] already includes '/analytics' → no changes needed
        to the permissions table.
      */}
      <Route
        path="/analytics"
        element={protect('/analytics', <RoleAnalyticsPage />)}
      />

      <Route
        path="/qr-attendance"
        element={protect('/qr-attendance', <QRCodePage />)}
      />

      <Route
        path="/settings"
        element={protect('/settings', <ProfilePage />)}
      />

      <Route
        path="/timetable"
        element={protect('/timetable', <AdminTimetablePage />)}
      />

      <Route
        path="/class-views"
        element={protect('/class-views', <AdminTimetablePage />)}
      />

      <Route
        path="/batch-import"
        element={protect('/batch-import', <BatchImportPage />)}
      />

      <Route
        path="/student-management"
        element={protect('/student-management', <StudentManagementPage />)}
      />

      <Route
        path="/course-management"
        element={protect('/course-management', <CourseManagementPage />)}
      />

      {/* ── Fallbacks ────────────────────────────────────────────────────── */}

      <Route path="/"  element={<DefaultRedirect />} />
      <Route path="*"  element={<DefaultRedirect />} />

    </Routes>
  </BrowserRouter>
);

export default AppRouter;