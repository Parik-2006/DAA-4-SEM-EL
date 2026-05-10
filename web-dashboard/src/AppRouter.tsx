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
  isAdmin as isSessionAdmin,
  isTeacher as isSessionTeacher,
  isStudent as isSessionStudent,
} from './utils/roles';

// ── Pages ─────────────────────────────────────────────────────────────────────

import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages';
import { ProfilePage } from './pages/ProfilePage';
import { AttendancePage } from './pages/AttendancePage';
import { HistoryPage } from './pages/HistoryPage';
import { StudentDashboard } from './pages/StudentDashboard';
import FaceRegistrationPage from './pages/FaceRegistrationPage';
import BatchImportPage from './pages/BatchImportPage';
import StudentManagementPage from './pages/StudentManagementPage';
import CourseManagementPage from './pages/CourseManagementPage';
import AdminAnalyticsPage from './pages/AdminAnalyticsPage';
import AdminTimetablePage from './pages/AdminTimetablePage';
import { Layout } from './components';

// ── Types ─────────────────────────────────────────────────────────────────────

export type UserRole = 'admin' | 'teacher' | 'student' | null;

// ── Role Helpers ──────────────────────────────────────────────────────────────

export function getStoredRole(): UserRole {
  return getSessionRole();
}
export function isAdmin() { return isSessionAdmin(getStoredRole()); }
export function isTeacher() { return isSessionTeacher(getStoredRole()); }
export function isStudent() { return isSessionStudent(getStoredRole()); }

// ── Route Permissions ─────────────────────────────────────────────────────────

const ROLE_ALLOWED: Record<NonNullable<UserRole>, string[]> = {
  admin: [
    '/dashboard', '/attendance', '/face', '/history',
    '/analytics', '/batch-import', '/student-management',
    '/course-management', '/timetable', '/class-views', '/profile',
  ],
  teacher: ['/dashboard', '/attendance', '/face', '/history', '/profile'],
  student: ['/attendance', '/face', '/history', '/status', '/profile'],
};

function defaultRouteFor(role: UserRole): string {
  switch (role) {
    case 'admin':
    case 'teacher':
      return '/dashboard';
    case 'student':
      return '/attendance';
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
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      background: 'var(--cream-100, #FAF6ED)',
    }}
  >
    <div
      style={{
        width: 40,
        height: 40,
        borderRadius: '50%',
        border: '3px solid #e2e8f0',
        borderTopColor: '#6366F1',
        animation: 'spin 0.8s linear infinite',
      }}
    />
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
  </div>
);

// ── Role-Aware Pages ──────────────────────────────────────────────────────────

/**
 * Students see their own live status dashboard; staff see the admin dashboard.
 */
const RoleDashboard: React.FC = () => {
  const role = getStoredRole();
  if (role === 'student') {
    const studentId = sessionStorage.getItem('user_id') ?? '';
    return <StudentDashboard studentId={studentId} />;
  }
  return <DashboardPage />;
};

/**
 * Students see their own attendance status; teachers/admins see full tools.
 * IMPORTANT: Students MUST NOT see teacher attendance tools.
 */
const RoleAttendancePage: React.FC = () => {
  if (isStudent()) {
    const studentId = sessionStorage.getItem('user_id') ?? '';
    return (
      <Layout>
        <StudentDashboard studentId={studentId} />
      </Layout>
    );
  }
  return <AttendancePage />;
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
    isAuthenticated() ? true : null
  );

  useEffect(() => {
    const unsub = onAuthChange((user: unknown) => {
      const hasToken = !!getSessionToken();
      const ok = hasToken;
      if (!ok) clearSession();
      setAuthenticated(ok);
    });
    return unsub;
  }, []);

  if (authenticated === null) return <LoadingScreen />;
  if (!authenticated) return <Navigate to="/login" replace />;
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

const ProtectedRoute: React.FC<{ children: React.ReactNode; routePath: string }> = ({
  children,
  routePath,
}) => (
  <AuthGate>
    <RoleGate routePath={routePath}>{children}</RoleGate>
  </AuthGate>
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
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    }}
  >
    <Routes>

      {/* ── Public ───────────────────────────────────────────────── */}

      <Route path="/index.html" element={<Navigate to="/" replace />} />

      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />

      {/* ── Dashboard (role-aware) ────────────────────────────────── */}

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute routePath="/dashboard">
            <RoleDashboard />
          </ProtectedRoute>
        }
      />

      {/* ── Attendance (role-aware) ───────────────────────────────── */}
      {/*
          Students → self-only live status (StudentDashboard)
          Teachers / Admins → full attendance tools (AttendancePage)
          HistoryPage MUST internally call getStudentHistory(studentId)
          and NEVER fetch all records for students.
      */}

      <Route
        path="/attendance"
        element={
          <ProtectedRoute routePath="/attendance">
            <RoleAttendancePage />
          </ProtectedRoute>
        }
      />

      {/* ── Face Registration / Live Camera ──────────────────────── */}

      <Route
        path="/face"
        element={
          <ProtectedRoute routePath="/face">
            <FaceRegistrationPage />
          </ProtectedRoute>
        }
      />

      {/* ── History ──────────────────────────────────────────────── */}

      <Route
        path="/history"
        element={
          <ProtectedRoute routePath="/history">
            <HistoryPage />
          </ProtectedRoute>
        }
      />

      {/* /status is an alias for students to reach their history */}
      <Route
        path="/status"
        element={
          <ProtectedRoute routePath="/status">
            <HistoryPage />
          </ProtectedRoute>
        }
      />

      {/* ── Profile ──────────────────────────────────────────────── */}

      <Route
        path="/profile"
        element={
          <ProtectedRoute routePath="/profile">
            <ProfilePage />
          </ProtectedRoute>
        }
      />

      {/* ── Admin Only ───────────────────────────────────────────── */}

      <Route
        path="/analytics"
        element={
          <ProtectedRoute routePath="/analytics">
            <AdminAnalyticsPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/timetable"
        element={
          <ProtectedRoute routePath="/timetable">
            <AdminTimetablePage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/class-views"
        element={
          <ProtectedRoute routePath="/class-views">
            <AdminTimetablePage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/batch-import"
        element={
          <ProtectedRoute routePath="/batch-import">
            <BatchImportPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/student-management"
        element={
          <ProtectedRoute routePath="/student-management">
            <StudentManagementPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/course-management"
        element={
          <ProtectedRoute routePath="/course-management">
            <CourseManagementPage />
          </ProtectedRoute>
        }
      />

      {/* ── Fallbacks ─────────────────────────────────────────────── */}

      <Route path="/" element={<DefaultRedirect />} />
      <Route path="*" element={<DefaultRedirect />} />

    </Routes>
  </BrowserRouter>
);

export default AppRouter;