import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smart_attendance/models/user_model.dart';
import 'package:smart_attendance/services/auth_service.dart';

// ── Auth State ────────────────────────────────────────────────────────────────

enum AuthStatus { initial, authenticated, unauthenticated, loading, error }

class AuthState {
  final AuthStatus status;
  final UserModel? user;
  final String? role; // 'admin' or 'student'
  final String? userId;
  final String? errorMessage;

  const AuthState({
    required this.status,
    this.user,
    this.role,
    this.userId,
    this.errorMessage,
  });

  const AuthState.initial() : this(status: AuthStatus.initial);
  const AuthState.loading() : this(status: AuthStatus.loading);
  const AuthState.authenticated(UserModel user, {String? role, String? userId})
      : this(
          status: AuthStatus.authenticated,
          user: user,
          role: role,
          userId: userId,
        );
  const AuthState.unauthenticated() : this(status: AuthStatus.unauthenticated);
  AuthState.error(String message)
      : this(status: AuthStatus.error, errorMessage: message);

  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isLoading => status == AuthStatus.loading;
  bool get isAdmin => role?.toLowerCase() == 'admin';
  bool get isStudent => role?.toLowerCase() == 'student';

  AuthState copyWith({
    AuthStatus? status,
    UserModel? user,
    String? role,
    String? userId,
    String? errorMessage,
  }) {
    return AuthState(
      status: status ?? this.status,
      user: user ?? this.user,
      role: role ?? this.role,
      userId: userId ?? this.userId,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }
}

// ── Auth Notifier ─────────────────────────────────────────────────────────────

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthService _authService;

  AuthNotifier(this._authService) : super(const AuthState.initial()) {
    checkAuthStatus();
  }

  /// Called on app launch to restore session
  Future<void> checkAuthStatus() async {
    state = const AuthState.loading();
    try {
      final isAuth = await _authService.isAuthenticated();
      if (isAuth) {
        final user = await _authService.getMe();
        state = AuthState.authenticated(user);
      } else {
        state = const AuthState.unauthenticated();
      }
    } catch (_) {
      state = const AuthState.unauthenticated();
    }
  }

  Future<void> login({
    required String email,
    required String password,
  }) async {
    state = const AuthState.loading();
    try {
      final result = await _authService.login(
        email: email,
        password: password,
      );
      state = AuthState.authenticated(
        result.user,
        role: result.role,
        userId: result.userId,
      );
    } on DioException catch (e) {
      state = AuthState.error(e.message ?? 'Login failed');
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }

  Future<void> register({
    required String name,
    required String email,
    required String password,
    required String role, // 'admin' or 'student'
    String? studentId,
    String? department,
    String? semester,
  }) async {
    state = const AuthState.loading();
    try {
      await _authService.register(
        name: name,
        email: email,
        password: password,
        role: role,
      );
      // Auto-login after registration
      await login(email: email, password: password);
    } on DioException catch (e) {
      state = AuthState.error(e.message ?? 'Registration failed');
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }

  Future<void> logout() async {
    await _authService.logout();
    state = const AuthState.unauthenticated();
  }

  void clearError() {
    if (state.status == AuthStatus.error) {
      state = const AuthState.unauthenticated();
    }
  }
}

// ── Providers ─────────────────────────────────────────────────────────────────

final authServiceProvider = Provider<AuthService>((ref) => AuthService());

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.watch(authServiceProvider));
});

/// Convenience provider: current logged-in user (nullable)
final currentUserProvider = Provider<UserModel?>((ref) {
  return ref.watch(authProvider).user;
});

/// Convenience provider: is user authenticated
final isAuthenticatedProvider = Provider<bool>((ref) {
  return ref.watch(authProvider).isAuthenticated;
});
