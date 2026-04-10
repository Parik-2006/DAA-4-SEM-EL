import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:smart_attendance/components/attendance_record_card.dart';
import 'package:smart_attendance/components/statistics_card.dart';
import 'package:smart_attendance/models/dashboard_model.dart';
import 'package:smart_attendance/providers/attendance_provider.dart';
import 'package:smart_attendance/providers/dashboard_provider.dart';
import 'package:smart_attendance/theme/app_theme.dart';

class AttendanceDashboardScreen extends ConsumerStatefulWidget {
  const AttendanceDashboardScreen({super.key});

  @override
  ConsumerState<AttendanceDashboardScreen> createState() =>
      _AttendanceDashboardScreenState();
}

class _AttendanceDashboardScreenState
    extends ConsumerState<AttendanceDashboardScreen>
    with WidgetsBindingObserver {
  String? _selectedCourseId;
  late ScrollController _scrollController;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _scrollController = ScrollController();

    // Start polling on screen load
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref
          .read(realtimeAttendanceProvider.notifier)
          .startPolling(courseId: _selectedCourseId);
      ref.read(attendanceStatsProvider.notifier).startListening();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    ref.read(realtimeAttendanceProvider.notifier).stopPolling();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:
        // Resume polling when app comes to foreground
        ref
            .read(realtimeAttendanceProvider.notifier)
            .startPolling(courseId: _selectedCourseId);
        break;
      case AppLifecycleState.paused:
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
        // Stop polling when app goes to background
        ref.read(realtimeAttendanceProvider.notifier).stopPolling();
        break;
      case AppLifecycleState.inactive:
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final coursesAsync = ref.watch(myCoursesProvider);
    final realtimeAttendance = ref.watch(realtimeAttendanceProvider);
    final attendanceStats = ref.watch(attendanceStatsProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Live Attendance'),
        backgroundColor: AppColors.surface,
        elevation: 0,
        actions: [
          // Refresh button
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: GestureDetector(
                onTap: () {
                  ref
                      .read(realtimeAttendanceProvider.notifier)
                      .refreshData(courseId: _selectedCourseId);
                  ref.read(attendanceStatsProvider.notifier).fetchStats(
                        courseId: _selectedCourseId,
                      );
                },
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    realtimeAttendance.isLoading
                        ? Icons.refresh_rounded
                        : Icons.refresh_outlined,
                    color: AppColors.primary,
                    size: 20,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Course filter
          coursesAsync.when(
            data: (courses) => _buildCourseFilter(courses),
            loading: () => const SizedBox(height: 56),
            error: (_, __) => const SizedBox.shrink(),
          ),

          // Main content
          Expanded(
            child: realtimeAttendance.isLoading &&
                    realtimeAttendance.records.isEmpty
                ? const Center(
                    child: CircularProgressIndicator(),
                  )
                : RefreshIndicator(
                    onRefresh: () => ref
                        .read(realtimeAttendanceProvider.notifier)
                        .refreshData(courseId: _selectedCourseId),
                    child: CustomScrollView(
                      controller: _scrollController,
                      slivers: [
                        // Statistics section
                        SliverToBoxAdapter(
                          child: Padding(
                            padding: const EdgeInsets.all(20),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Status indicator
                                _buildStatusIndicator(realtimeAttendance),
                                const SizedBox(height: 20),

                                // Stats cards
                                attendanceStats.isLoading
                                    ? const Center(
                                        child: CircularProgressIndicator(),
                                      )
                                    : _buildStatisticsCards(attendanceStats.stats),
                              ],
                            ),
                          ),
                        ),

                        // Attendance records
                        SliverPadding(
                          padding: const EdgeInsets.symmetric(horizontal: 20),
                          sliver: SliverToBoxAdapter(
                            child: Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    'Recent Check-ins',
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleLarge
                                        ?.copyWith(
                                          fontWeight: FontWeight.w600,
                                        ),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 6,
                                    ),
                                    decoration: BoxDecoration(
                                      color: AppColors.primary.withOpacity(0.1),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Text(
                                      '${realtimeAttendance.records.length}',
                                      style: TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600,
                                        color: AppColors.primary,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),

                        // Records list
                        if (realtimeAttendance.records.isEmpty)
                          SliverFillRemaining(
                            child: Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.remove_circle_outline,
                                    size: 48,
                                    color: AppColors.grey300,
                                  ),
                                  const SizedBox(height: 12),
                                  Text(
                                    'No attendance records',
                                    style: TextStyle(
                                      color: AppColors.grey500,
                                      fontSize: 14,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          )
                        else
                          SliverPadding(
                            padding: const EdgeInsets.fromLTRB(0, 0, 0, 32),
                            sliver: SliverList.separated(
                              itemCount: realtimeAttendance.records.length,
                              separatorBuilder: (_, __) =>
                                  const SizedBox(height: 10),
                              itemBuilder: (context, index) {
                                final record =
                                    realtimeAttendance.records[index];
                                return Padding(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 20,
                                  ),
                                  child: AttendanceRecordCard(
                                    studentName: record.studentName,
                                    studentId: record.studentId,
                                    status: record.status,
                                    markedAt: record.markedAt,
                                    avatarUrl: record.avatarUrl,
                                    confidence: record.confidence,
                                  ),
                                );
                              },
                            ),
                          ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  /// Build course filter chips
  Widget _buildCourseFilter(List<dynamic> courses) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Filter by Course',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                // All courses chip
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: const Text('All'),
                    selected: _selectedCourseId == null,
                    onSelected: (_) {
                      setState(() => _selectedCourseId = null);
                      ref
                          .read(realtimeAttendanceProvider.notifier)
                          .startPolling();
                    },
                  ),
                ),

                // Course chips
                ...courses.map((course) {
                  final courseCode =
                      course.code ?? 'Course'; // Assuming code property
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      label: Text(courseCode),
                      selected: _selectedCourseId == course.id,
                      onSelected: (_) {
                        setState(() => _selectedCourseId = course.id);
                        ref
                            .read(realtimeAttendanceProvider.notifier)
                            .startPolling(courseId: course.id);
                      },
                    ),
                  );
                }),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Build status indicator
  Widget _buildStatusIndicator(RealtimeAttendanceState state) {
    final isPolling = state.isPolling;
    final lastSync = state.lastSyncTime;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isPolling ? AppColors.success.withOpacity(0.08) : Colors.grey.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isPolling ? AppColors.success.withOpacity(0.3) : Colors.grey.withOpacity(0.3),
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isPolling ? AppColors.success : Colors.grey,
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                isPolling ? 'Live Updates Enabled' : 'Updating...',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: isPolling ? AppColors.success : Colors.grey,
                ),
              ),
              if (lastSync != null)
                Text(
                  'Last sync: ${DateFormat('HH:mm:ss').format(lastSync)}',
                  style: const TextStyle(
                    fontSize: 10,
                    color: AppColors.grey500,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  /// Build statistics cards
  Widget _buildStatisticsCards(AttendanceStats stats) {
    return StatisticsGrid(
      columns: 2,
      cards: [
        StatisticsCardData(
          title: 'Present',
          value: stats.totalPresent,
          subtitle: '${stats.presentPercent.toStringAsFixed(1)}%',
          backgroundColor: AppColors.success,
          icon: Icons.check_circle,
          percentage: stats.presentPercent,
        ),
        StatisticsCardData(
          title: 'Late',
          value: stats.totalLate,
          subtitle: '${stats.latePercent.toStringAsFixed(1)}%',
          backgroundColor: AppColors.warning,
          icon: Icons.schedule,
          percentage: stats.latePercent,
        ),
        StatisticsCardData(
          title: 'Absent',
          value: stats.totalAbsent,
          subtitle: '${stats.absentPercent.toStringAsFixed(1)}%',
          backgroundColor: AppColors.error,
          icon: Icons.cancel,
          percentage: stats.absentPercent,
        ),
        StatisticsCardData(
          title: 'Excused',
          value: stats.totalExcused,
          subtitle: 'Excused',
          backgroundColor: AppColors.info,
          icon: Icons.info,
        ),
      ],
    );
  }
}
