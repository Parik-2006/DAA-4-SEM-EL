import 'package:equatable/equatable.dart';

enum AttendanceStatus { present, absent, late, excused }

class AttendanceModel extends Equatable {
  final String id;
  final String userId;
  final String courseId;
  final String courseName;
  final AttendanceStatus status;
  final DateTime markedAt;
  final String? location;
  final String? markedBy;
  final String? notes;

  const AttendanceModel({
    required this.id,
    required this.userId,
    required this.courseId,
    required this.courseName,
    required this.status,
    required this.markedAt,
    this.location,
    this.markedBy,
    this.notes,
  });

  factory AttendanceModel.fromJson(Map<String, dynamic> json) {
    return AttendanceModel(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      courseId: json['course_id'] as String,
      courseName: json['course_name'] as String,
      status: AttendanceStatus.values.firstWhere(
        (s) => s.name == (json['status'] as String? ?? 'present'),
        orElse: () => AttendanceStatus.present,
      ),
      markedAt: DateTime.parse(json['marked_at'] as String),
      location: json['location'] as String?,
      markedBy: json['marked_by'] as String?,
      notes: json['notes'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'user_id': userId,
        'course_id': courseId,
        'course_name': courseName,
        'status': status.name,
        'marked_at': markedAt.toIso8601String(),
        'location': location,
        'marked_by': markedBy,
        'notes': notes,
      };

  @override
  List<Object?> get props => [
        id,
        userId,
        courseId,
        status,
        markedAt,
      ];
}

class AttendanceSummary extends Equatable {
  final int totalClasses;
  final int presentCount;
  final int absentCount;
  final int lateCount;
  final int excusedCount;

  const AttendanceSummary({
    required this.totalClasses,
    required this.presentCount,
    required this.absentCount,
    required this.lateCount,
    required this.excusedCount,
  });

  double get attendancePercentage {
    if (totalClasses == 0) return 0;
    return ((presentCount + lateCount) / totalClasses) * 100;
  }

  factory AttendanceSummary.fromJson(Map<String, dynamic> json) {
    return AttendanceSummary(
      totalClasses: json['total_classes'] as int? ?? 0,
      presentCount: json['present_count'] as int? ?? 0,
      absentCount: json['absent_count'] as int? ?? 0,
      lateCount: json['late_count'] as int? ?? 0,
      excusedCount: json['excused_count'] as int? ?? 0,
    );
  }

  @override
  List<Object?> get props => [
        totalClasses,
        presentCount,
        absentCount,
        lateCount,
        excusedCount,
      ];
}
