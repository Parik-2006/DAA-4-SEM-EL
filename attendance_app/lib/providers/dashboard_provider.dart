import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smart_attendance/models/dashboard_model.dart';
import 'package:smart_attendance/services/dashboard_service.dart';

// ── Dashboard Service Provider ─────────────────────────────────────────────────

final dashboardServiceProvider = Provider<DashboardService>((ref) {
  final service = DashboardService();
  
  // Cleanup when provider is disposed
  ref.onDispose(() {
    service.dispose();
  });

  return service;
});

// ── Real-time Attendance Records Stream ────────────────────────────────────────

class RealtimeAttendanceState {
  final List<RealtimeAttendanceRecord> records;
  final bool isLoading;
  final String? error;
  final bool isPolling;
  final DateTime? lastSyncTime;

  const RealtimeAttendanceState({
    this.records = const [],
    this.isLoading = false,
    this.error,
    this.isPolling = false,
    this.lastSyncTime,
  });

  RealtimeAttendanceState copyWith({
    List<RealtimeAttendanceRecord>? records,
    bool? isLoading,
    String? error,
    bool? isPolling,
    DateTime? lastSyncTime,
  }) {
    return RealtimeAttendanceState(
      records: records ?? this.records,
      isLoading: isLoading ?? this.isLoading,
      error: error ?? this.error,
      isPolling: isPolling ?? this.isPolling,
      lastSyncTime: lastSyncTime ?? this.lastSyncTime,
    );
  }
}

class RealtimeAttendanceNotifier extends StateNotifier<RealtimeAttendanceState> {
  final DashboardService _dashboardService;
  StreamSubscription? _subscription;

  RealtimeAttendanceNotifier(this._dashboardService)
      : super(const RealtimeAttendanceState());

  /// Start real-time polling
  void startPolling({String? courseId}) {
    state = state.copyWith(isPolling: true);
    
    _dashboardService.startPolling(courseId: courseId);
    
    // Listen to records stream
    _subscription = _dashboardService.recordsStream.listen(
      (records) {
        state = state.copyWith(
          records: records,
          isLoading: false,
          error: null,
          lastSyncTime: DateTime.now(),
        );
      },
      onError: (e) {
        state = state.copyWith(
          error: e.toString(),
          isLoading: false,
        );
      },
    );
  }

  /// Stop polling
  void stopPolling() {
    _subscription?.cancel();
    _dashboardService.stopPolling();
    state = state.copyWith(isPolling: false);
  }

  /// Manually refresh data
  Future<void> refreshData({String? courseId}) async {
    state = state.copyWith(isLoading: true);
    try {
      final records = await _dashboardService.getLiveAttendance(courseId: courseId);
      state = state.copyWith(
        records: records,
        isLoading: false,
        error: null,
        lastSyncTime: DateTime.now(),
      );
    } catch (e) {
      state = state.copyWith(
        error: e.toString(),
        isLoading: false,
      );
    }
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _dashboardService.stopPolling();
    super.dispose();
  }
}

final realtimeAttendanceProvider =
    StateNotifierProvider<RealtimeAttendanceNotifier, RealtimeAttendanceState>(
        (ref) {
  final service = ref.watch(dashboardServiceProvider);
  return RealtimeAttendanceNotifier(service);
});

// ── Attendance Stats Stream ────────────────────────────────────────────────────

class AttendanceStatsState {
  final AttendanceStats stats;
  final bool isLoading;
  final String? error;

  const AttendanceStatsState({
    required this.stats,
    this.isLoading = false,
    this.error,
  });

  AttendanceStatsState copyWith({
    AttendanceStats? stats,
    bool? isLoading,
    String? error,
  }) {
    return AttendanceStatsState(
      stats: stats ?? this.stats,
      isLoading: isLoading ?? this.isLoading,
      error: error ?? this.error,
    );
  }
}

class AttendanceStatsNotifier extends StateNotifier<AttendanceStatsState> {
  final DashboardService _dashboardService;
  StreamSubscription? _subscription;

  AttendanceStatsNotifier(this._dashboardService)
      : super(AttendanceStatsState(
          stats: AttendanceStats(
            totalPresent: 0,
            totalLate: 0,
            totalAbsent: 0,
            totalExcused: 0,
            lastUpdated: DateTime.now(),
          ),
        ));

  /// Start listening to stats updates
  void startListening() {
    _subscription = _dashboardService.statsStream.listen(
      (stats) {
        state = state.copyWith(
          stats: stats,
          isLoading: false,
          error: null,
        );
      },
      onError: (e) {
        state = state.copyWith(
          error: e.toString(),
          isLoading: false,
        );
      },
    );
  }

  /// Fetch stats manually
  Future<void> fetchStats({
    String? courseId,
    DateTime? date,
  }) async {
    state = state.copyWith(isLoading: true);
    try {
      final stats =
          await _dashboardService.getAttendanceStats(courseId: courseId, date: date);
      state = state.copyWith(
        stats: stats,
        isLoading: false,
        error: null,
      );
    } catch (e) {
      state = state.copyWith(
        error: e.toString(),
        isLoading: false,
      );
    }
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }
}

final attendanceStatsProvider =
    StateNotifierProvider<AttendanceStatsNotifier, AttendanceStatsState>((ref) {
  final service = ref.watch(dashboardServiceProvider);
  return AttendanceStatsNotifier(service);
});

// ── Attendance History Provider ────────────────────────────────────────────────

class AttendanceHistoryFilter {
  final String? courseId;
  final DateTime? startDate;
  final DateTime? endDate;
  final int page;
  final int limit;

  const AttendanceHistoryFilter({
    this.courseId,
    this.startDate,
    this.endDate,
    this.page = 1,
    this.limit = 30,
  });

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AttendanceHistoryFilter &&
        other.courseId == courseId &&
        other.startDate == startDate &&
        other.endDate == endDate &&
        other.page == page &&
        other.limit == limit;
  }

  @override
  int get hashCode =>
      courseId.hashCode ^
      startDate.hashCode ^
      endDate.hashCode ^
      page.hashCode ^
      limit.hashCode;
}

final attendanceHistoryProvider = FutureProvider.family<
    List<RealtimeAttendanceRecord>,
    AttendanceHistoryFilter>((ref, filter) async {
  final service = ref.watch(dashboardServiceProvider);
  return service.getAttendanceHistory(
    courseId: filter.courseId,
    startDate: filter.startDate,
    endDate: filter.endDate,
    page: filter.page,
    limit: filter.limit,
  );
});

// ── Attendance Summary Provider ────────────────────────────────────────────────

class AttendanceSummaryFilter {
  final String? courseId;
  final DateTime? startDate;
  final DateTime? endDate;

  const AttendanceSummaryFilter({
    this.courseId,
    this.startDate,
    this.endDate,
  });

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AttendanceSummaryFilter &&
        other.courseId == courseId &&
        other.startDate == startDate &&
        other.endDate == endDate;
  }

  @override
  int get hashCode =>
      courseId.hashCode ^ startDate.hashCode ^ endDate.hashCode;
}

final attendanceSummaryProvider = FutureProvider.family<Map<String, int>,
    AttendanceSummaryFilter>((ref, filter) async {
  final service = ref.watch(dashboardServiceProvider);
  return service.getAttendanceSummary(
    courseId: filter.courseId,
    startDate: filter.startDate,
    endDate: filter.endDate,
  );
});
