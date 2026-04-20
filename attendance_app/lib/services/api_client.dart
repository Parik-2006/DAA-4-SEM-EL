import 'dart:io';
import 'package:dio/dio.dart';

/// API Client for backend communication
class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  late Dio _dio;

  String baseUrl = 'http://localhost:8000'; // Change to your backend URL

  factory ApiClient() {
    return _instance;
  }

  ApiClient._internal() {
    _initializeDio();
  }

  void _initializeDio() {
    _dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 10),
        sendTimeout: const Duration(seconds: 10),
        contentType: 'application/json',
      ),
    );

    // Add interceptors
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          debugPrint('[API] ${options.method} ${options.path}');
          return handler.next(options);
        },
        onResponse: (response, handler) {
          debugPrint('[API] Response: ${response.statusCode}');
          return handler.next(response);
        },
        onError: (error, handler) {
          debugPrint('[API] Error: ${error.message}');
          return handler.next(error);
        },
      ),
    );
  }

  /// Add auth token to requests
  void setAuthToken(String token) {
    _dio.options.headers['Authorization'] = 'Bearer $token';
  }

  /// Health check
  Future<dynamic> healthCheck() async {
    try {
      final response = await _dio.get('/health');
      return response.data;
    } catch (e) {
      rethrow;
    }
  }

  /// Get all students
  Future<List<dynamic>> getStudents() async {
    try {
      final response = await _dio.get('/api/students');
      return response.data as List<dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  /// Record attendance
  Future<dynamic> recordAttendance({
    required String studentId,
    required String courseId,
    required bool isPresent,
    String? photoUrl,
  }) async {
    try {
      final response = await _dio.post(
        '/api/attendance/record',
        data: {
          'student_id': studentId,
          'course_id': courseId,
          'is_present': isPresent,
          'photo_url': photoUrl,
          'timestamp': DateTime.now().toIso8601String(),
        },
      );
      return response.data;
    } catch (e) {
      rethrow;
    }
  }

  /// Upload file
  Future<String> uploadFile({
    required File file,
    required String uploadPath,
  }) async {
    try {
      final formData = FormData.fromMap({
        'file': await MultipartFile.fromFile(
          file.path,
          filename: file.path.split('/').last,
        ),
      });

      final response = await _dio.post(
        '/api/upload',
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
        ),
      );

      return response.data['url'] ?? '';
    } catch (e) {
      rethrow;
    }
  }

  /// Get student statistics
  Future<dynamic> getStatistics(String courseId) async {
    try {
      final response = await _dio.get('/api/statistics/$courseId');
      return response.data;
    } catch (e) {
      rethrow;
    }
  }
}
