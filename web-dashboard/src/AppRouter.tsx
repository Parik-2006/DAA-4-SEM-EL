// src/AppRouter.tsx

import React, {
  useEffect,
  useState,
} from 'react';

import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
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
  getStoredRole as getSessionRole,
  isAdmin as isSessionAdmin,
  isTeacher as isSessionTeacher,
  isStudent as isSessionStudent,
} from './utils/roles';

// ─────────────────────────────────────────────────────────────
// Pages
// ─────────────────────────────────────────────────────────────

import { LoginPage } from './pages/LoginPage';

import { DashboardPage } from './pages/DashboardPage';

import { ProfilePage } from './pages/ProfilePage';

import { AttendancePage } from './pages/AttendancePage';

import { HistoryPage } from './pages/HistoryPage';

import { StudentDashboard } from './pages/StudentDashboard';

import BatchImportPage from './pages/BatchImportPage';

import StudentManagementPage from './pages/StudentManagementPage';

import CourseManagementPage from './pages/CourseManagementPage';

import AdminAnalyticsPage from './pages/AdminAnalyticsPage';

import AdminTimetablePage from './pages/AdminTimetablePage';
import FaceRegistrationPage from './pages/FaceRegistrationPage';

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

export type UserRole =
  | 'admin'
  | 'teacher'
  | 'faculty'
  | 'student'
  | null;

// ─────────────────────────────────────────────────────────────
// Role Helpers
// ─────────────────────────────────────────────────────────────

/**
 * Safe role normalization.
 *
 * Unknown role ALWAYS becomes student
 * (most restrictive access).
 */

export function getStoredRole(): UserRole {
  return getSessionRole();
}

export function isAdmin() {
  return isSessionAdmin(getStoredRole());
}

export function isTeacher() {
  return isSessionTeacher(getStoredRole());
}

export function isStudent() {
  return isSessionStudent(getStoredRole());
}

// ─────────────────────────────────────────────────────────────
// Route Permissions
// ─────────────────────────────────────────────────────────────

const ROLE_ALLOWED: Record<
  NonNullable<UserRole>,
  string[]
> = {

  admin: [

    '/dashboard',

    '/attendance',
    '/face',

    '/history',

    '/analytics',

    '/batch-import',

    '/student-management',

    '/course-management',

    '/timetable',

    '/class-views',

    '/profile',
  ],

  teacher: [

    '/dashboard',

    '/attendance',
    '/face',

    '/history',

    '/profile',
  ],

  student: [

    '/attendance',

    '/face',

    '/history',

    '/status',

    '/profile',
  ],
};

// ─────────────────────────────────────────────────────────────
// Default Redirect
// ─────────────────────────────────────────────────────────────

function defaultRouteFor(
  role: UserRole
): string {

  switch (
    role
  ) {

    case 'admin':
      return '/dashboard';

    case 'teacher':
      return '/dashboard';

    case 'faculty':
      return '/dashboard';

    case 'student':
      return '/attendance';

    default:
      return '/login';
  }
}

// ─────────────────────────────────────────────────────────────
// Route Permission Check
// ─────────────────────────────────────────────────────────────

function isAllowed(
  role: UserRole,
  routePath: string
): boolean {

  if (!role)
    return false;

  return ROLE_ALLOWED[
    role
  ]?.includes(
    routePath
  );
}

// ─────────────────────────────────────────────────────────────
// Loading Screen
// ─────────────────────────────────────────────────────────────

const LoadingScreen =
  () => (
    <div className="flex items-center justify-center h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600" />
    </div>
  );

// ─────────────────────────────────────────────────────────────
// Student-only attendance page
// IMPORTANT:
// Students MUST NOT see teacher attendance tools
// ─────────────────────────────────────────────────────────────

const StudentAttendancePage: React.FC =
  () => {

    const studentId =
      localStorage.getItem(
        'user_id'
      ) ?? '';

    return (
      <StudentDashboard
        studentId={
          studentId
        }
      />
    );
  };

// ─────────────────────────────────────────────────────────────
// Role-aware Dashboard
// ─────────────────────────────────────────────────────────────

const RoleDashboard: React.FC =
  () => {

    const role =
      getStoredRole();

    // Students never see
    // admin dashboard analytics.

    if (
      role ===
      'student'
    ) {

      const studentId =
        sessionStorage.getItem(
          'user_id'
        ) ?? '';

      return (
        <StudentDashboard
          studentId={
            studentId
          }
        />
      );
    }

    return (
      <DashboardPage />
    );
  };

