import 'dart:async';

import 'package:logger/logger.dart';
import 'package:smart_attendance/models/dashboard_model.dart';
import 'package:smart_attendance/services/api_service.dart';

/// Service for real-time attendance data with polling support
class DashboardService {
  final _api = ApiService.instance;
  final _logger = Logger();

  // Polling state
  Timer? _pollingTimer;
  final Duration _pollingInterval = const Duration(seconds: 5);
  final _recordsController = StreamController<List<RealtimeAttendanceRecord>>.broadcast();
  final _statsController = StreamController<AttendanceStats>.broadcast();

  /// Get stream of real-time attendance records
  Stream<List<RealtimeAttendanceRecord>> get recordsStream => _recordsController.stream;

  /// Get stream of attendance statistics
  Stream<AttendanceStats> get statsStream => _statsController.stream;

  /// Fetch real-time attendance for a specific course
  /// 
  /// Expected backend endpoint: GET /api/v1/attendance/live?course_id={courseId}&limit={limit}
  Future<List<RealtimeAttendanceRecord>> getLiveAttendance({
    String? courseId,
    int limit = 50,
  }) async {
    try {
      _logger.d('Fetching live attendance records...');

      final response = await _api.dio.get(
        '/api/v1/attendance/live',
        queryParameters: {
          if (courseId != null) 'course_id': courseId,
          'limit': limit,
        },
      );

      final records = (response.data as List<dynamic>?)
              ?.map((r) => RealtimeAttendanceRecord.fromJson(
                    r as Map<String, dynamic>,
                  ))
              .toList() ??
          [];

      _logger.i('Fetched ${records.length} live attendance records');
      return records;
    } catch (e) {
      _logger.e('Failed to fetch live attendance: $e');
      throw Exception('Failed to fetch live attendance: $e');
    }
  }

  /// Fetch attendance statistics
  /// 
  /// Expected backend endpoint: GET /api/v1/attendance/stats?course_id={courseId}&date={date}
  Future<AttendanceStats> getAttendanceStats({
    String? courseId,
    DateTime? date,
  }) async {
    try {
      _logger.d('Fetching attendance statistics...');

      final response = await _api.dio.get(
        '/api/v1/attendance/stats',
        queryParameters: {
          if (courseId != null) 'course_id': courseId,
          if (date != null) 'date': date.toIso8601String().split('T').first,
        },
      );

      final stats = AttendanceStats.fromJson(
        response.data as Map<String, dynamic>,
      );

      _logger.i('Fetched attendance stats: ${stats.total} total');
      return stats;
    } catch (e) {
      _logger.e('Failed to fetch stats: $e');
      return AttendanceStats(
        totalPresent: 0,
        totalLate: 0,
        totalAbsent: 0,
        totalExcused: 0,
        lastUpdated: DateTime.now(),
      );
    }
  }

  /// Start polling for real-time updates
  void startPolling({
    String? courseId,
  }) {
    _logger.d('Starting polling for real-time attendance...');

    // Cancel existing timer if any
    stopPolling();

    // Initial fetch
    _refreshData(courseId: courseId);

    // Set up periodic polling
    _pollingTimer = Timer.periodic(_pollingInterval, (_) {
      _refreshData(courseId: courseId);
    });
  }

  /// Stop polling for updates
  void stopPolling() {
    _logger.d('Stopping polling...');
    _pollingTimer?.cancel();
    _pollingTimer = null;
  }

  /// Refresh data manually
  Future<void> _refreshData({String? courseId}) async {
    try {
      // Fetch records and stats in parallel
      final recordsResult = await Future.wait([
        getLiveAttendance(courseId: courseId),
        getAttendanceStats(courseId: courseId),
      ]);

      final records = recordsResult[0] as List<RealtimeAttendanceRecord>;
      final stats = recordsResult[1] as AttendanceStats;

      // Emit updates to streams
      _recordsController.add(records);
      _statsController.add(stats);

      _logger.d('Data refreshed: ${records.length} records, ${stats.total} stats');
    } catch (e) {
      _logger.e('Error refreshing data: $e');
    }
  }

  /// Get attendance records for a specific date range (for history)
  /// 
  /// Expected backend endpoint: GET /api/v1/attendance/history
  Future<List<RealtimeAttendanceRecord>> getAttendanceHistory({
    String? courseId,
    DateTime? startDate,
    DateTime? endDate,
    int page = 1,
    int limit = 30,
  }) async {
    try {
      _logger.d('Fetching attendance history...');

      final response = await _api.dio.get(
        '/api/v1/attendance/history',
        queryParameters: {
          if (courseId != null) 'course_id': courseId,
          if (startDate != null)
            'start_date': startDate.toIso8601String().split('T').first,
          if (endDate != null)
            'end_date': endDate.toIso8601String().split('T').first,
          'page': page,
          'limit': limit,
        },
      );

      final records = (response.data as List<dynamic>?)
              ?.map((r) => RealtimeAttendanceRecord.fromJson(
                    r as Map<String, dynamic>,
                  ))
              .toList() ??
          [];

      _logger.i('Fetched ${records.length} history records');
      return records;
    } catch (e) {
      _logger.e('Failed to fetch history: $e');
      throw Exception('Failed to fetch attendance history: $e');
    }
  }

  /// Get attendance summary by status for a time period
  /// 
  /// Expected backend endpoint: GET /api/v1/attendance/summary
  Future<Map<String, int>> getAttendanceSummary({
    String? courseId,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    try {
      _logger.d('Fetching attendance summary...');

      final response = await _api.dio.get(
        '/api/v1/attendance/summary',
        queryParameters: {
          if (courseId != null) 'course_id': courseId,
          if (startDate != null)
            'start_date': startDate.toIso8601String().split('T').first,
          if (endDate != null)
            'end_date': endDate.toIso8601String().split('T').first,
        },
      );

      final summary = Map<String, int>.from(
        response.data as Map<String, dynamic>,
      );

      return summary;
    } catch (e) {
      _logger.e('Failed to fetch summary: $e');
      return {};
    }
  }

  /// Cleanup resources
  void dispose() {
    _logger.d('Disposing DashboardService...');
    stopPolling();
    _recordsController.close();
    _statsController.close();
  }
}
