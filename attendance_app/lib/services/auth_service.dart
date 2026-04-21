import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:smart_attendance/models/user_model.dart';
import 'package:smart_attendance/services/api_service.dart';
import 'package:dio/dio.dart';

class AuthService {
  final _api = ApiService.instance;
  final _storage = const FlutterSecureStorage();

  static const _tokenKey = 'access_token';
  static const _userRoleKey = 'user_role';
  static const _userIdKey = 'user_id';

  /// Login with email + password (calls backend /api/v1/user/login)
  Future<AuthLoginResult> login({
    required String email,
    required String password,
  }) async {
    try {
      final response = await _api.post(
        '/api/v1/user/login',
        data: {
          'email': email,
          'password': password,
        },
      );

      final userId = response.data['user_id'] as String;
      final role = response.data['role'] as String;
      final token = response.data['token'] as String?;

      // Store token and role securely
      await _storage.write(key: _tokenKey, value: token ?? '');
      await _storage.write(key: _userRoleKey, value: role);
      await _storage.write(key: _userIdKey, value: userId);

      // Fetch full user profile
      final userProfile = await getProfile(userId);

      return AuthLoginResult(
        userId: userId,
        role: role,
        token: token,
        user: userProfile,
      );
    } catch (e) {
      if (e is DioException) {
        throw ApiException(
          message: e.response?.data['detail'] ?? 'Login failed',
          data: e.toString(),
        );
      }
      throw ApiException(
        message: 'Login failed. Please try again.',
        data: e.toString(),
      );
    }
  }

  /// Register a new user (admin or student)
  Future<AuthRegisterResult> register({
    required String name,
    required String email,
    required String password,
    required String role, // 'admin' or 'student'
  }) async {
    try {
      final response = await _api.post(
        '/api/v1/user/register',
        data: {
          'email': email,
          'password': password,
          'name': name,
          'role': role,
        },
      );

      final userId = response.data['user_id'] as String;

      return AuthRegisterResult(
        userId: userId,
        message: response.data['message'] as String? ?? 'Registration successful',
      );
    } catch (e) {
      if (e is DioException) {
        throw ApiException(
          message: e.response?.data['detail'] ?? 'Registration failed',
          data: e.toString(),
        );
      }
      throw ApiException(
        message: 'Registration failed. Please try again.',
        data: e.toString(),
      );
    }
  }

  /// Fetch user profile by user ID
  Future<UserModel> getProfile(String userId) async {
    try {
      final response = await _api.get(
        '/api/v1/user/profile/$userId',
      );

      final userData = response.data as Map<String, dynamic>;
      return UserModel.fromJson(userData);
    } catch (e) {
      throw ApiException(
        message: 'Failed to load profile.',
        data: e.toString(),
      );
    }
  }

  /// Clear all stored tokens and data (logout)
  Future<void> logout() async {
    try {
      await _api.post('/api/v1/user/logout');
    } catch (_) {
      // Don't block logout if server call fails
    } finally {
      await _storage.deleteAll();
    }
  }

  /// Check if a valid token exists in secure storage
  Future<bool> isAuthenticated() async {
    final token = await _storage.read(key: _tokenKey);
    return token != null && token.isNotEmpty;
  }

  /// Retrieve stored access token
  Future<String?> getStoredToken() => _storage.read(key: _tokenKey);

  /// Get stored user role
  Future<String?> getStoredRole() => _storage.read(key: _userRoleKey);

  /// Get stored user ID
  Future<String?> getStoredUserId() => _storage.read(key: _userIdKey);
}

class AuthLoginResult {
  final String userId;
  final String role;
  final String? token;
  final UserModel user;

  const AuthLoginResult({
    required this.userId,
    required this.role,
    required this.token,
    required this.user,
  });
}

class AuthRegisterResult {
  final String userId;
  final String message;

  const AuthRegisterResult({
    required this.userId,
    required this.message,
  
  final UserModel user;

  const AuthLoginResult({
    required this.userId,
    required this.role,
    required this.token,
    required this.user,
  });
}

class AuthRegisterResult {
  final String userId;
  final String message;

  const AuthRegisterResult({
    required this.userId,
    required this.message,
  });
}
