import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:smart_attendance/models/course_model.dart';
import 'package:smart_attendance/models/user_model.dart';
import 'package:smart_attendance/services/api_service.dart';

/// Handles all authentication operations with the FastAPI backend.
///
/// FastAPI endpoints expected:
///   POST /api/v1/auth/login       → { access_token, token_type, expires_in }
///   POST /api/v1/auth/logout
///   POST /api/v1/auth/refresh     → { access_token }
///   GET  /api/v1/auth/me          → UserModel JSON
///   POST /api/v1/auth/register
class AuthService {
  final _api = ApiService.instance;
  final _storage = const FlutterSecureStorage();

  static const _tokenKey = 'access_token';
  static const _refreshKey = 'refresh_token';
  static const _userKey = 'cached_user';

  /// Login with email + password (OAuth2 form submission for FastAPI)
  Future<AuthResult> login({
    required String email,
    required String password,
  }) async {
    try {
      // FastAPI uses form data for OAuth2 token endpoint
      final response = await _api.post(
        '${ApiConfig.authPrefix}/login',
        data: {
          'username': email, // FastAPI OAuth2 uses 'username'
          'password': password,
        },
        options: _formDataOptions(),
      );

      final tokenData = AuthTokenModel.fromJson(
        response.data as Map<String, dynamic>,
      );

      // Persist tokens securely
      await _storage.write(key: _tokenKey, value: tokenData.accessToken);
      if (tokenData.refreshToken != null) {
        await _storage.write(key: _refreshKey, value: tokenData.refreshToken);
      }

      // Fetch user profile
      final user = await getMe();
      return AuthResult(token: tokenData, user: user);
    } on Exception catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException.fromDioException(e as dynamic);
    }
  }

  /// Fetch the current authenticated user's profile
  Future<UserModel> getMe() async {
    try {
      final response = await _api.get('${ApiConfig.authPrefix}/me');
      return UserModel.fromJson(response.data as Map<String, dynamic>);
    } on Exception catch (e) {
      throw ApiException(
        message: 'Failed to load profile.',
        data: e.toString(),
      );
    }
  }

  /// Register a new student account
  Future<UserModel> register({
    required String name,
    required String email,
    required String password,
    required String studentId,
    String? department,
    String? semester,
  }) async {
    try {
      final response = await _api.post(
        '${ApiConfig.authPrefix}/register',
        data: {
          'name': name,
          'email': email,
          'password': password,
          'student_id': studentId,
          'department': department,
          'semester': semester,
          'role': 'student',
        },
      );
      return UserModel.fromJson(response.data as Map<String, dynamic>);
    } on Exception catch (e) {
      if (e is ApiException) rethrow;
      throw const ApiException(message: 'Registration failed. Try again.');
    }
  }

  /// Clear all stored tokens (logout)
  Future<void> logout() async {
    try {
      // Notify backend (best-effort)
      await _api.post('${ApiConfig.authPrefix}/logout');
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

  // Form-data options required by FastAPI OAuth2 token endpoint
  static _formDataOptions() {
    return _DioOptionsHelper.formData();
  }
}

class _DioOptionsHelper {
  static formData() {
    return import('package:dio/dio.dart').Options(
      contentType: 'application/x-www-form-urlencoded',
    );
  }
}

// ignore: non_constant_identifier_names
dynamic import(String _) => throw UnimplementedError();

// ---- Use this actual import pattern in your service ----
// import 'package:dio/dio.dart';
// options: Options(contentType: 'application/x-www-form-urlencoded'),

class AuthResult {
  final AuthTokenModel token;
  final UserModel user;

  const AuthResult({required this.token, required this.user});
}
