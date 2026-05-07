// src/AppRouter.tsx

import React, { useEffect, useState } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom';

// ─────────────────────────────────────────────────────────────
// Auth Services
// ─────────────────────────────────────────────────────────────

import {
  onAuthChange,
  clearSession,
  getSessionToken,
} from './services/firebase/auth.service';

import {
  getStoredRole,
  isAdmin,
  isTeacher,
  isStudent,
} from './utils/roles';

// ─────────────────────────────────────────────────────────────
// Pages
// ─────────────────────────────────────────────────────────────

import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import RoleLandingPage from './pages/RoleLandingPage';
import AdminAnalyticsPage from './pages/AdminAnalyticsPage';
import AdminTimetablePage from './pages/AdminTimetablePage';
import { ProfilePage } from './pages/ProfilePage';
import { AttendancePage } from './pages/AttendancePage';
import { HistoryPage } from './pages/HistoryPage';

import BatchImportPage from './pages/BatchImportPage';
import StudentManagementPage from './pages/StudentManagementPage';
import CourseManagementPage from './pages/CourseManagementPage';

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

type UserRole = 'admin' | 'teacher' | 'student' | null;

function defaultRouteFor(role: UserRole): string {
  switch (role) {
    case 'admin':
      return '/dashboard';

    case 'teacher':
      return '/dashboard';

    case 'student':
      return '/attendance';

    default:
      return '/login';
  }
}

// ─────────────────────────────────────────────────────────────
// Role Permissions
// ─────────────────────────────────────────────────────────────

const ROLE_ALLOWED: Record<
  NonNullable<UserRole>,
  string[]
> = {
  admin: [
    '/dashboard',
    '/history',
    '/batch-import',
    '/student-management',
    '/course-management',
    '/timetable',
    '/class-views',
    '/analytics',
  ],

  teacher: [
    '/dashboard',
    '/attendance',
    '/history',
  ],

  student: [
    '/attendance',
    '/history',
    '/status',
  ],
};

function isAllowed(
  role: UserRole,
  routePath: string
): boolean {
  if (!role) return false;

  return ROLE_ALLOWED[role].includes(routePath);
}

// ─────────────────────────────────────────────────────────────
// Loading Screen
// ─────────────────────────────────────────────────────────────

const LoadingScreen = () => (
  <div className="flex items-center justify-center h-screen">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600" />
  </div>
);

// ─────────────────────────────────────────────────────────────
// Auth Gate
// ─────────────────────────────────────────────────────────────

interface AuthGateProps {
  children: React.ReactNode;
}

const AuthGate: React.FC<AuthGateProps> = ({
  children,
}) => {
  const [isAuthenticated, setIsAuthenticated] =
    useState<boolean | null>(null);

  useEffect(() => {
    const unsub = onAuthChange((user: unknown) => {
      const hasFirebaseUser = !!user;

      const hasToken = !!getSessionToken();

      const authenticated =
        hasFirebaseUser || hasToken;

      if (!authenticated) {
        clearSession();
      }

      setIsAuthenticated(authenticated);
    });

    return () => unsub();
  }, []);

  if (isAuthenticated === null) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// ─────────────────────────────────────────────────────────────
// Role Gate
// ─────────────────────────────────────────────────────────────

interface RoleGateProps {
  children: React.ReactNode;
  routePath: string;
}

const RoleGate: React.FC<RoleGateProps> = ({
  children,
  routePath,
}) => {
  const role = getStoredRole();

  if (!isAllowed(role, routePath)) {
    return (
      <Navigate
        to={defaultRouteFor(role)}
        replace
      />
    );
  }

  return <>{children}</>;
};

// ─────────────────────────────────────────────────────────────
// Protected Route
// ─────────────────────────────────────────────────────────────

interface ProtectedRouteProps {
  children: React.ReactNode;
  routePath: string;
}

const ProtectedRoute: React.FC<
  ProtectedRouteProps
> = ({ children, routePath }) => {
  return (
    <AuthGate>
      <RoleGate routePath={routePath}>
        {children}
      </RoleGate>
    </AuthGate>
  );
};

// ─────────────────────────────────────────────────────────────
// Public Only Route
// ─────────────────────────────────────────────────────────────

interface PublicOnlyRouteProps {
  children: React.ReactNode;
}

const PublicOnlyRoute: React.FC<
  PublicOnlyRouteProps
> = ({ children }) => {
  const hasToken =
    !!getSessionToken();

  const role = getStoredRole();

  if (hasToken) {
    return (
      <Navigate
        to={defaultRouteFor(role)}
        replace
      />
    );
  }

  return <>{children}</>;
};

// ─────────────────────────────────────────────────────────────
// Default Redirect
// ─────────────────────────────────────────────────────────────

const DefaultRedirect: React.FC = () => {
  const role = getStoredRole();

  const hasToken =
    !!getSessionToken();

  if (!hasToken) {
    return <Navigate to="/login" replace />;
  }

  return (
    <Navigate
      to={defaultRouteFor(role)}
      replace
    />
  );
};

// ─────────────────────────────────────────────────────────────
// App Router
// ─────────────────────────────────────────────────────────────

const AppRouter: React.FC = () => {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Routes>

        {/* ───────────────── PUBLIC ───────────────── */}

        <Route
          path="/login"
          element={
            <PublicOnlyRoute>
              <LoginPage />
            </PublicOnlyRoute>
          }
        />

        <Route
          path="/index.html"
          element={<Navigate to="/" replace />}
        />

        {/* ───────────────── ADMIN ───────────────── */}

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute routePath="/dashboard">
              <RoleLandingPage />
            </ProtectedRoute>
          }
        />

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

        {/* ───────────────── SHARED ───────────────── */}

        <Route
          path="/attendance"
          element={
            <ProtectedRoute routePath="/attendance">
              <AttendancePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/live-attendance"
          element={
            <ProtectedRoute routePath="/live-attendance">
              <AttendancePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/mark-attendance"
          element={
            <ProtectedRoute routePath="/mark-attendance">
              <AttendancePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/history"
          element={
            <ProtectedRoute routePath="/history">
              <HistoryPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/status"
          element={
            <ProtectedRoute routePath="/status">
              <HistoryPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/profile"
          element={
            <ProtectedRoute routePath="/profile">
              <ProfilePage />
            </ProtectedRoute>
          }
        />

        {/* ───────────────── EXTRA ───────────────── */}

        {/* ───────────────── FALLBACK ───────────────── */}

        <Route path="/" element={<DefaultRedirect />} />

        <Route
          path="*"
          element={<DefaultRedirect />}
        />

      </Routes>
    </BrowserRouter>
  );
};

export default AppRouter;