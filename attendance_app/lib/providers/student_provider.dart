import 'package:riverpod/riverpod.dart';
import '../services/api_service.dart';
import '../models/attendance_model.dart';

class StudentService {
  final ApiService _apiService;

  StudentService(this._apiService);

  Future<AttendanceSummary> getTodayAttendance(String studentId) async {
    try {
      final response = await _apiService.dio.get(
        '/api/v1/student/attendance/today',
        queryParameters: {'student_id': studentId},
      );
      return AttendanceSummary.fromJson(response.data);
    } catch (e) {
      return AttendanceSummary.empty();
    }
  }

  Future<List<AttendanceRecord>> getAttendanceHistory(String studentId) async {
    try {
      final response = await _apiService.dio.get(
        '/api/v1/student/attendance/history',
        queryParameters: {'student_id': studentId, 'limit': '30'},
      );
      final records = response.data['records'] as List?;
      if (records == null) return [];
      return records
          .map((e) => AttendanceRecord.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      return [];
    }
  }
}

final studentServiceProvider = Provider((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return StudentService(apiService);
});

final studentTodayAttendanceProvider =
    FutureProvider.family<AttendanceSummary, String>((ref, studentId) async {
  final service = ref.watch(studentServiceProvider);
  return service.getTodayAttendance(studentId);
});

final studentAttendanceHistoryProvider =
    FutureProvider.family<List<AttendanceRecord>, String>((ref, studentId) async {
  final service = ref.watch(studentServiceProvider);
  return service.getAttendanceHistory(studentId);
});

class AttendanceSummary {
  final String status;
  final String? markedAt;
  final double? confidence;

  AttendanceSummary({
    required this.status,
    this.markedAt,
    this.confidence,
  });

  factory AttendanceSummary.empty() => AttendanceSummary(status: 'not_marked');

  factory AttendanceSummary.fromJson(Map<String, dynamic> json) {
    return AttendanceSummary(
      status: json['status'] ?? 'unknown',
      markedAt: json['markedAt'],
      confidence: (json['confidence'] as num?)?.toDouble(),
    );
  }
}

class AttendanceRecord {
  final String id;
  final String date;
  final String status;
  final String markedAt;
  final double? confidence;

  AttendanceRecord({
    required this.id,
    required this.date,
    required this.status,
    required this.markedAt,
    this.confidence,
  });

  factory AttendanceRecord.fromJson(Map<String, dynamic> json) {
    return AttendanceRecord(
      id: json['id'] ?? '',
      date: json['date'] ?? '',
      status: json['status'] ?? '',
      markedAt: json['markedAt'] ?? '',
      confidence: (json['confidence'] as num?)?.toDouble(),
    );
  }
}
