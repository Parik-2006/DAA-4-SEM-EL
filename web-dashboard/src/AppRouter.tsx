import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { onAuthChange } from './services/firebase/auth.service';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { ProfilePage } from './pages/ProfilePage';
import { AttendancePage } from './pages/AttendancePage';
import FaceRegistrationPage from './pages/FaceRegistrationPage';
import QRCodePage from './pages/QRCodePage';
import BatchImportPage from './pages/BatchImportPage';
import StudentManagementPage from './pages/StudentManagementPage';
import CourseManagementPage from './pages/CourseManagementPage';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = React.useState<boolean | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthChange((user: unknown) => {
      setIsAuthenticated(!!user);
    });
    return () => unsubscribe();
  }, []);

  if (isAuthenticated === null) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600" />
      </div>
    );
  }

  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
};

export const AppRouter: React.FC = () => {
  return (
    // future flags silence the v6 → v7 upgrade warnings
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/attendance"
          element={
            <ProtectedRoute>
              <AttendancePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/face-registration"
          element={
            <ProtectedRoute>
              <FaceRegistrationPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/qr-attendance"
          element={
            <ProtectedRoute>
              <QRCodePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/batch-import"
          element={
            <ProtectedRoute>
              <BatchImportPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/student-management"
          element={
            <ProtectedRoute>
              <StudentManagementPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/course-management"
          element={
            <ProtectedRoute>
              <CourseManagementPage />
            </ProtectedRoute>
          }
        />

        {/* Default redirect */}
        <Route path="/" element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  );
};
