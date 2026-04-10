import 'package:smart_attendance/models/attendance_model.dart';
import 'package:smart_attendance/models/course_model.dart';
import 'package:smart_attendance/services/api_service.dart';

/// Handles all attendance-related API calls to the FastAPI backend.
///
/// Expected FastAPI endpoints:
///   GET  /api/v1/attendance/me                    → List<AttendanceModel>
///   GET  /api/v1/attendance/me/summary            → AttendanceSummary
///   POST /api/v1/attendance/mark                  → AttendanceModel
///   POST /api/v1/attendance/mark-qr               → AttendanceModel
///   GET  /api/v1/courses                          → List<CourseModel>
///   GET  /api/v1/courses/{course_id}/attendance   → List<AttendanceModel>
class AttendanceService {
  final _api = ApiService.instance;

  /// Fetch attendance records for the logged-in student.
  /// Optional filters: [courseId], [startDate], [endDate]
  Future<List<AttendanceModel>> getMyAttendance({
    String? courseId,
    DateTime? startDate,
    DateTime? endDate,
    int page = 1,
    int limit = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'limit': limit,
      };
      if (courseId != null) queryParams['course_id'] = courseId;
      if (startDate != null) {
        queryParams['start_date'] = startDate.toIso8601String().split('T').first;
      }
      if (endDate != null) {
        queryParams['end_date'] = endDate.toIso8601String().split('T').first;
      }

      final response = await _api.get(
        '${ApiConfig.attendancePrefix}/me',
        queryParameters: queryParams,
      );

      final items = response.data as List<dynamic>;
      return items
          .map((e) => AttendanceModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } on Exception {
      throw const ApiException(message: 'Failed to load attendance records.');
    }
  }

  /// Fetch overall attendance summary for the current user.
  Future<AttendanceSummary> getMyAttendanceSummary({
    String? courseId,
  }) async {
    try {
      final response = await _api.get(
        '${ApiConfig.attendancePrefix}/me/summary',
        queryParameters: courseId != null ? {'course_id': courseId} : null,
      );
      return AttendanceSummary.fromJson(
        response.data as Map<String, dynamic>,
      );
    } on Exception {
      throw const ApiException(message: 'Failed to load attendance summary.');
    }
  }

  /// Mark attendance manually (e.g., teacher marking present).
  Future<AttendanceModel> markAttendance({
    required String courseId,
    required String userId,
    required AttendanceStatus status,
    String? notes,
  }) async {
    try {
      final response = await _api.post(
        '${ApiConfig.attendancePrefix}/mark',
        data: {
          'course_id': courseId,
          'user_id': userId,
          'status': status.name,
          'notes': notes,
          'marked_at': DateTime.now().toIso8601String(),
        },
      );
      return AttendanceModel.fromJson(
        response.data as Map<String, dynamic>,
      );
    } on Exception catch (e) {
      if (e is ApiException) rethrow;
      throw const ApiException(message: 'Failed to mark attendance.');
    }
  }

  /// Mark attendance via QR code token scanned from lecturer's screen.
  Future<AttendanceModel> markAttendanceWithQr({
    required String qrToken,
    String? deviceId,
  }) async {
    try {
      final response = await _api.post(
        '${ApiConfig.attendancePrefix}/mark-qr',
        data: {
          'qr_token': qrToken,
          'device_id': deviceId,
          'scanned_at': DateTime.now().toIso8601String(),
        },
      );
      return AttendanceModel.fromJson(
        response.data as Map<String, dynamic>,
      );
    } on Exception catch (e) {
      if (e is ApiException) rethrow;
      throw const ApiException(message: 'QR scan failed. Please try again.');
    }
  }

  /// Fetch all enrolled courses for the logged-in student.
  Future<List<CourseModel>> getMyCourses() async {
    try {
      final response = await _api.get('${ApiConfig.coursesPrefix}/enrolled');
      final items = response.data as List<dynamic>;
      return items
          .map((e) => CourseModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } on Exception {
      throw const ApiException(message: 'Failed to load courses.');
    }
  }

  /// Teacher: Get attendance for a specific course session.
  Future<List<AttendanceModel>> getCourseAttendance({
    required String courseId,
    DateTime? date,
  }) async {
    try {
      final queryParams = <String, dynamic>{};
      if (date != null) {
        queryParams['date'] = date.toIso8601String().split('T').first;
      }

      final response = await _api.get(
        '${ApiConfig.coursesPrefix}/$courseId/attendance',
        queryParameters: queryParams,
      );

      final items = response.data as List<dynamic>;
      return items
          .map((e) => AttendanceModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } on Exception {
      throw const ApiException(message: 'Failed to load course attendance.');
    }
  }

  /// Generate a QR token for a live session (teacher only).
  Future<Map<String, dynamic>> generateQrToken({
    required String courseId,
    int expiryMinutes = 10,
  }) async {
    try {
      final response = await _api.post(
        '${ApiConfig.attendancePrefix}/generate-qr',
        data: {
          'course_id': courseId,
          'expiry_minutes': expiryMinutes,
        },
      );
      return response.data as Map<String, dynamic>;
    } on Exception catch (e) {
      if (e is ApiException) rethrow;
      throw const ApiException(message: 'Failed to generate QR code.');
    }
  }
}
