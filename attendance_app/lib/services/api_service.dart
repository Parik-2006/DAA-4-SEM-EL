import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:logger/logger.dart';

/// Base API configuration pointing to FastAPI backend.
/// Change [baseUrl] to your FastAPI server address.
class ApiConfig {
  // Development: local emulator or device IP
  static const String devBaseUrl = 'http://10.0.2.2:8000'; // Android emulator
  // static const String devBaseUrl = 'http://192.168.1.100:8000'; // Physical device

  // Production
  static const String prodBaseUrl = 'https://api.yourattendance.com';

  static const String baseUrl = devBaseUrl; // Switch to prod for release

  // FastAPI endpoints
  static const String authPrefix = '/api/v1/auth';
  static const String usersPrefix = '/api/v1/users';
  static const String coursesPrefix = '/api/v1/courses';
  static const String attendancePrefix = '/api/v1/attendance';

  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 30);
}

/// Singleton Dio client with interceptors for auth, logging, and error handling.
class ApiService {
  static ApiService? _instance;
  late final Dio _dio;
  final _storage = const FlutterSecureStorage();
  final _logger = Logger();

  ApiService._() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        connectTimeout: ApiConfig.connectTimeout,
        receiveTimeout: ApiConfig.receiveTimeout,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    _addInterceptors();
  }

  static ApiService get instance {
    _instance ??= ApiService._();
    return _instance!;
  }

  Dio get dio => _dio;

  void _addInterceptors() {
    // Auth interceptor - injects JWT token from secure storage
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: 'access_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          _logger.d(
            '→ ${options.method} ${options.path}\n'
            'Headers: ${options.headers}\n'
            'Body: ${options.data}',
          );
          return handler.next(options);
        },
        onResponse: (response, handler) {
          _logger.d(
            '← ${response.statusCode} ${response.requestOptions.path}\n'
            'Data: ${response.data}',
          );
          return handler.next(response);
        },
        onError: (error, handler) async {
          _logger.e(
            '✗ ${error.response?.statusCode} ${error.requestOptions.path}\n'
            'Error: ${error.message}',
          );

          // Handle 401: token expired → try refresh
          if (error.response?.statusCode == 401) {
            final refreshed = await _refreshToken();
            if (refreshed) {
              // Retry the original request with new token
              final token = await _storage.read(key: 'access_token');
              error.requestOptions.headers['Authorization'] = 'Bearer $token';
              final clonedRequest = await _dio.fetch(error.requestOptions);
              return handler.resolve(clonedRequest);
            }
          }

          return handler.next(error);
        },
      ),
    );
  }

  Future<bool> _refreshToken() async {
    try {
      final refreshToken = await _storage.read(key: 'refresh_token');
      if (refreshToken == null) return false;

      final response = await _dio.post(
        '${ApiConfig.authPrefix}/refresh',
        data: {'refresh_token': refreshToken},
        options: Options(headers: {'Authorization': null}),
      );

      final newToken = response.data['access_token'] as String?;
      if (newToken != null) {
        await _storage.write(key: 'access_token', value: newToken);
        return true;
      }
      return false;
    } catch (_) {
      // Clear tokens on refresh failure — forces re-login
      await _storage.deleteAll();
      return false;
    }
  }

  /// Generic GET request
  Future<Response<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    return _dio.get<T>(
      path,
      queryParameters: queryParameters,
      options: options,
    );
  }

  /// Generic POST request
  Future<Response<T>> post<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    return _dio.post<T>(
      path,
      data: data,
      queryParameters: queryParameters,
      options: options,
    );
  }

  /// Generic PUT request
  Future<Response<T>> put<T>(
    String path, {
    dynamic data,
    Options? options,
  }) async {
    return _dio.put<T>(path, data: data, options: options);
  }

  /// Generic PATCH request
  Future<Response<T>> patch<T>(
    String path, {
    dynamic data,
    Options? options,
  }) async {
    return _dio.patch<T>(path, data: data, options: options);
  }

  /// Generic DELETE request
  Future<Response<T>> delete<T>(String path, {Options? options}) async {
    return _dio.delete<T>(path, options: options);
  }
}

/// Custom exception that wraps Dio errors into user-friendly messages.
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic data;

  const ApiException({
    required this.message,
    this.statusCode,
    this.data,
  });

  factory ApiException.fromDioException(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const ApiException(
          message: 'Connection timed out. Please check your internet.',
          statusCode: 408,
        );
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        final data = e.response?.data;
        final detail = (data is Map) ? data['detail'] ?? data['message'] : null;
        return ApiException(
          message: detail?.toString() ?? _messageForStatus(statusCode),
          statusCode: statusCode,
          data: data,
        );
      case DioExceptionType.connectionError:
        return const ApiException(
          message: 'Cannot reach the server. Check your connection.',
          statusCode: 503,
        );
      default:
        return ApiException(
          message: e.message ?? 'An unexpected error occurred.',
        );
    }
  }

  static String _messageForStatus(int? status) {
    return switch (status) {
      400 => 'Invalid request. Please check your input.',
      401 => 'Session expired. Please log in again.',
      403 => 'You don\'t have permission to do that.',
      404 => 'The requested resource was not found.',
      409 => 'A conflict occurred. Please try again.',
      422 => 'Validation failed. Please check your input.',
      429 => 'Too many requests. Please slow down.',
      500 => 'Server error. Please try again later.',
      503 => 'Service unavailable. Please try again later.',
      _ => 'Something went wrong (error $status).',
    };
  }

  @override
  String toString() => 'ApiException($statusCode): $message';
}
