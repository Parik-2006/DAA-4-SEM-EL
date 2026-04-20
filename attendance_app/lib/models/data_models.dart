class StudentModel {
  final String id;
  final String name;
  final String email;
  final String? photoUrl;
  final String studentId;
  final String courseId;
  final DateTime createdAt;

  StudentModel({
    required this.id,
    required this.name,
    required this.email,
    this.photoUrl,
    required this.studentId,
    required this.courseId,
    required this.createdAt,
  });

  factory StudentModel.fromJson(Map<String, dynamic> json) {
    return StudentModel(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      email: json['email'] as String? ?? '',
      photoUrl: json['photo_url'] as String?,
      studentId: json['student_id'] as String? ?? '',
      courseId: json['course_id'] as String? ?? '',
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String)
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'email': email,
      'photo_url': photoUrl,
      'student_id': studentId,
      'course_id': courseId,
      'created_at': createdAt.toIso8601String(),
    };
  }

  StudentModel copyWith({
    String? id,
    String? name,
    String? email,
    String? photoUrl,
    String? studentId,
    String? courseId,
    DateTime? createdAt,
  }) {
    return StudentModel(
      id: id ?? this.id,
      name: name ?? this.name,
      email: email ?? this.email,
      photoUrl: photoUrl ?? this.photoUrl,
      studentId: studentId ?? this.studentId,
      courseId: courseId ?? this.courseId,
      createdAt: createdAt ?? this.createdAt,
    );
  }
}

class AttendanceModel {
  final String id;
  final String studentId;
  final String courseId;
  final bool isPresent;
  final DateTime timestamp;
  final String? photoUrl;

  AttendanceModel({
    required this.id,
    required this.studentId,
    required this.courseId,
    required this.isPresent,
    required this.timestamp,
    this.photoUrl,
  });

  factory AttendanceModel.fromJson(Map<String, dynamic> json) {
    return AttendanceModel(
      id: json['id'] as String? ?? '',
      studentId: json['student_id'] as String? ?? '',
      courseId: json['course_id'] as String? ?? '',
      isPresent: json['is_present'] as bool? ?? false,
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'] as String)
          : DateTime.now(),
      photoUrl: json['photo_url'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'student_id': studentId,
      'course_id': courseId,
      'is_present': isPresent,
      'timestamp': timestamp.toIso8601String(),
      'photo_url': photoUrl,
    };
  }
}

class StatisticsModel {
  final int totalStudents;
  final int presentCount;
  final int absentCount;
  final double attendancePercentage;

  StatisticsModel({
    required this.totalStudents,
    required this.presentCount,
    required this.absentCount,
    required this.attendancePercentage,
  });

  factory StatisticsModel.fromJson(Map<String, dynamic> json) {
    return StatisticsModel(
      totalStudents: json['total_students'] as int? ?? 0,
      presentCount: json['present_count'] as int? ?? 0,
      absentCount: json['absent_count'] as int? ?? 0,
      attendancePercentage: (json['attendance_percentage'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'total_students': totalStudents,
      'present_count': presentCount,
      'absent_count': absentCount,
      'attendance_percentage': attendancePercentage,
    };
  }
}
