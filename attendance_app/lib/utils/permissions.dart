import 'package:smart_attendance/models/user_model.dart';

class PermissionManager {
  static bool canMarkAttendance(UserRole role) {
    return role == UserRole.admin || role == UserRole.student;
  }

  static bool canViewAllAttendance(UserRole role) {
    return role == UserRole.admin;
  }

  static bool canManageUsers(UserRole role) {
    return role == UserRole.admin;
  }

  static bool canRegisterStudents(UserRole role) {
    return role == UserRole.admin;
  }

  static bool canViewOwnAttendance(UserRole role) {
    return role == UserRole.admin || role == UserRole.student;
  }

  static bool canViewReports(UserRole role) {
    return role == UserRole.admin;
  }

  static bool isAdmin(UserRole role) {
    return role == UserRole.admin;
  }

  static bool isStudent(UserRole role) {
    return role == UserRole.student;
  }
}
