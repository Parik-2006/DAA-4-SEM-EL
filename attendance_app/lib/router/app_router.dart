import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:smart_attendance/providers/auth_provider.dart';
import 'package:smart_attendance/screens/admin/admin_dashboard_screen.dart';
import 'package:smart_attendance/screens/attendance/attendance_screen.dart';
import 'package:smart_attendance/screens/attendance/dashboard_screen.dart';
import 'package:smart_attendance/screens/attendance/live_camera_screen.dart';
import 'package:smart_attendance/screens/attendance/qr_scan_screen.dart';
import 'package:smart_attendance/screens/auth/login_screen.dart';
import 'package:smart_attendance/screens/auth/login_type_screen.dart';
import 'package:smart_attendance/screens/auth/register_screen.dart';
import 'package:smart_attendance/screens/auth/student_registration_screen.dart';
import 'package:smart_attendance/screens/history/enhanced_history_screen.dart';
import 'package:smart_attendance/screens/history/history_screen.dart';
import 'package:smart_attendance/screens/home/home_screen.dart';
import 'package:smart_attendance/screens/profile/profile_screen.dart';
import 'package:smart_attendance/screens/shell/main_shell.dart';
import 'package:smart_attendance/screens/splash_screen.dart';
import 'package:smart_attendance/screens/student/student_dashboard_screen.dart';
import 'package:smart_attendance/screens/auth/forgot_password_screen.dart';

// Route name constants
class AppRoutes {
  static const splash = '/';
  static const loginType = '/login-type';
  static const login = '/login';
  static const register = '/register';
  static const forgotPassword = '/forgot-password';
  static const studentRegistration = '/student-registration';
  static const home = '/home';
  static const attendance = '/attendance';
  static const dashboard = '/dashboard';
  static const adminDashboard = '/admin-dashboard';
  static const studentDashboard = '/student-dashboard';
  static const liveCamera = '/live-camera';
  static const qrScan = '/qr-scan';
  static const history = '/history';
  static const enhancedHistory = '/history-enhanced';
  static const profile = '/profile';
}

final appRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: true,
    redirect: (context, state) {
      final isLoading = authState.status == AuthStatus.initial ||
          authState.status == AuthStatus.loading;
      final isAuthenticated = authState.isAuthenticated;
      final isAdmin = authState.isAdmin;
      final isStudent = authState.isStudent;
      final currentPath = state.matchedLocation;

      // Wait while auth state initializes
      if (isLoading && currentPath != AppRoutes.splash) {
        return AppRoutes.splash;
      }

      final isOnAuthPage = currentPath == AppRoutes.login ||
          currentPath == AppRoutes.loginType ||
          currentPath == AppRoutes.register ||
          currentPath == AppRoutes.studentRegistration;

      // Redirect unauthenticated users to login-type
      if (!isLoading && !isAuthenticated && !isOnAuthPage &&
          currentPath != AppRoutes.splash) {
        return AppRoutes.loginType;
      }

      // Redirect authenticated users away from auth pages
      if (!isLoading && isAuthenticated && isOnAuthPage) {
        // Route to appropriate dashboard based on role
        if (isAdmin) {
          return AppRoutes.adminDashboard;
        } else if (isStudent) {
          return AppRoutes.studentDashboard;
        }
        return AppRoutes.home;
      }

      // Role-based dashboard routing
      if (!isLoading && isAuthenticated) {
        if (isAdmin && currentPath != AppRoutes.adminDashboard) {
          // Allow admins to visit all routes
          return null;
        } else if (isStudent && currentPath == AppRoutes.adminDashboard) {
          return AppRoutes.studentDashboard;
        }
      }

      return null;
    },
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: AppRoutes.loginType,
        pageBuilder: (context, state) => _fadeTransition(
          state,
          const LoginTypeScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.login,
        pageBuilder: (context, state) => _fadeTransition(
          state,
          LoginScreen(
            role: state.extra as String?,
          ),
        ),
      ),
      GoRoute(
        path: AppRoutes.register,
        pageBuilder: (context, state) => _slideTransition(
          state,
          const RegisterScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.forgotPassword,
        pageBuilder: (context, state) => _slideTransition(
          state,
          const ForgotPasswordScreen(),
        ),
      ),
      GoRoute(
        path: AppRoutes.studentRegistration,
        pageBuilder: (context, state) => _slideTransition(
          state,
          const StudentRegistrationScreen(),
        ),
      ),
      // Admin Dashboard (full-screen)
      GoRoute(
        path: AppRoutes.adminDashboard,
        pageBuilder: (context, state) => _noTransition(
          state,
          const AdminDashboardScreen(),
        ),
      ),
      // Student Dashboard (full-screen)
      GoRoute(
        path: AppRoutes.studentDashboard,
        pageBuilder: (context, state) => _noTransition(
          state,
          const StudentDashboardScreen(),
        ),
      ),
      // Main app shell with bottom nav
      ShellRoute(
        builder: (context, state, child) => MainShell(child: child),
        routes: [
          GoRoute(
            path: AppRoutes.home,
            pageBuilder: (context, state) => _noTransition(
              state,
              const HomeScreen(),
            ),
          ),
          GoRoute(
            path: AppRoutes.attendance,
            pageBuilder: (context, state) => _noTransition(
              state,
              const AttendanceScreen(),
            ),
          ),
          GoRoute(
            path: AppRoutes.history,
            pageBuilder: (context, state) => _noTransition(
              state,
              const HistoryScreen(),
            ),
          ),
          GoRoute(
            path: AppRoutes.profile,
            pageBuilder: (context, state) => _noTransition(
              state,
              const ProfileScreen(),
            ),
          ),
        ],
      ),
      // Attendance dashboard (full-screen)
      GoRoute(
        path: AppRoutes.dashboard,
        pageBuilder: (context, state) => _slideTransition(
          state,
          const AttendanceDashboardScreen(),
        ),
      ),
      // Enhanced history (full-screen)
      GoRoute(
        path: AppRoutes.enhancedHistory,
        pageBuilder: (context, state) => _slideTransition(
          state,
          const EnhancedHistoryScreen(),
        ),
      ),
      // Full-screen QR scanner (outside shell)
      GoRoute(
        path: AppRoutes.qrScan,
        pageBuilder: (context, state) => _slideUpTransition(
          state,
          const QrScanScreen(),
        ),
      ),
      // Full-screen live camera (outside shell)
      GoRoute(
        path: AppRoutes.liveCamera,
        pageBuilder: (context, state) => _slideUpTransition(
          state,
          const LiveCameraScreen(),
        ),
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            Text('Page not found: ${state.error}'),
            TextButton(
              onPressed: () => context.go(AppRoutes.home),
              child: const Text('Go Home'),
            ),
          ],
        ),
      ),
    ),
  );
});
              child: const Text('Go Home'),
            ),
          ],
        ),
      ),
    ),
  );
});

// ── Page Transitions ──────────────────────────────────────────────────────────

CustomTransitionPage _fadeTransition(GoRouterState state, Widget child) {
  return CustomTransitionPage(
    key: state.pageKey,
    child: child,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      return FadeTransition(opacity: animation, child: child);
    },
  );
}

CustomTransitionPage _slideTransition(GoRouterState state, Widget child) {
  return CustomTransitionPage(
    key: state.pageKey,
    child: child,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      final tween = Tween(
        begin: const Offset(1, 0),
        end: Offset.zero,
      ).chain(CurveTween(curve: Curves.easeInOut));
      return SlideTransition(position: animation.drive(tween), child: child);
    },
  );
}

CustomTransitionPage _slideUpTransition(GoRouterState state, Widget child) {
  return CustomTransitionPage(
    key: state.pageKey,
    child: child,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      final tween = Tween(
        begin: const Offset(0, 1),
        end: Offset.zero,
      ).chain(CurveTween(curve: Curves.easeOut));
      return SlideTransition(position: animation.drive(tween), child: child);
    },
  );
}

NoTransitionPage _noTransition(GoRouterState state, Widget child) {
  return NoTransitionPage(key: state.pageKey, child: child);
}
