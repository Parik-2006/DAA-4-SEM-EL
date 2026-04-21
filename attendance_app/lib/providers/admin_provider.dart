import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smart_attendance/models/attendance_model.dart';
import 'package:smart_attendance/models/user_model.dart';
import 'package:smart_attendance/services/api_service.dart';

// ── Admin Service ──────────────────────────────────────────────────────────────

class AdminService {
  final _api = ApiService.instance;

  /// Fetch all students (admin only)
  Future<List<UserModel>> getAllStudents() async {
    try {
      final response = await _api.get('/api/v1/admin/students');
      final items = response.data as List<dynamic>;
      return items
          .map((e) => UserModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } on Exception {
      throw const ApiException(message: 'Failed to load student list.');
    }
  }

  /// Fetch today's attendance stats (admin only)
  Future<AdminAttendanceStats> getTodayStats() async {
    try {
      final response = await _api.get('/api/v1/admin/attendance/today');
      return AdminAttendanceStats.fromJson(
        response.data as Map<String, dynamic>,
      );
    } on Exception {
      // Return empty stats on failure so UI degrades gracefully
      return AdminAttendanceStats.empty();
    }
  }

  /// Fetch attendance records for a specific date (admin only)
  Future<List<AdminAttendanceRecord>> getAttendanceForDate({
    required String date, // YYYY-MM-DD
    String? courseId,
    int page = 1,
    int limit = 50,
  }) async {
    try {
      final response = await _api.get(
        '/api/v1/admin/attendance',
        queryParameters: {
          'date': date,
          if (courseId != null) 'course_id': courseId,
          'page': page,
          'limit': limit,
        },
      );
      final items = response.data as List<dynamic>;
      return items
          .map((e) =>
              AdminAttendanceRecord.fromJson(e as Map<String, dynamic>))
          .toList();
    } on Exception {
      throw const ApiException(message: 'Failed to load attendance records.');
    }
  }

  /// Register a new student face (admin only)
  Future<void> registerStudentFace({
    required String studentId,
    required String faceImageBase64,
  }) async {
    try {
      await _api.post(
        '/api/v1/admin/students/$studentId/face',
        data: {'face_image_base64': faceImageBase64},
      );
    } on Exception {
      throw const ApiException(message: 'Failed to register student face.');
    }
  }
}

// ── Data Models ────────────────────────────────────────────────────────────────

class AdminAttendanceStats {
  final int totalStudents;
  final int presentToday;
  final int absentToday;
  final int lateToday;
  final double attendanceRate;

  const AdminAttendanceStats({
    required this.totalStudents,
    required this.presentToday,
    required this.absentToday,
    required this.lateToday,
    required this.attendanceRate,
  });

  factory AdminAttendanceStats.empty() => const AdminAttendanceStats(
        totalStudents: 0,
        presentToday: 0,
        absentToday: 0,
        lateToday: 0,
        attendanceRate: 0,
      );

  factory AdminAttendanceStats.fromJson(Map<String, dynamic> json) {
    final total = json['total_students'] as int? ?? 0;
    final present = json['present_today'] as int? ?? 0;
    final absent = json['absent_today'] as int? ?? 0;
    final late = json['late_today'] as int? ?? 0;
    final rate = total > 0 ? ((present + late) / total * 100) : 0.0;

    return AdminAttendanceStats(
      totalStudents: total,
      presentToday: present,
      absentToday: absent,
      lateToday: late,
      attendanceRate: (json['attendance_rate'] as num?)?.toDouble() ?? rate,
    );
  }
}

class AdminAttendanceRecord {
  final String id;
  final String studentId;
  final String studentName;
  final String? studentAvatarUrl;
  final String status; // present | absent | late | excused
  final DateTime markedAt;
  final double? confidence;

  const AdminAttendanceRecord({
    required this.id,
    required this.studentId,
    required this.studentName,
    this.studentAvatarUrl,
    required this.status,
    required this.markedAt,
    this.confidence,
  });

  factory AdminAttendanceRecord.fromJson(Map<String, dynamic> json) {
    return AdminAttendanceRecord(
      id: json['id'] as String? ?? '',
      studentId: json['student_id'] as String? ?? '',
      studentName: json['student_name'] as String? ?? 'Unknown',
      studentAvatarUrl: json['avatar_url'] as String?,
      status: json['status'] as String? ?? 'absent',
      markedAt: DateTime.parse(
        json['marked_at'] as String? ?? DateTime.now().toIso8601String(),
      ),
      confidence: (json['confidence'] as num?)?.toDouble(),
    );
  }
}

// ── Providers ──────────────────────────────────────────────────────────────────

final adminServiceProvider = Provider<AdminService>((ref) => AdminService());

/// All students list (refreshable)
final adminStudentsProvider = FutureProvider<List<UserModel>>((ref) {
  return ref.watch(adminServiceProvider).getAllStudents();
});

/// Today's attendance stats
final adminTodayStatsProvider =
    FutureProvider<AdminAttendanceStats>((ref) async {
  return ref.watch(adminServiceProvider).getTodayStats();
});

/// Attendance records for a given date
final adminAttendanceByDateProvider =
    FutureProvider.family<List<AdminAttendanceRecord>, String>((ref, date) {
  return ref
      .watch(adminServiceProvider)
      .getAttendanceForDate(date: date);
});
