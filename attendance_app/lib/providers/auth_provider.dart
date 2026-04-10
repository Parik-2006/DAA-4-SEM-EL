import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smart_attendance/models/user_model.dart';
import 'package:smart_attendance/services/auth_service.dart';

// ── Auth State ────────────────────────────────────────────────────────────────

enum AuthStatus { initial, authenticated, unauthenticated, loading, error }

class AuthState {
  final AuthStatus status;
  final UserModel? user;
  final String? errorMessage;

  const AuthState({
    required this.status,
    this.user,
    this.errorMessage,
  });

  const AuthState.initial() : this(status: AuthStatus.initial);
  const AuthState.loading() : this(status: AuthStatus.loading);
  const AuthState.authenticated(UserModel user)
      : this(status: AuthStatus.authenticated, user: user);
  const AuthState.unauthenticated() : this(status: AuthStatus.unauthenticated);
  AuthState.error(String message)
      : this(status: AuthStatus.error, errorMessage: message);

  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isLoading => status == AuthStatus.loading;

  AuthState copyWith({
    AuthStatus? status,
    UserModel? user,
    String? errorMessage,
  }) {
    return AuthState(
      status: status ?? this.status,
      user: user ?? this.user,
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
      state = AuthState.authenticated(result.user);
    } on ApiException catch (e) {
      state = AuthState.error(e.message);
    } catch (_) {
      state = AuthState.error('Login failed. Please try again.');
    }
  }

  Future<void> register({
    required String name,
    required String email,
    required String password,
    required String studentId,
    String? department,
    String? semester,
  }) async {
    state = const AuthState.loading();
    try {
      await _authService.register(
        name: name,
        email: email,
        password: password,
        studentId: studentId,
        department: department,
        semester: semester,
      );
      // Auto-login after registration
      await login(email: email, password: password);
    } on ApiException catch (e) {
      state = AuthState.error(e.message);
    } catch (_) {
      state = AuthState.error('Registration failed. Please try again.');
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
