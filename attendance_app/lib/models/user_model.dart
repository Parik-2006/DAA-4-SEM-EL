import 'package:equatable/equatable.dart';

enum UserRole { student, teacher, admin }

class UserModel extends Equatable {
  final String id;
  final String name;
  final String email;
  final String? studentId;
  final String? department;
  final String? semester;
  final String? avatarUrl;
  final UserRole role;
  final bool isActive;
  final DateTime createdAt;

  const UserModel({
    required this.id,
    required this.name,
    required this.email,
    this.studentId,
    this.department,
    this.semester,
    this.avatarUrl,
    required this.role,
    this.isActive = true,
    required this.createdAt,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String,
      name: json['name'] as String,
      email: json['email'] as String,
      studentId: json['student_id'] as String?,
      department: json['department'] as String?,
      semester: json['semester'] as String?,
      avatarUrl: json['avatar_url'] as String?,
      role: UserRole.values.firstWhere(
        (r) => r.name == (json['role'] as String? ?? 'student'),
        orElse: () => UserRole.student,
      ),
      isActive: json['is_active'] as bool? ?? true,
      createdAt: DateTime.parse(
        json['created_at'] as String? ?? DateTime.now().toIso8601String(),
      ),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'email': email,
        'student_id': studentId,
        'department': department,
        'semester': semester,
        'avatar_url': avatarUrl,
        'role': role.name,
        'is_active': isActive,
        'created_at': createdAt.toIso8601String(),
      };

  UserModel copyWith({
    String? id,
    String? name,
    String? email,
    String? studentId,
    String? department,
    String? semester,
    String? avatarUrl,
    UserRole? role,
    bool? isActive,
    DateTime? createdAt,
  }) {
    return UserModel(
      id: id ?? this.id,
      name: name ?? this.name,
      email: email ?? this.email,
      studentId: studentId ?? this.studentId,
      department: department ?? this.department,
      semester: semester ?? this.semester,
      avatarUrl: avatarUrl ?? this.avatarUrl,
      role: role ?? this.role,
      isActive: isActive ?? this.isActive,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  String get initials {
    final parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return '${parts.first[0]}${parts.last[0]}'.toUpperCase();
    }
    return name.substring(0, name.length >= 2 ? 2 : 1).toUpperCase();
  }

  @override
  List<Object?> get props => [
        id,
        name,
        email,
        studentId,
        department,
        semester,
        avatarUrl,
        role,
        isActive,
        createdAt,
      ];
}
