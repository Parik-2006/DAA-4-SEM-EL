import 'package:equatable/equatable.dart';

/// Represents real-time attendance record with student info
class RealtimeAttendanceRecord extends Equatable {
  final String id;
  final String studentName;
  final String studentId;
  final String courseName;
  final DateTime markedAt;
  final String status; // present, late, absent, excused
  final String? avatarUrl;
  final double? confidence; // For face detection confidence

  const RealtimeAttendanceRecord({
    required this.id,
    required this.studentName,
    required this.studentId,
    required this.courseName,
    required this.markedAt,
    required this.status,
    this.avatarUrl,
    this.confidence,
  });

  factory RealtimeAttendanceRecord.fromJson(Map<String, dynamic> json) {
    return RealtimeAttendanceRecord(
      id: json['id'] as String,
      studentName: json['student_name'] as String? ?? 'Unknown',
      studentId: json['student_id'] as String? ?? '',
      courseName: json['course_name'] as String? ?? 'Course',
      markedAt: DateTime.parse(
        json['marked_at'] as String? ?? DateTime.now().toIso8601String(),
      ),
      status: json['status'] as String? ?? 'present',
      avatarUrl: json['avatar_url'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'student_name': studentName,
        'student_id': studentId,
        'course_name': courseName,
        'marked_at': markedAt.toIso8601String(),
        'status': status,
        'avatar_url': avatarUrl,
        'confidence': confidence,
      };

  @override
  List<Object?> get props => [
        id,
        studentName,
        studentId,
        courseName,
        markedAt,
        status,
        avatarUrl,
        confidence,
      ];
}

/// Attendance statistics for dashboard
class AttendanceStats extends Equatable {
  final int totalPresent;
  final int totalLate;
  final int totalAbsent;
  final int totalExcused;
  final DateTime lastUpdated;

  const AttendanceStats({
    required this.totalPresent,
    required this.totalLate,
    required this.totalAbsent,
    required this.totalExcused,
    required this.lastUpdated,
  });

  int get total => totalPresent + totalLate + totalAbsent + totalExcused;

  double get presentPercent => total == 0 ? 0 : (totalPresent / total) * 100;
  double get latePercent => total == 0 ? 0 : (totalLate / total) * 100;
  double get absentPercent => total == 0 ? 0 : (totalAbsent / total) * 100;

  factory AttendanceStats.fromJson(Map<String, dynamic> json) {
    return AttendanceStats(
      totalPresent: json['total_present'] as int? ?? 0,
      totalLate: json['total_late'] as int? ?? 0,
      totalAbsent: json['total_absent'] as int? ?? 0,
      totalExcused: json['total_excused'] as int? ?? 0,
      lastUpdated: DateTime.parse(
        json['last_updated'] as String? ?? DateTime.now().toIso8601String(),
      ),
    );
  }

  Map<String, dynamic> toJson() => {
        'total_present': totalPresent,
        'total_late': totalLate,
        'total_absent': totalAbsent,
        'total_excused': totalExcused,
        'last_updated': lastUpdated.toIso8601String(),
      };

  @override
  List<Object?> get props =>
      [totalPresent, totalLate, totalAbsent, totalExcused, lastUpdated];
}

/// Dashboard state for real-time updates
class DashboardState extends Equatable {
  final List<RealtimeAttendanceRecord> records;
  final AttendanceStats stats;
  final bool isLoading;
  final String? error;
  final DateTime? lastSyncTime;
  final bool isAutoRefreshing;

  const DashboardState({
    this.records = const [],
    required this.stats,
    this.isLoading = false,
    this.error,
    this.lastSyncTime,
    this.isAutoRefreshing = false,
  });

  DashboardState copyWith({
    List<RealtimeAttendanceRecord>? records,
    AttendanceStats? stats,
    bool? isLoading,
    String? error,
    DateTime? lastSyncTime,
    bool? isAutoRefreshing,
  }) {
    return DashboardState(
      records: records ?? this.records,
      stats: stats ?? this.stats,
      isLoading: isLoading ?? this.isLoading,
      error: error ?? this.error,
      lastSyncTime: lastSyncTime ?? this.lastSyncTime,
      isAutoRefreshing: isAutoRefreshing ?? this.isAutoRefreshing,
    );
  }

  @override
  List<Object?> get props =>
      [records, stats, isLoading, error, lastSyncTime, isAutoRefreshing];
}