// ─────────────────────────────────────────────────────────────
// Auth Gate
// ─────────────────────────────────────────────────────────────

interface AuthGateProps {
  children: React.ReactNode;
}

const AuthGate: React.FC<
  AuthGateProps
> = ({
  children,
}) => {

  const [
    isAuthenticated,
    setIsAuthenticated,
  ] =
    useState<
      boolean | null
    >(null);

  useEffect(() => {

    const unsub =
      onAuthChange(
        (
          user: unknown
        ) => {

          const hasFirebaseUser =
            !!user;

          const hasToken =
            !!getSessionToken();

          const authenticated =
            hasFirebaseUser ||
            hasToken;

          if (
            !authenticated
          ) {
            clearSession();
          }

          setIsAuthenticated(
            authenticated
          );
        }
      );

    return () =>
      unsub();

  }, []);

  if (
    isAuthenticated ===
    null
  ) {
    return (
      <LoadingScreen />
    );
  }

  if (
    !isAuthenticated
  ) {
    return (
      <Navigate
        to="/login"
        replace
      />
    );
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

const RoleGate: React.FC<
  RoleGateProps
> = ({
  children,
  routePath,
}) => {

  const role =
    getStoredRole();

  // Prevent deep-link access

  if (
    !isAllowed(
      role,
      routePath
    )
  ) {

    return (
      <Navigate
        to={defaultRouteFor(
          role
        )}
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
> = ({
  children,
  routePath,
}) => {

  return (
    <AuthGate>
      <RoleGate
        routePath={
          routePath
        }
      >
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
> = ({
  children,
}) => {

  const hasToken =
    !!getSessionToken();

  const role =
    getStoredRole();

  if (
    hasToken
  ) {

    return (
      <Navigate
        to={defaultRouteFor(
          role
        )}
        replace
      />
    );
  }

  return <>{children}</>;
};

// ─────────────────────────────────────────────────────────────
// Default Redirect
// ─────────────────────────────────────────────────────────────

const DefaultRedirect: React.FC =
  () => {

    const role =
      getStoredRole();

    const hasToken =
      !!getSessionToken();

    if (
      !hasToken
    ) {

      return (
        <Navigate
          to="/login"
          replace
        />
      );
    }

    return (
      <Navigate
        to={defaultRouteFor(
          role
        )}
        replace
      />
    );
  };

// ─────────────────────────────────────────────────────────────
// App Router
// ─────────────────────────────────────────────────────────────

const AppRouter: React.FC =
  () => {

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
            element={
              <Navigate
                to="/"
                replace
              />
            }
          />

          {/* ───────────────── DASHBOARD ───────────────── */}

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute routePath="/dashboard">
                <RoleDashboard />
              </ProtectedRoute>
            }
          />

          {/* ───────────────── ATTENDANCE ───────────────── */}

          {/* 
             STUDENTS:
             → self-only live status

             TEACHERS/ADMINS:
             → full attendance tools
          */}

          <Route
            path="/attendance"
            element={
              <ProtectedRoute routePath="/attendance">

                {isStudent() ? (
                  <StudentAttendancePage />
                ) : (
                  <AttendancePage />
                )}

              </ProtectedRoute>
            }
          />

          {/* Face registration / live camera (students + staff) */}
          <Route
            path="/face"
            element={
              <ProtectedRoute routePath="/face">
                <FaceRegistrationPage />
              </ProtectedRoute>
            }
          />

          {/* ───────────────── HISTORY ───────────────── */}

          {/* 
             HistoryPage MUST internally:
             - call getStudentHistory(studentId)
             - NEVER fetch all records for students
          */}

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

          {/* ───────────────── PROFILE ───────────────── */}

          <Route
            path="/profile"
            element={
              <ProtectedRoute routePath="/profile">
                <ProfilePage />
              </ProtectedRoute>
            }
          />

          {/* ───────────────── ADMIN ONLY ───────────────── */}

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

          {/* ───────────────── FALLBACKS ───────────────── */}

          <Route
            path="/"
            element={
              <DefaultRedirect />
            }
          />

          <Route
            path="*"
            element={
              <DefaultRedirect />
            }
          />

        </Routes>
      </BrowserRouter>
    );
  };

export default AppRouter;