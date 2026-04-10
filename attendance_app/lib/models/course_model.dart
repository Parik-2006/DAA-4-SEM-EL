import 'package:equatable/equatable.dart';

class CourseModel extends Equatable {
  final String id;
  final String name;
  final String code;
  final String teacherName;
  final String? teacherId;
  final String department;
  final int credits;
  final List<ScheduleSlot> schedule;
  final int totalStudents;
  final bool isActive;

  const CourseModel({
    required this.id,
    required this.name,
    required this.code,
    required this.teacherName,
    this.teacherId,
    required this.department,
    required this.credits,
    required this.schedule,
    required this.totalStudents,
    this.isActive = true,
  });

  factory CourseModel.fromJson(Map<String, dynamic> json) {
    return CourseModel(
      id: json['id'] as String,
      name: json['name'] as String,
      code: json['code'] as String,
      teacherName: json['teacher_name'] as String,
      teacherId: json['teacher_id'] as String?,
      department: json['department'] as String,
      credits: json['credits'] as int? ?? 3,
      schedule: (json['schedule'] as List<dynamic>? ?? [])
          .map((s) => ScheduleSlot.fromJson(s as Map<String, dynamic>))
          .toList(),
      totalStudents: json['total_students'] as int? ?? 0,
      isActive: json['is_active'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'code': code,
        'teacher_name': teacherName,
        'teacher_id': teacherId,
        'department': department,
        'credits': credits,
        'schedule': schedule.map((s) => s.toJson()).toList(),
        'total_students': totalStudents,
        'is_active': isActive,
      };

  @override
  List<Object?> get props => [id, name, code, teacherName, department];
}

class ScheduleSlot extends Equatable {
  final String dayOfWeek; // 'Monday', 'Tuesday', etc.
  final String startTime; // '09:00'
  final String endTime;   // '10:30'
  final String? room;

  const ScheduleSlot({
    required this.dayOfWeek,
    required this.startTime,
    required this.endTime,
    this.room,
  });

  factory ScheduleSlot.fromJson(Map<String, dynamic> json) {
    return ScheduleSlot(
      dayOfWeek: json['day_of_week'] as String,
      startTime: json['start_time'] as String,
      endTime: json['end_time'] as String,
      room: json['room'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'day_of_week': dayOfWeek,
        'start_time': startTime,
        'end_time': endTime,
        'room': room,
      };

  @override
  List<Object?> get props => [dayOfWeek, startTime, endTime, room];
}

// Auth token model
class AuthTokenModel extends Equatable {
  final String accessToken;
  final String tokenType;
  final int expiresIn;
  final String? refreshToken;

  const AuthTokenModel({
    required this.accessToken,
    required this.tokenType,
    required this.expiresIn,
    this.refreshToken,
  });

  factory AuthTokenModel.fromJson(Map<String, dynamic> json) {
    return AuthTokenModel(
      accessToken: json['access_token'] as String,
      tokenType: json['token_type'] as String? ?? 'bearer',
      expiresIn: json['expires_in'] as int? ?? 3600,
      refreshToken: json['refresh_token'] as String?,
    );
  }

  @override
  List<Object?> get props => [accessToken, tokenType, expiresIn];
}
