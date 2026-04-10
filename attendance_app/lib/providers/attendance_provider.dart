import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smart_attendance/models/attendance_model.dart';
import 'package:smart_attendance/models/course_model.dart';
import 'package:smart_attendance/services/attendance_service.dart';

// ── Service Provider ──────────────────────────────────────────────────────────

final attendanceServiceProvider = Provider<AttendanceService>(
  (ref) => AttendanceService(),
);

// ── My Courses ────────────────────────────────────────────────────────────────

final myCoursesProvider = FutureProvider<List<CourseModel>>((ref) async {
  return ref.watch(attendanceServiceProvider).getMyCourses();
});

// ── Attendance Summary ────────────────────────────────────────────────────────

final attendanceSummaryProvider =
    FutureProvider.family<AttendanceSummary, String?>((ref, courseId) async {
  return ref
      .watch(attendanceServiceProvider)
      .getMyAttendanceSummary(courseId: courseId);
});

// ── My Attendance Records ─────────────────────────────────────────────────────

class AttendanceFilter {
  final String? courseId;
  final DateTime? startDate;
  final DateTime? endDate;

  const AttendanceFilter({this.courseId, this.startDate, this.endDate});

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AttendanceFilter &&
        other.courseId == courseId &&
        other.startDate == startDate &&
        other.endDate == endDate;
  }

  @override
  int get hashCode =>
      courseId.hashCode ^ startDate.hashCode ^ endDate.hashCode;
}

final myAttendanceProvider =
    FutureProvider.family<List<AttendanceModel>, AttendanceFilter>(
        (ref, filter) async {
  return ref.watch(attendanceServiceProvider).getMyAttendance(
        courseId: filter.courseId,
        startDate: filter.startDate,
        endDate: filter.endDate,
      );
});

// ── QR Attendance Marking ─────────────────────────────────────────────────────

class QrMarkingState {
  final bool isLoading;
  final bool isSuccess;
  final String? errorMessage;
  final AttendanceModel? result;

  const QrMarkingState({
    this.isLoading = false,
    this.isSuccess = false,
    this.errorMessage,
    this.result,
  });

  QrMarkingState copyWith({
    bool? isLoading,
    bool? isSuccess,
    String? errorMessage,
    AttendanceModel? result,
  }) {
    return QrMarkingState(
      isLoading: isLoading ?? this.isLoading,
      isSuccess: isSuccess ?? this.isSuccess,
      errorMessage: errorMessage,
      result: result ?? this.result,
    );
  }
}

class QrMarkingNotifier extends StateNotifier<QrMarkingState> {
  final AttendanceService _service;

  QrMarkingNotifier(this._service) : super(const QrMarkingState());

  Future<void> markWithQr(String qrToken) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final result = await _service.markAttendanceWithQr(qrToken: qrToken);
      state = state.copyWith(isLoading: false, isSuccess: true, result: result);
    } on Exception catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  void reset() => state = const QrMarkingState();
}

final qrMarkingProvider =
    StateNotifierProvider<QrMarkingNotifier, QrMarkingState>((ref) {
  return QrMarkingNotifier(ref.watch(attendanceServiceProvider));
});

// ── Selected Course Filter ────────────────────────────────────────────────────

final selectedCourseFilterProvider = StateProvider<String?>((ref) => null);
