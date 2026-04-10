import 'package:logger/logger.dart';
import 'package:smart_attendance/models/face_model.dart';
import 'package:smart_attendance/models/user_model.dart';
import 'package:smart_attendance/services/api_service.dart';

/// Exception for API errors
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic originalError;

  ApiException({
    required this.message,
    this.statusCode,
    this.originalError,
  });

  factory ApiException.fromDioException(dynamic error) {
    return ApiException(
      message: error.toString(),
      originalError: error,
    );
  }

  @override
  String toString() => message;
}

/// Handles student registration with face data capture
class RegistrationService {
  final _api = ApiService.instance;
  final _logger = Logger();

  /// Register a new student with basic info and face data
  /// 
  /// Expected backend endpoint: POST /api/v1/students/register-student
  Future<UserModel> registerStudent({
    required String name,
    required String email,
    required String studentId,
    required String password,
    required String department,
    String? semester,
    required String faceImageBase64,
  }) async {
    try {
      _logger.d('Registering student: $email with student ID: $studentId');
      
      final response = await _api.dio.post(
        '${ApiConfig.authPrefix}/register',
        data: {
          'name': name,
          'email': email,
          'student_id': studentId,
          'password': password,
          'department': department,
          'semester': semester,
          'role': 'student',
          'face_image_base64': faceImageBase64,
        },
      );

      final user = UserModel.fromJson(
        response.data as Map<String, dynamic>,
      );
      
      _logger.i('Student registered successfully: ${user.name}');
      return user;
    } catch (e) {
      _logger.e('Registration failed: $e');
      throw ApiException(
        message: 'Failed to register student: ${e.toString()}',
        originalError: e,
      );
    }
  }

  /// Upload additional face data for an already registered student
  Future<FaceData> uploadFaceData({
    required String studentId,
    required String faceImageBase64,
  }) async {
    try {
      _logger.d('Uploading face data for student: $studentId');
      
      final response = await _api.dio.post(
        '/api/v1/students/$studentId/face-data',
        data: {
          'face_image_base64': faceImageBase64,
        },
      );

      final faceData = FaceData.fromJson(
        response.data as Map<String, dynamic>,
      );
      
      _logger.i('Face data uploaded successfully');
      return faceData;
    } catch (e) {
      _logger.e('Face data upload failed: $e');
      throw ApiException(
        message: 'Failed to upload face data: ${e.toString()}',
        originalError: e,
      );
    }
  }

  /// Fetch detected faces from backend for live camera feed
  /// 
  /// Expected backend endpoint: GET /api/v1/face-recognition/detect
  Future<FaceDetectionResponse> detectFaces({
    required String frameBase64,
  }) async {
    try {
      final response = await _api.dio.post(
        '/api/v1/face-recognition/detect',
        data: {
          'frame_base64': frameBase64,
        },
      );

      final detectionResponse = FaceDetectionResponse.fromJson(
        response.data as Map<String, dynamic>,
      );
      
      return detectionResponse;
    } catch (e) {
      _logger.e('Face detection failed: $e');
      throw ApiException(
        message: 'Failed to detect faces: ${e.toString()}',
        originalError: e,
      );
    }
  }

  /// Fetch all registered student names for face database
  Future<List<Map<String, dynamic>>> getRegisteredStudents() async {
    try {
      _logger.d('Fetching registered students...');
      
      final response = await _api.dio.get(
        '/api/v1/students/list',
        queryParameters: {
          'fields': 'id,name,student_id,avatar_url',
        },
      );

      final students = (response.data as List<dynamic>?)
              ?.cast<Map<String, dynamic>>() ??
          [];
      
      _logger.i('Fetched ${students.length} students');
      return students;
    } catch (e) {
      _logger.e('Failed to fetch students: $e');
      throw ApiException(
        message: 'Failed to fetch students: ${e.toString()}',
        originalError: e,
      );
    }
  }
}
